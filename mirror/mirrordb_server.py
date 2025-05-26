import aiohttp
import asyncio
import datetime
import uuid
import functools
import json
import os
import pytz
import re
import sys

from dotenv import load_dotenv
from enum import Enum
from pathlib import Path
from typing import List, Literal
from urllib.parse import urlparse, parse_qs

from mcp import types
from mcp.server.fastmcp import FastMCP
from google.oauth2 import service_account
from googleapiclient.discovery import build
from notion_client import Client

from database_functions import (
    create_calendar_event,
    create_child_task,
    create_parent_with_child_task,
    create_standalone_task,
    fetch_habit_group,
    get_google_calendar_events,
    get_notion_tasks,
    update_habit,
    update_notion_task,
)

BASE_DIR = Path(__file__).resolve().parent.parent
local_tz = pytz.timezone("America/New_York")
load_dotenv()

GOOGLE_CALENDAR_CRED_PATH = os.getenv("GOOGLE_CALENDAR_CRED_PATH")
CREDS_PATH = os.path.join(BASE_DIR, GOOGLE_CALENDAR_CRED_PATH)
GOOGLE_EVENT_CALENDAR_ID = os.getenv("GOOGLE_EVENT_CALENDAR_ID")
GOOGLE_CALENDAR_IDS = os.getenv("GOOGLE_CALENDAR_IDS").split(",")
SCOPES_READ = ["https://www.googleapis.com/auth/calendar.readonly"]
SCOPES_EVENTS = ["https://www.googleapis.com/auth/calendar.events"]

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_TASK_DB = os.getenv("NOTION_TASK_DB_ID")
NOTION_HABIT_DB = os.getenv("NOTION_HABIT_DB_ID")


INTERACTION_SERVICE_URL = os.getenv(
    "INTERACTION_SERVICE_URL", "http://localhost:8000/api"
)
CONFIRMATION_POLLING_INTERVAL = int(os.getenv("CONFIRMATION_POLLING_INTERVAL", "2"))
CONFIRMATION_TIMEOUT_SECONDS = int(os.getenv("CONFIRMATION_TIMEOUT_SECONDS", "300"))


