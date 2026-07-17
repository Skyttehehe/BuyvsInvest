from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-key-not-for-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "calculator",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "boligvsinvest.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {},
    },
]

WSGI_APPLICATION = "boligvsinvest.wsgi.application"

# Ingen database nødvendig - alt beregnes i hukommelsen.
DATABASES = {}

LANGUAGE_CODE = "da-dk"
TIME_ZONE = "Europe/Copenhagen"
USE_TZ = True
