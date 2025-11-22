import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel, cosine_similarity
from collections import defaultdict
from functools import lru_cache
import logging
import time

logger = logging.getLogger(__name__)

# --------------------------------------------------
# GLOBAL VARIABLES
# --------------------------------------------------
MOVIES_DF = None
TFIDF_MATRIX = None
TFIDF_VECT = None
TRENDING_CACHE = {"data": {}, "last_update": 0}


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def safe_join(list_obj, sep=", "):
    if not list_obj:
        return ""
    if isinstance(list_obj, str):
        return list_obj
    return sep.join([str(x) for x in list_obj if x])


# --------------------------------------------------
# PRELOAD MOVIES + TFIDF MATRIX
# --------------------------------------------------
def preload_movies_and_tfidf(cur, tfidf_matrix_path="tfidf_matrix.pkl", tfidf_vect_path="tfidf_vect.pkl"):
    """
    Loads MOVIES_DF, TFIDF_MATRIX, TFIDF_VECT once at startup.
    If already loaded → skips reloading.
    """

    global MOVIES_DF, TFIDF_MATRIX, TFIDF_VECT

    # Skip if already loaded
    if MOVIES_DF is not None and TFIDF_MATRIX is not None:
        return

    # ---- Load Movies ----
    cur.execute("""
        SELECT id, title, overview, genres, original_language, poster_path
        FROM movies
        WHERE id IS NOT NULL AND popularity > 1.0
    """)

    rows = cur.fetchall()
    columns = ['movie_id', 'title', 'overview', 'genres', 'language', 'poster_path']
    df = pd.DataFrame(rows, columns=columns)

    df['overview'] = df['overview'].fillna('')
    df['genres'] = df['genres'].fillna('')
    df['language'] = df['language'].fillna('')

    MOVIES_DF = df

    # ---- Try Loading Precomputed TFIDF ----
    try:
        TFIDF_MATRIX = joblib.load(tfidf_matrix_path)
        TFIDF_VECT = joblib.load(tfidf_vect_path)
        logger.info("Loaded precomputed TFIDF matrix")

    except Exception as e:
        logger.error("TFIDF Cache Missing → Recomputing: %s", e)

        df['genres_clean'] = df['genres'].str.replace(',', ' ')
        df['content'] = (
            df['title'].fillna('') + ' ' +
            df['genres_clean'].fillna('') + ' ' +
            df['language'].fillna('') + ' ' +
            df['overview'].fillna('')
        )

        tfidf = TfidfVectorizer(max_features=10000, stop_words='english')
        TFIDF_MATRIX = tfidf.fit_transform(df['content'])
        TFIDF_VECT = tfidf

        joblib.dump(TFIDF_MATRIX, tfidf_matrix_path)
        joblib.dump(TFIDF_VECT, tfidf_vect_path)

        logger.info("TFIDF matrix computed & cached")


