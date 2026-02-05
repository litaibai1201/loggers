# -*- coding: utf-8 -*-
"""
@文件: context.py
@说明: 日志上下文管理器
@时间: 2024
"""
from typing import Any, Dict, Literal, Optional
import structlog
import uuid
import os
import contextvars
import threading
from functools import wraps

from ..conf.log_conf import LOGGING_CONFIG
from .models import ErrorModel, HTTPRequestModel, HTTPResponseModel, DatabaseModel

# 线程上下文传播相关的全局变量
_original_thread_init = threading.Thread.__init__
_propagation_enabled = False


class LogContext:
    """日志上下文管理器 - 使用 structlog 原生 contextvars 支持"""

    def __init__(
        self,
        logger_name: str = "my.custom",
        log_file: Optional[str] = None,
        when: str = 'D',
        interval: int = 1,
        backup_count: int = 14,
        max_bytes: int = 200 * 1024 * 1024,
        use_gzip: bool = False
    ):
        """初始化日志上下文

        Args:
            logger_name: logger 名称，默认为 "my.custom"
                        可以创建多个不同的 logger 实例，写入不同的日志文件
                        例如: "my.app", "my.database", "my.api" 等
            log_file: 日志文件路径（可选），例如: "logs/my_module.log"
                     - 如果指定，将使用指定的文件路径
                     - 如果不指定且 logger_name 在预配置中，使用配置文件中的 handler
                     - 如果不指定且 logger_name 不在预配置中，自动创建 {logger_name}.log
            when: 日志轮转时间单位，默认 'D' (按天)
                 可选值: 'S'(秒), 'M'(分), 'H'(小时), 'D'(天), 'W0'-'W6'(周几), 'midnight'(午夜)
            interval: 轮转间隔，默认 1（配合 when 使用，如 when='D', interval=1 表示每天轮转）
            backup_count: 保留的备份文件数量，默认 14（保留14天）
            max_bytes: 单个日志文件最大字节数，默认 200MB
            use_gzip: 是否压缩备份文件，默认 False

        使用示例:
            # 使用默认配置（my.custom）
            logger1 = LogContext()

            # 使用预配置的 logger（如 "test"），日志写入 test.log
            logger2 = LogContext("test")

            # 使用预配置 logger 的子 logger，日志传播到父级
            logger3 = LogContext("test.structured")  # → 写入 test.log

            # 使用未预配置的名称，自动创建 api.log
            logger4 = LogContext("api")  # → 自动创建 logs/api.log

            # 显式指定日志文件路径
            logger5 = LogContext("my_module", log_file="logs/my_module.log")

            # 自定义轮转配置：每小时轮转，保留7个备份，启用压缩
            logger6 = LogContext(
                "hourly_logger",
                log_file="logs/hourly.log",
                when='H',
                interval=1,
                backup_count=7,
                use_gzip=True
            )
        """
        # 获取 structlog logger（自动支持 contextvars）
        self.logger = structlog.get_logger(logger_name)
        self.logger_name = logger_name

        # 判断是否需要创建文件 handler
        configured_loggers = set(LOGGING_CONFIG.get('loggers', {}).keys())

        if log_file:
            # 用户显式指定了日志文件
            self._setup_file_handler(
                logger_name, log_file, when, interval, backup_count, max_bytes, use_gzip
            )
        elif not self._is_logger_configured(logger_name, configured_loggers):
            # logger_name 不在预配置中，自动创建 {logger_name}.log
            log_dir = LOGGING_CONFIG.get('log_dir', 'logs')
            # 将 logger_name 中的点替换为下划线，避免文件名问题
            safe_name = logger_name.replace('.', '_')
            auto_log_file = os.path.join(log_dir, f"{safe_name}.log")
            self._setup_file_handler(
                logger_name, auto_log_file, when, interval, backup_count, max_bytes, use_gzip
            )

        # 🔥 使用 contextvars 绑定服务信息（支持线程传递）
        service_info = {
            "name": LOGGING_CONFIG.get("service_name", "unknown"),
            "environment": LOGGING_CONFIG.get("environment", "prd")
        }
        structlog.contextvars.bind_contextvars(service=service_info)

    def _is_logger_configured(self, logger_name: str, configured_loggers: set) -> bool:
        """检查 logger_name 是否在预配置中（包括作为子 logger）

        Args:
            logger_name: 要检查的 logger 名称
            configured_loggers: 已配置的 logger 名称集合

        Returns:
            bool: 如果 logger_name 或其父级在配置中则返回 True
        """
        # 精确匹配
        if logger_name in configured_loggers:
            return True

        # 检查是否是已配置 logger 的子 logger
        # 例如 "test.structured" 是 "test" 的子 logger
        parts = logger_name.split('.')
        for i in range(len(parts) - 1, 0, -1):
            parent_name = '.'.join(parts[:i])
            if parent_name in configured_loggers:
                return True

        return False

    def _setup_file_handler(
        self,
        logger_name: str,
        log_file: str,
        when: str = 'D',
        interval: int = 1,
        backup_count: int = 14,
        max_bytes: int = 200 * 1024 * 1024,
        use_gzip: bool = False
    ):
        """为指定的 logger 动态创建文件 handler

        Args:
            logger_name: logger 名称
            log_file: 日志文件路径
            when: 日志轮转时间单位
            interval: 轮转间隔
            backup_count: 保留的备份文件数量
            max_bytes: 单个日志文件最大字节数
            use_gzip: 是否压缩备份文件
        """
        import logging
        from .handlers import OrganizedFileHandler

        # 从配置获取目录设置
        config_log_dir = LOGGING_CONFIG.get('log_dir', 'logs')
        archive_subdir = LOGGING_CONFIG.get('archive_subdir', 'archive')
        lock_subdir = LOGGING_CONFIG.get('lock_subdir', '.locks')

        # 计算归档和锁文件目录路径
        archive_dir = os.path.join(config_log_dir, archive_subdir)
        lock_dir = os.path.join(config_log_dir, lock_subdir)

        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # 获取标准 logger
        std_logger = logging.getLogger(logger_name)

        # 检查是否已经有相同文件的 handler（避免重复添加）
        for handler in std_logger.handlers:
            if hasattr(handler, 'baseFilename') and handler.baseFilename == os.path.abspath(log_file):
                # 已存在，不重复添加
                return

        # 创建文件 handler（使用 OrganizedFileHandler）
        file_handler = OrganizedFileHandler(
            filename=log_file,
            when=when,
            interval=interval,
            backupCount=backup_count,
            maxBytes=max_bytes,
            encoding='utf-8',
            use_gzip=use_gzip,
            archive_dir=archive_dir,
            lock_dir=lock_dir,
        )

        # 创建格式化器
        formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)

        # 添加到 logger
        std_logger.addHandler(file_handler)
        std_logger.setLevel(logging.DEBUG)
        std_logger.propagate = False

        # 同时添加错误日志 handler（写入统一的 error.log）
        error_log_file = os.path.join(config_log_dir, 'error.log')

        # 检查是否已有 error handler
        has_error_handler = False
        for handler in std_logger.handlers:
            if hasattr(handler, 'baseFilename') and handler.baseFilename == os.path.abspath(error_log_file):
                has_error_handler = True
                break

        if not has_error_handler:
            error_handler = OrganizedFileHandler(
                filename=error_log_file,
                when='D',
                interval=1,
                backupCount=7,
                maxBytes=200 * 1024 * 1024,
                encoding='utf-8',
                use_gzip=False,
                archive_dir=archive_dir,
                lock_dir=lock_dir,
            )
            error_formatter = logging.Formatter(
                '[%(asctime)s][%(filename)s][%(lineno)s][%(levelname)s][%(thread)d] - %(message)s'
            )
            error_handler.setFormatter(error_formatter)
            error_handler.setLevel(logging.ERROR)
            std_logger.addHandler(error_handler)

    def set_service_info(
        self,
        name: str = None,
        environment: str = None
    ) -> None:
        """设置服务信息（可选，用于覆盖配置文件）

        Args:
            name: 服务名称，默认从配置文件读取
            environment: 环境（dev/test/prd），默认从配置文件读取

        注意：一般不需要调用此方法，系统会自动从配置文件读取。
             只在需要临时覆盖配置时使用。
        """
        service_info = {
            "name": name or LOGGING_CONFIG.get("service_name", "unknown"),
            "environment": environment or LOGGING_CONFIG.get("environment", "prd")
        }

        # 使用 contextvars 绑定上下文（支持线程传递）
        structlog.contextvars.bind_contextvars(service=service_info)

    def set_trace_id(self, trace_id: str) -> None:
        """设置链路追踪ID"""
        structlog.contextvars.bind_contextvars(trace={"id": trace_id})

    def set_transaction_id(self, transaction_id: str) -> None:
        """设置事务ID"""
        structlog.contextvars.bind_contextvars(
            transaction={"id": transaction_id})

    def get_trace_id(self) -> Optional[str]:
        """获取当前的 trace_id"""
        # 从 contextvars 中获取
        ctx = structlog.contextvars.get_contextvars()
        trace = ctx.get("trace", {})
        return trace.get("id") if isinstance(trace, dict) else None

    def get_transaction_id(self) -> Optional[str]:
        """获取当前的 transaction_id"""
        # 从 contextvars 中获取
        ctx = structlog.contextvars.get_contextvars()
        transaction = ctx.get("transaction", {})
        return transaction.get("id") if isinstance(transaction, dict) else None

    def clear_context(self) -> None:
        """清空上下文（用于请求结束或线程复用场景）

        在以下场景调用：
        1. Flask 请求结束时（在 teardown_request 中）
        2. 线程池/协程池复用线程时
        3. 批处理任务完成时
        """
        # 清空 contextvars 中的所有上下文
        structlog.contextvars.clear_contextvars()

        # 🔥 自动重新绑定配置文件中的服务信息
        service_info = {
            "name": LOGGING_CONFIG.get("service_name", "unknown"),
            "environment": LOGGING_CONFIG.get("environment", "prd")
        }
        structlog.contextvars.bind_contextvars(service=service_info)

    # ==================== 线程上下文传播 ====================

    def enable_propagation(self) -> None:
        """启用线程上下文自动传播

        调用后，所有通过 threading.Thread 创建的子线程都会自动继承
        父线程的 contextvars 上下文（包括 trace_id、transaction_id 等）。

        使用示例：
            from loggers import logger

            logger.enable_propagation()

            def api_handler():
                logger.set_trace_id("req-123")
                # 子线程自动继承 trace_id
                threading.Thread(target=background_task).start()
        """
        global _propagation_enabled
        if not _propagation_enabled:
            threading.Thread.__init__ = self._context_aware_thread_init
            _propagation_enabled = True

    def disable_propagation(self) -> None:
        """禁用线程上下文自动传播"""
        global _propagation_enabled
        if _propagation_enabled:
            threading.Thread.__init__ = _original_thread_init
            _propagation_enabled = False

    def is_propagation_enabled(self) -> bool:
        """检查线程上下文传播是否已启用"""
        return _propagation_enabled

    @staticmethod
    def _context_aware_thread_init(self_thread, *args, **kwargs):
        """支持 contextvars 的 Thread.__init__ 包装器"""
        ctx = contextvars.copy_context()
        target = kwargs.get('target') or (args[1] if len(args) > 1 else None)

        if target is not None:
            @wraps(target)
            def wrapped_target(*target_args, **target_kwargs):
                return ctx.run(target, *target_args, **target_kwargs)

            if 'target' in kwargs:
                kwargs['target'] = wrapped_target
            else:
                args = list(args)
                if len(args) > 1:
                    args[1] = wrapped_target
                args = tuple(args)

        _original_thread_init(self_thread, *args, **kwargs)

    def info(
        self,
        message: str,
        event: Optional[str] = None,
        category: Optional[Literal[
            "http",
            "business",
            "database",
            "validation",
            "error",
            "performance",
            "audit"
        ]] = None,
        client_ip: Optional[str] = None,
        req: Optional[HTTPRequestModel] = None,
        resp: Optional[HTTPResponseModel] = None,
        db: Optional[DatabaseModel] = None,
        custom: Optional[Dict[str, Any]] = None,
        error: Optional[ErrorModel] = None,
        **kwargs
    ) -> None:
        """记录 INFO 级别日志

        Args:
            message: 日志消息（必需）
            event: 事件名称（可选）
            category: 日志分类（可选）
            client_ip: 客户端IP（可选）
            req: HTTP请求信息（可选）
            resp: HTTP响应信息（可选）
            db: 数据库操作信息（可选）
            custom: 自定义字段（可选）
            error: 错误信息（可选）
            **kwargs: 其他额外字段
        """
        # 只传递非 None 的参数
        log_kwargs = {
            k: v for k, v in {
                "event": event,
                "category": category,
                "client_ip": client_ip,
                "req": req,
                "resp": resp,
                "db": db,
                "custom": custom,
                "error": error
            }.items() if v is not None
        }
        log_kwargs.update(kwargs)
        self._log("info", message, **log_kwargs)

    def warning(
        self,
        message: str,
        event: Optional[str] = None,
        category: Optional[Literal[
            "http",
            "business",
            "database",
            "validation",
            "error",
            "performance",
            "audit"
        ]] = None,
        client_ip: Optional[str] = None,
        req: Optional[HTTPRequestModel] = None,
        resp: Optional[HTTPResponseModel] = None,
        db: Optional[DatabaseModel] = None,
        custom: Optional[Dict[str, Any]] = None,
        error: Optional[ErrorModel] = None,
        **kwargs
    ) -> None:
        """记录 WARNING 级别日志

        Args:
            message: 日志消息（必需）
            event: 事件名称（可选）
            category: 日志分类（可选）
            client_ip: 客户端IP（可选）
            req: HTTP请求信息（可选）
            resp: HTTP响应信息（可选）
            db: 数据库操作信息（可选）
            custom: 自定义字段（可选）
            error: 错误信息（可选）
            **kwargs: 其他额外字段
        """
        # 只传递非 None 的参数
        log_kwargs = {
            k: v for k, v in {
                "event": event,
                "category": category,
                "client_ip": client_ip,
                "req": req,
                "resp": resp,
                "db": db,
                "custom": custom,
                "error": error
            }.items() if v is not None
        }
        log_kwargs.update(kwargs)
        self._log("warning", message, **log_kwargs)

    def error(
        self,
        message: str,
        event: Optional[str] = None,
        category: Optional[Literal[
            "http",
            "business",
            "database",
            "validation",
            "error",
            "performance",
            "audit"
        ]] = None,
        client_ip: Optional[str] = None,
        req: Optional[HTTPRequestModel] = None,
        resp: Optional[HTTPResponseModel] = None,
        db: Optional[DatabaseModel] = None,
        custom: Optional[Dict[str, Any]] = None,
        error: Optional[ErrorModel] = None,
        **kwargs
    ) -> None:
        """记录 ERROR 级别日志

        Args:
            message: 日志消息（必需）
            event: 事件名称（可选）
            category: 日志分类（可选）
            client_ip: 客户端IP（可选）
            req: HTTP请求信息（可选）
            resp: HTTP响应信息（可选）
            db: 数据库操作信息（可选）
            custom: 自定义字段（可选）
            error: 错误信息（可选），支持以下类型：
                   - Exception对象: 捕获的异常
                   - str: traceback.format_exc()的结果
                   - ErrorModel: 已构造的错误模型
            **kwargs: 其他额外字段
        """
        # 智能处理 error 参数
        formatted_error = self._format_error(error)

        # 只传递非 None 的参数
        log_kwargs = {
            k: v for k, v in {
                "event": event,
                "category": category,
                "client_ip": client_ip,
                "req": req,
                "resp": resp,
                "db": db,
                "custom": custom,
                "error": formatted_error,
            }.items() if v is not None
        }
        log_kwargs.update(kwargs)
        self._log("error", message, **log_kwargs)

    def critical(
        self,
        message: str,
        event: Optional[str] = None,
        category: Optional[Literal[
            "http",
            "business",
            "database",
            "validation",
            "error",
            "performance",
            "audit"
        ]] = None,
        client_ip: Optional[str] = None,
        req: Optional[HTTPRequestModel] = None,
        resp: Optional[HTTPResponseModel] = None,
        db: Optional[DatabaseModel] = None,
        custom: Optional[Dict[str, Any]] = None,
        error: Optional[ErrorModel] = None,
        **kwargs
    ) -> None:
        """记录 CRITICAL 级别日志

        Args:
            message: 日志消息（必需）
            event: 事件名称（可选）
            category: 日志分类（可选）
            client_ip: 客户端IP（可选）
            req: HTTP请求信息（可选）
            resp: HTTP响应信息（可选）
            db: 数据库操作信息（可选）
            custom: 自定义字段（可选）
            error: 错误信息（可选），支持以下类型：
                   - Exception对象: 捕获的异常
                   - str: traceback.format_exc()的结果
                   - ErrorModel: 已构造的错误模型
            **kwargs: 其他额外字段
        """
        # 智能处理 error 参数
        formatted_error = self._format_error(error)

        # 只传递非 None 的参数
        log_kwargs = {
            k: v for k, v in {
                "event": event,
                "category": category,
                "client_ip": client_ip,
                "req": req,
                "resp": resp,
                "db": db,
                "custom": custom,
                "error": formatted_error,
            }.items() if v is not None
        }
        log_kwargs.update(kwargs)
        self._log("critical", message, **log_kwargs)

    def debug(
        self,
        message: str,
        event: Optional[str] = None,
        category: Optional[Literal[
            "http",
            "business",
            "database",
            "validation",
            "error",
            "performance",
            "audit"
        ]] = None,
        client_ip: Optional[str] = None,
        req: Optional[HTTPRequestModel] = None,
        resp: Optional[HTTPResponseModel] = None,
        db: Optional[DatabaseModel] = None,
        custom: Optional[Dict[str, Any]] = None,
        error: Optional[ErrorModel] = None,
        **kwargs
    ) -> None:
        """记录 DEBUG 级别日志

        Args:
            message: 日志消息（必需）
            event: 事件名称（可选）
            category: 日志分类（可选）
            client_ip: 客户端IP（可选）
            req: HTTP请求信息（可选）
            resp: HTTP响应信息（可选）
            db: 数据库操作信息（可选）
            custom: 自定义字段（可选）
            error: 错误信息（可选）
            **kwargs: 其他额外字段
        """
        # 只传递非 None 的参数
        log_kwargs = {
            k: v for k, v in {
                "event": event,
                "category": category,
                "client_ip": client_ip,
                "req": req,
                "resp": resp,
                "db": db,
                "custom": custom,
                "error": error
            }.items() if v is not None
        }
        log_kwargs.update(kwargs)
        self._log("debug", message, **log_kwargs)

    def _format_error(self, error: Any) -> Optional[Dict[str, Any]]:
        """格式化错误信息"""
        if error is None:
            return None

        if isinstance(error, ErrorModel):
            return error.model_dump(exclude_none=True)

        if isinstance(error, dict):
            return error

        if isinstance(error, BaseException):
            import traceback
            return {
                "message": str(error),
                "error_type": type(error).__name__,
                "stack_trace": traceback.format_exc()
            }

        if isinstance(error, str):
            return {"message": error}

        return {"message": str(error), "error_type": type(error).__name__}

    def _log(self, level: str, message: str, **kwargs) -> None:
        """根据级别输出日志（自动注入公共字段，防御性设计）

        Args:
            level: 日志级别
            message: 日志消息
            **kwargs: 其他结构化字段（event, category, req, resp, db, error, custom 等）
        """
        try:
            # 构建日志数据
            log_data = {"message": message, **kwargs}

            # 自动设置默认的 category（如果没有提供）
            if "category" not in log_data:
                log_data["category"] = self._infer_category(log_data, level)

            # 自动设置默认的 event（如果没有提供）
            if "event" not in log_data:
                log_data["event"] = self._generate_default_event(
                    log_data, level)

            # 自动生成 trace_id 和 transaction_id（如果未设置）
            self._ensure_trace_and_transaction()

            # 使用 logger 输出日志（自动包含 contextvars 中的上下文）
            log_method = getattr(self.logger, level, self.logger.info)
            log_method(**log_data)
        except Exception as e:
            # 日志记录失败不应该影响业务逻辑
            import sys
            print(f"WARNING: Failed to write log: {e}", file=sys.stderr)

    def _ensure_trace_and_transaction(self) -> None:
        """确保 trace_id 和 transaction_id 存在（自动生成如果不存在）"""
        ctx = structlog.contextvars.get_contextvars()

        # 自动生成 trace_id（如果不存在）
        if "trace" not in ctx:
            trace_id = uuid.uuid4().hex
            structlog.contextvars.bind_contextvars(trace={"id": trace_id})

        # 自动生成 transaction_id（如果不存在）
        if "transaction" not in ctx:
            transaction_id = uuid.uuid4().hex
            structlog.contextvars.bind_contextvars(
                transaction={"id": transaction_id})

    def _infer_category(self, log_data: Dict[str, Any], level: str) -> str:
        """根据日志数据推断分类

        Args:
            log_data: 日志数据
            level: 日志级别

        Returns:
            推断的分类
        """
        # 根据包含的字段推断
        if "error" in log_data:
            return "error"
        elif "db" in log_data:
            return "database"
        elif "req" in log_data or "resp" in log_data:
            return "http"
        # 检测 SQLAlchemy 查询对象
        elif self._is_sqlalchemy_query(log_data):
            return "database"
        elif level in ["error", "critical"]:
            return "error"
        elif level == "warning":
            return "validation"
        else:
            # 默认为 business
            return "business"

    def _is_sqlalchemy_query(self, log_data: Dict[str, Any]) -> bool:
        """检测是否包含 SQLAlchemy 查询相关字段

        Args:
            log_data: 日志数据

        Returns:
            是否是数据库查询
        """
        # 检查是否包含 SQLAlchemy 相关的关键字
        SQLALCHEMY_KEYWORDS = {
            "query", "sql", "statement", "table", "model",
            "duration", "row_count", "rows_affected"
        }

        # 如果 custom 字段中包含这些关键字，可能是数据库操作
        custom = log_data.get("custom")
        if isinstance(custom, dict):
            custom_keys = set(custom.keys())
            # 如果有 2 个以上匹配，推断为数据库操作
            if len(custom_keys & SQLALCHEMY_KEYWORDS) >= 2:
                return True

        return False

    def _generate_default_event(self, log_data: Dict[str, Any], level: str) -> str:
        """生成默认的事件名称

        Args:
            log_data: 日志数据
            level: 日志级别

        Returns:
            生成的事件名称
        """
        category = log_data["category"]

        # 根据分类和级别生成事件名称
        if category == "error":
            return f"error_{level}"
        elif category == "database":
            # 尝试从 db 字段获取 statement_type
            if "db" in log_data and isinstance(log_data["db"], dict):
                statement_type = log_data["db"].get("statement_type", "query")
                return f"database_{statement_type.lower()}"
            return "database_query"
        elif category == "http":
            # 根据是否包含 req/resp 判断
            if "req" in log_data and "resp" not in log_data:
                return "http_request"
            elif "resp" in log_data and "req" not in log_data:
                return "http_response"
            else:
                return "http_transaction"
        elif category == "audit":
            return "audit_action"
        elif category == "performance":
            return "performance_metric"
        elif category == "validation":
            return "validation_check"
        else:
            # 默认 business 类型
            return f"business_{level}"


# 创建默认 logger 实例（可选使用）
logger = LogContext()
