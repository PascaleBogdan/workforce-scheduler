from pymongo import MongoClient
import sys
import urllib.parse

# Format password if it contains special characters
password = "mt_2026!"
password = urllib.parse.quote_plus(password)
uri = f"mongodb+srv://bogdan:{password}@mt.sytpdwh.mongodb.net/?appName=MT"

print(f"Connecting to {uri}")
try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    info = client.server_info()
    print("SUCCESS: Connected to MongoDB Atlas!")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
