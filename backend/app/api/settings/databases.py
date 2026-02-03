"""
Database connection management endpoints (account-level).

Educational Note: Database connections are integrations that can later be attached
to projects as "DATABASE" sources. We keep credentials server-side and only send
masked connection URIs to the frontend.

Routes:
- GET    /settings/databases           - List database connections (masked)
- POST   /settings/databases           - Create a database connection
- DELETE /settings/databases/<id>      - Delete a database connection
- POST   /settings/databases/validate  - Validate connection without saving
"""

from flask import jsonify, request, current_app

from app.api.settings import settings_bp
from app.services.data_services.database_connection_service import (
    database_connection_service,
    DEFAULT_USER_ID,
)


@settings_bp.route("/settings/databases", methods=["GET"])
def list_databases():
    """List database connections available to the current user (masked)."""
    try:
        # Single-user mode for now
        connections = database_connection_service.list_connections(user_id=DEFAULT_USER_ID)
        return jsonify({"success": True, "databases": connections, "count": len(connections)}), 200
    except Exception as e:
        current_app.logger.error(f"Error listing databases: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/databases", methods=["POST"])
def create_database():
    """Create a new database connection."""
    try:
        data = request.get_json() or {}

        name = (data.get("name") or "").strip()
        db_type = (data.get("db_type") or "").strip()
        connection_uri = (data.get("connection_uri") or "").strip()
        description = (data.get("description") or "").strip()

        if not name:
            return jsonify({"success": False, "error": "name is required"}), 400
        if db_type not in {"postgresql", "mysql"}:
            return jsonify({"success": False, "error": "db_type must be 'postgresql' or 'mysql'"}), 400
        if not connection_uri:
            return jsonify({"success": False, "error": "connection_uri is required"}), 400

        # Optional: Validate before saving (safer UX)
        validation = database_connection_service.validate_connection(db_type, connection_uri)
        if not validation.get("valid"):
            return jsonify({"success": False, "error": validation.get("message", "Validation failed")}), 400

        created = database_connection_service.create_connection(
            name=name,
            db_type=db_type,
            connection_uri=connection_uri,
            description=description,
            user_id=DEFAULT_USER_ID,
        )

        return jsonify({"success": True, "database": created}), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error creating database connection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/databases/<connection_id>", methods=["DELETE"])
def delete_database(connection_id: str):
    """Delete a database connection (owner only in single-user mode)."""
    try:
        ok = database_connection_service.delete_connection(connection_id, user_id=DEFAULT_USER_ID)
        if not ok:
            return jsonify({"success": False, "error": "Database connection not found"}), 404
        return jsonify({"success": True, "message": "Database connection deleted"}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting database connection {connection_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route("/settings/databases/validate", methods=["POST"])
def validate_database():
    """Validate a database connection without saving it."""
    try:
        data = request.get_json() or {}
        db_type = (data.get("db_type") or "").strip()
        connection_uri = (data.get("connection_uri") or "").strip()

        validation = database_connection_service.validate_connection(db_type, connection_uri)
        return jsonify({"success": True, **validation}), 200 if validation.get("valid") else 400
    except Exception as e:
        current_app.logger.error(f"Error validating database connection: {e}")
        return jsonify({"success": False, "valid": False, "message": str(e)}), 500

