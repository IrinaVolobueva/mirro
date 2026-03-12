from django.contrib import admin
from django.urls import path,include


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('mirro_api.urls')),
    path('app/', include('mirro_app.urls')),
]
