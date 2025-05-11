from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("vision-board-feed/", views.vision_board_feed, name="vision-board-feed"),
    path("affirmations-feed/", views.affirmations_feed, name="affirmations-feed"),
    path("task-feed/", views.task_feed, name="task-feed"),
    path("calendar-feed/", views.calendar_feed, name="calendar-feed"),
    path("habits/<str:emoji>/", views.fetch_habit_group, name="fetch_habit_group"),
    path("habits/update", views.update_habit, name="update_habit"),
    path("tasks/update", views.update_task, name="update_task"),
    path("weather/", views.weather_forecast, name="weather_forecast"),
    path("voice/", views.voice, name="voice"),
    path("voice/chat", views.voice_chat, name="voice_chat"),
]
