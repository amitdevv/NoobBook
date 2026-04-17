"""
Mixpanel Integration Service - Query API access for NoobBook chat.

Educational Note: Uses Mixpanel's Service Account auth (HTTP Basic) against
the Query API (https://mixpanel.com/api/query/). No OAuth — admin configures
one service account globally; all users in the app share access to that
Mixpanel project.

Lazy singleton pattern mirroring jira_service.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class MixpanelService:
    """
    Mixpanel Query API service.

    Config (env vars):
        MIXPANEL_SERVICE_ACCOUNT_USERNAME
        MIXPANEL_SERVICE_ACCOUNT_SECRET
        MIXPANEL_PROJECT_ID
        MIXPANEL_REGION (optional, "us" | "eu" | "in"; default "us")
    """

    REGION_HOSTS = {
        "us": "https://mixpanel.com",
        "eu": "https://eu.mixpanel.com",
        "in": "https://in.mixpanel.com",
    }

    def __init__(self):
        self._auth: Optional[HTTPBasicAuth] = None
        self._project_id: Optional[str] = None
        self._base_url: Optional[str] = None
        self._configured: Optional[bool] = None

    def _load_config(self) -> None:
        if self._configured is not None:
            return

        username = os.getenv("MIXPANEL_SERVICE_ACCOUNT_USERNAME", "").strip().strip('"')
        secret = os.getenv("MIXPANEL_SERVICE_ACCOUNT_SECRET", "").strip().strip('"')
        project_id = os.getenv("MIXPANEL_PROJECT_ID", "").strip().strip('"')
        region = os.getenv("MIXPANEL_REGION", "us").strip().lower() or "us"

        host = self.REGION_HOSTS.get(region, self.REGION_HOSTS["us"])
        self._base_url = f"{host}/api/query"
        self._auth = HTTPBasicAuth(username, secret) if username and secret else None
        self._project_id = project_id or None
        self._configured = bool(self._auth and self._project_id)

        if self._configured:
            logger.info("Mixpanel service configured: project_id=%s region=%s", project_id, region)

    def reload_config(self) -> None:
        """Reset cached config so next call re-reads env vars."""
        self._configured = None

    def is_configured(self) -> bool:
        self._load_config()
        return bool(self._configured)

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        method: str = "GET",
    ) -> Dict[str, Any]:
        """
        Call the Mixpanel Query API.

        Educational Note: Mixpanel's Query API returns either JSON objects or
        NDJSON (for /export). The endpoints we use here all return JSON.
        """
        self._load_config()
        if not self._configured:
            return {
                "success": False,
                "error": (
                    "Mixpanel not configured. Please add MIXPANEL_SERVICE_ACCOUNT_USERNAME, "
                    "MIXPANEL_SERVICE_ACCOUNT_SECRET, and MIXPANEL_PROJECT_ID to your .env."
                ),
            }

        # project_id is required on every Query API call
        merged_params = {"project_id": self._project_id}
        if params:
            merged_params.update({k: v for k, v in params.items() if v is not None})

        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        headers = {"Accept": "application/json"}

        try:
            if method == "GET":
                response = requests.get(
                    url, auth=self._auth, headers=headers, params=merged_params, timeout=30
                )
            elif method == "POST":
                response = requests.post(
                    url, auth=self._auth, headers=headers, data=merged_params, timeout=30
                )
            else:
                return {"success": False, "error": f"Unsupported HTTP method: {method}"}

            if response.status_code == 200:
                try:
                    return {"success": True, "data": response.json()}
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid JSON response from Mixpanel: {response.text[:200]}",
                    }
            if response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed. Check service account username/secret.",
                }
            if response.status_code == 402:
                return {
                    "success": False,
                    "error": "Mixpanel rejected the request (payment/quota). See response: "
                    + response.text[:200],
                }
            if response.status_code == 403:
                return {
                    "success": False,
                    "error": "Permission denied. Service account must have access to the project.",
                }
            if response.status_code == 404:
                return {"success": False, "error": f"Not found: {endpoint}"}
            if response.status_code == 429:
                return {
                    "success": False,
                    "error": "Rate limit hit (Mixpanel Query API: 60/hr, 5 concurrent). Try again later.",
                }
            return {
                "success": False,
                "error": f"Mixpanel API error: {response.status_code} - {response.text[:200]}",
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Mixpanel request timed out."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Could not connect to Mixpanel API."}
        except Exception as e:
            return {"success": False, "error": f"Request failed: {str(e)}"}

    # --- Tool methods ---

    def list_events(self, limit: int = 100) -> Dict[str, Any]:
        """
        List event names tracked in the project.

        Endpoint: GET /events/names?type=general&limit=N
        """
        result = self._make_request(
            "events/names",
            params={"type": "general", "limit": min(max(limit, 1), 255)},
        )
        if not result["success"]:
            return result

        names = result["data"]
        if not isinstance(names, list):
            names = []

        return {"success": True, "events": names, "total": len(names)}

    def query_events(
        self,
        event_names: List[str],
        from_date: str,
        to_date: str,
        unit: str = "day",
        event_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Get event counts over time.

        Endpoint: GET /events?event=["A","B"]&from_date=YYYY-MM-DD&to_date=YYYY-MM-DD&unit=day&type=general
        """
        if not event_names:
            return {"success": False, "error": "event_names is required (non-empty list)."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        return self._make_request(
            "events",
            params={
                "event": json.dumps(event_names),
                "from_date": from_date,
                "to_date": to_date,
                "unit": unit,
                "type": event_type,
            },
        )

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: Optional[str] = None,
        where: Optional[str] = None,
        unit: str = "day",
        segmentation_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Segment a single event by a property.

        Endpoint: GET /segmentation?event=X&from_date=Y&to_date=Z&on=properties["..."]&type=general
        """
        if not event:
            return {"success": False, "error": "event is required."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        params: Dict[str, Any] = {
            "event": event,
            "from_date": from_date,
            "to_date": to_date,
            "unit": unit,
            "type": segmentation_type,
        }
        if on:
            params["on"] = on
        if where:
            params["where"] = where

        return self._make_request("segmentation", params=params)

    def list_funnels(self) -> Dict[str, Any]:
        """List funnels configured in the project. Endpoint: GET /funnels/list"""
        result = self._make_request("funnels/list")
        if not result["success"]:
            return result

        funnels = result["data"]
        if not isinstance(funnels, list):
            funnels = []

        formatted = [
            {"funnel_id": f.get("funnel_id"), "name": f.get("name")}
            for f in funnels
        ]
        return {"success": True, "funnels": formatted, "total": len(formatted)}

    def query_funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        unit: str = "day",
    ) -> Dict[str, Any]:
        """
        Query funnel conversion over time.

        Endpoint: GET /funnels?funnel_id=N&from_date=Y&to_date=Z&unit=day
        """
        if funnel_id is None:
            return {"success": False, "error": "funnel_id is required (integer)."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        return self._make_request(
            "funnels",
            params={
                "funnel_id": funnel_id,
                "from_date": from_date,
                "to_date": to_date,
                "unit": unit,
            },
        )

    def retention(
        self,
        born_event: str,
        event: Optional[str],
        from_date: str,
        to_date: str,
        retention_type: str = "birth",
        unit: str = "day",
    ) -> Dict[str, Any]:
        """
        Retention analysis.

        Endpoint: GET /retention?from_date=Y&to_date=Z&retention_type=birth&born_event=X&event=Y&unit=day
        """
        if not born_event:
            return {"success": False, "error": "born_event is required."}
        if not from_date or not to_date:
            return {"success": False, "error": "from_date and to_date are required (YYYY-MM-DD)."}

        params: Dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "retention_type": retention_type,
            "born_event": born_event,
            "unit": unit,
        }
        if event:
            params["event"] = event

        return self._make_request("retention", params=params)

    def jql(self, script: str) -> Dict[str, Any]:
        """
        Run a JQL script.

        Endpoint: POST /jql  (form-encoded with `script`)

        Educational Note: JQL is feature-complete but deprecated in Mixpanel's
        docs. Still the most expressive query tool — kept as an escape hatch.
        """
        if not script or not script.strip():
            return {"success": False, "error": "script is required (JavaScript JQL code)."}

        return self._make_request("jql", params={"script": script}, method="POST")


# Singleton instance
mixpanel_service = MixpanelService()
