from django.urls import path

from .views import (
    ProfileView,
    RegistrationView,
    csrf_cookie_view,
    login_view,
    logout_view,
    refresh_view,
)

urlpatterns = [
    path("csrf/", csrf_cookie_view, name="csrf-cookie"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", login_view, name="login"),
    path("refresh/", refresh_view, name="token-refresh"),
    path("logout/", logout_view, name="logout"),
    path("me/", ProfileView.as_view(), name="profile"),
]
