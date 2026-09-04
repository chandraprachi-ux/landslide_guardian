import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
try:
    from pymongo import MongoClient
except ImportError:  # Optional for local demo mode
    MongoClient = None

logger = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(ENV_FILE)
MONGO_URI = os.getenv("MONGODB_URI")


class MemoryCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list):
            for key, direction in reversed(key_or_list):
                self.docs.sort(key=lambda d: d.get(key, ""), reverse=direction < 0)
        else:
            self.docs.sort(key=lambda d: d.get(key_or_list, ""), reverse=(direction or 1) < 0)
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    def __iter__(self):
        return iter(self.docs)


class MemoryCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(dict(doc))
        return type("InsertResult", (), {"inserted_id": None})()

    def find_one(self, query=None, sort=None):
        query = query or {}
        matches = [d for d in self.docs if all(d.get(k) == v for k, v in query.items())]
        if sort:
            matches = list(MemoryCursor(matches).sort(sort))
        return matches[0] if matches else None

    def find(self, query=None, projection=None):
        query = query or {}
        docs = [dict(d) for d in self.docs if all(d.get(k) == v for k, v in query.items())]
        if projection:
            docs = [
                {k: v for k, v in d.items() if projection.get(k, 1) and k != "_id"}
                for d in docs
            ]
        return MemoryCursor(docs)

    def update_one(self, query, update, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                d.update(update.get("$set", {}))
                return
        if upsert:
            doc = dict(query)
            doc.update(update.get("$set", {}))
            self.docs.append(doc)

    def delete_one(self, query):
        for i, d in enumerate(self.docs):
            if all(d.get(k) == v for k, v in query.items()):
                del self.docs[i]
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    def count_documents(self, query=None):
        query = query or {}
        return sum(1 for d in self.docs if all(d.get(k) == v for k, v in query.items()))

    def create_index(self, *args, **kwargs):
        return None


class MemoryDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = MemoryCollection()
        return self.collections[name]


class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.is_connected = False
        self.mode = "memory"

        if not MONGO_URI or MongoClient is None:
            logger.warning("MONGODB_URI is not configured; using in-memory prototype storage.")
            self._use_memory()
            return

        try:
            self.client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            self.client.admin.command("ping")
            self.db = self.client["landslide_guardian"]
            self.is_connected = True
            self.mode = "mongodb_atlas"
            logger.info("MongoDB Atlas connected successfully.")
        except Exception as exc:
            logger.warning("MongoDB connection failed; using in-memory storage: %s", exc)
            self._use_memory()

        self._bind_collections()
        self._create_indexes()

    def _use_memory(self):
        self.client = None
        self.db = MemoryDatabase()
        self.is_connected = False
        self.mode = "memory"
        self._bind_collections()
        self._create_indexes()

    def _bind_collections(self):
        self.users = self.db["users"]
        self.locations = self.db["locations"]
        self.environmental_data = self.db["environmental_data"]
        self.risk_assessments = self.db["risk_assessments"]
        self.alerts = self.db["alerts"]
        self.citizens = self.db["citizens"]
        self.sensor_readings = self.db["sensor_readings"]
        self.sensor_latest = self.db["sensor_latest"]
        self.notification_log = self.db["notification_log"]
        self.rainfall_records = self.db["rainfall_records"]
        self.otps = self.db["otps"]

    def _create_indexes(self):
        self.risk_assessments.create_index([("timestamp", -1)])
        self.alerts.create_index([("timestamp", -1)])
        self.alerts.create_index([("risk_score", -1)])
        self.citizens.create_index([("location", 1)])
        self.sensor_readings.create_index([("timestamp", -1)])
        self.sensor_latest.create_index([("device_id", 1), ("section_id", 1)])
        self.notification_log.create_index([("timestamp", -1)])
        self.rainfall_records.create_index([("location_key", 1), ("timestamp", -1)])
        self.rainfall_records.create_index([("dedup_key", 1)])
        self.otps.create_index([("email", 1)])

    def ping(self) -> bool:
        if not self.is_connected or self.client is None:
            return False
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False


def clean_document(doc: Any):
    if not doc:
        return None
    result = dict(doc)
    result.pop("_id", None)
    return result


db_manager = DatabaseManager()
