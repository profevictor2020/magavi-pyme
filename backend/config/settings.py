"""
Configuración de Django para MAGAVI.

Toda config sensible/entorno-dependiente se lee de variables de entorno
(ver .env.example en la raíz del repo). No se versionan secretos.
"""

import os
from datetime import timedelta
from pathlib import Path

from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-dev-key-not-for-production")

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
# El default de django-cors-headers no incluye headers custom: sin esto,
# el navegador bloquea en el preflight cualquier request del frontend que
# lleve X-Company-Id (ver core/tenancy.py) — CORS no se ejerce con curl,
# así que esto solo se detecta probando contra un navegador real.
CORS_ALLOW_HEADERS = [*default_headers, "x-company-id"]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    # Apps de MAGAVI (módulos de negocio; sin modelos propios todavía)
    "core",
    "accounts",
    "companies",
    "catalog",
    "sales",
    "purchases",
    "inventory",
    "cashbox",
    "documents",
    "assistant",
    "audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los estáticos de Django (admin, DRF browsable API) desde el
    # propio proceso de gunicorn en producción, sin depender de que NGINX
    # conozca las rutas internas de Django (ver docs/DEPLOY.md).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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

WSGI_APPLICATION = "config.wsgi.application"


# Base de datos: siempre PostgreSQL (ver docs/DECISIONS.md). No se usa
# SQLite ni como fallback, para no divergir del motor de producción.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "magavi"),
        "USER": os.environ.get("POSTGRES_USER", "magavi"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "magavi_dev_password"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}


AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Argon2 primero: ver docs/SECURITY.md #2. Se mantienen los hashers de
# Django como fallback para verificar hashes existentes si algún día se
# migra el algoritmo.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]


# MAGAVI opera con micro y pequeñas empresas chilenas.
LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# Definir STORAGES reemplaza también el storage "default" (archivos
# subidos por usuarios, ver MEDIA_ROOT abajo) si no se declara
# explícitamente — Django deja de aplicar su valor por defecto
# (FileSystemStorage) en cuanto este setting existe.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Almacenamiento local para el MVP (ver docs/ARCHITECTURE.md #3.7); la
# interfaz de Django (FileField) permite migrar a S3/MinIO más adelante
# sin tocar el resto del código.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Deny-by-default (ver docs/SECURITY.md): cada vista pública debe declarar
# AllowAny de forma explícita.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # Rate limiting (ver docs/SECURITY.md #9): solo en las superficies con
    # riesgo real de abuso (fuerza bruta en auth, costo de inferencia en
    # el asistente y en el pipeline de documentos) — no un límite global
    # que pueda romper uso legítimo del resto de la API.
    "DEFAULT_THROTTLE_RATES": {
        "auth": "10/min",
        "assistant": "30/min",
        "documents": "20/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Asistente / IA (ver docs/ARCHITECTURE.md #3.5, docs/DECISIONS.md
# ADR-004 y ADR-010). "ollama" es el proveedor de producción
# (self-hosted). "deepseek_dev" es una excepción documentada SOLO para
# desarrollo/pruebas: envía mensajes a un proveedor externo, nunca debe
# usarse en producción. "fake" es para tests automáticos.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")
LLM_OLLAMA_BASE_URL = os.environ.get("LLM_OLLAMA_BASE_URL", "http://llm-inference:11434")
LLM_OLLAMA_MODEL = os.environ.get("LLM_OLLAMA_MODEL", "qwen2.5:7b-instruct")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Captura de documentos / OCR (ver docs/ARCHITECTURE.md #3.6,
# docs/DECISIONS.md ADR-005 y ADR-011, docs/SECURITY.md #6).
OCR_PROVIDER = os.environ.get("OCR_PROVIDER", "tesseract")
OCR_TESSERACT_LANG = os.environ.get("OCR_TESSERACT_LANG", "spa")
DOCUMENT_MAX_UPLOAD_SIZE_BYTES = int(
    os.environ.get("DOCUMENT_MAX_UPLOAD_SIZE_BYTES", 10 * 1024 * 1024)
)
DOCUMENT_ALLOWED_CONTENT_TYPES = env_list(
    "DOCUMENT_ALLOWED_CONTENT_TYPES", "image/jpeg,image/png,image/webp"
)

# Celery (ver docs/DECISIONS.md ADR-007): procesamiento async de OCR y
# estructuración de documentos. CELERY_TASK_ALWAYS_EAGER=true hace que
# las tareas corran en el mismo proceso, sin necesitar Redis — se usa en
# tests y puede usarse en desarrollo sin worker levantado.
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Cabeceras de transporte/seguridad (ver docs/SECURITY.md #11). Todo esto
# se activa solo cuando DEBUG=False: en dev y en CI (donde DJANGO_DEBUG
# no se define y por lo tanto DEBUG queda en True, ver env_bool arriba)
# se mantiene desactivado a propósito — SECURE_SSL_REDIRECT=True sin TLS
# real (como en el cliente de pruebas o en `docker compose` sin nginx
# delante) redirigiría toda request y rompería la app entera, no solo
# los tests. En producción, TLS lo termina NGINX (docs/ARCHITECTURE.md
# #3.8) delante de este backend.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
# X-Content-Type-Options, Referrer-Policy y X-Frame-Options ya vienen de
# los defaults de Django (SecurityMiddleware/XFrameOptionsMiddleware,
# ambos instalados arriba) — no hace falta repetirlos aquí.
