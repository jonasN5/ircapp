import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = '!8gd%24y2x#6t^npsij&+)*pc^%jyzh=np%cr5e6#78l6xdv3w'
# Keep debug true while beta testing
DEBUG = True
USE_I18N = False
USE_TZ = True
# DATETIME_FORMAT = 'N jS, P'

HOST = '127.0.0.1'  # Address used to access IRCApp in the browser, changeable in config.ini
PORT = 8020  # Port used to access IRCApp in the browser, changeable in config.ini
TIME_ZONE = 'Europe/Paris'  # Timezone used by IRCApp, changeable in config.ini
DOWNLOAD_DIR = None  # Download directory used by IRCApp, changeable in config.ini
PORT_FORWARDING = None  # Timezone used in IRCApp, changeable in config.ini

# Needs to be declared explicitly for CherryPy
ROOT_URLCONF = 'urls'

"""" Uncomment and provide your own class to replace the default """
IRCAPP_SEARCH_ENGINE = 'ircapp.managers.search_engine.SunXdccSearchEngine'

ALLOWED_HOSTS = ['localhost', HOST]
INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'core',
)

MIDDLEWARE = [
    'middleware.PutParsingMiddleware',
    'middleware.DeleteParsingMiddleware'
]


if sys.platform == "win32":
    my_database = os.path.join(os.environ["LOCALAPPDATA"], "IRCApp", "IRCApp.sqlite3")
else:
    my_database = os.path.abspath(os.path.join(os.path.expanduser("~"), ".IRCApp", "IRCApp.sqlite3"))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        # 'NAME': os.path.join(os.path.dirname(sys.executable), 'db.sqlite3'),
        'NAME': my_database,
        'USER': '',  # Not used with sqlite3.
        'PASSWORD': '',  # Not used with sqlite3.
        'HOST': '',  # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',  # Set to empty string for default. Not used with sqlite3.
    }

}
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            'templates/',
            'templates',
            '/templates',
            '/templates/',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                # Insert your TEMPLATE_CONTEXT_PROCESSORS here or use this
                # list if you haven't customized them:
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.contrib.messages.context_processors.messages',
            ]
        }
    }
]
STATIC_URL = '/static/'
# STATIC_URL = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static/'),
# STATICFILES_DIRS = (
#     # Put strings here, like "/home/html/static" or "C:/www/django/static".
#     # Always use forward slashes, even on Windows.
#     # Don't forget to use absolute paths, not relative paths.
#     os.path.join(BASE_DIR, 'core', 'static'),
# )
STATIC_ROOT = os.path.join(BASE_DIR, 'core', 'static')