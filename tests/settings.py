from __future__ import annotations

DEBUG = False

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django_q",
    "tests",
]

Q_CLUSTER = {
    "name": "test",
    "sync": True,
    "workers": 1,
    "timeout": 90,
    "retry": 120,
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",
}

SECRET_KEY = "test-secret-key"

USE_TZ = True
