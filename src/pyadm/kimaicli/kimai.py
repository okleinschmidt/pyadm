"""Thin wrapper around the Kimai REST API (Kimai 2.x, /api endpoints)."""

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Union

import requests

from pyadm.net_utils import apply_force_ipv4, config_flag

logger = logging.getLogger(__name__)

# Kimai expects HTML5 datetime-local values, i.e. without a timezone offset.
API_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

DEFAULT_TIMEOUT = 30


class KimaiError(RuntimeError):
    """Raised when the Kimai API rejects a request or cannot be reached."""


def format_api_datetime(value: datetime) -> str:
    """Render a datetime the way Kimai's API wants it: local time, no offset."""
    return value.replace(tzinfo=None).strftime(API_DATETIME_FORMAT)


def parse_api_datetime(value: str) -> datetime:
    """Parse a datetime as returned by the API (may carry an offset or 'Z')."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def entity_id(value: Any) -> Optional[int]:
    """Extract an entity ID from an API field that is either an ID or an object."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if isinstance(value, dict):
        return entity_id(value.get("id"))
    return None


def entity_name(value: Any, fallback: str = "") -> str:
    """Extract a display name from an API field that may just be an ID."""
    if isinstance(value, dict):
        for key in ("name", "title", "alias", "username"):
            if value.get(key):
                return str(value[key])
        return str(value.get("id", fallback))
    if value is None:
        return fallback
    return str(value)


