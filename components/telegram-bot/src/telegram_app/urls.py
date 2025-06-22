from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('bot/webhook/', views.telegram_webhook, name='telegram_webhook'),
] 