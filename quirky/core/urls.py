from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    # Add your URL patterns here
    path('signup/', views.signup, name='signup'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
     path('chat/message/', views.chat_message, name='chat_message'),
     path('chat/', views.chat_page, name='chat_page'),
     path('db/', views.db_connect, name='db_connect'),
    path('login/', auth_views.LoginView.as_view(template_name = 'core/login.html'), name='login')
]