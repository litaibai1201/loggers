# -*- coding: utf-8 -*-
"""
@文件: logger.py
@说明: 日志配置和初始化
@时间: 2024
"""
import logging.config
import socket
import os
import sys
import atexit
from typing import Any, Dict, Optional
from queue import Queue
from logging.handlers import QueueHandler, QueueListener

import structlog
from pydantic import ValidationError

from ..conf import LOGGING_CONFIG
from .models import LogModel

# 全局变量：保存 QueueListener 实例
_queue_listener: Optional[QueueListener] = None


class LoggerConfig:
    """日志配置管理器"""

    @staticmethod
    def get_host_ip() -> str:
        """获取本机IP地址"""
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "unknown"

    @staticmethod
    def validate_log_structure(_logger: Any, _method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """验证日志数据结构

        Note: _logger 和 _method_name 是 structlog 处理器接口要求的参数,
              虽然在此方法中未使用,但必须保留以符合接口规范
        """
        try:
            LogModel(**event_dict)
        except ValidationError as e:
            # 日志验证失败时,记录错误但不中断业务
            error_logger = logging.getLogger("my.custom.error")
            error_logger.error(
                f"Log validation failed (non-blocking): {str(e)}\n"
                f"Original log data: {event_dict}"
            )
            # 不抛出异常,保证业务代码不被中断
            # 添加标记字段表明这是一个格式错误的日志
            event_dict["_validation_error"] = str(e)
        event_dict.setdefault("client_ip", LoggerConfig.get_host_ip())
        return event_dict


def configure_logger(use_queue_handler: Optional[bool] = None):
    """初始化日志系统

    Args:
        use_queue_handler: 是否使用队列处理器（非阻塞日志记录）
            - None: 自动判断（检测 asyncio 环境或读取配置文件）
            - True: 强制启用（推荐用于 FastAPI/AsyncIO/高并发应用）
            - False: 禁用（推荐用于多进程应用或低并发场景）

    使用场景:
        # 场景1: FastAPI/AsyncIO 应用
        configure_logger(use_queue_handler=True)

        # 场景2: 多进程应用 (Gunicorn)
        configure_logger(use_queue_handler=False)

        # 场景3: 自动检测
        configure_logger()  # 会自动检测环境

        # 场景4: 通过环境变量控制
        # export LOG_USE_QUEUE_HANDLER=true
        configure_logger()
    """
    # 确保日志目录存在
    _ensure_log_directories()

    # 准备配置（注入目录设置到处理器）
    config = _prepare_logging_config()

    # 配置标准日志处理器
    logging.config.dictConfig(config)

    # 判断是否启用队列处理器
    if use_queue_handler is None:
        # 优先从配置文件读取
        config_value = LOGGING_CONFIG.get('use_queue_handler')

        if config_value is not None:
            # 配置文件中明确设置了值（True 或 False）
            use_queue_handler = config_value
        else:
            # 配置文件未设置，自动检测 asyncio 环境
            use_queue_handler = _is_asyncio_environment()

    # 设置队列处理器（如果启用）
    if use_queue_handler:
        _setup_queue_handler()

    # 配置 structlog（使用原生 contextvars 支持）
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # 🔥 自动合并 contextvars
            LoggerConfig.validate_log_structure,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
        context_class=dict,  # 使用 dict 作为上下文存储
    )


def _prepare_logging_config() -> Dict[str, Any]:
    """准备日志配置，注入目录设置到处理器

    Returns:
        修改后的日志配置字典
    """
    import copy
    config = copy.deepcopy(LOGGING_CONFIG)

    # 获取目录配置
    log_dir = config.get('log_dir', 'logs')
    archive_subdir = config.get('archive_subdir', 'archive')
    lock_subdir = config.get('lock_subdir', '.locks')
    max_backup_count = config.get('max_backup_count', 14)

    # 计算完整路径
    archive_dir_path = os.path.join(log_dir, archive_subdir)
    lock_dir_path = os.path.join(log_dir, lock_subdir)

    # 注入目录配置到处理器
    handlers = config.get('handlers', {})
    for handler_name, handler_config in handlers.items():
        # 处理使用 OrganizedFileHandler 的处理器
        if 'OrganizedFileHandler' in handler_config.get('class', ''):
            # 拼接完整的文件路径（log_dir + filename）
            if 'filename' in handler_config:
                filename = handler_config['filename']
                # 如果 filename 不包含目录，则拼接 log_dir
                if not os.path.dirname(filename):
                    handler_config['filename'] = os.path.join(log_dir, filename)
            # 添加归档目录配置
            handler_config['archive_dir'] = archive_dir_path
            # 添加锁文件目录配置
            handler_config['lock_dir'] = lock_dir_path
            # 使用全局配置的备份数量（如果处理器没有单独设置）
            if 'backupCount' not in handler_config:
                handler_config['backupCount'] = max_backup_count

    return config


