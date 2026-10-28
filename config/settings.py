import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-smartlib-secret-key-pq9-2026-xusniddin-gofurov')

# Development vs Production DEBUG
is_render = bool(os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_HOSTNAME'))
DEBUG = os.environ.get('DJANGO_DEBUG', str(not is_render)).lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
    'https://*.loca.lt',
    'https://*.lhr.life',
    'https://*.localhost.run',
    'https://*.serveousercontent.com',
    'https://*.serveo.net',
    'https://*.pinggy.link',
    'https://*.pinggy.io',
    'https://*.pinggy.online',
    'https://*.onrender.com',
    'https://*.up.railway.app',
    'https://*.pythonanywhere.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

try:
    import socket as _sock
    _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
    _s.settimeout(0.1)
    _s.connect(('8.8.8.8', 80))
    _lan_ip = _s.getsockname()[0]
    _s.close()
    if _lan_ip and f'http://{_lan_ip}:8000' not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f'http://{_lan_ip}:8000')
except Exception:
    pass

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'books',
]

MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
                'books.context_processors.smartlib_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

database_url = os.environ.get('DATABASE_URL', '').strip()
if database_url:
    import urllib.parse
    parsed_db = urllib.parse.urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': parsed_db.path.lstrip('/'),
            'USER': parsed_db.username,
            'PASSWORD': parsed_db.password,
            'HOST': parsed_db.hostname,
            'PORT': parsed_db.port or 5432,
            'CONN_MAX_AGE': 600,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_USER_MODEL = 'users.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_BOT_USERNAME = os.environ.get('TELEGRAM_BOT_USERNAME', 'SmartLibUzBot')
TELEGRAM_ADMIN_CHAT_ID = os.environ.get('TELEGRAM_ADMIN_CHAT_ID', '')

LANGUAGE_CODE = 'uz'

LANGUAGES = [
    ('uz', "O'zbekcha"),
    ('ru', 'Русский'),
    ('en', 'English'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

JAZZMIN_SETTINGS = {
    "site_title": "SmartLib Admin",
    "site_header": "SmartLib",
    "site_brand": "SmartLib",
    "welcome_sign": "SmartLib tizimiga xush kelibsiz",
    "copyright": "SmartLib Solutions",
    "search_model": ["users.CustomUser", "books.Book"],
    "user_avatar": "profile_picture",
    "topmenu_links": [
        {"name": "Saytga o'tish", "url": "home", "new_window": False},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "users",
        "users.Library",
        "users.CustomUser",
        "users.StudentBase",
        "auth",
        "books",
        "books.Book",
        "books.BookCopy",
        "books.Loan",
        "books.Reservation",
        "books.Genre",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-circle",
        "users.Library": "fas fa-university",
        "users.CustomUser": "fas fa-user-graduate",
        "users.StudentBase": "fas fa-database",
        "books.Book": "fas fa-book",
        "books.BookCopy": "fas fa-barcode",
        "books.Loan": "fas fa-hand-holding",
        "books.Reservation": "fas fa-clock",
        "books.Review": "fas fa-star",
        "books.Favorite": "fas fa-heart",
        "books.Notification": "fas fa-bell",
        "books.Genre": "fas fa-tags",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_css": "css/admin_custom.css",
    "custom_js": "js/admin_custom.js",
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
}

