-- Project database schema, version 1 (DOMAIN-MODEL §6.2, ADR-0002).
-- Aggregate JSON + indexed projection columns. Released migrations are immutable.
-- Append-only tables (Invariant 9) abort UPDATE and DELETE via triggers (ADR-0002 D-3).

CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);
CREATE TABLE id_sequences (prefix TEXT PRIMARY KEY, next INTEGER NOT NULL);
CREATE TABLE kernel_instances (id TEXT PRIMARY KEY, hostname TEXT, started_at TEXT, heartbeat_at TEXT, pid INTEGER);
CREATE TABLE idempotency_keys (key TEXT PRIMARY KEY, operation TEXT NOT NULL, result_ref TEXT, created_at TEXT NOT NULL);

CREATE TABLE projects (key TEXT PRIMARY KEY, name TEXT NOT NULL, repo_path TEXT NOT NULL, current_phase_id TEXT,
                       paused INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE phases (id TEXT PRIMARY KEY, project_key TEXT NOT NULL REFERENCES projects(key), ordinal INTEGER NOT NULL,
                     state TEXT NOT NULL, gate_round INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX ix_phases_ordinal ON phases(project_key, ordinal);
CREATE INDEX ix_phases_state ON phases(project_key, state);

CREATE TABLE work_items (id TEXT PRIMARY KEY, kind TEXT NOT NULL, project_key TEXT NOT NULL REFERENCES projects(key),
                         parent_id TEXT REFERENCES work_items(id), phase_id TEXT REFERENCES phases(id),
                         state TEXT NOT NULL, state_version INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL,
                         owner_role TEXT, assigned_run_id TEXT, external_ref TEXT, priority TEXT NOT NULL, risk TEXT NOT NULL,
                         fix_loops INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX ix_work_items_state ON work_items(project_key, state);
CREATE INDEX ix_work_items_parent ON work_items(parent_id);
CREATE INDEX ix_work_items_phase ON work_items(phase_id, state);
CREATE UNIQUE INDEX ix_work_items_external ON work_items(external_ref) WHERE external_ref IS NOT NULL;

CREATE TABLE work_item_transitions (seq INTEGER PRIMARY KEY AUTOINCREMENT, work_item_id TEXT NOT NULL REFERENCES work_items(id),
                         from_state TEXT NOT NULL, to_state TEXT NOT NULL, event TEXT NOT NULL, source TEXT NOT NULL,
                         actor_role TEXT NOT NULL, run_id TEXT, reason TEXT, at TEXT NOT NULL);
CREATE INDEX ix_transitions_item ON work_item_transitions(work_item_id, seq);
CREATE TRIGGER work_item_transitions_immutable BEFORE UPDATE ON work_item_transitions BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE release_candidates (id TEXT PRIMARY KEY, project_key TEXT NOT NULL, number INTEGER NOT NULL, state TEXT NOT NULL,
                         commit_sha TEXT NOT NULL, json TEXT NOT NULL, created_at TEXT NOT NULL);

CREATE TABLE agent_runs (id TEXT PRIMARY KEY, project_key TEXT NOT NULL, work_item_id TEXT NOT NULL REFERENCES work_items(id),
                         role TEXT NOT NULL, model_id TEXT NOT NULL, provider TEXT NOT NULL, effort TEXT NOT NULL, state TEXT NOT NULL,
                         purpose TEXT NOT NULL, kernel_instance TEXT NOT NULL, parent_run_id TEXT, provider_session_id TEXT,
                         started_at TEXT, ended_at TEXT, json TEXT NOT NULL);
CREATE INDEX ix_runs_state ON agent_runs(state, kernel_instance);
CREATE INDEX ix_runs_item ON agent_runs(work_item_id, started_at);

CREATE TABLE checkpoints (id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES agent_runs(id), work_item_id TEXT NOT NULL,
                         seq INTEGER NOT NULL, kind TEXT NOT NULL, head_sha TEXT NOT NULL, handover_id TEXT, at TEXT NOT NULL, json TEXT NOT NULL);
CREATE UNIQUE INDEX ix_checkpoints_run_seq ON checkpoints(run_id, seq);
CREATE TRIGGER checkpoints_immutable BEFORE UPDATE ON checkpoints BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE handovers (id TEXT PRIMARY KEY, work_item_id TEXT NOT NULL, from_run_id TEXT NOT NULL, to_run_id TEXT,
                         reason TEXT NOT NULL, ai_path TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_handovers_item ON handovers(work_item_id, created_at);

CREATE TABLE ledger_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, at TEXT NOT NULL,
                         project_key TEXT NOT NULL, actor_role TEXT NOT NULL, work_item_id TEXT, run_id TEXT, phase_id TEXT,
                         model_id TEXT, tool TEXT, cost_usd REAL, outcome TEXT, json TEXT NOT NULL);
CREATE INDEX ix_ledger_kind_at ON ledger_events(kind, at);
CREATE INDEX ix_ledger_item ON ledger_events(work_item_id, seq);
CREATE INDEX ix_ledger_run ON ledger_events(run_id, seq);
CREATE INDEX ix_ledger_phase ON ledger_events(phase_id, kind);
CREATE TRIGGER ledger_events_no_update BEFORE UPDATE ON ledger_events BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
CREATE TRIGGER ledger_events_no_delete BEFORE DELETE ON ledger_events BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;

CREATE TABLE cost_records (id TEXT PRIMARY KEY, at TEXT NOT NULL, project_key TEXT NOT NULL, category TEXT NOT NULL, provider TEXT NOT NULL,
                         model_id TEXT, dimension TEXT NOT NULL, quantity REAL NOT NULL, unit TEXT NOT NULL, cost_usd REAL NOT NULL DEFAULT 0,
                         run_id TEXT, work_item_id TEXT, phase_id TEXT, role TEXT, json TEXT NOT NULL);
CREATE INDEX ix_cost_item ON cost_records(work_item_id);
CREATE INDEX ix_cost_phase ON cost_records(phase_id, category);
CREATE INDEX ix_cost_run ON cost_records(run_id);
CREATE TRIGGER cost_records_immutable BEFORE UPDATE ON cost_records BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE budgets (id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_id TEXT NOT NULL, dimension TEXT NOT NULL, "limit" REAL NOT NULL,
                         consumed REAL NOT NULL DEFAULT 0, soft_notified INTEGER NOT NULL DEFAULT 0, json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX ix_budgets_scope ON budgets(scope, scope_id);

CREATE TABLE evidence (id TEXT PRIMARY KEY, kind TEXT NOT NULL, work_item_id TEXT, phase_id TEXT, run_id TEXT, uri TEXT NOT NULL,
                         sha256 TEXT, produced_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_evidence_item ON evidence(work_item_id, kind);
CREATE INDEX ix_evidence_phase ON evidence(phase_id, kind);
CREATE TRIGGER evidence_immutable BEFORE UPDATE ON evidence BEGIN SELECT RAISE(ABORT,'immutable'); END;

CREATE TABLE decisions (id TEXT PRIMARY KEY, category TEXT NOT NULL, status TEXT NOT NULL, topic TEXT NOT NULL, owner_role TEXT NOT NULL,
                         autonomy_level INTEGER NOT NULL, debate_id TEXT, version INTEGER NOT NULL DEFAULT 1, ai_path TEXT NOT NULL,
                         decided_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_decisions_status ON decisions(status, category);
CREATE TABLE decision_work_items (decision_id TEXT NOT NULL REFERENCES decisions(id), work_item_id TEXT NOT NULL, PRIMARY KEY (decision_id, work_item_id));

CREATE TABLE debates (id TEXT PRIMARY KEY, topic TEXT NOT NULL, category TEXT NOT NULL, state TEXT NOT NULL, work_item_id TEXT,
                         round INTEGER NOT NULL DEFAULT 0, max_rounds INTEGER NOT NULL, decision_id TEXT, opened_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE debate_positions (id INTEGER PRIMARY KEY AUTOINCREMENT, debate_id TEXT NOT NULL REFERENCES debates(id), round INTEGER NOT NULL,
                         role TEXT NOT NULL, run_id TEXT NOT NULL, at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_positions_debate ON debate_positions(debate_id, round);

CREATE TABLE escalations (id TEXT PRIMARY KEY, from_role TEXT NOT NULL, to_level INTEGER NOT NULL, category TEXT NOT NULL, work_item_id TEXT,
                         run_id TEXT, approval_request_id TEXT, resolved_decision_id TEXT, created_at TEXT NOT NULL, json TEXT NOT NULL);

CREATE TABLE approval_requests (id TEXT PRIMARY KEY, kind TEXT NOT NULL, approver TEXT NOT NULL, requested_by_role TEXT NOT NULL,
                         run_id TEXT, work_item_id TEXT, state TEXT NOT NULL, requested_at TEXT NOT NULL, decided_at TEXT, json TEXT NOT NULL);
CREATE INDEX ix_approvals_state ON approval_requests(state, approver);

CREATE TABLE approved_artifacts (id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, scope TEXT NOT NULL, version INTEGER NOT NULL,
                         content_sha256 TEXT NOT NULL, ai_path TEXT NOT NULL, approved_at TEXT NOT NULL, json TEXT NOT NULL);

CREATE TABLE memory_index (path TEXT PRIMARY KEY, doc_id TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, status TEXT,
                         version INTEGER NOT NULL, updated_at TEXT NOT NULL, freshness_commit TEXT, freshness_status TEXT,
                         freshness_checked_at TEXT, raw_sha256 TEXT NOT NULL, relevant_files_json TEXT NOT NULL, related_json TEXT NOT NULL);
CREATE INDEX ix_memory_doc ON memory_index(doc_id);
CREATE INDEX ix_memory_type ON memory_index(type, status);

CREATE TABLE hook_executions (id INTEGER PRIMARY KEY AUTOINCREMENT, hook_name TEXT NOT NULL, hook_id TEXT NOT NULL, at TEXT NOT NULL,
                         run_id TEXT, work_item_id TEXT, status TEXT NOT NULL, duration_ms INTEGER NOT NULL, message TEXT);
CREATE INDEX ix_hooks_name_at ON hook_executions(hook_name, at);

CREATE TABLE commands (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, args_json TEXT NOT NULL, requested_at TEXT NOT NULL,
                         requested_by TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING');
CREATE TABLE command_results (command_id INTEGER PRIMARY KEY REFERENCES commands(id), finished_at TEXT NOT NULL, ok INTEGER NOT NULL, result_json TEXT NOT NULL);

CREATE TABLE skill_projections (skill TEXT NOT NULL, provider TEXT NOT NULL, target_path TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                         generated_from_sha256 TEXT NOT NULL, generated_at TEXT NOT NULL, PRIMARY KEY (skill, provider, target_path));

CREATE TABLE work_provider_sync (provider TEXT PRIMARY KEY, last_sync_at TEXT NOT NULL, last_delivery_id TEXT);
CREATE TABLE webhook_deliveries (delivery_id TEXT PRIMARY KEY, received_at TEXT NOT NULL);

-- improvement (PK = both DBs; project DB holds scope=PROJECT rows, kernel DB holds scope=KERNEL rows)
CREATE TABLE improvement_observations (id TEXT PRIMARY KEY, scope TEXT NOT NULL, origin_project TEXT NOT NULL, improvement_scope TEXT NOT NULL,
                         source_signal TEXT NOT NULL, work_item_id TEXT, run_id TEXT, promoted_to TEXT, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE INDEX ix_obs_signal ON improvement_observations(source_signal, created_at);
CREATE TABLE improvement_candidates (id TEXT PRIMARY KEY, scope TEXT NOT NULL, state TEXT NOT NULL, risk TEXT NOT NULL, created_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE patterns (id TEXT PRIMARY KEY, scope TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('PATTERN','ANTI')), title TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE retrospectives (id TEXT PRIMARY KEY, level TEXT NOT NULL, subject_id TEXT NOT NULL, project_key TEXT NOT NULL, generated_at TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE behavior_versions (kind TEXT NOT NULL, name TEXT NOT NULL, version TEXT NOT NULL, stage TEXT NOT NULL, content_sha256 TEXT NOT NULL,
                         introduced_at TEXT NOT NULL, json TEXT NOT NULL, PRIMARY KEY (kind, name, version));

-- BEFORE DELETE abort triggers for the remaining append-only tables (ADR-0002 D-3).
CREATE TRIGGER work_item_transitions_no_delete BEFORE DELETE ON work_item_transitions BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER checkpoints_no_delete BEFORE DELETE ON checkpoints BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER cost_records_no_delete BEFORE DELETE ON cost_records BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence BEGIN SELECT RAISE(ABORT,'immutable'); END;
