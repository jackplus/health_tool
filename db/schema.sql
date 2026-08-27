-- Personal health data hub schema.
-- Applied automatically on first Postgres container start via
-- docker-entrypoint-initdb.d/.

CREATE TABLE IF NOT EXISTS raw_uploads (
    id                BIGSERIAL PRIMARY KEY,
    source            TEXT NOT NULL,
    filename          TEXT NOT NULL,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    status            TEXT NOT NULL DEFAULT 'pending',
    records_parsed    INTEGER NOT NULL DEFAULT 0,
    records_inserted  INTEGER NOT NULL DEFAULT 0,
    notes             TEXT
);

ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS transport TEXT NOT NULL DEFAULT 'upload';
ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS payload_hash TEXT;
ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS records_duplicate INTEGER NOT NULL DEFAULT 0;
ALTER TABLE raw_uploads ADD COLUMN IF NOT EXISTS records_ignored INTEGER NOT NULL DEFAULT 0;
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_uploads_api_hash
    ON raw_uploads (payload_hash) WHERE payload_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS health_metrics (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT NOT NULL,
    source_name         TEXT NOT NULL DEFAULT '',
    metric_type         TEXT NOT NULL,
    start_timestamp     TIMESTAMPTZ NOT NULL,
    end_timestamp       TIMESTAMPTZ NOT NULL,
    value               DOUBLE PRECISION NOT NULL,
    unit                TEXT NOT NULL DEFAULT '',
    sub_key             TEXT NOT NULL DEFAULT '',
    raw                 JSONB,
    ingestion_batch_id  BIGINT REFERENCES raw_uploads(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_name, metric_type, start_timestamp, end_timestamp, sub_key)
);

CREATE INDEX IF NOT EXISTS idx_health_metrics_type_time
    ON health_metrics (metric_type, start_timestamp);
CREATE INDEX IF NOT EXISTS idx_health_metrics_source_type_time
    ON health_metrics (source, metric_type, start_timestamp);

CREATE TABLE IF NOT EXISTS workouts (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT NOT NULL,
    source_name         TEXT NOT NULL DEFAULT '',
    external_id         TEXT NOT NULL DEFAULT '',
    workout_type        TEXT NOT NULL,
    start_timestamp     TIMESTAMPTZ NOT NULL,
    end_timestamp       TIMESTAMPTZ NOT NULL,
    duration_minutes    DOUBLE PRECISION,
    distance            DOUBLE PRECISION,
    distance_unit       TEXT,
    energy_burned       DOUBLE PRECISION,
    energy_unit         TEXT,
    raw                 JSONB,
    ingestion_batch_id  BIGINT REFERENCES raw_uploads(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_name, start_timestamp, end_timestamp, workout_type)
);

CREATE INDEX IF NOT EXISTS idx_workouts_time ON workouts (start_timestamp);
CREATE UNIQUE INDEX IF NOT EXISTS idx_workouts_external_id
    ON workouts (source, external_id) WHERE external_id <> '';

-- Optional v2: nightly/manual rollups for fast dashboard queries once raw
-- data volume makes on-the-fly aggregation slow. Not required for v1.
CREATE TABLE IF NOT EXISTS daily_rollups (
    id            BIGSERIAL PRIMARY KEY,
    day           DATE NOT NULL,
    metric_type   TEXT NOT NULL,
    source        TEXT NOT NULL,
    agg_type      TEXT NOT NULL, -- sum | avg | min | max
    agg_value     DOUBLE PRECISION NOT NULL,
    computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (day, metric_type, source, agg_type)
);

CREATE TABLE IF NOT EXISTS insight_reports (
    id              BIGSERIAL PRIMARY KEY,
    report_type     TEXT NOT NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    rule_version    TEXT NOT NULL,
    status          TEXT NOT NULL,
    data_coverage   JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary         TEXT NOT NULL DEFAULT '',
    comparisons     JSONB NOT NULL DEFAULT '{}'::jsonb,
    findings        JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (report_type, period_end, rule_version)
);

CREATE TABLE IF NOT EXISTS health_profile (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    timezone    TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    goals       JSONB NOT NULL DEFAULT '[]'::jsonb,
    constraints JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO health_profile (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS mcp_audit_log (
    id           BIGSERIAL PRIMARY KEY,
    called_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    tool_name    TEXT NOT NULL,
    params       JSONB NOT NULL DEFAULT '{}'::jsonb,
    record_count INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL
);
