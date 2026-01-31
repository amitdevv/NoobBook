"""
Notion Integration Service - Notion API integration for NoobBook.

Educational Note: This service provides methods to query Notion pages and databases
using the Notion API. It follows NoobBook's service pattern with lazy-loaded
client initialization and environment-based configuration.
"""
import os
from typing import Dict, Any, Optional, List
import requests


class NotionService:
    """
    Notion API integration service.

    Educational Note: Singleton pattern with lazy client initialization.
    Configuration is read from environment variables on first use.
    """

    # Notion API base URL
    API_BASE = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    def __init__(self):
        """Initialize the Notion service with lazy-loaded configuration."""
        self._api_key = None
        self._configured = None  # Cache configuration check

    def _load_config(self) -> None:
        """Lazy-load Notion configuration from environment variables."""
        if self._configured is not None:
            return  # Already loaded

        # Read configuration
        self._api_key = os.getenv('NOTION_API_KEY', '').strip()

        # Set configured flag
        self._configured = bool(self._api_key)

        if self._configured:
            print(f"✓ Notion service configured")
        else:
            print("⚠ Notion service not configured (missing NOTION_API_KEY)")

    def is_configured(self) -> bool:
        """Check if Notion credentials are configured."""
        self._load_config()
        return self._configured

    def _make_request(
        self,
        endpoint: str,
        method: str = 'GET',
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Notion API.

        Args:
            endpoint: API endpoint (relative to base URL)
            method: HTTP method (GET or POST)
            json_data: JSON body for POST requests

        Returns:
            Dict with 'success' flag and either 'data' or 'error'
        """
        self._load_config()

        if not self.is_configured():
            return {
                "success": False,
                "error": "Notion not configured. Please add NOTION_API_KEY to .env"
            }

        try:
            url = f"{self.API_BASE}/{endpoint}"
            headers = {
                'Authorization': f'Bearer {self._api_key}',
                'Notion-Version': self.API_VERSION,
                'Content-Type': 'application/json'
            }

            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=json_data, timeout=30)
            else:
                return {"success": False, "error": f"Unsupported HTTP method: {method}"}

            # Handle response codes
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            elif response.status_code == 401:
                return {"success": False, "error": "Authentication failed. Check your NOTION_API_KEY"}
            elif response.status_code == 403:
                return {"success": False, "error": "Permission denied. Check your Notion integration permissions"}
            elif response.status_code == 404:
                return {"success": False, "error": f"Not found: {endpoint}"}
            elif response.status_code == 429:
                return {"success": False, "error": "Rate limit exceeded. Please try again later"}
            else:
                return {
                    "success": False,
                    "error": f"Notion API error: {response.status_code} - {response.text[:200]}"
                }

        except requests.exceptions.Timeout:
            return {"success": False, "error": "Request timed out. Notion server might be slow or unreachable"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Connection failed. Check network connectivity"}
        except Exception as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}

    def search(self, query: Optional[str] = None, filter_type: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        """
        Search Notion pages and databases.

        Args:
            query: Search query string (optional, returns all if not provided)
            filter_type: Filter by object type: 'page' or 'database' (optional)
            limit: Maximum number of results (default: 20, max: 100)

        Returns:
            Dict with 'success' flag and either 'results' list or 'error'
        """
        # Build search payload
        payload = {
            "page_size": min(limit, 100)
        }

        if query:
            payload["query"] = query

        if filter_type:
            payload["filter"] = {
                "value": filter_type,
                "property": "object"
            }

        # TODO: Add pagination support (has_more / start_cursor) for large workspaces
        result = self._make_request('search', method='POST', json_data=payload)

        if not result['success']:
            return result

        # Format results
        data = result['data']
        results = data.get('results', [])

        formatted_results = []
        for item in results:
            formatted_item = {
                'id': item.get('id'),
                'type': item.get('object'),  # 'page' or 'database'
                'created_time': item.get('created_time'),
                'last_edited_time': item.get('last_edited_time'),
                'url': item.get('url')
            }

            # Extract title
            if item.get('object') == 'page':
                properties = item.get('properties', {})
                title_prop = properties.get('title', {})
                if title_prop.get('title'):
                    formatted_item['title'] = ''.join([t.get('plain_text', '') for t in title_prop['title']])
            elif item.get('object') == 'database':
                title = item.get('title', [])
                if title:
                    formatted_item['title'] = ''.join([t.get('plain_text', '') for t in title])

            formatted_results.append(formatted_item)

        return {
            "success": True,
            "results": formatted_results,
            "total": len(formatted_results),
            "has_more": data.get('has_more', False)
        }

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get page content including properties and blocks.

        Args:
            page_id: Notion page ID

        Returns:
            Dict with 'success' flag and either 'page' dict or 'error'
        """
        if not page_id:
            return {"success": False, "error": "page_id is required"}

        # Get page metadata
        page_result = self._make_request(f'pages/{page_id}')
        if not page_result['success']:
            return page_result

        page = page_result['data']

        # Get page blocks (content)
        # Limitation: Only fetches top-level blocks. Nested children (e.g. items
        # inside toggles, columns, or synced blocks) are not recursively fetched.
        # TODO: Add pagination support (has_more / next_cursor) for pages with 100+ blocks
        blocks_result = self._make_request(f'blocks/{page_id}/children')
        if not blocks_result['success']:
            return blocks_result

        blocks = blocks_result['data'].get('results', [])

        # Extract text content from blocks
        content_parts = []
        for block in blocks:
            block_type = block.get('type')
            if block_type and block_type in block:
                block_content = block[block_type]
                if 'rich_text' in block_content:
                    text = ''.join([t.get('plain_text', '') for t in block_content['rich_text']])
                    if text:
                        content_parts.append(text)

        return {
            "success": True,
            "page": {
                'id': page.get('id'),
                'url': page.get('url'),
                'created_time': page.get('created_time'),
                'last_edited_time': page.get('last_edited_time'),
                'content': '\n\n'.join(content_parts)
            }
        }

    def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Get database schema and properties.

        Args:
            database_id: Notion database ID

        Returns:
            Dict with 'success' flag and either 'database' dict or 'error'
        """
        if not database_id:
            return {"success": False, "error": "database_id is required"}

        result = self._make_request(f'databases/{database_id}')
        if not result['success']:
            return result

        database = result['data']

        # Extract schema
        properties = database.get('properties', {})
        schema = {}
        for prop_name, prop_data in properties.items():
            schema[prop_name] = {
                'type': prop_data.get('type'),
                'id': prop_data.get('id')
            }

        return {
            "success": True,
            "database": {
                'id': database.get('id'),
                'title': ''.join([t.get('plain_text', '') for t in database.get('title', [])]),
                'url': database.get('url'),
                'created_time': database.get('created_time'),
                'last_edited_time': database.get('last_edited_time'),
                'schema': schema
            }
        }

    def query_database(
        self,
        database_id: str,
        filter_conditions: Optional[Dict] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Query database with optional filters.

        Args:
            database_id: Notion database ID
            filter_conditions: Optional filter object (Notion filter format)
            limit: Maximum results (default: 20, max: 100)

        Returns:
            Dict with 'success' flag and either 'results' list or 'error'
        """
        if not database_id:
            return {"success": False, "error": "database_id is required"}

        # Build query payload
        payload = {
            "page_size": min(limit, 100)
        }

        if filter_conditions:
            payload["filter"] = filter_conditions

        result = self._make_request(f'databases/{database_id}/query', method='POST', json_data=payload)

        if not result['success']:
            return result

        # Format results
        data = result['data']
        results = data.get('results', [])

        formatted_results = []
        for page in results:
            properties = page.get('properties', {})
            formatted_page = {
                'id': page.get('id'),
                'url': page.get('url'),
                'created_time': page.get('created_time'),
                'last_edited_time': page.get('last_edited_time'),
                'properties': {}
            }

            # Extract property values
            for prop_name, prop_data in properties.items():
                prop_type = prop_data.get('type')
                if prop_type == 'title':
                    formatted_page['properties'][prop_name] = ''.join([t.get('plain_text', '') for t in prop_data.get('title', [])])
                elif prop_type == 'rich_text':
                    formatted_page['properties'][prop_name] = ''.join([t.get('plain_text', '') for t in prop_data.get('rich_text', [])])
                elif prop_type in ['number', 'checkbox', 'url', 'email', 'phone_number']:
                    formatted_page['properties'][prop_name] = prop_data.get(prop_type)
                elif prop_type == 'select':
                    select = prop_data.get('select')
                    formatted_page['properties'][prop_name] = select.get('name') if select else None
                elif prop_type == 'multi_select':
                    formatted_page['properties'][prop_name] = [s.get('name') for s in prop_data.get('multi_select', [])]
                elif prop_type == 'date':
                    date = prop_data.get('date')
                    formatted_page['properties'][prop_name] = date.get('start') if date else None

            formatted_results.append(formatted_page)

        return {
            "success": True,
            "results": formatted_results,
            "total": len(formatted_results),
            "has_more": data.get('has_more', False)
        }


# Singleton instance
notion_service = NotionService()
