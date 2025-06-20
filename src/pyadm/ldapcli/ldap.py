import logging
import ssl
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
        use_ssl = str(self.config.get('use_ssl', 'false')).lower() in ('1', 'true', 'yes', 'on')
        
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
