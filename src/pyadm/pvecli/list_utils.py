from typing import Any, Dict, Iterable, List, Optional, Tuple
from tabulate import tabulate

from pyadm.output import guest_status, usage


class SortError(ValueError):
    pass


def _sort_key(value: Any) -> Tuple[int, Any]:
    if value is None:
        return (2, "")
    if isinstance(value, bool):
        return (0, int(value))
    if isinstance(value, (int, float)):
        return (0, value)
    if isinstance(value, str):
        return (1, value.lower())
    return (1, str(value).lower())


def _parse_sort_fields(sort_by: str) -> List[Tuple[str, bool]]:
    parts = [p.strip() for p in sort_by.split(",") if p.strip()]
    if not parts:
        raise SortError("Sort fields cannot be empty.")
    fields: List[Tuple[str, bool]] = []
    for part in parts:
        reverse = False
        if part[0] in ("-", "+"):
            reverse = part[0] == "-"
            part = part[1:]
        if not part:
            raise SortError("Invalid sort field.")
        fields.append((part, reverse))
    return fields


def sort_items(
    items: Iterable[Dict[str, Any]],
    sort_by: Optional[str],
    allowed_fields: Optional[Iterable[str]] = None,
    field_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    if not sort_by:
        return list(items)

    parsed = _parse_sort_fields(sort_by)
    allowed = {f.lower() for f in allowed_fields} if allowed_fields else None
    normalized_map = {k.lower(): v for k, v in (field_map or {}).items()}

    sorted_items = list(items)
    for field, reverse in reversed(parsed):
        field_key = field.lower()
        if allowed is not None and field_key not in allowed:
            raise SortError(f"Invalid sort field '{field}'. Allowed: {', '.join(sorted(allowed))}")
        mapped = normalized_map.get(field_key, field)
        sorted_items = sorted(
            sorted_items,
            key=lambda item: _sort_key(item.get(mapped)),
            reverse=reverse,
        )

    return sorted_items


# Fields that are "some amount of a maximum", mapped to the field holding that
# maximum. They are rendered as "used (NN%)" and coloured by how full they are.
USAGE_FIELDS = {
    'mem': 'maxmem',
    'disk': 'maxdisk',
}


def format_uptime(seconds: float) -> str:
    """Render an uptime in days/hours/minutes rather than a long hour count."""
    seconds = int(seconds)
    days, hours = seconds // 86400, (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    return f"{days}d {hours}h" if days else f"{hours}h {minutes}m"


def format_bytes(value: int, unit: str = "GB") -> str:
    """Render a byte count in GB (default) or MB."""
    if unit == "MB":
        return f"{value / (1024**2):.0f} MB"
    return f"{value / (1024**3):.2f} GB"


def render_resource_table(items, default_fields, output=None, mem_unit="GB"):
    """Build and return a tabulated string for a list of PVE resource dicts.

    Args:
        items: Iterable of resource dicts (VMs, containers, …)
        default_fields: Field list used when *output* is not specified
        output: Optional comma-separated field override string
        mem_unit: "GB" (default) or "MB" for maxmem formatting
    """
    fields = output.split(',') if output else default_fields
    table_data = []
    for item in items:
        row = []
        for field in fields:
            if field in item:
                value = item[field]
                if field in ('maxmem', 'maxdisk') and isinstance(value, int):
                    row.append(format_bytes(value, mem_unit if field == 'maxmem' else "GB"))
                elif field == 'uptime' and isinstance(value, (int, float)):
                    row.append(format_uptime(value))
                elif field == 'cpu' and isinstance(value, (int, float)):
                    # The API reports CPU usage as a 0..1 fraction, not a percentage
                    row.append(usage(value * 100))
                elif field in USAGE_FIELDS and isinstance(value, int):
                    # Show how much of the matching maximum is in use, not just the raw size
                    maximum = item.get(USAGE_FIELDS[field])
                    percent = (value / maximum * 100) if maximum else None
                    text = format_bytes(value, mem_unit)
                    if percent is not None:
                        text = f"{text} ({percent:.0f}%)"
                    row.append(usage(percent, text))
                elif field == 'status':
                    row.append(guest_status(value))
                else:
                    row.append(value)
            else:
                row.append("")
        table_data.append(row)
    return tabulate(table_data, headers=fields)
