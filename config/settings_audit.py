"""
Audit sozlamalari: asl db.sqlite3 ga TEGMAYDI.
Barcha testlar backups/ ichidagi nusxada bajariladi.
"""
import os
from .settings import *  # noqa: F401,F403

AUDIT_DB = os.environ.get('SMARTLIB_AUDIT_DB')
if not AUDIT_DB:
    raise RuntimeError("SMARTLIB_AUDIT_DB muhit o'zgaruvchisi berilmagan (asl bazani himoya qilish uchun).")

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': AUDIT_DB,
    }
}
MEDIA_ROOT = os.path.join(os.path.dirname(AUDIT_DB), 'audit_media')
ALLOWED_HOSTS = ['*', 'testserver']
AUTH_PASSWORD_VALIDATORS = []
