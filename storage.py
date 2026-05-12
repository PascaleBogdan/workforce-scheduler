import os
import json
import pandas as pd
import streamlit as st
import io

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

HISTORY_DIR = "istoric"

def get_db():
    if "MONGODB_URI" in st.secrets and MongoClient is not None:
        client = MongoClient(st.secrets["MONGODB_URI"])
        return client["workforce_scheduler"]
    return None

def load_text(filename):
    db = get_db()
    if db is not None:
        doc = db["settings"].find_one({"_id": filename})
        if doc and "data" in doc:
            return doc["data"]
        return None
    else:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        return None

def save_text(filename, content):
    db = get_db()
    if db is not None:
        db["settings"].update_one(
            {"_id": filename},
            {"$set": {"data": content}},
            upsert=True
        )
    else:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

def load_json(filename):
    db = get_db()
    if db is not None:
        doc = db["settings"].find_one({"_id": filename})
        if doc and "data" in doc:
            return doc["data"]
        return None
    else:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return None
        return None

def save_json(filename, data):
    db = get_db()
    if db is not None:
        db["settings"].update_one(
            {"_id": filename},
            {"$set": {"data": data}},
            upsert=True
        )
    else:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def load_df(filename):
    db = get_db()
    if db is not None:
        doc = db["settings"].find_one({"_id": filename})
        if doc and "data" in doc:
            return pd.DataFrame(doc["data"])
        return None
    else:
        if os.path.exists(filename):
            try:
                return pd.read_csv(filename)
            except:
                return None
        return None

def save_df(filename, df):
    db = get_db()
    if db is not None:
        data = df.to_dict(orient="records")
        db["settings"].update_one(
            {"_id": filename},
            {"$set": {"data": data}},
            upsert=True
        )
    else:
        df.to_csv(filename, index=False)

def list_history_files():
    db = get_db()
    if db is not None:
        docs = db["istoric"].find({"_id": {"$regex": r"^orar_.*\.csv$"}})
        return sorted([doc["_id"] for doc in docs], reverse=True)
    else:
        if not os.path.exists(HISTORY_DIR):
            return []
        return sorted([f for f in os.listdir(HISTORY_DIR) if f.startswith("orar_") and f.endswith(".csv")], reverse=True)

def load_history_df(fname):
    db = get_db()
    if db is not None:
        doc = db["istoric"].find_one({"_id": fname})
        if doc and "data" in doc:
            return pd.DataFrame(doc["data"])
        return None
    else:
        path = os.path.join(HISTORY_DIR, fname)
        if os.path.exists(path):
            return pd.read_csv(path)
        return None

def save_history_df(fname, df):
    db = get_db()
    if db is not None:
        data = df.to_dict(orient="records")
        db["istoric"].update_one(
            {"_id": fname},
            {"$set": {"data": data}},
            upsert=True
        )
    else:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        df.to_csv(os.path.join(HISTORY_DIR, fname), index=False)

def load_history_json(fname):
    db = get_db()
    if db is not None:
        doc = db["istoric"].find_one({"_id": fname})
        if doc and "data" in doc:
            return doc["data"]
        return None
    else:
        path = os.path.join(HISTORY_DIR, fname)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return None
        return None

def save_history_json(fname, data):
    db = get_db()
    if db is not None:
        db["istoric"].update_one(
            {"_id": fname},
            {"$set": {"data": data}},
            upsert=True
        )
    else:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        with open(os.path.join(HISTORY_DIR, fname), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

def delete_history_files(fname):
    db = get_db()
    json_name = fname.replace(".csv", ".json")
    if db is not None:
        db["istoric"].delete_one({"_id": fname})
        db["istoric"].delete_one({"_id": json_name})
    else:
        try:
            os.remove(os.path.join(HISTORY_DIR, fname))
            json_path = os.path.join(HISTORY_DIR, json_name)
            if os.path.exists(json_path):
                os.remove(json_path)
        except Exception:
            pass
