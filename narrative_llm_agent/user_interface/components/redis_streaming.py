import redis
from dash import DiskcacheManager
import sys
from celery import Celery
from dash import CeleryManager

from narrative_llm_agent.config import get_config

CELERY_CALLBACK_MANAGER = None
DISKCACHE_CALLBACK_MANAGER = None


def get_celery_app():
    config = get_config()
    redis_url = get_config().redis_url
    if config.use_background_llm_callbacks and redis_url is not None:
        return Celery("__main__", broker=redis_url, backend=redis_url)
    return None


def get_redis_client():
    """Get Redis client if available"""
    redis_url = get_config().redis_url
    if redis_url is not None:
        return redis.from_url(redis_url)
    return None


def get_background_callback_manager(celery_app=None):
    """Factory function to get appropriate background callback manager."""

    if celery_app is not None:
        global CELERY_CALLBACK_MANAGER
        if CELERY_CALLBACK_MANAGER is None:
            # Use Redis & Celery if REDIS_URL set as an env variable
            CELERY_CALLBACK_MANAGER = CeleryManager(celery_app)
        return CELERY_CALLBACK_MANAGER

    return None

class RedisStreamRedirector:
    def __init__(self, session_id: str, log_name: str, redis_client: redis.Redis):
        self.session_id = session_id
        self.redis_client = redis_client
        self.original_stdout = None
        self.original_stderr = None
        self.key = f"{log_name}:{session_id}"
    def __enter__(self):
        # Store original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # Redirect to this instance
        sys.stdout = self
        sys.stderr = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original streams
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        if exc_type:
            # Log exception to Redis
            self.write(f"💥 Exception: {exc_type.__name__}: {exc_val}")

    def write(self, text):
        if self.redis_client:
            # Append to Redis list
            self.redis_client.lpush(self.key, text)
            # Keep only last 1000 entries
            self.redis_client.ltrim(self.key, 0, 999)
            # Set expiration (24 hours)
            self.redis_client.expire(self.key, 86400)
        else:
            print(text, end='')

    def flush(self):
        pass


def get_logs_from_redis(session_id: str, log_name: str, redis_client: redis.Redis):
    """Retrieve logs from Redis for a given session and log type"""
    if not redis_client:
        return ""

    try:
        key = f"{log_name}:{session_id}"
        logs = redis_client.lrange(key, 0, -1)
        if logs:
            # Reverse to get chronological order
            return "".join(log.decode('utf-8') for log in reversed(logs))
    except Exception as e:
        print(f"Error reading from Redis: {e}")
        return f"Error reading logs: {e}"

    return ""
