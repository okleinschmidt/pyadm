"""Client for an Uptime Kuma instance.

Uptime Kuma has no REST API: the frontend talks to the server over Socket.IO,
and so does this client through the 'uptime-kuma-api' package. The import is
deferred to the first connection so that the rest of pyadm keeps working when
the package is not installed.

Times are the awkward part of the protocol. Uptime Kuma stores maintenance
windows as naive 'YYYY-MM-DD HH:MM:SS' strings plus a separate timezone name,
so everything here is formatted without an offset and the timezone travels in
the 'timezoneOption' field.
"""

import logging
import re
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Sequence, Union

from pyadm.net_utils import apply_force_ipv4, config_flag

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30

# How Uptime Kuma writes the timestamps of a maintenance window.
API_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

DURATION_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+(?:\.\d+)?)h)?(?:(?P<minutes>\d+)m)?$",
    re.IGNORECASE,
)

WEEKDAY_NAMES = {
    "sun": 0, "sunday": 0,
    "mon": 1, "monday": 1,
    "tue": 2, "tues": 2, "tuesday": 2,
    "wed": 3, "weds": 3, "wednesday": 3,
    "thu": 4, "thur": 4, "thurs": 4, "thursday": 4,
    "fri": 5, "friday": 5,
    "sat": 6, "saturday": 6,
}

# Uptime Kuma counts weekdays from Sunday, so the groups are spelled out here
# rather than derived from Python's Monday-based numbering.
WEEKDAY_GROUPS = {
    "weekdays": [1, 2, 3, 4, 5],
    "workdays": [1, 2, 3, 4, 5],
    "weekend": [0, 6],
    "all": [0, 1, 2, 3, 4, 5, 6],
    "daily": [0, 1, 2, 3, 4, 5, 6],
}

WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Heartbeat status codes as they arrive in 'important' and beat lists.
MONITOR_STATUS_NAMES = {0: "down", 1: "up", 2: "pending", 3: "maintenance"}


# Fields that Uptime Kuma 2.x stores NOT NULL but that uptime-kuma-api - which
# targets 1.23 - does not send. Without them the server's INSERT fails.
SERVER_2X_MONITOR_FIELDS = {"conditions": []}

# A backend error arrives with the whole failed statement in front of the
# actual complaint: "insert into `monitor` (...) values (...) - SQLITE_...".
SQL_STATEMENT = re.compile(r"^(insert into|update|delete from|select)\b", re.IGNORECASE)
MISSING_COLUMN = re.compile(r"NOT NULL constraint failed: \w+\.(\w+)")


class UptimeError(RuntimeError):
    """Raised when Uptime Kuma rejects a request or cannot be reached."""


def explain_error(message: Any) -> str:
    """Turn a backend error into a sentence that says what to do about it.

    Uptime Kuma passes database errors through verbatim, so a missing field
    reaches the client as a page of SQL. The statement is dropped and the
    known causes are named; the original text stays available with --debug.
    """
    text = " ".join(str(message).split())

    if SQL_STATEMENT.match(text) and " - " in text:
        # Keep the complaint at the end, drop the statement in front of it.
        text = text.rsplit(" - ", 1)[-1].strip()

    missing = MISSING_COLUMN.search(text)
    if missing:
        return (
            f"the server requires the monitor field '{missing.group(1)}', which "
            f"this client did not send. The Uptime Kuma server is newer than the "
            f"installed 'uptime-kuma-api' supports; run with --debug for the "
            f"original message."
        )
    if "SQLITE_CONSTRAINT" in text or "ER_" in text:
        return f"the server rejected the data: {text}"
    return text


# ----------------------------------------------------------------------
# Parsing helpers (no Click, so they stay testable on their own)
# ----------------------------------------------------------------------
def parse_duration(value: str) -> timedelta:
    """Parse '2h', '90m', '1h30m', '1:30' or a plain number of minutes."""
    text = str(value).strip().lower()
    if not text:
        raise UptimeError("Duration cannot be empty.")

    if ":" in text:
        parts = text.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise UptimeError(f"Invalid duration '{value}'. Use HH:MM or 1h30m.")
        return timedelta(hours=int(parts[0]), minutes=int(parts[1]))

    if text.isdigit():
        return timedelta(minutes=int(text))

    match = DURATION_PATTERN.match(text)
    if not match or not any(match.groupdict().values()):
        raise UptimeError(
            f"Invalid duration '{value}'. Use e.g. 2h, 90m, 1h30m or 1:30."
        )
    return timedelta(
        hours=float(match.group("hours") or 0),
        minutes=int(match.group("minutes") or 0),
    )


