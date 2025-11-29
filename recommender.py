import pandas as pd
import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from scipy.sparse import csr_matrix, vstack
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
MOVIE_ID_TO_INDEX = {}  # NEW: Fast movie ID lookup
INDEX_TO_MOVIE_ID = {}  # NEW: Reverse mapping


# --------------------------------------------------
# PRELOAD MOVIES + TFIDF MATRIX (OPTIMIZED)
# --------------------------------------------------
def preload_movies_and_tfidf(cur, tfidf_matrix_path="tfidf_matrix.pkl", tfidf_vect_path="tfidf_vect.pkl"):
    """
    Loads MOVIES_DF, TFIDF_MATRIX, TFIDF_VECT once at startup.
    OPTIMIZATIONS:
    - Added index mappings for O(1) movie ID lookups
    - Reduced memory with efficient dtypes
    """
    global MOVIES_DF, TFIDF_MATRIX, TFIDF_VECT, MOVIE_ID_TO_INDEX, INDEX_TO_MOVIE_ID

    if MOVIES_DF is not None and TFIDF_MATRIX is not None:
        return

    # Load Movies with optimized dtypes
    cur.execute("""
        SELECT id, title, overview, genres, original_language, poster_path
        FROM movies
        WHERE id IS NOT NULL AND popularity > 1.0
    """)

    rows = cur.fetchall()
    columns = ['movie_id', 'title', 'overview', 'genres', 'language', 'poster_path']
    df = pd.DataFrame(rows, columns=columns)

    # Optimize memory usage
    df['movie_id'] = df['movie_id'].astype('int32')
    df['overview'] = df['overview'].fillna('').astype('string')
    df['genres'] = df['genres'].fillna('').astype('string')
    df['language'] = df['language'].fillna('').astype('string')
    df['title'] = df['title'].astype('string')
    df['poster_path'] = df['poster_path'].astype('string')

    # Create fast lookup indices
    MOVIE_ID_TO_INDEX = {mid: idx for idx, mid in enumerate(df['movie_id'].values)}
    INDEX_TO_MOVIE_ID = {idx: mid for mid, idx in MOVIE_ID_TO_INDEX.items()}

    MOVIES_DF = df

    # Try Loading Precomputed TFIDF
    try:
        TFIDF_MATRIX = joblib.load(tfidf_matrix_path)
        TFIDF_VECT = joblib.load(tfidf_vect_path)
        logger.info("Loaded precomputed TFIDF matrix")

    except Exception as e:
        logger.error("TFIDF Cache Missing → Recomputing: %s", e)

        # Vectorized string operations
        df['content'] = (
            df['title'] + ' ' +
            df['genres'].str.replace(',', ' ', regex=False) + ' ' +
            df['language'] + ' ' +
            df['overview']
        )

        tfidf = TfidfVectorizer(max_features=10000, stop_words='english', dtype=np.float32)
        TFIDF_MATRIX = tfidf.fit_transform(df['content'])
        TFIDF_VECT = tfidf

        joblib.dump(TFIDF_MATRIX, tfidf_matrix_path)
        joblib.dump(TFIDF_VECT, tfidf_vect_path)

        logger.info("TFIDF matrix computed & cached")


# --------------------------------------------------
# USER PREFS / WATCHLIST / WATCHED (OPTIMIZED)
# --------------------------------------------------
# Simple in-memory cache with timestamps
USER_PREFS_CACHE = {}
USER_WATCHED_CACHE = {}
CACHE_TTL = 300  # 5 minutes

def load_user_preferences(user_id, cur):
    """Cache user preferences with time-based invalidation"""
    global USER_PREFS_CACHE
    
    now = time.time()
    cache_key = user_id
    
    # Check cache
    if cache_key in USER_PREFS_CACHE:
        cached_data, timestamp = USER_PREFS_CACHE[cache_key]
        if now - timestamp < CACHE_TTL:
            return cached_data
    
    prefs = {"language": set(), "genre": set()}

    try:
        cur.execute("SELECT preference_type, preference_value FROM user_preferences WHERE user_id=%s", (user_id,))
        rows = cur.fetchall()

        for t, v in rows:
            if t in prefs:
                prefs[t].add(v)

    except Exception as e:
        logger.debug("Could not load user preferences: %s", e)

    # Update cache
    USER_PREFS_CACHE[cache_key] = (prefs, now)
    return prefs


