# tests/test_withdraw.py
"""
Usage:
  python -m tests.test_withdraw \
    --chain base \
    --from 0xYourAddr \
    --to 0x000000000000000000000000000000000000dEaD \
    --amount 0.0001 \
    --unit ether \
    --wait
Notes:
  - --chain 支持链ID或别名（如：8453 / base / sepolia）
  - RPC 从 .env (RPC_URL__{chainId}) 或 configs/chains.yaml 读取
"""
from __future__ import annotations

import argparse
import getpass
from typing import Any, Dict

from dotenv import load_dotenv
from web3 import Web3

from configs.chain_registry import resolve_chain_id
from core.withdraw import withdraw_eth, wait_receipt

load_dotenv()


def withdraw_entry(
    chain: int | str,
    from_addr: str,
    to: str,
    amount: float | int | str,
    password: str,
    unit: str = "ether",
    priority_fee_gwei: int | None = None,
    gas_limit: int | None = None,
    wait: bool = False,
    timeout_sec: int = 180,
    poll_sec: int = 3,
) -> Dict[str, Any]:
    """
    测试/脚手架层的出金入口：
      - 将 amount（按 unit）转换为 wei
      - 调用 withdraw_eth 完成 构造→签名→落库→广播
      - 可选等待回执
    """
    chain_id = resolve_chain_id(chain)

    # 金额换算
    if unit.lower() == "wei":
        value_wei = int(amount)
    else:
        # 建议传 str 以避免浮点误差
        value_wei = Web3.to_wei(amount, unit)

    # 出金主流程（构造→签名→落库→广播）
    print(f'withdraw info: chain={chain_id}, from={from_addr}, to={to}, value_wei={value_wei}, unit={unit}, priority_fee_gwei={priority_fee_gwei}, gas_limit={gas_limit}')
    res = withdraw_eth(
        chain_id=chain_id,
        from_addr=from_addr,
        to=to,
        value_wei=int(value_wei),
        password=password,
        priority_fee_gwei=priority_fee_gwei if priority_fee_gwei is not None else None,
        gas_limit=gas_limit,
    )

    # 可选等待回执
    if wait:
        rcpt = wait_receipt(chain_id, res["hash"], timeout_sec=timeout_sec, poll_sec=poll_sec)
        res["receipt"] = rcpt
    return res


def main():
    parser = argparse.ArgumentParser(description="dwallet tests: withdraw (ETH native) CLI")
    parser.add_argument("--chain", required=True, type=str,
                        help="Chain (numeric chainId or alias, e.g. 8453 / base / sepolia)")
    parser.add_argument("--from", dest="from_addr", required=True, help="Sender address (0x...)")
    parser.add_argument("--to", required=True, help="Recipient address (0x...)")
    parser.add_argument("--amount", required=True, help="Amount number in the given unit (recommend string)")
    parser.add_argument("--unit", default="ether", help="Unit of amount: wei/gwei/ether (default: ether)")
    parser.add_argument("--priority-fee", type=float, default=None, help="Tip in gwei (optional; overrides chain default)")
    parser.add_argument("--gas-limit", type=int, default=None, help="Override gas limit (optional)")
    parser.add_argument("--password", help="Keystore password (if omitted, you will be prompted)")
    parser.add_argument("--wait", action="store_true", help="Wait for receipt")
    parser.add_argument("--timeout", type=int, default=180, help="Receipt wait timeout seconds (default: 180)")
    parser.add_argument("--poll", type=int, default=3, help="Receipt polling interval seconds (default: 3)")
    args = parser.parse_args()

    pwd = args.password or getpass.getpass("Keystore password: ")
    result = withdraw_entry(
        chain=args.chain,
        from_addr=args.from_addr,
        to=args.to,
        amount=args.amount,
        password=pwd,
        unit=args.unit,
        priority_fee_gwei=int(args.priority_fee) if args.priority_fee is not None else None,
        gas_limit=args.gas_limit,
        wait=args.wait,
        timeout_sec=args.timeout,
        poll_sec=args.poll,
    )
    print("tx hash:", result["hash"])
    if args.wait:
        print("receipt:", result.get("receipt"))


if __name__ == "__main__":
    main()