def parse_time(value: str) -> time:
    """Parse 'HH:MM' or 'HH:MM:SS'."""
    try:
        return time.fromisoformat(str(value).strip())
    except ValueError as exc:
        raise UptimeError(f"Invalid time '{value}'. Use HH:MM.") from exc


def parse_datetime(value: str, now: Optional[datetime] = None) -> datetime:
    """Parse a point in time as accepted on the command line.

    Understood: 'now', 'YYYY-MM-DD HH:MM', 'YYYY-MM-DDTHH:MM', 'YYYY-MM-DD'
    (midnight), and a bare 'HH:MM' meaning today - or tomorrow, when that time
    has already passed.
    """
    reference = now or datetime.now()
    text = str(value).strip()
    if text.lower() == "now":
        return reference.replace(second=0, microsecond=0)

    try:
        return datetime.fromisoformat(text.replace(" ", "T"))
    except ValueError:
        pass

    try:
        parsed_time = time.fromisoformat(text)
    except ValueError as exc:
        raise UptimeError(
            f"Invalid date/time '{value}'. Use 'now', 'HH:MM', 'YYYY-MM-DD' or "
            f"'YYYY-MM-DD HH:MM'."
        ) from exc

    candidate = datetime.combine(reference.date(), parsed_time)
    if candidate < reference:
        # A bare time in the past means the next occurrence, not a window
        # that ended before it began.
        candidate += timedelta(days=1)
    return candidate


def parse_time_range(value: str) -> List[Dict[str, int]]:
    """Parse 'HH:MM-HH:MM' into the pair of time objects the API expects."""
    text = str(value).strip()
    if "-" not in text:
        raise UptimeError(f"Invalid time window '{value}'. Use HH:MM-HH:MM.")
    begin_text, _, end_text = text.partition("-")
    begin, end = parse_time(begin_text), parse_time(end_text)
    return [
        {"hours": begin.hour, "minutes": begin.minute},
        {"hours": end.hour, "minutes": end.minute},
    ]


def parse_weekdays(values: Sequence[str]) -> List[int]:
    """Turn weekday names, ranges ('mon-fri') and groups ('weekend') into indexes."""
    selected: List[int] = []

    def add(index: int) -> None:
        if index not in selected:
            selected.append(index)

    for raw in values:
        for token in str(raw).replace(" ", "").split(","):
            if not token:
                continue
            key = token.lower()
            if key in WEEKDAY_GROUPS:
                for index in WEEKDAY_GROUPS[key]:
                    add(index)
                continue
            if "-" in key:
                start_name, _, end_name = key.partition("-")
                if start_name not in WEEKDAY_NAMES or end_name not in WEEKDAY_NAMES:
                    raise UptimeError(f"Invalid weekday range '{token}'.")
                index = WEEKDAY_NAMES[start_name]
                end = WEEKDAY_NAMES[end_name]
                while True:  # Ranges wrap around the week: 'fri-mon' works
                    add(index)
                    if index == end:
                        break
                    index = (index + 1) % 7
                continue
            if key not in WEEKDAY_NAMES:
                raise UptimeError(
                    f"Invalid weekday '{token}'. Use sun..sat, a range like mon-fri, "
                    f"or a group like weekdays/weekend/all."
                )
            add(WEEKDAY_NAMES[key])

    return sorted(selected)


def parse_days_of_month(values: Sequence[str]) -> List[Any]:
    """Parse day-of-month selectors: '1', '15', ranges like '1-3', or 'last'."""
    selected: List[Any] = []

    def add(day: Any) -> None:
        if day not in selected:
            selected.append(day)

    def add_number(token: str) -> None:
        if not token.isdigit() or not 1 <= int(token) <= 31:
            raise UptimeError(f"Invalid day of month '{token}'. Use 1-31 or 'last'.")
        add(int(token))

    for raw in values:
        for token in str(raw).replace(" ", "").split(","):
            if not token:
                continue
            if token.lower() in ("last", "lastday", "lastday1"):
                add("lastDay1")
                continue
            if "-" in token:
                start_text, _, end_text = token.partition("-")
                add_number(start_text)
                add_number(end_text)
                for day in range(int(start_text), int(end_text) + 1):
                    add(day)
                continue
            add_number(token)

    numbers = sorted(day for day in selected if isinstance(day, int))
    return numbers + [day for day in selected if not isinstance(day, int)]