class Priority(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Status(str, Enum):
    DONE = "Done"
    NOT_STARTED = "Not started"
    IN_PROGRESS = "In progress"


cache = {
    "habits": {},
    "events": {},
    "tasks": {},
}


def parse_url(url):
    parsed_url = urlparse(url)
    base_uri = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
    kwargs = parse_qs(parsed_url.query)
    return base_uri, kwargs


def get_today():
    now = datetime.datetime.now(local_tz)
    now = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_str = now.isoformat()
    return today_str


def clean_date(dt_str, tz_str="America/New_York", default_time="T00:00:00"):
    if type(dt_str) is datetime.datetime:
        return dt_str
    local_tz = pytz.timezone(tz_str)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", dt_str):
        dt_obj = datetime.datetime.fromisoformat(dt_str + default_time)
        return local_tz.localize(dt_obj).isoformat()
    try:
        dt_obj = datetime.datetime.fromisoformat(dt_str.replace(" ", "T"))
        return (
            dt_obj.isoformat()
            if dt_obj.tzinfo
            else local_tz.localize(dt_obj).isoformat()
        )
    except ValueError:
        return None


def get_delta(date_time_str, delta=0):
    given_datetime = datetime.datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S%z")
    if delta != 0:
        delta_timedelta = datetime.timedelta(days=delta)
        result_datetime = given_datetime + delta_timedelta
    else:
        result_datetime = given_datetime

    # Ensure the result has the correct timezone and format as RFC3339
    result_datetime_tz = result_datetime.astimezone(local_tz)
    return result_datetime_tz.isoformat()


def get_now():
    now = datetime.datetime.now(local_tz)
    now_str = now.isoformat()
    return now_str


mcp = FastMCP("SmartMirror BackendDB FastMCP")


@mcp.tool(description="Gets the user's local time zone.")
async def get_time_zone() -> dict:
    return "America/New_York"


@mcp.tool(description="Gets the current date and time in the user's local time zone.")
async def get_current_datetime() -> dict:
    return get_now()


@mcp.tool(
    description="Returns any tasks that are not complete (or have subtasks that are) not complete on or before the specified date."
)
async def tasks_on_or_before(on_or_before_date: str):
    return await get_tasks(on_or_before_date)


@mcp.tool(
    name="get_active_tasks",
    description="Returns active tasks, defined as tasks that are (or have subtasks that are) not complete and due on or before the current date.",
)
async def current_tasks():
    return await get_tasks()


async def get_tasks(on_or_before_date=None):
    global cache
    if on_or_before_date is None:
        on_or_before_date = get_today()
    notion = Client(auth=NOTION_API_KEY)
    notion_tasks = get_notion_tasks(notion, NOTION_TASK_DB, on_or_before_date)
    flattened_tasks = {}
    task_counter = 1
    for task_data in notion_tasks:
        project_task_id = str(task_counter)
        task_data["task_id"] = project_task_id
        flattened_tasks[project_task_id] = task_data
        task_counter += 1
        if "children" in task_data:
            new_children = []
            for child_task in task_data["children"]:
                new_children.append(str(task_counter))
                child_task["project_task_id"] = project_task_id
                flattened_tasks[str(task_counter)] = child_task
                task_counter += 1
            flattened_tasks[project_task_id]["subtasks"] = new_children
    cache["tasks"] = flattened_tasks
    return json.dumps(clean_tasks(flattened_tasks), default=str)


def clean_events(events_dict):
    return clean_dict(events_dict, ["id", "calendar_id"])


def clean_habits(habits_dict):
    return clean_dict(habits_dict, ["id", "property"])


def clean_tasks(tasks_dict):
    return clean_dict(tasks_dict, ["id", "parent_id"])


def clean_dict(dict_, ignore_keys):
    clean_dict = {}
    for item_id, item in dict_.items():
        clean_item = {k: v for k, v in item.items() if k not in ignore_keys}
        clean_dict[item_id] = clean_item
    return clean_dict


@mcp.tool(
    name="get_daily_habits",
    description="Returns the completion status of habits for today's date.",
)
async def get_habits():
    global cache
    habits = {}
    count = 0
    notion = Client(auth=NOTION_API_KEY)
    for emoji, time in zip(
        ["☀️", "🌙", "🌸", "✨"], ["Morning", "Evening", "Daily", "Weekly"]
    ):
        habit_group = fetch_habit_group(notion, emoji, NOTION_HABIT_DB)
        for habit in habit_group:
            habit["timeofday"] = f"{emoji} {time}"
            habit["habit_id"] = str(count)
            habits[str(count)] = habit
            count += 1
    cache["habits"] = habits
    return json.dumps(clean_habits(habits))


@mcp.tool(
    description="Returns the user's calendar events occuring on the specified date."
)
async def events_on(date):
    events = await get_events(date)
    return events


@mcp.tool(
    description="Returns the user's calendar events starting and ending between the specified dates.",
)
async def events_between(start_date, end_date):
    return await get_events(start_date, end_date)


@mcp.tool(
    name="get_todays_events",
    description="Returns the user's calendar events for today's date.",
)
async def todays_events():
    return await get_events()


async def get_events(start_date=None, end_date=None):
    global cache
    if start_date is None:
        start_date = get_today()
    else:
        start_date = clean_date(start_date)
    if end_date is None:
        end_date = get_delta(start_date, delta=1)
    else:
        end_date = clean_date(end_date)
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=SCOPES_READ
    )
    calendar_ids = GOOGLE_CALENDAR_IDS
    count = 0
    events = get_google_calendar_events(creds, calendar_ids, start_date, end_date)
    for i, e in enumerate(events):
        e["event_id"] = i
        cache["events"][i] = e
    events = clean_events(cache["events"])
    return {
        "function_called": "get_events",
        "events": events,
    }


