-- Basic Social Features Migration
-- Run this SQL script to add follower/following and playlist tables

-- 1. Follower/Following Table
CREATE TABLE IF NOT EXISTS user_follows (
    follow_id INT AUTO_INCREMENT PRIMARY KEY,
    follower_id INT NOT NULL,
    following_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (follower_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_follow (follower_id, following_id)
);

-- 2. Playlists Table
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

-- 3. Playlist Movies (junction table)
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

-- 4. Playlist Collaborators (for sharing)
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

-- Add indexes for better performance
CREATE INDEX idx_follower ON user_follows(follower_id);
CREATE INDEX idx_following ON user_follows(following_id);
CREATE INDEX idx_playlist_user ON playlists(user_id);