def format_weekdays(weekdays: Sequence[Any]) -> str:
    """Render the weekday indexes of a maintenance for a table cell."""
    labels = []
    for day in weekdays or []:
        try:
            labels.append(WEEKDAY_LABELS[int(day)])
        except (ValueError, TypeError, IndexError):
            labels.append(str(day))
    return ", ".join(labels)


def format_time_range(time_range: Sequence[Dict[str, Any]]) -> str:
    """Render the daily time window of a maintenance as 'HH:MM-HH:MM'."""
    if not time_range or len(time_range) < 2:
        return ""

    def render(entry: Any) -> str:
        if not isinstance(entry, dict):
            return str(entry)
        return f"{int(entry.get('hours', 0)):02d}:{int(entry.get('minutes', 0)):02d}"

    return f"{render(time_range[0])}-{render(time_range[1])}"


def format_api_datetime(value: datetime) -> str:
    """Render a datetime the way Uptime Kuma stores it: local time, no offset."""
    return value.replace(tzinfo=None, microsecond=0).strftime(API_DATETIME_FORMAT)


def enum_value(value: Any) -> Any:
    """Unwrap the enum members the API returns (MonitorType, strategy, ...)."""
    return getattr(value, "value", value)


def status_name(value: Any) -> str:
    """Name of a heartbeat status code."""
    if isinstance(value, bool) or value is None:
        return ""
    try:
        return MONITOR_STATUS_NAMES.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(enum_value(value))


