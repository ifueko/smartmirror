import json
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from google.oauth2 import service_account
from googleapiclient.discovery import build
from notion_client import Client
from database_functions import (
    calendar_feed,
    create_calendar_event,
    fetch_habit_group,
    task_feed,
    update_habit,
    update_task      
)
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

mcp = FastMCP("mirror")
load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_TASK_DB = os.getenv("NOTION_TASK_DB_ID")
NOTION_HABIT_DB = os.getenv("NOTION_HABIT_DB_ID")
GOOGLE_CALENDAR_IDS = os.getenv("GOOGLE_CALENDAR_IDS").split(',')
GOOGLE_CALENDAR_CRED_PATH = os.getenv("GOOGLE_CALENDAR_CRED_PATH")
notion = Client(auth=NOTION_API_KEY)
event_calendar_ids = GOOGLE_CALENDAR_IDS[0] # make specific dotenv later
creds_path = os.path.join(BASE_DIR, GOOGLE_CALENDAR_CRED_PATH)
calendar_ids = GOOGLE_CALENDAR_IDS

@mcp.tool()
async def get_calendar_events():
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds_path = os.path.join(BASE_DIR, GOOGLE_CALENDAR_CRED_PATH)
    calendar_ids = GOOGLE_CALENDAR_IDS
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    events = calendar_feed(creds, calendar_ids)
    return json.dumps(events)

#ignore for now @mcp.tool()
async def add_calendar_event(summary, start_iso, end_iso):
    try:
        create_calendar_event(creds, event_calendar_id, summary, start_iso, end_iso)
    except:
        return f"Couldnt create calendar event with information: {summary} from {start_iso} to {end_iso}"
    return f"Created calendar event with information: {summary} from {start_iso} to {end_iso}"

@mcp.tool()
async def get_tasks():
    tasks = task_feed(notion, NOTION_TASK_DB)
    return json.dumps(tasks, default=str)

@mcp.tool()
async def get_habits():
    habits = {}
    for emoji, time in zip(["☀️", "🌙", "🌸", "✨"], ["Morning", "Evening", "Daily", "Weekly"]):
        habit_group = fetch_habit_group(notion, emoji, NOTION_HABIT_DB)
        habits[time] = habit_group
    return json.dumps(habits) 

# ignore for now @mcp.tool()
async def toggle_habit(page_id, prop, done):
    try:
        update_habit(notion, page_id, prop, done)
    except Exception as e:
        return f"Could not update habit with error {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
