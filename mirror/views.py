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
from googleapiclient.discovery import build
from notion_client import Client
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST

import logging
logger = logging.getLogger(__name__)

seed_offset_vision_board = 0
seed_offset_affirmations = 0
notion = Client(auth=settings.NOTION_API_KEY)
PRIORITY_ORDER = {"High": 1, "Medium": 2, "Low": 3}
STATUS_ORDER = {"Done": 1, "Not started": 2, "In progress": 3}

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
        service = build('calendar', 'v3', credentials=creds)
        events = []
        # Time range for the next 48 hours
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone()
        time_min = now.isoformat()
        time_max = (now + datetime.timedelta(hours=48)).isoformat()
        for calendar_id in calendar_ids:
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            for event in events_result.get('items', []):
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                events.append({
                    "title": event.get("summary", "No Title"),
                    "start": start,
                    "end": end,
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                })
        events = sorted(events, key=lambda x: x['start'])
        return JsonResponse({"events": events})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def fetch_habit_group(request, emoji):  # emoji: ☀️, 🌙, 🌸
    db_id = settings.NOTION_HABIT_DB_ID

    try:
        response = notion.databases.query(
            **{
                "database_id": db_id,
                "sorts": [{"property": "Day", "direction": "descending"}],
                "page_size": 1
            }
        )
        latest = response["results"][0]
        props = latest["properties"]

        habits = []
        for key, value in props.items():
            if emoji in key and value["type"] == "checkbox":
                habits.append({
                    "title": key.strip(),
                    "done": value["checkbox"],
                    "id": latest["id"],
                    "property": key  # used for updating
                })

        return JsonResponse({"habits": habits})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def task_feed(request):
    database_id = settings.NOTION_TASK_DB_ID
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).astimezone()
    today_str = now.isoformat()
    yesterday_str = (now + datetime.timedelta(hours=-24)).isoformat()
    try:
        # 1. Fetch all children tasks due today or earlier
        child_response = notion.databases.query(
            **{
                "database_id": database_id,
                "filter": {
                    "or": [
                       {"and": [ 
                            {
                                "property": "Date",
                                "date": {
                                    "on_or_before": today_str
                                }
                            },
                            {
                                "property": "Status",
                                "status": {
                                    "does_not_equal": "Done"
                                }
                            }
                        ]},
                        {"and": [
                            {
                                "property": "Status",
                                "status": {
                                    "equals": "Done"
                                }
                            },
                            {
                                "property": "Date",
                                "date": {
                                    "on_or_after": yesterday_str
                                }
                            }]
                        }
                    ]
                }
            }
        )
        child_tasks = child_response.get("results", [])

        # 2. Collect parent IDs
        parent_ids = {
            task["properties"]["Parent item"]["relation"][0]["id"]
            for task in child_tasks
            if task["properties"]["Parent item"]["relation"]
        }

        # 3. Fetch parent tasks if any
        parent_tasks = []
        for parent_id in parent_ids:
            try:
                page = notion.pages.retrieve(parent_id)
                parent_tasks.append(page)
            except Exception:
                pass

        raw_tasks = child_tasks + parent_tasks
    except Exception as e:
        print(e)
        return JsonResponse({"error": str(e)}, status=500)
    tasks = []
    for task in raw_tasks:
        props = task["properties"]
        name = props["Name"]["title"][0]["plain_text"] if props["Name"]["title"] else "Untitled"
        status = props["Status"]["status"]["name"] if props["Status"]["status"] else None
        priority = props["Priority"]["select"]["name"] if props["Priority"]["select"] else None 
        parent_id = props["Parent item"]["relation"][0]["id"] if props["Parent item"]["relation"] else None
        date_prop = props["Date"]["date"]["start"] if props["Date"]["date"] else None
        parsed_date = parse_date(date_prop) if date_prop else None
        tasks.append({
            "id": task["id"],
            "title": name,
            "date": parsed_date,
            "status": status,
            "priority": priority,
            "priority_value": PRIORITY_ORDER.get(priority, 99),
            "status_value": STATUS_ORDER.get(status, 99),
            "parent_id": parent_id,
        })

    grouped = defaultdict(list)
    parent_lookup = {}

    for task in tasks:
        if task["parent_id"]:
            grouped[task["parent_id"]].append(task)
        else:
            parent_lookup[task["id"]] = task

    structured = []
    def compare_child(t):
        date_cmp = datetime.date.max
        if t["date"]:
            date_cmp = t["date"]
        return (date_cmp , t["priority_value"], t["status_value"])

    for parent_id, children in grouped.items():
        parent = parent_lookup.get(parent_id)
        if parent:
            structured.append({
                "parent": parent,
                "children": sorted(children, key=compare_child)
            })

    # Include standalone tasks with no children
    standalone = [
        task for task in tasks
        if task["id"] not in grouped and task["parent_id"] is None
    ]
    for task in sorted(standalone, key=lambda t: t["priority_value"]):
        structured.append({"parent": task, "children": []})
    def sort_structured(group):
        parent = group['parent']
        date_val = parent["date"] or datetime.date.max
        for child in children:
            if child["date"] and child["date"] is not None:
                if parent["date"] is None or child["date"] > parent["date"]:
                    date_val = child["date"]
        return (date_val, parent['priority_value'])
    structured.sort(key=sort_structured)
    return JsonResponse({"tasks": structured})

@ensure_csrf_cookie
def dashboard(request):
    return render(request, "mirror/dashboard.html")

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
    return JsonResponse({"images": images[:50]})

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
    affirmations = affirmations[:2] # get top 2 affirmations
    return JsonResponse({"affirmations": affirmations})

def update_task(request):
    return JsonResponse({"error": "not yet implemented"})

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
        print(page_id, prop, done)
        notion.pages.update(
            page_id=page_id,
            properties={
                prop: {"checkbox": done}
            }
        )
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

        # Update the Notion status field
        notion.pages.update(
            page_id=page_id,
            properties={
                "Status": {
                    "status": {"name": new_status}
                }
            }
        )

        return JsonResponse({"success": True})

    except Exception as e:
        logger.exception("❌ Exception in update_task")
        return JsonResponse({"error": str(e)}, status=500)
