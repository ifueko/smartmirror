import datetime
import json
import os
import random
from dateutil.parser import parse as parse_date
from dateutil.parser import isoparse
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pytz

local_tz = pytz.timezone("America/New_York")

PRIORITY_ORDER = {"High": 1, "Medium": 2, "Low": 3}
STATUS_ORDER = {"Done": 3, "Not started": 1, "In progress": 2}


def get_google_calendar_events(creds, calendar_ids, time_min, time_max):
    service = build("calendar", "v3", credentials=creds)
    events = []
    for calendar_id in calendar_ids:
        events_result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        for event in events_result.get("items", []):
            print(event)
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            events.append(
                {
                    "id": event.get("id"),
                    "calendar_id": calendar_id,
                    "title": event.get("summary", "No Title"),
                    "start": start,
                    "end": end,
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                }
            )
    events = sorted(events, key=lambda x: x["start"])
    return events


def calendar_feed(creds, calendar_ids):
    now = datetime.datetime.now(local_tz)
    time_min = now.isoformat()
    time_max = (now + datetime.timedelta(hours=48)).isoformat()
    print("from feed", time_min, time_max)
    events = get_google_calendar_events(creds, calendar_ids, time_min, time_max)
    return events


def create_calendar_event(creds, calendar_id, summary, start_iso, end_iso):
    event = {
        "summary": f"{summary}",
        "start": {
            "dateTime": f"{start_iso}",
            "timeZone": "America/New_York",
        },
        "end": {
            "dateTime": f"{end_iso}",
            "timeZone": "America/New_York",
        },
    }
    service = build("calendar", "v3", credentials=creds)
    event = service.events().insert(calendarId=calendar_id, body=event).execute()
    return event


def fetch_habit_group(notion, emoji, db_id):
    response = notion.databases.query(
        **{
            "database_id": db_id,
            "sorts": [{"property": "Day", "direction": "descending"}],
            "page_size": 1,
        }
    )
    latest = response["results"][0]
    props = latest["properties"]
    habits = []
    for key, value in props.items():
        if emoji in key and value["type"] == "checkbox":
            habits.append(
                {
                    "title": key.strip(),
                    "done": value["checkbox"],
                    "id": latest["id"],
                    "property": key,  # used for updating
                }
            )
    return habits


def task_feed(notion, db_id):
    now = datetime.datetime.now(local_tz)
    today_str = now.isoformat()
    return get_notion_tasks(notion, db_id, today_str)


def get_notion_tasks(notion, db_id, on_or_before):
    # 1. Fetch all children tasks due today or earlier
    child_response = notion.databases.query(
        **{
            "database_id": db_id,
            "filter": {
                "or": [
                    {
                        "and": [
                            {
                                "property": "Date",
                                "date": {"on_or_before": on_or_before},
                            },
                            {
                                "property": "Status",
                                "status": {"does_not_equal": "Done"},
                            },
                        ]
                    },
                    {
                        "and": [
                            {"property": "Status", "status": {"equals": "Done"}},
                            {"property": "Date", "date": {"equals": on_or_before}},
                        ]
                    },
                ]
            },
        }
    )
    child_tasks = child_response.get("results", [])
    child_tasks = [
        task
        for task in child_tasks
        if task["properties"]["Date"]["date"]
        and task["properties"]["Date"]["date"]["start"] <= on_or_before
    ]
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
    # 1. Process flat tasks
    flat_tasks = {}
    for task in raw_tasks:
        props = task["properties"]
        name = (
            props["Name"]["title"][0]["plain_text"]
            if props["Name"]["title"]
            else "Untitled"
        )
        status = (
            props["Status"]["status"]["name"] if props["Status"]["status"] else None
        )
        priority = (
            props["Priority"]["select"]["name"] if props["Priority"]["select"] else None
        )
        parent_id = (
            props["Parent item"]["relation"][0]["id"]
            if props["Parent item"]["relation"]
            else None
        )
        date_prop = props["Date"]["date"]["start"] if props["Date"]["date"] else None
        parsed_date = parse_date(date_prop) if date_prop else None
        flat_tasks[task["id"]] = {
            "id": task["id"],
            "title": name,
            "date": parsed_date,
            "status": status,
            "priority": priority,
            "priority_value": PRIORITY_ORDER.get(priority, 99),
            "status_value": STATUS_ORDER.get(status, 99),
            "parent_id": parent_id,
            "children": [],
        }

    # 2. Build hierarchy
    root_tasks = []

    for task_id, task in flat_tasks.items():
        parent_id = task["parent_id"]
        if parent_id and parent_id in flat_tasks:
            flat_tasks[parent_id]["children"].append(task)
        else:
            root_tasks.append(task)

    # 3. Sort children at each level
    def sort_task_tree(tasks):
        def sort_key(t):
            task_date = t["date"]
            if isinstance(task_date, datetime.datetime):
                task_date = task_date.date()
            return (
                task_date or datetime.date.max,
                t["status_value"],
                t["priority_value"],
            )

        tasks.sort(key=sort_key)
        for t in tasks:
            sort_task_tree(t["children"])

    sort_task_tree(root_tasks)
    return root_tasks


