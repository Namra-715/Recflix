-- Follow Requests Migration
-- Run this SQL script to add follow request functionality

-- Create follow_requests table
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

