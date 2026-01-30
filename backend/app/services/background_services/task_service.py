"""
Task Service - Background task management using ThreadPoolExecutor.

Educational Note: This service manages background tasks without external
dependencies like Celery or Redis. It uses Python's built-in ThreadPoolExecutor
for concurrent execution and Supabase for task tracking.

Why ThreadPoolExecutor works for our use case:
- Our tasks are I/O-bound (API calls, file operations)
- I/O operations release the GIL (Global Interpreter Lock)
- While one thread waits for Claude API, other threads can run
- User can chat while PDFs are being processed in background

How it works:
1. Task is submitted with a callable and arguments
2. ThreadPoolExecutor runs it in a background thread
3. Task status is tracked in Supabase background_tasks table
4. Source status is updated directly by the task

Storage: Supabase background_tasks table
"""
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional, List


def _get_supabase():
    """Get Supabase client (lazy import to avoid circular imports)."""
    from app.services.integrations.supabase.supabase_client import get_supabase
    return get_supabase()


class TaskService:
    """
    Service class for managing background tasks.

    Educational Note: This is a simple task queue implementation using
    Python's built-in ThreadPoolExecutor with Supabase for persistence.
    """

    # Maximum concurrent background tasks
    MAX_WORKERS = 4
    TABLE = "background_tasks"

    def __init__(self):
        """Initialize the task service."""
        # Thread pool for executing tasks
        # Educational Note: ThreadPoolExecutor manages a pool of worker threads
        # Tasks are queued and executed as threads become available
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)

        # Lock for thread-safe operations
        self._lock = threading.Lock()

        # Track running futures (for potential cancellation)
        self._futures: Dict[str, Future] = {}

        # Track cancelled tasks - workers check this to stop early
        self._cancelled_tasks: set = set()

        # Clean up any stale tasks from previous runs
        self._cleanup_stale_tasks()

    def _cleanup_stale_tasks(self) -> None:
        """
        Clean up tasks that were running when server stopped.

        Educational Note: If the server restarts while tasks are running,
        those tasks will be stuck in "running" or "pending" state forever.
        We mark them as failed on startup.
        """
        try:
            supabase = _get_supabase()

            # Update all pending/running tasks to failed
            response = (
                supabase.table(self.TABLE)
                .update({
                    "status": "failed",
                    "error_message": "Server restarted while task was running",
                    "completed_at": datetime.now().isoformat()
                })
                .in_("status", ["pending", "running"])
                .execute()
            )

            if response.data:
                print(f"Marked {len(response.data)} stale tasks as failed")
        except Exception as e:
            print(f"Error cleaning up stale tasks: {e}")

    def submit_task(
        self,
        task_type: str,
        target_id: str,
        callable_func: Callable,
        *args,
        target_type: str = "source",
        **kwargs
    ) -> str:
        """
        Submit a task for background execution.

        Educational Note: This method returns immediately after queuing the task.
        The actual execution happens in a background thread.

        Args:
            task_type: Type of task (e.g., "source_processing")
            target_id: ID of the target resource (e.g., source_id)
            callable_func: The function to execute
            target_type: Type of target (source, studio_signal, chat)
            *args, **kwargs: Arguments to pass to the function

        Returns:
            task_id: Unique identifier for tracking the task
        """
        task_id = str(uuid.uuid4())

        # Create task record in Supabase
        task_record = {
            "id": task_id,
            "task_type": task_type,
            "target_id": target_id,
            "target_type": target_type,
            "status": "pending",
            "error_message": None,
            "progress": 0,
        }

        try:
            supabase = _get_supabase()
            supabase.table(self.TABLE).insert(task_record).execute()
        except Exception as e:
            print(f"Error creating task record: {e}")

        # Wrapper function that handles status updates
        def task_wrapper():
            try:
                print(f"DEBUG task_wrapper: Starting task {task_id}", flush=True)
                # Update status to running
                self._update_task(task_id, status="running", started_at=datetime.now().isoformat())

                print(f"DEBUG task_wrapper: Executing callable for task {task_id}", flush=True)
                # Execute the actual task
                result = callable_func(*args, **kwargs)
                print(f"DEBUG task_wrapper: Task {task_id} completed with result", flush=True)

                # Update status to completed
                self._update_task(
                    task_id,
                    status="completed",
                    progress=100,
                    completed_at=datetime.now().isoformat()
                )

                return result

            except Exception as e:
                # Update status to failed
                print(f"DEBUG task_wrapper: Task {task_id} EXCEPTION: {e}", flush=True)
                import traceback
                traceback.print_exc()
                self._update_task(
                    task_id,
                    status="failed",
                    error_message=str(e),
                    completed_at=datetime.now().isoformat()
                )
                print(f"Task {task_id} failed: {e}", flush=True)

            finally:
                # Remove from futures tracking
                self._futures.pop(task_id, None)
                # Remove from cancelled set if present
                self._cancelled_tasks.discard(task_id)

        # Submit to executor - this returns immediately
        future = self._executor.submit(task_wrapper)
        self._futures[task_id] = future

        print(f"Task submitted: {task_id} ({task_type} for {target_id})")

        return task_id

    def _update_task(self, task_id: str, **updates) -> None:
        """Update a task's fields in Supabase."""
        try:
            supabase = _get_supabase()
            supabase.table(self.TABLE).update(updates).eq("id", task_id).execute()
        except Exception as e:
            print(f"Error updating task {task_id}: {e}")

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task's current status from Supabase."""
        try:
            supabase = _get_supabase()
            response = (
                supabase.table(self.TABLE)
                .select("*")
                .eq("id", task_id)
                .execute()
            )
            if response.data:
                task = response.data[0]
                # Map Supabase column names to expected format
                task["type"] = task.get("task_type", "")
                return task
            return None
        except Exception as e:
            print(f"Error getting task {task_id}: {e}")
            return None

    def get_tasks_for_target(self, target_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific target from Supabase."""
        try:
            supabase = _get_supabase()
            response = (
                supabase.table(self.TABLE)
                .select("*")
                .eq("target_id", target_id)
                .execute()
            )
            tasks = response.data or []
            # Map column names for compatibility
            for task in tasks:
                task["type"] = task.get("task_type", "")
            return tasks
        except Exception as e:
            print(f"Error getting tasks for target {target_id}: {e}")
            return []

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.

        Educational Note: Cancellation is cooperative - we set a flag that
        the running task should check periodically. For ThreadPoolExecutor,
        we can also try to cancel the future if it hasn't started yet.

        Args:
            task_id: The task ID to cancel

        Returns:
            True if cancellation was initiated, False if task not found
        """
        task = self.get_task(task_id)
        if not task:
            return False

        # Only cancel pending or running tasks
        if task["status"] not in ["pending", "running"]:
            return False

        # Add to cancelled set - workers should check this
        self._cancelled_tasks.add(task_id)

        # Try to cancel the future if it hasn't started yet
        future = self._futures.get(task_id)
        if future:
            cancelled = future.cancel()
            if cancelled:
                print(f"Task {task_id} cancelled before it started")

        # Update task status in Supabase
        self._update_task(
            task_id,
            status="cancelled",
            error_message="Cancelled by user",
            completed_at=datetime.now().isoformat()
        )

        print(f"Task {task_id} cancellation requested")
        return True

    def is_cancelled(self, task_id: str) -> bool:
        """
        Check if a task has been cancelled.

        Educational Note: Long-running tasks should call this periodically
        and stop early if True. This enables cooperative cancellation.

        Args:
            task_id: The task ID to check

        Returns:
            True if task should stop, False otherwise
        """
        return task_id in self._cancelled_tasks

    def cancel_tasks_for_target(self, target_id: str) -> int:
        """
        Cancel all running/pending tasks for a target (e.g., a source).

        Args:
            target_id: The target resource ID

        Returns:
            Number of tasks cancelled
        """
        tasks = self.get_tasks_for_target(target_id)
        cancelled_count = 0

        for task in tasks:
            if task["status"] in ["pending", "running"]:
                if self.cancel_task(task["id"]):
                    cancelled_count += 1

        return cancelled_count

    def is_target_cancelled(self, target_id: str) -> bool:
        """
        Check if any task for a target has been cancelled.

        Educational Note: This is useful for long-running operations that
        need to check if they should stop early, but don't know their task_id.

        Args:
            target_id: The target resource ID (e.g., source_id)

        Returns:
            True if any task for this target was cancelled
        """
        tasks = self.get_tasks_for_target(target_id)
        for task in tasks:
            if task["id"] in self._cancelled_tasks:
                return True
            # Also check if task status is cancelled
            if task["status"] == "cancelled":
                return True
        return False

    def cleanup_old_tasks(self, older_than_hours: int = 24) -> int:
        """
        Remove completed/failed tasks older than specified hours.

        Educational Note: Call this periodically to prevent the database
        from growing indefinitely with old task records.

        Args:
            older_than_hours: Remove tasks completed more than this many hours ago

        Returns:
            Number of tasks removed
        """
        try:
            supabase = _get_supabase()
            cutoff = (datetime.now() - timedelta(hours=older_than_hours)).isoformat()

            # Delete old completed/failed/cancelled tasks
            response = (
                supabase.table(self.TABLE)
                .delete()
                .in_("status", ["completed", "failed", "cancelled"])
                .lt("completed_at", cutoff)
                .execute()
            )

            removed_count = len(response.data) if response.data else 0

            # Clean up cancelled tasks from in-memory set
            if removed_count > 0:
                # Get remaining task IDs
                remaining = supabase.table(self.TABLE).select("id").execute()
                remaining_ids = {t["id"] for t in (remaining.data or [])}
                self._cancelled_tasks = self._cancelled_tasks.intersection(remaining_ids)
                print(f"Cleaned up {removed_count} old tasks")

            return removed_count
        except Exception as e:
            print(f"Error cleaning up old tasks: {e}")
            return 0

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown the executor gracefully.

        Args:
            wait: If True, wait for running tasks to complete
        """
        print("Shutting down task service...")
        self._executor.shutdown(wait=wait)
        print("Task service shutdown complete")


# Singleton instance
task_service = TaskService()
