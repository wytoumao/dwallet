# dwallet — ETH Wallet Backend (Python / FastAPI)

一个**后端先行**的去中心化钱包内核，面向浏览器插件或移动端前端：
- 以 **Python + FastAPI** 提供 REST API；
- 通过 **web3.py / eth-account** 完成账户、签名、交易、余额、历史等核心能力；
- 坚持 **“私钥不出后端”** 的安全设计，可平滑接入远程签名（Web3Signer/HSM）与多链扩展。

> 当前目标：**先跑通 ETH 单链 MVP**，再按路线上线授权/风险、ENS、ERC-4337 等高级能力。

---

## ✨ 特性概览（MVP）
- 账户与密钥：助记词（BIP-39）/派生（BIP-32/44）、Keystore v3 加密存储（只回显一次助记词）。
- 签名能力：`eth_sign` / `personal_sign` / **EIP-712**，交易签名 **EIP-1559 (type 0x2)**。
- 交易流：构造（估 gas/fee、管理 nonce）→ 签名 → 广播 → 回执跟踪/重发。
- 查询：ETH 余额、ERC-20 余额与元数据（带轻量缓存）。
- 历史：节点 + 区块浏览器（Blockscout/Etherscan）**聚合**，无须自建索引即可上线。

> 设计宗旨：先最小闭环（Create → Balance → Transfer → Receipt → History），再逐项增强。

---

## 🏗️ 架构图

```mermaid
flowchart LR
  subgraph Client[前端：浏览器插件 / App / 内部工具]
    A[EIP-1193 Provider\n或 REST 客户端]
  end

  subgraph API[API 接口层（FastAPI）]
    B1[/Auth/权限(可选)/]
    B2[/钱包与签名 API/]
    B3[/链上读写与查询 API/]
  end

  subgraph Core[核心服务层]
    C1[Keyring 密钥管理\nBIP-39/32/44 + Keystore v3]
    C2[Signer 签名\n712/1559/个人签名]
    C3[Tx 构造器\nGas/Nonce/1559 策略]
    C4[Broadcaster & Tracker\n广播/回执/替换重发]
    C5[Balances & Tokens\nETH/ERC20 + 缓存]
    C6[History 聚合\n节点 + Explorer]
    C7[Approvals & Risk (可选)\nallowance & revoke]
    C8[AA(可选)\nERC-4337]
  end

  subgraph Adapters[适配/资源层]
    D1[RPC 池管理\n多节点/重试/熔断]
    D2[Explorer 适配\nBlockscout/Etherscan]
    D3[存储与缓存\nSQLite/PG + Redis]
    D4[可观测性\n结构日志/OTEL]
    D5[远程/硬件签名\nWeb3Signer/HSM/HWI]
  end

  A --> B2 & B3
  B2 --> C1 & C2 & C3 & C4
  B3 --> C5 & C6
  C2 & C3 & C4 & C5 & C6 --> D1
  C6 --> D2
  C1 --> D3
  C4 & C5 & C6 --> D3
  Core --> D4
  C2 --> D5
```

---

## 📁 目录结构（建议）

```text
dwallet/
├─ app.py                    # 入口（FastAPI）
├─ api/
│  ├─ accounts.py            # /wallets, /accounts
│  ├─ evm_tx.py              # build/sign/send/receipt
│  ├─ balances.py            # balance/token 列表
│  ├─ history.py             # history 聚合
│  └─ typed_data.py          # sign-typed-data
├─ core/
│  ├─ keyring.py             # keystore v3 + 解锁
│  ├─ signer.py              # sign_tx / sign_eip712
│  ├─ tx_builder.py          # gas/nonce/1559
│  ├─ broadcaster.py         # 广播/重试/替换
│  ├─ balances.py            # ETH/ERC20 查询
│  └─ history.py             # 节点/Explorer 聚合
├─ adapters/
│  ├─ rpc_pool.py            # 多 RPC 池/熔断/超时
│  ├─ explorer.py            # Blockscout/Etherscan 适配
│  ├─ storage.py             # SQLite/PG DAO
│  └─ cache.py               # Redis 封装（可选）
├─ configs/
│  ├─ chains.yaml            # 链注册（CAIP-2/RPC/Explorer）
│  └─ tokens_mainnet.json    # TokenList 示例
├─ migrations/               # SQLite→PG 迁移脚本
├─ data/keystore/            # keystore v3 文件
├─ tests/                    # e2e 与单测
├─ requirements.txt
└─ .env.example
```

---

## 🧩 模块说明

### 1) Keyring（密钥管理）
- 生成/导入助记词与账户，按 BIP-44 路径（`m/44'/60'/0'/0/0`）派生。
- 以 Keystore v3（scrypt/pbkdf2）加密落盘，仅在内存中短暂解密私钥；**永不通过 API 返回私钥**。
- 预留远程签名/HSM 扩展点：在 `core.signer` 中替换实现即可。

### 2) Signer（签名）
- `eth_sign` / `personal_sign` / **EIP-712**（`eth_account.messages.encode_structured_data`）。
- 交易签名覆盖 **EIP-1559**（type 0x2），向下兼容 legacy。

### 3) Tx 构造器
- 自动估算 `gas`；读取最新块 `baseFeePerGas` 计算 `maxFeePerGas` 与 `maxPriorityFeePerGas`（默认 2 gwei，可配置）。
- **Nonce 管理**：同地址并发签名时加锁，支持替换/撤销（同 nonce 抬价）。

### 4) Broadcaster & Tracker
- `sendRawTransaction` 广播；`getTransactionReceipt` 轮询；异常统一为标准错误码。
- stuck 交易自动重发策略（bump 费率），可按策略开关。

