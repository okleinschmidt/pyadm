import json
import pprint
import logging

from elasticsearch import Elasticsearch

class ElasticSearch():
    
    def __init__(self, config):
        self.config = config
        self.es = Elasticsearch(config['url'], basic_auth=(config['username'], config['password'])) 

    # show information about elastic cluster
    def info(self):
        """ Retrive information about cluster """
        es = self.es
        return es.info()

    # list all indices
    def list_indices(self):
        """ List all indices """
        try:
            es = self.es
            
            response = es.cat.indices(format="json")
            all_indices = [index for index in response if not index['index'].startswith('.')]
            sorted_indices = sorted(all_indices, key=lambda x: x['index'])
            return sorted_indices
        except Exception as e:
            logging.error(f"Error deleting index: {index}. {e}")
            raise Exception(f"An error occurred: {e}")
        
    # reindex indices
    def reindex(self, source, dest):
        """ Reindex indices """
        try:
            es = self.es
            body = {
                "source": {
                    "index": source
                },
                "dest": {
                    "index": dest
                }
            }
            es.reindex(body=body, wait_for_completion=True)
        except Exception as e:
            logging.error(f"Error deleting index: {index}. {e}")
            raise Exception(f"An error occurred: {e}")

    # delete index
    def delete_index(self, index):
        """ Delete index """
        try:
            es = self.es
            es.indices.delete(index=index)
        except Exception as e:
            logging.error(f"Error deleting index: {index}. {e}")
            raise Exception(f"An error occurred: {e}")