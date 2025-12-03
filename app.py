from flask import Flask, render_template, request, redirect, session, flash, url_for,jsonify
from flask_mysqldb import MySQL
import bcrypt
from database_query import MovieDatabase, MYSQL_CONFIG
from sql_queries import (
    CHECK_USER_EXISTS, GET_USER_BY_EMAIL, INSERT_USER,
    GET_TRENDING_MOVIES, GET_MOVIE_DETAILS, GET_MOVIE_DETAILS_FROM_MOVIES,
    GET_USER_WATCHLIST, CHECK_WATCHLIST_EXISTS, INSERT_WATCHLIST, DELETE_WATCHLIST,
    GET_ALREADY_WATCHED, CHECK_ALREADY_WATCHED_EXISTS, INSERT_ALREADY_WATCHED, UPDATE_LAST_WATCHED,
    GET_REVIEWED_MOVIES, CHECK_REVIEW_EXISTS, INSERT_REVIEW, GET_MOVIE_REVIEWS,
    CHECK_FOLLOW_EXISTS, INSERT_FOLLOW, DELETE_FOLLOW, GET_FOLLOWING, GET_FOLLOWERS,
    GET_USER_FOLLOW_STATS, SEARCH_USERS, GET_FOLLOWED_USERS_MOVIES,
    CHECK_FOLLOW_REQUEST_EXISTS, INSERT_FOLLOW_REQUEST, GET_PENDING_FOLLOW_REQUESTS,
    GET_SENT_FOLLOW_REQUESTS, ACCEPT_FOLLOW_REQUEST, CANCEL_FOLLOW_REQUEST,
    INSERT_PLAYLIST, GET_USER_PLAYLISTS, GET_PUBLIC_PLAYLISTS, GET_PLAYLIST_DETAILS,
    CHECK_PLAYLIST_ACCESS, GET_PLAYLIST_MOVIES, INSERT_PLAYLIST_MOVIE, DELETE_PLAYLIST_MOVIE,
    CHECK_PLAYLIST_MOVIE_EXISTS, UPDATE_PLAYLIST, DELETE_PLAYLIST,
    INSERT_COLLABORATOR, GET_PLAYLIST_COLLABORATORS, DELETE_COLLABORATOR,GET_LIKED_MOVIES,GET_USER_LIKE_STATUS,GET_DISTINCT_LANGUAGES, GET_ALL_GENRES,
    DELETE_USER_PREFERENCES, INSERT_LANGUAGE_PREFERENCE, INSERT_GENRE_PREFERENCE,
    CHECK_LIKE_STATUS, UPDATE_LIKE_STATUS, INSERT_LIKE_STATUS,UPDATE_REVIEW,ADVANCED_SEARCH_PLATFORM
)
import langcodes
import json
from recommender import hybrid_recommendations
import time
from datetime import datetime


app = Flask(__name__)
app.secret_key = "supersecretkey"

# MySQL Configuration - using shared config from database_query.py
app.config['MYSQL_HOST'] = MYSQL_CONFIG['host']
app.config['MYSQL_USER'] = MYSQL_CONFIG['user']
app.config['MYSQL_PASSWORD'] = MYSQL_CONFIG['password']
app.config['MYSQL_DB'] = MYSQL_CONFIG['database']
app.config['MYSQL_PORT'] = MYSQL_CONFIG['port']

mysql = MySQL(app)


def has_poster_path(path_value):
    """Utility to ensure poster paths exist before rendering."""
    return bool(path_value and str(path_value).strip())


# Home route
@app.route('/')
def home():
    return redirect('/login')

#registration route

@app.route('/register', methods=['GET', 'POST'])
def register():
    message = None
    success = False  # flag for styling in template
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

        cur = mysql.connection.cursor()
        # Check if user exists
        cur.execute(CHECK_USER_EXISTS, (email,))
        account = cur.fetchone()

        if account:
            message = "User already exists. Please login."
        else:
            # Insert new user
            cur.execute(INSERT_USER, (full_name, email, hashed_password))
            mysql.connection.commit()
            message = "Account created successfully! Please login."
            success = True

        cur.close()
    return render_template('register.html', message=message, success=success)



# Login Page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute(GET_USER_BY_EMAIL, (email,))
        user = cur.fetchone()
        cur.close()

        if not user:
            # Email not registered
            return render_template('login.html', message="Email not registered. Please create an account.")
        
        if bcrypt.checkpw(password, user[2].encode('utf-8')):
            session['user_id'] = user[0]
            session['full_name'] = user[1]
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', message="Incorrect password. Please try again.")

    return render_template('login.html')



