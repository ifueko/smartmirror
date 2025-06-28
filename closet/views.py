import random
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.http import JsonResponse
from datetime import date, timedelta

from notion_client import Client
from . import database_functions
from .services import get_mcp_service

notion = Client(auth=settings.NOTION_API_KEY)
closet_inventory = settings.CLOSET_INVENTORY
inventory_by_id = {listing['notion_page_id']: listing | {"name": name, "notion_page_id": ""} for name, listing in closet_inventory.items()} 
todays_outfit = {}
this_weeks_outfits = []

def update_outfits(request):
    global todays_outfit, this_weeks_outfits
    today = date.today()
    for i in range(7):
        if i == 0:
            outfit_date = today
        else: 
            outfit_date = today + timedelta(days=i)
        outfit_date_iso = outfit_date.isoformat()
        outfits = database_functions.fetch_outfits(notion, settings.OUTFITS_DB_ID, outfit_date_iso, inventory_by_id)
        outfit = [] if len(outfits) == 0 else outfits[0]
        if i == 0:
            todays_outfit = {"date": str(outfit_date), "items": outfit}
        this_weeks_outfits.append({"date": str(outfit_date), "items": outfit})
    return JsonResponse({"status": "success"})

def daily_outfit(request):
    return JsonResponse(todays_outfit)

def weekly_outfits(request):
    return JsonResponse({"outfits": this_weeks_outfits})

@ensure_csrf_cookie
def closet(request):
    return render(request, "closet/closet.html")

def closet_feed(request):
    inventory = list(closet_inventory.values())
    random.Random(random.random()).shuffle(inventory)
    season_sort = get_upcoming_seasons()
    def closet_sort_key(x):
        output = x['Season']
        if type(output) == list and len(output) > 0:
            output = random.choice(output)
        if output not in season_sort:
            output = random.choice(season_sort)
        return season_sort.index(output)
    inventory = sorted(inventory, key=closet_sort_key)
    return JsonResponse({"inventory": inventory})


def get_upcoming_seasons(today=None):
    if today is None:
        today = date.today()
    Y = today.year

    # Define start dates for each season
    seasons = {
        'Spring': date(Y, 3, 20),
        'Summer': date(Y, 6, 21),
        'Fall': date(Y, 9, 23),
        'Winter': date(Y, 12, 21)
    }
    if today > seasons['Winter']:
        seasons['Spring'] = date(Y + 1, 3, 20)
    upcoming = []
    for season, start_date in seasons.items():
        if start_date < today:
            start_date = start_date.replace(year=start_date.year + 1)
        delta_days = (start_date - today).days
        upcoming.append((season, delta_days))
    upcoming_sorted = sorted(upcoming, key=lambda x: x[1])
    return [season for season, _ in upcoming_sorted]

