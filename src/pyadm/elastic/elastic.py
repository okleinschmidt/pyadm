
import logging
from typing import Any, Dict, List, Optional, Union

try:
    from opensearchpy import OpenSearch
    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
from elasticsearch import Elasticsearch

class ElasticSearch:
    """
    Wrapper class for Elasticsearch and OpenSearch operations.
    """
    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the connection to the Elasticsearch or OpenSearch cluster.

        Args:
            config (Dict[str, Any]): Configuration dictionary with 'url', 'username', 'password', optionally 'engine', 'skip_tls_verify'.
        """
        self.config = config
        self.engine = config.get('engine', '').lower()
        self.client: Union[Elasticsearch, Any]

        # TLS/SSL verification
        skip_tls_verify = str(config.get('skip_tls_verify', 'false')).lower() in ('1', 'true', 'yes', 'on')
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