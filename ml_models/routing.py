from django.urls import re_path
from . import consumers  # Create this file next

websocket_urlpatterns = [
    re_path(r"ws/asr/$", consumers.ASRConsumer.as_asgi()),
]
