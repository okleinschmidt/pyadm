import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
import tabulate as tabulate_module

from pyadm.output import age, guest_status, style, usage
from pyadm.table import render_table


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
    return render_table(table_data, fields)


# Proxmox reports the live state of a guest as a pseudo-snapshot with this name.
CURRENT_SNAPSHOT = "current"


def format_age(seconds: float) -> str:
    """Render an age as the two most significant units (e.g. '3d 4h', '12m')."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    days, hours = seconds // 86400, (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def build_snapshot_tree(snapshots: Iterable[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
    """Order snapshots as a depth-first tree, following their 'parent' links.

    Args:
        snapshots: Snapshot dicts as returned by the PVE API

    Returns:
        List of (depth, snapshot) pairs in display order
    """
    items = list(snapshots)
    known = {s.get("name") for s in items}
    children: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for snap in items:
        parent = snap.get("parent")
        # A parent that is not in the list itself (deleted meanwhile) becomes a root
        children.setdefault(parent if parent in known else None, []).append(snap)

    for siblings in children.values():
        # Oldest first; the live state has no timestamp and always sorts last
        siblings.sort(key=lambda s: (s.get("snaptime") is None, s.get("snaptime") or 0, s.get("name") or ""))

    ordered: List[Tuple[int, Dict[str, Any]]] = []
    seen: set = set()

    def walk(name: Optional[str], depth: int) -> None:
        for snap in children.get(name, []):
            if snap.get("name") in seen:
                continue  # Guard against a cycle in the parent links
            seen.add(snap.get("name"))
            ordered.append((depth, snap))
            walk(snap.get("name"), depth + 1)

    walk(None, 0)

    # Anything left out by a cycle is still worth showing, at the root level
    for snap in items:
        if snap.get("name") not in seen:
            ordered.append((0, snap))

    return ordered


def _tree_prefix(ancestors_last: List[bool], is_last: bool) -> str:
    """Draw the branch characters leading up to a node at depth len(ancestors_last)."""
    if not ancestors_last:
        return ""
    # Ancestors that were the last of their siblings leave empty space, others a bar
    prefix = "".join("   " if last else "\u2502  " for last in ancestors_last[1:])
    return prefix + ("\u2514\u2500 " if is_last else "\u251c\u2500 ")


def _last_of_branch(ordered: List[Tuple[int, Dict[str, Any]]]) -> List[bool]:
    """For each entry, whether it is the last child of its parent."""
    flags = [True] * len(ordered)
    for index, (depth, _) in enumerate(ordered):
        for next_depth, _ in ordered[index + 1:]:
            if next_depth < depth:
                break
            if next_depth == depth:
                flags[index] = False
                break
    return flags


def _snapshot_row(snap: Dict[str, Any], now: float) -> List[str]:
    """Format one snapshot as name, creation time, age, RAM flag and description."""
    name = snap.get("name") or ""
    is_current = name == CURRENT_SNAPSHOT
    label = style("NOW (current state)", "cyan") if is_current else name

    snaptime = snap.get("snaptime")
    created = datetime.fromtimestamp(snaptime).strftime("%Y-%m-%d %H:%M") if snaptime else ""
    age_text = age((now - snaptime) / 86400, format_age(now - snaptime)) if snaptime else ""
    # A snapshot with vmstate also captured the RAM, so rolling back resumes mid-run
    ram = style("yes", "yellow") if snap.get("vmstate") else ""

    lines = (snap.get("description") or "").strip().splitlines()
    description = lines[0] if lines else ""
    if len(description) > 40:
        description = description[:37] + "..."

    return [label, created, age_text, ram, description]


SNAPSHOT_HEADERS = ["name", "created", "age", "ram", "description"]


@contextmanager
def _preserve_whitespace():
    """Keep tabulate from stripping the indentation of the tree column."""
    previous = tabulate_module.PRESERVE_WHITESPACE
    tabulate_module.PRESERVE_WHITESPACE = True
    try:
        yield
    finally:
        tabulate_module.PRESERVE_WHITESPACE = previous


def _drop_ram(rows: List[List[Any]], headers: List[str], ram_index: int) -> Tuple[List[List[Any]], List[str]]:
    """Remove the RAM column, which only ever applies to QEMU guests."""
    return ([row[:ram_index] + row[ram_index + 1:] for row in rows],
            headers[:ram_index] + headers[ram_index + 1:])


def render_snapshot_tree(snapshots: Iterable[Dict[str, Any]], now: Optional[float] = None,
                         ram_column: bool = True) -> str:
    """Build a tabulated snapshot tree showing how snapshots descend from each other."""
    now = time.time() if now is None else now
    ordered = build_snapshot_tree(snapshots)
    last_flags = _last_of_branch(ordered)

    rows = []
    branch_last: List[bool] = []
    for index, (depth, snap) in enumerate(ordered):
        # Depth-first order means the current path is simply the stack trimmed to this depth
        del branch_last[depth:]
        prefix = _tree_prefix(branch_last, last_flags[index])
        branch_last.append(last_flags[index])

        row = _snapshot_row(snap, now)
        row[0] = prefix + row[0]
        rows.append(row)

    headers = SNAPSHOT_HEADERS
    if not ram_column:
        rows, headers = _drop_ram(rows, headers, SNAPSHOT_HEADERS.index("ram"))

    with _preserve_whitespace():
        return render_table(rows, headers)


def render_snapshot_table(snapshots: Iterable[Dict[str, Any]], now: Optional[float] = None,
                          ram_column: bool = True) -> str:
    """Build a flat snapshot table, with the parent shown as its own column."""
    now = time.time() if now is None else now
    rows = []
    for snap in snapshots:
        row = _snapshot_row(snap, now)
        rows.append(row[:1] + [snap.get("parent") or ""] + row[1:])

    headers = [SNAPSHOT_HEADERS[0], "parent"] + SNAPSHOT_HEADERS[1:]
    if not ram_column:
        rows, headers = _drop_ram(rows, headers, headers.index("ram"))
    return render_table(rows, headers)


def _snaptimes(snapshots: Iterable[Dict[str, Any]]) -> List[float]:
    return [s["snaptime"] for s in snapshots if s.get("snaptime")]


def oldest_snaptime(snapshots: Iterable[Dict[str, Any]]) -> Optional[float]:
    """Timestamp of the oldest snapshot, or None if none of them is dated."""
    times = _snaptimes(snapshots)
    return min(times) if times else None


def newest_snaptime(snapshots: Iterable[Dict[str, Any]]) -> Optional[float]:
    """Timestamp of the newest snapshot, or None if none of them is dated."""
    times = _snaptimes(snapshots)
    return max(times) if times else None


def _age_cell(snaptime: Optional[float], now: float) -> str:
    if not snaptime:
        return ""
    elapsed = now - snaptime
    return age(elapsed / 86400, format_age(elapsed))


OVERVIEW_HEADERS = ["vmid", "name", "node", "status", "snaps", "oldest", "newest", "ram", "snapshot names"]


def render_snapshot_overview(entries: Iterable[Dict[str, Any]], now: Optional[float] = None,
                             ram_column: bool = True) -> str:
    """Build the cluster-wide table: one row per VM that has snapshots.

    Args:
        entries: Dicts with the VM fields plus a 'snapshots' list
        now: Reference time for the age columns (defaults to the current time)
        ram_column: Show the memory-state column (QEMU guests only)
    """
    now = time.time() if now is None else now

    rows = []
    for entry in entries:
        snapshots = entry.get("snapshots") or []
        names = ", ".join(s.get("name", "") for s in snapshots)
        if len(names) > 45:
            names = names[:42] + "..."
        name = entry.get("name") or ""
        if entry.get("template"):
            name = f"{name} (template)"
        rows.append([
            entry.get("vmid"),
            name,
            entry.get("node"),
            guest_status(entry.get("status")),
            len(snapshots),
            _age_cell(oldest_snaptime(snapshots), now),
            _age_cell(newest_snaptime(snapshots), now),
            # Memory state makes a snapshot far more expensive to keep lying around
            style("yes", "yellow") if any(s.get("vmstate") for s in snapshots) else "",
            names,
        ])

    headers = OVERVIEW_HEADERS
    if not ram_column:
        rows, headers = _drop_ram(rows, headers, OVERVIEW_HEADERS.index("ram"))
    return render_table(rows, headers)
