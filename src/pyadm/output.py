"""Shared output helpers: opt-in colouring of status values."""

import os
from typing import Any, Mapping, Optional

import click

from pyadm.config import cluster_config
from pyadm.net_utils import config_flag

# Resolved once per invocation by init_colors().
_colors_enabled = False

# Cluster/guest states mapped to a colour. States not listed stay unstyled,
# so an unexpected value is never dressed up as if it were understood.
CLUSTER_STATUS_COLORS = {
    "green": "green",
    "yellow": "yellow",
    "red": "red",
}

GUEST_STATUS_COLORS = {
    "running": "green",
    "online": "green",
    "paused": "yellow",
    "suspended": "yellow",
    "prelaunch": "yellow",
    "stopped": "red",
    "offline": "red",
    "unknown": "red",
}

# Shared thresholds for "how full is it" values: shard budget, CPU, memory, disk.
# One pair of numbers everywhere, so the same colour always means the same thing.
DEFAULT_WARN_PERCENT = 80.0
DEFAULT_CRIT_PERCENT = 90.0

_warn_percent = DEFAULT_WARN_PERCENT
_crit_percent = DEFAULT_CRIT_PERCENT

# Ages at which a snapshot stops looking routine and starts looking forgotten.
DEFAULT_WARN_DAYS = 7.0
DEFAULT_CRIT_DAYS = 30.0

_warn_days = DEFAULT_WARN_DAYS
_crit_days = DEFAULT_CRIT_DAYS

# Uptime Kuma heartbeat states. "maintenance" is a planned outage, so it is
# blue rather than red: nothing is wrong with the service.
MONITOR_STATUS_COLORS = {
    "up": "green",
    "down": "red",
    "pending": "yellow",
    "maintenance": "blue",
    "active": "green",
    "paused": "yellow",
}

DISK_STATE_COLORS = {
    "ok": "green",
    "low": "yellow",
    "high": "red",
    "flood": "red",
}


def _read_number(config: Optional[Mapping[str, Any]], key: str, fallback: float) -> float:
    """Read a threshold from the context section, else [GENERAL], else the default."""
    for source in (config, _general_section()):
        if not source:
            continue
        for candidate, value in source.items():
            if candidate.lower() == key:
                try:
                    return float(str(value).strip().rstrip("%"))
                except ValueError:
                    return fallback
    return fallback


def _general_section() -> Mapping[str, Any]:
    try:
        return cluster_config.get_section("GENERAL")
    except RuntimeError:
        return {}


def init_colors(config: Optional[Mapping[str, Any]] = None) -> bool:
    """
    Decide whether output should be coloured, and remember the answer.

    Colour is opt-in: 'colors' in the active context section, otherwise in a
    [GENERAL] section. NO_COLOR is honoured regardless, per https://no-color.org,
    and Click drops the escape codes by itself when output is not a terminal.

    Args:
        config: Configuration of the active context, if one is resolved

    Returns:
        True if colouring is enabled
    """
    global _colors_enabled, _warn_percent, _crit_percent, _warn_days, _crit_days

    _warn_percent = _read_number(config, "warn_percent", DEFAULT_WARN_PERCENT)
    _crit_percent = _read_number(config, "crit_percent", DEFAULT_CRIT_PERCENT)
    _warn_days = _read_number(config, "warn_days", DEFAULT_WARN_DAYS)
    _crit_days = _read_number(config, "crit_days", DEFAULT_CRIT_DAYS)

    if os.environ.get("NO_COLOR"):
        _colors_enabled = False
        return False

    if config is not None and any(k.lower() == "colors" for k in config):
        _colors_enabled = config_flag(config, "colors")
        return _colors_enabled

    _colors_enabled = config_flag(_general_section(), "colors")
    return _colors_enabled


def colors_enabled() -> bool:
    """Whether colouring is currently enabled."""
    return _colors_enabled


def style(text: Any, color: Optional[str], bold: bool = False) -> str:
    """Colour *text*, or return it unchanged when colouring is off."""
    text = str(text)
    if not _colors_enabled or not color:
        return text
    return click.style(text, fg=color, bold=bold)


def _styled_by_map(value: Any, mapping: Mapping[str, str]) -> str:
    if value is None:
        return ""
    return style(value, mapping.get(str(value).strip().lower()))


def cluster_status(value: Any) -> str:
    """Colour an Elasticsearch/OpenSearch cluster status (green/yellow/red)."""
    return _styled_by_map(value, CLUSTER_STATUS_COLORS)


def guest_status(value: Any) -> str:
    """Colour a VM, container or node status (running/paused/stopped/...)."""
    return _styled_by_map(value, GUEST_STATUS_COLORS)


def monitor_status(value: Any) -> str:
    """Colour an Uptime Kuma monitor state (up/down/pending/maintenance)."""
    return _styled_by_map(value, MONITOR_STATUS_COLORS)


def disk_state(value: Any) -> str:
    """Colour a disk watermark state (ok/low/high/flood)."""
    return _styled_by_map(value, DISK_STATE_COLORS)


def usage_color(percent: Any) -> Optional[str]:
    """Colour for a "how full" percentage: green, then yellow, then red."""
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return None
    if value >= _crit_percent:
        return "red"
    if value >= _warn_percent:
        return "yellow"
    return "green"


def usage(percent: Any, text: Optional[str] = None) -> str:
    """Render a usage percentage (or *text*) coloured by how full it is."""
    if percent is None:
        return text if text is not None else ""
    rendered = text if text is not None else f"{float(percent):.1f}%"
    return style(rendered, usage_color(percent))


def age_color(days: Any) -> Optional[str]:
    """Colour for an age in days: unremarkable, then yellow, then red."""
    try:
        value = float(days)
    except (TypeError, ValueError):
        return None
    if value >= _crit_days:
        return "red"
    if value >= _warn_days:
        return "yellow"
    return None


def age(days: Any, text: Optional[str] = None) -> str:
    """Render an age in days (or *text*) coloured by how stale it is."""
    if days is None:
        return text if text is not None else ""
    rendered = text if text is not None else f"{float(days):.0f}d"
    return style(rendered, age_color(days))


def thresholds() -> tuple:
    """The warn/crit percentages currently in force."""
    return (_warn_percent, _crit_percent)
