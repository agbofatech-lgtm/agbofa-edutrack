from django.urls import path

from core.api.v1.auth import CsrfTokenView, LogoutView, SessionView
from core.api.v1.health import LivenessView, ReadinessView

app_name = "v1"

urlpatterns = [
    path("health/live/", LivenessView.as_view(), name="health-live"),
    path("health/ready/", ReadinessView.as_view(), name="health-ready"),
    path("auth/csrf/", CsrfTokenView.as_view(), name="auth-csrf"),
    path("auth/session/", SessionView.as_view(), name="auth-session"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
]
