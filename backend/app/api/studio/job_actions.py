"""
Studio job actions — currently just `cancel`.

A studio job runs in a background ThreadPoolExecutor worker (via
`task_service.submit_task`). The agent service code periodically calls
`raise_if_cancelled(project_id, job_id)` at natural boundaries (start of
work, top of generation loop, before expensive external calls) to give
the user a way to stop a long-running generation.

This route is the trigger end of that loop. It:

  1. Looks up the job; 404 if missing.
  2. Branches on the current status — three of them are terminal and
     handled inline (idempotent ``cancelled``, race-with-finished
     ``ready``, already-failed ``error``). Otherwise we proceed.
  3. Calls ``task_service.cancel_tasks_for_target(job_id)`` so the
     worker's next breakpoint trips immediately (in-memory hint, no DB
     read). The DB write below is the durable backstop.
  4. Calls ``studio_index_service.update_job(status='cancelled', ...)``.
     The clobber matrix in update_job rejects late ``ready`` writes from
     the worker if they race in after this — the DB row is the single
     source of truth for the final state.

Race semantics — what the caller sees:
  * Normal cooperative cancel (status was processing/pending) → 200,
    ``{success, status:'cancelled', job}``.
  * Worker finished AFTER user clicked Stop but BEFORE this route ran →
    we observe ``status='ready'`` and return ``{success, status:'ready',
    late:true, job}``. Frontend rolls its optimistic 'cancelling' state
    back and surfaces "Generation finished before cancel — keeping the
    result."
  * Worker errored prior → 409 ``{success:false, status:'error', job}``.
    Cancel is moot.
  * Job already cancelled → 200 idempotent ``{success, status:'cancelled',
    job}``. Double-confirm and replay-safe.
  * Project / job not found → 404.

The cancel intent is project-scoped via the existing `before_request`
hook on `studio_bp` that calls `verify_project_access`. Cross-project
cancels are not possible because `get_job` requires both ids match.
"""
from datetime import datetime, timezone

from flask import jsonify

from app.api.studio import studio_bp
from app.services.background_services.task_service import task_service
from app.services.studio_services import studio_index_service


@studio_bp.route(
    "/projects/<project_id>/studio/jobs/<job_id>/cancel",
    methods=["POST"],
)
def cancel_studio_job(project_id: str, job_id: str):
    job = studio_index_service.get_job(project_id, job_id)
    if not job:
        return jsonify({"success": False, "error": "job not found"}), 404

    current_status = job.get("status")

    if current_status == "cancelled":
        # Idempotent — second confirm or two-tab race lands here.
        return jsonify({
            "success": True,
            "status": "cancelled",
            "job": job,
        }), 200

    if current_status == "ready":
        # Worker beat us; the result is real. Tell the frontend to roll
        # its optimistic cancel state back and keep the output. The
        # `late` flag is the signal for that UI behavior.
        return jsonify({
            "success": True,
            "status": "ready",
            "late": True,
            "job": job,
        }), 200

    if current_status == "error":
        return jsonify({
            "success": False,
            "status": "error",
            "job": job,
        }), 409

    # Live job (pending or processing) — actually cancel.
    # In-memory hint first so the worker's next breakpoint trips before
    # the DB roundtrip below.
    task_service.cancel_tasks_for_target(job_id)

    # `datetime.utcnow()` is deprecated in 3.12+ — use a timezone-aware
    # value so the ISO string carries an explicit offset and matches what
    # the rest of the studio_jobs callers store.
    now_iso = datetime.now(timezone.utc).isoformat()
    updated = studio_index_service.update_job(
        project_id, job_id,
        status="cancelled",
        completed_at=now_iso,
        cancelled_at=now_iso,  # stored inside job_data JSONB
    )

    # Second race window: the worker may have written ready/error in the
    # gap between our initial `get_job` (which saw `processing` and let
    # us through) and the `update_job` above. The clobber matrix would
    # then drop our cancelled write — `updated` reflects the worker's
    # winning row, NOT a cancellation. Branch on the actual final status
    # so the frontend never sees `{status:'cancelled'}` when the DB is
    # something else.
    final = updated or job
    final_status = final.get("status")

    if final_status == "ready":
        return jsonify({
            "success": True,
            "status": "ready",
            "late": True,
            "job": final,
        }), 200

    if final_status == "error":
        return jsonify({
            "success": False,
            "status": "error",
            "job": final,
        }), 409

    # Normal cooperative cancel — DB row landed `cancelled` as expected.
    return jsonify({
        "success": True,
        "status": final_status or "cancelled",
        "job": final,
    }), 200