@csrf_exempt
@require_http_methods(["POST"])
async def voice_chat(request):
    try:
        data = json.loads(request.body)
        msg = data.get("message", "").strip()
        confirmed_action_details = data.get(
            "confirmed_action_details"
        )  # Sent by frontend on confirm

        mcp_service = await get_mcp_service()
        if not mcp_service or not mcp_service.client or not mcp_service.client.session:
            logger.error("MCP Service or session not available.")
            return JsonResponse(
                {"error": "Voice service is currently unavailable."}, status=503
            )

        if confirmed_action_details:
            # User has confirmed an action from the modal
            tool_name = confirmed_action_details.get("tool_name")
            parameters = confirmed_action_details.get("parameters", {})
            parameters["confirmed_by_user"] = True  # Crucial: signal confirmation

            if not tool_name:
                logger.error("Confirmed action details missing tool_name.")
                return JsonResponse(
                    {"error": "Invalid confirmation request."}, status=400
                )

            logger.info(
                f"Executing confirmed MCP tool: '{tool_name}' with params: {parameters}"
            )
            try:
                # Directly call the MCP tool via the session
                # Ensure mcp_service.client.session is valid
                if not mcp_service.client.session:
                    logger.error(
                        "MCP client session is not available for direct tool call."
                    )
                    return JsonResponse(
                        {"error": "Failed to execute confirmed action: session lost."},
                        status=500,
                    )

                tool_result = await mcp_service.client.session.call_tool(
                    tool_name, parameters
                )

                response_payload_str = None
                if (
                    hasattr(tool_result, "content")
                    and tool_result.content
                    and hasattr(tool_result.content[0], "text")
                ):
                    response_payload_str = tool_result.content[0].text

                if not response_payload_str:
                    logger.error(
                        f"No text content in tool_result for {tool_name}: {tool_result}"
                    )
                    return JsonResponse(
                        {"error": "Received empty response from confirmed action."},
                        status=500,
                    )

                response_payload = json.loads(response_payload_str)

                if response_payload.get("status") == "success":
                    return JsonResponse(
                        {
                            "response": [
                                response_payload.get(
                                    "message", "Action completed successfully."
                                )
                            ],
                            "action_confirmed_executed": True,
                            "updated_data": response_payload.get(
                                "updated_data"
                            ),  # Pass this to frontend
                        }
                    )
                else:  # Error from the MCP tool after confirmation
                    return JsonResponse(
                        {
                            "error": response_payload.get(
                                "message", "Confirmed action resulted in an error."
                            ),
                            "action_confirmed_executed": True,
                        },
                        status=400,
                    )

            except Exception as e:
                logger.error(
                    f"Error directly calling MCP tool '{tool_name}': {type(e).__name__}: {e}",
                    exc_info=True,
                )
                return JsonResponse(
                    {"error": f"Error executing confirmed action: {str(e)}"}, status=500
                )

        elif not msg:  # If not a confirmed action, a message is required
            logger.warning(
                "Voice chat request with empty message and no confirmed action."
            )
            return JsonResponse({"error": "Message cannot be empty."}, status=400)

        else:  # Standard query to Gemini
            logger.info(f"Processing voice chat query via Gemini: '{msg}'")
            # This call goes to Gemini, which might then call an MCP tool.
            # The `process_query` in `mcp_client.py` will interact with Gemini and tools.
            # The final response from Gemini (after any tool calls it makes) is returned.
            response_text_from_gemini_or_tool = await mcp_service.process_query(msg)

            try:
                # Attempt to parse the response. If it's a JSON from our MCP tool (e.g., confirmation_required),
                # it means Gemini decided the tool's direct JSON output was the answer.
                parsed_tool_response = json.loads(response_text_from_gemini_or_tool)

                if (
                    isinstance(parsed_tool_response, dict)
                    and parsed_tool_response.get("status") == "confirmation_required"
                ):
                    return JsonResponse(
                        {
                            "needs_confirmation": True,
                            "action_details": parsed_tool_response.get(
                                "action_details"
                            ),
                            "response": [
                                parsed_tool_response.get("action_details", {}).get(
                                    "description", "Please confirm this action."
                                )
                            ],
                        }
                    )
                # If a tool ran successfully without confirmation (e.g. get_tasks) and Gemini returned its JSON:
                elif isinstance(parsed_tool_response, dict) and (
                    parsed_tool_response.get("status") == "success"
                    or parsed_tool_response.get("status") == "error"
                ):
                    return JsonResponse(
                        {
                            "response": [
                                parsed_tool_response.get("message", "Action processed.")
                            ],
                            "updated_data": parsed_tool_response.get(
                                "updated_data"
                            ),  # For get_tasks, get_habits etc.
                        }
                    )
                else:
                    # It was valid JSON but not in our expected tool format. Treat as plain text from Gemini.
                    response_lines = str(response_text_from_gemini_or_tool).split("\n")
                    return JsonResponse({"response": response_lines})

            except json.JSONDecodeError:
                # It's a natural language response from Gemini, not a direct JSON from our tools.
                response_lines = [
                    r.strip()
                    for r in response_text_from_gemini_or_tool.strip().split("\n")
                    if len(r.strip()) > 0
                ]
                return JsonResponse({"response": response_lines})
            except Exception as e:
                logger.error(
                    f"Error processing Gemini's response in voice_chat: {type(e).__name__}: {e}",
                    exc_info=True,
                )
                return JsonResponse(
                    {"error": f"Internal error processing response: {str(e)}"},
                    status=500,
                )

    except json.JSONDecodeError:
        logger.error("Invalid JSON received in voice_chat request.", exc_info=True)
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        logger.error(
            f"Error processing voice_chat request: {type(e).__name__}: {e}",
            exc_info=True,
        )
        return JsonResponse(
            {"error": f"An internal error occurred: {str(e)}"}, status=500
        )
