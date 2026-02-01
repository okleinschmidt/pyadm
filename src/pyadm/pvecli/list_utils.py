from typing import Any, Dict, Iterable, List, Optional, Tuple


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