def get_user_watched_and_watchlist(user_id, cur):
    """Cache watched/watchlist with time-based invalidation"""
    global USER_WATCHED_CACHE
    
    now = time.time()
    cache_key = user_id
    
    # Check cache
    if cache_key in USER_WATCHED_CACHE:
        cached_data, timestamp = USER_WATCHED_CACHE[cache_key]
        if now - timestamp < CACHE_TTL:
            return cached_data
    
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

    result = (frozenset(watched), frozenset(watchlist))
    
    # Update cache
    USER_WATCHED_CACHE[cache_key] = (result, now)
    return result


# --------------------------------------------------
# CONTENT-BASED FILTERING (OPTIMIZED)
# --------------------------------------------------
def content_recommend_for_user(user_id, cur, top_k=30):
    """
    OPTIMIZATIONS:
    - Removed slow iterrows() loop
    - Vectorized genre/language filtering
    - Used boolean indexing instead of loops
    - Fast movie ID lookups with index mapping
    """
    global MOVIES_DF, TFIDF_MATRIX, MOVIE_ID_TO_INDEX

    # Ensure data is loaded
    if MOVIES_DF is None or TFIDF_MATRIX is None:
        preload_movies_and_tfidf(cur)

    df = MOVIES_DF
    tfidf_matrix = TFIDF_MATRIX

    prefs = load_user_preferences(user_id, cur)
    watched, watchlist = get_user_watched_and_watchlist(user_id, cur)

    # Vectorized preference filtering
    if prefs["genre"] or prefs["language"]:
        genre_match = df['genres'].str.contains('|'.join(prefs["genre"]), case=False, na=False) if prefs["genre"] else False
        lang_match = df['language'].isin(prefs["language"]) if prefs["language"] else False
        mask = genre_match | lang_match
        candidate_idx = np.where(mask)[0]
    else:
        candidate_idx = np.arange(len(df))

    if len(candidate_idx) == 0:
        candidate_idx = np.arange(len(df))

    # Fast index lookup for watched movies
    watched_idx = [MOVIE_ID_TO_INDEX[mid] for mid in watched if mid in MOVIE_ID_TO_INDEX]

    # User Profile Vector
    if watched_idx:
        user_vec = tfidf_matrix[watched_idx].mean(axis=0)
    else:
        user_vec = tfidf_matrix[candidate_idx].mean(axis=0)

    user_vec = np.asarray(user_vec).reshape(1, -1)

    # Compute similarities (using sparse matrix operations)
    cosine_sim = linear_kernel(user_vec, tfidf_matrix).flatten()

    # Vectorized exclusion of watched/watchlist
    exclude_ids = watched | watchlist
    exclude_idx = np.array([MOVIE_ID_TO_INDEX[mid] for mid in exclude_ids if mid in MOVIE_ID_TO_INDEX])
    if len(exclude_idx) > 0:
        cosine_sim[exclude_idx] = -1

    # Get top K
    top_idx = np.argpartition(-cosine_sim, min(top_k, len(cosine_sim)-1))[:top_k]
    top_idx = top_idx[np.argsort(-cosine_sim[top_idx])]

    # Build results using iloc (faster than repeated filtering)
    recs = [
        (
            int(df.iloc[idx]['movie_id']),
            df.iloc[idx]['title'],
            float(cosine_sim[idx]),
            df.iloc[idx]['poster_path']
        )
        for idx in top_idx if cosine_sim[idx] > 0
    ]

    return recs


# --------------------------------------------------
# COLLABORATIVE FILTERING (OPTIMIZED)
# --------------------------------------------------
RATINGS_CACHE = {"data": None, "last_update": 0}
RATINGS_CACHE_TTL = 600  # 10 minutes

def load_user_ratings_cached(cur):
    """Cache the ratings DataFrame with time-based invalidation"""
    global RATINGS_CACHE
    
    now = time.time()
    
    # Check cache
    if RATINGS_CACHE['data'] is not None and (now - RATINGS_CACHE['last_update'] < RATINGS_CACHE_TTL):
        return RATINGS_CACHE['data']
    
    try:
        cur.execute("SELECT user_id, movie_id, rating FROM reviews WHERE rating IS NOT NULL")
        rows = cur.fetchall()
        if not rows:
            df = pd.DataFrame(columns=['user_id', 'movie_id', 'rating'])
        else:
            df = pd.DataFrame(rows, columns=['user_id', 'movie_id', 'rating'])
            df['user_id'] = df['user_id'].astype('int32')
            df['movie_id'] = df['movie_id'].astype('int32')
            df['rating'] = df['rating'].astype('float32')
        
        # Update cache
        RATINGS_CACHE['data'] = df
        RATINGS_CACHE['last_update'] = now
        return df
    except Exception as e:
        logger.error(f"Error loading ratings: {e}")
        return pd.DataFrame(columns=['user_id', 'movie_id', 'rating'])


