from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health, name='health'),

    # Web UI -> TX queue
    path('tx/', views.tx_message, name='tx_message'),
    # ESP32 TX
    path('tx/pending/', views.tx_pending, name='tx_pending'),
    path('tx/sent/', views.tx_sent, name='tx_sent'),

    # ESP32 RX
    path('rx/', views.rx_message, name='rx_message'),

    # NEW: ESP32 Repeater
    path('repeater/activity/', views.repeater_activity, name='repeater_activity'),

    # Queries
    path('messages/', views.list_messages, name='list_messages'),
    path('stats/', views.stats, name='stats'),
]
