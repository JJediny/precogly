"""
Production settings for Precogly backend.
"""

from .base import *  # noqa: F401, F403

DEBUG = False

# Security settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Stricter CORS in production
CORS_ALLOW_ALL_ORIGINS = False

# No loopback model endpoints on an exposed deployment. Any org member can save
# one, and signup adds new users to the primary organization automatically, so on
# an install with open registration a permissive policy hands anyone who can
# register a request originating inside the network. A deployment that really does
# run its model on the same host sets AI_PROVIDER_URL_POLICY back to allow-loopback.
AI_PROVIDER_URL_POLICY = env.str(  # noqa: F405
    "AI_PROVIDER_URL_POLICY", default="deny-private"
)

# Email backend for production
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
