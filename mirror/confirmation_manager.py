import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Body, Path
from pydantic import BaseModel, Field

# --- In-Memory "Database" for Confirmations ---
# Structure:
# {
#   "action_id_1": {
#       "description": "User-friendly description...",
#       "details": { ...original tool args... },
#       "status": "pending" | "confirmed" | "denied" | "cli_processed"
#   },
#   ...
# }
confirmations_db: Dict[str, Dict[str, Any]] = {}
db_lock = asyncio.Lock() # To ensure thread-safe (or async-safe) access to the db

# --- Pydantic Models for Request/Response ---
class ConfirmationRequest(BaseModel):
    action_id: str = Field(..., description="Unique ID for the action, provided by the requester.")
    description: str = Field(..., description="User-friendly description of the action to be confirmed.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Original arguments or details of the action.")

class ConfirmationStatusResponse(BaseModel):
    action_id: str
    status: Literal["pending", "confirmed", "denied", "timeout", "error", "not_found"] # Added more statuses
    description: str | None = None
    details: Dict[str, Any] | None = None

class StoredConfirmationItem(BaseModel):
    action_id: str
    description: str
    details: Dict[str, Any]
    status: Literal["pending", "confirmed", "denied", "timeout", "error"] = "pending"


# --- FastAPI Application Setup ---

# Lifecycle manager for background tasks
background_tasks = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the CLI confirmation processor
    print("Confirmation Manager: Starting CLI confirmation processor task...")
    # Create a task that will run in the background
    cli_task = asyncio.create_task(cli_confirmation_processor())
    background_tasks.add(cli_task)
    # Ensure the task is properly cancelled on shutdown
    cli_task.add_done_callback(background_tasks.discard)
    yield
    # Shutdown: Cancel any running background tasks
    print("Confirmation Manager: Shutting down. Cancelling background tasks...")
    for task in list(background_tasks): # Iterate over a copy
        if not task.done():
            task.cancel()
    await asyncio.gather(*[task for task in background_tasks if not task.done()], return_exceptions=True)
    print("Confirmation Manager: Shutdown complete.")


app = FastAPI(
    title="Confirmation Manager Service",
    description="Manages and processes action confirmations via HTTP and CLI.",
    lifespan=lifespan
)

# --- HTTP Endpoints ---

@app.post("/request_confirmation", status_code=202) # 202 Accepted
async def request_confirmation(request_data: ConfirmationRequest = Body(...)):
    """
    Receives a request for an action to be confirmed.
    Stores it and marks its status as 'pending'.
    """
    action_id = request_data.action_id
    async with db_lock:
        if action_id in confirmations_db:
            # If re-requesting, perhaps update description/details but keep status if already processed by CLI?
            # For simplicity, let's allow overwriting if it's still pending, or reject if processed.
            if confirmations_db[action_id]["status"] != "pending":
                raise HTTPException(
                    status_code=409, # Conflict
                    detail=f"Action ID '{action_id}' already exists and has been processed. Status: {confirmations_db[action_id]['status']}"
                )
        
        confirmations_db[action_id] = StoredConfirmationItem(
            action_id=action_id,
            description=request_data.description,
            details=request_data.details,
            status="pending"
        ).model_dump() # Store as dict

    print(f"[HTTP] Received confirmation request for action ID: {action_id} - \"{request_data.description[:50]}...\"")
    return {"action_id": action_id, "status": "pending", "message": "Confirmation request received and is pending."}

@app.get("/confirmation_status/{action_id}", response_model=ConfirmationStatusResponse)
async def get_confirmation_status(action_id: str = Path(..., description="The unique ID of the action.")):
    """
    Allows polling for the status of a specific confirmation request.
    """
    async with db_lock:
        item = confirmations_db.get(action_id)

    if not item:
        # Raise HTTPException(status_code=404, detail=f"Action ID '{action_id}' not found.")
        # The MCP server might expect a specific JSON structure even for not_found
        return ConfirmationStatusResponse(action_id=action_id, status="not_found", description="Action ID not found.")

    print(f"[HTTP] Status check for action ID: {action_id} -> {item['status']}")
    return ConfirmationStatusResponse(
        action_id=item["action_id"],
        status=item["status"], # Should be one of the Literal values
        description=item.get("description"),
        details=item.get("details")
    )

