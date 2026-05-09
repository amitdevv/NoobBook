"""
Tests for cooperative studio-job cancellation.

Covers the three layers from the design:
  Layer 1: raise_if_cancelled trips on either signal source (in-memory
           task_service set OR studio_jobs.status = "cancelled").
  Layer 2a: with_failure_guard handles StudioJobCancelled distinctly from
            generic exceptions — it does NOT call update_job (which would
            be no-op'd by the clobber matrix anyway), DOES run storage
            cleanup, and swallows the exception so the worker thread
            finishes cleanly.
  Layer 2b: update_job's status-transition matrix refuses cross-terminal
            writes — `cancelled <-> ready`, `cancelled <-> error`,
            and any from-terminal write. Same-status writes are allowed
            (idempotent).

The previous PR #211 test suite is restored verbatim where its semantics
still match this implementation, with the with_failure_guard tests
updated for the new "swallow + cleanup" cancel branch and a parametrized
matrix test added for completeness.
"""
from unittest.mock import patch, MagicMock

import pytest

from app.services.background_services import task_service
from app.services.studio_services import studio_index_service
from app.services.studio_services.studio_index_service import StudioJobCancelled


# task_service.is_target_cancelled is a METHOD on the singleton instance,
# not a module-level function — so the string-path `patch("...task_service.
# is_target_cancelled")` fails to resolve. patch.object on the singleton is
# the correct mock for these tests.


# ==========================================================================
# Layer 1 — raise_if_cancelled
# ==========================================================================


class TestRaiseIfCancelled:

    def test_no_cancel_is_noop(self):
        """Neither signal active → raise_if_cancelled returns silently."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "processing"},
        ):
            studio_index_service.raise_if_cancelled("p1", "j1")  # no exception

    def test_in_memory_set_trips(self):
        """task_service._cancelled_tasks set hit → raises immediately."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=True,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "processing"},
        ):
            with pytest.raises(StudioJobCancelled):
                studio_index_service.raise_if_cancelled("p1", "j1")

    def test_db_status_cancelled_trips(self):
        """In-memory set miss but DB row says cancelled → still raises.
        Covers the cross-process case (cancel issued from a different
        pod / after a worker restart)."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "cancelled"},
        ):
            with pytest.raises(StudioJobCancelled):
                studio_index_service.raise_if_cancelled("p1", "j1")

    def test_missing_job_is_noop(self):
        """get_job returns None (job deleted concurrently) → don't raise.
        The route would have returned 404 to the user; the worker should
        finish or fail naturally rather than throwing on a phantom cancel."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=None,
        ):
            studio_index_service.raise_if_cancelled("p1", "j1")  # no exception


# ==========================================================================
# Layer 2a — with_failure_guard cancel branch
# ==========================================================================


class TestWithFailureGuardCancelBranch:

    def test_studio_job_cancelled_swallowed_and_cleaned(self):
        """When the wrapped function raises StudioJobCancelled, the guard:
          - does NOT call update_job (the cancel route already wrote
            status='cancelled' and the clobber matrix would drop our
            write anyway);
          - DOES call purge_job_storage to remove orphan partial files;
          - SWALLOWS the exception (returns None) so the worker thread
            ends cleanly without a stack trace in logs.
        """
        def cancelled_worker(*, project_id, job_id, **_):
            raise StudioJobCancelled("user clicked stop")

        wrapped = studio_index_service.with_failure_guard(cancelled_worker)
        with patch(
            "app.services.studio_services.studio_index_service.update_job"
        ) as mock_update, patch(
            "app.services.studio_services.studio_index_service.purge_job_storage"
        ) as mock_purge:
            result = wrapped(project_id="p1", job_id="j1")

        assert result is None
        mock_update.assert_not_called()
        mock_purge.assert_called_once_with("p1", "j1")

    def test_other_exceptions_still_flip_to_error_and_reraise(self):
        """Non-cancellation exceptions still get the existing 'error'
        treatment (and re-raise so task_service marks background_tasks
        failed for observability)."""
        def crashing_worker(*, project_id, job_id, **_):
            raise RuntimeError("boom")

        wrapped = studio_index_service.with_failure_guard(crashing_worker)
        with patch(
            "app.services.studio_services.studio_index_service.update_job"
        ) as mock_update, patch(
            "app.services.studio_services.studio_index_service.purge_job_storage"
        ) as mock_purge:
            with pytest.raises(RuntimeError):
                wrapped(project_id="p1", job_id="j1")

        mock_update.assert_called_once()
        kwargs = mock_update.call_args.kwargs
        assert kwargs.get("status") == "error"
        # purge runs only on the cancel path, NOT on generic crashes —
        # the studio_jobs row stays in `error` and partial files stay
        # available for a manual retry.
        mock_purge.assert_not_called()


