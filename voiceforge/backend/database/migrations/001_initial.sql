-- Schema version 1; initial install only.
CREATE TABLE characters (
	id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	species VARCHAR,
	profile TEXT,
	active_version INTEGER,
	created VARCHAR,
	PRIMARY KEY (id)
);
CREATE TABLE voice_versions (
	id VARCHAR NOT NULL,
	character_id VARCHAR,
	version INTEGER,
	path TEXT,
	sha256 VARCHAR,
	transcript TEXT,
	config TEXT,
	emotion VARCHAR,
	created VARCHAR,
	PRIMARY KEY (id)
);
CREATE INDEX ix_voice_versions_character_id ON voice_versions (character_id);
CREATE TABLE jobs (
	id VARCHAR NOT NULL,
	character_id VARCHAR,
	dialogue_id VARCHAR,
	text TEXT,
	emotion VARCHAR,
	settings TEXT,
	status VARCHAR,
	progress FLOAT,
	error TEXT,
	result TEXT,
	approved INTEGER,
	created VARCHAR,
	PRIMARY KEY (id)
);
CREATE INDEX ix_jobs_status ON jobs (status);
CREATE INDEX ix_jobs_dialogue_id ON jobs (dialogue_id);
CREATE INDEX ix_jobs_character_id ON jobs (character_id);
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
