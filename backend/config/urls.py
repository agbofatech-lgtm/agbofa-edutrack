from django.urls import include, path

urlpatterns = [
    path("api/v1/", include(("core.api.v1.urls", "api"), namespace="v1")),
]
