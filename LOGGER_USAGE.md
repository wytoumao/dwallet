# 使用示例文档

## 全局Logger使用指南

### 1. 基本使用
所有模块现在都使用统一的全局logger：

```python
from core.logger import get_logger

logger = get_logger()
logger.info("这是一条信息")
logger.debug("这是调试信息")
logger.error("这是错误信息")
```

### 2. 动态控制日志级别

#### 启用调试模式（显示所有日志）：
```python
from core.logger import enable_debug
enable_debug()
```

#### 禁用调试模式（只显示INFO及以上级别）：
```python
from core.logger import disable_debug
disable_debug()
```

#### 自定义日志级别：
```python
from core.logger import set_log_level
import logging

set_log_level(logging.WARNING)  # 只显示WARNING和ERROR
```

### 3. 自定义logger配置

如果你想修改日志格式或其他配置：

```python
from core.logger import setup_logger
import logging

# 重新配置logger
logger = setup_logger(
    name="dwallet",
    level=logging.DEBUG,
    format_str="%(levelname)s - %(message)s"  # 简化格式
)
```

### 4. 在API服务中控制日志

你可以在API启动时设置日志级别：

```python
# 在 api/server.py 中
from core.logger import enable_debug, disable_debug

if __name__ == "__main__":
    # 开发模式 - 启用调试日志
    enable_debug()
    
    # 生产模式 - 只显示重要信息
    # disable_debug()
    
    app.run(debug=True)
```

### 5. 环境变量控制（可选扩展）

你还可以通过环境变量控制日志级别：

```python
import os
from core.logger import set_log_level
import logging

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR
}
set_log_level(level_map.get(log_level, logging.INFO))
```

### 6. 当前的日志输出控制

现在所有的gas估算调试信息都使用 `logger.debug()`，你可以：

- 默认情况下看不到这些调试信息（只显示INFO级别）
- 需要调试时调用 `enable_debug()` 就能看到详细的gas估算过程
- 不需要修改任何业务代码，只需要调整logger配置
