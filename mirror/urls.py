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
    path("voice_chrome/", views.voice_chrome, name="voice_chrome"),
    path("voice/chat", views.voice_chat, name="voice_chat"),
    path("voice_chrome/chat", views.voice_chat, name="voice_chat"),
    path('api/request_confirmation', views.handle_request_confirmation, name='api_request_confirmation'),
    path('api/add_thought', views.handle_thought, name='api_add_thought'),
    path('api/confirmation_status/<str:action_id>', views.handle_get_confirmation_status, name='api_get_confirmation_status'),
    path('api/get_pending_ui_confirmations', views.get_pending_ui_confirmations, name='api_get_pending_ui_confirmations'),
    path('api/get_pending_thoughts', views.get_pending_thoughts, name='api_get_pending_thoughts'),
    path('api/submit_ui_confirmation/<str:action_id>', views.submit_ui_confirmation, name='api_submit_ui_confirmation'),
]
