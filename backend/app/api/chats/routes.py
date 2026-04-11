"""
Chat CRUD endpoints.

Educational Note: These endpoints handle chat lifecycle operations.
A chat is a container for a conversation - it has metadata (title, timestamps)
and holds messages, but the actual AI processing happens in the messages blueprint.

Routes:
- GET    /projects/<id>/chats              - List all chats
- POST   /projects/<id>/chats              - Create new chat
- GET    /projects/<id>/chats/<id>         - Get chat with messages
- PUT    /projects/<id>/chats/<id>         - Update chat (rename)
- DELETE /projects/<id>/chats/<id>         - Delete chat
- GET    /projects/<id>/chats/<id>/costs   - Get per-chat cost/token breakdown
"""
from flask import jsonify, request, current_app
from app.api.chats import chats_bp
from app.services.data_services import chat_service


@chats_bp.route('/projects/<project_id>/chats', methods=['GET'])
def list_project_chats(project_id):
    """
    Get all chats for a specific project.

    Educational Note: Returns chat metadata only (not full messages)
    for efficient loading of the chat list in the UI.
    """
    try:
        chats = chat_service.list_chats(project_id)
        return jsonify({
            'success': True,
            'chats': chats,
            'count': len(chats)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error listing chats for project {project_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chats_bp.route('/projects/<project_id>/chats', methods=['POST'])
def create_chat(project_id):
    """
    Create a new chat in a project.

    Educational Note: Initializes an empty conversation.
    Messages are added via the messages blueprint's send_message endpoint.
    """
    try:
        data = request.get_json() or {}
        title = data.get('title', 'New Chat')

        chat = chat_service.create_chat(project_id, title)

        return jsonify({
            'success': True,
            'chat': chat
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error creating chat: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chats_bp.route('/projects/<project_id>/chats/<chat_id>', methods=['GET'])
def get_chat(project_id, chat_id):
    """
    Get full chat data including all messages.

    Educational Note: Loads the complete conversation history
    for display in the chat interface. Pass ?raw=true to include
    all messages with original content blocks (for debug/raw view).
    """
    try:
        include_raw = request.args.get("raw", "false").lower() == "true"
        chat = chat_service.get_chat(project_id, chat_id, include_raw=include_raw)

        if not chat:
            return jsonify({
                'success': False,
                'error': 'Chat not found'
            }), 404

        return jsonify({
            'success': True,
            'chat': chat
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting chat {chat_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chats_bp.route('/projects/<project_id>/chats/<chat_id>', methods=['PUT'])
def update_chat(project_id, chat_id):
    """
    Update chat metadata (currently only title).

    Educational Note: Allows users to rename chats for better organization.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is required'
            }), 400

        # Build updates from allowed fields
        updates = {}
        if 'title' in data:
            updates['title'] = data['title']
        if 'selected_source_ids' in data:
            updates['selected_source_ids'] = data['selected_source_ids']

        if not updates:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400

        chat = chat_service.update_chat(project_id, chat_id, updates)

        if not chat:
            return jsonify({
                'success': False,
                'error': 'Chat not found'
            }), 404

        return jsonify({
            'success': True,
            'chat': chat
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error updating chat {chat_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chats_bp.route('/projects/<project_id>/chats/<chat_id>', methods=['DELETE'])
def delete_chat(project_id, chat_id):
    """
    Delete a chat and all its messages.

    Educational Note: This is a hard delete. In production,
    consider soft delete with archive functionality.
    """
    try:
        success = chat_service.delete_chat(project_id, chat_id)

        if not success:
            return jsonify({
                'success': False,
                'error': 'Chat not found'
            }), 404

        return jsonify({
            'success': True,
            'message': 'Chat deleted successfully'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error deleting chat {chat_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@chats_bp.route('/projects/<project_id>/chats/<chat_id>/costs', methods=['GET'])
def get_chat_costs(project_id, chat_id):
    """
    Get per-chat cost and token usage breakdown.

    Educational Note: Mirrors /projects/<id>/costs but scoped to a single
    chat. Returns the same shape: total_cost and by_model breakdown with
    input_tokens, output_tokens, and cost for each of opus/sonnet/haiku.
    """
    try:
        costs = chat_service.get_chat_costs(project_id, chat_id)
        return jsonify({
            'success': True,
            'costs': costs
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting chat costs {chat_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
