import asyncio
import time
import json
from mirrordb_server import (
    mcp,
    clean_habits,
    clean_tasks,
    clean_events,
    create_project_or_task_standalone,
    create_subtask_with_project_id,
    create_new_project_with_subtask,
    update_task,
    update_habit_status,
    create_event,
    delete_event,
    update_event,
    get_tasks,
    get_habits,
    get_events,
    cache,
    Priority,
    Status,
)

async def run_tests():
    print("--- Initial Data Fetch ---")
    tasks = await get_tasks()
    print("Initial Tasks Cache:"); print(json.dumps(tasks, indent=2))
    habits = await get_habits()
    print("Initial Habits Cache:", json.dumps(habits, indent=2))
    events = await get_events()
    print("Initial Events Cache:", json.dumps(events, indent=2))
    print("-" * 30)

    """
    print("--- Testing Task Creation ---")
    new_standalone_task_result = await create_project_or_task_standalone(
        title="Test Standalone Task",
        due_date_iso="2025-05-15",
        priority="Medium",
        status="Not started",
    )
    tasks = await get_tasks()
    print("Create Standalone Task Result:", json.loads(new_standalone_task_result)['new_task'])
    def get_first_task_id1():
        for task in cache['tasks']:
            print(cache['tasks'][task]['title'])
            if cache['tasks'][task]['title'] == "Updated Standalone Task Title":
                first_task_id = task
                return first_task_id
        return None
    def get_first_task_id():
        for task in cache['tasks']:
            print(cache['tasks'][task]['title'])
            if cache['tasks'][task]['title'] == "Test Standalone Task":
                first_task_id = task
                return first_task_id
        return None
    first_task_id = get_first_task_id()
    print(first_task_id, cache['tasks'][first_task_id]['id'], cache['tasks'][first_task_id]['title'])
    new_subtask_result = await create_subtask_with_project_id(
        project_id=first_task_id,
        child_title="Test Subtask",
        due_date_iso="2025-05-19",
        status="Not started",
        priority="High",
    )
    print("Create Subtask Result:", json.loads(new_subtask_result)['new_task'])
    first_task_id = get_first_task_id()
    new_project_with_subtask_result = await create_new_project_with_subtask(
            project_title="Test Project",
            child_title="Test Project Subtask",
            project_due_date_iso="2025-05-20",
            child_due_date_iso="2025-05-21",
            project_status="Not started",
            child_status="In progress",
            project_priority="High",
            child_priority="Medium",
    )
    print("Create Project with Subtask Result:", json.loads(new_project_with_subtask_result)['child_task'])
    print("-" * 30)
    print("--- Testing Task Update ---")
    first_task_id = get_first_task_id()
    update_title_result = await update_task(task_id=first_task_id, title="Updated Standalone Task Title")
    print("Update Task Title Result:", update_title_result)
    first_task_id = get_first_task_id1()
    update_priority_result = await update_task(task_id=first_task_id, priority="High")
    print("Update Task Priority Result:", update_priority_result)
    first_task_id = get_first_task_id1()
    update_status_result = await update_task(task_id=first_task_id, status="In progress")
    print("Update Task Status Result:", update_status_result)
    first_task_id = get_first_task_id1()
    update_date_result = await update_task(task_id=first_task_id, due_date_iso="2025-05-14")
    print(json.loads(update_date_result)['updated_task'])
    print("-" * 30)
    print("--- Testing Habit Update ---")
    first_habit_id = next(iter(cache.get("habits", {})), None)
    if first_habit_id:
        update_habit_result_done = await update_habit_status(id_=first_habit_id, done=True)
        print("Update Habit to Done Result:", update_habit_result_done)
        await get_habits() # Refresh cache
        update_habit_result_not_done = await update_habit_status(id_=first_habit_id, done=False)
        print("Update Habit to Not Done Result:", update_habit_result_not_done)
        await get_habits() # Refresh cache
    else:
        print("Warning: No habits found to test update_habit_status.")
    print("-" * 30)
    """

    print("--- Testing Event Creation, Update, and Deletion ---")
    new_event_result = await create_event(
        name="Test Event",
        start_iso="2025-05-16T10:00:00",
        end_iso="2025-05-16T11:00:00",
    )
    new_event_result = json.loads(new_event_result)
    print("Create Event Result:", new_event_result['new_event'])
    await get_events() # Refresh cache
    first_event_google_id = new_event_result['new_event']['id']
    print(first_event_google_id)
    for key, event in cache['events'].items():
        if event['id'] == first_event_google_id:
            print("UPDATING!!!")
            update_event_result = await update_event(
                event_id=key, name="Updated Test Event Name"
            )
            print(update_event_result)
            time.sleep(30)
    for key, event in cache['events'].items():
        if event['id'] == first_event_google_id:
            print("DELETING!!!")
            delete_event_result = await delete_event(cache_id=key)
            print("Delete Event Result:", delete_event_result)
    print("-" * 30)

if __name__ == "__main__":
    asyncio.run(run_tests())
