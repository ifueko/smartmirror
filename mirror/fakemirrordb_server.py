from mcp.server.fastmcp import FastMCP
import uuid
import sys
from typing import List
import functools
import asyncio
import os
import aiohttp

INTERACTION_SERVICE_URL = os.getenv(
    "INTERACTION_SERVICE_URL", "http://localhost:8000/api"
)
CONFIRMATION_POLLING_INTERVAL = int(os.getenv("CONFIRMATION_POLLING_INTERVAL", "2"))
CONFIRMATION_TIMEOUT_SECONDS = int(os.getenv("CONFIRMATION_TIMEOUT_SECONDS", "300"))


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


cache = {}


def confirm(
    description_template: str,
    cache_key: str = None,
    id_param_name: str = None,
    info_param_names: List[str] = [],
):
    global cache

    def decorator(tool_func):
        @functools.wraps(tool_func)  # Preserves metadata of the wrapped function
        async def wrapper(*args, **kwargs):
            info = [kwargs.get(i) for i in info_param_names]
            description = description_template.format(*info)
            if cache_key is not None:
                assert id_param_name is not None
                id_ = kwargs.get(id_param_name)
                name = cache[cache_key][id_]["name"]
                description = f"Update {cache_key} ({name}): " + description
            action = str(uuid.uuid4())
            confirm = True # For testing we can ignore confirmation polling
            #confirm = await poll_confirmation(description, action)
            assert confirm, f"{description}: this action was rejected."
            result = await tool_func(*args, **kwargs)
            return result

        return wrapper

    return decorator


mcp = FastMCP()

cache["habits"] = {
    "0": {
        "name": "brush teeth",
        "status": True,
    },
    "1": {
        "name": "eat dinner",
        "status": False,
    },
}

cache["events"] = {
    "0": {
        "name": "pick up dinner",
        "start_iso": "2025-05-13T16:11:02.880098-04:00",
        "end_iso": "2025-05-13T17:11:02.880098-04:00",
    },
    "1": {
        "name": "eat dinner",
        "start_iso": "2025-05-13T17:11:02.880098-04:00",
        "end_iso": "2025-05-13T18:11:02.880098-04:00",
    },
}

cache["tasks"] = {
    "0": {
        "name": "clean kitchen",
        "status": "In Progress",
    }
}


@mcp.tool()
async def get_habits():
    global cache
    print(f"Called: function get_habits.", file=sys.stderr)
    return {
        "function_called": "get_habits",
        "habits": cache["habits"],
    }


@mcp.tool()
async def get_tasks():
    global cache
    print(f"Called: function get_tasks.", file=sys.stderr)
    return {
        "function_called": "get_tasks",
        "tasks": cache["tasks"],
    }


@mcp.tool()
async def get_events():
    global cache
    print(f"Called: function get_events.", file=sys.stderr)
    return {
        "function_called": "get_events",
        "events": cache["events"],
    }


@mcp.tool()
@confirm(
    description_template="Mark as {}.",
    cache_key="habits",
    id_param_name="id_",
    info_param_names=["status"],
)
async def update_habit_status(id_: str, status: bool):
    global cache
    cache["habits"][id_]["status"] = status
    return {
        "function_called": "update_habit_status",
        "status": "Success",
        "habits": cache["habits"],
    }


@mcp.tool()
@confirm(
    description_template="Create new task: {} with due date {}",
    info_param_names=["name", "due_date"],
)
async def create_task(name: str, due_date_iso: str):
    global cache
    cache["tasks"][str(len(cache["tasks"]))] = {
        "name": name,
        "status": "Not started",
    }
    return {
        "function_called": "update_task_status",
        "status": "Success",
        "tasks": cache["tasks"],
    }


@mcp.tool()
@confirm(
    description_template="Create new event: {} from {} to {}",
    info_param_names=["name", "start_iso", "end_iso"],
)
async def create_event(name: str, start_iso: str, end_iso: str):
    global cache
    cache["events"][str(len(cache["events"]))] = {
        "name": name,
        "start_iso": start_iso,
        "end_iso": end_iso,
    }
    return {
        "function_called": "create_event",
        "status": "Success",
        "events": cache["events"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
