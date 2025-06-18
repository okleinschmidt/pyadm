import logging
from typing import Any, Dict, List, Optional
import ldap3
from ldap3.core.exceptions import LDAPException

class LDAPClient:

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
            return bool(self.get_group_members(group_cn))
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
            return self.conn.modify(group_dn, {'member': [(ldap3.MODIFY_ADD, [user_dn])]})
        except Exception as e:
            logging.error(f"Failed to add user to group: {e}")
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
            return self.conn.modify(group_dn, {'member': [(ldap3.MODIFY_DELETE, [user_dn])]})
        except Exception as e:
            logging.error(f"Failed to remove user from group: {e}")
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
    """
    Wrapper class for LDAP operations.
    """
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
        skip_tls_verify = str(self.config.get('skip_tls_verify', 'false')).lower() in ('1', 'true', 'yes', 'on')
        use_starttls = str(self.config.get('use_starttls', 'false')).lower() in ('1', 'true', 'yes', 'on')
        if skip_tls_verify:
            server_kwargs['tls'] = ldap3.Tls(validate=ldap3.ssl.CERT_NONE)
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
        self.conn.bind()

    def search(self, search_filter: str, attributes: Optional[List[str]] = None) -> List[Any]:
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
            logging.error(f"LDAP search failed: {e}")
            raise
        except Exception as e:
            logging.error(f"LDAP error: {e}")
            raise

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
