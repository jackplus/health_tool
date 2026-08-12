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
