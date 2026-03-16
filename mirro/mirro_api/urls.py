from django.urls import path
from mirro_api.views import get_xcsrf, users, auth, boards, qwe, boards_id, boards_id_accesses

urlpatterns = [
    path('get_xcsrf/', get_xcsrf, name='get_xcsrf'),
    path('users/', users, name='users'),
    path('auth/', auth, name='auth'),
    path('boards/', boards, name='boards'),
    path('qwe/', qwe, name='qwe'),
    path('boards/<int:pk_board>/', boards_id, name='boards_id'),
    path('boards_id_accesses/<int:pk_board>/', boards_id_accesses, name='boards_id_accesses'),
]