async def poll_confirmation(
    description: str, action_id: str, details: dict = None
) -> bool:
    if details is None:
        details = {}
    payload_to_service = {
        "action_id": action_id,
        "description": description,
        "details": details,
    }
    service_url = INTERACTION_SERVICE_URL
    poll_interval = CONFIRMATION_POLLING_INTERVAL
    timeout_seconds = CONFIRMATION_TIMEOUT_SECONDS
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{service_url}/request_confirmation", json=payload_to_service
        ) as resp:
            if resp.status not in [200, 201, 202]:
                return False
        elapsed_time = 0
        while elapsed_time < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed_time += poll_interval
            async with session.get(
                f"{service_url}/confirmation_status/{action_id}"
            ) as poll_resp:
                if poll_resp.status == 200:
                    data = await poll_resp.json()
                    status = data.get("status")
                    if status == "confirmed":
                        return True
                    if status == "denied":
                        return False
                    if status == "pending":
                        continue
                    return False
        return False


def confirm(
    description_template: str,
    cache_key: str = None,
    id_param_name: str = None,
    info_param_names: List[str] = [],
):
    global cache

    def decorator(tool_func):
        @functools.wraps(tool_func)
        async def wrapper(*args, **kwargs):
            info = [kwargs.get(i) for i in info_param_names]
            description = description_template.format(*info)
            if cache_key is not None:
                assert id_param_name is not None
                id_ = kwargs.get(id_param_name)
                try:
                    name = cache[cache_key][id_]["name"]
                except:
                    name = cache[cache_key][id_]["title"]
                description = f"Update {cache_key} ({name}): " + description
            action = str(uuid.uuid4())
            confirm = await poll_confirmation(description, action)
            assert confirm, f"{description}: this action was rejected."
            result = await tool_func(*args, **kwargs)
            return result

        return wrapper

    return decorator


@mcp.tool(
    description="Updates the current day's completion status of the habit with the specified dict id",
)
@confirm(
    description_template="Mark as {}.",
    cache_key="habits",
    id_param_name="habit_id",
    info_param_names=["done"],
)
async def update_habit_status(habit_id: str, done: bool):
    global cache
    habit = cache["habits"][habit_id]
    page_id = habit["id"]
    prop = habit["property"]
    notion = Client(auth=NOTION_API_KEY)
    update_habit(notion, page_id, prop, done)
    habits = await get_habits()
    return {
        "function_called": "update_habit_status",
        "status": "Success",
        "habits": habits,
    }


@mcp.tool(
    name="create_project_or_task_standalone",
    description="Creates a new entry in the task database. Can be a project task, or standalone task with no subtasks. Project tasks are identical to standalone tasks, but often have subtasks.",
)
@confirm(
    description_template="Create new project or task: {} due {} priority {}",
    info_param_names=["title", "due_date_iso", "priority"],
)
async def create_project_or_task_standalone(
    title: str,
    due_date_iso: str,
    priority: Literal["High", "Medium", "Low"],
    status: Literal["Done", "Not started", "In progress"],
) -> str:
    """MCP function for creating a new standalone task."""
    notion = Client(auth=NOTION_API_KEY)
    task = create_standalone_task(
        notion, NOTION_TASK_DB, title, due_date_iso, priority, status
    )
    if task:
        tasks = await get_tasks()
        return json.dumps(
            {
                "status": "Success",
                "tasks": tasks,
                "new_task": clean_tasks({1: task})[1],
            },
            default=str,
        )
    else:
        return json.dumps(
            {"status": "Failed", "error": "Could not create standalone task"},
            default=str,
        )