def collaborative_recommend_for_user(user_id, cur, top_k=30):
    """
    OPTIMIZATIONS:
    - Cached ratings DataFrame
    - Reduced similarity computation to top 50 users only
    - Optimized dtype usage (float32 vs float64)
    - Vectorized operations
    """
    global MOVIES_DF, MOVIE_ID_TO_INDEX

    # Ensure data is loaded
    if MOVIES_DF is None:
        preload_movies_and_tfidf(cur)

    df = MOVIES_DF
    ratings_df = load_user_ratings_cached(cur)
    
    if ratings_df.empty or user_id not in ratings_df["user_id"].unique():
        return []

    # Use sparse matrix for memory efficiency
    pivot = ratings_df.pivot_table(
        index="user_id", 
        columns="movie_id",
        values="rating", 
        fill_value=0
    ).astype('float32')

    if user_id not in pivot.index:
        return []

    user_vector = pivot.loc[user_id].values.reshape(1, -1)
    
    # Compute similarities efficiently
    from sklearn.metrics.pairwise import cosine_similarity
    sims = cosine_similarity(user_vector, pivot.values, dense_output=True).flatten()

    # Get top similar users (limit to 50 for speed)
    sim_users_idx = np.argpartition(-sims, min(50, len(sims)-1))[:50]
    sim_users_idx = sim_users_idx[sim_users_idx != np.where(pivot.index == user_id)[0][0]]
    sim_users_idx = sim_users_idx[sims[sim_users_idx] > 0]
    
    if len(sim_users_idx) == 0:
        return []

    watched, _ = get_user_watched_and_watchlist(user_id, cur)

    # Vectorized weighted score computation
    similar_users_ratings = pivot.iloc[sim_users_idx]
    similarities = sims[sim_users_idx].reshape(-1, 1)
    
    weighted_sum = (similar_users_ratings.values * similarities).sum(axis=0)
    sim_sum = (similarities * (similar_users_ratings.values > 0)).sum(axis=0)
    
    # Avoid division by zero
    predictions = np.divide(weighted_sum, sim_sum, where=sim_sum > 0, out=np.zeros_like(weighted_sum))
    
    # Get movie IDs and filter watched
    movie_ids = pivot.columns.values
    valid_mask = (predictions > 0) & (~np.isin(movie_ids, list(watched)))
    
    valid_movies = movie_ids[valid_mask]
    valid_scores = predictions[valid_mask]
    
    # Sort and get top K
    top_indices = np.argpartition(-valid_scores, min(top_k, len(valid_scores)-1))[:top_k]
    top_indices = top_indices[np.argsort(-valid_scores[top_indices])]

    # Build results
    recs = []
    for idx in top_indices:
        mid = valid_movies[idx]
        score = valid_scores[idx]
        
        if mid in MOVIE_ID_TO_INDEX:
            df_idx = MOVIE_ID_TO_INDEX[mid]
            recs.append((
                int(mid), 
                df.iloc[df_idx]['title'], 
                float(score), 
                df.iloc[df_idx]['poster_path']
            ))

    return recs


# --------------------------------------------------
# TRENDING MOVIES CACHE (OPTIMIZED)
# --------------------------------------------------
GET_TRENDING_MOVIES = """
    SELECT id, title, poster_path, popularity, vote_average, vote_count, release_date
    FROM movies
    WHERE popularity > 5 AND vote_count > 100
    ORDER BY popularity DESC
    LIMIT 500
"""

def get_trending_movies(cur, ttl=1800):
    """Cache trending movies for 30 mins."""
    global TRENDING_CACHE
    now = time.time()

    if TRENDING_CACHE['data'] and (now - TRENDING_CACHE['last_update'] < ttl):
        return TRENDING_CACHE['data']

    try:
        cur.execute(GET_TRENDING_MOVIES)
        rows = cur.fetchall()

        # Vectorized score computation
        data = np.array(rows, dtype=object)
        movie_ids = data[:, 0].astype(int)
        popularity = data[:, 3].astype(float)
        vote_avg = data[:, 4].astype(float)
        vote_cnt = data[:, 5].astype(float)
        
        scores = popularity + (vote_avg * vote_cnt) / (vote_cnt + 100)
        
        trending_scores = dict(zip(movie_ids, scores))

        TRENDING_CACHE['data'] = trending_scores
        TRENDING_CACHE['last_update'] = now

        return trending_scores

    except Exception as e:
        logger.error(f"Error computing trending: {e}")
        return {}


