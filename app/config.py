import os

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", "health"),
    "user": os.environ.get("POSTGRES_USER", "health"),
    "password": os.environ.get("POSTGRES_PASSWORD", "change_me"),
}

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")

# Which source the dashboard defaults to when both Apple Health and Xiaomi
# report the same metric type on overlapping dates. Purely a display default
# -- the underlying rows for both sources are always kept, and the UI lets
# the user override this per page via an explicit source filter.
DEFAULT_SOURCE_PRIORITY = {
    "steps": "apple_health",
    "heart_rate": "apple_health",
    "resting_heart_rate": "apple_health",
    "walking_heart_rate": "apple_health",
    "active_energy": "apple_health",
    "distance": "apple_health",
    "weight": "apple_health",
    "sleep_stage": "apple_health",
}

SOURCE_LABELS = {
    "apple_health": "Apple Health",
    "xiaomi": "小米运动健康",
}

BATCH_SIZE = 5000
