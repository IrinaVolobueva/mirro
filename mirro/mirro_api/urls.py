from django.urls import path
from mirro_api.views import get_xcsrf, users, auth, boards, qwe

urlpatterns = [
    path('get_xcsrf/', get_xcsrf, name='get_xcsrf'),
    path('users/', users, name='users'),
    path('auth/', auth, name='auth'),
    path('boards/', boards, name='boards'),
    path('qwe/', qwe, name='qwe')
]