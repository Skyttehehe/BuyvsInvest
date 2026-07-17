from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/calculate", views.api_calculate, name="api_calculate"),
]
