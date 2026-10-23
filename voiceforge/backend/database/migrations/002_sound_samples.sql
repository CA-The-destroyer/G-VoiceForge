-- Additive schema migration; SQLAlchemy initialize creates the same table.
CREATE TABLE IF NOT EXISTS sound_samples (
 id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, pool VARCHAR,
 species VARCHAR, event VARCHAR, review_status VARCHAR,
 source_path TEXT, audio_path TEXT, source_sha256 VARCHAR, audio_sha256 VARCHAR,
 source TEXT, processing TEXT, duration FLOAT, parent_id VARCHAR, created VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_sound_samples_pool ON sound_samples(pool);
CREATE INDEX IF NOT EXISTS ix_sound_samples_review_status ON sound_samples(review_status);
INSERT OR IGNORE INTO schema_version VALUES (2);
