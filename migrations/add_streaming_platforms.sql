-- Create StreamingPlatforms table for tracking where content is available
-- Safe to run multiple times in Cloud SQL (IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS StreamingPlatforms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(512) NOT NULL,
  year SMALLINT,
  age_rating VARCHAR(64),
  imdb_rating DECIMAL(3,1),
  rotten_tomatoes_rating VARCHAR(16),
  netflix TINYINT(1) DEFAULT 0,
  hulu TINYINT(1) DEFAULT 0,
  prime_video TINYINT(1) DEFAULT 0,
  disney_plus TINYINT(1) DEFAULT 0,
  content_type VARCHAR(32),
  directors VARCHAR(1024),
  genres VARCHAR(1024),
  country VARCHAR(256),
  language VARCHAR(256),
  runtime INT,
  release_date DATE,
  last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


