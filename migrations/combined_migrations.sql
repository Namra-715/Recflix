-- Combined Migration for Cloud SQL
-- Run this single file to set up all social features and follow requests

-- ============================================================================
-- 1. SOCIAL FEATURES MIGRATION
-- ============================================================================

-- Follower/Following Table
CREATE TABLE IF NOT EXISTS user_follows (
    follow_id INT AUTO_INCREMENT PRIMARY KEY,
    follower_id INT NOT NULL,
    following_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (follower_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_follow (follower_id, following_id)
);

-- Playlists Table
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Playlist Movies (junction table)
CREATE TABLE IF NOT EXISTS playlist_movies (
    playlist_movie_id INT AUTO_INCREMENT PRIMARY KEY,
    playlist_id INT NOT NULL,
    movie_id INT NOT NULL,
    added_by_user_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    FOREIGN KEY (added_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_playlist_movie (playlist_id, movie_id)
);

-- Playlist Collaborators (for sharing)
CREATE TABLE IF NOT EXISTS playlist_collaborators (
    collaboration_id INT AUTO_INCREMENT PRIMARY KEY,
    playlist_id INT NOT NULL,
    user_id INT NOT NULL,
    invited_by_user_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (invited_by_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_collaboration (playlist_id, user_id)
);

-- ============================================================================
-- 2. FOLLOW REQUESTS MIGRATION
-- ============================================================================

-- Follow Requests Table
CREATE TABLE IF NOT EXISTS follow_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    requester_id INT NOT NULL,
    requested_id INT NOT NULL,
    status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (requester_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (requested_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_follow_request (requester_id, requested_id),
    INDEX idx_requested_status (requested_id, status),
    INDEX idx_requester_status (requester_id, status)
);

-- ============================================================================
-- 3. INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_follower ON user_follows(follower_id);
CREATE INDEX IF NOT EXISTS idx_following ON user_follows(following_id);
CREATE INDEX IF NOT EXISTS idx_playlist_user ON playlists(user_id);

-- ============================================================================
-- VERIFICATION (Optional - uncomment to check)
-- ============================================================================

-- SHOW TABLES LIKE 'user_follows';
-- SHOW TABLES LIKE 'playlists';
-- SHOW TABLES LIKE 'playlist_movies';
-- SHOW TABLES LIKE 'playlist_collaborators';
-- SHOW TABLES LIKE 'follow_requests';