def update_habit(notion, page_id, prop, done):
    return notion.pages.update(page_id=page_id, properties={prop: {"checkbox": done}})


def update_task(notion, page_id, new_status):
    # Update the Notion status field
    page = notion.pages.update(
        page_id=page_id, properties={"Status": {"status": {"name": new_status}}}
    )
    return page


def create_standalone_task(
    notion, db_id, title, due_date_iso, priority, status, parent_id=None
):
    try:
        props = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": due_date_iso}},
            "Priority": {"select": {"name": priority}},
            "Status": {"status": {"name": status}},
        }
        if parent_id is not None:
            props["Parent item"] = {"relation": [{"id": parent_id}]}
        new_task_page = notion.pages.create(
            parent={"database_id": db_id},
            properties=props,
        )
        return new_task_page
    except Exception as e:
        print(f"Error creating standalone task: {e}")
        return None


def create_child_task(notion, db_id, parent_id, title, due_date_iso, priority, status):
    return create_standalone_task(
        notion, db_id, title, due_date_iso, priority, status, parent_id
    )


def create_parent_with_child_task(
    notion,
    db_id,
    parent_title,
    child_title,
    parent_due_date_iso,
    child_due_date_iso,
    parent_priority,
    child_priority,
    parent_status,
    child_status,
):
    parent_task = create_standalone_task(
        notion, db_id, parent_title, parent_due_date_iso, parent_priority, parent_status
    )
    parent_id = parent_task["id"]
    child_task = create_standalone_task(
        notion,
        db_id,
        child_title,
        child_due_date_iso,
        child_priority,
        child_status,
        parent_id,
    )
    return parent_task, child_task


def update_notion_task(
    notion,
    task_id,
    due_date_iso=None,
    title=None,
    priority=None,
    status=None,
    trash=False,
):
    """Updates an existing Notion task page."""
    update_payload = {"properties": {}}
    if title is not None:
        update_payload["properties"]["Name"] = {"title": [{"text": {"content": title}}]}
    if due_date_iso is not None:
        update_payload["properties"]["Date"] = {"date": {"start": due_date_iso}}
    if priority is not None:
        update_payload["properties"]["Priority"] = {"select": {"name": priority}}
    if status is not None:
        update_payload["properties"]["Status"] = {"status": {"name": status}}
    if trash:
        update_payload["in_trash"] = True

    if not update_payload["properties"]:
        print("Warning: No properties provided for update.")
        return None

    try:
        response = notion.pages.update(page_id=task_id, **update_payload)
        return response
    except Exception as e:
        print(f"Error updating task {task_id}: {e}")
        return None


def create_calendar_event(
    creds, calendar_id, summary, start_iso, end_iso, timezone="America/New_York"
):
    service = build("calendar", "v3", credentials=creds)

    start_dt = isoparse(start_iso)
    end_dt = isoparse(end_iso)

    event_body = {
        "summary": summary,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": timezone,
        },
    }

    created_event = (
        service.events().insert(calendarId=calendar_id, body=event_body).execute()
    )
    print(f"Event created: {created_event.get('htmlLink')}")
    return created_event
