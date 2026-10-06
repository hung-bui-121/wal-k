-- Kernel-global database schema, version 1 (DOMAIN-MODEL §6.2, table -> DB mapping).
-- Lives at $WALK_HOME/kernel.db. Released migrations are immutable.

CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);
CREATE TABLE id_sequences (prefix TEXT PRIMARY KEY, next INTEGER NOT NULL);
CREATE TABLE improvement_observations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, origin_project TEXT NOT NULL, improvement_scope TEXT NOT NULL,
                         source_signal TEXT NOT NULL, work_item_id TEXT, run_id TEXT, promoted_to TEXT, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_obs_signal ON improvement_observations(source_signal, created_at);
CREATE TABLE improvement_candidates (id TEXT PRIMARY KEY, scope TEXT NOT NULL, state TEXT NOT NULL, risk TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE patterns (id TEXT PRIMARY KEY, scope TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('PATTERN','ANTI')), title TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE retrospectives (id TEXT PRIMARY KEY, level TEXT NOT NULL, subject_id TEXT NOT NULL, project_key TEXT NOT NULL, generated_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE behavior_versions (kind TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL, stage TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                         introduced_at TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY (kind, name, version));
CREATE TABLE experiments (id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT, json TEXT NOT NULL);
CREATE TABLE kernel_changelog (version TEXT NOT NULL, entry_seq INTEGER NOT NULL, candidate_id TEXT, changed TEXT NOT NULL, reason TEXT NOT NULL,
                         evidence TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY (version, entry_seq));
