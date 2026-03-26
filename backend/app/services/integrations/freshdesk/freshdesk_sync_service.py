"""
Freshdesk Sync Service - Syncs Freshdesk tickets into local Supabase table.

Educational Note: This service bridges the Freshdesk API and local storage.
It fetches tickets from the Freshdesk API, transforms them with resolved
names and computed metrics, and upserts them into the `freshdesk_tickets`
Supabase table for fast local querying by the analysis agent.

Two sync modes:
- backfill: Fetches tickets updated in the last N days (initial import)
- incremental: Fetches tickets updated since the last sync timestamp
"""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.integrations.freshdesk.freshdesk_service import (
    freshdesk_service,
    STATUS_MAP,
    PRIORITY_MAP,
    SOURCE_MAP,
)
from app.services.integrations.supabase import get_supabase

logger = logging.getLogger(__name__)


class FreshdeskSyncService:
    """
    Service for syncing Freshdesk ticket data into local Supabase tables.

    Educational Note: By storing ticket data locally, the analysis agent
    can run fast SQL queries without hitting the Freshdesk API for every
    question. The sync can be re-run to keep data fresh.
    """

    def sync_tickets(
        self,
        project_id: str,
        source_id: str,
        mode: str = "backfill",
        days_back: int = 30,
    ) -> Dict[str, int]:
        """
        Sync tickets from Freshdesk into the local freshdesk_tickets table.

        Supports cancellation via task_service.is_target_cancelled() and
        reports progress by updating the source's processing_info.
        """
        from app.services.background_services import task_service

        self._current_project_id = project_id

        if not freshdesk_service.is_configured():
            return {
                "tickets_fetched": 0, "tickets_created": 0,
                "tickets_updated": 0, "errors": 1,
                "error_message": "Freshdesk not configured",
            }

        stats = {
            "tickets_fetched": 0, "tickets_created": 0,
            "tickets_updated": 0, "errors": 0,
        }

        def _is_cancelled() -> bool:
            return task_service.is_target_cancelled(source_id)

        def _on_progress(total_fetched: int, rate_info: dict = None) -> None:
            """Update source processing_info with live ticket count + ETA."""
            try:
                from app.services.source_services import source_service
                info = {
                    "syncing": True,
                    "tickets_fetched": total_fetched,
                    "mode": mode,
                }
                if rate_info:
                    rate_total = rate_info.get("rate_total", 50)
                    info["rate_limit"] = rate_total
                    # ETA: rough estimate based on rate limit (pages/min)
                    # Each page = 100 tickets, rate_total = pages we can do per minute
                    if total_fetched > 0:
                        info["pages_fetched"] = total_fetched // 100
                source_service.update_source(project_id, source_id, processing_info=info)
            except Exception:
                pass  # Non-critical

        try:
            freshdesk_service.populate_caches()

            # Use batched fetch for backfill (handles 50k+ tickets via date-range windows)
            # Use single fetch for incremental (typically small number of recent tickets)
            if mode == "backfill":
                raw_tickets = freshdesk_service.fetch_all_tickets_batched(
                    days_back=days_back,
                    batch_days=5,
                    cancel_check=_is_cancelled,
                    on_progress=_on_progress,
                )
            else:
                updated_since = self._get_updated_since(source_id, mode, days_back)
                raw_tickets = freshdesk_service.fetch_all_tickets(
                    updated_since=updated_since,
                    cancel_check=_is_cancelled,
                    on_progress=_on_progress,
                )

            stats["tickets_fetched"] = len(raw_tickets)

            if _is_cancelled():
                stats["cancelled"] = True
                return stats

            if not raw_tickets:
                logger.info(
                    "Freshdesk sync: no tickets found (source_id=%s, mode=%s)",
                    source_id, mode,
                )
                return stats

            # Transform and batch-upsert tickets (100 at a time for performance)
            batch: List[Dict] = []
            for raw_ticket in raw_tickets:
                try:
                    transformed = self._transform_ticket(raw_ticket, source_id)
                    batch.append(transformed)
                except Exception as e:
                    stats["errors"] += 1
                    logger.error("Transform error for ticket %s: %s", raw_ticket.get("id"), e)

                if len(batch) >= 100:
                    self._upsert_batch(batch)
                    stats["tickets_created"] += len(batch)
                    batch = []

            # Final batch
            if batch:
                self._upsert_batch(batch)
                stats["tickets_created"] += len(batch)
                    logger.error(
                        "Failed to sync ticket %s: %s",
                        raw_ticket.get("id"),
                        e,
                    )

            logger.info(
                "Freshdesk sync complete (source_id=%s): fetched=%d, created=%d, updated=%d, errors=%d",
                source_id,
                stats["tickets_fetched"],
                stats["tickets_created"],
                stats["tickets_updated"],
                stats["errors"],
            )

        except Exception as e:
            logger.exception("Freshdesk sync failed (source_id=%s): %s", source_id, e)
            stats["errors"] += 1

        return stats

    def get_sync_stats(self, source_id: str) -> Dict[str, Any]:
        """
        Get statistics about synced tickets for a source.

        Args:
            source_id: The source UUID

        Returns:
            Dict with ticket_count, status_breakdown, date_range
        """
        try:
            supabase = get_supabase()

            # Total ticket count
            count_result = (
                supabase.table("freshdesk_tickets")
                .select("id", count="exact")
                .eq("source_id", source_id)
                .execute()
            )
            ticket_count = count_result.count if count_result.count is not None else 0

            if ticket_count == 0:
                return {
                    "ticket_count": 0,
                    "status_breakdown": {},
                    "date_range": {"earliest": None, "latest": None},
                }

            # Status breakdown
            tickets_result = (
                supabase.table("freshdesk_tickets")
                .select("status")
                .eq("source_id", source_id)
                .execute()
            )
            status_counts: Dict[str, int] = {}
            for row in tickets_result.data or []:
                status = row.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            # Date range
            earliest_result = (
                supabase.table("freshdesk_tickets")
                .select("created_at")
                .eq("source_id", source_id)
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            latest_result = (
                supabase.table("freshdesk_tickets")
                .select("created_at")
                .eq("source_id", source_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            earliest = (
                earliest_result.data[0].get("created_at")
                if earliest_result.data
                else None
            )
            latest = (
                latest_result.data[0].get("created_at")
                if latest_result.data
                else None
            )

            return {
                "ticket_count": ticket_count,
                "status_breakdown": status_counts,
                "date_range": {"earliest": earliest, "latest": latest},
            }

        except Exception as e:
            logger.error("Failed to get sync stats for source %s: %s", source_id, e)
            return {
                "ticket_count": 0,
                "status_breakdown": {},
                "date_range": {"earliest": None, "latest": None},
            }

    def _get_updated_since(
        self, source_id: str, mode: str, days_back: int
    ) -> Optional[str]:
        """
        Determine the updated_since filter based on sync mode.

        For backfill: returns a datetime N days ago.
        For incremental: queries the max synced_at from existing tickets.

        Args:
            source_id: The source UUID
            mode: 'backfill' or 'incremental'
            days_back: Days to look back for backfill mode

        Returns:
            ISO 8601 datetime string or None
        """
        if mode == "incremental":
            try:
                supabase = get_supabase()
                result = (
                    supabase.table("freshdesk_tickets")
                    .select("synced_at")
                    .eq("source_id", source_id)
                    .order("synced_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    last_synced = result.data[0].get("synced_at")
                    if last_synced:
                        logger.info(
                            "Freshdesk incremental sync since: %s", last_synced
                        )
                        return last_synced
            except Exception as e:
                logger.warning(
                    "Failed to get last sync time, falling back to backfill: %s", e
                )

        # Backfill mode or incremental fallback
        since = datetime.now(timezone.utc) - timedelta(days=days_back)
        return since.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _transform_ticket(
        self, raw_ticket: Dict[str, Any], source_id: str
    ) -> Dict[str, Any]:
        """
        Transform a raw Freshdesk API ticket into the local table schema.

        Educational Note: We resolve numeric IDs to human-readable names
        and compute derived metrics (resolution time, first response time)
        so the analysis agent doesn't need to do these lookups at query time.

        Args:
            raw_ticket: Raw ticket dict from Freshdesk API
            source_id: The source UUID to associate with

        Returns:
            Transformed ticket dict matching freshdesk_tickets table schema
        """
        ticket_id = raw_ticket.get("id")
        stats = raw_ticket.get("stats") or {}
        requester = raw_ticket.get("requester") or {}
        company = raw_ticket.get("company") or {}

        # Resolve names from cached lookup tables
        responder_info = freshdesk_service.resolve_agent(
            raw_ticket.get("responder_id")
        )
        group_name = freshdesk_service.resolve_group(raw_ticket.get("group_id"))
        product_name = freshdesk_service.resolve_product(
            raw_ticket.get("product_id")
        )

        # Compute resolution time in hours
        resolution_time_hours = self._compute_hours_between(
            raw_ticket.get("created_at"),
            stats.get("resolved_at"),
        )

        # Compute first response time in hours
        first_response_time_hours = self._compute_hours_between(
            raw_ticket.get("created_at"),
            stats.get("first_responded_at"),
        )

        return {
            "ticket_id": ticket_id,
            "source_id": source_id,
            "project_id": self._current_project_id,
            "subject": raw_ticket.get("subject", ""),
            "description_text": raw_ticket.get("description_text", raw_ticket.get("description", "")),
            "status": STATUS_MAP.get(raw_ticket.get("status", 0), "Unknown"),
            "priority": PRIORITY_MAP.get(raw_ticket.get("priority", 0), "Unknown"),
            "source_channel": SOURCE_MAP.get(raw_ticket.get("source", 0), "Unknown"),
            "ticket_type": raw_ticket.get("type") or None,
            "tags": raw_ticket.get("tags") or [],
            "requester_name": requester.get("name", "Unknown"),
            "requester_email": requester.get("email", ""),
            "requester_id": raw_ticket.get("requester_id"),
            "company_name": company.get("name", "") if isinstance(company, dict) else "",
            "company_id": raw_ticket.get("company_id"),
            "agent_name": responder_info.get("name", "Unassigned"),
            "agent_email": responder_info.get("email", ""),
            "responder_id": raw_ticket.get("responder_id"),
            "group_name": group_name,
            "group_id": raw_ticket.get("group_id"),
            "product_name": product_name,
            "product_id": raw_ticket.get("product_id"),
            "ticket_created_at": raw_ticket.get("created_at"),
            "ticket_updated_at": raw_ticket.get("updated_at"),
            "due_by": raw_ticket.get("due_by"),
            "resolved_at": stats.get("resolved_at"),
            "closed_at": stats.get("closed_at"),
            "first_responded_at": stats.get("first_responded_at"),
            "resolution_time_hours": resolution_time_hours,
            "first_response_time_hours": first_response_time_hours,
            "is_escalated": raw_ticket.get("is_escalated", False),
            "custom_fields": raw_ticket.get("custom_fields", {}),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def _upsert_ticket(self, ticket_data: Dict[str, Any]) -> bool:
        """
        Upsert a ticket into the freshdesk_tickets table.

        Educational Note: Uses Supabase's upsert (INSERT ... ON CONFLICT UPDATE)
        on the (ticket_id, source_id) composite key. Returns True if the row
        was newly created, False if it was updated.

        Args:
            ticket_data: Transformed ticket dict

        Returns:
            True if created (new), False if updated (existing)
        """
        supabase = get_supabase()

        # Check if ticket already exists
        existing = (
            supabase.table("freshdesk_tickets")
            .select("id")
            .eq("ticket_id", ticket_data["ticket_id"])
            .eq("source_id", ticket_data["source_id"])
            .limit(1)
            .execute()
        )

        is_new = not existing.data

        # Upsert the ticket
        supabase.table("freshdesk_tickets").upsert(
            ticket_data,
            on_conflict="ticket_id,source_id",
        ).execute()

        return is_new

    def _upsert_batch(self, tickets: List[Dict[str, Any]]) -> None:
        """Batch upsert tickets for performance (100 at a time instead of 1-by-1)."""
        if not tickets:
            return
        try:
            supabase = get_supabase()
            supabase.table("freshdesk_tickets").upsert(
                tickets, on_conflict="source_id,ticket_id"
            ).execute()
        except Exception as e:
            logger.error("Batch upsert failed (%d tickets): %s", len(tickets), e)

    @staticmethod
    def _compute_hours_between(
        start_iso: Optional[str], end_iso: Optional[str]
    ) -> Optional[float]:
        """
        Compute hours between two ISO datetime strings.

        Args:
            start_iso: Start datetime in ISO format
            end_iso: End datetime in ISO format

        Returns:
            Hours as float, or None if either timestamp is missing
        """
        if not start_iso or not end_iso:
            return None

        try:
            # Parse ISO strings (handle both Z and +00:00 timezone formats)
            start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
            delta = end - start
            return round(delta.total_seconds() / 3600, 2)
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Auto-sync: background thread that runs incremental sync periodically
    # ------------------------------------------------------------------

    _auto_sync_threads: Dict[str, threading.Thread] = {}
    _auto_sync_stop_flags: Dict[str, threading.Event] = {}
    AUTO_SYNC_INTERVAL_SECONDS = 15 * 60  # 15 minutes

    def start_auto_sync(self, project_id: str, source_id: str) -> None:
        """Start a background thread that syncs tickets every 15 minutes."""
        key = f"{project_id}:{source_id}"
        if key in self._auto_sync_threads and self._auto_sync_threads[key].is_alive():
            logger.info("Auto-sync already running for %s", key)
            return

        stop_flag = threading.Event()
        self._auto_sync_stop_flags[key] = stop_flag

        def _sync_loop():
            logger.info("Auto-sync started for %s (every %ds)", key, self.AUTO_SYNC_INTERVAL_SECONDS)
            while not stop_flag.is_set():
                stop_flag.wait(self.AUTO_SYNC_INTERVAL_SECONDS)
                if stop_flag.is_set():
                    break
                try:
                    logger.info("Auto-sync running incremental sync for %s", key)
                    stats = self.sync_tickets(project_id, source_id, mode="incremental")
                    logger.info("Auto-sync complete for %s: %s", key, stats)
                except Exception as e:
                    logger.error("Auto-sync error for %s: %s", key, e)
            logger.info("Auto-sync stopped for %s", key)

        t = threading.Thread(target=_sync_loop, daemon=True, name=f"freshdesk-sync-{source_id[:8]}")
        t.start()
        self._auto_sync_threads[key] = t

    def stop_auto_sync(self, project_id: str, source_id: str) -> None:
        """Stop the auto-sync thread for a source."""
        key = f"{project_id}:{source_id}"
        flag = self._auto_sync_stop_flags.pop(key, None)
        if flag:
            flag.set()
        self._auto_sync_threads.pop(key, None)


# Singleton instance
freshdesk_sync_service = FreshdeskSyncService()
