-- Performance Optimization: Add Indexes for Movies Table
-- Run this on your Cloud SQL instance to improve query performance
-- Note: If indexes already exist, you may get errors - that's okay, just skip those lines

-- Index for release_date (used in trending movies query)
CREATE INDEX idx_movies_release_date ON movies(release_date);

-- Index for popularity (used in sorting)
CREATE INDEX idx_movies_popularity ON movies(popularity DESC);

-- Index for vote_average (used in sorting)
CREATE INDEX idx_movies_vote_avg ON movies(vote_average DESC);

-- Index for poster_path (used in filtering)
CREATE INDEX idx_movies_poster_path ON movies(poster_path(255));

-- Index for title (used in search)
CREATE INDEX idx_movies_title ON movies(title);

-- Composite index for trending query (MOST IMPORTANT!)
-- This index covers the WHERE and ORDER BY clauses for the optimized query
CREATE INDEX idx_movies_trending 
ON movies(release_date, popularity DESC, vote_average DESC, vote_count DESC);

-- Additional covering index for the optimized query
-- Includes all columns needed so MySQL doesn't need to access the table
CREATE INDEX idx_movies_trending_covering 
ON movies(release_date, popularity DESC, vote_average DESC, vote_count, poster_path(255), id, title);

-- Index for movie lookups by ID (if not already primary key)
-- Note: PRIMARY KEY already exists, but this ensures fast lookups
-- CREATE INDEX IF NOT EXISTS idx_movies_id ON movies(id); -- Usually not needed if id is PRIMARY KEY

-- Verify indexes were created
SHOW INDEXES FROM movies;

