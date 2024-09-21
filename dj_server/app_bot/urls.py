from django.urls import path
from . import views

from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('', views.index, name='index'),
    path('telegram', csrf_exempt(views.telegram), name='Telegram updates'),
    path('health', views.health, name='Health check')
]