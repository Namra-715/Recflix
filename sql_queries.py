"""
SQL Queries for Recflix Application
This module contains all SQL queries used throughout the application,
providing separation of concerns for database operations.
"""

# ============================================================================
# USER QUERIES
# ============================================================================

# Check if user exists by email
CHECK_USER_EXISTS = "SELECT * FROM users WHERE email=%s"

# Get user by email for login
GET_USER_BY_EMAIL = "SELECT user_id, full_name, password FROM users WHERE email=%s"

# Insert new user
INSERT_USER = "INSERT INTO users (full_name, email, password) VALUES (%s, %s, %s)"


# ============================================================================
# MOVIE QUERIES
# ============================================================================

# Get trending movies (recent releases with high popularity and weighted rating)
# Optimized: Pre-filter by popularity and vote_count to reduce rows before complex ORDER BY
# This uses a subquery to first filter to top candidates, then applies the complex calculation
GET_TRENDING_MOVIES = """
    SELECT id, title, poster_path, popularity, vote_average, vote_count, release_date
    FROM (
        SELECT id, title, poster_path, popularity, vote_average, vote_count, release_date
        FROM movies
        WHERE release_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
          AND poster_path IS NOT NULL 
          AND poster_path != ''
          AND popularity > 0
          AND vote_count > 10
        ORDER BY popularity DESC, vote_average DESC
        LIMIT 500
    ) AS top_candidates
    ORDER BY (vote_average * vote_count / (vote_count + 100)) + popularity DESC
    LIMIT 50
"""

# Get movie details with overview (join already_watched and movies)
GET_MOVIE_DETAILS = """
    SELECT aw.title, aw.poster_path, aw.last_watched, m.overview
    FROM already_watched aw
    JOIN movies m ON aw.movie_id = m.id
    WHERE aw.user_id=%s AND aw.movie_id=%s
"""

# Get movie details directly from movies table (for movies not in already_watched)
GET_MOVIE_DETAILS_FROM_MOVIES = """
    SELECT title, poster_path, overview
    FROM movies
    WHERE id=%s
"""

# Base query for movie filtering (used in database_query.py)
BASE_MOVIE_QUERY = "SELECT * FROM movies WHERE 1=1"


# ============================================================================
# WATCHLIST QUERIES
# ============================================================================

# Get user's watchlist
GET_USER_WATCHLIST = "SELECT movie_id, title, poster_path FROM watchlist WHERE user_id=%s"

# Check if movie exists in watchlist
CHECK_WATCHLIST_EXISTS = "SELECT * FROM watchlist WHERE user_id=%s AND movie_id=%s"

# Add movie to watchlist
INSERT_WATCHLIST = "INSERT INTO watchlist (user_id, movie_id, title, poster_path) VALUES (%s, %s, %s, %s)"

# Remove movie from watchlist
DELETE_WATCHLIST = "DELETE FROM watchlist WHERE user_id=%s AND movie_id=%s"


# ============================================================================
# ALREADY WATCHED QUERIES
# ============================================================================

# Get user's already watched movies
GET_ALREADY_WATCHED = """
    SELECT movie_id, title, poster_path 
    FROM already_watched 
    WHERE user_id = %s 
"""

# Check if movie exists in already_watched
CHECK_ALREADY_WATCHED_EXISTS = "SELECT * FROM already_watched WHERE user_id=%s AND movie_id=%s"

# Insert movie into already_watched
INSERT_ALREADY_WATCHED = """
    INSERT INTO already_watched (user_id, movie_id, title, poster_path, last_watched) 
    VALUES (%s, %s, %s, %s, NOW())
"""

# Update last_watched timestamp
UPDATE_LAST_WATCHED = "UPDATE already_watched SET last_watched = NOW() WHERE user_id=%s AND movie_id=%s"


# ============================================================================
# REVIEW QUERIES
# ============================================================================

# Get reviewed movies for a user
GET_REVIEWED_MOVIES = "SELECT movie_id FROM reviews WHERE user_id=%s"

# Check if review exists
CHECK_REVIEW_EXISTS = "SELECT * FROM reviews WHERE user_id=%s AND movie_id=%s"

# Insert new review
INSERT_REVIEW = """
    INSERT INTO reviews (user_id, movie_id, rating, review_text)
    VALUES (%s, %s, %s, %s)
"""

UPDATE_REVIEW="UPDATE reviews SET rating = %s, review_text = %s WHERE user_id = %s AND movie_id = %s"


# Get newest reviews for a movie (join with users to get reviewer name)
# Orders by review_id DESC (assuming auto-increment, newer reviews have higher IDs)
GET_MOVIE_REVIEWS = """
    SELECT r.review_id, r.user_id, r.rating, r.review_text, u.full_name
    FROM reviews r
    JOIN users u ON r.user_id = u.user_id
    WHERE r.movie_id = %s
    ORDER BY r.review_id DESC
    LIMIT 10
"""