@mcp.tool(
    name="create_subtask_with_project_id",
    description="Creates a new subtask under an existing project task.",
)
@confirm(
    description_template="Create new child task: {} under project with id: {} with due date {}, status {}, priority {}",
    info_param_names=[
        "child_title",
        "project_id",
        "due_date_iso",
        "status",
        "priority",
    ],
)
async def create_subtask_with_project_id(
    project_id: str,
    child_title: str,
    due_date_iso: str,
    status: str = None,
    priority: str = None,
) -> str:
    """MCP function for creating a new child task under an existing project."""
    notion = Client(auth=NOTION_API_KEY)
    notion_project_id = cache["tasks"][project_id]["id"]
    child = create_child_task(
        notion,
        NOTION_TASK_DB,
        notion_project_id,
        child_title,
        due_date_iso,
        priority,
        status,
    )
    if child:
        tasks = await get_tasks()  # Refresh cache to reflect the new child
        return json.dumps(
            {
                "status": "Success",
                "tasks": tasks,
                "new_task": clean_tasks({1: child})[1],
            },
            default=str,
        )
    else:
        return json.dumps(
            {
                "status": "Failed",
                "error": f"Could not create child task under project {project_id}",
            },
            default=str,
        )


@mcp.tool(
    description="Create new project with child task and additional details (due dates, priorities, completion statuses)",
)
@confirm(
    description_template="Create new project: {} with child task: {} project due date {} child due date {} project priority {} child priority {}",
    info_param_names=[
        "project_title",
        "child_title",
        "project_due_date_iso",
        "child_due_date_iso",
        "project_priority",
        "child_priority",
        "project_status",
        "child_status",
    ],
)
async def create_new_project_with_subtask(
    project_title: str,
    child_title: str,
    project_due_date_iso: str,
    child_due_date_iso: str,
    project_status: Literal["Done", "Not started", "In progress"],
    child_status: Literal["Done", "Not started", "In progress"],
    project_priority: Literal["High", "Medium", "Low"],
    child_priority: Literal["High", "Medium", "Low"],
) -> str:
    """MCP function for creating a new project task with a child task."""
    notion = Client(auth=NOTION_API_KEY)
    project_task, child_task = create_parent_with_child_task(
        notion,
        NOTION_TASK_DB,
        project_title,
        child_title,
        project_due_date_iso,
        child_due_date_iso,
        project_priority,
        child_priority,
        project_status,
        child_status,
    )
    if project_task and child_task:
        tasks = await get_tasks()  # Refresh cache
        new_tasks = clean_tasks({0: project_task, 1: child_task})
        result = {
            "status": "Success",
            "tasks": tasks,
            "project": new_tasks[0],
            "child_task": new_tasks[1],
        }
        return json.dumps(result, default=str)
    else:
        return json.dumps(
            {"status": "Failed", "error": f"Could not create project task with child"},
            default=str,
        )


@mcp.tool(description="Updates one or more details of the task with the sepcified id.")
@confirm(
    description_template="Update task: id {}; params: {} {} {} {}",
    info_param_names=["task_id", "title", "due_date_iso", "status", "priority"],
)
async def update_task(
    task_id: str,
    title: str = None,
    due_date_iso: str = None,
    status: str = None,
    priority: str = None,
) -> str:
    global cache
    if not any([title, status, priority, due_date_iso]):
        return json.dumps(
            {
                "status": "Failed",
                "error": "At least one property must be provided for update",
            },
            default=str,
        )
    notion = Client(auth=NOTION_API_KEY)
    notion_task_id = cache["tasks"][task_id]["id"]
    updated_task = update_notion_task(
        notion, notion_task_id, due_date_iso, title, priority, status
    )
    if updated_task:
        tasks = await get_tasks()
        updated_task = clean_tasks({1: updated_task})[1]
        return json.dumps(
            {
                "status": "Success",
                "updated_task_id": task_id,
                "tasks": tasks,
                "updated_task": updated_task,
            },
            default=str,
        )
    else:
        return json.dumps(
            {"status": "Failed", "error": f"Could not update task {task_id}"},
            default=str,
        )


