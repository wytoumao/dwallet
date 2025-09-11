# core/signer.py
import json
import os
from typing import Any, Dict

from eth_account import Account
from eth_account.messages import encode_defunct, encode_typed_data
from hexbytes import HexBytes

from adapters.storage import get_account

Account.enable_unaudited_hdwallet_features()

# ---------- 内部：从本地 keystore 解锁私钥 ----------
def _load_privkey_from_keystore(address: str, password: str) -> bytes:
    meta = get_account(address)
    if not meta:
        raise ValueError("ACCOUNT_NOT_FOUND")
    ks_path = meta["keystore_path"]
    if not os.path.exists(ks_path):
        raise ValueError("KEYSTORE_MISSING")
    with open(ks_path, "r", encoding="utf-8") as f:
        ks_json = json.load(f)
    try:
        return Account.decrypt(ks_json, password)  # bytes
    except Exception as e:
        raise ValueError("BAD_PASSWORD") from e

def _acct_from_keystore(address: str, password: str) -> Account:
    priv = _load_privkey_from_keystore(address, password)
    return Account.from_key(priv)

# ---------- personal_sign（EIP-191） ----------
def personal_sign(address: str, password: str, message: str | bytes) -> Dict[str, Any]:
    """
    与 MetaMask personal_sign 等价：对 "\x19Ethereum Signed Message:\n{len(m)}" || m 签名
    输入 message 可以是 str（utf-8）或 bytes
    返回: { "address", "messageHash", "signature", "mode": "personal_sign" }
    """
    acct = _acct_from_keystore(address, password)
    if isinstance(message, str):
        msg = encode_defunct(text=message)
    else:
        msg = encode_defunct(primitive=message)
    signed = acct.sign_message(msg)
    return {
        "address": acct.address,
        "messageHash": signed.messageHash.hex(),
        "signature": signed.signature.hex(),
        "mode": "personal_sign",
    }

# ---------- eth_sign（对原始32字节哈希签名） ----------
def eth_sign(address: str, password: str, message_hash_hex: str) -> Dict[str, Any]:
    """
    直接对 32字节哈希签名（不是 personal_sign）。适用于链下验签已固定哈希的场景。
    message_hash_hex: 0x 前缀的32字节十六进制字符串
    """
    h = HexBytes(message_hash_hex)
    if len(h) != 32:
        raise ValueError("BAD_MESSAGE_HASH_LENGTH")
    acct = _acct_from_keystore(address, password)
    sig = acct.sign_hash(h)
    return {
        "address": acct.address,
        "messageHash": h.hex(),
        "signature": sig.signature.hex(),
        "mode": "eth_sign",
    }

# ---------- EIP-712 Typed Data v4 ----------
def sign_typed_data(address: str, password: str, typed_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    typed_data 为符合 EIP-712（v4）的 dict（含 types / domain / primaryType / message）
    返回: { "address", "signature", "mode": "eip712" }
    """
    acct = _acct_from_keystore(address, password)
    msg = encode_typed_data(primitive=typed_data)  # 计算 EIP-712 digest
    signed = acct.sign_message(msg)
    return {
        "address": acct.address,
        "signature": signed.signature.hex(),
        "mode": "eip712",
    }

# ---------- EIP-1559 交易离线签名（type 0x2） ----------
def sign_tx_1559(
    address: str,
    password: str,
    tx: Dict[str, Any],
) -> Dict[str, Any]:
    """
    期待的 tx 字段（全部为 wei / 原始值，已做 gas/nonce/费率计算）：
      {
        "chainId": 1,
        "nonce": 0,
        "to": "0x...",             # 合约创建可省略或置为 None
        "value": 0,                # int(wei)
        "data": "0x...",           # 可选
        "gas": 21000,
        "maxFeePerGas": 1500000000,
        "maxPriorityFeePerGas": 2000000,
        "type": 2                  # 可省略，函数内会强制为 2
      }
    返回: { "raw": "0x...", "hash": "0x...", "tx": {...} }
    """
    # 规范化
    tx_norm = dict(tx)
    tx_norm["type"] = 2
    # eth-account 要求不存在 None 字段；清理掉为 None 的键
    tx_norm = {k: v for k, v in tx_norm.items() if v is not None}

    required = ["chainId", "nonce", "gas", "maxFeePerGas", "maxPriorityFeePerGas"]
    missing = [k for k in required if k not in tx_norm]
    if missing:
        raise ValueError(f"MISSING_FIELDS: {missing}")

    acct = _acct_from_keystore(address, password)
    if acct.address.lower() != address.lower():
        # 防止用户传错地址与 keystore 不匹配（比如导入了另一个地址的 ks）
        raise ValueError("ADDRESS_MISMATCH")

    signed = acct.sign_transaction(tx_norm)
    return {
        "raw": signed.raw_transaction.hex(),
        "hash": signed.hash.hex(),
        "tx": {**tx_norm, "from": acct.address},
    }