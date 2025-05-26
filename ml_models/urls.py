# audio_processing/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("simple_record/", views.simple_audio_recorder, name="simple_audio_recorder"),
]
