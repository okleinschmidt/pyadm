def first_value(attr_dict, key):
    """Return the first value for a key in an LDAP attribute dict (case-insensitive)."""
    values = attr_dict.get(key)
    if values is None:
        for attr_key, attr_values in attr_dict.items():
            if attr_key.lower() == key.lower():
                values = attr_values
                break
    if not values:
        return None
    if isinstance(values, list):
        return str(values[0]) if values else None
    return str(values)


def stringify_attrs(attr_dict):
    """Convert an LDAP attribute dict to a JSON-serialisable dict of string lists."""
    return {str(k): [str(v) for v in vals] for k, vals in attr_dict.items()}


def resolve_group_dn(ldap_client, group):
    """Resolve a group CN or full DN to its DN. Returns None if not found."""
    if "dc=" in group.lower() and "," in group:
        return group
    group_result = ldap_client.get_group(group)
    if not group_result:
        return None
    return group_result[0].entry_dn


def resolve_user_dn(ldap_client, user):
    """Resolve a user CN/UID/mail or full DN to its DN. Returns None if not found."""
    if "dc=" in user.lower():
        return user
    user_result = ldap_client.get_user(user)
    if not user_result:
        return None
    return user_result[0].entry_dn
