# api/withdraw_api.py
"""
HTTP API接口 for dwallet withdraw功能

Usage:
  python -m api.withdraw_api

API Endpoints:
  POST /api/withdraw - 执行提款操作
  GET /api/health - 健康检查
"""
from __future__ import annotations

import traceback
from typing import Any, Dict

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest

from tests.test_withdraw import withdraw_entry
from configs.chain_registry import resolve_chain_id, list_supported_chains
from adapters.storage import init_db

app = Flask(__name__)

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        "status": "ok",
        "service": "dwallet-api",
        "supported_chains": list_supported_chains()
    })

@app.route('/api/withdraw', methods=['POST'])
def api_withdraw():
    """
    提款API接口

    Request Body (JSON):
    {
        "chain": "base" | 8453,           // 链名称或链ID
        "from_addr": "0x...",             // 发送方地址
        "to": "0x...",                    // 接收方地址
        "amount": "0.001",                // 金额（字符串推荐）
        "password": "your_password",      // keystore密码
        "unit": "ether",                  // 可选，默认ether
        "priority_fee_gwei": 2,           // 可选，优先费用
        "gas_limit": 21000,               // 可选，gas限制
        "wait": true,                     // 可选，是否等待确认
        "timeout_sec": 180,               // 可选，等待超时时间
        "poll_sec": 3                     // 可选，轮询间隔
    }

    Response:
        "amount": "0.001",                // 金额（字���串推荐）
        "success": true,
        "data": {
            "hash": "0x...",
            "raw": "0x...",
            "tx": {...},
            "receipt": {...}  // 如果wait=true
        }
    }
    """
    try:
        # 检查Content-Type
        if not request.is_json:
            raise BadRequest("Content-Type must be application/json")

        data = request.get_json()
        if not data:
            raise BadRequest("Request body is required")

        # 验证必需参数
        required_fields = ['chain', 'from_addr', 'to', 'amount', 'password']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise BadRequest(f"Missing required fields: {missing_fields}")

        # 提取参数
        chain = data['chain']
        from_addr = data['from_addr']
        to = data['to']
        amount = data['amount']
        password = data['password']

        # 可选参数
        unit = data.get('unit', 'ether')
        priority_fee_gwei = data.get('priority_fee_gwei')
        gas_limit = data.get('gas_limit')
        wait = data.get('wait', False)
        timeout_sec = data.get('timeout_sec', 180)
        poll_sec = data.get('poll_sec', 3)

        # 验证链ID
        try:
            chain_id = resolve_chain_id(chain)
        except ValueError as e:
            raise BadRequest(f"Invalid chain: {e}")

        # 验证地址格式（简单检查）
        if not (from_addr.startswith('0x') and len(from_addr) == 42):
            raise BadRequest("Invalid from_addr format")
        if not (to.startswith('0x') and len(to) == 42):
            raise BadRequest("Invalid to address format")

        # 执行提款
        result = withdraw_entry(
            chain=chain,
            from_addr=from_addr,
            to=to,
            amount=amount,
            password=password,
            unit=unit,
            priority_fee_gwei=priority_fee_gwei,
            gas_limit=gas_limit,
            wait=wait,
            timeout_sec=timeout_sec,
            poll_sec=poll_sec
        )

        # 处理返回数据，确保所有数据都是JSON可序列化的
        def serialize_for_json(obj):
            """递归处理对象，将HexBytes等转换为字符串"""
            if hasattr(obj, 'hex'):  # HexBytes对象
                return obj.hex()
            elif isinstance(obj, bytes):
                return obj.hex()
            elif isinstance(obj, dict):
                return {k: serialize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_for_json(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(serialize_for_json(item) for item in obj)
            else:
                return obj

        # 序列化result数据
        serialized_result = serialize_for_json(result)

        return jsonify({
            "success": True,
            "data": {
                "chain_id": chain_id,
                "hash": serialized_result["hash"],
                "raw": serialized_result["raw"],
                "tx": serialized_result["tx"],
                "receipt": serialized_result.get("receipt")
            }
        })

    except BadRequest as e:
        return jsonify({
            "success": False,
            "error": "bad_request",
            "message": str(e)
        }), 400

    except ValueError as e:
        # 处理业务逻辑错误（如密码错误、余额不足等）
        error_msg = str(e)
        if "BAD_PASSWORD" in error_msg:
            return jsonify({
                "success": False,
                "error": "authentication_failed",
                "message": "Invalid keystore password"
            }), 401
        elif "INSUFFICIENT_FUNDS" in error_msg:
            return jsonify({
                "success": False,
                "error": "insufficient_funds",
                "message": error_msg
            }), 400
        elif "ACCOUNT_NOT_FOUND" in error_msg:
            return jsonify({
                "success": False,
                "error": "account_not_found",
                "message": "Account not found in local storage"
            }), 404
        else:
            return jsonify({
                "success": False,
                "error": "validation_error",
                "message": error_msg
            }), 400

    except Exception as e:
        # 处理未预期的错误
        app.logger.error(f"Unexpected error in withdraw API: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "internal_server_error",
            "message": "An unexpected error occurred"
        }), 500


@app.route('/api/chains', methods=['GET'])
def api_chains():
    """获取支持的链列表"""
    try:
        from configs.chain_registry import load_chains_config
        chains = load_chains_config()

        return jsonify({
            "success": True,
            "data": {
                "chains": chains,
                "supported_aliases": list_supported_chains()
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "internal_server_error",
            "message": str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "not_found",
        "message": "Endpoint not found"
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "error": "method_not_allowed",
        "message": "Method not allowed"
    }), 405


if __name__ == '__main__':
    # 开发环境运行
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True
    )
