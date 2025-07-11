from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transfer/', views.transfer_money, name='transfer_money'),
    # path('verify/<uuid:token>/', views.verify_email, name='verify_email'),
    path('messages/', views.user_messages, name='user_messages'),  # Chat messages
    path('send-message/', views.send_message, name='send_message'),  # Send message
    path('top-up/', views.top_up, name='top_up'),  # Top-up functionality
    path('deposit/', views.deposit, name='deposit'),  # Deposit functionality
    path('transaction-history/', views.transaction_history, name='transaction_history'),  # Transaction history
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
]

