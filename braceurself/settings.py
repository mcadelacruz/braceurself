# project settings

from pathlib import Path

# project directory setup
BASE_DIR = Path(__file__).resolve().parent.parent


# development settings
SECRET_KEY = 'django-insecure-a-!(d%qzm-!&j6a3puxni+!1lpe0)ak-(asg&rt3zm64ms5xob'
DEBUG = True
ALLOWED_HOSTS = ['braceurself.pythonanywhere.com', '127.0.0.1']


# application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'shop',  # my main app
]

# middleware configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# url configuration
ROOT_URLCONF = 'braceurself.urls'

# template configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# wsgi configuration
WSGI_APPLICATION = 'braceurself.wsgi.application'


# database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# static files (css, javascript, images)
STATIC_URL = 'static/'

# default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'