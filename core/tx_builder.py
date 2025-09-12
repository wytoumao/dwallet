# core/tx_builder.py
from typing import Optional, Dict, Any
import os
from web3 import Web3
from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware
from configs.chain_registry import get_chain_config
from core.logger import get_logger

logger = get_logger()

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

def suggest_fees_1559(w3: Web3, priority_fee_gwei: Optional[int] = None) -> dict:
    """
    建议 EIP-1559 费用参数

    Args:
        w3: Web3实例
        priority_fee_gwei: 优先费用(gwei)，如果为None则自动获取推荐值
    """

    # 如果没有指定priority_fee，尝试动态获取
    if priority_fee_gwei is None:
        try:
            # 方法1: 使用 eth_maxPriorityFeePerGas (EIP-1559标准方法)
            max_priority_fee_wei = w3.eth.max_priority_fee
            priority_fee_gwei = w3.from_wei(max_priority_fee_wei, 'gwei')
            logger.debug(f"🔍 动态获取优先费用: {priority_fee_gwei} gwei (来源: eth_maxPriorityFeePerGas)")
        except Exception as e1:
            logger.debug(f"🔍 eth_maxPriorityFeePerGas 失败: {e1}")
            try:
                # 方法2: 使用 eth_feeHistory 分析历史数据
                fee_history = w3.eth.fee_history(20, 'latest', [25, 50, 75])  # 获取最近20个块的费用历史
                if fee_history and fee_history.get('reward'):
                    # 使用第50百分位作为推荐值
                    recent_tips = [reward[1] for reward in fee_history['reward'] if reward and len(reward) > 1]
                    if recent_tips:
                        avg_tip = sum(recent_tips) // len(recent_tips)
                        priority_fee_gwei = w3.from_wei(avg_tip, 'gwei')
                        logger.debug(f"🔍 动态获取优先费用: {priority_fee_gwei} gwei (来源: eth_feeHistory)")
                    else:
                        raise Exception("No valid fee history data")
                else:
                    raise Exception("No fee history available")
            except Exception as e2:
                logger.debug(f"🔍 eth_feeHistory 失败: {e2}")
                try:
                    # 方法3: 基于当前gas price估算
                    current_gas_price = w3.eth.gas_price
                    current_block = w3.eth.get_block('latest')
                    base_fee = current_block.get('baseFeePerGas', 0)

                    if base_fee > 0:
                        # 估算tip = (gasPrice - baseFee) * 0.8 (保守估计)
                        estimated_tip = max((current_gas_price - base_fee) * 0.8, w3.to_wei(0.1, 'gwei'))
                        priority_fee_gwei = w3.from_wei(estimated_tip, 'gwei')
                        logger.debug(f"🔍 动态获取优先费用: {priority_fee_gwei} gwei (来源: gasPrice估算)")
                    else:
                        raise Exception("No base fee available")
                except Exception as e3:
                    logger.debug(f"🔍 gasPrice估算失败: {e3}")
                    # 方法4: 使用保守的默认值
                    priority_fee_gwei = 2.0
                    logger.debug(f"🔍 使用默认优先费用: {priority_fee_gwei} gwei (所有动态方法都失败)")

    # 确保priority_fee_gwei是合理的数值
    priority_fee_gwei = max(float(priority_fee_gwei), 0.0001)  # 最小0.001 gwei
    priority_fee_gwei = min(float(priority_fee_gwei), 2.0)  # 最大100 gwei

    block = w3.eth.get_block("pending")
    base = block.get("baseFeePerGas")
    if base is None:
        # 不支持EIP-1559的网络，使用legacy gas price
        gp = int(w3.eth.gas_price)
        logger.debug(f"🔍 Legacy网络，使用gasPrice: {w3.from_wei(gp, 'gwei')} gwei")
        return {"baseFeePerGas": None, "maxPriorityFeePerGas": 0, "maxFeePerGas": gp, "legacyGasPrice": gp}

    tip = w3.to_wei(priority_fee_gwei, "gwei")
    max_fee = base * 2 + tip

    logger.debug(f"🔍 费用计算: baseFee={w3.from_wei(base, 'gwei'):.3f} gwei, tip={priority_fee_gwei:.3f} gwei, maxFee={w3.from_wei(max_fee, 'gwei'):.3f} gwei")

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
        try:
            # 先检查账户余额是否足够
            balance = w3.eth.get_balance(from_addr_checksum)
            logger.debug(f"🔍 账户余额: {balance} wei ({Web3.from_wei(balance, 'ether')} ETH)")
            logger.debug(f"🔍 转账金额: {value_wei} wei ({Web3.from_wei(value_wei, 'ether')} ETH)")

            # 尝试估算gas，但先移除一些可能导致问题的字段
            estimate_params = {
                "from": from_addr_checksum,
                "to": to_checksum,
                "value": int(value_wei),
            }
            # 只有在有data的时候才加入data字段
            if draft.get("data"):
                estimate_params["data"] = draft["data"]

            logger.debug(f"🔍 Gas估算参数: {estimate_params}")
            est = w3.eth.estimate_gas(estimate_params)
            logger.debug(f"🔍 Gas估算: 原始估算={est}")
            # 添加 50% 的安全缓冲区，防止 gas 估算不足
            gas_limit = int(est * 1.5)
            # 确保最小 gas 为 21000（简单转账）或 50000（合约交互）
            min_gas = 50000 if draft.get("data") else 21000
            gas_limit = max(gas_limit, min_gas)
            logger.debug(f"🔍 Gas最终: 缓冲后={int(est * 1.5)}, 最小值={min_gas}, 最终={gas_limit}")
        except Exception as e:
            logger.debug(f"🔍 Gas估算失败: {e}")
            logger.debug(f"🔍 错误类型: {type(e)}")
            # 如果估算失败，使用默认值
            min_gas = 100000 if draft.get("data") else 50000
            gas_limit = min_gas
            logger.debug(f"🔍 Gas回退: 使用默认值={gas_limit}")
    else:
        logger.debug(f"🔍 Gas传入: 使用预设值={gas_limit}")
    tx = {**draft, "gas": gas_limit, "nonce": int(nonce)}
    return {k: v for k, v in tx.items() if v is not None}