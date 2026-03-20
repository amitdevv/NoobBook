"""
Freshdesk Integration Service - Freshdesk API client for NoobBook.

Educational Note: This service provides methods to query Freshdesk tickets
using the Freshdesk REST API v2. It follows NoobBook's service pattern with
lazy-loaded client initialization and environment-based configuration.

Freshdesk uses Basic Auth with the API key as username and 'X' as password.
Rate limiting is handled by checking the X-RateLimit-Remaining response header.
"""
import logging
import os
import time
from typing import Dict, Any, Optional, List

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


# Freshdesk ticket field mappings
# Educational Note: Freshdesk stores these as integer codes in the API response.
# We resolve them to human-readable labels for the analysis agent.
STATUS_MAP: Dict[int, str] = {
    2: "Open",
    3: "Pending",
    4: "Resolved",
    5: "Closed",
    6: "Waiting on Customer",
    7: "Waiting on Third Party",
}

PRIORITY_MAP: Dict[int, str] = {
    1: "Low",
    2: "Medium",
    3: "High",
    4: "Urgent",
}

SOURCE_MAP: Dict[int, str] = {
    1: "Email",
    2: "Portal",
    3: "Phone",
    7: "Chat",
    9: "Feedback Widget",
    10: "Outbound Email",
}


class FreshdeskService:
    """
    Freshdesk API integration service.

    Educational Note: Singleton pattern with lazy client initialization.
    Configuration is read from environment variables on first use.
    Freshdesk API uses Basic Auth: (api_key, 'X').
    """

    def __init__(self):
        """Initialize the Freshdesk service with lazy-loaded configuration."""
        self._api_key: Optional[str] = None
        self._domain: Optional[str] = None
        self._base_url: Optional[str] = None
        self._configured: Optional[bool] = None

        # Caches for name resolution (populated by populate_caches)
        self._agents_cache: Dict[int, Dict[str, str]] = {}
        self._groups_cache: Dict[int, str] = {}
        self._products_cache: Dict[int, str] = {}

    def _load_config(self) -> None:
        """
        Lazy-load Freshdesk configuration from environment variables.

        Educational Note: Freshdesk API base URL is:
        https://{domain}.freshdesk.com/api/v2
        """
        if self._configured is not None:
            return  # Already loaded

        self._api_key = os.getenv("FRESHDESK_API_KEY", "").strip()
        self._domain = os.getenv("FRESHDESK_DOMAIN", "").strip()

        if self._api_key and self._domain:
            # Strip protocol and trailing slashes if user accidentally included them
            domain = self._domain.replace("https://", "").replace("http://", "").rstrip("/")
            # Handle both "company" and "company.freshdesk.com" formats
            if ".freshdesk.com" not in domain:
                domain = f"{domain}.freshdesk.com"
            self._base_url = f"https://{domain}/api/v2"
            self._configured = True
            logger.info("Freshdesk service configured: %s", domain)
        else:
            self._configured = False

    def reload_config(self) -> None:
        """Reset cached config so next call re-reads from environment."""
        self._configured = None
        self._agents_cache.clear()
        self._groups_cache.clear()
        self._products_cache.clear()

    def is_configured(self) -> bool:
        """Check if Freshdesk credentials are configured."""
        self._load_config()
        return self._configured

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make a GET request to the Freshdesk API.

        Educational Note: Freshdesk API uses Basic Auth with the API key as
        username and 'X' as password. Rate limits are communicated via the
        X-RateLimit-Remaining header. When it reaches 0, we wait until the
        rate limit resets (indicated by the Retry-After header).

        Args:
            endpoint: API endpoint (relative to base_url, e.g., "tickets")
            params: Query parameters

        Returns:
            Dict with 'success' flag and either 'data' or 'error'
        """
        self._load_config()

        if not self._configured:
            return {
                "success": False,
                "error": "Freshdesk not configured. Please add FRESHDESK_API_KEY and FRESHDESK_DOMAIN to .env",
            }

        try:
            url = f"{self._base_url}/{endpoint}"
            auth = HTTPBasicAuth(self._api_key, "X")
            headers = {"Content-Type": "application/json"}

            response = requests.get(
                url, auth=auth, headers=headers, params=params, timeout=30
            )

            # Handle rate limiting
            # Educational Note: Freshdesk returns X-RateLimit-Remaining header.
            # When exhausted, we should wait for the Retry-After period.
            rate_remaining = response.headers.get("X-RateLimit-Remaining")
            if rate_remaining is not None and int(rate_remaining) <= 1:
                retry_after = int(response.headers.get("Retry-After", "30"))
                logger.warning(
                    "Freshdesk rate limit nearly exhausted. Waiting %ds.",
                    retry_after,
                )
                time.sleep(retry_after)

            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed. Check your FRESHDESK_API_KEY.",
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "error": "Permission denied. Check your Freshdesk permissions.",
                }
            elif response.status_code == 404:
                return {"success": False, "error": f"Not found: {endpoint}"}
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                return {
                    "success": False,
                    "error": f"Rate limited. Retry after {retry_after}s.",
                }
            else:
                return {
                    "success": False,
                    "error": f"Freshdesk API error: {response.status_code} - {response.text[:200]}",
                }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out. Freshdesk server might be slow or unreachable.",
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Connection failed. Check FRESHDESK_DOMAIN and network connectivity.",
            }
        except Exception as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}

    def list_tickets(
        self,
        updated_since: Optional[str] = None,
        page: int = 1,
        per_page: int = 100,
    ) -> List[Dict]:
        """
        List tickets with pagination.

        Educational Note: Freshdesk /tickets endpoint supports:
        - updated_since: ISO 8601 datetime filter
        - include: comma-separated list of related objects to embed
        - page/per_page: pagination controls (max 100 per page)

        Args:
            updated_since: ISO datetime string to filter tickets updated after this time
            page: Page number (1-indexed)
            per_page: Results per page (max 100)

        Returns:
            List of ticket dicts (empty list on error)
        """
        params: Dict[str, Any] = {
            "page": page,
            "per_page": min(per_page, 100),
            "include": "description,requester,stats,company",
            "order_by": "updated_at",
            "order_type": "desc",
        }

        if updated_since:
            params["updated_since"] = updated_since

        result = self._make_request("tickets", params=params)
        if not result["success"]:
            logger.error("Failed to list tickets (page %d): %s", page, result.get("error"))
            return []

        return result.get("data", [])

    def fetch_all_tickets(
        self, updated_since: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch all tickets across all pages.

        Educational Note: Freshdesk paginates at 100 tickets per page.
        We iterate through pages until we get an empty page or fewer
        results than the page size.

        Args:
            updated_since: ISO datetime string to filter tickets

        Returns:
            Combined list of all ticket dicts
        """
        all_tickets: List[Dict] = []
        page = 1
        per_page = 100

        while True:
            tickets = self.list_tickets(
                updated_since=updated_since,
                page=page,
                per_page=per_page,
            )

            if not tickets:
                break

            all_tickets.extend(tickets)
            logger.info(
                "Freshdesk: fetched page %d (%d tickets, %d total)",
                page,
                len(tickets),
                len(all_tickets),
            )

            # If we got fewer than per_page, we've reached the last page
            if len(tickets) < per_page:
                break

            page += 1

            # Safety limit: Freshdesk API caps at 300 pages
            if page > 300:
                logger.warning("Freshdesk: hit 300-page safety limit")
                break

        return all_tickets

    def populate_caches(self) -> None:
        """
        Populate internal caches for agents, groups, and products.

        Educational Note: Freshdesk tickets reference agents, groups, and products
        by numeric ID. We fetch these lookup tables once and cache them so we can
        resolve IDs to human-readable names during ticket transformation.
        """
        # Fetch agents (paginated, typically < 500)
        self._agents_cache.clear()
        page = 1
        while True:
            result = self._make_request("agents", params={"page": page, "per_page": 100})
            if not result["success"]:
                logger.warning("Failed to fetch agents page %d: %s", page, result.get("error"))
                break
            agents = result.get("data", [])
            if not agents:
                break
            for agent in agents:
                agent_id = agent.get("id")
                contact = agent.get("contact", {}) or {}
                self._agents_cache[agent_id] = {
                    "name": contact.get("name", "Unknown Agent"),
                    "email": contact.get("email", ""),
                }
            if len(agents) < 100:
                break
            page += 1

        # Fetch groups
        self._groups_cache.clear()
        result = self._make_request("groups")
        if result["success"]:
            for group in result.get("data", []):
                self._groups_cache[group.get("id")] = group.get("name", "Unknown Group")

        # Fetch products
        self._products_cache.clear()
        result = self._make_request("products")
        if result["success"]:
            for product in result.get("data", []):
                self._products_cache[product.get("id")] = product.get("name", "Unknown Product")

        logger.info(
            "Freshdesk caches populated: %d agents, %d groups, %d products",
            len(self._agents_cache),
            len(self._groups_cache),
            len(self._products_cache),
        )

    def resolve_agent(self, agent_id: Optional[int]) -> Dict[str, str]:
        """
        Resolve an agent ID to name and email.

        Args:
            agent_id: Freshdesk agent ID

        Returns:
            Dict with 'name' and 'email' keys
        """
        if not agent_id:
            return {"name": "Unassigned", "email": ""}
        cached = self._agents_cache.get(agent_id)
        if cached:
            return cached
        return {"name": f"Agent #{agent_id}", "email": ""}

    def resolve_group(self, group_id: Optional[int]) -> str:
        """
        Resolve a group ID to its name.

        Args:
            group_id: Freshdesk group ID

        Returns:
            Group name string
        """
        if not group_id:
            return "None"
        return self._groups_cache.get(group_id, f"Group #{group_id}")

    def resolve_product(self, product_id: Optional[int]) -> str:
        """
        Resolve a product ID to its name.

        Args:
            product_id: Freshdesk product ID

        Returns:
            Product name string
        """
        if not product_id:
            return "None"
        return self._products_cache.get(product_id, f"Product #{product_id}")


# Singleton instance
freshdesk_service = FreshdeskService()
