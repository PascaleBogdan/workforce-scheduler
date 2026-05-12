import os
import json
import pandas as pd
from pymongo import MongoClient
import urllib.parse

password = "mt_2026!"
password = urllib.parse.quote_plus(password)
uri = f"mongodb+srv://bogdan:{password}@mt.sytpdwh.mongodb.net/?appName=MT"
client = MongoClient(uri)
db = client["workforce_scheduler"]

def migrate_text(filename):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        db["settings"].update_one({"_id": filename}, {"$set": {"data": content}}, upsert=True)
        print(f"Migrated {filename}")

def migrate_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            db["settings"].update_one({"_id": filename}, {"$set": {"data": data}}, upsert=True)
            print(f"Migrated {filename}")
        except Exception as e:
            print(f"Error migrating {filename}: {e}")

def migrate_df(filename):
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename)
            data = df.to_dict(orient="records")
            db["settings"].update_one({"_id": filename}, {"$set": {"data": data}}, upsert=True)
            print(f"Migrated {filename}")
        except Exception as e:
            print(f"Error migrating {filename}: {e}")

HISTORY_DIR = "istoric"

def migrate_history():
    if os.path.exists(HISTORY_DIR):
        for fname in os.listdir(HISTORY_DIR):
            path = os.path.join(HISTORY_DIR, fname)
            if fname.endswith(".csv"):
                try:
                    df = pd.read_csv(path)
                    data = df.to_dict(orient="records")
                    db["istoric"].update_one({"_id": fname}, {"$set": {"data": data}}, upsert=True)
                    print(f"Migrated history {fname}")
                except Exception as e:
                    print(f"Error migrating {fname}: {e}")
            elif fname.endswith(".json"):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    db["istoric"].update_one({"_id": fname}, {"$set": {"data": data}}, upsert=True)
                    print(f"Migrated history {fname}")
                except Exception as e:
                    print(f"Error migrating {fname}: {e}")

if __name__ == "__main__":
    print("Starting migration to MongoDB...")
    migrate_text("angajati.txt")
    migrate_json("colors.json")
    migrate_json("presets.json")
    migrate_df("istoric_baza.csv")
    migrate_history()
    print("Migration complete!")
