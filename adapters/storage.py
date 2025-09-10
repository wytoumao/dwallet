# dwallet/adapters/storage.py
import os
import sqlite3
import time

DB_URL = os.getenv("DB_URL", "sqlite:///./data/wallet.db")
DB_PATH = DB_URL.replace("sqlite:///", "")

def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    with _conn() as cx:
        cx.execute("""
        CREATE TABLE IF NOT EXISTS accounts(
          address TEXT PRIMARY KEY,
          keystore_path TEXT NOT NULL,
          label TEXT,
          created_at INTEGER NOT NULL
        );
        """)
        cx.commit()

def insert_account(address: str, keystore_path: str, label: str | None = None):
    with _conn() as cx:
        cx.execute(
            "INSERT INTO accounts(address, keystore_path, label, created_at) VALUES (?, ?, ?, ?)",
            (address.lower(), keystore_path, label, int(time.time()))
        )
        cx.commit()

def get_account(address: str) -> dict | None:
    with _conn() as cx:
        cur = cx.execute(
            "SELECT address, keystore_path, label, created_at FROM accounts WHERE address = ?",
            (address.lower(),)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "address": row[0],
            "keystore_path": row[1],
            "label": row[2],
            "created_at": row[3],
        }

def account_exists(address: str) -> bool:
    return get_account(address) is not None