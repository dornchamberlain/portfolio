# Public comparison copy: historical credentials redacted.
# Example Python Code to Insert a Document 

from pymongo import MongoClient 
from bson.objectid import ObjectId 

class AnimalShelter(object): 
    """ CRUD operations for Animal collection in MongoDB """ 

    def __init__(self, username, password): 
        # Initializing the MongoClient. This helps to access the MongoDB 
        # databases and collections. This is hard-wired to use the aac 
        # database, the animals collection, and the aac user. 
        # 
        # Connection Variables 
        # 
        USER = username
        PASS = password
        HOST = 'localhost' 
        PORT = 27017 
        DB = 'aac' 
        COL = 'animals' 
        # 
        # Initialize Connection 
        # 
        safe_pass = PASS.replace("!", "%21")
        self.client = MongoClient(
            f'mongodb://{USER}:{safe_pass}@{HOST}:{PORT}/?authSource=admin'
        )
        self.database = self.client[DB]
        self.collection = self.database[COL] 

    # Create a method to return the next available record number for use in the create method
    # (Not required for Module Four, so left intentionally blank)
            
    # Complete this create method to implement the C in CRUD. 
    def create(self, data):
        if data is not None:
            if isinstance(data, dict):
                try:
                    result = self.collection.insert_one(data)  # data should be dictionary
                    return result.acknowledged
                except Exception:
                    return False
            else:
                return False
        else: 
            raise Exception("Nothing to save, because data parameter is empty") 

    # Create method to implement the R in CRUD.
    def read(self, query):
        if query is not None:
            if isinstance(query, dict):
                try:
                    results = self.collection.find(query)
                    return list(results)
                except Exception:
                    return []
            else:
                return []
        else:
            return []

    # Update method to handle the U in CRUD.
    def update(self, query, update_data):
        if query is None or update_data is None:
            return 0
        if not isinstance(query, dict) or not isinstance(update_data, dict):
            return 0
        try:
            result = self.collection.update_many(query, {"$set": update_data})
            return result.modified_count
        except Exception as e:
            print(f"Update error: {e}")
            return 0

    # Delete method to handle the D in CRUD.
    def delete(self, query):
        if query is None:
            return 0
        if not isinstance(query, dict):
            return 0
        try:
            result = self.collection.delete_many(query)
            return result.deleted_count
        except Exception as e:
            print(f"Delete error: {e}")
            return 0