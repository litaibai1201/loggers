# Loggers 模块完整使用文档

## 📚 目录

1. [模块概述](#模块概述)
2. [模块结构](#模块结构)
3. [核心功能](#核心功能)
4. [配置方式](#配置方式)
5. [基本使用](#基本使用)
6. [多 Logger 实例](#多-logger-实例)
7. [多线程与上下文管理](#多线程与上下文管理)
8. [Flask 集成](#flask-集成)
9. [数据库日志](#数据库日志)
10. [性能监控](#性能监控)
11. [高级特性](#高级特性)
12. [最佳实践](#最佳实践)

## 📖 专题文档

- **[错误日志记录完整指南](./ERROR_LOGGING_GUIDE.md)** - 详细介绍错误日志的各种使用方式和最佳实践

---

## 模块概述

Loggers 是一个功能强大的结构化日志系统,基于 `structlog` 构建,提供:

- ✅ **结构化日志**: JSON 格式,便于分析和检索
- ✅ **自动化集成**: Flask HTTP/SQL 日志自动记录
- ✅ **上下文管理**: trace_id/transaction_id 自动传递
- ✅ **多线程安全**: 上下文隔离,防止污染
- ✅ **性能优化**: 队列处理器,非阻塞日志
- ✅ **灵活配置**: 支持多 logger 实例,自定义配置

---

## 模块结构

```
loggers/
├── __init__.py                 # 模块导出
├── conf/
│   ├── __init__.py
│   └── log_conf.py            # 默认配置
├── core/
│   ├── __init__.py
│   ├── logger.py              # 日志配置和初始化
│   ├── context.py             # LogContext 核心类
│   └── context_propagation.py # 线程上下文传递
├── utils/
│   ├── __init__.py
│   ├── models.py              # 日志数据模型
│   ├── ip_utils.py            # IP 获取工具
│   ├── decorators.py          # 装饰器
│   ├── executors.py           # 上下文感知执行器
│   └── utils.py               # 工具函数
└── integrations/
    ├── __init__.py
    └── flask_hooks.py         # Flask 自动日志钩子
```

### 核心文件说明

#### 1. `core/logger.py` - 日志系统配置

**功能**:
- 日志系统初始化
- 队列处理器配置
- 日志格式化和验证
- 全局配置管理

**关键类/函数**:
- `LoggerConfig`: 日志配置类
- `configure_logger()`: 配置日志系统
- `get_queue_handler_status()`: 获取队列状态

#### 2. `core/context.py` - 日志上下文

**功能**:
- 提供 `LogContext` 类
- 管理日志上下文(trace_id, transaction_id)
- 提供日志记录方法(info, warning, error 等)
- 支持结构化日志参数

**关键类**:
- `LogContext`: 日志上下文类,核心 API

#### 3. `core/context_propagation.py` - 上下文传递

**功能**:
- 线程间上下文自动传递
- 父子线程 trace_id 共享
- 上下文快照和隔离

**关键函数**:
- `enable_context_propagation()`: 启用自动传递
- `disable_context_propagation()`: 禁用自动传递
- `is_context_propagation_enabled()`: 检查状态

#### 4. `utils/models.py` - 数据模型

**功能**:
- 定义结构化日志数据模型
- 类型安全的日志字段

**关键模型**:
- `LogModel`: 完整日志模型
- `HTTPRequestModel`: HTTP 请求模型
- `HTTPResponseModel`: HTTP 响应模型
- `DatabaseModel`: 数据库操作模型
- `ErrorModel`: 错误信息模型

#### 5. `utils/ip_utils.py` - IP 获取

**功能**:
- 从 Flask/FastAPI/Django 获取真实客户端 IP
- 支持代理和负载均衡器

**关键函数**:
- `get_real_ip()`: 自动获取真实 IP
- `get_real_ip_from_flask()`: Flask 专用
- `get_real_ip_from_fastapi()`: FastAPI 专用

#### 6. `integrations/flask_hooks.py` - Flask 集成

**功能**:
- 自动记录 HTTP 请求/响应
- 自动记录 SQL 查询
- 自动获取真实 IP
- 错误处理

**关键类**:
- `FlaskHooksRegister`: Flask 钩子注册器
- `flask_hooks`: 全局钩子实例

---

## 核心功能

### 1. 结构化日志

所有日志都是 JSON 格式,包含标准字段:

```json
{
  "message": "用户登录成功",
  "event": "user_login",
  "category": "business",
  "service": {
    "name": "hr_server",
    "environment": "prd"
  },
  "trace": {"id": "req-123"},
  "transaction": {"id": "txn-456"},
  "client_ip": "203.0.113.45",
  "custom": {"user_id": "12345"},
  "level": "info",
  "timestamp": "2024-12-04T10:30:00.123Z"
}
```

### 2. 自动化集成

- **HTTP 日志**: 自动记录所有请求/响应
- **SQL 日志**: 自动记录所有数据库查询
- **真实 IP**: 自动从代理获取客户端 IP
- **错误追踪**: 自动记录异常和堆栈

### 3. 上下文管理

- **trace_id**: 追踪单个请求的完整生命周期
- **transaction_id**: 追踪业务事务
- **自动传递**: 父子线程自动共享上下文
- **自动隔离**: 防止线程间上下文污染

---

## 配置方式

### 1. 默认配置

使用 `conf/log_conf.py` 中的默认配置:

```python
from loggers import logger

# 直接使用,无需配置
logger.info("Hello World")
```

### 2. 自定义配置

创建自定义配置文件:

```python
# my_log_config.py
LOGGING_CONFIG = {
    'service_name': 'my_service',
    'environment': 'dev',
    'use_queue_handler': True,  # 启用队列处理器
    'queue_size': 1000,
    
    'handlers': {
        'file_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'filename': 'logs/app.log',
            'when': 'H',  # 每小时轮转
            'interval': 1,
            'backupCount': 24,
            'maxBytes': 100 * 1024 * 1024,  # 100MB
        }
    },
    'loggers': {
        'my.custom': {
            'handlers': ['file_handler'],
            'level': 'INFO',
        }
    }
}
```

使用自定义配置:

```python
from loggers import configure_logger
from my_log_config import LOGGING_CONFIG

# 应用自定义配置
configure_logger(LOGGING_CONFIG)
```

### 3. 队列处理器配置

**何时启用**:
- ✅ FastAPI/AsyncIO 应用
- ✅ 高并发 Flask 应用
- ✅ 需要非阻塞日志的场景

**何时禁用**:
- ❌ 多进程应用(Gunicorn with multiple workers)
- ❌ 低并发 CLI 工具

```python
LOGGING_CONFIG = {
    'use_queue_handler': True,  # 启用
    'queue_size': -1,  # 无限制(-1) 或指定大小
}
```

---

## 基本使用

### 1. 导入和初始化

```python
from loggers import logger

# 直接使用默认 logger
logger.info("应用启动")
```

### 2. 日志级别

```python
# 5 个标准级别
logger.debug("调试信息")
logger.info("普通信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

### 3. 结构化参数

```python
# 使用 category 分类
logger.info("用户登录", category="business")

# 使用 event 标记事件
logger.info("订单创建", event="order_created", category="business")

# 使用 custom 添加自定义字段
logger.info(
    "数据处理完成",
    category="business",
    custom={
        "record_count": 1000,
        "duration_ms": 523.45,
        "status": "success"
    }
)
```

### 4. HTTP 日志

```python
from loggers import HTTPRequestModel, HTTPResponseModel

# 记录 HTTP 请求
req_model = HTTPRequestModel(
    method="POST",
    path="/api/users",
    headers={"Content-Type": "application/json"},
    body={"name": "John"}
)

logger.info(
    "HTTP 请求",
    event="http_request",
    category="http",
    req=req_model
)

# 记录 HTTP 响应
resp_model = HTTPResponseModel(
    status_code=201,
    body={"id": 123, "name": "John"},
    event_duration=0.156
)

logger.info(
    "HTTP 响应",
    event="http_response",
    category="http",
    resp=resp_model
)
```

### 5. 数据库日志

```python
from loggers import DatabaseModel

db_model = DatabaseModel(
    statement="SELECT * FROM users WHERE id = ?",
    statement_type="SELECT",
    status="success",
    duration=0.025,
    row_count=1
)

logger.info(
    "数据库查询",
    event="database_query",
    category="database",
    db=db_model
)
```

### 6. 错误日志

**⭐ 推荐使用方式：直接传递异常对象**

```python
try:
    # 业务逻辑
    result = risky_operation()
except Exception as e:
    # 方式1: 直接传异常对象（最推荐）
    logger.error(
        "操作失败",
        category="error",
        error=e,  # 直接传异常对象，自动解析为结构化数据
        custom={"operation": "risky_operation"}
    )
```

**其他支持的方式：**

```python
import traceback
from loggers import ErrorModel

try:
    result = risky_operation()
except Exception as e:
    # 方式2: 传 traceback 字符串（兼容旧代码）
    logger.error("操作失败", error=traceback.format_exc())

    # 方式3: 手动构造 ErrorModel（用于复杂场景）
    error_model = ErrorModel(
        message=str(e),
        error_type=type(e).__name__,
        error_code="BIZ_001",  # 业务错误代码
        stack_trace=traceback.format_exc()
    )
    logger.error("操作失败", error=error_model)
```

> 📖 **详细说明**：查看 [错误日志记录完整指南](./ERROR_LOGGING_GUIDE.md) 了解：
> - 为什么推荐方式1
> - 各种方式的区别和适用场景
> - ELK 友好的结构化输出
> - 实际应用场景示例
> - 迁移指南和最佳实践

---

## 多 Logger 实例

创建多个 logger 实例有两种方式:

### 方式一: 通过配置文件 (推荐用于固定的 logger)

适用场景: 需要为不同模块配置固定的日志文件、轮转策略等

#### 1. 配置 log_conf.py

```python
# loggers/conf/log_conf.py
LOGGING_CONFIG = {
    'service_name': 'hr_server',
    'environment': 'prd',
    
    'handlers': {
        # API 日志 handler
        'api_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'formatter': 'simple_msg',
            'level': 'DEBUG',
            'filename': 'logs/api.log',
            'when': 'H',  # 每小时轮转
            'interval': 1,
            'backupCount': 24,
            'maxBytes': 100 * 1024 * 1024,
            'encoding': 'utf-8',
            'use_gzip': False,
        },
        # 数据库日志 handler
        'db_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'formatter': 'simple_msg',
            'level': 'DEBUG',
            'filename': 'logs/database.log',
            'when': 'D',  # 每天轮转
            'interval': 1,
            'backupCount': 30,
            'maxBytes': 200 * 1024 * 1024,
            'encoding': 'utf-8',
            'use_gzip': True,  # 启用压缩
        },
        # 审计日志 handler
        'audit_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'formatter': 'simple_msg',
            'level': 'INFO',
            'filename': 'logs/audit.log',
            'when': 'midnight',  # 每天午夜轮转
            'interval': 1,
            'backupCount': 90,  # 保留90天
            'maxBytes': 500 * 1024 * 1024,
            'encoding': 'utf-8',
            'use_gzip': True,
        },
    },
    'loggers': {
        # API logger
        'api': {
            'handlers': ['api_handler'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # 数据库 logger
        'database': {
            'handlers': ['db_handler'],
            'level': 'DEBUG',
            'propagate': False,
        },
        # 审计 logger
        'audit': {
            'handlers': ['audit_handler'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}
```

#### 2. 使用配置好的 logger

```python
from loggers import LogContext

# 使用配置文件中定义的 logger
api_logger = LogContext("api")          # 使用 api_handler
db_logger = LogContext("database")      # 使用 db_handler
audit_logger = LogContext("audit")      # 使用 audit_handler

# 使用不同的 logger
api_logger.info("API 请求处理", category="http")
db_logger.info("数据库查询", category="database")
audit_logger.info("用户操作", category="audit")
```

**优点**:
- ✅ 集中管理配置,便于维护
- ✅ 可以为每个 logger 配置不同的轮转策略
- ✅ 支持多个 handler (如同时写入文件和发送到远程)
- ✅ 适合团队协作,配置统一

**配置参数说明**:
- `when`: 轮转时间单位
  - `'S'`: 秒
  - `'M'`: 分钟
  - `'H'`: 小时
  - `'D'`: 天
  - `'W0'-'W6'`: 周几 (0=周一)
  - `'midnight'`: 每天午夜
- `interval`: 轮转间隔 (配合 when 使用)
- `backupCount`: 保留的备份文件数量
- `maxBytes`: 单个日志文件最大字节数
- `use_gzip`: 是否压缩备份文件

---

### 方式二: 直接传参创建 (推荐用于动态 logger)

适用场景: 需要动态创建 logger,或者不想修改配置文件

#### 1. 使用默认配置

```python
from loggers import LogContext

# 使用默认配置 (写入 logs/myapp.log)
logger = LogContext()
logger.info("使用默认配置")
```

#### 2. 指定日志文件 (使用默认轮转配置)

```python
from loggers import LogContext

# 指定日志文件,其他使用默认配置
# 默认: 每天轮转,保留14天,200MB,不压缩
module_logger = LogContext("my_module", log_file="logs/my_module.log")
module_logger.info("模块日志")
```

#### 3. 完全自定义配置

```python
from loggers import LogContext

# 完全自定义所有参数
hourly_logger = LogContext(
    logger_name="hourly",
    log_file="logs/hourly.log",
    when='H',              # 每小时轮转
    interval=1,            # 每1小时
    backup_count=24,       # 保留24个备份 (24小时)
    max_bytes=50 * 1024 * 1024,  # 50MB
    use_gzip=True          # 启用压缩
)

# 每分钟轮转的 logger
minute_logger = LogContext(
    logger_name="minute",
    log_file="logs/minute.log",
    when='M',              # 每分钟轮转
    interval=5,            # 每5分钟
    backup_count=12,       # 保留12个备份 (1小时)
    max_bytes=10 * 1024 * 1024,  # 10MB
    use_gzip=False
)

# 每周轮转的 logger
weekly_logger = LogContext(
    logger_name="weekly",
    log_file="logs/weekly.log",
    when='W0',             # 每周一轮转
    interval=1,
    backup_count=52,       # 保留52周 (1年)
    max_bytes=1024 * 1024 * 1024,  # 1GB
    use_gzip=True
)
```

**参数说明**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `logger_name` | str | "my.custom" | logger 名称 |
| `log_file` | str | None | 日志文件路径,不指定则使用配置文件 |
| `when` | str | 'D' | 轮转时间单位 |
| `interval` | int | 1 | 轮转间隔 |
| `backup_count` | int | 14 | 保留备份数量 |
| `max_bytes` | int | 200MB | 单文件最大字节数 |
| `use_gzip` | bool | False | 是否压缩备份 |

**优点**:
- ✅ 灵活,无需修改配置文件
- ✅ 适合动态场景
- ✅ 代码即配置,一目了然
- ✅ 适合临时测试或独立模块

---

### 实际应用示例

#### 示例 1: 按模块分离 (配置文件方式)

```python
# controllers/user_controller.py
from loggers import LogContext

# 使用配置文件中的 'api' logger
logger = LogContext("api")

class UserController:
    def create_user(self, data):
        logger.info("创建用户", category="business", custom={"data": data})
```

```python
# services/database_service.py
from loggers import LogContext

# 使用配置文件中的 'database' logger
logger = LogContext("database")

class DatabaseService:
    def query(self, sql):
        logger.info("执行查询", category="database", custom={"sql": sql})
```

#### 示例 2: 按功能分离 (直接参数方式)

```python
# 审计日志 - 每天轮转,保留90天,启用压缩
audit_logger = LogContext(
    "audit",
    log_file="logs/audit.log",
    when='midnight',
    backup_count=90,
    use_gzip=True
)

def log_user_action(user_id, action):
    audit_logger.info(
        "用户操作",
        category="audit",
        custom={
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.now().isoformat()
        }
    )
```

```python
# 性能日志 - 每小时轮转,保留7天
perf_logger = LogContext(
    "performance",
    log_file="logs/performance.log",
    when='H',
    backup_count=24 * 7,  # 7天 * 24小时
    use_gzip=True
)

def log_slow_operation(operation, duration):
    if duration > 1.0:
        perf_logger.warning(
            "慢操作",
            category="performance",
            custom={"operation": operation, "duration": duration}
        )
```

#### 示例 3: 混合使用

```python
# 使用配置文件中的 logger
api_logger = LogContext("api")

# 动态创建临时测试 logger
test_logger = LogContext(
    "test",
    log_file="logs/test.log",
    when='M',
    interval=1,
    backup_count=10
)

# 根据环境选择
import os
if os.getenv('ENV') == 'dev':
    logger = test_logger
else:
    logger = api_logger
```

---

### 两种方式对比

| 特性 | 配置文件方式 | 直接参数方式 |
|------|-------------|-------------|
| 配置管理 | 集中管理,便于维护 | 分散在代码中 |
| 灵活性 | 需要修改配置文件 | 代码即配置,灵活 |
| 适用场景 | 固定的 logger | 动态创建 |
| 团队协作 | 配置统一,适合团队 | 适合个人或独立模块 |
| 多 handler | 支持 | 不支持 |
| 推荐用途 | 生产环境 | 开发测试 |

**建议**:
- 生产环境: 使用配置文件方式,便于统一管理
- 开发测试: 使用直接参数方式,快速灵活
- 混合使用: 核心 logger 用配置文件,临时 logger 用直接参数

```

---

## 多线程与上下文管理

### 1. trace_id 基本使用

```python
from loggers import logger

# 设置 trace_id
logger.set_trace_id("req-12345")

# 所有后续日志都会包含这个 trace_id
logger.info("处理开始")  # trace_id: req-12345
logger.info("处理中")    # trace_id: req-12345
logger.info("处理完成")  # trace_id: req-12345

# 获取当前 trace_id
current_trace = logger.get_trace_id()
print(f"当前 trace_id: {current_trace}")

# 清理上下文
logger.clear_context()
```

### 2. 启用自动上下文传递

```python
from loggers import enable_context_propagation, logger
import threading

# 在应用启动时调用一次
enable_context_propagation()

def background_task():
    # 子线程自动继承父线程的 trace_id
    logger.info("后台任务执行")  # 自动包含父线程的 trace_id

def api_handler():
    logger.set_trace_id("req-12345")
    logger.info("API 处理开始")
    
    # 创建子线程,自动继承 trace_id
    thread = threading.Thread(target=background_task)
    thread.start()
    thread.join()
    
    logger.info("API 处理完成")
```

**日志输出**:
```json
{"message": "API 处理开始", "trace": {"id": "req-12345"}}
{"message": "后台任务执行", "trace": {"id": "req-12345"}}
{"message": "API 处理完成", "trace": {"id": "req-12345"}}
```

### 3. 上下文隔离(防止污染)

#### 问题场景

```python
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)

def task1():
    logger.set_trace_id("task-1")
    logger.info("任务1执行")
    # ❌ 没有清理上下文

def task2():
    # ❌ 可能复用 task1 的线程,继承错误的 trace_id
    logger.info("任务2执行")  # 可能显示 trace_id: task-1

executor.submit(task1)
executor.submit(task2)
```

#### 解决方案 1: 使用 ContextAwareThreadPoolExecutor

```python
from loggers.utils import ContextAwareThreadPoolExecutor

executor = ContextAwareThreadPoolExecutor(max_workers=2)

def task1():
    logger.set_trace_id("task-1")
    logger.info("任务1执行")
    # ✅ 自动清理上下文

def task2():
    logger.set_trace_id("task-2")
    logger.info("任务2执行")  # ✅ 正确的 trace_id
    # ✅ 自动清理上下文

executor.submit(task1)
executor.submit(task2)
```

#### 解决方案 2: 使用装饰器

```python
from loggers.utils import context_cleanup_decorator
from concurrent.futures import ThreadPoolExecutor

@context_cleanup_decorator
def task1():
    logger.set_trace_id("task-1")
    logger.info("任务1执行")
    # ✅ 自动清理上下文

@context_cleanup_decorator
def task2():
    logger.set_trace_id("task-2")
    logger.info("任务2执行")
    # ✅ 自动清理上下文

executor = ThreadPoolExecutor(max_workers=2)
executor.submit(task1)
executor.submit(task2)
```

#### 解决方案 3: 手动清理

```python
def task1():
    try:
        logger.set_trace_id("task-1")
        logger.info("任务1执行")
    finally:
        logger.clear_context()  # 手动清理
```

### 4. Flask 请求中的上下文管理

```python
from flask import Flask
from loggers import logger

app = Flask(__name__)

@app.before_request
def before_request():
    # 为每个请求生成唯一 trace_id
    import uuid
    trace_id = str(uuid.uuid4())
    logger.set_trace_id(trace_id)

@app.teardown_request
def teardown_request(exception=None):
    # 请求结束后清理上下文
    logger.clear_context()

@app.route('/api/users')
def get_users():
    logger.info("获取用户列表")  # 自动包含 trace_id
    return {"users": []}
```

---

## Flask 集成

### 1. 基本集成

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from loggers.integrations import flask_hooks

def create_app():
    app = Flask(__name__)
    db = SQLAlchemy(app)
    
    # 注册 Flask 钩子(必须在 db.init_app 之后)
    flask_hooks.init_app(app, db)
    
    return app
```

**自动功能**:
- ✅ 记录所有 HTTP 请求(方法、路径、参数、客户端 IP)
- ✅ 记录所有 HTTP 响应(状态码、响应体、耗时)
- ✅ 记录所有 SQL 查询(语句、参数、执行时间)
- ✅ 记录 SQL 错误(失败的查询、错误信息)
- ✅ 自动获取真实客户端 IP
- ✅ 自动设置 trace_id

### 2. 禁用 SQL 日志

```python
# 只记录 HTTP 日志,不记录 SQL
flask_hooks.init_app(app, db, enable_db_logging=False)
```

### 3. 只记录 HTTP 日志

```python
# 不提供 db 参数
flask_hooks.init_app(app)
```

### 4. 根据环境配置

```python
import os

def create_app():
    app = Flask(__name__)
    db = SQLAlchemy(app)
    
    # 根据环境变量决定是否启用 SQL 日志
    enable_sql = os.getenv('ENABLE_SQL_LOGGING', 'true').lower() == 'true'
    
    flask_hooks.init_app(app, db, enable_db_logging=enable_sql)
    
    return app
```

### 5. HTTP 日志示例

**请求日志**:
```json
{
  "message": "HTTP 请求开始: POST /api/users",
  "event": "http_request_start",
  "category": "http",
  "client_ip": "203.0.113.45",
  "req": {
    "method": "POST",
    "path": "/api/users",
    "headers": {"Content-Type": "application/json"},
    "body": {"name": "John"}
  },
  "custom": {
    "request_id": "1701234567890",
    "remote_addr": "192.168.1.100"
  }
}
```

**响应日志**:
```json
{
  "message": "HTTP 请求完成: POST /api/users - 201",
  "event": "http_request_complete",
  "category": "http",
  "resp": {
    "status_code": 201,
    "body": {"id": 123, "name": "John"},
    "event_duration": 0.156
  },
  "custom": {
    "request_id": "1701234567890",
    "duration_ms": 156.23
  }
}
```

### 6. SQL 日志示例

**成功查询**:
```json
{
  "message": "SQL 命令: SELECT",
  "event": "database-SELECT",
  "category": "database",
  "db": {
    "statement": "SELECT * FROM users WHERE id = ?",
    "statement_type": "SELECT",
    "status": "success",
    "duration": 0.025,
    "row_count": 1
  },
  "custom": {
    "parameters": [123],
    "duration_ms": 25.34
  }
}
```

**失败查询**:
```json
{
  "message": "SQL 执行失败: SELECT",
  "event": "database-SELECT-error",
  "category": "database",
  "db": {
    "statement": "SELECT * FROM non_existent_table",
    "statement_type": "SELECT",
    "status": "failed",
    "duration": 0.015
  },
  "error": {
    "message": "Table doesn't exist",
    "error_type": "OperationalError",
    "stack_trace": "..."
  }
}
```

---

## 数据库日志

### 1. 使用 DatabaseLogger

```python
from loggers.utils import DatabaseLogger

# 记录成功的查询
DatabaseLogger.log_query(
    sql="SELECT * FROM users WHERE id = ?",
    status="success",
    duration=0.025,
    statement_type="SELECT"
)

# 记录失败的查询
DatabaseLogger.log_error(
    sql="INSERT INTO users VALUES (?)",
    error_message="Duplicate key error"
)
```

### 2. 手动记录数据库操作

```python
from loggers import logger, DatabaseModel
import time

def execute_query(sql, params):
    start_time = time.time()
    
    try:
        # 执行查询
        result = db.execute(sql, params)
        duration = time.time() - start_time
        
        # 记录成功
        db_model = DatabaseModel(
            statement=sql,
            statement_type="SELECT",
            status="success",
            duration=duration,
            row_count=len(result)
        )
        
        logger.info(
            "数据库查询成功",
            category="database",
            db=db_model,
            custom={"parameters": params}
        )
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        
        # 记录失败
        db_model = DatabaseModel(
            statement=sql,
            statement_type="SELECT",
            status="failed",
            duration=duration
        )
        
        logger.error(
            "数据库查询失败",
            category="database",
            db=db_model,
            error={
                "message": str(e),
                "error_type": type(e).__name__
            }
        )
        raise
```

---

## 性能监控

### 1. 使用 LogExecutionTime 装饰器

```python
from loggers.utils import LogExecutionTime

# 监控函数执行时间
@LogExecutionTime.track(slow_threshold=1.0, category="performance")
def search_employees(keyword):
    # 函数逻辑
    time.sleep(0.5)
    return results

# 调用函数
search_employees("John")
```

**日志输出**:
```json
{
  "message": "函数执行完成: search_employees",
  "category": "performance",
  "custom": {
    "function": "search_employees",
    "module": "__main__",
    "duration": 0.501,
    "status": "success"
  }
}
```

**慢执行警告**:
```json
{
  "message": "函数执行缓慢: search_employees",
  "category": "performance",
  "custom": {
    "function": "search_employees",
    "duration": 1.523,
    "threshold": 1.0,
    "status": "slow"
  },
  "level": "warning"
}
```

### 2. 手动性能监控

```python
import time

def process_data(data):
    start_time = time.time()
    
    try:
        # 处理逻辑
        result = heavy_computation(data)
        
        duration = time.time() - start_time
        
        logger.info(
            "数据处理完成",
            category="performance",
            custom={
                "operation": "process_data",
                "duration": round(duration, 3),
                "record_count": len(data)
            }
        )
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        
        logger.error(
            "数据处理失败",
            category="performance",
            custom={
                "operation": "process_data",
                "duration": round(duration, 3)
            },
            error={
                "message": str(e),
                "error_type": type(e).__name__
            }
        )
        raise
```

---

## 高级特性

### 1. 动态日志级别

```python
from loggers import logger

# 运行时修改日志级别
logger.set_level("DEBUG")  # 显示所有日志
logger.set_level("WARNING")  # 只显示警告和错误
```

### 2. 条件日志

```python
# 只在特定条件下记录
if user.is_admin:
    logger.info(
        "管理员操作",
        category="audit",
        custom={"user_id": user.id, "action": "delete_user"}
    )
```

### 3. 批量日志

```python
# 记录批量操作
results = []
for item in items:
    result = process_item(item)
    results.append(result)

logger.info(
    "批量处理完成",
    category="business",
    custom={
        "total_count": len(items),
        "success_count": sum(1 for r in results if r.success),
        "failed_count": sum(1 for r in results if not r.success)
    }
)
```

### 4. 日志采样

```python
import random

# 只记录 10% 的日志(用于高频操作)
if random.random() < 0.1:
    logger.info("高频操作", category="performance")
```

### 5. 日志聚合

```python
# 聚合多个操作的结果
stats = {
    "total": 0,
    "success": 0,
    "failed": 0,
    "duration": 0
}

for item in items:
    start = time.time()
    try:
        process(item)
        stats["success"] += 1
    except:
        stats["failed"] += 1
    finally:
        stats["total"] += 1
        stats["duration"] += time.time() - start

logger.info(
    "批量处理统计",
    category="business",
    custom=stats
)
```

---

## 最佳实践

### 1. 日志分类

使用 `category` 字段对日志进行分类:

```python
# 业务日志
logger.info("订单创建", category="business")

# HTTP 日志
logger.info("API 请求", category="http")

# 数据库日志
logger.info("查询执行", category="database")

# 性能日志
logger.info("慢查询", category="performance")

# 审计日志
logger.info("用户操作", category="audit")

# 错误日志
logger.error("系统错误", category="error")
```

### 2. 使用 event 标记

```python
# 明确的事件名称
logger.info("用户注册", event="user_registered", category="business")
logger.info("订单支付", event="order_paid", category="business")
logger.info("邮件发送", event="email_sent", category="business")
```

### 3. 结构化自定义字段

```python
# ✅ 好的做法
logger.info(
    "订单处理",
    category="business",
    custom={
        "order_id": "ORD-12345",
        "user_id": "USR-67890",
        "amount": 99.99,
        "status": "completed"
    }
)

# ❌ 避免的做法
logger.info(f"订单 ORD-12345 处理完成,用户 USR-67890,金额 99.99")
```

### 4. 错误处理

```python
# ✅ 完整的错误信息
try:
    risky_operation()
except Exception as e:
    logger.error(
        "操作失败",
        category="error",
        error={
            "message": str(e),
            "error_type": type(e).__name__,
            "stack_trace": traceback.format_exc()
        },
        custom={
            "operation": "risky_operation",
            "user_id": current_user.id
        }
    )
```

### 5. 敏感信息处理

```python
# ❌ 不要记录敏感信息
logger.info(f"用户登录: {username}, 密码: {password}")

# ✅ 脱敏处理
logger.info(
    "用户登录",
    category="audit",
    custom={
        "username": username,
        "password": "***",  # 脱敏
        "ip": client_ip
    }
)
```

### 6. 日志查询

使用 `jq` 工具查询日志:

```bash
# 查询所有错误日志
cat logs/app.log | jq 'select(.level == "error")'

# 查询特定 trace_id 的所有日志
cat logs/app.log | jq 'select(.trace.id == "req-12345")'

# 查询慢 SQL(超过 1 秒)
cat logs/app.log | jq 'select(.category == "database" and .custom.duration_ms > 1000)'

# 查询特定时间范围
cat logs/app.log | jq 'select(.timestamp >= "2024-12-04T10:00:00")'

# 统计错误数量
cat logs/app.log | jq 'select(.level == "error")' | wc -l
```

### 7. 性能优化

```python
# 启用队列处理器(高并发场景)
LOGGING_CONFIG = {
    'use_queue_handler': True,
    'queue_size': -1
}

# 限制日志大小
logger.info(
    "大数据处理",
    custom={
        "data": large_data[:100],  # 只记录前 100 条
        "total_count": len(large_data)
    }
)

# 使用日志采样
if random.random() < 0.01:  # 1% 采样
    logger.info("高频操作")
```

### 8. 测试环境配置

```python
# test_config.py
LOGGING_CONFIG = {
    'service_name': 'hr_server',
    'environment': 'test',  # 标记为测试环境
    'handlers': {
        'test_handler': {
            'filename': 'logs/test.log',
            'level': 'DEBUG'  # 测试环境显示所有日志
        }
    }
}
```

---

## 完整示例

### Flask 应用完整示例

```python
# app.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from loggers import enable_context_propagation, logger
from loggers.integrations import flask_hooks

# 启用上下文自动传递
enable_context_propagation()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
    
    db = SQLAlchemy(app)
    
    # 注册 Flask 钩子
    flask_hooks.init_app(app, db, enable_db_logging=True)
    
    @app.teardown_request
    def teardown_request(exception=None):
        # 清理上下文
        logger.clear_context()
    
    @app.route('/api/users')
    def get_users():
        # HTTP 和 SQL 日志自动记录
        users = User.query.all()
        
        # 业务日志手动记录
        logger.info(
            "获取用户列表",
            category="business",
            custom={"count": len(users)}
        )
        
        return {"users": [u.to_dict() for u in users]}
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run()
```

---

## 总结

Loggers 模块提供了完整的日志解决方案:

1. **结构化日志**: JSON 格式,便于分析
2. **自动化集成**: Flask HTTP/SQL 自动记录
3. **上下文管理**: trace_id 自动传递和隔离
4. **多线程安全**: 防止上下文污染
5. **性能优化**: 队列处理器,非阻塞
6. **灵活配置**: 多 logger 实例,自定义配置

通过合理使用这些功能,可以构建强大的日志系统,支持问题排查、性能分析和业务监控。