# --------------------------------------------------
# HYBRID RECOMMENDER (OPTIMIZED)
# --------------------------------------------------
def hybrid_recommendations(user_id, cur,
                           top_k=20,
                           content_weight=0.5,
                           cf_weight=0.3,
                           trending_weight=0.2):
    """
    OPTIMIZATIONS:
    - Added preload checks
    - Vectorized normalization
    - Optimized final blending with numpy operations
    """
    global MOVIES_DF, TFIDF_MATRIX, MOVIE_ID_TO_INDEX

    # Ensure data is loaded
    if MOVIES_DF is None or TFIDF_MATRIX is None:
        preload_movies_and_tfidf(cur)

    if MOVIES_DF is None or MOVIES_DF.empty:
        logger.error("MOVIES_DF is empty → cannot generate recommendations")
        return []

    # Get recommendations from all sources
    content_recs = content_recommend_for_user(user_id, cur, top_k=200)
    cf_recs = collaborative_recommend_for_user(user_id, cur, top_k=200)
    trending_scores = get_trending_movies(cur)

    # Vectorized normalization
    def normalize(recs):
        if not recs:
            return {}
        scores = np.array([r[2] for r in recs], dtype=np.float32)
        min_score, max_score = scores.min(), scores.max()
        
        if max_score == min_score:
            return {r[0]: 1.0 for r in recs}
        
        normalized = (scores - min_score) / (max_score - min_score)
        return {recs[i][0]: float(normalized[i]) for i in range(len(recs))}

    c_scores = normalize(content_recs)
    cf_scores = normalize(cf_recs)

    # Trending normalization
    trending_norm = {}
    if trending_scores:
        vals = np.array(list(trending_scores.values()), dtype=np.float32)
        min_val, max_val = vals.min(), vals.max()
        
        if max_val > min_val:
            trending_norm = {
                mid: float((s - min_val) / (max_val - min_val))
                for mid, s in trending_scores.items()
            }
        else:
            trending_norm = {mid: 1.0 for mid in trending_scores}

    # Efficient blending
    all_ids = set(c_scores) | set(cf_scores) | set(trending_norm)
    
    final_scores = {
        mid: (
            content_weight * c_scores.get(mid, 0) +
            cf_weight * cf_scores.get(mid, 0) +
            trending_weight * trending_norm.get(mid, 0)
        )
        for mid in all_ids
    }

    # Get top K using heap (more efficient than full sort)
    sorted_final = sorted(final_scores.items(), key=lambda x: -x[1])[:top_k]

    # Build final results
    result = []
    for mid, score in sorted_final:
        if mid not in MOVIE_ID_TO_INDEX:
            continue
            
        idx = MOVIE_ID_TO_INDEX[mid]
        poster = MOVIES_DF.iloc[idx]['poster_path']
        poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else None

        result.append({
            "movie_id": int(mid),
            "title": MOVIES_DF.iloc[idx]["title"],
            "score": float(score),
            "poster_path": poster_url
        })

    return result


# --------------------------------------------------
# CACHE INVALIDATION HELPERS
# --------------------------------------------------
def invalidate_user_cache(user_id=None):
    """
    Call this when user preferences/watchlist changes.
    If user_id is None, clears all user caches.
    """
    global USER_PREFS_CACHE, USER_WATCHED_CACHE
    
    if user_id is None:
        USER_PREFS_CACHE.clear()
        USER_WATCHED_CACHE.clear()
        logger.info("Cleared all user caches")
    else:
        USER_PREFS_CACHE.pop(user_id, None)
        USER_WATCHED_CACHE.pop(user_id, None)
        logger.info(f"Cleared cache for user {user_id}")


def invalidate_ratings_cache():
    """Call this when new ratings are added"""
    global RATINGS_CACHE
    RATINGS_CACHE['data'] = None
    RATINGS_CACHE['last_update'] = 0
    logger.info("Cleared ratings cache")


def invalidate_trending_cache():
    """Call this to force trending movies refresh"""
    global TRENDING_CACHE
    TRENDING_CACHE['data'] = {}
    TRENDING_CACHE['last_update'] = 0
    logger.info("Cleared trending cache")


# --------------------------------------------------
# INITIALIZATION
# --------------------------------------------------
def initialize_recommender(cur):
    """
    Initialize the recommender system at application startup.
    Call this once when your Flask app starts.
    
    Example usage in your Flask app:
        @app.before_first_request
        def init():
            from flask import g
            initialize_recommender(g.db_cursor)
    """
    logger.info("Initializing recommender system...")
    preload_movies_and_tfidf(cur)
    logger.info(f"Loaded {len(MOVIES_DF)} movies into memory")
    logger.info("Recommender system ready!")