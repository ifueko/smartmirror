import asyncio
import datetime
import logging
import json
import os
import pytz
import random
import requests
import uuid

from collections import defaultdict
from dateutil.parser import parse as parse_date
from google.oauth2 import service_account
from notion_client import Client

from django.conf import settings
from django.http import JsonResponse, HttpRequest
from django.shortcuts import render
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from typing import Dict, Any, Literal, List

from . import database_functions
from .services import get_mcp_service

logger = logging.getLogger(__name__)
local_tz = pytz.timezone("America/New_York")
confirmations_db: Dict[str, Dict[str, Any]] = {}
db_lock = asyncio.Lock()
ConfirmationStatusLiteral = Literal["pending", "confirmed", "denied", "timeout", "error", "not_found"]
StoredConfirmationStatusLiteral = Literal["pending", "confirmed", "denied", "timeout", "error"]
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

@csrf_exempt
@require_http_methods(["POST"])
async def voice_chat(request):
    try:
        data = json.loads(request.body)
        msg = data.get("message", "").strip()
        confirmed_action_details = data.get("confirmed_action_details") # Sent by frontend on confirm

        mcp_service = await get_mcp_service()
        if not mcp_service or not mcp_service.client or not mcp_service.client.session:
             logger.error("MCP Service or session not available.")
             return JsonResponse({"error": "Voice service is currently unavailable."}, status=503)


        if confirmed_action_details:
            # User has confirmed an action from the modal
            tool_name = confirmed_action_details.get("tool_name")
            parameters = confirmed_action_details.get("parameters", {})
            parameters["confirmed_by_user"] = True # Crucial: signal confirmation

            if not tool_name:
                logger.error("Confirmed action details missing tool_name.")
                return JsonResponse({"error": "Invalid confirmation request."}, status=400)

            logger.info(f"Executing confirmed MCP tool: '{tool_name}' with params: {parameters}")
            try:
                # Directly call the MCP tool via the session
                # Ensure mcp_service.client.session is valid
                if not mcp_service.client.session:
                    logger.error("MCP client session is not available for direct tool call.")
                    return JsonResponse({"error": "Failed to execute confirmed action: session lost."}, status=500)

                tool_result = await mcp_service.client.session.call_tool(tool_name, parameters)
                
                response_payload_str = None
                if hasattr(tool_result, "content") and tool_result.content and \
                   hasattr(tool_result.content[0], "text"):
                    response_payload_str = tool_result.content[0].text
                
                if not response_payload_str:
                    logger.error(f"No text content in tool_result for {tool_name}: {tool_result}")
                    return JsonResponse({"error": "Received empty response from confirmed action."}, status=500)

                response_payload = json.loads(response_payload_str)

                if response_payload.get("status") == "success":
                    return JsonResponse({
                        "response": [response_payload.get("message", "Action completed successfully.")],
                        "action_confirmed_executed": True,
                        "updated_data": response_payload.get("updated_data") # Pass this to frontend
                    })
                else: # Error from the MCP tool after confirmation
                    return JsonResponse({
                        "error": response_payload.get("message", "Confirmed action resulted in an error."),
                        "action_confirmed_executed": True,
                    }, status=400)

            except Exception as e:
                logger.error(f"Error directly calling MCP tool '{tool_name}': {type(e).__name__}: {e}", exc_info=True)
                return JsonResponse({"error": f"Error executing confirmed action: {str(e)}"}, status=500)

        elif not msg: # If not a confirmed action, a message is required
            logger.warning("Voice chat request with empty message and no confirmed action.")
            return JsonResponse({"error": "Message cannot be empty."}, status=400)

        else: # Standard query to Gemini
            logger.info(f"Processing voice chat query via Gemini: '{msg}'")
            # This call goes to Gemini, which might then call an MCP tool.
            # The `process_query` in `mcp_client.py` will interact with Gemini and tools.
            # The final response from Gemini (after any tool calls it makes) is returned.
            response_text_from_gemini_or_tool = await mcp_service.process_query(msg)

            try:
                # Attempt to parse the response. If it's a JSON from our MCP tool (e.g., confirmation_required),
                # it means Gemini decided the tool's direct JSON output was the answer.
                parsed_tool_response = json.loads(response_text_from_gemini_or_tool)

                if isinstance(parsed_tool_response, dict) and parsed_tool_response.get("status") == "confirmation_required":
                    return JsonResponse({
                        "needs_confirmation": True,
                        "action_details": parsed_tool_response.get("action_details"),
                        "response": [parsed_tool_response.get("action_details", {}).get("description", "Please confirm this action.")]
                    })
                # If a tool ran successfully without confirmation (e.g. get_tasks) and Gemini returned its JSON:
                elif isinstance(parsed_tool_response, dict) and (parsed_tool_response.get("status") == "success" or parsed_tool_response.get("status") == "error"):
                     return JsonResponse({
                        "response": [parsed_tool_response.get("message", "Action processed.")],
                        "updated_data": parsed_tool_response.get("updated_data") # For get_tasks, get_habits etc.
                    })
                else:
                    # It was valid JSON but not in our expected tool format. Treat as plain text from Gemini.
                    response_lines = str(response_text_from_gemini_or_tool).split('\n')
                    return JsonResponse({"response": response_lines})

            except json.JSONDecodeError:
                # It's a natural language response from Gemini, not a direct JSON from our tools.
                response_lines = response_text_from_gemini_or_tool.split('\n')
                return JsonResponse({"response": response_lines})
            except Exception as e:
                 logger.error(f"Error processing Gemini's response in voice_chat: {type(e).__name__}: {e}", exc_info=True)
                 return JsonResponse({"error": f"Internal error processing response: {str(e)}"}, status=500)

    except json.JSONDecodeError:
        logger.error("Invalid JSON received in voice_chat request.", exc_info=True)
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        logger.error(f"Error processing voice_chat request: {type(e).__name__}: {e}", exc_info=True)
        return JsonResponse({"error": f"An internal error occurred: {str(e)}"}, status=500)

