# api/client_example.py
"""
API客户端使用示例

演示如何通过HTTP请求调用dwallet API
"""
import requests
import json


def call_withdraw_api(
    chain: str,
    from_addr: str,
    to: str,
    amount: str,
    password: str,
    unit: str = "ether",
    wait: bool = True,
    api_base_url: str = "http://127.0.0.1:5000"
):
    """调用提款API"""
    url = f"{api_base_url}/api/withdraw"

    payload = {
        "chain": chain,
        "from_addr": from_addr,
        "to": to,
        "amount": amount,
        "password": password,
        "unit": unit,
        "wait": wait,
        "timeout_sec": 300,  # 5分钟超时
        "poll_sec": 5        # 每5秒检查一次
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=320  # HTTP请求超时比API内部超时稍长
        )

        result = response.json()

        if response.status_code == 200 and result["success"]:
            print("✅ 提款成功!")
            print(f"交易哈希: {result['data']['hash']}")
            if result['data'].get('receipt'):
                receipt = result['data']['receipt']
                print(f"区块号: {receipt.get('blockNumber')}")
                print(f"状态: {'成功' if receipt.get('status') == 1 else '失败'}")
        else:
            print("❌ 提款失败!")
            print(f"错误: {result.get('error', 'unknown')}")
            print(f"消息: {result.get('message', 'No message')}")

        return result

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return {"success": False, "error": "timeout"}
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败，请确保API服务正在运行")
        return {"success": False, "error": "connection_error"}
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return {"success": False, "error": "request_error"}


def check_api_health(api_base_url: str = "http://127.0.0.1:5000"):
    """检查API健康状态"""
    try:
        response = requests.get(f"{api_base_url}/api/health", timeout=10)
        result = response.json()

        if response.status_code == 200:
            print("✅ API服务正常")
            print(f"支持的链: {', '.join(result['supported_chains'])}")
        else:
            print("❌ API服务异常")

        return result
    except Exception as e:
        print(f"❌ 无法连接到API服务: {e}")
        return None


def get_supported_chains(api_base_url: str = "http://127.0.0.1:5000"):
    """获取支持的链信息"""
    try:
        response = requests.get(f"{api_base_url}/api/chains", timeout=10)
        result = response.json()

        if response.status_code == 200 and result["success"]:
            print("支持的链:")
            for chain in result["data"]["chains"]:
                print(f"  - {chain['name']} (ID: {chain['chainId']})")

        return result
    except Exception as e:
        print(f"❌ 获取链信息失败: {e}")
        return None


if __name__ == "__main__":
    # 示例用法
    print("=== dwallet API 客户端示例 ===\n")

    # 1. 检查API健康状态
    print("1. 检查API状态:")
    check_api_health()
    print()

    # 2. 获取支持的链
    print("2. 获取支持的链:")
    get_supported_chains()
    print()

    # 3. 执行提款（示例 - 请修改为你的实际参数）
    print("3. 执行提款示例:")
    print("注意: 请修改下面的参数为你的实际值")

    # 示例参数（请根据实际情况修改）
    example_params = {
        "chain": "base",
        "from_addr": "0x192dad222732231e62f27b74cf3bd2e1c5d575e7",
        "to": "0x395d6fbc07bbc954ba36bbbe5fb7e180d4f173de",
        "amount": "0.000001",
        "password": "your_password_here",  # 请替换为实际密码
        "unit": "ether",
        "wait": True
    }

    print(f"示例参数: {json.dumps(example_params, indent=2)}")

    # 取消注释下面的行来执行实际的API调用
    # result = call_withdraw_api(**example_params)
    # print(f"结果: {json.dumps(result, indent=2)}")
