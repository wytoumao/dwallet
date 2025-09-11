# core/withdraw.py
import time
from typing import Optional, Dict, Any
from web3 import Web3

from core.tx_builder import build_tx_1559, _make_w3, suggest_fees_1559
from core.signer import sign_tx_1559
from core import signer as signer_mod
from adapters.storage import insert_tx_local, update_tx_status

def _ensure_eth_balance_enough(chain_id: int, from_addr: str, value_wei: int, gas_limit: int, max_fee_per_gas: int):
    w3 = _make_w3(chain_id)
    # Convert to checksum address before making Web3 calls
    from_addr_checksum = Web3.to_checksum_address(from_addr)
    bal = int(w3.eth.get_balance(from_addr_checksum))
    need = int(value_wei) + int(gas_limit) * int(max_fee_per_gas)
    if bal < need:
        raise ValueError(f"INSUFFICIENT_FUNDS: balance={bal} need>={need}")

def withdraw_eth(
    chain_id: int,
    from_addr: str,
    to: str,
    value_wei: int,
    password: str,
    priority_fee_gwei: int = 2,
    gas_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    完整出金流程：构造 → 签名 → 落库 → 广播（可选等待回执）
    返回: {"hash","raw","tx"}
    """
    # 1) 构造交易（含 nonce/fee/gas）
    tx = build_tx_1559(chain_id, from_addr, to, value_wei=value_wei,
                       gas_limit=gas_limit, priority_fee_gwei=priority_fee_gwei)

    # 2) 基于最保守的费用检查余额是否足够
    #    注意：effectiveGasPrice = min(maxFee, base+tip)
    fees = suggest_fees_1559(_make_w3(chain_id), priority_fee_gwei)
    _ensure_eth_balance_enough(chain_id, from_addr, value_wei, tx["gas"], fees["maxFeePerGas"])

    # 3) 签名（离线）
    signed = sign_tx_1559(from_addr, password, tx)  # 返回 {"raw","hash","tx"}

    # 4) 落库（SIGNED）
    insert_tx_local(signed["hash"], from_addr, to, value_wei,
                    nonce=tx["nonce"], chain_id=chain_id,
                    status="SIGNED", raw_hex=signed["raw"])

    # 5) 广播
    from core.broadcaster import send_raw_tx
    h2 = send_raw_tx(chain_id, signed["raw"])
    # 正常情况下 h2 == signed["hash"]
    update_tx_status(h2, "BROADCAST", submitted_at=int(time.time()))
    return {"hash": h2, "raw": signed["raw"], "tx": signed["tx"]}

def wait_receipt(chain_id: int, tx_hash: str, timeout_sec: int = 120, poll_sec: int = 3):
    from core.broadcaster import wait_receipt as _wait
    r = _wait(chain_id, tx_hash, timeout_sec, poll_sec)
    if r and int(r.get("status", 0)) == 1:
        update_tx_status(tx_hash, "CONFIRMED")
    return r
# tests/tx_flow.py
"""
CLI: build → sign → broadcast (ETH native withdraw)

Usage:
  python -m tests.tx_flow \
    --chain 11155111 \
    --from 0xYourAddr \
    --to 0x000000000000000000000000000000000000dEaD \
    --amount 0.0001 \
    --unit ether \
    --wait
"""
import argparse
import getpass
from typing import Any, Dict

from web3 import Web3
from core.withdraw import withdraw_eth, wait_receipt


def withdraw_entry(
    chain_id: int,
    from_addr: str,
    to: str,
    amount: float | int | str,
    password: str,
    unit: str = "ether",
    priority_fee_gwei: int = 2,
    gas_limit: int | None = None,
    wait: bool = False,
    timeout_sec: int = 180,
    poll_sec: int = 3,
) -> Dict[str, Any]:
    """
    统一的“出金入口函数”（测试/脚手架层）。负责：
      - 将 amount（按 unit）转换为 wei
      - 调用 withdraw_eth 完成 构造→签名→落库→广播
      - 可选等待回执
    返回: {"hash","raw","tx", "receipt"?(可选)}
    """
    # 金额换算
    if unit.lower() == "wei":
        value_wei = int(amount)
    else:
        value_wei = Web3.to_wei(amount, unit)

    # 出金主流程（构造→签名→落库→广播）
    res = withdraw_eth(
        chain_id=chain_id,
        from_addr=from_addr,
        to=to,
        value_wei=int(value_wei),
        password=password,
        priority_fee_gwei=priority_fee_gwei,
        gas_limit=gas_limit,
    )

    # 可选等待回执
    if wait:
        rcpt = wait_receipt(chain_id, res["hash"], timeout_sec=timeout_sec, poll_sec=poll_sec)
        res["receipt"] = rcpt
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="dwallet tests: withdraw (ETH native) CLI")
    parser.add_argument("--chain", type=int, required=True, help="EIP-155 chainId, e.g. 1 / 8453 / 11155111")
    parser.add_argument("--from", dest="from_addr", required=True, help="Sender address (0x...)")
    parser.add_argument("--to", required=True, help="Recipient address (0x...)")
    parser.add_argument("--amount", required=True, help="Amount number in the given unit (recommend string)")
    parser.add_argument("--unit", default="ether", help="Unit of amount: wei/gwei/ether (default: ether)")
    parser.add_argument("--priority-fee", type=int, default=2, help="Tip in gwei (default: 2)")
    parser.add_argument("--gas-limit", type=int, default=None, help="Override gas limit (optional)")
    parser.add_argument("--password", help="Keystore password (if omitted, you will be prompted)")
    parser.add_argument("--wait", action="store_true", help="Wait for receipt")
    parser.add_argument("--timeout", type=int, default=180, help="Receipt wait timeout seconds (default: 180)")
    parser.add_argument("--poll", type=int, default=3, help="Receipt polling interval seconds (default: 3)")
    args = parser.parse_args()

    pwd = args.password or getpass.getpass("Keystore password: ")
    result = withdraw_entry(
        chain_id=args.chain,
        from_addr=args.from_addr,
        to=args.to,
        amount=args.amount,
        password=pwd,
        unit=args.unit,
        priority_fee_gwei=args.priority_fee,
        gas_limit=args.gas_limit,
        wait=args.wait,
        timeout_sec=args.timeout,
        poll_sec=args.poll,
    )
    print("tx hash:", result["hash"])
    if args.wait:
        print("receipt:", result.get("receipt"))