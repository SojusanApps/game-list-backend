"""This is a base configuration for MyGameList Django application."""

import logging
import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from django.utils.translation import gettext_lazy as _

from my_game_list import __version__

oeg = os.environ.get

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = oeg("DJANGO_SECRET_KEY", "secret_key_to_change_on_production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = oeg("DJANGO_DEBUG", "False").lower() == "true"

CORS_ALLOWED_ORIGINS = oeg("DJANGO_CORS_ALLOWED_ORIGINS", "*").split(",")
ALLOWED_HOSTS = oeg("DJANGO_ALLOWED_HOSTS", "*").split(",")

# The default value "" with a combination of split(",") returns [""] instead of empty list [], as a default value.
django_csrf_trusted_origins = oeg("DJANGO_CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = django_csrf_trusted_origins.split(",") if django_csrf_trusted_origins else []

DOCUMENTATION_ENABLED = oeg("DJANGO_DOCUMENTATION_ENABLED", "True").lower() == "true"

MAIN_APP = "my_game_list"

INSTALLED_APPS = [
    # modeltranslation must be before django.contrib.admin to properly register translation options for admin interface
    "modeltranslation",
    # Django apps
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third party apps
    "rest_framework",
    "drf_spectacular",
    "django_extensions",
    "django_filters",
    "corsheaders",
    "django_prometheus",
    "django_celery_results",
    "django_celery_beat",
    # Internal apps
    f"{MAIN_APP}.{MAIN_APP}",
    f"{MAIN_APP}.users",
    f"{MAIN_APP}.games",
    f"{MAIN_APP}.collections",
    f"{MAIN_APP}.friendships",
    f"{MAIN_APP}.notifications",
    f"{MAIN_APP}.moderation",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "my_game_list.users.middleware.UpdateLastActivityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = f"{MAIN_APP}.{MAIN_APP}.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = f"{MAIN_APP}.{MAIN_APP}.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": oeg("DJANGO_DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": oeg("POSTGRES_DB", "my_game_list"),
        "USER": oeg("POSTGRES_USER", "my_game_list"),
        "PASSWORD": oeg("POSTGRES_PASSWORD", "my_game_list"),
        "HOST": oeg("POSTGRES_HOST", "localhost"),
        "PORT": oeg("POSTGRES_PORT", "5432"),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": oeg("REDIS_URL", "redis://localhost:6379"),
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGES = (
    ("en", _("English")),
    ("pl", _("Polish")),
)

LANGUAGE_CODE = "en-us"

MODELTRANSLATION_DEFAULT_LANGUAGE = "en"
MODELTRANSLATION_FALLBACK_LANGUAGES = {"default": ("en",)}

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

ROSETTA_MESSAGES_SOURCE_LANGUAGE_CODE = "en"
ROSETTA_SHOW_AT_ADMIN_PANEL = True

LOCALE_PATHS = [
    BASE_DIR / "locale",
]

STATIC_URL = "/static/"
STATIC_ROOT = f"/opt/{MAIN_APP}/static"

MEDIA_URL = "/media/"
MEDIA_ROOT = f"/opt/{MAIN_APP}/media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.User"

CORS_ALLOWED_ORIGINS = oeg("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:4200").split(",")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("my_game_list.my_game_list.authentication.KeycloakAuthentication",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

KEYCLOAK_SERVER_URL = oeg("KEYCLOAK_SERVER_URL", "https://keycloak_server_url_to_change_on_production")
KEYCLOAK_REALM = oeg("KEYCLOAK_REALM", "my-game-list")
KEYCLOAK_AUDIENCE = oeg("KEYCLOAK_AUDIENCE", "my-game-list-frontend")
KEYCLOAK_CLIENT_ID = oeg("KEYCLOAK_CLIENT_ID", "my-game-list-frontend")

SPECTACULAR_SETTINGS = {
    "TITLE": "MyGameList API",
    "DESCRIPTION": "Application to manage game lists.",
    "VERSION": ".".join(map(str, __version__)),
    "SCHEMA_PATH_PREFIX": "/api/",
    "TAGS": [
        {
            "name": "collection",
            "description": (
                "Manage user-created game collections and their items. "
                "Collections have three visibility levels — PUBLIC, FRIENDS, PRIVATE — "
                "and three modes: STANDARD, TIER_LIST, and COLLABORATIVE. "
                "COLLABORATIVE collections allow invited collaborators to add and reorder "
                "items alongside the owner. Item positions are maintained via server-managed "
                "fractional decimal values that allow insertion without renumbering other items."
            ),
        },
        {
            "name": "game",
            "description": (
                "Browse and interact with the game catalogue. "
                "Covers the core Game resource, user game-tracking via GameList (with statuses "
                "such as Playing, Completed, and Plan to Play), social interactions "
                "(GameFollow, GameReview, GameMedia), and the read-only Lookup Models "
                "that categorise games: Genre, Platform, Company, GameType, GameStatus, "
                "GameEngine, GameMode, PlayerPerspective, and ExternalGameSource. "
                "Lookup Models are sourced from IGDB or maintained manually and are "
                "only writable by administrators."
            ),
        },
        {
            "name": "friendship",
            "description": (
                "Manage friendships and friendship requests between users. "
                "A Friendship is a confirmed, bidirectional relationship between two users. "
                "A FriendshipRequest is a pending invitation; accepting it creates reciprocal "
                "Friendship records for both parties and sends a notification to the requester."
            ),
        },
        {
            "name": "notification",
            "description": (
                "Retrieve and manage in-app notifications for the authenticated user. "
                "Notifications are generated automatically by system events such as incoming "
                "friendship requests and accepted requests. Each notification carries a "
                "category (e.g. FRIENDSHIP), a level (INFO, WARNING, ERROR), and an unread flag."
            ),
        },
        {
            "name": "user",
            "description": (
                "Register new users and manage user accounts. "
                "User creation (registration) is publicly accessible without authentication; "
                "all other operations require a valid session. "
                "The detail endpoint returns additional private fields to the authenticated "
                "account owner that are not visible to other users."
            ),
        },
        {
            "name": "version",
            "description": (
                "Application version information. "
                "Returns the current semantic version of the running API. "
                "This endpoint is publicly accessible without authentication."
            ),
        },
    ],
    "ENUM_NAME_OVERRIDES": {
        "GameListStatusEnum": "my_game_list.games.models.GameListStatus",
        "TranslationSuggestionStatusEnum": "my_game_list.games.models.TranslationSuggestionStatus",
        "ReportStatusEnum": "my_game_list.moderation.models.ReportStatus",
    },
}

MGL_LOG_DIR_PATH = oeg("MGL_LOG_DIR_PATH", BASE_DIR.parent.parent / "logs")
MGL_LOG_FILENAME = oeg("MGL_LOG_FILENAME", "my_game_list.log")

if not (log_path := Path(MGL_LOG_DIR_PATH)).is_dir():
    log_path.mkdir(exist_ok=True)

LOG_FILE_PATH = Path(MGL_LOG_DIR_PATH, MGL_LOG_FILENAME)
LOGLEVEL = oeg("DJANGO_LOGLEVEL", "INFO").upper()


class OTelFallbackFilter(logging.Filter):
    """Ensures OTEL fields exist on log records before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add OTEL fields with default values if they are missing."""
        if not hasattr(record, "otelTraceID"):
            record.otelTraceID = "0"
            record.otelSpanID = "0"
            record.otelServiceName = ""
        return True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
        "otel_fallback": {
            "()": "my_game_list.settings.base.OTelFallbackFilter",
        },
    },
    "formatters": {
        "color": {
            "()": "colorlog.ColoredFormatter",
            "format": (
                "{log_color}[{asctime}] {levelname}\t{module} - {funcName}"
                " [trace_id={otelTraceID} span_id={otelSpanID}] :: {message}"
            ),
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "log_colors": {
                "DEBUG": "light_black",
                "INFO": "cyan",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "colorlog.StreamHandler",
            "formatter": "color",
            "filters": ["require_debug_true", "otel_fallback"],
        },
        "file": {
            "level": LOGLEVEL,
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "color",
            "filters": ["otel_fallback"],
            "backupCount": 5,
            "maxBytes": 5242880,  # 5*1024*1024 bytes (5MB)
            "filename": LOG_FILE_PATH,
            "encoding": "utf8",
        },
    },
    "loggers": {
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
        "django.db.backends": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "error": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "django": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "django.server": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
}

MYPYPATH = BASE_DIR.parent.parent / "stubs"

IGDB_CLIENT_ID = oeg("IGDB_CLIENT_ID", "client_id_to_change_on_production")
IGDB_CLIENT_SECRET = oeg("IGDB_CLIENT_SECRET", "secret_key_to_change_on_production")

# Celery configuration
CELERY_BROKER_URL = oeg("CELERY_BROKER_URL", "amqp://guest:guest@rabbitmq:5672//")
CELERY_RESULT_BACKEND = oeg("CELERY_RESULT_BACKEND", "django-db")
CELERY_CACHE_BACKEND = "django-cache"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "cleanup-notifications-daily": {
        "task": "my_game_list.notifications.tasks.cleanup_old_notifications",
        "schedule": timedelta(days=1),
    },
    "notify-game-releases-daily": {
        "task": "my_game_list.notifications.tasks.notify_game_releases",
        "schedule": crontab(hour=3, minute=0),
    },
    "nightly-igdb-import-and-recalculate": {
        "task": "my_game_list.games.tasks.nightly_igdb_import_and_recalculate",
        "schedule": crontab(hour=0, minute=0),
    },
}

STEAM_API_KEY = oeg("STEAM_API_KEY", "steam_api_key_to_change_on_production")
