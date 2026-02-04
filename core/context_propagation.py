# -*- coding: utf-8 -*-
"""
@文件: context_propagation.py
@说明: 线程上下文自动传递功能
@时间: 2024
"""
import contextvars
import threading
from functools import wraps


# 保存原始的 Thread.__init__
_original_thread_init = threading.Thread.__init__
_context_propagation_enabled = False


def _context_aware_thread_init(self, *args, **kwargs):
    """支持 contextvars 的 Thread.__init__ 包装器

    自动将父线程的 contextvars 上下文传递给子线程，
    使得子线程可以继承父线程的 trace_id、transaction_id 等上下文信息。

    注意：
    1. 子线程获得的是父线程上下文的**快照副本**（深拷贝）
    2. 父线程后续的上下文修改（包括 clear_context()）不会影响子线程
    3. 子线程可以自由修改自己的上下文，不会影响父线程
    """
    # 获取当前线程的上下文快照
    ctx = contextvars.copy_context()

    # 获取原始的 target 函数
    target = kwargs.get('target') or (args[1] if len(args) > 1 else None)

    if target is not None:
        # 包装 target 函数，使其在父线程的上下文副本中运行
        @wraps(target)
        def wrapped_target(*target_args, **target_kwargs):
            return ctx.run(target, *target_args, **target_kwargs)

        # 替换 target
        if 'target' in kwargs:
            kwargs['target'] = wrapped_target
        else:
            args = list(args)
            if len(args) > 1:
                args[1] = wrapped_target
            args = tuple(args)

    # 调用原始的 __init__
    _original_thread_init(self, *args, **kwargs)


def enable_context_propagation():
    """启用线程上下文自动传递

    调用此函数后，所有通过 threading.Thread 创建的子线程都会自动继承
    父线程的 contextvars 上下文（包括 trace_id、transaction_id 等）。

    使用场景：
    - 在应用启动时调用一次即可（如 app.py 或 __init__.py）
    - 适用于需要追踪异步任务、后台处理等场景
    - 对现有代码零侵入，无需修改业务代码

    示例：
        # 在应用启动时
        from loggers import enable_context_propagation, logger
        enable_context_propagation()

        # 之后所有线程代码无需修改
        def api_handler():
            logger.set_trace_id("req-123")

            # 子线程自动继承 trace_id = "req-123"
            threading.Thread(target=background_task).start()

    注意事项：
    1. 子线程获得的是上下文的**快照副本**，父子线程互不影响
    2. 父线程调用 clear_context() 不会影响已创建的子线程
    3. 如果需要子线程使用独立的 trace_id，可以在子线程中显式调用 set_trace_id()

    兼容性：
    - 支持 threading.Thread
    - 支持 concurrent.futures.ThreadPoolExecutor
    - 支持所有基于 threading.Thread 的第三方库
    """
    global _context_propagation_enabled
    if not _context_propagation_enabled:
        threading.Thread.__init__ = _context_aware_thread_init
        _context_propagation_enabled = True


def disable_context_propagation():
    """禁用线程上下文自动传递（恢复原始行为）

    调用此函数后，threading.Thread 将恢复到 Python 原生行为，
    子线程不再自动继承父线程的 contextvars 上下文。

    使用场景：
    - 调试或测试时需要验证原生行为
    - 某些特殊场景需要完全隔离的线程上下文

    示例：
        from loggers import disable_context_propagation
        disable_context_propagation()
    """
    global _context_propagation_enabled
    if _context_propagation_enabled:
        threading.Thread.__init__ = _original_thread_init
        _context_propagation_enabled = False


def is_context_propagation_enabled() -> bool:
    """检查线程上下文自动传递是否已启用

    Returns:
        bool: True 表示已启用，False 表示未启用
    """
    return _context_propagation_enabled
