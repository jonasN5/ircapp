import os, sys

try:
    par_dir = os.path.abspath(os.path.dirname(__file__))
except:
    par_dir = os.path.dirname(sys.executable)


SECRET_KEY = '!8gd%24y2x#6t^npsij&+)*pc^%jyzh=np%cr5e6#78l6xdv3w'
#keep debug true while beta testing
DEBUG = False
USE_I18N = False
USE_TZ = True
#DATETIME_FORMAT = 'N jS, P'
try:
    with open(os.path.join(par_dir, "config.ini"), "r") as cfg:    
        content = cfg.readlines()
        TIME_ZONE = content[2][10:-1].strip(" ")
except:
    TIME_ZONE = 'Europe/Paris'

    
ROOT_URLCONF = 'urls'
ALLOWED_HOSTS = ['localhost']
ADMINS = ["ircappwebmaster@gmail.com"]
INSTALLED_APPS = (
    'django.contrib.staticfiles',
    'ircapp',
)
MIDDLEWARE_CLASSES = ()
if sys.platform == "win32":
    my_database = os.path.join(os.environ["LOCALAPPDATA"], "IRCapp", "db.sqlite3")
else:
    my_database = os.path.abspath(os.path.join(par_dir, 'db.sqlite3'))
DATABASES = {
'default': {
    'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
    #'NAME': os.path.join(os.path.dirname(sys.executable), 'db.sqlite3'),
    'NAME': my_database,
    'USER': '', # Not used with sqlite3.
    'PASSWORD': '', # Not used with sqlite3.
    'HOST': '', # Set to empty string for localhost. Not used with sqlite3.
    'PORT': '', # Set to empty string for default. Not used with sqlite3.
}

}
TEMPLATES = [
{
'BACKEND': 'django.template.backends.django.DjangoTemplates',
'DIRS': [
    os.path.join(os.path.dirname(sys.executable), 'templates'),
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
#STATIC_URL = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static/'),
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(par_dir,'ircapp', 'static'),
)  
STATIC_ROOT = os.path.join(par_dir,'ircapp', 'static')



