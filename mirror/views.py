import os
import random
from datetime import date
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse

def dashboard(request):
    return render(request, "mirror/dashboard.html")

def vision_board_feed(request):
    folder = os.path.join(settings.BASE_DIR, "mirror/static/mirror/vision")
    images = sorted([
        f"/static/mirror/vision/{file}"
        for file in os.listdir(folder)
        if file.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))
    ])
    seed = int(date.today().strftime("%Y%m%d")) + 42
    random.Random(seed).shuffle(images)
    return JsonResponse({"images": images[:50]})
