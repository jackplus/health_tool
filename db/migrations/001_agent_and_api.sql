ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS transport TEXT NOT NULL DEFAULT 'upload';
ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS payload_hash TEXT;
ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS records_duplicate INTEGER NOT NULL DEFAULT 0;
ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS records_ignored INTEGER NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_uploads_api_hash
    ON raw_uploads (payload_hash) WHERE payload_hash IS NOT NULL;

ALTER TABLE workouts ADD COLUMN IF NOT EXISTS external_id TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_workouts_external_id
    ON workouts (source, external_id) WHERE external_id <> '';

CREATE TABLE IF NOT EXISTS insight_reports (
    id BIGSERIAL PRIMARY KEY,
    report_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rule_version TEXT NOT NULL,
    status TEXT NOT NULL,
    data_coverage JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary TEXT NOT NULL DEFAULT '',
    comparisons JSONB NOT NULL DEFAULT '{}'::jsonb,
    findings JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (report_type, period_end, rule_version)
);
ALTER TABLE insight_reports ADD COLUMN IF NOT EXISTS comparisons JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS health_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    goals JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO health_profile (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS mcp_audit_log (
    id BIGSERIAL PRIMARY KEY,
    called_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    tool_name TEXT NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    record_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);
