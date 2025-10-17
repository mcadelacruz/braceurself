# main url configuration for the project

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # url for the django admin site
    path('admin/', admin.site.urls),
    # includes all urls from the shop app
    path('', include('shop.urls')),
]

# serves media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)