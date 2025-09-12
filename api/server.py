# api/server.py
"""
dwallet HTTP API 服务器

启动HTTP API服务来提供提款功能

Usage:
    python -m api.server

    或者直接运行:
    python api/server.py
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from api.withdraw_api import app

# 加载环境变量
load_dotenv()

if __name__ == '__main__':
    # 从环境变量读取配置
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', 5000))
    debug = os.getenv('API_DEBUG', 'true').lower() == 'true'

    print(f"🚀 启动 dwallet API 服务器...")
    print(f"📍 地址: http://{host}:{port}")
    print(f"🔧 调试模式: {debug}")
    print(f"📖 API文档: http://{host}:{port}/api/health")
    print(f"⛓️  支持的链: http://{host}:{port}/api/chains")
    print(f"💰 提款接口: POST http://{host}:{port}/api/withdraw")
    print()

    try:
        app.run(
            host=host,
            port=port,
            debug=debug
        )
    except KeyboardInterrupt:
        print("\n👋 API服务器已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