# --- CLI Confirmation Processor ---

async def cli_confirmation_processor():
    """
    Periodically checks for pending confirmations and processes them via CLI input.
    Runs as an asyncio background task.
    """
    print("[CLI Processor] Started. Will check for pending confirmations every few seconds.")
    while True:
        try:
            await asyncio.sleep(3) # Check every 3 seconds

            pending_actions_to_process = []
            async with db_lock:
                # Find items that are 'pending' and haven't been picked up by this CLI loop yet
                for action_id, item_data in confirmations_db.items():
                    if item_data["status"] == "pending":
                        pending_actions_to_process.append(dict(item_data)) # Process a copy

            if not pending_actions_to_process:
                continue

            print(f"\n--- [CLI Processor] Found {len(pending_actions_to_process)} pending confirmation(s) ---")
            for item_copy in pending_actions_to_process:
                action_id = item_copy["action_id"]
                description = item_copy["description"]
                details_summary = str(item_copy.get("details", {}))[:100] # Show a snippet of details

                print(f"\nAction ID: {action_id}")
                print(f"Description: {description}")
                print(f"Details: {details_summary}...")

                # Get user input without blocking the asyncio event loop
                while True:
                    try:
                        user_input = await asyncio.to_thread(input, "Confirm this action? (y/n/skip): ")
                        user_input = user_input.strip().lower()
                        if user_input in ['y', 'yes']:
                            new_status = "confirmed"
                            break
                        elif user_input in ['n', 'no']:
                            new_status = "denied"
                            break
                        elif user_input in ['s', 'skip']:
                            new_status = None # Keep as pending, process next time
                            print(f"[CLI Processor] Skipped action ID: {action_id}. It will remain pending.")
                            break
                        else:
                            print("Invalid input. Please enter 'y', 'n', or 's' (skip).")
                    except EOFError: # Handle if input stream is closed (e.g. piping)
                        print("[CLI Processor] EOF received, cannot get user input. Skipping.")
                        new_status = None
                        break
                    except Exception as e:
                        print(f"[CLI Processor] Error during input: {e}. Skipping this item for now.")
                        new_status = None
                        break
                
                if new_status: # 'y' or 'n' was chosen
                    async with db_lock:
                        if action_id in confirmations_db and confirmations_db[action_id]["status"] == "pending": # Ensure it wasn't changed elsewhere
                            confirmations_db[action_id]["status"] = new_status
                            print(f"[CLI Processor] Action ID: {action_id} status updated to: {new_status.upper()}")
                        elif action_id not in confirmations_db:
                             print(f"[CLI Processor] Action ID: {action_id} was removed before processing.")
                        else:
                            print(f"[CLI Processor] Action ID: {action_id} status was changed from 'pending' before CLI processing completed ({confirmations_db[action_id]['status']}). No CLI update made.")
            
            if pending_actions_to_process: # If any actions were listed
                print("--- [CLI Processor] Finished processing current batch of confirmations. ---")

        except asyncio.CancelledError:
            print("[CLI Processor] Task cancelled. Exiting.")
            break
        except Exception as e:
            print(f"[CLI Processor] Error in CLI processing loop: {e}")
            print("[CLI Processor] Will attempt to continue after a short delay.")
            await asyncio.sleep(10) # Longer delay if there's a persistent error


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Confirmation Manager Service with CLI prompt...")
    # uvicorn.run("confirmation_manager:app", host="0.0.0.0", port=8000, reload=True)
    # Using reload=True is good for development but not for this combined CLI/server.
    # We will run uvicorn programmatically to integrate the asyncio task.
    
    # Configuration for Uvicorn
    config = uvicorn.Config(app="confirmation_manager:app", host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    # FastAPI's lifespan will start the cli_confirmation_processor task.
    # We run the uvicorn server.
    # Note: To properly shut down with Ctrl+C, uvicorn needs to handle signals.
    # Running it this way should allow the lifespan events to trigger.
    async def main():
        await server.serve()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Confirmation Manager: Received interrupt, shutting down...")
    finally:
        # Lifespan's shutdown should handle task cancellation.
        print("Confirmation Manager: Main process exiting.")
