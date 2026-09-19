"""Shared network helpers for the pyadm modules."""

import logging
import socket
from typing import Any, Mapping

import urllib3.util.connection as urllib3_connection

logger = logging.getLogger(__name__)

TRUTHY_VALUES = {"1", "true", "yes", "on"}

# Original resolver family callback, kept so the patch stays idempotent.
_DEFAULT_ALLOWED_GAI_FAMILY = urllib3_connection.allowed_gai_family


def config_flag(config: Mapping[str, Any], key: str, default: bool = False) -> bool:
    """Read a boolean flag from a config section."""
    value = config.get(key)
    if value is None:
        return default
    return str(value).strip().lower() in TRUTHY_VALUES


def force_ipv4_enabled(config: Mapping[str, Any]) -> bool:
    """Return True if the config section asks for IPv4-only connections."""
    return config_flag(config, "force_ipv4")


def apply_force_ipv4(config: Mapping[str, Any]) -> bool:
    """
    Restrict urllib3-based clients (requests, proxmoxer, elasticsearch,
    opensearch) to IPv4 when 'force_ipv4' is set in the config section.

    A host whose AAAA record points to an unreachable address costs one full
    connect timeout per TCP connection: urllib3 walks the getaddrinfo results
    strictly in order instead of racing them the way Happy Eyeballs does, so
    every new connection blocks on the dead IPv6 address before falling back
    to IPv4.

    Args:
        config: Configuration dictionary of the active context

    Returns:
        True if IPv4-only mode was enabled, False otherwise
    """
    if not force_ipv4_enabled(config):
        return False

    urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
    logger.debug("force_ipv4 is set: restricting connections to IPv4")
    return True


def reset_force_ipv4() -> None:
    """Restore the default address family selection (mainly for tests)."""
    urllib3_connection.allowed_gai_family = _DEFAULT_ALLOWED_GAI_FAMILY
