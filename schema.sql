CREATE DATABASE IF NOT EXISTS aws_community CHARACTER SET utf8mb4;
USE aws_community;

CREATE TABLE IF NOT EXISTS members (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  full_name     VARCHAR(120) NOT NULL,
  email         VARCHAR(160) NOT NULL UNIQUE,
  phone         VARCHAR(30),
  city          VARCHAR(80),
  country       VARCHAR(80),
  job_title     VARCHAR(120),
  company       VARCHAR(120),
  aws_level     ENUM('Beginner','Intermediate','Advanced','Expert') DEFAULT 'Beginner',
  certifications VARCHAR(255),
  skills        VARCHAR(255),
  linkedin_url  VARCHAR(255),
  bio           TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS uploads (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  member_id     INT NOT NULL,
  category      ENUM('resume','file','folder') NOT NULL,
  s3_key        VARCHAR(512) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  relative_path VARCHAR(512),
  content_type  VARCHAR(120),
  size_bytes    BIGINT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
  INDEX (member_id)
);
