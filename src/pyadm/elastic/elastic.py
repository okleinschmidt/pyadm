import json

from elasticsearch import Elasticsearch

class ElasticSearch():
    
    def __init__(self, config):
        self.config = config
        
    def info(self):
        """ Retrive information about cluster """
        config = self.config
        
        
        