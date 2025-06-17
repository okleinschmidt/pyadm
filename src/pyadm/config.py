import configparser
from pathlib import Path

class ClusterConfig:
    """
    Loads and manages multiple Elastic/OpenSearch or LDAP server configs from pyadm.conf.
    """
    def __init__(self, config_file=None):
        self.config = configparser.ConfigParser()
        self.config_file = config_file or (Path.home() / ".config/pyadm/pyadm.conf")
        self.config.read(self.config_file)

    def get_clusters(self, prefix="ELASTIC"):
        """
        Returns a dict of all clusters/servers (section names starting with the given prefix).
        Args:
            prefix (str): Section prefix, e.g. 'ELASTIC' or 'LDAP'.
        Returns:
            dict: section name -> config dict
        """
        clusters = {}
        for section in self.config.sections():
            if section.upper().startswith(prefix.upper()):
                clusters[section] = dict(self.config[section])
        return clusters

    def get_cluster(self, name=None, prefix="ELASTIC"):
        """
        Returns the config dict for the given cluster/server name (section), or the first if name is None.
        Args:
            name (str): Section name.
            prefix (str): Section prefix.
        Returns:
            dict: config dict for the selected cluster/server
        """
        clusters = self.get_clusters(prefix=prefix)
        if not clusters:
            raise RuntimeError(f"No {prefix} cluster/server defined in config.")
        if name and name in clusters:
            return clusters[name]
        # fallback: e.g. 'ELASTIC' or 'LDAP', else first
        if prefix.upper() in clusters:
            return clusters[prefix.upper()]
        return next(iter(clusters.values()))

cluster_config = ClusterConfig()
config = cluster_config.config

cluster_config = ClusterConfig()
config = cluster_config.config
