
import logging
from typing import Any, Dict, List, Optional, Union

try:
    from opensearchpy import OpenSearch
    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
from elasticsearch import Elasticsearch

from pyadm.net_utils import apply_force_ipv4, config_flag

class ElasticSearch:
    """
    Wrapper class for Elasticsearch and OpenSearch operations.
    """
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the connection to the Elasticsearch or OpenSearch cluster.

        Args:
            config (Dict[str, Any]): Configuration dictionary with 'url', 'username', 'password', optionally 'engine', 'skip_tls_verify', 'force_ipv4'.
        """
        self.config = config
        self.engine = config.get('engine', '').lower()
        self.client: Union[Elasticsearch, Any]

        # Restrict to IPv4 if the cluster host has an unreachable AAAA record
        apply_force_ipv4(config)

        # TLS/SSL verification
        skip_tls_verify = config_flag(config, 'skip_tls_verify')
        ssl_kwargs = {}
        if skip_tls_verify:
            ssl_kwargs = {
                'verify_certs': False,
                'ssl_show_warn': False,
            }
        # Use OpenSearch if requested or if URL hints at it and package is available
        # Always use OpenSearch client if engine is set to opensearch and package is available
        if self.engine == 'opensearch' and OPENSEARCH_AVAILABLE:
            self.client = OpenSearch(
                config['url'],
                http_auth=(config['username'], config['password']),
                **ssl_kwargs
            )
        else:
            self.client = Elasticsearch(
                config['url'],
                basic_auth=(config['username'], config['password']),
                **ssl_kwargs
            )

    def info(self) -> Dict[str, Any]:
        """
        Return information about the cluster.

        Returns:
            Dict[str, Any]: Cluster information.
        """
        return self.client.info()

    def list_indices(self) -> List[Dict[str, Any]]:
        """
        List all indices (except system indices), sorted by name.

        Returns:
            List[Dict[str, Any]]: List of indices.
        """
        try:
            response = self.client.cat.indices(format="json")
            all_indices = [index for index in response if not index['index'].startswith('.')]
            sorted_indices = sorted(all_indices, key=lambda x: x['index'])
            return sorted_indices
        except Exception as e:
            logging.error(f"Error listing indices: {e}")
            raise Exception(f"An error occurred: {e}")

    def _cluster_setting(self, key: str, fallback: Any) -> Any:
        """
        Read an effective cluster setting, honouring the usual precedence.

        Transient beats persistent beats the built-in default, which is what the
        cluster itself applies.
        """
        try:
            settings = self.client.cluster.get_settings(include_defaults=True, flat_settings=True)
        except Exception as e:
            logging.debug(f"Could not read cluster settings ({e}); assuming {key}={fallback}")
            return fallback
        for scope in ("transient", "persistent", "defaults"):
            value = (settings.get(scope) or {}).get(key)
            if value is not None:
                return value
        return fallback

    def get_shard_capacity(self) -> Dict[str, Any]:
        """
        Report how much of the cluster's shard budget is used.

        A cluster refuses to create new shards once the number of open shards
        reaches cluster.max_shards_per_node times the number of data nodes. Both
        assigned and unassigned shards count towards it, so an unassigned replica
        consumes budget just like a started primary does. Closed indices do not.

        Returns:
            Dict[str, Any]: used, limit, remaining, percent_used and the parts it
            was computed from.
        """
        try:
            health = self.client.cluster.health()
            shards = self.client.cat.shards(format="json")

            data_nodes = int(health.get("number_of_data_nodes") or 0)
            max_per_node = int(self._cluster_setting("cluster.max_shards_per_node", 1000))
            limit = max_per_node * data_nodes

            used = len(shards)
            primaries = sum(1 for shard in shards if shard.get("prirep") == "p")
            unassigned = sum(1 for shard in shards if shard.get("state") == "UNASSIGNED")

            return {
                "used": used,
                "limit": limit,
                "remaining": max(limit - used, 0),
                "percent_used": round(used / limit * 100, 1) if limit else None,
                "primaries": primaries,
                "replicas": used - primaries,
                "unassigned": unassigned,
                "data_nodes": data_nodes,
                "max_shards_per_node": max_per_node,
                "cluster_status": health.get("status"),
            }
        except Exception as e:
            logging.error(f"Error determining shard capacity: {e}")
            raise Exception(f"An error occurred: {e}")

    def get_shards_per_index(self) -> List[Dict[str, Any]]:
        """
        Count shards per index, so the biggest consumers of the budget are visible.

        Returns:
            List[Dict[str, Any]]: One entry per index, most shards first.
        """
        try:
            counts: Dict[str, Dict[str, Any]] = {}
            for shard in self.client.cat.shards(format="json"):
                entry = counts.setdefault(
                    shard["index"],
                    {"index": shard["index"], "shards": 0, "primaries": 0, "replicas": 0, "unassigned": 0},
                )
                entry["shards"] += 1
                if shard.get("prirep") == "p":
                    entry["primaries"] += 1
                else:
                    entry["replicas"] += 1
                if shard.get("state") == "UNASSIGNED":
                    entry["unassigned"] += 1
            return sorted(counts.values(), key=lambda e: (-e["shards"], e["index"]))
        except Exception as e:
            logging.error(f"Error counting shards per index: {e}")
            raise Exception(f"An error occurred: {e}")

    @staticmethod
    def _disk_state(disk_percent: Any, thresholds: List[Any]) -> Optional[str]:
        """Classify a node's disk usage against the watermarks: ok/low/high/flood."""
        try:
            used = float(disk_percent)
        except (TypeError, ValueError):
            return None
        state = "ok"
        for level, limit in thresholds:
            if limit is not None and used >= limit:
                state = "flood" if level == "flood_stage" else level
        return state

    def get_node_allocation(self) -> List[Dict[str, Any]]:
        """
        Per-node shard counts and disk usage, plus the disk watermarks in force.

        Running out of disk blocks writes just like running out of shard budget
        does, so both belong in the same picture.

        Returns:
            List[Dict[str, Any]]: One entry per node (UNASSIGNED row included).
        """
        try:
            rows = self.client.cat.allocation(format="json")
            watermarks = {
                level: self._cluster_setting(
                    f"cluster.routing.allocation.disk.watermark.{level}", default
                )
                for level, default in (("low", "85%"), ("high", "90%"), ("flood_stage", "95%"))
            }
            thresholds = []
            for level in ("low", "high", "flood_stage"):
                try:
                    thresholds.append((level, float(str(watermarks[level]).rstrip("%"))))
                except ValueError:
                    # A watermark can be given as a byte size ("20gb") rather than
                    # a percentage; in that case we cannot classify on percent.
                    thresholds.append((level, None))

            for row in rows:
                row["watermark_low"] = watermarks["low"]
                row["watermark_high"] = watermarks["high"]
                row["watermark_flood"] = watermarks["flood_stage"]
                row["state"] = self._disk_state(row.get("disk.percent"), thresholds)
            return rows
        except Exception as e:
            logging.error(f"Error reading node allocation: {e}")
            raise Exception(f"An error occurred: {e}")

    def reindex(self, source: str, dest: str) -> None:
        """
        Reindex data from a source index to a destination index.

        Args:
            source (str): Source index.
            dest (str): Destination index.
        """
        try:
            body = {
                "source": {"index": source},
                "dest": {"index": dest}
            }
            self.client.reindex(body=body, wait_for_completion=True)
        except Exception as e:
            logging.error(f"Error reindexing from {source} to {dest}: {e}")
            raise Exception(f"An error occurred: {e}")

    def delete_index(self, index: str) -> bool:
        """
        Delete an index.

        Args:
            index (str): Name of the index to delete.

        Returns:
            bool: True on success, False on error.
        """
        try:
            self.client.indices.delete(index=index)
            return True
        except Exception as e:
            logging.error(f"Error deleting index: {index}. {e}")
            return False

    def create_index(self, index: str, body: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a new index.

        Args:
            index (str): Name of the index to create.
            body (Optional[Dict[str, Any]]): Optional index settings/mappings.

        Returns:
            bool: True on success, False on error.
        """
        try:
            self.client.indices.create(index=index, body=body or {})
            return True
        except Exception as e:
            logging.error(f"Error creating index: {index}. {e}")
            return False

    def get_mapping(self, index: str) -> Dict[str, Any]:
        """
        Get the mapping of an index.

        Args:
            index (str): Name of the index.

        Returns:
            Dict[str, Any]: Mapping information.
        """
        try:
            return self.client.indices.get_mapping(index=index)
        except Exception as e:
            logging.error(f"Error getting mapping for index {index}: {e}")
            return {}

    def search(self, index: str, query: Dict[str, Any], size: int = 10) -> Dict[str, Any]:
        """
        Search for documents in an index.

        Args:
            index (str): Name of the index.
            query (Dict[str, Any]): Query DSL.
            size (int): Number of results to return.

        Returns:
            Dict[str, Any]: Search results.
        """
        try:
            return self.client.search(index=index, body={"query": query}, size=size)
        except Exception as e:
            logging.error(f"Error searching index {index}: {e}")
            return {}

    def cluster_health(self) -> Dict[str, Any]:
        """
        Get cluster health information.

        Returns:
            Dict[str, Any]: Cluster health info.
        """
        try:
            return self.client.cluster.health()
        except Exception as e:
            logging.error(f"Error getting cluster health: {e}")
            return {}

    def get_aliases(self, index: Optional[str] = None) -> Dict[str, Any]:
        """
        Get aliases for an index or all indices.

        Args:
            index (Optional[str]): Index name or None for all.

        Returns:
            Dict[str, Any]: Alias information.
        """
        try:
            return self.client.indices.get_alias(index=index or "*")
        except Exception as e:
            logging.error(f"Error getting aliases: {e}")
            return {}

    def get_settings(self, index: Optional[str] = None) -> Dict[str, Any]:
        """
        Get settings for an index or all indices.

        Args:
            index (Optional[str]): Index name or None for all.

        Returns:
            Dict[str, Any]: Settings information.
        """
        try:
            return self.client.indices.get_settings(index=index or "*")
        except Exception as e:
            logging.error(f"Error getting settings: {e}")
            return {}

    def update_settings(self, index: str, settings: Dict[str, Any]) -> bool:
        """
        Update settings for an index.

        Args:
            index (str): Index name.
            settings (Dict[str, Any]): Settings to update.

        Returns:
            bool: True on success, False on error.
        """
        try:
            self.client.indices.put_settings(index=index, body=settings)
            return True
        except Exception as e:
            logging.error(f"Error updating settings for index {index}: {e}")
            return False