"""
Notion Integration Service - Notion API integration for NoobBook.

Educational Note: This service provides methods to query Notion pages and databases
using the Notion API. It follows NoobBook's service pattern with lazy-loaded
client initialization and environment-based configuration.

The page-fetch path recursively walks child blocks (with caps) so toggles,
sub-pages, column layouts, and nested lists actually surface in the text we
hand to RAG. Both ``search`` and the page/block walkers paginate through
``has_more`` / ``next_cursor`` so large workspaces and long pages aren't
truncated at 100 results.
"""
import logging
import os
from typing import Dict, Any, Optional, List, Tuple
import requests

logger = logging.getLogger(__name__)


# Recursion and result caps for page extraction. These guard against
# pathologically large or self-referential Notion pages so a single import
# can't run away with the worker pool. Tune in one place if needed.
MAX_RECURSION_DEPTH = 5
MAX_TOTAL_BLOCKS = 2000
MAX_PAGINATION_PAGES = 50  # ~5000 blocks/items per paginated endpoint


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
            logger.info("Notion service configured")

    def reload_config(self) -> None:
        """Reset cached config so next call re-reads from environment."""
        self._configured = None

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

    # ------------------------------------------------------------------
    # Pagination helpers
    # ------------------------------------------------------------------

    def _paginate_post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        page_size: int = 100,
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Walk a paginated POST endpoint until ``has_more`` is false or we hit
        MAX_PAGINATION_PAGES. Returns (success, results, error).
        """
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(MAX_PAGINATION_PAGES):
            body = dict(payload)
            body["page_size"] = min(page_size, 100)
            if cursor:
                body["start_cursor"] = cursor
            resp = self._make_request(endpoint, method='POST', json_data=body)
            if not resp.get("success"):
                return False, results, resp.get("error")
            data = resp["data"]
            results.extend(data.get("results", []) or [])
            if not data.get("has_more"):
                return True, results, None
            cursor = data.get("next_cursor")
            if not cursor:
                return True, results, None
        logger.warning("Notion pagination hit cap of %d pages at %s", MAX_PAGINATION_PAGES, endpoint)
        return True, results, None

    def _paginate_get(
        self,
        endpoint: str,
        page_size: int = 100,
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Walk a paginated GET endpoint (e.g. ``blocks/{id}/children``). Notion
        accepts start_cursor / page_size as query params on these endpoints.
        Returns (success, results, error).
        """
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        for _ in range(MAX_PAGINATION_PAGES):
            sep = '&' if '?' in endpoint else '?'
            url = f"{endpoint}{sep}page_size={min(page_size, 100)}"
            if cursor:
                url = f"{url}&start_cursor={cursor}"
            resp = self._make_request(url)
            if not resp.get("success"):
                return False, results, resp.get("error")
            data = resp["data"]
            results.extend(data.get("results", []) or [])
            if not data.get("has_more"):
                return True, results, None
            cursor = data.get("next_cursor")
            if not cursor:
                return True, results, None
        logger.warning("Notion pagination hit cap of %d pages at %s", MAX_PAGINATION_PAGES, endpoint)
        return True, results, None

    # ------------------------------------------------------------------
    # Block → text rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _rich_text_to_str(rich_text: Optional[List[Dict[str, Any]]]) -> str:
        """Join Notion's rich_text array into plain text."""
        if not rich_text:
            return ""
        return "".join(rt.get("plain_text", "") for rt in rich_text)

    @classmethod
    def _render_block(cls, block: Dict[str, Any], indent: int = 0) -> Optional[str]:
        """
        Render a single Notion block as markdown-ish plain text. Returns None
        when the block has no surfaceable text (e.g. unsupported embeds).
        Children are NOT rendered here — the recursive walker handles them.
        """
        block_type = block.get("type")
        if not block_type or block_type not in block:
            return None
        body = block[block_type] or {}
        text = cls._rich_text_to_str(body.get("rich_text"))
        prefix = "  " * indent

        if block_type == "paragraph":
            return f"{prefix}{text}" if text else None
        if block_type == "heading_1":
            return f"{prefix}# {text}" if text else None
        if block_type == "heading_2":
            return f"{prefix}## {text}" if text else None
        if block_type == "heading_3":
            return f"{prefix}### {text}" if text else None
        if block_type == "bulleted_list_item":
            return f"{prefix}- {text}"
        if block_type == "numbered_list_item":
            return f"{prefix}1. {text}"
        if block_type == "to_do":
            checked = body.get("checked", False)
            box = "[x]" if checked else "[ ]"
            return f"{prefix}- {box} {text}"
        if block_type == "toggle":
            return f"{prefix}▸ {text}" if text else None
        if block_type == "quote":
            return f"{prefix}> {text}" if text else None
        if block_type == "callout":
            return f"{prefix}> {text}" if text else None
        if block_type == "code":
            language = body.get("language", "")
            return f"{prefix}```{language}\n{text}\n{prefix}```" if text else None
        if block_type == "divider":
            return f"{prefix}---"
        if block_type == "child_page":
            # Title is on the block itself, not in rich_text
            title = body.get("title", "")
            return f"{prefix}## {title}" if title else None
        if block_type == "child_database":
            title = body.get("title", "")
            return f"{prefix}### Database: {title}" if title else None
        if block_type == "bookmark" or block_type == "embed":
            url = body.get("url", "")
            caption = cls._rich_text_to_str(body.get("caption"))
            label = caption or url
            return f"{prefix}[{label}]({url})" if url else None

        # Fallback: if we got any text out of rich_text, emit it
        return f"{prefix}{text}" if text else None

    def _walk_blocks(
        self,
        parent_id: str,
        indent: int,
        depth: int,
        counter: Dict[str, int],
    ) -> Tuple[List[str], Optional[str]]:
        """
        Recursively walk children of ``parent_id`` and return rendered lines.
        Caps recursion at MAX_RECURSION_DEPTH and total emitted blocks at
        MAX_TOTAL_BLOCKS. Returns (lines, error_or_none).
        """
        lines: List[str] = []
        if depth > MAX_RECURSION_DEPTH:
            return lines, None
        if counter["count"] >= MAX_TOTAL_BLOCKS:
            return lines, None

        ok, blocks, err = self._paginate_get(f"blocks/{parent_id}/children")
        if not ok:
            return lines, err

        for block in blocks:
            if counter["count"] >= MAX_TOTAL_BLOCKS:
                lines.append("…(truncated: page exceeded block cap)")
                return lines, None
            rendered = self._render_block(block, indent=indent)
            if rendered:
                lines.append(rendered)
                counter["count"] += 1

            if block.get("has_children") and depth < MAX_RECURSION_DEPTH:
                child_id = block.get("id")
                if child_id:
                    child_lines, child_err = self._walk_blocks(
                        child_id, indent=indent + 1, depth=depth + 1, counter=counter
                    )
                    if child_err:
                        # Don't abort the whole page on a single child fetch error
                        logger.warning(
                            "Notion child fetch failed for block %s: %s", child_id, child_err
                        )
                    lines.extend(child_lines)

        return lines, None

    # ------------------------------------------------------------------
    # Search / Page / Database
    # ------------------------------------------------------------------

    def search(self, query: Optional[str] = None, filter_type: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        """
        Search Notion pages and databases (paginated).

        Args:
            query: Search query string (optional, returns all if not provided)
            filter_type: Filter by object type: 'page' or 'database' (optional)
            limit: Maximum number of results to return after pagination (default 100)

        Returns:
            Dict with 'success' flag and either 'results' list or 'error'
        """
        payload: Dict[str, Any] = {}
        if query:
            payload["query"] = query
        if filter_type:
            payload["filter"] = {"value": filter_type, "property": "object"}

        ok, raw_results, err = self._paginate_post('search', payload, page_size=min(limit, 100))
        if not ok:
            return {"success": False, "error": err or "Notion search failed"}

        # Truncate to caller's requested limit after pagination so partial pages
        # don't get over-fetched in pathological cases.
        raw_results = raw_results[:limit]

        formatted_results: List[Dict[str, Any]] = []
        for item in raw_results:
            formatted_item: Dict[str, Any] = {
                'id': item.get('id'),
                'type': item.get('object'),  # 'page' or 'database'
                'created_time': item.get('created_time'),
                'last_edited_time': item.get('last_edited_time'),
                'url': item.get('url'),
            }

            # Extract title
            if item.get('object') == 'page':
                properties = item.get('properties', {}) or {}
                # Find the title property — it's not always called "title"
                title_text = ""
                for prop in properties.values():
                    if prop.get('type') == 'title':
                        title_text = self._rich_text_to_str(prop.get('title'))
                        break
                formatted_item['title'] = title_text or "Untitled"
            elif item.get('object') == 'database':
                formatted_item['title'] = self._rich_text_to_str(item.get('title')) or "Untitled"

            formatted_results.append(formatted_item)

        return {
            "success": True,
            "results": formatted_results,
            "total": len(formatted_results),
            "has_more": False,
        }

    def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get page content including properties and all nested blocks.

        Recursively walks child blocks (toggles, sub-pages, columns, nested
        lists) up to MAX_RECURSION_DEPTH levels and MAX_TOTAL_BLOCKS total
        rendered blocks. Long pages are paginated via the blocks/{id}/children
        endpoint.

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

        # Extract title from the page's own properties for display
        title = "Untitled"
        for prop in (page.get('properties') or {}).values():
            if prop.get('type') == 'title':
                title = self._rich_text_to_str(prop.get('title')) or "Untitled"
                break

        counter = {"count": 0}
        lines, err = self._walk_blocks(page_id, indent=0, depth=0, counter=counter)
        if err and not lines:
            return {"success": False, "error": err}

        content = "\n\n".join(line for line in lines if line)

        return {
            "success": True,
            "page": {
                'id': page.get('id'),
                'title': title,
                'url': page.get('url'),
                'created_time': page.get('created_time'),
                'last_edited_time': page.get('last_edited_time'),
                'content': content,
                'block_count': counter["count"],
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
        properties = database.get('properties', {}) or {}
        schema = {
            prop_name: {
                'type': prop_data.get('type'),
                'id': prop_data.get('id'),
            }
            for prop_name, prop_data in properties.items()
        }

        return {
            "success": True,
            "database": {
                'id': database.get('id'),
                'title': self._rich_text_to_str(database.get('title')) or "Untitled",
                'url': database.get('url'),
                'created_time': database.get('created_time'),
                'last_edited_time': database.get('last_edited_time'),
                'schema': schema,
            }
        }

    def query_database(
        self,
        database_id: str,
        filter_conditions: Optional[Dict] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Query database with optional filters (paginated).

        Args:
            database_id: Notion database ID
            filter_conditions: Optional filter object (Notion filter format)
            limit: Maximum results after pagination (default 100)

        Returns:
            Dict with 'success' flag and either 'results' list or 'error'
        """
        if not database_id:
            return {"success": False, "error": "database_id is required"}

        payload: Dict[str, Any] = {}
        if filter_conditions:
            payload["filter"] = filter_conditions

        ok, raw_results, err = self._paginate_post(
            f'databases/{database_id}/query', payload, page_size=min(limit, 100)
        )
        if not ok:
            return {"success": False, "error": err or "Notion database query failed"}

        raw_results = raw_results[:limit]

        formatted_results: List[Dict[str, Any]] = []
        for page in raw_results:
            properties = page.get('properties', {}) or {}
            formatted_page: Dict[str, Any] = {
                'id': page.get('id'),
                'url': page.get('url'),
                'created_time': page.get('created_time'),
                'last_edited_time': page.get('last_edited_time'),
                'properties': {},
            }

            # Extract property values
            for prop_name, prop_data in properties.items():
                prop_type = prop_data.get('type')
                if prop_type == 'title':
                    formatted_page['properties'][prop_name] = self._rich_text_to_str(prop_data.get('title'))
                elif prop_type == 'rich_text':
                    formatted_page['properties'][prop_name] = self._rich_text_to_str(prop_data.get('rich_text'))
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
            "has_more": False,
        }


# Singleton instance
notion_service = NotionService()
