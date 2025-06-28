"""
URL configuration for MSK Earning project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin-panel/', include('mlm_app.admin_urls')),
    path('', include('mlm_app.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = "MSK Earning Admin"
admin.site.site_title = "MSK Earning"
admin.site.index_title = "Welcome to MSK Earning Administration"
