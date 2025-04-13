from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("vision-board-feed", views.vision_board_feed, name="vision-board-feed"),
]
