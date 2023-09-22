import json
import pprint

from elasticsearch import Elasticsearch

# client = Elasticsearch(
#     cloud_id=CLOUD_ID,
#     basic_auth=("elastic", ELASTIC_PASSWORD)
# )

class ElasticSearch():
    
    def __init__(self, config):
        self.config = config
        self.es = Elasticsearch(config['url'], basic_auth=(config['username'], config['password'])) 
        
    def info(self):
        """ Retrive information about cluster """
        es = self.es
        return es.info()

    def list_indices(self):
        """ List all indices """
        es = self.es
        
        response = es.cat.indices(format="json")
        all_indices = [index for index in response if not index['index'].startswith('.')]
        sorted_indices = sorted(all_indices, key=lambda x: x['index'])
        return sorted_indices
        