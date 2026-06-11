import logging
from src.tool_registry import odysseus_tool

logger = logging.getLogger(__name__)

@odysseus_tool({
    "type": "function",
    "function": {
        "name": "get_research_report",
        "description": "Fetch the generated markdown report from a completed deep research task.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "The ID of the completed research task"}
            },
            "required": ["task_id"]
        }
    }
})
def do_get_research_report(args: dict) -> str:
    """
    Implementation for get_research_report.
    This reads the completed markdown payload from the task store or DB.
    """
    task_id = args.get("task_id")
    if not task_id:
        return "Error: task_id is required."
    
    # TODO: Connect to Odysseus's core.database to read the Task/Research result.
    return f"Mock Output: Successfully retrieved research report for {task_id}. (Database hook pending)."


@odysseus_tool({
    "type": "function",
    "function": {
        "name": "list_active_tasks",
        "description": "List all background tasks currently running or queued.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
})
def do_list_active_tasks(args: dict) -> str:
    """
    Returns the list of active tasks from the scheduler.
    """
    return "Mock Output: 0 active background tasks. (Scheduler hook pending)."

