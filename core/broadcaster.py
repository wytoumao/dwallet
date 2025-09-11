# core/broadcaster.py
import os, time
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

def send_raw_tx(chain_id: int, raw_hex: str) -> str:
    w3 = _make_w3(chain_id)
    tx_hash = w3.eth.send_raw_transaction(raw_hex)
    return tx_hash.hex()

def wait_receipt(chain_id: int, tx_hash: str, timeout_sec: int = 120, poll_sec: int = 3):
    w3 = _make_w3(chain_id)
    deadline = time.time() + timeout_sec
    print(f"Waiting for transaction {tx_hash} to be mined...")

    while time.time() < deadline:
        try:
            r = w3.eth.get_transaction_receipt(tx_hash)
            if r:  # type: ignore
                print(f"Transaction confirmed! Block: {r.get('blockNumber')}, Status: {r.get('status')}")
                return dict(r)
        except Exception as e:
            # Handle TransactionNotFound and other temporary errors gracefully
            if "not found" in str(e).lower():
                print(f"Transaction still pending... (checking again in {poll_sec}s)")
            else:
                print(f"Error checking receipt: {e} (retrying in {poll_sec}s)")

        time.sleep(poll_sec)

    print(f"Timeout after {timeout_sec}s. Transaction may still be pending.")
    print(f"Check manually at: https://basescan.org/tx/{tx_hash}")
    return None