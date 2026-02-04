"""
Flask application factory for NoobBook.

Educational Note: The application factory pattern allows us to create
multiple app instances with different configurations (dev, test, prod).
This is a Flask best practice for larger applications.
"""
from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO

from config import config

# Initialize extensions globally but without app context
socketio = SocketIO(cors_allowed_origins="*")


def create_app(config_name='development'):
    """
    Create and configure the Flask application.

    Educational Note: This factory function:
    1. Creates the Flask instance
    2. Loads configuration
    3. Initializes extensions
    4. Registers blueprints (route modules)
    """
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Ensure base directories exist before any routes access them
    from app.utils.path_utils import ensure_base_directories
    ensure_base_directories()

    # Initialize extensions with app context
    CORS(app, origins=app.config['CORS_ALLOWED_ORIGINS'])
    socketio.init_app(app, async_mode='threading')

    # Register blueprints (modular route handlers)
    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix=app.config['API_PREFIX'])

    # Bootstrap admin (optional) when env vars are provided
    from app.services.integrations.supabase import auth_service, is_supabase_enabled
    if is_supabase_enabled():
        auth_service.bootstrap_admin_from_env()

    # Optional auth enforcement (RBAC)
    from app.services.auth.rbac import get_request_identity, is_auth_required

    @app.before_request
    def enforce_auth():
        if not is_auth_required():
            return None

        path = request.path
        api_prefix = app.config.get('API_PREFIX', '/api/v1')

        if not path.startswith(api_prefix):
            return None

        # Allow auth endpoints without authentication
        if path.startswith(f"{api_prefix}/auth"):
            return None

        identity = get_request_identity()
        if not identity.is_authenticated:
            return {"success": False, "error": "Authentication required"}, 401

        # Enforce per-project access for project-scoped routes
        project_prefix = f"{api_prefix}/projects/"
        if path.startswith(project_prefix):
            remainder = path[len(project_prefix):]
            project_id = remainder.split("/", 1)[0] if remainder else ""
            if project_id:
                from app.services.data_services import project_service
                if not project_service.has_project_access(project_id, identity.user_id):
                    return {"success": False, "error": "Project not found"}, 404

        return None

    # Register error handlers
    register_error_handlers(app)

    # Log successful initialization
    app.logger.info(f"✅ {app.config['APP_NAME']} backend initialized successfully")

    return app


def register_error_handlers(app):
    """
    Register global error handlers for the application.

    Educational Note: Centralized error handling ensures consistent
    error responses across all endpoints.
    """
    @app.errorhandler(404)
    def not_found(error):
        return {"error": "Resource not found"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Internal error: {error}")
        return {"error": "Internal server error"}, 500

    @app.errorhandler(400)
    def bad_request(error):
        return {"error": "Bad request"}, 400