# ============================================================================
# FOLLOWER/FOLLOWING QUERIES
# ============================================================================

# Check if user follows another user
CHECK_FOLLOW_EXISTS = "SELECT * FROM user_follows WHERE follower_id=%s AND following_id=%s"

# Follow a user
INSERT_FOLLOW = "INSERT INTO user_follows (follower_id, following_id) VALUES (%s, %s)"

# Unfollow a user
DELETE_FOLLOW = "DELETE FROM user_follows WHERE follower_id=%s AND following_id=%s"

# Get users that current user follows
GET_FOLLOWING = """
    SELECT u.user_id, u.full_name, u.email, uf.created_at
    FROM user_follows uf
    JOIN users u ON uf.following_id = u.user_id
    WHERE uf.follower_id = %s
    ORDER BY uf.created_at DESC
"""

# Get users that follow current user
GET_FOLLOWERS = """
    SELECT u.user_id, u.full_name, u.email, uf.created_at
    FROM user_follows uf
    JOIN users u ON uf.follower_id = u.user_id
    WHERE uf.following_id = %s
    ORDER BY uf.created_at DESC
"""

# Get follower/following counts for a user
GET_USER_FOLLOW_STATS = """
    SELECT 
        (SELECT COUNT(*) FROM user_follows WHERE following_id = %s) as followers_count,
        (SELECT COUNT(*) FROM user_follows WHERE follower_id = %s) as following_count
"""

# Search users by name or email
SEARCH_USERS = """
    SELECT user_id, full_name, email
    FROM users
    WHERE (full_name LIKE %s OR email LIKE %s) AND user_id != %s
    LIMIT 20
"""

# ============================================================================
# FOLLOW REQUEST QUERIES
# ============================================================================

# Check if follow request exists
CHECK_FOLLOW_REQUEST_EXISTS = """
    SELECT * FROM follow_requests 
    WHERE requester_id=%s AND requested_id=%s
"""

# Create a follow request
INSERT_FOLLOW_REQUEST = """
    INSERT INTO follow_requests (requester_id, requested_id, status) 
    VALUES (%s, %s, 'pending')
"""

# Get pending follow requests for a user (requests they received)
GET_PENDING_FOLLOW_REQUESTS = """
    SELECT fr.request_id, fr.requester_id, fr.requested_id, fr.created_at,
           u.user_id, u.full_name, u.email
    FROM follow_requests fr
    JOIN users u ON fr.requester_id = u.user_id
    WHERE fr.requested_id = %s AND fr.status = 'pending'
    ORDER BY fr.created_at DESC
"""

# Get follow requests sent by a user
GET_SENT_FOLLOW_REQUESTS = """
    SELECT fr.request_id, fr.requester_id, fr.requested_id, fr.status, fr.created_at,
           u.user_id, u.full_name, u.email
    FROM follow_requests fr
    JOIN users u ON fr.requested_id = u.user_id
    WHERE fr.requester_id = %s AND fr.status = 'pending'
    ORDER BY fr.created_at DESC
"""

# Accept a follow request (creates the follow relationship and updates request status)
ACCEPT_FOLLOW_REQUEST = """
    UPDATE follow_requests 
    SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
    WHERE request_id = %s AND requested_id = %s AND status = 'pending'
"""

# Cancel a follow request (by the requester)
CANCEL_FOLLOW_REQUEST = """
    DELETE FROM follow_requests 
    WHERE request_id = %s AND requester_id = %s AND status = 'pending'
"""

# Get movies watched by users that the current user follows
# Returns distinct movies (no user info) ordered by most recently watched
GET_FOLLOWED_USERS_MOVIES = """
    SELECT DISTINCT aw.movie_id, aw.title, aw.poster_path, MAX(aw.last_watched) as most_recent_watch
    FROM already_watched aw
    WHERE aw.user_id IN (
        SELECT following_id 
        FROM user_follows 
        WHERE follower_id = %s
    )
    AND aw.poster_path IS NOT NULL 
    AND aw.poster_path != ''
    GROUP BY aw.movie_id, aw.title, aw.poster_path
    ORDER BY most_recent_watch DESC
    LIMIT 50
"""


# ============================================================================
# PLAYLIST QUERIES
# ============================================================================

# Create a new playlist
INSERT_PLAYLIST = """
    INSERT INTO playlists (user_id, name, description, is_public) 
    VALUES (%s, %s, %s, %s)
"""

# Get user's playlists (owned + collaborated)
GET_USER_PLAYLISTS = """
    SELECT p.*, 
           (SELECT COUNT(*) FROM playlist_movies WHERE playlist_id = p.playlist_id) as movie_count
    FROM playlists p
    WHERE p.user_id = %s OR p.playlist_id IN (
        SELECT playlist_id FROM playlist_collaborators WHERE user_id = %s
    )
    ORDER BY p.updated_at DESC
"""