### 5) Balances & Tokens
- 原生 ETH：`eth_getBalance`；
- ERC-20：`balanceOf` + `decimals/symbol`，带缓存；TokenList 支持自定义与白名单。

### 6) History 聚合
- 最小实现：节点 + 区块浏览器（Blockscout/Etherscan 等）**聚合**；解析 `input`/`logs` → 人类可读动作。
- 后期可替换成自建索引（Kafka + 索引器 + PG）。

### 7) Approvals & Risk（二期）
- 汇总 ERC-20 allowance；提供一键 revoke；
- 前置风险检查：方法黑名单、无限授权提示、金额阈值等。

### 8) ERC-4337（可选）
- UserOperation 构造与签名；Bundler 客户端；Paymaster/Session Keys。

---

## 🔌 API 参考（MVP）

> 基本路径：`/` ；所有端点返回 JSON。链 ID 以 EIP-155 的 `chainId` 传入。

### 账户 / 密钥
- **创建或导入助记词**
  - `POST /wallets`
  - 请求：`{"password":"StrongPass!","mnemonic?":"...","path?":"m/44'/60'/0'/0/0"}`
  - 返回：`address`, `mnemonic?`（仅首次生成时返回）, `keystore_path`
- **以私钥导入（开发期）**
  - `POST /wallets/import-privkey`
  - 请求：`{"password":"...","private_key":"0x..."}`

### 余额 / 资产
- **原生余额**：`GET /evm/{chainId}/balance?address=0x...`
- **代币列表（可选）**：`GET /evm/{chainId}/tokens?address=0x...`

### 交易
- **构造 1559 交易**：`POST /evm/{chainId}/build-tx`
  - 请求示例：`{"from":"0x...","to":"0x...","value_eth":0.001,"data?":"0x..."}`
- **签名交易**：`POST /evm/{chainId}/sign-tx`
  - 请求：`{"address":"0x...","password":"...","tx":{ 上一步返回的 tx }}`
- **广播交易**：`POST /evm/{chainId}/send-raw-tx`  → `{ "raw": "0x..." }`
- **查询回执**：`GET /evm/{chainId}/tx/{hash}`

### EIP-712 签名
- `POST /evm/{chainId}/sign-typed-data`
  - 请求：`{"address":"0x...","password":"...","typedData":{EIP-712 对象}}`

> **错误标准化**：`{"code":"NONCE_TOO_LOW","message":"...","details":{...}}`。

---

## ⚙️ 配置与运行

**依赖**（`requirements.txt`）
```
fastapi>=0.111
uvicorn[standard]>=0.30
web3>=6.20
pydantic>=2.7
python-dotenv>=1.0
```

**环境变量**（`.env.example`）
```
RPC_URL__1=https://rpc.ankr.com/eth
RPC_URL__8453=https://mainnet.base.org
KEYSTORE_DIR=./data/keystore
DB_URL=sqlite:///./data/wallet.db
```
> 以 `RPC_URL__{chainId}` 为键配置多条链；MVP 使用 SQLite，生产建议 PG + Redis。

**启动**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload --port 8000
```

---

## 🗃️ 数据模型（SQLite 示例）

```sql
CREATE TABLE IF NOT EXISTS accounts(
  address TEXT PRIMARY KEY,
  keystore_path TEXT NOT NULL,
  label TEXT,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tx_local(
  hash TEXT PRIMARY KEY,
  sender TEXT NOT NULL,
  to TEXT,
  value_wei TEXT NOT NULL,
  nonce INTEGER NOT NULL,
  chain_id INTEGER NOT NULL,
  status TEXT,
  raw BLOB,
  submitted_at INTEGER,
  updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS balances_cache(
  address TEXT NOT NULL,
  chain_id INTEGER NOT NULL,
  token TEXT,
  balance_wei TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY(address, chain_id, token)
);
```

---

## 🧰 RPC 池与稳定性
- 多 RPC 节点轮询 + 健康检查（失败率/延迟）；
- 读请求走最快、写请求走最稳；
- 熔断与指数退避重试；
- 限流与配额，防止前端滥用。

---

## 🔐 安全清单（必须落实）
- 私钥仅在后端内存中短暂解密；磁盘仅保存 **Keystore v3**；**不提供导出私钥 API**。
- 所有 `sign-*` 与 `send-*` 端点支持二次校验（密码/OTP/域名白名单/额度）。
- 交易前静态模拟（`eth_call`）与方法黑名单；
- 审计日志：来源 IP/Origin、账户、方法、哈希、耗时；
- 速率限制、IP 黑名单、暴力破解防护；
- 助记词只回显一次，且脱敏落库（如需）。

---

## 🧪 开发与测试
- 本地链：Anvil/Ganache（预置资金账户）。
- e2e：创建账户 → 查余额 → 构造/签名/广播 → 回执 → 历史。
- 并发：同地址签名/广播使用（分布式）锁；
- 可观测：结构化日志 + Trace（OpenTelemetry 可选）。

---

## 🗺️ 路线图
- **M1（MVP）**：账户/签名/1559 转账/余额/历史 + 统一错误码。
- **M2（体验）**：Approvals（allowance & revoke）、ENS、地址簿、通知。
- **M3（扩展）**：多链注册（CAIP-2）、RPC 池熔断、OpenTelemetry、PG/Redis。
- **M4（高级）**：ERC-4337（bundler 客户端/Paymaster）、硬件/远程签名接入。

---

## 📄 许可证
建议使用 **MIT** 或 **Apache-2.0**（按团队合规要求自定）。

---

## 🙌 致谢
- FastAPI · web3.py · eth-account · （可选）Blockscout/Etherscan · 社区贡献者。