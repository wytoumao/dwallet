# dwallet/core/keyring.py
import json
import os
from datetime import datetime, timezone
from typing import Optional, Tuple

from eth_account import Account
from mnemonic import Mnemonic

from adapters.storage import init_db, insert_account, account_exists

# 允许 HD 派生（eth-account 的“未审计功能”）
Account.enable_unaudited_hdwallet_features()

DEFAULT_BASE_PATH = "m/44'/60'/0'/0"   # BIP44: 账户外链
DEFAULT_INDEX = 0
KEYSTORE_DIR = os.getenv("KEYSTORE_DIR", "./data/keystore")

# 确保库与目录就绪
init_db()
os.makedirs(KEYSTORE_DIR, exist_ok=True)

def _utc_keystore_filename(address: str) -> str:
    # Geth 命名：UTC--YYYY-MM-DDTHH-MM-SSZ--<address>
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    return f"UTC--{ts}--{address.lower()}.json"

def _ensure_password_ok(pw: str):
    if not isinstance(pw, str) or len(pw) < 8:
        raise ValueError("Password too short (min 8 chars).")

def _write_keystore(ks_json: dict, address: str) -> str:
    fname = _utc_keystore_filename(address)
    fpath = os.path.join(KEYSTORE_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(ks_json, f, ensure_ascii=False)
    return fpath

def derive_path(base_path: str = DEFAULT_BASE_PATH, index: int = DEFAULT_INDEX) -> str:
    return f"{base_path}/{index}"

def create_wallet(
    password: str,
    mnemonic: Optional[str] = None,
    base_path: str = DEFAULT_BASE_PATH,
    index: int = DEFAULT_INDEX,
    label: Optional[str] = None,
) -> Tuple[str, Optional[str], str, str]:
    """
    生成/导入助记词 → BIP44 (base_path/index) 派生 → Keystore v3 加密落盘 → 记录数据库
    返回: (address, mnemonic_if_new, keystore_path, derivation_path)
    """
    _ensure_password_ok(password)

    # 助记词：随机生成 or 校验导入
    m = Mnemonic("english")
    is_new = mnemonic is None
    if is_new:
        mnemonic = m.generate(strength=128)  # 12 words
    if not m.check(mnemonic):
        raise ValueError("Invalid mnemonic")

    # 路径与派生
    path = derive_path(base_path, index)
    acct = Account.from_mnemonic(mnemonic, account_path=path)
    address = acct.address

    if account_exists(address):
        raise ValueError("ACCOUNT_EXISTS")

    # Keystore v3（默认 scrypt）
    ks = Account.encrypt(acct.key, password)
    keystore_path = _write_keystore(ks, address)

    # 写库（不保存助记词/私钥）
    insert_account(address, keystore_path, label=label)

    # 仅新生成时回显助记词
    return address, (mnemonic if is_new else None), keystore_path, path

def import_private_key(password: str, private_key_hex: str, label: Optional[str] = None) -> tuple[str, str]:
    """
    （开发期可用）用私钥直接生成 keystore 并入库；不回显私钥。
    返回: (address, keystore_path)
    """
    _ensure_password_ok(password)
    acct = Account.from_key(private_key_hex)
    address = acct.address
    if account_exists(address):
        raise ValueError("ACCOUNT_EXISTS")
    ks = Account.encrypt(acct.key, password)
    keystore_path = _write_keystore(ks, address)
    insert_account(address, keystore_path, label=label)
    return address, keystore_path

def preview_derived_address(mnemonic: str, base_path: str = DEFAULT_BASE_PATH, index: int = 0) -> str:
    """
    只用于“看地址不落库”，方便你在创建前预览不同 index 的地址。
    """
    m = Mnemonic("english")
    if not m.check(mnemonic):
        raise ValueError("Invalid mnemonic")
    path = derive_path(base_path, index)
    acct = Account.from_mnemonic(mnemonic, account_path=path)
    return acct.address