async def voice_chat_orig(request):
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


@csrf_exempt # mirrordb_server is an external service
@require_http_methods(["POST"])
async def handle_request_confirmation(request: HttpRequest):
    """
    Called by mirrordb_server.py to INITIATE a confirmation.
    Stores the request for the UI to pick up.
    """
    try:
        payload = json.loads(request.body)
        action_id = payload.get("action_id")
        description = payload.get("description")
        details = payload.get("details", {})

        if not all([action_id, description]):
            return JsonResponse({"error": "Missing action_id or description"}, status=400)

        # Using async with db_lock in a sync Django view is tricky.
        # If your Django is fully async, this is fine.
        # If it's sync, db_lock should be threading.Lock and acquire/release manually.
        # For now, assuming you might run Django with ASGI and async views are possible.
        # If not, convert this view to sync and use threading.Lock.
        async with db_lock: # If this view is truly async
        # with db_lock: # If this view is sync and db_lock is threading.Lock
            if action_id in confirmations_db and confirmations_db[action_id]["status"] != "pending":
                return JsonResponse({"error": f"Action ID '{action_id}' already processed or conflict."}, status=409)
            
            confirmations_db[action_id] = {
                "action_id": action_id,
                "description": description,
                "details": details,
                "status": "pending" # type: StoredConfirmationStatusLiteral
            }
        logger.info(f"[WEB APP VIEW] Confirmation requested: {action_id} - \"{description[:50]}...\"")
        return JsonResponse({"action_id": action_id, "status": "pending", "message": "Confirmation request received for UI processing."}, status=202)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        logger.error(f"Error in handle_request_confirmation: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)

@require_http_methods(["GET"])
async def handle_get_confirmation_status(request: HttpRequest, action_id: str):
    """
    Called by mirrordb_server.py to POLL for the status.
    """
    async with db_lock: # If async view
    # with db_lock: # If sync view
        item = confirmations_db.get(action_id)

    if not item:
        return JsonResponse({
            "action_id": action_id,
            "status": "not_found", # type: ConfirmationStatusLiteral
            "description": None,
            "details": None
        }) # FastAPI version returned 200 with this, let's stick to that for client compatibility
    
    logger.info(f"[WEB APP VIEW] Status check for {action_id}: current status is {item['status']}")
    return JsonResponse({
        "action_id": item["action_id"],
        "status": item["status"], # type: ConfirmationStatusLiteral
        "description": item.get("description"),
        "details": item.get("details")
    })

# === Endpoints for your Frontend UI (e.g., voice_chat page script) ===

@require_http_methods(["GET"])
async def get_pending_ui_confirmations(request: HttpRequest):
    """
    Called by your voice_chat page's JavaScript to fetch actions needing UI confirmation.
    """
    pending_for_ui: List[Dict[str, Any]] = []
    async with db_lock: # If async view
    # with db_lock: # If sync view
        for action_id, item_data in confirmations_db.items():
            if item_data["status"] == "pending":
                pending_for_ui.append({
                    "action_id": action_id,
                    "description": item_data["description"],
                    "details": item_data.get("details", {})
                })
    logger.info(f"[WEB APP VIEW] UI polled for pending confirmations, found: {len(pending_for_ui)}")
    return JsonResponse(pending_for_ui, safe=False) # safe=False for list response

@csrf_exempt # Assuming this might be called via JS without full CSRF token setup easily
@require_http_methods(["POST"])
async def submit_ui_confirmation(request: HttpRequest, action_id: str):
    """
    Called by your voice_chat page's JavaScript when the user clicks "Confirm" or "Deny".
    """
    try:
        payload = json.loads(request.body)
        user_confirmed = payload.get("confirmed") # Expecting {"confirmed": true/false}

        if user_confirmed is None or not isinstance(user_confirmed, bool):
            return JsonResponse({"error": "Invalid payload: 'confirmed' boolean field missing or invalid."}, status=400)

        new_status: StoredConfirmationStatusLiteral = "confirmed" if user_confirmed else "denied"
        
        async with db_lock: # If async view
        # with db_lock: # If sync view
            if action_id not in confirmations_db:
                return JsonResponse({"error": f"Action ID '{action_id}' not found."}, status=404)
            
            item = confirmations_db[action_id]
            if item["status"] != "pending":
                logger.info(f"[WEB APP VIEW] UI submitted for already processed action {action_id} (current: {item['status']}). Ignoring.")
                return JsonResponse({"action_id": action_id, "status": item["status"], "message": "Action already processed, UI input ignored."})

            item["status"] = new_status
        
        logger.info(f"[WEB APP VIEW] UI submitted for {action_id}: User chose {'CONFIRMED' if user_confirmed else 'DENIED'}. Status set to {new_status}.")
        return JsonResponse({"action_id": action_id, "status": new_status, "message": "Confirmation decision recorded."})
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except Exception as e:
        logger.error(f"Error in submit_ui_confirmation for {action_id}: {e}", exc_info=True)
        return JsonResponse({"error": str(e)}, status=500)