class KimaiClient:
    """Client for a single Kimai instance."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Args:
            config: Context section with 'url' and credentials. Either an API
                token ('api_token'/'token') for bearer auth, or 'username' plus
                'api_password'/'password' for the legacy X-AUTH headers.
        """
        self.config = config
        url = (config.get("url") or config.get("base_url") or "").strip()
        if not url:
            raise KimaiError("No 'url' configured for this Kimai context.")
        self.base_url = url.rstrip("/")

        # A host whose AAAA record is unreachable costs a connect timeout per call
        apply_force_ipv4(config)

        self.verify = not config_flag(config, "skip_tls_verify")
        try:
            self.timeout = int(str(config.get("timeout", DEFAULT_TIMEOUT)).strip())
        except ValueError:
            self.timeout = DEFAULT_TIMEOUT

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        token = (config.get("api_token") or config.get("token") or "").strip()
        username = (config.get("username") or config.get("user") or "").strip()
        password = (config.get("api_password") or config.get("password") or "").strip()

        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            # Kimai 1.x and early 2.x: user plus API password in custom headers
            self.session.headers["X-AUTH-USER"] = username
            self.session.headers["X-AUTH-TOKEN"] = password
        else:
            raise KimaiError(
                "No Kimai credentials configured. Set 'api_token', or "
                "'username' together with 'api_password'."
            )

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        logger.debug("Kimai %s %s params=%s payload=%s", method, url, params, payload)
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=payload,
                verify=self.verify,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise KimaiError(f"Kimai API not reachable: {exc}") from exc

        if response.status_code >= 400:
            raise KimaiError(
                f"Kimai API error {response.status_code} on {method} {path}: "
                f"{response.text.strip()}"
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise KimaiError(f"Unexpected non-JSON response from {method} {path}") from exc

    def _get_list(self, path: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        data = self._request("GET", path, params=params)
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Instance / user
    # ------------------------------------------------------------------
    def ping(self) -> Dict[str, Any]:
        """Check that the API answers and the credentials are accepted."""
        return self._request("GET", "/api/ping") or {}

    def version(self) -> Dict[str, Any]:
        """Return version information about the Kimai instance."""
        return self._request("GET", "/api/version") or {}

    def me(self) -> Dict[str, Any]:
        """Return the user the API token belongs to."""
        return self._request("GET", "/api/users/me") or {}

    def list_users(self, visible: str = "1") -> List[Dict[str, Any]]:
        """List users (requires admin permissions)."""
        return self._get_list("/api/users", {"visible": visible})

    # ------------------------------------------------------------------
    # Master data
    # ------------------------------------------------------------------
    def list_customers(self, visible: str = "1", term: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"visible": visible}
        if term:
            params["term"] = term
        return self._get_list("/api/customers", params)

    def list_projects(
        self,
        customer: Optional[int] = None,
        visible: str = "1",
        term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"visible": visible}
        if customer is not None:
            params["customer"] = customer
        if term:
            params["term"] = term
        return self._get_list("/api/projects", params)

    def list_activities(
        self,
        project: Optional[int] = None,
        visible: str = "1",
        term: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"visible": visible}
        if project is not None:
            # Activities bound to the project, plus the global ones
            params["project"] = project
            params["globals"] = "true"
        activities = self._get_list("/api/activities", params)
        if term:
            # The activities endpoint has no term filter, so narrow it here
            needle = term.lower()
            activities = [
                a for a in activities if needle in entity_name(a.get("name")).lower()
            ]
        return activities

    def list_tags(self) -> List[str]:
        data = self._request("GET", "/api/tags")
        if not isinstance(data, list):
            return []
        return [item if isinstance(item, str) else entity_name(item) for item in data]

    def get_customer(self, customer_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/customers/{customer_id}") or {}

    def get_project(self, project_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/projects/{project_id}") or {}

    def get_activity(self, activity_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/activities/{activity_id}") or {}

    # ------------------------------------------------------------------
    # Name resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _match_by_name(items: List[Dict[str, Any]], name: str, label: str) -> Dict[str, Any]:
        """Find exactly one item by name: exact match wins, else unique substring."""
        wanted = name.strip().lower()
        exact = [i for i in items if entity_name(i.get("name")).strip().lower() == wanted]
        candidates = exact or [
            i for i in items if wanted in entity_name(i.get("name")).strip().lower()
        ]

        if not candidates:
            raise KimaiError(f"No {label} found matching '{name}'.")
        if len(candidates) > 1:
            names = ", ".join(
                f"{entity_name(c.get('name'))} (ID {c.get('id')})" for c in candidates[:10]
            )
            raise KimaiError(
                f"'{name}' matches several {label}s: {names}. "
                f"Use the numeric ID or a more specific name."
            )
        return candidates[0]

    def resolve_customer(self, value: Union[str, int]) -> Dict[str, Any]:
        """Resolve a customer ID or name to the customer object."""
        if str(value).isdigit():
            return self.get_customer(int(value))
        return self._match_by_name(self.list_customers(visible="3"), str(value), "customer")

    def resolve_project(self, value: Union[str, int]) -> Dict[str, Any]:
        """Resolve a project ID or name to the project object."""
        if str(value).isdigit():
            return self.get_project(int(value))
        return self._match_by_name(self.list_projects(visible="3"), str(value), "project")

    def resolve_activity(
        self, value: Union[str, int], project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Resolve an activity ID or name, preferring activities of *project_id*."""
        if str(value).isdigit():
            return self.get_activity(int(value))

        if project_id is not None:
            scoped = self.list_activities(project=project_id, visible="3")
            try:
                return self._match_by_name(scoped, str(value), "activity")
            except KimaiError:
                # Fall through to a global lookup so an unassigned activity still works
                logger.debug("Activity '%s' not found for project %s", value, project_id)
        return self._match_by_name(self.list_activities(visible="3"), str(value), "activity")

    # ------------------------------------------------------------------
    # Timesheets
    # ------------------------------------------------------------------
    def list_timesheets(
        self,
        begin: Optional[datetime] = None,
        end: Optional[datetime] = None,
        project: Optional[int] = None,
        activity: Optional[int] = None,
        user: Optional[Union[int, str]] = None,
        size: int = 100,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"size": size, "page": page, "order": "DESC"}
        if begin is not None:
            params["begin"] = format_api_datetime(begin)
        if end is not None:
            params["end"] = format_api_datetime(end)
        if project is not None:
            params["project"] = project
        if activity is not None:
            params["activity"] = activity
        if user is not None:
            params["user"] = user
        return self._get_list("/api/timesheets", params)

    def list_timesheets_for_day(self, target_date: date, tzinfo) -> List[Dict[str, Any]]:
        """All timesheets that start on *target_date* in the given timezone."""
        day_start = datetime.combine(target_date, time(0, 0), tzinfo=tzinfo)
        return self.list_timesheets(begin=day_start, end=day_start + timedelta(days=1), size=200)

    def get_timesheet(self, timesheet_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/api/timesheets/{timesheet_id}") or {}

    def active_timesheets(self) -> List[Dict[str, Any]]:
        """Currently running timesheet records of the authenticated user."""
        return self._get_list("/api/timesheets/active")

    def create_timesheet(
        self,
        *,
        begin: datetime,
        end: Optional[datetime],
        project_id: int,
        activity_id: int,
        description: str = "",
        tags: Optional[List[str]] = None,
        user_id: Optional[int] = None,
        billable: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Create a timesheet record. Without *end* the record is left running."""
        payload: Dict[str, Any] = {
            "begin": format_api_datetime(begin),
            "project": project_id,
            "activity": activity_id,
        }
        if end is not None:
            payload["end"] = format_api_datetime(end)
        if description:
            payload["description"] = description
        if tags:
            # Some Kimai versions expect a comma-separated string rather than a list
            payload["tags"] = ",".join(tags)
        if user_id is not None:
            payload["user"] = user_id
        if billable is not None:
            payload["billable"] = billable

        created = self._request("POST", "/api/timesheets", payload=payload)
        if not isinstance(created, dict):
            raise KimaiError("Unexpected API response while creating a timesheet.")
        return created

    def update_timesheet(self, timesheet_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        updated = self._request("PATCH", f"/api/timesheets/{timesheet_id}", payload=payload)
        return updated if isinstance(updated, dict) else {}

    def delete_timesheet(self, timesheet_id: int) -> None:
        self._request("DELETE", f"/api/timesheets/{timesheet_id}")

    def stop_timesheet(self, timesheet_id: int) -> Dict[str, Any]:
        stopped = self._request("PATCH", f"/api/timesheets/{timesheet_id}/stop")
        return stopped if isinstance(stopped, dict) else {}

    def restart_timesheet(self, timesheet_id: int) -> Dict[str, Any]:
        restarted = self._request("PATCH", f"/api/timesheets/{timesheet_id}/restart")
        return restarted if isinstance(restarted, dict) else {}