# Helper function to fetch trending movies from local DB (for new users)
def get_local_trending_movies():
    cur = mysql.connection.cursor()
    cur.execute(GET_TRENDING_MOVIES)
    results = cur.fetchall()
    cur.close()
    # Return as list of dicts for easy template use
    return [
        {
            'id': row[0],
            'title': row[1],
            'poster_path': row[2],
            'popularity': row[3],
            'vote_average': row[4],
            'vote_count': row[5],
            'release_date': row[6]
        }
        for row in results
        if has_poster_path(row[2])
    ]


# Dashboard Page
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect('/login')

    user_name = session['full_name']
    user_id = session['user_id']

    cur = mysql.connection.cursor()
    # Fetch user's watchlist
    cur.execute(GET_USER_WATCHLIST, (user_id,))
    watchlist = [movie for movie in cur.fetchall() if has_poster_path(movie[2])]
    cur.close()

    is_new_user = len(watchlist) == 0
    trending_movies = get_local_trending_movies()

    # --- Handle simple search (header search box) ---
    search_query = request.args.get('query', '').strip()
    search_results = []
    if search_query:
        filters = {'title': search_query}
        db = MovieDatabase(
            host=MYSQL_CONFIG['host'],
            database=MYSQL_CONFIG['database'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            port=MYSQL_CONFIG['port']
        )
        if db.connect():
            # Limit search results to 100 for performance
            search_results = db.query_movies(filters, limit=100)
            db.disconnect()
            # Skip movies without poster paths to keep UI consistent
            search_results = [
                movie for movie in search_results
                if has_poster_path(movie.get('poster_path'))
            ]

    cur = mysql.connection.cursor()
    cur.execute(GET_ALREADY_WATCHED, (user_id,))
    already_watched = [movie for movie in cur.fetchall() if has_poster_path(movie[2])]
   

    cur.execute(GET_REVIEWED_MOVIES, (user_id,))
    reviewed_movies = [row[0] for row in cur.fetchall()]

    # Get movies watched by users that the current user follows
    try:
        cur.execute(GET_FOLLOWED_USERS_MOVIES, (user_id,))
        followed_users_movies = cur.fetchall()
        # Convert to list of dicts for template consistency and filter posterless movies
        followed_users_movies = [
            {
                'id': movie[0],
                'title': movie[1],
                'poster_path': movie[2]
            }
            for movie in followed_users_movies
            if has_poster_path(movie[2])
        ]
    except Exception as e:
        # If user_follows table doesn't exist yet, set to empty list
        followed_users_movies = []
        print(f"Error fetching followed users movies: {e}")
    
    # Get pending follow requests
    try:
        cur.execute(GET_PENDING_FOLLOW_REQUESTS, (user_id,))
        pending_requests = cur.fetchall()
    except Exception as e:
        pending_requests = []
        print(f"Error fetching pending requests: {e}")

    # 🎯 --- Get Personalized Recommendations ---
    try:
        recommendations = hybrid_recommendations(user_id, cur)
    except Exception as e:
        print("Recommendation error:", e)
        recommendations = []


    cur.execute(GET_LIKED_MOVIES, (user_id,))
    rows = cur.fetchall()

    liked_movies = [
    {
        'id': row[0],
        'title': row[1],
        'poster_path': row[2]
    }
    for row in rows
    if has_poster_path(row[2])
    ]



    cur.close()

    return render_template(
        'dashboard.html',
        user_name=user_name,
        user_id=user_id,
        trending_movies=trending_movies,
        watchlist=watchlist,
        is_new_user=is_new_user,
        search_results=search_results,
        search_query=search_query,
        already_watched=already_watched,
        followed_users_movies=followed_users_movies,
        reviewed_movies=reviewed_movies,
        pending_requests=pending_requests,
        recommendations=recommendations,
        liked_movies=liked_movies
    )

#advanced search
@app.route('/advanced_search')
def advanced_search():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect('/login')

    user_id = session['user_id']
    user_name = session.get('full_name', '')

    # Read filters
    title = request.args.get('title', '').strip()
    genres = request.args.get('genres', '').strip()
    director = request.args.get('director', '').strip()
    cast = request.args.get('cast', '').strip()
    min_vote_average = request.args.get('min_vote_average', '').strip()
    min_imdb_rating = request.args.get('min_imdb_rating', '').strip()
    min_runtime = request.args.get('min_runtime', '').strip()
    original_language = request.args.get('original_language', '').strip()
    status = request.args.get('status', '').strip()
    platform = request.args.get('platform', '').strip()

    search_results = []

    # Platform column mapping
    platform_column_map = {
        'netflix': 'netflix',
        'hulu': 'hulu',
        'prime_video': 'prime_video',
        'disney_plus': 'disney_plus',
    }

    platform_column = platform_column_map.get(platform.lower()) if platform else None

    if platform_column:
        cur = mysql.connection.cursor()

        # Start with the base query from sql_queries.py
        query = ADVANCED_SEARCH_PLATFORM.format(platform_column=platform_column)
        params = []

        # Add filters
        if title:
            query += " AND LOWER(m.title) LIKE %s"
            params.append(f"%{title.lower()}%")

        if genres:
            query += " AND LOWER(m.genres) LIKE %s"
            params.append(f"%{genres.lower()}%")

        if director:
            query += " AND LOWER(m.director) LIKE %s"
            params.append(f"%{director.lower()}%")

        if cast:
            query += " AND LOWER(m.cast) LIKE %s"
            params.append(f"%{cast.lower()}%")

        if min_vote_average:
            try:
                query += " AND m.vote_average >= %s"
                params.append(float(min_vote_average))
            except ValueError:
                pass

        if min_imdb_rating:
            try:
                query += " AND m.imdb_rating >= %s"
                params.append(float(min_imdb_rating))
            except ValueError:
                pass

        if min_runtime:
            try:
                query += " AND m.runtime >= %s"
                params.append(int(min_runtime))
            except ValueError:
                pass

        if original_language:
            query += " AND LOWER(m.original_language) = %s"
            params.append(original_language.lower())

        if status:
            query += " AND LOWER(m.status) = %s"
            params.append(status.lower())

        query += " LIMIT 200"

        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        cur.close()

        search_results = [
            {
                'id': row[0],
                'title': row[1],
                'poster_path': row[2],
                'release_date': row[3],
                'vote_average': row[4],
                'imdb_rating': row[5],
            }
            for row in rows
            if has_poster_path(row[2])
        ]

    else:
        # Non-platform search: MovieDatabase handles it
        filters = {}
        if title:
            filters['title'] = title
        if genres:
            filters['genres'] = [g.strip() for g in genres.split(',') if g.strip()]
        if director:
            filters['director'] = director
        if cast:
            filters['cast'] = cast
        if min_vote_average:
            try:
                filters['vote_average'] = {'operator': '>=', 'value': float(min_vote_average)}
            except ValueError:
                pass
        if min_imdb_rating:
            try:
                filters['imdb_rating'] = {'operator': '>=', 'value': float(min_imdb_rating)}
            except ValueError:
                pass
        if min_runtime:
            try:
                filters['runtime'] = {'operator': '>=', 'value': int(min_runtime)}
            except ValueError:
                pass
        if original_language:
            filters['original_language'] = original_language
        if status:
            filters['status'] = status

        if filters:
            db = MovieDatabase(**MYSQL_CONFIG)
            if db.connect():
                search_results = db.query_movies(filters, limit=200)
                db.disconnect()

                search_results = [
                    movie for movie in search_results
                    if has_poster_path(movie.get('poster_path'))
                ]

    form_values = {
        'title': title,
        'genres': genres,
        'director': director,
        'cast': cast,
        'min_vote_average': min_vote_average,
        'min_imdb_rating': min_imdb_rating,
        'min_runtime': min_runtime,
        'original_language': original_language,
        'status': status,
        'platform': platform,
    }

    return render_template(
        'advanced_search.html',
        user_id=user_id,
        user_name=user_name,
        search_results=search_results,
        form_values=form_values
    )
#create watch list
@app.route('/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    if 'user_id' not in session:
        flash("Please log in to add movies to your watchlist.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']
    title = request.form['title']
    poster_path = request.form['poster_path']

    cur = mysql.connection.cursor()

    # Check if movie is already in watchlist
    cur.execute(CHECK_WATCHLIST_EXISTS, (user_id, movie_id))
    existing = cur.fetchone()

    if existing:
        flash("This movie is already in your watchlist!", "already_exists")
    else:
        cur.execute(INSERT_WATCHLIST, (user_id, movie_id, title, poster_path))
        mysql.connection.commit()
        flash(f"Added '{title}' to your watchlist!", "success")

    cur.close()
    return redirect(url_for('dashboard'))

#remove from watch list
@app.route('/remove_from_watchlist', methods=['POST'])
def remove_from_watchlist():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']

    cur = mysql.connection.cursor()
    cur.execute(DELETE_WATCHLIST, (user_id, movie_id))
    mysql.connection.commit()
    cur.close()

    flash("Movie removed from your watchlist.", "info")
    return redirect(url_for('dashboard'))

#already watched
@app.route('/already_watched', methods=['POST'])
def already_watched():
    if 'user_id' not in session:
        flash("Please login to watch movies.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']
    title = request.form['title']
    poster_path = request.form['poster_path']

    cur = mysql.connection.cursor()

    # Check if already in already_watched
    cur.execute(CHECK_ALREADY_WATCHED_EXISTS, (user_id, movie_id))
    existing = cur.fetchone()

    if existing:
        # Update last_watched timestamp if movie already exists
        cur.execute(UPDATE_LAST_WATCHED, (user_id, movie_id))
    else:
        # Insert new row with last_watched timestamp
        cur.execute(INSERT_ALREADY_WATCHED, (user_id, movie_id, title, poster_path))

    mysql.connection.commit()
    cur.close()

    flash(f"Now playing '{title}' — added to Already Watched!", "success")
    return redirect(url_for('dashboard'))

#updating the last_watched details
@app.route('/update_last_watched', methods=['POST'])
def update_last_watched():
    if 'user_id' not in session:
        flash("Login required", "warning")
        return redirect(url_for('dashboard'))

    movie_id = request.form.get('movie_id')  
    user_id = session['user_id']

    cur = mysql.connection.cursor()
    cur.execute(UPDATE_LAST_WATCHED, (user_id, movie_id))
    mysql.connection.commit()
    cur.close()

    flash("Resume time updated!", "success")
    return redirect(url_for('movie_details', movie_id=movie_id))

#fetching movie details based on selected movie 
@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    if 'user_id' not in session:
        flash("Login required", "warning")
        return redirect(url_for('dashboard'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    # Get reviews for this movie
    cur.execute(GET_MOVIE_REVIEWS, (movie_id,))
    reviews = cur.fetchall()
    
    # Check if user has already reviewed this movie
    cur.execute(CHECK_REVIEW_EXISTS, (user_id, movie_id))
    user_reviewed = cur.fetchone() is not None

    # Get user's playlists for "Add to Playlist" dropdown
    try:
        cur.execute(GET_USER_PLAYLISTS, (user_id, user_id))
        user_playlists = cur.fetchall()
    except Exception as e:
        # If playlists table doesn't exist yet, set to empty list
        user_playlists = []
        print(f"Error fetching playlists: {e}")

    # First try to get from already_watched (if user has watched it)
    cur.execute(GET_MOVIE_DETAILS, (user_id, movie_id))
    result = cur.fetchone()

        # Fetch user's like/dislike status for this movie
    try:
        cur.execute(GET_USER_LIKE_STATUS, (user_id, movie_id))
        row = cur.fetchone()
        user_likes_dislikes = {movie_id: row[0]} if row else {}
    except Exception as e:
        user_likes_dislikes = {}
        print(f"Error fetching like/dislike: {e}")


    
    if result:
        # Movie is in already_watched
        title, poster_path, last_watched, description = result
        cur.close()
        return render_template(
            "movieDetails.html",
            movie_id=movie_id,
            title=title,
            poster_path=poster_path,
            last_watched=last_watched,
            description=description,
            in_watched=True,
            reviews=reviews,
            user_reviewed=user_reviewed,
            user_playlists=user_playlists,
            user_likes_dislikes=user_likes_dislikes 
        )
    else:
        # Movie not in already_watched, get from movies table directly
        cur.execute(GET_MOVIE_DETAILS_FROM_MOVIES, (movie_id,))
        result = cur.fetchone()
        cur.close()

        if not result:
            flash("No details found for this movie.", "warning")
            return redirect(url_for('dashboard'))

        title, poster_path, description = result
        return render_template(
            "movieDetails.html",
            movie_id=movie_id,
            title=title,
            poster_path=poster_path,
            last_watched=None,
            description=description,
            in_watched=False,
            reviews=reviews,
            user_reviewed=user_reviewed,
            user_playlists=user_playlists,
            user_likes_dislikes=user_likes_dislikes
        )

#reviews
@app.route('/add_review', methods=['POST'])
def add_review():
    if 'user_id' not in session:
        flash("Please login to write a review.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    movie_id = request.form['movie_id']
    rating = request.form['rating']
    review_text = request.form['review_text']

    cur = mysql.connection.cursor()

    # Check if review already exists for this user and movie
    cur.execute(CHECK_REVIEW_EXISTS, (user_id, movie_id))
    existing_review = cur.fetchone()

    if existing_review:
        # Update the existing review
        cur.execute(UPDATE_REVIEW, (rating, review_text, user_id, movie_id))
        mysql.connection.commit()
        flash("Your review has been updated!", "success")
    else:
        # Insert new review
        cur.execute(INSERT_REVIEW, (user_id, movie_id, rating, review_text))
        mysql.connection.commit()
        flash("Your review has been submitted!", "success")

    cur.close()
    return redirect(url_for('movie_details', movie_id=movie_id))






# ============================================================================
# FOLLOWER/FOLLOWING ROUTES
# ============================================================================

# Send a follow request
@app.route('/follow/<int:user_id>', methods=['POST'])
def follow_user(user_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    if current_user_id == user_id:
        flash("You cannot follow yourself.", "warning")
        return redirect(url_for('dashboard'))
    
    cur = mysql.connection.cursor()
    
    # Check if already following
    cur.execute(CHECK_FOLLOW_EXISTS, (current_user_id, user_id))
    if cur.fetchone():
        flash("You are already following this user.", "info")
        cur.close()
        return redirect(url_for('user_profile', user_id=user_id))
    
    # Check if there's already a request
    cur.execute(CHECK_FOLLOW_REQUEST_EXISTS, (current_user_id, user_id))
    existing_request = cur.fetchone()
    if existing_request:
        status = existing_request[3]
        if status == 'pending':
            flash("You already have a pending follow request for this user.", "info")
            cur.close()
            return redirect(url_for('user_profile', user_id=user_id))
        elif status == 'accepted':
            # Clean up: delete accepted request if it exists (shouldn't happen, but just in case)
            cur.execute("DELETE FROM follow_requests WHERE requester_id=%s AND requested_id=%s AND status='accepted'", 
                       (current_user_id, user_id))
            mysql.connection.commit()
            # Continue to create new request below
    
    # Create a new follow request
    cur.execute(INSERT_FOLLOW_REQUEST, (current_user_id, user_id))
    mysql.connection.commit()
    cur.close()
    flash("Follow request sent! The user will need to accept it.", "success")
    return redirect(url_for('user_profile', user_id=user_id))


# Accept a follow request
@app.route('/accept_follow_request/<int:request_id>', methods=['POST'])
def accept_follow_request(request_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    cur = mysql.connection.cursor()
    
    # Get the request details to verify ownership
    cur.execute("SELECT requester_id, requested_id, status FROM follow_requests WHERE request_id=%s", (request_id,))
    request_data = cur.fetchone()
    
    if not request_data or request_data[1] != current_user_id:
        flash("Follow request not found or you don't have permission.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    if request_data[2] != 'pending':
        flash("This follow request is no longer pending.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    requester_id = request_data[0]
    
    # Accept the request (update status)
    cur.execute(ACCEPT_FOLLOW_REQUEST, (request_id, current_user_id))
    
    # Create the actual follow relationship
    cur.execute(INSERT_FOLLOW, (requester_id, current_user_id))
    
    # Delete the accepted request since we don't need it anymore (follow relationship exists)
    cur.execute("DELETE FROM follow_requests WHERE request_id=%s", (request_id,))
    
    mysql.connection.commit()
    cur.close()
    flash("Follow request accepted!", "success")
    return redirect(url_for('dashboard'))


# Reject a follow request
@app.route('/reject_follow_request/<int:request_id>', methods=['POST'])
def reject_follow_request(request_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    cur = mysql.connection.cursor()
    
    # Get the request details to verify ownership
    cur.execute("SELECT requested_id, status FROM follow_requests WHERE request_id=%s", (request_id,))
    request_data = cur.fetchone()
    
    if not request_data or request_data[0] != current_user_id:
        flash("Follow request not found or you don't have permission.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    if request_data[1] != 'pending':
        flash("This follow request is no longer pending.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    # Delete the request instead of marking as rejected
    cur.execute("DELETE FROM follow_requests WHERE request_id=%s AND requested_id=%s", (request_id, current_user_id))
    mysql.connection.commit()
    cur.close()
    flash("Follow request rejected.", "info")
    return redirect(url_for('dashboard'))


# Unfollow a user (stop following someone)
@app.route('/unfollow/<int:user_id>', methods=['POST'])
def unfollow_user(user_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute(DELETE_FOLLOW, (current_user_id, user_id))
    mysql.connection.commit()
    cur.close()
    flash("You unfollowed this user.", "info")
    # Redirect to own profile if unfollowing from own profile, otherwise to the user's profile
    redirect_to = request.form.get('return_to', 'profile')
    if redirect_to == 'own_profile':
        return redirect(url_for('user_profile', user_id=current_user_id))
    return redirect(url_for('user_profile', user_id=user_id))


# Remove a follower (remove someone who follows you)
@app.route('/remove_follower/<int:user_id>', methods=['POST'])
def remove_follower(user_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    cur = mysql.connection.cursor()
    # Delete the follow relationship where user_id is following current_user_id
    cur.execute(DELETE_FOLLOW, (user_id, current_user_id))
    mysql.connection.commit()
    cur.close()
    flash("Follower removed.", "info")
    return redirect(url_for('user_profile', user_id=current_user_id))


# User profile page
@app.route('/user/<int:user_id>')
def user_profile(user_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    current_user_id = session['user_id']
    cur = mysql.connection.cursor()
    
    cur.execute("SELECT user_id, full_name, email FROM users WHERE user_id=%s", (user_id,))
    user = cur.fetchone()
    if not user:
        flash("User not found.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    cur.execute(GET_USER_FOLLOW_STATS, (user_id, user_id))
    stats = cur.fetchone()
    followers_count = stats[0] if stats else 0
    following_count = stats[1] if stats else 0
    
    is_following = False
    has_pending_request = False
    pending_request_id = None
    if current_user_id != user_id:
        cur.execute(CHECK_FOLLOW_EXISTS, (current_user_id, user_id))
        is_following = cur.fetchone() is not None
        
        # Check if there's a pending request from current user to this user
        cur.execute(CHECK_FOLLOW_REQUEST_EXISTS, (current_user_id, user_id))
        request_data = cur.fetchone()
        if request_data and request_data[3] == 'pending':
            has_pending_request = True
            pending_request_id = request_data[0]
    
    # Get pending follow requests for the current user (if viewing own profile)
    pending_requests = []
    followers = []
    following = []
    if current_user_id == user_id:
        cur.execute(GET_PENDING_FOLLOW_REQUESTS, (current_user_id,))
        pending_requests = cur.fetchall()
        
        # Get followers and following lists for own profile
        cur.execute(GET_FOLLOWERS, (user_id,))
        followers = cur.fetchall()
        
        cur.execute(GET_FOLLOWING, (user_id,))
        following = cur.fetchall()
    
    cur.execute(GET_USER_WATCHLIST, (user_id,))
    watchlist = cur.fetchall()
    
    if current_user_id == user_id:
        cur.execute(GET_USER_PLAYLISTS, (user_id, user_id))
    else:
        cur.execute("SELECT * FROM playlists WHERE user_id=%s AND is_public=TRUE", (user_id,))
    playlists = cur.fetchall()
    
    cur.close()
    return render_template('user_profile.html', profile_user=user, followers_count=followers_count,
                         following_count=following_count, is_following=is_following,
                         has_pending_request=has_pending_request, pending_request_id=pending_request_id,
                         pending_requests=pending_requests, followers=followers, following=following,
                         is_own_profile=(current_user_id == user_id), watchlist=watchlist, playlists=playlists)


# Following list
@app.route('/following')
def following_list():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute(GET_FOLLOWING, (user_id,))
    following = cur.fetchall()
    cur.close()
    return render_template('following.html', following=following)


# Followers list
@app.route('/followers')
def followers_list():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute(GET_FOLLOWERS, (user_id,))
    followers = cur.fetchall()
    cur.close()
    return render_template('followers.html', followers=followers)


# Search users
@app.route('/search_users')
def search_users():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    query = request.args.get('q', '').strip()
    user_id = session['user_id']
    users = []
    if query:
        cur = mysql.connection.cursor()
        search_term = f"%{query}%"
        cur.execute(SEARCH_USERS, (search_term, search_term, user_id))
        users = cur.fetchall()
        cur.close()
    return render_template('search_users.html', users=users, query=query)


# ============================================================================
# PLAYLIST ROUTES
# ============================================================================

# Create playlist
@app.route('/playlist/create', methods=['GET', 'POST'])
def create_playlist():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        is_public = 'is_public' in request.form
        is_shared = 'is_shared' in request.form
        
        cur = mysql.connection.cursor()
        cur.execute(INSERT_PLAYLIST, (user_id, name, description, is_public))
        mysql.connection.commit()
        playlist_id = cur.lastrowid
        
        # If it's a shared playlist, add selected collaborators
        if is_shared:
            selected_user_ids = request.form.getlist('collaborators')
            for collaborator_id in selected_user_ids:
                try:
                    collaborator_id = int(collaborator_id)
                    cur.execute(INSERT_COLLABORATOR, (playlist_id, collaborator_id, user_id))
                except (ValueError, Exception) as e:
                    print(f"Error adding collaborator {collaborator_id}: {e}")
            mysql.connection.commit()
        
        cur.close()
        
        flash("Playlist created successfully!", "success")
        return redirect(url_for('view_playlist', playlist_id=playlist_id))
    
    # GET request - fetch users you follow for the form
    cur = mysql.connection.cursor()
    try:
        cur.execute(GET_FOLLOWING, (user_id,))
        following_users = cur.fetchall()
    except Exception as e:
        following_users = []
        print(f"Error fetching following users: {e}")
    cur.close()
    
    return render_template('playlist_create.html', following_users=following_users)


# View playlist
@app.route('/playlist/<int:playlist_id>')
def view_playlist(playlist_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    
    cur.execute(GET_PLAYLIST_DETAILS, (playlist_id,))
    playlist = cur.fetchone()
    if not playlist:
        flash("Playlist not found.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    cur.execute(CHECK_PLAYLIST_ACCESS, (user_id, playlist_id, user_id, playlist_id))
    access_result = cur.fetchone()
    access_level = access_result[0] if access_result else None
    
    if not access_level:
        flash("You don't have access to this playlist.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    cur.execute(GET_PLAYLIST_MOVIES, (playlist_id,))
    movies = cur.fetchall()
    
    cur.execute(GET_PLAYLIST_COLLABORATORS, (playlist_id,))
    collaborators = cur.fetchall()
    
    cur.close()
    return render_template('playlist_view.html', playlist=playlist, movies=movies,
                         collaborators=collaborators, access_level=access_level,
                         is_owner=(access_level == 'owner'))


# Add movie to playlist
@app.route('/playlist/<int:playlist_id>/add', methods=['POST'])
def add_to_playlist(playlist_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    movie_id = request.form['movie_id']
    
    cur = mysql.connection.cursor()
    cur.execute(CHECK_PLAYLIST_ACCESS, (user_id, playlist_id, user_id, playlist_id))
    access_result = cur.fetchone()
    access_level = access_result[0] if access_result else None
    
    if access_level not in ['owner', 'collaborator']:
        flash("You don't have permission to add movies to this playlist.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    cur.execute(CHECK_PLAYLIST_MOVIE_EXISTS, (playlist_id, movie_id))
    if cur.fetchone():
        flash("Movie is already in this playlist.", "info")
        cur.close()
        return redirect(url_for('view_playlist', playlist_id=playlist_id))
    
    cur.execute(INSERT_PLAYLIST_MOVIE, (playlist_id, movie_id, user_id))
    mysql.connection.commit()
    cur.close()
    flash("Movie added to playlist!", "success")
    return redirect(url_for('view_playlist', playlist_id=playlist_id))


# Remove movie from playlist
@app.route('/playlist/<int:playlist_id>/remove', methods=['POST'])
def remove_from_playlist(playlist_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    movie_id = request.form['movie_id']
    
    cur = mysql.connection.cursor()
    cur.execute(CHECK_PLAYLIST_ACCESS, (user_id, playlist_id, user_id, playlist_id))
    access_result = cur.fetchone()
    access_level = access_result[0] if access_result else None
    
    if access_level not in ['owner', 'collaborator']:
        flash("You don't have permission to remove movies from this playlist.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    cur.execute(DELETE_PLAYLIST_MOVIE, (playlist_id, movie_id))
    mysql.connection.commit()
    cur.close()
    flash("Movie removed from playlist.", "info")
    return redirect(url_for('view_playlist', playlist_id=playlist_id))


# Browse public playlists
@app.route('/playlists/browse')
def browse_playlists():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    cur = mysql.connection.cursor()
    cur.execute(GET_PUBLIC_PLAYLISTS)
    playlists = cur.fetchall()
    cur.close()
    return render_template('playlists_browse.html', playlists=playlists)


# My playlists
@app.route('/playlists')
def my_playlists():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    user_id = session['user_id']
    cur = mysql.connection.cursor()
    cur.execute(GET_USER_PLAYLISTS, (user_id, user_id))
    playlists = cur.fetchall()
    cur.close()
    return render_template('my_playlists.html', playlists=playlists, current_user_id=user_id)


# Add movie to playlist from movie details page
@app.route('/movie/<int:movie_id>/add_to_playlist', methods=['POST'])
def add_movie_to_playlist_from_details(movie_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    playlist_id = request.form.get('playlist_id')
    
    if not playlist_id:
        flash("Please select a playlist.", "warning")
        return redirect(url_for('movie_details', movie_id=movie_id))
    
    cur = mysql.connection.cursor()
    
    # Check access
    cur.execute(CHECK_PLAYLIST_ACCESS, (user_id, playlist_id, user_id, playlist_id))
    access_result = cur.fetchone()
    access_level = access_result[0] if access_result else None
    
    if access_level not in ['owner', 'collaborator']:
        flash("You don't have permission to add movies to this playlist.", "warning")
        cur.close()
        return redirect(url_for('movie_details', movie_id=movie_id))
    
    # Check if movie already in playlist
    cur.execute(CHECK_PLAYLIST_MOVIE_EXISTS, (playlist_id, movie_id))
    if cur.fetchone():
        flash("Movie is already in this playlist.", "info")
        cur.close()
        return redirect(url_for('movie_details', movie_id=movie_id))
    
    # Add movie
    cur.execute(INSERT_PLAYLIST_MOVIE, (playlist_id, movie_id, user_id))
    mysql.connection.commit()
    cur.close()
    
    flash("Movie added to playlist!", "success")
    return redirect(url_for('movie_details', movie_id=movie_id))


# Share playlist with user
@app.route('/playlist/<int:playlist_id>/share', methods=['POST'])
def share_playlist(playlist_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    share_user_id = request.form.get('user_id')
    
    if not share_user_id:
        flash("Please provide a user ID.", "warning")
        return redirect(url_for('view_playlist', playlist_id=playlist_id))
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT user_id FROM playlists WHERE playlist_id=%s", (playlist_id,))
    playlist = cur.fetchone()
    
    if not playlist or playlist[0] != user_id:
        flash("You can only share playlists you own.", "warning")
        cur.close()
        return redirect(url_for('dashboard'))
    
    try:
        cur.execute(INSERT_COLLABORATOR, (playlist_id, share_user_id, user_id))
        mysql.connection.commit()
        flash("Playlist shared successfully!", "success")
    except:
        flash("User is already a collaborator or user not found.", "warning")
    
    cur.close()
    return redirect(url_for('view_playlist', playlist_id=playlist_id))



@app.route("/preferences")
def preferences():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    FAMOUS_LANGUAGES = ["English", "Spanish", "French", "German", "Japanese",
                        "Korean", "Hindi", "Chinese", "Italian", "Portuguese"]

    # Get all languages
    cur.execute(GET_DISTINCT_LANGUAGES)
    lang_rows = cur.fetchall()
    language_codes = [row[0] for row in lang_rows]

    all_languages = []
    for code in language_codes:
        try:
            full_name = langcodes.Language.get(code).display_name()
        except:
            full_name = code.upper()
        all_languages.append({"code": code, "name": full_name})

    famous_languages = [lang for lang in all_languages if lang["name"] in FAMOUS_LANGUAGES]

    # --- Genres ---
    cur.execute(GET_ALL_GENRES)
    rows = cur.fetchall()
    cur.close()

    VALID_GENRES = [
        "Action", "Adventure", "Animation", "Comedy", "Crime", "Documentary",
        "Drama", "Family", "Fantasy", "History", "Horror", "Music",
        "Mystery", "Romance", "Sci-Fi", "Thriller", "War", "Western"
    ]

    all_genres = set()
    for row in rows:
        for g in row[0].split(','):
            g = g.strip()
            if g in VALID_GENRES:
                all_genres.add(g)

    genres = [{"name": g} for g in sorted(all_genres)]

    return render_template("preferences.html",
                           all_languages=all_languages,
                           languages=famous_languages,
                           genres=genres)



@app.route("/save_preferences", methods=["POST"])
def save_preferences():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    selected_languages = request.form.getlist('languages[]')
    selected_genres = request.form.getlist('genres[]')

    cur = None
    try:
        cur = mysql.connection.cursor()

        # Clear user's old preferences
        cur.execute(DELETE_USER_PREFERENCES, [user_id])

        # Insert languages
        for lang in selected_languages:
            cur.execute(INSERT_LANGUAGE_PREFERENCE, (user_id, lang))

        # Insert genres
        for genre in selected_genres:
            cur.execute(INSERT_GENRE_PREFERENCE, (user_id, genre))

        mysql.connection.commit()
        flash("Your preferences have been saved!", "success")

    except Exception as e:
        mysql.connection.rollback()
        print("Database error:", e)
        flash("An error occurred while saving your preferences.", "danger")

    finally:
        if cur:
            cur.close()

    return redirect(url_for('preferences'))


@app.route('/recommendations')
def recommendations():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    user_id = session['user_id']
    cur = mysql.connection.cursor()

    start = time.time()
    try:
        recs = hybrid_recommendations(user_id, cur, top_k=20, content_weight=0.6, cf_weight=0.4)
    except Exception as e:
        print("Error generating recommendations:", e)
        recs = []
    cur.close()
    elapsed = time.time() - start
    # optionally flash short info: flash(f"Generated {len(recs)} recommendations in {elapsed:.2f}s", "info")
    return render_template('dashboard.html', recommendations=recs)


@app.route("/movie/like_dislike", methods=["POST"])
def update_like_dislike():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for("login"))

    user_id = session['user_id']
    movie_id = int(request.form.get("movie_id"))
    action = request.form.get("action")  # like or dislike

    liked_disliked = "Y" if action == "like" else "N"

    cur = mysql.connection.cursor()

    # Check if entry exists
    cur.execute(CHECK_LIKE_STATUS, (user_id, movie_id))
    row = cur.fetchone()

    if row:
        current = row[0]
        if current == liked_disliked:
            flash(f"You have already {'liked' if current=='Y' else 'disliked'} this movie.", "info")
        else:
            cur.execute(UPDATE_LIKE_STATUS, (liked_disliked, datetime.now(), user_id, movie_id))
            flash(f"{'Liked' if liked_disliked=='Y' else 'Disliked'} successfully.", "success")
    else:
        cur.execute(INSERT_LIKE_STATUS, (user_id, movie_id, liked_disliked))
        flash(f"{'Liked' if liked_disliked=='Y' else 'Disliked'} successfully.", "success")

    mysql.connection.commit()
    cur.close()

    return redirect(request.referrer or url_for("movieDetails"))



# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect('/login')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
