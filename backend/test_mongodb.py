from pathlib import Path
import os

from dotenv import load_dotenv
from pymongo import MongoClient

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_FILE)

uri = os.getenv("MONGODB_URI")
if not uri:
    raise RuntimeError(f"MONGODB_URI is missing from {ENV_FILE}")

print("Testing MongoDB Atlas connection...")

client = MongoClient(uri, serverSelectionTimeoutMS=5000)
client.admin.command("ping")

print("SUCCESS: MongoDB Atlas is connected!")
db = client["landslide_guardian"]
print("Database:", db.name)
print("Collections:")
print(db.list_collection_names())

client.close()
