# dwallet/adapters/storage.py
import os
import sqlite3
import time

# 强制所有模块使用同一个数据库文件：项目根目录下的 data/wallet.db
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "wallet.db")

print(f"使用数据库: {DB_PATH}")  # 调试信息

def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    cx = sqlite3.connect(DB_PATH, isolation_level=None)  # autocommit
    # Improve concurrency & durability tradeoffs for SQLite
    cx.execute("PRAGMA journal_mode=WAL;")
    cx.execute("PRAGMA synchronous=NORMAL;")
    cx.execute("PRAGMA foreign_keys=ON;")
    return cx

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
        cx.execute("""
        CREATE TABLE IF NOT EXISTS tx_local(
          hash TEXT PRIMARY KEY,
          sender TEXT NOT NULL,
          [to] TEXT,
          value_wei TEXT NOT NULL,
          nonce INTEGER NOT NULL,
          chain_id INTEGER NOT NULL,
          status TEXT,
          raw BLOB,
          submitted_at INTEGER,
          updated_at INTEGER
        );
        """)
        cx.execute("CREATE INDEX IF NOT EXISTS idx_tx_sender_chain_nonce ON tx_local(sender, chain_id, nonce);")
        cx.commit()

def insert_account(address: str, keystore_path: str, label: str | None = None):
    try:
        with _conn() as cx:
            cx.execute(
                "INSERT INTO accounts(address, keystore_path, label, created_at) VALUES (?, ?, ?, strftime('%s','now'))",
                (address.lower(), keystore_path, label)
            )
            cx.commit()
    except sqlite3.IntegrityError as e:
        raise ValueError("ACCOUNT_EXISTS") from e

def get_account(address: str) -> dict | None:
    with _conn() as cx:
        cur = cx.execute(
            "SELECT address, keystore_path, label, created_at FROM accounts WHERE address = ?",
            (address.lower(),)  # 修复：加上逗号使其成为元组
        )
        row = cur.fetchone()
        print(row)
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


# --- tx_local DAO helpers ---
def insert_tx_local(
    hash_hex: str,
    sender: str,
    to: str | None,
    value_wei: int | str,
    nonce: int,
    chain_id: int,
    status: str = "SIGNED",
    raw_hex: str | None = None,
    submitted_at: int | None = None,
):
    """Insert a locally signed/broadcast tx record."""
    ts = int(time.time())
    with _conn() as cx:
        cx.execute(
            "INSERT INTO tx_local(hash, sender, [to], value_wei, nonce, chain_id, status, raw, submitted_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                hash_hex.lower(),
                sender.lower(),
                (to.lower() if to else None),
                str(value_wei),
                int(nonce),
                int(chain_id),
                status,
                bytes.fromhex(raw_hex[2:]) if (raw_hex and raw_hex.startswith('0x')) else None,
                (int(submitted_at) if submitted_at is not None else None),
                ts,
            ),
        )
        cx.commit()

def update_tx_status(hash_hex: str, status: str, submitted_at: int | None = None):
    """Update tx status and timestamps."""
    ts = int(time.time())
    with _conn() as cx:
        cx.execute(
            "UPDATE tx_local SET status = ?, submitted_at = COALESCE(?, submitted_at), updated_at = ? WHERE hash = ?",
            (status, submitted_at, ts, hash_hex.lower()),
        )
        cx.commit()

def get_tx(hash_hex: str) -> dict | None:
    with _conn() as cx:
        cur = cx.execute(
            "SELECT hash, sender, [to], value_wei, nonce, chain_id, status, raw, submitted_at, updated_at "
            "FROM tx_local WHERE hash = ?",
            (hash_hex.lower(),)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "hash": row[0],
            "sender": row[1],
            "to": row[2],
            "value_wei": row[3],
            "nonce": row[4],
            "chain_id": row[5],
            "status": row[6],
            "raw": row[7],
            "submitted_at": row[8],
            "updated_at": row[9],
        }

def max_local_nonce(sender: str, chain_id: int) -> int | None:
    """Return the max nonce we have recorded locally for a sender on a chain, or None."""
    with _conn() as cx:
        cur = cx.execute(
            "SELECT MAX(nonce) FROM tx_local WHERE sender = ? AND chain_id = ?",
            (sender.lower(), int(chain_id)),
        )
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None