def _ensure_log_directories():
    """确保所有日志目录都存在（包括归档目录和锁文件目录）"""
    # 获取配置的目录
    log_dir = LOGGING_CONFIG.get('log_dir', 'logs')
    archive_subdir = LOGGING_CONFIG.get('archive_subdir', 'archive')
    lock_subdir = LOGGING_CONFIG.get('lock_subdir', '.locks')

    # 创建主日志目录
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # 创建归档目录
    archive_dir = os.path.join(log_dir, archive_subdir)
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir, exist_ok=True)

    # 创建锁文件目录
    lock_dir = os.path.join(log_dir, lock_subdir)
    if not os.path.exists(lock_dir):
        os.makedirs(lock_dir, exist_ok=True)

    # 确保 handler 配置中的目录也存在
    handlers = LOGGING_CONFIG.get("handlers", {})
    for _handler_name, handler_config in handlers.items():
        if "filename" in handler_config:
            log_file = handler_config["filename"]
            file_dir = os.path.dirname(log_file)
            if file_dir and not os.path.exists(file_dir):
                os.makedirs(file_dir, exist_ok=True)


def _is_asyncio_environment() -> bool:
    """检测是否运行在 asyncio 环境中

    Returns:
        bool: True 表示检测到 asyncio/FastAPI/异步框架
    """
    # 检测常见的异步框架模块
    async_modules = ['asyncio', 'fastapi', 'aiohttp', 'tornado', 'sanic']
    for module in async_modules:
        if module in sys.modules:
            return True
    return False


def _setup_queue_handler():
    """设置队列处理器（用于 AsyncIO 和高并发场景）

    工作原理:
        1. 创建线程安全的队列
        2. 业务线程将日志放入队列（非阻塞，极快）
        3. 后台线程从队列取日志并写入文件（串行，无竞争）

    优势:
        - 业务线程不会被文件 I/O 阻塞
        - 避免多线程竞争文件锁（特别是 Windows）
        - AsyncIO 应用不会阻塞事件循环
    """
    global _queue_listener

    logger = logging.getLogger('my.custom')

    # 如果已经设置过，先停止旧的监听器
    if _queue_listener is not None:
        _queue_listener.stop()

    # 保存原始的 handlers
    original_handlers = logger.handlers[:]

    if not original_handlers:
        # 如果没有 handlers，直接返回
        return

    # 创建队列
    queue_size = LOGGING_CONFIG.get('queue_size', -1)
    log_queue = Queue(maxsize=queue_size)

    # 创建队列处理器
    queue_handler = QueueHandler(log_queue)

    # 创建队列监听器（在后台线程中处理日志）
    _queue_listener = QueueListener(
        log_queue,
        *original_handlers,
        respect_handler_level=True  # 尊重每个 handler 的日志级别
    )

    # 替换 logger 的 handlers
    logger.handlers = [queue_handler]

    # 启动后台监听线程
    _queue_listener.start()

    # 注册退出时停止监听器
    atexit.register(_stop_queue_listener)

    # 输出提示信息
    import sys
    print("✅ QueueHandler enabled - Non-blocking logging activated", file=sys.stderr)
    print(
        f"   Queue size: {'unlimited' if queue_size == -1 else queue_size}", file=sys.stderr)
    print(f"   Platform: {sys.platform}", file=sys.stderr)


def _stop_queue_listener():
    """停止队列监听器（在程序退出时调用）"""
    global _queue_listener
    if _queue_listener is not None:
        _queue_listener.stop()
        _queue_listener = None


def get_queue_handler_status() -> Dict[str, Any]:
    """获取队列处理器状态（用于监控和调试）

    Returns:
        dict: 包含状态信息的字典
    """
    global _queue_listener

    if _queue_listener is None:
        return {
            "enabled": False,
            "message": "QueueHandler is not enabled"
        }

    logger = logging.getLogger('my.custom')
    queue_handler = None

    # 查找 QueueHandler
    for handler in logger.handlers:
        if isinstance(handler, QueueHandler):
            queue_handler = handler
            break

    if queue_handler is None:
        return {
            "enabled": False,
            "message": "QueueHandler not found in logger handlers"
        }

    queue = queue_handler.queue
    return {
        "enabled": True,
        "queue_size_current": queue.qsize(),
        "queue_size_max": queue.maxsize if queue.maxsize > 0 else "unlimited",
        "message": "QueueHandler is running"
    }