# --------------------------------------------------
# USER PREFS / WATCHLIST / WATCHED
# --------------------------------------------------
def load_user_preferences(cur, user_id):
    prefs = {"language": set(), "genre": set()}

    try:
        cur.execute("SELECT preference_type, preference_value FROM user_preferences WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()

        for t, v in rows:
            if t in prefs:
                prefs[t].add(v)

    except Exception as e:
        logger.info("Could not load user preferences: %s", e)

    return prefs


def get_user_watched_and_watchlist(cur, user_id):
    watched, watchlist = set(), set()

    try:
        cur.execute("SELECT movie_id FROM already_watched WHERE user_id=%s", (user_id,))
        watched.update([row[0] for row in cur.fetchall()])
    except:
        pass

    try:
        cur.execute("SELECT movie_id FROM watchlist WHERE user_id=%s", (user_id,))
        watchlist.update([row[0] for row in cur.fetchall()])
    except:
        pass

    return watched, watchlist


# --------------------------------------------------
# CONTENT-BASED FILTERING
# --------------------------------------------------
def content_recommend_for_user(user_id, cur, top_k=30):
    global MOVIES_DF, TFIDF_MATRIX

    df = MOVIES_DF
    tfidf_matrix = TFIDF_MATRIX

    prefs = load_user_preferences(cur, user_id)
    watched, watchlist = get_user_watched_and_watchlist(cur, user_id)

    mask = pd.Series([False] * len(df))

    # If user has preferences → filter
    if prefs["genre"] or prefs["language"]:
        for i, row in df.iterrows():
            genres = set([g.strip() for g in str(row["genres"]).split(",") if g.strip()])
            lang = row["language"]

            if (prefs["genre"] and genres.intersection(prefs["genre"])) or \
               (prefs["language"] and lang in prefs["language"]):
                mask.iat[i] = True
    else:
        mask[:] = True

    candidate_idx = np.where(mask)[0]
    if len(candidate_idx) == 0:
        candidate_idx = np.arange(len(df))

    watched_idx = df[df['movie_id'].isin(watched)].index.tolist()

    # User Profile Vector
    if watched_idx:
        user_vec = tfidf_matrix[watched_idx].mean(axis=0)
    else:
        user_vec = tfidf_matrix[candidate_idx].mean(axis=0)

    user_vec = np.asarray(user_vec).reshape(1, -1)

    cosine_sim = linear_kernel(user_vec, tfidf_matrix).flatten()

    # Remove watched + watchlist
    for i, mid in enumerate(df['movie_id'].values):
        if mid in watched or mid in watchlist:
            cosine_sim[i] = -1

    top_idx = np.argsort(-cosine_sim)[:top_k]

    recs = []
    for idx in top_idx:
        recs.append((
            int(df.iloc[idx]['movie_id']),
            df.iloc[idx]['title'],
            float(cosine_sim[idx]),
            df.iloc[idx]['poster_path']
        ))

    return recs


# --------------------------------------------------
# COLLABORATIVE FILTERING
# --------------------------------------------------
def load_user_ratings(cur):
    try:
        cur.execute("SELECT user_id, movie_id, rating FROM reviews WHERE rating IS NOT NULL")
        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame(columns=['user_id', 'movie_id', 'rating'])
        return pd.DataFrame(rows, columns=['user_id', 'movie_id', 'rating'])
    except:
        return pd.DataFrame(columns=['user_id', 'movie_id', 'rating'])


def collaborative_recommend_for_user(user_id, cur, top_k=30):
    global MOVIES_DF
    df = MOVIES_DF

    ratings_df = load_user_ratings(cur)
    if ratings_df.empty or user_id not in ratings_df["user_id"].unique():
        return []

    pivot = ratings_df.pivot_table(index="user_id", columns="movie_id",
                                   values="rating").fillna(0)

    user_vector = pivot.loc[user_id].values.reshape(1, -1)
    sims = cosine_similarity(user_vector, pivot.values).flatten()

    sim_df = pd.DataFrame({"user_id": pivot.index, "sim": sims})
    sim_df = sim_df[(sim_df["user_id"] != user_id) & (sim_df["sim"] > 0)]
    sim_df = sim_df.sort_values("sim", ascending=False).head(50)

    watched, _ = get_user_watched_and_watchlist(cur, user_id)

    weighted_scores = defaultdict(float)
    sim_sums = defaultdict(float)

    for _, row in sim_df.iterrows():
        other = row["user_id"]
        sim = row["sim"]

        other_ratings = pivot.loc[other]
        for mid, rating in other_ratings.items():
            if rating and mid not in watched:
                weighted_scores[mid] += sim * rating
                sim_sums[mid] += sim

    predictions = [
        (mid, weighted_scores[mid] / sim_sums[mid])
        for mid in weighted_scores if sim_sums[mid] > 0
    ]

    predictions.sort(key=lambda x: -x[1])

    recs = []
    for mid, score in predictions[:top_k]:
        row = df[df['movie_id'] == mid]
        if not row.empty:
            recs.append((mid, row.iloc[0]['title'], score, row.iloc[0]['poster_path']))

    return recs


# --------------------------------------------------
# TRENDING MOVIES CACHE
# --------------------------------------------------
def get_trending_movies(cur, ttl=1800):
    """Cache trending movies for 30 mins."""
    global TRENDING_CACHE
    now = time.time()

    if TRENDING_CACHE['data'] and (now - TRENDING_CACHE['last_update'] < ttl):
        return TRENDING_CACHE['data']

    try:
        cur.execute(GET_TRENDING_MOVIES)
        rows = cur.fetchall()

        trending_scores = {}
        for row in rows:
            movie_id, title, poster_path, popularity, vote_avg, vote_cnt, release_date = row
            score = popularity + (vote_avg * vote_cnt) / (vote_cnt + 100)
            trending_scores[int(movie_id)] = score

        TRENDING_CACHE['data'] = trending_scores
        TRENDING_CACHE['last_update'] = now

        return trending_scores

    except:
        return {}


# --------------------------------------------------
# HYBRID RECOMMENDER (MAIN FUNCTION)
# --------------------------------------------------
@lru_cache(maxsize=1024)
def hybrid_recommendations_cached(user_id):
    from flask import g
    cur = g.db_cursor

    # Ensure preload executed
    if MOVIES_DF is None or TFIDF_MATRIX is None:
        preload_movies_and_tfidf(cur)

    return hybrid_recommendations(user_id, cur)


def hybrid_recommendations(user_id, cur,
                           top_k=20,
                           content_weight=0.5,
                           cf_weight=0.3,
                           trending_weight=0.2):

    global MOVIES_DF, TFIDF_MATRIX

    # Ensure preload executed
    if MOVIES_DF is None or TFIDF_MATRIX is None:
        preload_movies_and_tfidf(cur)

    df = MOVIES_DF

    if df is None or df.empty:
        logger.error("MOVIES_DF is empty → cannot generate recommendations")
        return []

    content_recs = content_recommend_for_user(user_id, cur, top_k=200)
    cf_recs = collaborative_recommend_for_user(user_id, cur, top_k=200)
    trending_scores = get_trending_movies(cur)

    def normalize(recs):
        if not recs:
            return {}
        arr = np.array([r[2] for r in recs], float)
        minv, maxv = arr.min(), arr.max()
        return {
            r[0]: 1.0 if maxv == minv else (r[2] - minv) / (maxv - minv)
            for r in recs
        }

    c_scores = normalize(content_recs)
    cf_scores = normalize(cf_recs)

    # Trending normalization
    trending_norm = {}
    if trending_scores:
        vals = np.array(list(trending_scores.values()), float)
        minv, maxv = vals.min(), vals.max()
        trending_norm = {
            mid: 1.0 if maxv == minv else (s - minv) / (maxv - minv)
            for mid, s in trending_scores.items()
        }

    # Blending
    final_scores = {}
    all_ids = set(c_scores) | set(cf_scores) | set(trending_norm)
    for mid in all_ids:
        final_scores[mid] = (
            content_weight * c_scores.get(mid, 0) +
            cf_weight * cf_scores.get(mid, 0) +
            trending_weight * trending_norm.get(mid, 0)
        )

    # Sort top K
    sorted_final = sorted(final_scores.items(), key=lambda x: -x[1])[:top_k]

    result = []
    for mid, score in sorted_final:
        row = df[df['movie_id'] == mid]
        if row.empty:
            continue

        poster = row.iloc[0]['poster_path']
        poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None

        result.append({
            "movie_id": int(mid),
            "title": row.iloc[0]["title"],
            "score": float(score),
            "poster_path": poster_url
        })

    return result
