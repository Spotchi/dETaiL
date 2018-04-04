import datetime
import os
import pymongo
import hashlib
from pymongo import MongoClient
from bson.objectid import ObjectId
from detl.db_context import db_context
import json
import logging
from detl.identity import Identity
def db_client(config_path='configs/db.json'):

    with open(config_path) as fd:
        config = json.load(fd)

    host = config['host']
    port = config['port']
    db = config['db']
    collection = config['collection']
    data_folder = config['data_folder']

    return MyDb(host, port, db, collection, data_folder)


class MyDb(object):

    def __init__(self, host, port, db, collection, data_folder):

        self.client = MongoClient(host, port)
        self.db = getattr(self.client, db)
        self.coll = getattr(self.db, collection)
    
        self.data_folder = data_folder

        # TODO : in the future, split the find into two cases : whether the file is available or not (in that case, can download)

    def find(self, identity):

        hash_value = identity.__id_hash__()
        result = self.coll.find_one({'config_hash': hash_value})
        return result
    
    def find_from_hash(self, hash_val):

        return self.coll.find_one({'config_hash': hash_val})


    def find_file(self, identity, unpack_input=False, unpack_len=0):
        if unpack_input:
            all_identities = [Identity('unpack', [identity, i], {}) for i in range(unpack_len)]
            return [self._find_file(all_identities[i]) for i in range(unpack_len)]
        return self._find_file(identity)

    def _find_file(self, identity):

        res = self.find(identity)
        if res is not None:
            if 'file_descriptor' in res:
                return res['file_descriptor']

    
    def insert(self, results, save_func, save_data=True, unpack_input=False):
        if unpack_input:
            for res in results:
                self._insert(res.identity, res, save_func, save_data=save_data)
        else:
            self._insert(results.identity, results, save_func, save_data=save_data)


    def _insert(self, identity, results, save_func, save_data=True):
        
        # TODO : move to computation identity class
        hash_value = identity.__id_hash__()
        identity_dict = identity.to_dict(db=self)
        
        # If save_data
        if save_data:
            # Create a file path
            file_path = self.create_fd(identity)
            # TODO : handle errors
            # Save to file path
            save_func(results, file_path)
            # Add to dict
            identity_dict['file_descriptor'] = file_path

        # Save to collection
        post = self.coll.insert_one(identity_dict)
        return post


    def create_fd(self, identity):
        '''
        Save to a data folder whose name corresponds to the name of the identity
        '''
        # TODO : no global variable
        # TODO : assuming that the data folder is already created
        # TODO : move hash_value to identity init
        hash_value = identity.__id_hash__()
        folder = os.path.join(self.data_folder, identity.name)
        if not os.path.exists(folder):
            os.mkdir(folder)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fname = timestamp + str(hash_value)
        file_path = os.path.join(folder, fname)
        return file_path
        
    def as_default(self):

        return db_context.get_controller(self)

    def browse(self, fn_name, origin={}):
        '''
        browse('processor_2')
        browse('processor_2', {'source':{}, 'Preprocessor':{'kwargs':{'num_mul': 50}}})

        '''
        # TODO : write the origins as a dictionary with $and in mongo syntax
        results = self.coll.find({'name': fn_name})
        for res in results:
            if res in origin:
                yield res
            else:
                recursive_find(res, origin)
    
    def drop_all(self):
        self.coll.drop()

'''
db.test_pipeline.aggregate(
[
{"$graphLookup": {"from": "test_pipeline",
"startWith": "$args",
"connectFromField": "args",
"connectToField" : "_id",
"as": "ancestors"}},
{"$match": {"name": "processor_2"}},
{ "$addFields": { 
            "ancestors": { 
                "$reverseArray": { 
                    "$map": { 
                        "input": "$ancestors", 
                        "as": "t", 
                        "in": { "name": "$$t.name" }
                    } 
                } 
            }
        }}];
'''