@mcp.tool(
    name="create_calendar_event",
    description="Creates a new calendar event with description, starting and ending at the specified ISO Datetimes.",
)
@confirm(
    description_template="Create new event: {} from {} to {}. Returns the full updated calendar.",
    info_param_names=["description", "start_iso", "end_iso"],
)
async def create_event(description: str, start_iso: str, end_iso: str):
    global cache
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=SCOPES_EVENTS
    )
    calendar_id = GOOGLE_EVENT_CALENDAR_ID
    event = create_calendar_event(creds, calendar_id, description, start_iso, end_iso)
    assert event.get("htmlLink"), "Could not create event."
    events = await get_events()
    return json.dumps(
        {
            "function_called": "create_event",
            "status": "Success",
            "events": events,
            "new_event": event,
        },
        default=str,
    )


@mcp.tool(
    description="Deletes the calendar event with specified ID.",
)
@confirm(
    description_template="Delete event with cache ID: {}",
    info_param_names=["id"],
)
async def delete_event(event_id: str):
    """Deletes a Google Calendar event based on its local cache ID."""
    global cache
    event_data = cache["events"].get(event_id)
    if not event_data or not event_data.get("id"):
        return json.dumps(
            {
                "status": "Failed",
                "error": f"Event with cache ID '{event_id}' not found or has no Google ID.",
            },
            default=str,
        )
    event_google_id = event_data["id"]
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=SCOPES_EVENTS
    )
    service = build("calendar", "v3", credentials=creds)
    calendar_id = event_data["calendar_id"]
    try:
        service.events().delete(
            calendarId=calendar_id, eventId=event_google_id
        ).execute()
        events = await get_events()
        return {
            "function_called": "delete_event",
            "status": "Success",
            "deleted_event_id": event_id,
            "events": events,
        }
    except Exception as e:
        return json.dumps(
            {
                "status": "Failed",
                "error": f"Could not delete event with ID '{event_google_id}': {e}",
            },
            default=str,
        )


def update_google_calendar_event(
    creds,
    event_id,
    title=None,
    start_iso=None,
    end_iso=None,
    location=None,
    description=None,
):
    """Updates a Google Calendar event."""
    service = build("calendar", "v3", credentials=creds)
    event = cache["events"][event_id]
    print("event before")
    print(event)
    print()
    calendar_id = event["calendar_id"]
    event_id = event["id"]
    event_body = (
        service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    )
    if title:
        event_body["summary"] = title
    if start_iso:
        event_body["start"] = {
            "dateTime": start_iso,
            "timeZone": "America/New_York",
        }
    if end_iso:
        event_body["end"] = {
            "dateTime": end_iso,
            "timeZone": "America/New_York",
        }
    if location:
        event_body["location"] = location
    if description:
        event_body["description"] = description
    print(event_body)
    print()
    updated_event = (
        service.events()
        .update(calendarId=calendar_id, eventId=event_id, body=event_body)
        .execute()
    )
    print("event after")
    print(updated_event)
    print()
    return updated_event


@mcp.tool(description="Updates one or more details of the event with the sepcified id.")
@confirm(
    description_template="Update event id: {}",
    info_param_names=["event_id"],
)
async def update_event(
    event_id: str,
    name: str = None,
    start_iso: str = None,
    end_iso: str = None,
    location: str = None,
    description: str = None,
):
    if not any([name, start_iso, end_iso, location, description]):
        return json.dumps(
            {
                "status": "Failed",
                "error": "At least one property must be provided for update.",
            },
            default=str,
        )
    creds = service_account.Credentials.from_service_account_file(
        CREDS_PATH, scopes=SCOPES_EVENTS
    )
    try:
        updated_gcal_event = update_google_calendar_event(
            creds,
            event_id,
            name,
            start_iso,
            end_iso,
            location,
            description,
        )
        if updated_gcal_event:
            events = await get_events()
            return {
                "function_called": "update_event",
                "status": "Success",
                "events": events,
            }
            return events
        else:
            return json.dumps(
                {
                    "status": "Failed",
                    "error": f"Could not update event with ID '{event_id}'.",
                },
                default=str,
            )
    except Exception as e:
        return json.dumps(
            {
                "status": "Failed",
                "error": f"Error updating event with ID '{event_id}': {e}",
            },
            default=str,
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