# ==========================================================================
# Layer 2b — update_job clobber-protection matrix
# ==========================================================================


_FORBIDDEN_TRANSITIONS = [
    # from_status, to_status
    ("ready", "pending"),
    ("ready", "processing"),
    ("ready", "error"),
    ("ready", "cancelled"),
    ("error", "pending"),
    ("error", "processing"),
    ("error", "ready"),
    ("error", "cancelled"),
    ("cancelled", "pending"),
    ("cancelled", "processing"),
    ("cancelled", "ready"),
    ("cancelled", "error"),
]


_ALLOWED_TRANSITIONS = [
    ("pending", "pending"),
    ("pending", "processing"),
    ("pending", "ready"),
    ("pending", "error"),
    ("pending", "cancelled"),
    ("processing", "pending"),  # allowed by matrix; in practice unused
    ("processing", "processing"),
    ("processing", "ready"),
    ("processing", "error"),
    ("processing", "cancelled"),
    ("ready", "ready"),
    ("error", "error"),
    ("cancelled", "cancelled"),
]


class TestUpdateJobClobberMatrix:

    @pytest.mark.parametrize("from_status,to_status", _FORBIDDEN_TRANSITIONS)
    def test_forbidden_transition_drops_write(self, from_status, to_status):
        """Each forbidden transition: the existing row is returned
        unchanged and Supabase is never touched."""
        existing = {
            "id": "j1",
            "project_id": "p1",
            "status": from_status,
            "tag_for_test": from_status,
        }
        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=existing,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client"
        ) as mock_client:
            result = studio_index_service.update_job(
                "p1", "j1", status=to_status,
            )
        assert result == existing
        mock_client.assert_not_called()

    @pytest.mark.parametrize("from_status,to_status", _ALLOWED_TRANSITIONS)
    def test_allowed_transition_writes(self, from_status, to_status):
        """Each allowed transition: Supabase update is called."""
        existing = {"id": "j1", "project_id": "p1", "status": from_status}
        updated = {**existing, "status": to_status}

        class _FakeResp:
            data = [updated]

        class _FakeBuilder:
            def update(self, _payload):
                return self
            def eq(self, *_, **__):
                return self
            def execute(self):
                return _FakeResp()

        class _FakeClient:
            def table(self, _name):
                return _FakeBuilder()

        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=existing,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client",
            return_value=_FakeClient(),
        ), patch(
            "app.services.studio_services.studio_index_service._map_job",
            return_value=updated,
        ):
            result = studio_index_service.update_job(
                "p1", "j1", status=to_status,
            )
        assert result == updated

    def test_pure_jobdata_update_skips_status_check(self):
        """Updates that don't change `status` skip the matrix entirely
        (e.g. progress message bumps mid-generation)."""
        existing = {
            "id": "j1", "project_id": "p1", "status": "processing",
            "progress": "Step 1",
        }

        class _FakeResp:
            data = [{**existing, "progress": "Step 2"}]

        class _FakeBuilder:
            def update(self, _payload):
                return self
            def eq(self, *_, **__):
                return self
            def execute(self):
                return _FakeResp()

        class _FakeClient:
            def table(self, _name):
                return _FakeBuilder()

        with patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value=existing,
        ), patch(
            "app.services.studio_services.studio_index_service._get_client",
            return_value=_FakeClient(),
        ), patch(
            "app.services.studio_services.studio_index_service._map_job",
            side_effect=lambda r: r,
        ):
            result = studio_index_service.update_job(
                "p1", "j1", progress="Step 2",
            )
        # The matrix was never invoked (no `status` in updates), so the
        # write went through normally.
        assert result.get("progress") == "Step 2"


# ==========================================================================
# is_job_cancelled — two-source check
# ==========================================================================


class TestIsJobCancelled:

    def test_in_memory_short_circuits_db(self):
        """When the in-memory hint says True, we don't pay for the DB
        read."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=True,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
        ) as mock_get:
            assert studio_index_service.is_job_cancelled("p1", "j1") is True
        mock_get.assert_not_called()

    def test_db_consulted_when_memory_misses(self):
        """In-memory miss → fall back to DB."""
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "cancelled"},
        ):
            assert studio_index_service.is_job_cancelled("p1", "j1") is True

    def test_neither_signal(self):
        with patch.object(
            task_service, "is_target_cancelled", return_value=False,
        ), patch(
            "app.services.studio_services.studio_index_service.get_job",
            return_value={"status": "processing"},
        ):
            assert studio_index_service.is_job_cancelled("p1", "j1") is False
