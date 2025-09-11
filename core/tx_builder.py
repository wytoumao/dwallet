# core/tx_builder.py
from typing import Optional, Dict, Any
import os
from web3 import Web3
from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
from configs.chain_registry import get_chain_config

def _rpc_url_for_chain(chain_id: int) -> str:
    """
    Get RPC URL for chain. First tries environment variable, then falls back to chains.yaml config.
    Environment variable format: RPC_URL__{chain_id}
    """
    # First try environment variable (for custom RPC overrides)
    key = f"RPC_URL__{chain_id}"
    url = os.getenv(key)
    if url:
        return url

    # Fall back to chains.yaml configuration
    try:
        chain_config = get_chain_config(chain_id)
        rpc_urls = chain_config.get('rpc', [])
        if rpc_urls:
            return rpc_urls[0]  # Use first RPC URL
    except ValueError:
        pass

    raise ValueError(f"RPC_URL_NOT_SET: set {key} in .env or configure in chains.yaml")

def _make_w3(chain_id: int) -> Web3:
    w3 = Web3(Web3.HTTPProvider(_rpc_url_for_chain(chain_id), request_kwargs={"timeout": 20}))
    try:
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    except ValueError:
        pass
    return w3

def suggest_fees_1559(w3: Web3, priority_fee_gwei: Optional[int] = 2) -> dict:
    # Use default value if priority_fee_gwei is None
    if priority_fee_gwei is None:
        priority_fee_gwei = 2

    block = w3.eth.get_block("pending")
    base = block.get("baseFeePerGas")
    if base is None:
        gp = int(w3.eth.gas_price)
        return {"baseFeePerGas": None, "maxPriorityFeePerGas": 0, "maxFeePerGas": gp, "legacyGasPrice": gp}
    tip = w3.to_wei(priority_fee_gwei, "gwei")
    max_fee = base * 2 + tip
    return {"baseFeePerGas": int(base), "maxPriorityFeePerGas": int(tip), "maxFeePerGas": int(max_fee)}

def build_tx_1559(
    chain_id: int,
    from_addr: str,
    to: Optional[str],
    value_wei: int = 0,
    data: Optional[str] = None,
    gas_limit: Optional[int] = None,
    priority_fee_gwei: int = 2,
) -> Dict[str, Any]:
    w3 = _make_w3(chain_id)

    # Convert addresses to checksum format early
    from_addr_checksum = Web3.to_checksum_address(from_addr)
    to_checksum = Web3.to_checksum_address(to) if to else None

    nonce = w3.eth.get_transaction_count(from_addr_checksum, "pending")
    fees = suggest_fees_1559(w3, priority_fee_gwei)
    draft = {
        "from": from_addr_checksum,
        "to": to_checksum,
        "value": int(value_wei),
        "data": data if data not in (None, "", "0x", "0X") else None,
        "chainId": int(chain_id),
        "maxFeePerGas": fees["maxFeePerGas"],
        "maxPriorityFeePerGas": fees["maxPriorityFeePerGas"],
        "type": 2,
    }
    if gas_limit is None:
        est = w3.eth.estimate_gas({k: v for k, v in draft.items() if v is not None})
        gas_limit = int(est)
    tx = {**draft, "gas": gas_limit, "nonce": int(nonce)}
    return {k: v for k, v in tx.items() if v is not None}