class UptimeClient:
    """Client for a single Uptime Kuma instance.

    The connection is opened on first use and must be closed again, because
    the Socket.IO client keeps a background thread alive. Use it as a context
    manager: `with UptimeClient(cfg) as client: ...`.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Args:
            config: Context section with 'url' and credentials - either
                'username' plus 'password', or 'token' from a previous login.
        """
        self.config = config
        url = (config.get("url") or config.get("host") or "").strip()
        if not url:
            raise UptimeError("No 'url' configured for this Uptime Kuma context.")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        self.url = url.rstrip("/")

        # The Socket.IO handshake is an HTTP request, so the IPv4 workaround
        # applies here as well.
        apply_force_ipv4(config)

        self.verify = not config_flag(config, "skip_tls_verify")
        try:
            self.timeout = int(str(config.get("timeout", DEFAULT_TIMEOUT)).strip())
        except ValueError:
            self.timeout = DEFAULT_TIMEOUT

        self.username = (config.get("username") or config.get("user") or "").strip()
        self.password = (config.get("password") or "").strip()
        self.token = (config.get("token") or "").strip()
        self.mfa_token = (config.get("mfa_token") or config.get("two_factor_token") or "").strip()

        if not self.token and not (self.username and self.password):
            raise UptimeError(
                "No Uptime Kuma credentials configured. Set 'username' and "
                "'password', or a 'token' from a previous login."
            )

        self.api = None
        # Major version of the server, read once on the first write.
        self._server_major: Optional[int] = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Open the Socket.IO connection and log in."""
        if self.api is not None:
            return
        try:
            from uptime_kuma_api import UptimeKumaApi, UptimeKumaException
        except ImportError as exc:
            raise UptimeError(
                "The 'uptime-kuma-api' package is required for the uptime module. "
                "Install it with: pip install uptime-kuma-api"
            ) from exc

        logger.debug("Connecting to Uptime Kuma at %s", self.url)
        try:
            api = UptimeKumaApi(self.url, timeout=self.timeout, ssl_verify=self.verify)
        except Exception as exc:  # socket.io raises its own connection errors
            raise UptimeError(f"Uptime Kuma not reachable at {self.url}: {exc}") from exc

        try:
            if self.token:
                api.login_by_token(self.token)
            else:
                api.login(self.username, self.password, self.mfa_token)
        except UptimeKumaException as exc:
            api.disconnect()
            raise UptimeError(f"Login to {self.url} failed: {exc}") from exc
        except Exception as exc:
            api.disconnect()
            raise UptimeError(f"Login to {self.url} failed: {exc}") from exc

        self.api = api

    def close(self) -> None:
        """Close the connection and its background thread."""
        if self.api is None:
            return
        try:
            self.api.disconnect()
        except Exception as exc:  # A failing disconnect must not mask a result
            logger.debug("Ignoring error while disconnecting: %s", exc)
        finally:
            self.api = None

    def __enter__(self) -> "UptimeClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _call(self, method: str, /, *args, **kwargs) -> Any:
        """Call an API method and normalise its errors.

        The method name is positional-only: the payloads passed through here
        carry API fields such as 'name' and 'type', which would otherwise
        collide with this method's own parameters.
        """
        self.connect()
        try:
            return getattr(self.api, method)(*args, **kwargs)
        except Exception as exc:
            logger.debug("Uptime Kuma %s failed: %s", method, exc)
            raise UptimeError(
                f"Uptime Kuma error on {method}: {explain_error(exc)}"
            ) from exc

    # ------------------------------------------------------------------
    # Server compatibility
    #
    # uptime-kuma-api speaks the protocol of Uptime Kuma 1.23. Version 2.x
    # kept the protocol but added database columns that must not be NULL, so
    # a monitor written by the unmodified library is rejected by the backend.
    # The payload is therefore built with the library and completed here.
    # ------------------------------------------------------------------
    def server_major(self) -> int:
        """Major version of the server, 0 when it cannot be determined."""
        if self._server_major is None:
            version = str(self.info().get("version") or "")
            match = re.match(r"(\d+)", version.strip())
            self._server_major = int(match.group(1)) if match else 0
            logger.debug("Uptime Kuma server version: %s", version or "unknown")
        return self._server_major

    def _write_monitor(self, event: str, changes: Dict[str, Any],
                       base: Optional[Dict[str, Any]], label: str) -> Any:
        """Build a monitor payload the library's way and send it to a 2.x server.

        Args:
            event: Socket event, 'add' or 'editMonitor'
            changes: The fields given on the command line
            base: The stored monitor for an edit, None when creating
            label: Name of the operation for error messages
        """
        self.connect()
        try:
            from uptime_kuma_api import Event
            from uptime_kuma_api.api import (
                _check_arguments_monitor,
                _convert_monitor_input,
            )

            if base is None:
                data = self.api._build_monitor_data(**changes)
            else:
                data = dict(base)
                data.update(changes)
            _convert_monitor_input(data)
            _check_arguments_monitor(data)
            data.update(SERVER_2X_MONITOR_FIELDS)

            with self.api.wait_for_event(Event.MONITOR_LIST):
                return self.api._call(event, data)
        except KeyError as exc:
            # The library expects every monitor field to be present; a server
            # that does not send one lands here as a bare key name.
            logger.debug("Monitor payload incomplete: %s", exc)
            raise UptimeError(
                f"Uptime Kuma error on {label}: the monitor data from the server "
                f"does not contain the field {exc}, which this client expects. "
                f"The server version and the installed 'uptime-kuma-api' do not "
                f"match."
            ) from exc
        except (ImportError, AttributeError) as exc:
            # The library's internals moved: say so instead of failing obscurely.
            logger.debug("Monitor compatibility path unavailable: %s", exc)
            raise UptimeError(
                f"Cannot write monitors on Uptime Kuma {self.server_major()}.x "
                f"with the installed 'uptime-kuma-api': {exc}"
            ) from exc
        except Exception as exc:
            logger.debug("Uptime Kuma %s failed: %s", label, exc)
            raise UptimeError(
                f"Uptime Kuma error on {label}: {explain_error(exc)}"
            ) from exc

    # ------------------------------------------------------------------
    # Instance information
    # ------------------------------------------------------------------
    def info(self) -> Dict[str, Any]:
        """Version and configuration of the instance."""
        data = self._call("info")
        return data if isinstance(data, dict) else {}

    def uptime(self) -> Dict[str, Any]:
        """Uptime percentages per monitor, keyed by monitor ID."""
        data = self._call("uptime")
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Monitors
    # ------------------------------------------------------------------
    def list_monitors(self) -> List[Dict[str, Any]]:
        data = self._call("get_monitors")
        return data if isinstance(data, list) else []

    def get_monitor(self, monitor_id: int) -> Dict[str, Any]:
        data = self._call("get_monitor", monitor_id)
        return data if isinstance(data, dict) else {}

    def heartbeats(self) -> Dict[Any, List[Dict[str, Any]]]:
        """Recent heartbeats of every monitor, keyed by monitor ID."""
        data = self._call("get_heartbeats")
        return data if isinstance(data, dict) else {}

    def monitor_beats(self, monitor_id: int, hours: int = 24) -> List[Dict[str, Any]]:
        data = self._call("get_monitor_beats", monitor_id, hours)
        return data if isinstance(data, list) else []

    def add_monitor(self, **kwargs: Any) -> int:
        """Create a monitor and return its ID."""
        if self.server_major() >= 2:
            response = self._write_monitor("add", kwargs, None, "add_monitor")
        else:
            response = self._call("add_monitor", **kwargs)
        monitor_id = (response or {}).get("monitorID")
        if monitor_id is None:
            raise UptimeError("Unexpected response while creating the monitor.")
        return int(monitor_id)

    def edit_monitor(self, monitor_id: int, **kwargs: Any) -> Dict[str, Any]:
        if self.server_major() >= 2:
            # Like the library's own edit: read the monitor, apply the changes.
            base = self.get_monitor(monitor_id)
            return self._write_monitor("editMonitor", kwargs, base, "edit_monitor") or {}
        return self._call("edit_monitor", monitor_id, **kwargs) or {}

    def delete_monitor(self, monitor_id: int) -> None:
        self._call("delete_monitor", monitor_id)

    def pause_monitor(self, monitor_id: int) -> None:
        self._call("pause_monitor", monitor_id)

    def resume_monitor(self, monitor_id: int) -> None:
        self._call("resume_monitor", monitor_id)

    def add_monitor_tag(self, tag_id: int, monitor_id: int, value: str = "") -> None:
        self._call("add_monitor_tag", tag_id, monitor_id, value)

    # ------------------------------------------------------------------
    # Maintenance windows
    # ------------------------------------------------------------------
    def list_maintenances(self) -> List[Dict[str, Any]]:
        data = self._call("get_maintenances")
        return data if isinstance(data, list) else []

    def get_maintenance(self, maintenance_id: int) -> Dict[str, Any]:
        data = self._call("get_maintenance", maintenance_id)
        return data if isinstance(data, dict) else {}

    def maintenance_monitors(self, maintenance_id: int) -> List[Dict[str, Any]]:
        data = self._call("get_monitor_maintenance", maintenance_id)
        return data if isinstance(data, list) else []

    def maintenance_status_pages(self, maintenance_id: int) -> List[Dict[str, Any]]:
        data = self._call("get_status_page_maintenance", maintenance_id)
        return data if isinstance(data, list) else []

    def add_maintenance(self, **kwargs: Any) -> int:
        """Create a maintenance window and return its ID."""
        response = self._call("add_maintenance", **kwargs)
        maintenance_id = (response or {}).get("maintenanceID")
        if maintenance_id is None:
            raise UptimeError("Unexpected response while creating the maintenance.")
        return int(maintenance_id)

    def edit_maintenance(self, maintenance_id: int, **kwargs: Any) -> Dict[str, Any]:
        return self._call("edit_maintenance", maintenance_id, **kwargs) or {}

    def set_maintenance_monitors(
        self, maintenance_id: int, monitors: Sequence[Dict[str, Any]]
    ) -> None:
        """Attach monitors to a maintenance (replaces the current selection)."""
        payload = [
            {"id": monitor.get("id"), "name": monitor.get("name", "")}
            for monitor in monitors
        ]
        self._call("add_monitor_maintenance", maintenance_id, payload)

    def set_maintenance_status_pages(
        self, maintenance_id: int, status_pages: Sequence[Dict[str, Any]]
    ) -> None:
        """Attach status pages to a maintenance (replaces the current selection)."""
        payload = [
            {"id": page.get("id"), "title": page.get("title", "")}
            for page in status_pages
        ]
        self._call("add_status_page_maintenance", maintenance_id, payload)

    def pause_maintenance(self, maintenance_id: int) -> None:
        self._call("pause_maintenance", maintenance_id)

    def resume_maintenance(self, maintenance_id: int) -> None:
        self._call("resume_maintenance", maintenance_id)

    def delete_maintenance(self, maintenance_id: int) -> None:
        self._call("delete_maintenance", maintenance_id)

    # ------------------------------------------------------------------
    # Supporting objects
    # ------------------------------------------------------------------
    def list_notifications(self) -> List[Dict[str, Any]]:
        data = self._call("get_notifications")
        return data if isinstance(data, list) else []

    def list_tags(self) -> List[Dict[str, Any]]:
        data = self._call("get_tags")
        return data if isinstance(data, list) else []

    def list_status_pages(self) -> List[Dict[str, Any]]:
        data = self._call("get_status_pages")
        return data if isinstance(data, list) else []

    # ------------------------------------------------------------------
    # Name resolution
    # ------------------------------------------------------------------
    @staticmethod
    def _match_by_name(
        items: List[Dict[str, Any]], value: str, label: str, key: str = "name"
    ) -> Dict[str, Any]:
        """Find exactly one item by name: exact match wins, else unique substring."""
        wanted = str(value).strip().lower()
        exact = [i for i in items if str(i.get(key, "")).strip().lower() == wanted]
        candidates = exact or [
            i for i in items if wanted in str(i.get(key, "")).strip().lower()
        ]

        if not candidates:
            raise UptimeError(f"No {label} found matching '{value}'.")
        if len(candidates) > 1:
            names = ", ".join(
                f"{c.get(key)} (ID {c.get('id')})" for c in candidates[:10]
            )
            raise UptimeError(
                f"'{value}' matches several {label}s: {names}. "
                f"Use the numeric ID or a more specific name."
            )
        return candidates[0]

    def resolve_monitor(self, value: Union[str, int]) -> Dict[str, Any]:
        """Resolve a monitor ID or name to the monitor object."""
        if str(value).isdigit():
            monitor = self.get_monitor(int(value))
            if not monitor:
                raise UptimeError(f"No monitor with ID {value}.")
            return monitor
        return self._match_by_name(self.list_monitors(), str(value), "monitor")

    def resolve_monitors(self, values: Sequence[Union[str, int]]) -> List[Dict[str, Any]]:
        """Resolve several monitor IDs or names, keeping the order and dropping duplicates."""
        resolved: List[Dict[str, Any]] = []
        for value in values:
            monitor = self.resolve_monitor(value)
            if not any(m.get("id") == monitor.get("id") for m in resolved):
                resolved.append(monitor)
        return resolved

    def resolve_maintenance(self, value: Union[str, int]) -> Dict[str, Any]:
        """Resolve a maintenance ID or title to the maintenance object."""
        if str(value).isdigit():
            maintenance = self.get_maintenance(int(value))
            if not maintenance:
                raise UptimeError(f"No maintenance with ID {value}.")
            return maintenance
        return self._match_by_name(
            self.list_maintenances(), str(value), "maintenance", key="title"
        )

    def resolve_notifications(self, values: Sequence[Union[str, int]]) -> List[int]:
        """Resolve notification IDs or names to a list of IDs."""
        notifications = None
        resolved: List[int] = []
        for value in values:
            if str(value).isdigit():
                identifier = int(value)
            else:
                if notifications is None:
                    notifications = self.list_notifications()
                identifier = int(
                    self._match_by_name(notifications, str(value), "notification")["id"]
                )
            if identifier not in resolved:
                resolved.append(identifier)
        return resolved

    def resolve_tags(self, values: Sequence[Union[str, int]]) -> List[Dict[str, Any]]:
        """Resolve tag IDs or names to tag objects."""
        tags = None
        resolved: List[Dict[str, Any]] = []
        for value in values:
            if str(value).isdigit():
                tag: Dict[str, Any] = {"id": int(value), "name": str(value)}
            else:
                if tags is None:
                    tags = self.list_tags()
                tag = self._match_by_name(tags, str(value), "tag")
            if not any(t.get("id") == tag.get("id") for t in resolved):
                resolved.append(tag)
        return resolved

    def resolve_status_pages(self, values: Sequence[Union[str, int]]) -> List[Dict[str, Any]]:
        """Resolve status page IDs, slugs or titles to status page objects."""
        pages = self.list_status_pages()
        resolved: List[Dict[str, Any]] = []
        for value in values:
            text = str(value).strip()
            match = None
            if text.isdigit():
                match = next((p for p in pages if str(p.get("id")) == text), None)
                if match is None:
                    raise UptimeError(f"No status page with ID {text}.")
            else:
                match = next(
                    (p for p in pages if str(p.get("slug", "")).lower() == text.lower()),
                    None,
                )
            if match is None:
                match = self._match_by_name(pages, text, "status page", key="title")
            if not any(p.get("id") == match.get("id") for p in resolved):
                resolved.append(match)
        return resolved
