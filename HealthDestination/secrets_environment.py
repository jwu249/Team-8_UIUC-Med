# importing .env file

import environ
from pathlib import Path

env = environ.Env()

BASE_DIR = Path(__file__).resolve().parent.parent

environ.Env.read_env(BASE_DIR / ".env")

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]