# Get public playlists
GET_PUBLIC_PLAYLISTS = """
    SELECT p.*, u.full_name as creator_name,
           (SELECT COUNT(*) FROM playlist_movies WHERE playlist_id = p.playlist_id) as movie_count
    FROM playlists p
    JOIN users u ON p.user_id = u.user_id
    WHERE p.is_public = TRUE
    ORDER BY p.updated_at DESC
    LIMIT 50
"""

# Get playlist details
GET_PLAYLIST_DETAILS = """
    SELECT p.*, u.full_name as creator_name
    FROM playlists p
    JOIN users u ON p.user_id = u.user_id
    WHERE p.playlist_id = %s
"""

# Check if user can access playlist
CHECK_PLAYLIST_ACCESS = """
    SELECT 
        CASE 
            WHEN p.user_id = %s THEN 'owner'
            WHEN EXISTS(SELECT 1 FROM playlist_collaborators WHERE playlist_id = %s AND user_id = %s) THEN 'collaborator'
            WHEN p.is_public = TRUE THEN 'viewer'
            ELSE NULL
        END as access_level
    FROM playlists p
    WHERE p.playlist_id = %s
"""

# Get movies in a playlist
GET_PLAYLIST_MOVIES = """
    SELECT pm.*, m.title, m.poster_path, m.overview, u.full_name as added_by_name
    FROM playlist_movies pm
    JOIN movies m ON pm.movie_id = m.id
    JOIN users u ON pm.added_by_user_id = u.user_id
    WHERE pm.playlist_id = %s
    ORDER BY pm.added_at DESC
"""

# Add movie to playlist
INSERT_PLAYLIST_MOVIE = """
    INSERT INTO playlist_movies (playlist_id, movie_id, added_by_user_id)
    VALUES (%s, %s, %s)
"""

# Remove movie from playlist
DELETE_PLAYLIST_MOVIE = "DELETE FROM playlist_movies WHERE playlist_id=%s AND movie_id=%s"

# Check if movie exists in playlist
CHECK_PLAYLIST_MOVIE_EXISTS = "SELECT * FROM playlist_movies WHERE playlist_id=%s AND movie_id=%s"

# Update playlist (name, description, privacy)
UPDATE_PLAYLIST = """
    UPDATE playlists 
    SET name=%s, description=%s, is_public=%s 
    WHERE playlist_id=%s AND user_id=%s
"""

# Delete playlist
DELETE_PLAYLIST = "DELETE FROM playlists WHERE playlist_id=%s AND user_id=%s"

# Add collaborator to playlist
INSERT_COLLABORATOR = """
    INSERT INTO playlist_collaborators (playlist_id, user_id, invited_by_user_id)
    VALUES (%s, %s, %s)
"""

# Get playlist collaborators
GET_PLAYLIST_COLLABORATORS = """
    SELECT pc.*, u.full_name, u.email
    FROM playlist_collaborators pc
    JOIN users u ON pc.user_id = u.user_id
    WHERE pc.playlist_id = %s
"""

# Remove collaborator
DELETE_COLLABORATOR = "DELETE FROM playlist_collaborators WHERE playlist_id=%s AND user_id=%s"



GET_LIKED_MOVIES = """
SELECT m.id, m.title, m.poster_path
FROM user_likes_dislikes l
JOIN movies m ON l.movie_id = m.id
WHERE l.user_id = %s
  AND l.liked_disliked = 'Y'
"""


GET_USER_LIKE_STATUS = """
SELECT liked_disliked
FROM user_likes_dislikes
WHERE user_id = %s AND movie_id = %s
"""


# --- Preferences Page ---
GET_DISTINCT_LANGUAGES = """
SELECT DISTINCT original_language
FROM movies
WHERE original_language IS NOT NULL
"""

GET_ALL_GENRES = """
SELECT genres
FROM movies
WHERE genres IS NOT NULL
"""

DELETE_USER_PREFERENCES = """
DELETE FROM user_preferences
WHERE user_id = %s
"""

INSERT_LANGUAGE_PREFERENCE = """
INSERT INTO user_preferences (user_id, preference_type, preference_value)
VALUES (%s, 'language', %s)
"""

INSERT_GENRE_PREFERENCE = """
INSERT INTO user_preferences (user_id, preference_type, preference_value)
VALUES (%s, 'genre', %s)
"""

# --- Like / Dislike ---
CHECK_LIKE_STATUS = """
SELECT liked_disliked
FROM user_likes_dislikes
WHERE user_id=%s AND movie_id=%s
"""

UPDATE_LIKE_STATUS = """
UPDATE user_likes_dislikes
SET liked_disliked=%s, updated_at=%s
WHERE user_id=%s AND movie_id=%s
"""

INSERT_LIKE_STATUS = """
INSERT INTO user_likes_dislikes (user_id, movie_id, liked_disliked)
VALUES (%s, %s, %s)
"""
