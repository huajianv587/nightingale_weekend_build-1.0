
CREATE DATABASE IF NOT EXISTS nightingale_grip CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nightingale_grip;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('patient','clinician') NOT NULL,
  clinic_id BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS threads (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  patient_id BIGINT NOT NULL UNIQUE,
  clinic_id BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS messages (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  thread_id BIGINT NOT NULL,
  sender_role ENUM('patient','assistant','clinician','system') NOT NULL,
  content TEXT NOT NULL,
  redacted_for_llm TEXT NULL,
  confidence ENUM('low','med','high') NULL,
  risk_level ENUM('low','medium','high') NULL,
  risk_reason VARCHAR(255) NULL,
  risk_provenance DATETIME NULL,
  citations_json JSON NULL,
  is_ground_truth BOOLEAN NOT NULL DEFAULT FALSE,
  audio_asset_id VARCHAR(255) NULL,
  audio_transcript_id VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE,
  INDEX idx_messages_thread_created (thread_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS memory_items (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  patient_id BIGINT NOT NULL,
  kind ENUM('chief_complaint','symptom','medication','allergy') NOT NULL,
  value VARCHAR(255) NOT NULL,
  status ENUM('active','stopped','resolved','unknown') NOT NULL DEFAULT 'active',
  timeline_text VARCHAR(255) NULL,
  provenance_message_id BIGINT NOT NULL,
  provenance_start INT NOT NULL DEFAULT 0,
  provenance_end INT NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_memory_patient_kind (patient_id, kind)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS tickets (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  clinic_id BIGINT NOT NULL,
  patient_id BIGINT NOT NULL,
  thread_id BIGINT NOT NULL,
  status ENUM('open','closed') NOT NULL DEFAULT 'open',
  triggering_message_id BIGINT NOT NULL,
  risk_level ENUM('medium','high') NOT NULL,
  triage_summary_json JSON NOT NULL,
  profile_snapshot_json JSON NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  closed_at DATETIME NULL,
  FOREIGN KEY (patient_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE,
  INDEX idx_tickets_clinic_status (clinic_id, status, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  event_type VARCHAR(64) NOT NULL,
  actor_user_id BIGINT NULL,
  target_type VARCHAR(64) NULL,
  target_id VARCHAR(64) NULL,
  meta_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_audit_created (created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS request_fingerprints (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  kind ENUM('ip','device','phone') NOT NULL,
  fingerprint_hash CHAR(64) NOT NULL,
  strikes INT NOT NULL DEFAULT 0,
  blocked_until DATETIME NULL,
  last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_kind_hash (kind, fingerprint_hash)
) ENGINE=InnoDB;
