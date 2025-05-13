import asyncio
import datetime
import json
import os
import random
import requests
from collections import defaultdict
from dateutil.parser import parse as parse_date
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_date
from google.oauth2 import service_account
from notion_client import Client
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
import pytz
local_tz = pytz.timezone("America/New_York")  # or whatever your timezone is

from . import database_functions
from .services import get_mcp_service

import logging
logger = logging.getLogger(__name__)

seed_offset_vision_board = 0
seed_offset_affirmations = 0
notion = Client(auth=settings.NOTION_API_KEY)
PRIORITY_ORDER = {"High": 1, "Medium": 2, "Low": 3}
STATUS_ORDER = {"Done": 3, "Not started": 1, "In progress": 2}
VISION_BOARD_IMAGE_COUNT = 24

def weather_forecast(request):
    lat = 42.3601
    lon = -71.0942
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,apparent_temperature,weather_code"
        f"&temperature_unit=fahrenheit"
    )
    try:
        r = requests.get(url)
        data = r.json()["current"]
        return JsonResponse({
            "temp": data["temperature_2m"],
            "feels_like": data["apparent_temperature"],
            "weather_code": data["weather_code"]
        })
    except Exception as e:
        print(e)
        return JsonResponse({"error": str(e)}, status=500)

def calendar_feed(request):
    try:
        # Credentials & Calendar Setup
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        creds_path = os.path.join(settings.BASE_DIR, settings.GOOGLE_CALENDAR_CRED_PATH)
        calendar_ids = settings.GOOGLE_CALENDAR_IDS
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        events = database_functions.calendar_feed(creds, calendar_ids)
        return JsonResponse({"events": events})
    except Exception as e:
        print(e)
        return JsonResponse({"error": str(e)}, status=500)


def fetch_habit_group(request, emoji):  # emoji: ☀️, 🌙, 🌸
    db_id = settings.NOTION_HABIT_DB_ID
    try:
        habits = database_functions.fetch_habit_group(notion, emoji, db_id)
    except Exception as e:
        print(e)
        return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"habits": habits})

def task_feed(request):
    database_id = settings.NOTION_TASK_DB_ID
    try:
        root_tasks = database_functions.task_feed(notion, database_id)
    except Exception as e:
        print(e)
        return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"tasks": root_tasks})

@ensure_csrf_cookie
def dashboard(request):
    return render(request, "mirror/dashboard.html")

@ensure_csrf_cookie
def voice_chrome(request):
    return render(request, "mirror/voice_chat_chrome.html")

@ensure_csrf_cookie
def voice(request):
    return render(request, "mirror/voice_chat.html")

@csrf_exempt # Keep if you need to bypass CSRF for this API endpoint
@require_http_methods(["POST"]) # Ensures this view only accepts POST requests
async def voice_chat(request):
    try:
        data = json.loads(request.body)
        msg = data.get("message", "").strip()

        if not msg:
            logger.warning("Voice chat request with empty message.")
            return JsonResponse({"error": "Message cannot be empty."}, status=400)

        # Get the initialized and connected MCP service
        mcp_service = await get_mcp_service()
        
        logger.info(f"Processing voice chat query: '{msg}'")
        # The mcp_service.client.session can be checked here if needed for debugging
        # logger.debug(f"MCP Session state: {mcp_service.client.session}")

        response_text = await mcp_service.process_query(msg)
        response_text = response_text.split('\n')
        return JsonResponse({"response": response_text})

    except json.JSONDecodeError:
        logger.error("Invalid JSON received in voice_chat request.", exc_info=True)
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        # Log the full exception details for debugging
        logger.error(f"Error processing voice_chat request: {type(e).__name__}: {e}", exc_info=True)
        # Provide a generic error message to the client
        return JsonResponse({"error": f"An internal error occurred: {str(e)}"}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
async def voice_chat2(request):
    #try:
        data = json.loads(request.body)
        msg = data.get("message", "").strip()
        if not msg:
            return JsonResponse({"error": str(e)}, status=500)
        await _ensure_connected()
        print(mcp_client.session)
        response = await mcp_client.process_query(msg)
        return JsonResponse({"response": response})
    #except Exception as e:
    #    return JsonResponse({"error": str(e)}, status=500)

def vision_board_feed(request):
    global seed_offset_vision_board
    folder = os.path.join(settings.BASE_DIR, "mirror/static/mirror/vision")
    images = sorted([
        f"/static/mirror/vision/{file}"
        for file in os.listdir(folder)
        if file.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))
    ])
    seed = int(datetime.date.today().strftime("%Y%m%d")) + 42 + seed_offset_vision_board
    seed_offset_vision_board -= 1
    random.Random(seed).shuffle(images)
    return JsonResponse({"images": images[:VISION_BOARD_IMAGE_COUNT]})

def affirmations_feed(request):
    global seed_offset_affirmations
    file_path = os.path.join(
        settings.BASE_DIR, "mirror/static/mirror/data/affirmations.json"
    )
    with open(file_path, "r", encoding="utf-8") as f:
        affirmations = json.load(f)

    seed = int(datetime.date.today().strftime("%Y%m%d")) + 42 + seed_offset_affirmations
    seed_offset_affirmations -= 1 # on refresh show yesterday's affirmations
    random.Random(seed).shuffle(affirmations)
    affirmations = affirmations[:1] # get top affirmation
    return JsonResponse({"affirmations": affirmations})

@csrf_protect
@require_POST
def update_habit(request):
    try:
        body = request.body.decode("utf-8")
        data = json.loads(body)
        page_id = data.get("page_id")
        prop = data.get("property")
        done = data.get("done")
        if not page_id or not prop:
            logger.error("❌ Missing required fields")
            return JsonResponse({"error": "Missing page_id or property"}, status=400)
        database_functions.update_habit(notion, page_id, prop, done)
        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Exception in update_habit")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_protect
@require_POST
def update_task(request):
    try:
        body = request.body.decode("utf-8")
        data = json.loads(body)

        page_id = data.get("page_id")
        new_status = data.get("status")  # e.g. "Complete", "In Progress", etc.

        if not page_id or not new_status:
            logger.error("❌ Missing page_id or status in task update")
            return JsonResponse({"error": "Missing page_id or status"}, status=400)

        print(f"📝 Updating task {page_id} → status: {new_status}")

        database_functions.update_task(notion, page_id, new_status)
        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Exception in update_task")
        return JsonResponse({"error": str(e)}, status=500)
