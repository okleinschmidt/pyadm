import logging
import ssl
from typing import Any, Dict, List, Optional
import ldap3
from ldap3.core.exceptions import LDAPException

from pyadm.net_utils import config_flag, force_ipv4_enabled

class LDAPClient:
    """
    Wrapper class for LDAP operations.
    """

    def user_exists(self, username: str) -> bool:
        """
        Check if a user exists by UID, CN, or MAIL.

        Args:
            username (str): Username (UID, CN, or MAIL).

        Returns:
            bool: True if user exists, False otherwise.
        """
        try:
            return bool(self.get_user(username))
        except Exception:
            return False

    def group_exists(self, group_cn: str) -> bool:
        """
        Check if a group exists by CN.

        Args:
            group_cn (str): Group CN.

        Returns:
            bool: True if group exists, False otherwise.
        """
        try:
            return bool(self.get_group(group_cn))
        except Exception:
            return False

    def add_user_to_group(self, user_dn: str, group_dn: str) -> bool:
        """
        Add a user to a group.

        Args:
            user_dn (str): Distinguished Name of the user.
            group_dn (str): Distinguished Name of the group.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            result = self.conn.modify(group_dn, {'member': [(ldap3.MODIFY_ADD, [user_dn])]})
            if not result:
                # Log LDAP error details
                if hasattr(self.conn, 'result') and self.conn.result:
                    logging.error(f"LDAP modify failed: {self.conn.result.get('description', 'Unknown error')}")
                    logging.error(f"LDAP result code: {self.conn.result.get('result', 'Unknown')}")
                else:
                    logging.error("LDAP modify operation returned False without detailed error info")
            return result
        except Exception as e:
            logging.error(f"Failed to add user '{user_dn}' to group '{group_dn}': {e}")
            if hasattr(self.conn, 'result') and self.conn.result:
                logging.error(f"LDAP error details: {self.conn.result}")
            return False

    def remove_user_from_group(self, user_dn: str, group_dn: str) -> bool:
        """
        Remove a user from a group.

        Args:
            user_dn (str): Distinguished Name of the user.
            group_dn (str): Distinguished Name of the group.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            result = self.conn.modify(group_dn, {'member': [(ldap3.MODIFY_DELETE, [user_dn])]})
            if not result:
                # Log LDAP error details
                if hasattr(self.conn, 'result') and self.conn.result:
                    logging.error(f"LDAP modify failed: {self.conn.result.get('description', 'Unknown error')}")
                    logging.error(f"LDAP result code: {self.conn.result.get('result', 'Unknown')}")
                else:
                    logging.error("LDAP modify operation returned False without detailed error info")
            return result
        except Exception as e:
            logging.error(f"Failed to remove user '{user_dn}' from group '{group_dn}': {e}")
            if hasattr(self.conn, 'result') and self.conn.result:
                logging.error(f"LDAP error details: {self.conn.result}")
            return False

    def set_user_password(self, user_dn: str, new_password: str) -> bool:
        """
        Set a new password for a user.

        Args:
            user_dn (str): Distinguished Name of the user.
            new_password (str): New password.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            return self.conn.extend.standard.modify_password(user_dn, new_password=new_password)
        except Exception as e:
            logging.error(f"Failed to set user password: {e}")
            return False

    def _rdn_of(self, dn: str) -> str:
        """Return the leftmost RDN component of a DN."""
        return ldap3.utils.dn.parse_dn(dn)[0][0] + "=" + ldap3.utils.dn.parse_dn(dn)[0][1]

    def _log_failure(self, action: str) -> None:
        """Log the server's own explanation for the last failed operation."""
        result = getattr(self.conn, "result", None) or {}
        logging.error(
            f"{action} failed: {result.get('description', 'unknown error')} "
            f"(code {result.get('result', '?')}) {result.get('message', '')}".strip()
        )

    def _move_entry(self, dn: str, target_ou: str) -> bool:
        """Move an entry to another container, keeping its RDN."""
        try:
            if not self.conn.modify_dn(dn, self._rdn_of(dn), new_superior=target_ou):
                self._log_failure(f"Moving '{dn}' to '{target_ou}'")
                return False
            return True
        except Exception as e:
            logging.error(f"Failed to move '{dn}' to '{target_ou}': {e}")
            return False

    def move_user(self, user_dn: str, target_ou: str) -> bool:
        """
        Move a user entry into another OU/container.

        Args:
            user_dn (str): Distinguished Name of the user.
            target_ou (str): DN of the target container.

        Returns:
            bool: True on success, False otherwise.
        """
        return self._move_entry(user_dn, target_ou)

    def move_group(self, group_dn: str, target_ou: str) -> bool:
        """
        Move a group entry into another OU/container.

        Args:
            group_dn (str): Distinguished Name of the group.
            target_ou (str): DN of the target container.

        Returns:
            bool: True on success, False otherwise.
        """
        return self._move_entry(group_dn, target_ou)

    def rename_group(self, group_dn: str, new_cn: str) -> bool:
        """
        Rename a group by changing its CN.

        Args:
            group_dn (str): Distinguished Name of the group.
            new_cn (str): New common name.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            if not self.conn.modify_dn(group_dn, f"cn={new_cn}"):
                self._log_failure(f"Renaming '{group_dn}' to '{new_cn}'")
                return False
            return True
        except Exception as e:
            logging.error(f"Failed to rename '{group_dn}' to '{new_cn}': {e}")
            return False

    def delete_group(self, group_dn: str) -> bool:
        """
        Delete a group entry.

        Args:
            group_dn (str): Distinguished Name of the group.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            if not self.conn.delete(group_dn):
                self._log_failure(f"Deleting '{group_dn}'")
                return False
            return True
        except Exception as e:
            logging.error(f"Failed to delete '{group_dn}': {e}")
            return False

    def _group_container(self) -> str:
        """Container new groups are created in: 'group_base_dn', else 'base_dn'."""
        return self.config.get("group_base_dn") or self.config["base_dn"]

    def _group_object_classes(self) -> List[str]:
        """Object classes for new groups, from 'group_object_class'."""
        configured = self.config.get("group_object_class")
        if configured:
            return [c.strip() for c in configured.split(",") if c.strip()]
        return ["top", "groupOfNames"]

    def _next_posix_id(self, object_class: str, attribute: str, minimum: int) -> int:
        """Pick the next free numeric id for schemas that require a unique one."""
        highest = 0
        for entry in self.search(f"(objectClass={object_class})", [attribute]):
            values = entry.entry_attributes_as_dict.get(attribute) or []
            for value in values:
                try:
                    highest = max(highest, int(value))
                except (TypeError, ValueError):
                    continue
        return max(highest + 1, minimum)

    def _next_gid_number(self) -> int:
        """Pick the next free gidNumber, for schemas where posixGroup requires one."""
        return self._next_posix_id("posixGroup", "gidNumber", int(self.config.get("group_gid_min", 20000)))

    def _next_uid_number(self) -> int:
        """Pick the next free uidNumber, for schemas where posixAccount requires one."""
        return self._next_posix_id("posixAccount", "uidNumber", int(self.config.get("user_uid_min", 20000)))

    def create_group(self, name: str, description: Optional[str] = None) -> bool:
        """
        Create a new group.

        The container comes from 'group_base_dn' (falling back to 'base_dn') and the
        object classes from 'group_object_class' (default: top, groupOfNames). Attributes
        the chosen schema requires but cannot be guessed are filled in automatically:
        groupOfNames/groupOfUniqueNames need at least one member, so the bind account is
        seeded as the initial one, and posixGroup needs a gidNumber, so the next free one
        is used.

        Args:
            name (str): Common name of the new group.
            description (Optional[str]): Optional description.

        Returns:
            bool: True on success, False otherwise.
        """
        object_classes = self._group_object_classes()
        group_dn = f"cn={name},{self._group_container()}"
        attributes: Dict[str, Any] = {"cn": name}
        if description:
            attributes["description"] = description

        lowered = {c.lower() for c in object_classes}
        bind_dn = self.conn.user
        if "groupofnames" in lowered and bind_dn:
            attributes["member"] = [bind_dn]
        if "groupofuniquenames" in lowered and bind_dn:
            attributes["uniqueMember"] = [bind_dn]
        if "posixgroup" in lowered:
            attributes["gidNumber"] = self._next_gid_number()

        try:
            if not self.conn.add(group_dn, object_class=object_classes, attributes=attributes):
                self._log_failure(f"Creating group '{group_dn}'")
                return False
            logging.debug(f"Created group '{group_dn}' with object classes {object_classes}")
            return True
        except Exception as e:
            logging.error(f"Failed to create group '{group_dn}': {e}")
            return False

    def clone_user(self, user_dn: str, new_username: str) -> bool:
        """
        Clone a user entry under a new username in the same container.

        Identity- and state-bearing attributes are not copied: the clone gets its own
        RDN, and operational attributes the server owns are left for it to assign.

        Args:
            user_dn (str): Distinguished Name of the user to clone.
            new_username (str): Username (RDN value) of the new entry.

        Returns:
            bool: True on success, False otherwise.
        """
        source = self.get_attributes(user_dn)
        if not source:
            logging.error(f"Cannot clone '{user_dn}': entry not found or unreadable.")
            return False

        rdn_attr = ldap3.utils.dn.parse_dn(user_dn)[0][0]
        container = user_dn.split(",", 1)[1] if "," in user_dn else self.config["base_dn"]
        new_dn = f"{rdn_attr}={new_username},{container}"

        skip = {
            "objectclass", rdn_attr.lower(), "distinguishedname", "dn",
            "objectguid", "objectsid", "entryuuid", "entrydn", "entrycsn",
            "usncreated", "usnchanged", "whencreated", "whenchanged",
            "createtimestamp", "modifytimestamp", "creatorsname", "modifiersname",
            "pwdlastset", "lastlogon", "lastlogontimestamp", "logoncount",
            "badpasswordtime", "badpwdcount", "memberof", "userpassword",
            "samaccountname", "userprincipalname", "mail", "uidnumber",
        }
        attributes: Dict[str, Any] = {}
        for key, values in source.items():
            if key.lower() in skip or not values:
                continue
            attributes[key] = values
        attributes[rdn_attr] = new_username

        object_classes = [str(v) for v in (source.get("objectClass") or [])]
        if not object_classes:
            logging.error(f"Cannot clone '{user_dn}': source entry has no readable objectClass.")
            return False

        # uidNumber is skipped above because it must be unique, but posixAccount
        # requires one - so the clone gets the next free id rather than the source's.
        if any(c.lower() == "posixaccount" for c in object_classes):
            attributes["uidNumber"] = self._next_uid_number()

        try:
            if not self.conn.add(new_dn, object_class=object_classes, attributes=attributes):
                self._log_failure(f"Cloning '{user_dn}' to '{new_dn}'")
                return False
            logging.debug(f"Cloned '{user_dn}' to '{new_dn}'")
            return True
        except Exception as e:
            logging.error(f"Failed to clone '{user_dn}' to '{new_dn}': {e}")
            return False

    def is_connected(self) -> bool:
        """
        Check if the LDAP connection is alive.

        Returns:
            bool: True if connected, False otherwise.
        """
        return self.conn.bound if self.conn else False

    def reconnect(self) -> None:
        """
        Reconnect to the LDAP server.
        """
        self._connect()

    def get_attributes(self, dn: str, attributes: Optional[List[str]] = None) -> Optional[dict]:
        """
        Get attributes for a given DN.

        Args:
            dn (str): Distinguished Name.
            attributes (Optional[List[str]]): List of attributes to retrieve.

        Returns:
            Optional[dict]: Dictionary of attributes, or None if not found.
        """
        try:
            self.conn.search(dn, '(objectClass=*)', attributes=attributes or ldap3.ALL_ATTRIBUTES, search_scope=ldap3.BASE)
            if self.conn.entries:
                return self.conn.entries[0].entry_attributes_as_dict
            return None
        except Exception as e:
            logging.error(f"Failed to get attributes for {dn}: {e}")
            return None

    def set_attributes(self, dn: str, changes: dict) -> bool:
        """
        Set attributes for a given DN.

        Args:
            dn (str): Distinguished Name.
            changes (dict): Dictionary of attribute changes (attribute: [values]).

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            return self.conn.modify(dn, {k: [(ldap3.MODIFY_REPLACE, v if isinstance(v, list) else [v])] for k, v in changes.items()})
        except Exception as e:
            logging.error(f"Failed to set attributes for {dn}: {e}")
            return False

    def __init__(self, config: Dict[str, Any], password: Optional[str] = None) -> None:
        """
        Initialize the LDAP connection using the given config.

        Args:
            config (Dict[str, Any]): LDAP configuration dictionary.
            password (Optional[str]): Optional password for binding.
        """
        self.config = config
        self.password = password or config.get('bind_password')
        self.server = None
        self.conn = None
        self._connect()

    def _connect(self) -> None:
        """
        Establish and bind the LDAP connection.
        """
        server_kwargs = {}
        skip_tls_verify = config_flag(self.config, 'skip_tls_verify')
        use_starttls = config_flag(self.config, 'use_starttls')
        use_ssl = config_flag(self.config, 'use_ssl')

        # Skip unreachable AAAA records instead of blocking on their connect timeout
        if force_ipv4_enabled(self.config):
            server_kwargs['mode'] = ldap3.IP_V4_ONLY
            logging.debug("force_ipv4 is set: restricting LDAP connections to IPv4")
        
        # Handle SSL/TLS configuration
        server_url = self.config['server']
        if server_url.startswith('ldaps://') or use_ssl:
            # For LDAPS connections, set up SSL
            if skip_tls_verify:
                server_kwargs['use_ssl'] = True
                server_kwargs['tls'] = ldap3.Tls(validate=ssl.CERT_NONE)
            else:
                server_kwargs['use_ssl'] = True
                server_kwargs['tls'] = ldap3.Tls(validate=ssl.CERT_REQUIRED)
        elif skip_tls_verify:
            # For regular LDAP with TLS verification disabled
            server_kwargs['tls'] = ldap3.Tls(validate=ssl.CERT_NONE)
            
        self.server = ldap3.Server(self.config['server'], **server_kwargs)
        bind_pw = self.password
        if not bind_pw:
            raise ValueError("LDAP bind password is required.")
        self.conn = ldap3.Connection(
            self.server,
            user=self.config.get('bind_username', self.config.get('username')),
            password=bind_pw,
            auto_bind=False
        )
        self.conn.open()
        if use_starttls:
            self.conn.start_tls()
        
        # Attempt to bind
        bind_username = self.config.get('bind_username', self.config.get('username'))
        
        try:
            bind_result = self.conn.bind()
            if not bind_result:
                # If initial bind failed, try to convert email to DN format
                if '@' in bind_username and not bind_username.startswith('cn='):
                    # Try common DN formats for email addresses
                    email_user = bind_username.split('@')[0]
                    base_dn = self.config.get('base_dn', '')
                    
                    # Common DN patterns to try
                    dn_patterns = [
                        f"uid={email_user},{base_dn}",
                        f"cn={email_user},{base_dn}",
                        f"uid={bind_username},{base_dn}",
                        f"cn={bind_username},{base_dn}",
                        f"uid={email_user},cn=users,{base_dn}",
                        f"cn={email_user},cn=users,{base_dn}",
                        f"uid={bind_username},cn=users,{base_dn}",
                        f"cn={bind_username},cn=users,{base_dn}"
                    ]
                    
                    for dn_pattern in dn_patterns:
                        try:
                            logging.info(f"Attempting to bind with DN: {dn_pattern}")
                            # Create new connection with DN format
                            test_conn = ldap3.Connection(
                                self.server,
                                user=dn_pattern,
                                password=bind_pw,
                                auto_bind=False
                            )
                            test_conn.open()
                            if use_starttls:
                                test_conn.start_tls()
                            if test_conn.bind():
                                logging.info(f"Successfully bound with DN: {dn_pattern}")
                                # Replace the original connection with the successful one
                                self.conn.unbind()
                                self.conn = test_conn
                                return
                            test_conn.unbind()
                        except Exception as e:
                            logging.debug(f"Failed to bind with DN {dn_pattern}: {e}")
                            continue
                
                # If all bind attempts failed, provide detailed error
                if hasattr(self.conn, 'result') and self.conn.result:
                    error_code = self.conn.result.get('result', 'Unknown')
                    error_desc = self.conn.result.get('description', 'Unknown error')
                    error_msg = self.conn.result.get('message', '')
                    
                    if error_code == 34:  # invalidDNSyntax
                        raise ValueError(f"Invalid bind username format. The username '{bind_username}' must be in DN format (e.g., 'cn=admin,dc=example,dc=com') not email format. Tried multiple DN conversions but none worked. Error: {error_desc} - {error_msg}")
                    elif error_code == 49:  # invalidCredentials
                        raise ValueError(f"Authentication failed: Invalid credentials for user '{bind_username}'. Error: {error_desc} - {error_msg}")
                    else:
                        raise ValueError(f"LDAP bind failed (code {error_code}): {error_desc} - {error_msg}")
                else:
                    raise ValueError("LDAP bind failed without detailed error information")
        except Exception as e:
            if "Invalid bind username format" in str(e) or "Authentication failed" in str(e) or "LDAP bind failed" in str(e):
                raise
            else:
                raise ValueError(f"LDAP connection error: {e}")

    def search(self, search_filter: str, attributes: Optional[List[str]] = None, log_errors: bool = True) -> List[Any]:
        """
        Perform an LDAP search and return the result entries.

        Args:
            search_filter (str): LDAP search filter.
            attributes (Optional[List[str]]): List of attributes to retrieve.

        Returns:
            List[Any]: List of LDAP entries.
        """
        try:
            base_dn = self.config['base_dn']
            self.conn.search(base_dn, search_filter, attributes=attributes or [])
            return self.conn.entries
        except LDAPException as e:
            if log_errors:
                logging.error(f"LDAP search failed: {e}")
            raise
        except Exception as e:
            if log_errors:
                logging.error(f"LDAP error: {e}")
            raise

    def _search_any(self, search_filters: List[str], attributes: Optional[List[str]] = None) -> List[Any]:
        results: List[Any] = []
        seen_dns = set()
        for search_filter in search_filters:
            try:
                entries = self.search(search_filter, attributes, log_errors=False)
            except LDAPException as e:
                message = str(e).lower()
                if "invalid class" in message or ("objectclass" in message and "invalid" in message):
                    continue
                raise
            for entry in entries:
                dn = getattr(entry, "entry_dn", None)
                key = dn or str(entry)
                if key in seen_dns:
                    continue
                seen_dns.add(key)
                results.append(entry)
        return results

    def _parse_invalid_attribute(self, error_message: str) -> Optional[str]:
        message = error_message.lower()
        if "invalid attribute type" not in message:
            return None
        parts = error_message.split()
        if not parts:
            return None
        return parts[-1].strip()

    def _is_group_entry(self, entry: Any) -> bool:
        attrs = getattr(entry, "entry_attributes_as_dict", {}) or {}
        object_classes = [str(v).lower() for v in attrs.get("objectClass", [])]
        if object_classes:
            group_classes = {"group", "groupofnames", "groupofuniquenames", "posixgroup"}
            person_classes = {"person", "inetorgperson", "organizationalperson", "user", "posixaccount"}
            return any(cls in group_classes for cls in object_classes) and not any(cls in person_classes for cls in object_classes)
        # Fallback: treat entries with common group attributes as groups.
        group_attrs = {"member", "memberuid", "uniquemember"}
        return any(key in attrs for key in group_attrs)

    def list_users(self, attributes: Optional[List[str]] = None, allow_attribute_fallback: bool = False) -> List[Any]:
        """
        List users in the directory.

        Args:
            attributes (Optional[List[str]]): Attributes to retrieve.

        Returns:
            List[Any]: List of LDAP entries for users.
        """
        filters = [
            "(objectClass=person)",
            "(objectClass=inetOrgPerson)",
            "(objectClass=posixAccount)",
            "(objectClass=user)",
        ]
        attrs = list(attributes) if attributes else None
        if allow_attribute_fallback and attrs and "*" not in attrs:
            while True:
                try:
                    return self._search_any(filters, attrs)
                except LDAPException as e:
                    invalid_attr = self._parse_invalid_attribute(str(e))
                    if invalid_attr:
                        attrs = [a for a in attrs if a.lower() != invalid_attr.lower()]
                        if not attrs:
                            raise
                        continue
                    raise
        return self._search_any(filters, attrs)

    def list_groups(self, attributes: Optional[List[str]] = None, allow_attribute_fallback: bool = False) -> List[Any]:
        """
        List groups in the directory.

        Args:
            attributes (Optional[List[str]]): Attributes to retrieve.

        Returns:
            List[Any]: List of LDAP entries for groups.
        """
        filters = [
            "(objectClass=group)",
            "(objectClass=groupOfNames)",
            "(objectClass=groupOfUniqueNames)",
            "(objectClass=posixGroup)",
        ]
        search_attrs = list(attributes) if attributes else []
        if "*" not in search_attrs and not any(a.lower() == "objectclass" for a in search_attrs):
            search_attrs.append("objectClass")
        if allow_attribute_fallback and "*" not in search_attrs:
            while True:
                try:
                    entries = self._search_any(filters, search_attrs)
                    break
                except LDAPException as e:
                    invalid_attr = self._parse_invalid_attribute(str(e))
                    if invalid_attr:
                        search_attrs = [a for a in search_attrs if a.lower() != invalid_attr.lower()]
                        if not search_attrs:
                            raise
                        continue
                    raise
        else:
            entries = self._search_any(filters, search_attrs)
        return [entry for entry in entries if self._is_group_entry(entry)]

    def get_user(self, username: str, attributes: Optional[List[str]] = None) -> List[Any]:
        """
        Search for a user by UID, CN, or MAIL.

        Args:
            username (str): Username (UID, CN, or MAIL).
            attributes (Optional[List[str]]): Attributes to retrieve.

        Returns:
            List[Any]: List of LDAP entries for the user.
        """
        search_filter = f"(|(uid={username})(cn={username})(mail={username}))"
        return self.search(search_filter, attributes)

    def get_group(self, group_cn: str, attributes: Optional[List[str]] = None) -> List[Any]:
        """
        Search for a group by CN.

        Args:
            group_cn (str): Group CN.
            attributes (Optional[List[str]]): Attributes to retrieve.

        Returns:
            List[Any]: List of LDAP entries for the group.
        """
        search_filter = f"(cn={group_cn})"
        return self.search(search_filter, attributes)

    def get_group_members(self, group_cn: str, attributes: Optional[List[str]] = None) -> List[Any]:
        """
        Search for members of a group by CN.

        Args:
            group_cn (str): Group CN.
            attributes (Optional[List[str]]): Attributes to retrieve.

        Returns:
            List[Any]: List of LDAP entries for the group.
        """
        search_filter = f"(cn={group_cn})"
        return self.search(search_filter, attributes)

    def set_attribute(self, dn: str, attribute: str, value: str) -> bool:
        """
        Set a single attribute for a given DN.

        Args:
            dn (str): Distinguished Name.
            attribute (str): Attribute name.
            value (str): Attribute value.

        Returns:
            bool: True on success, False otherwise.
        """
        try:
            return self.conn.modify(dn, {attribute: [(ldap3.MODIFY_REPLACE, [value])]})
        except Exception as e:
            logging.error(f"Failed to set attribute {attribute} for {dn}: {e}")
            return False

    def get_user_groups(self, username: str) -> List[Any]:
        """
        Search for groups associated with a user.

        Args:
            username (str): Username (UID, CN, or MAIL).

        Returns:
            List[Any]: List of LDAP entries with group info.
        """
        search_filter = f"(|(uid={username})(cn={username})(mail={username}))"
        return self.search(search_filter, ["memberOf"])
