# Provide the same read interface for MongoDB and the sample file.
# The dashboard only needs reads; the database milestone will cover the other CRUD operations.
import json
import logging
from typing import Protocol
from .records import FIELDS

logger = logging.getLogger(__name__)

class RepositoryError(RuntimeError):
    # An unsuccessful read should not look like a successful search with no matches.
    pass

# These are the methods both data sources need so the dashboard can use either one.
class AnimalRepository(Protocol):
    def read_all(self) -> list[dict]: ...
    def close(self) -> None: ...

# This lets me run the dashboard with sample records while the database work is still pending.
class JsonRepository:
    def __init__(self, path):
        self.path = path

    def read_all(self):
        try:
            with self.path.open(encoding="utf-8") as source:
                records = json.load(source)
            if not isinstance(records, list):
                raise ValueError("Expected a list")
            return records
        except (OSError, UnicodeError, ValueError) as exc:
            logger.warning("Sample data read failed (%s)", type(exc).__name__)
            raise RepositoryError("Sample data could not be loaded. Check SHELTER_DATA_FILE.") from None

    def close(self):
        pass

# Keep MongoDB-specific calls behind the shared repository interface.
class MongoRepository:
    def __init__(self, client, database, collection):
        self.client = client
        self.collection = client[database][collection]

    def read_all(self):
        from pymongo.errors import PyMongoError
        try:
            # Only request the displayed fields and the ID needed to track row selection.
            return list(self.collection.find({}, {field: 1 for field in ("_id", *FIELDS)}))
        except PyMongoError as exc:
            # Log the error type only; exception text could include connection details.
            logger.warning("MongoDB read failed (%s)", type(exc).__name__)
            raise RepositoryError("Animal records could not be loaded. Check the database connection.") from None

    def close(self):
        self.client.close()

# Choose the data source from the configured mode.
def create_repository(settings):
    if settings.mode == "demo":
        return JsonRepository(settings.data_file)
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    try:
        # A three-second server-selection timeout bounds the wait for an unavailable server.
        client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000, connect=False)
    except (PyMongoError, ValueError):
        raise RepositoryError("MongoDB configuration is invalid.") from None
    try:
        return MongoRepository(client, settings.database, settings.collection)
    except Exception:
        client.close()
        raise
