import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
IS_PRODUCTION = os.getenv("DJANGO_ENV", "development").lower() == "production" or bool(
    os.getenv("VERCEL")
)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
allowed_hosts_value = os.getenv("DJANGO_ALLOWED_HOSTS", "")
cors_origins_value = os.getenv("CORS_ALLOWED_ORIGINS", "")
if IS_PRODUCTION and not all((SECRET_KEY, allowed_hosts_value, cors_origins_value)):
    raise ImproperlyConfigured(
        "Production requires DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, and CORS_ALLOWED_ORIGINS."
    )
if IS_PRODUCTION and len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("Production DJANGO_SECRET_KEY must contain at least 50 characters.")
SECRET_KEY = SECRET_KEY or "trucktrack-local-development-key"
ALLOWED_HOSTS = [
    host.strip()
    for host in (allowed_hosts_value or "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]
if IS_PRODUCTION and "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production DJANGO_ALLOWED_HOSTS cannot contain '*'.")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "planner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "trip_api.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
WSGI_APPLICATION = "trip_api.wsgi.application"
ASGI_APPLICATION = "trip_api.asgi.application"

# This service is intentionally stateless and does not need a database.
DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (cors_origins_value or "http://localhost:5173").split(",")
    if origin.strip()
]
CORS_ALLOW_ALL_ORIGINS = not IS_PRODUCTION and (
    os.getenv("CORS_ALLOW_ALL_ORIGINS", "false").lower() == "true"
)

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "planner.errors.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "locations": os.getenv("LOCATIONS_THROTTLE_RATE", "60/min"),
        "trip_plans": os.getenv("TRIP_PLANS_THROTTLE_RATE", "10/min"),
    },
    "NUM_PROXIES": 1 if IS_PRODUCTION else None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "TruckTrack Trip Planning API",
    "DESCRIPTION": "HGV routing and FMCSA hours-of-service planning.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

ORS_API_KEY = os.getenv("ORS_API_KEY", "")
ORS_API_BASE_URL = os.getenv("ORS_API_BASE_URL", "https://api.heigit.org")
ORS_TIMEOUT_SECONDS = float(os.getenv("ORS_TIMEOUT_SECONDS", "20"))

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = IS_PRODUCTION
SECURE_HSTS_SECONDS = 31_536_000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_HSTS_PRELOAD = IS_PRODUCTION
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
