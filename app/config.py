import os

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "health"),
    "user": os.environ.get("POSTGRES_USER", "health"),
    "password": os.environ.get("POSTGRES_PASSWORD", "change_me"),
}

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Shanghai")
HEALTH_API_KEY = os.environ.get("HEALTH_API_KEY", "")
MAX_API_BODY_BYTES = int(os.environ.get("MAX_API_BODY_BYTES", str(10 * 1024 * 1024)))
MIGRATIONS_DIR = os.environ.get("MIGRATIONS_DIR", "/app/db/migrations")

# Which source the dashboard defaults to when both Apple Health and Xiaomi
# report the same metric type on overlapping dates. Purely a display default
# -- the underlying rows for both sources are always kept, and the UI lets
# the user override this per page via an explicit source filter.
DEFAULT_SOURCE_PRIORITY = {
    "steps": "health_auto_export",
    "heart_rate": "health_auto_export",
    "resting_heart_rate": "health_auto_export",
    "hrv": "health_auto_export",
    "walking_heart_rate": "apple_health",
    "active_energy": "health_auto_export",
    "distance": "apple_health",
    "weight": "health_auto_export",
    "sleep_stage": "health_auto_export",
    "vo2_max": "health_auto_export",
}

SOURCE_LABELS = {
    "health_auto_export": "Apple Health 自动同步",
    "apple_health": "Apple Health",
    "xiaomi": "小米运动健康",
}

BATCH_SIZE = 5000
ANALYSIS_SOURCE_ORDER = ("health_auto_export", "apple_health", "xiaomi")
