"""Shared rendering of list output.

Every module lists things - VMs, indices, timesheet entries - and they should
all look the same. The house style is tabulate's default "simple" format with
lower-case headers named after the underlying fields, as `pyadm pve vm list`
has always rendered them. Keeping the format in one place means a change to it
reaches every listing at once, instead of drifting per module.
"""

import json
from typing import Any, Dict, Iterable, List, Optional, Sequence

import click
from tabulate import tabulate

# tabulate's default format: a header row underlined with dashes, no borders.
# Narrow enough for a terminal, still easy to feed into awk or cut.
TABLE_FORMAT = "simple"


def render_table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    """Render *rows* in the house style and return it as a string."""
    return tabulate(rows, headers=[str(header) for header in headers], tablefmt=TABLE_FORMAT)


def echo_table(
    rows: Sequence[Sequence[Any]],
    headers: Sequence[str],
    empty: str = "No entries found.",
) -> None:
    """Print a table, or *empty* when there is nothing to show."""
    if not rows:
        click.echo(empty)
        return
    click.echo(render_table(rows, headers))


def echo_json(data: Any) -> None:
    """Print data as JSON, the machine-readable counterpart of every listing."""
    click.echo(json.dumps(data, indent=2, default=str))


def select_fields(fields: Optional[str], defaults: Sequence[str]) -> List[str]:
    """Resolve the -o/--output field list against a command's default columns."""
    if not fields:
        return list(defaults)
    selected = [field.strip() for field in fields.split(",") if field.strip()]
    return selected or list(defaults)


def rows_from(items: Iterable[Dict[str, Any]], fields: Sequence[str]) -> List[List[Any]]:
    """Build table rows from dicts, leaving fields an item does not carry empty."""
    return [[item.get(field, "") for field in fields] for item in items]
