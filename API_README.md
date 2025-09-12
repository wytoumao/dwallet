# API_README.md
# dwallet HTTP API 接口文档

## 概述

这个HTTP API提供了dwallet提款功能的REST接口，让你可以通过HTTP请求来执行区块链提款操作。

## 启动API服务

### 方法1：使用server.py启动
```bash
cd /Users/bo/Desktop/github_project/dwallet
python api/server.py
```

### 方法2：使用模块启动
```bash
cd /Users/bo/Desktop/github_project/dwallet
python -m api.server
```

### 方法3：直接启动Flask应用
```bash
cd /Users/bo/Desktop/github_project/dwallet
python -m api.withdraw_api
```

服务默认运行在 `http://127.0.0.1:5000`

## API接口

### 1. 健康检查
**GET** `/api/health`

检查API服务状态和获取支持的链列表。

**响应示例:**
```json
{
  "status": "ok",
  "service": "dwallet-api",
  "supported_chains": ["1", "8453", "84532", "11155111", "ethereum", "base", "base-sepolia", "sepolia"]
}
```

### 2. 获取支持的链
**GET** `/api/chains`

获取详细的链配置信息。

**响应示例:**
```json
{
  "success": true,
  "data": {
    "chains": [
      {
        "chainId": 8453,
        "name": "Base Mainnet",
        "type": "l2-op",
        "rpc": ["https://mainnet.base.org"]
      }
    ],
    "supported_aliases": ["base", "sepolia", "ethereum"]
  }
}
```

### 3. 执行提款 ⭐️
**POST** `/api/withdraw`

执行区块链提款操作。

**请求头:**
```
Content-Type: application/json
```

**请求体:**
```json
{
  "chain": "base",                    // 必需：链名称或链ID
  "from_addr": "0x...",              // 必需：发送方地址
  "to": "0x...",                     // 必需：接收方地址
  "amount": "0.001",                 // 必需：金额（推荐字符串）
  "password": "your_password",       // 必需：keystore密码
  "unit": "ether",                   // 可选：单位，默认ether
  "priority_fee_gwei": 2,            // 可选：优先费用（gwei）
  "gas_limit": 21000,                // 可选：gas限制
  "wait": true,                      // 可选：是否等待确认，默认false
  "timeout_sec": 180,                // 可选：等���超时时间，默认180s
  "poll_sec": 3                      // 可选：轮询间隔，默认3s
}
```

**成功响应:**
```json
{
  "success": true,
  "data": {
    "chain_id": 8453,
    "hash": "0x...",                 // 交易哈希
    "raw": "0x...",                  // 原始交易数据
    "tx": {                          // 交易详情
      "from": "0x...",
      "to": "0x...",
      "value": 1000000000000,
      "gas": 21000
    },
    "receipt": {                     // 交易回执（仅当wait=true时）
      "blockNumber": 12345,
      "status": 1,
      "gasUsed": 21000
    }
  }
}
```

**错误响应:**
```json
{
  "success": false,
  "error": "bad_request",
  "message": "Missing required fields: ['password']"
}
```

## 错误码说明

| 错误码 | HTTP状态码 | 说明 |
|--------|------------|------|
| `bad_request` | 400 | 请求参数错误 |
| `authentication_failed` | 401 | keystore密码错误 |
| `account_not_found` | 404 | 账户不存在 |
| `insufficient_funds` | 400 | 余额不足 |
| `validation_error` | 400 | 参数验证失败 |
| `internal_server_error` | 500 | 服务器内部错误 |

## 使��示例

### curl命令示例
```bash
# 健康检查
curl http://127.0.0.1:5000/api/health

# 执行提款
curl -X POST http://127.0.0.1:5000/api/withdraw \
  -H "Content-Type: application/json" \
  -d '{
    "chain": "base",
    "from_addr": "0x192dad222732231e62f27b74cf3bd2e1c5d575e7",
    "to": "0x395d6fbc07bbc954ba36bbbe5fb7e180d4f173de",
    "amount": "0.000001",
    "password": "xc,00010",
    "unit": "ether",
    "wait": true
  }'
```

### Python客户端示例
参考 `api/client_example.py` 文件中的详细示例。

## 环境变量配置

可以通过环境变量或`.env`文件配置：

```bash
# API服务配置
API_HOST=127.0.0.1        # API监听地址
API_PORT=5000             # API监听端口
API_DEBUG=true            # 是否开启调试模式

# 自定义RPC URL（可选）
RPC_URL__8453=https://your-custom-base-rpc.com
RPC_URL__1=https://your-custom-ethereum-rpc.com
```

## 安全注意事项

⚠️ **重要安全提醒:**

1. **生产环境**: 不要在生产环境中使用 `debug=True`
2. **密码安全**: API会接收keystore密码，确保使用HTTPS
3. **网络访问**: 建议限制API服务的网络访问范围
4. **日志记录**: 确保密码不会被记录到日志中
5. **防火墙**: 配置适当的防火墙规则

## 故障排除

### 常见问题

1. **数据库锁定错误**: 确保没有其他进程在使用wallet.db
2. **RPC连接失败**: 检查网络连接和RPC URL配置
3. **密码错误**: 确认keystore密码正确
4. **余额不足**: 确认账户有足够的ETH支付交易费用

### 调试模式

启动API时使用调试模式获取详细错误信息：
```bash
API_DEBUG=true python api/server.py
```
