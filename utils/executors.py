# -*- coding: utf-8 -*-
"""
@文件: executors.py
@说明: 上下文感知的线程池/进程池执行器
@时间: 2024-12-03
"""
import functools
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Callable, TypeVar, Any, Optional

from ..core.context import logger


T = TypeVar('T')


class ContextAwareThreadPoolExecutor(ThreadPoolExecutor):
    """上下文感知的线程池执行器

    自动管理日志上下文生命周期，解决线程复用导致的上下文污染问题。

    问题场景:
        # ❌ 标准 ThreadPoolExecutor 的问题
        executor = ThreadPoolExecutor(max_workers=2)

        # 任务1 在线程1 执行，设置 trace_id = "abc"
        executor.submit(task1)

        # 任务2 复用线程1，继承了错误的 trace_id = "abc"
        executor.submit(task2)  # 应该有新的 trace_id!

    解决方案:
        # ✅ 使用 ContextAwareThreadPoolExecutor
        executor = ContextAwareThreadPoolExecutor(max_workers=2)

        # 任务1 在线程1 执行，设置 trace_id = "abc"
        executor.submit(task1)  # 自动清理上下文

        # 任务2 复用线程1，有新的 trace_id
        executor.submit(task2)  # ✅ 上下文干净

    使用示例:
        from loggers.utils import ContextAwareThreadPoolExecutor
        from loggers import logger

        def process_task(task_id):
            logger.info(f"Processing task {task_id}")
            # 无需手动调用 clear_context()
            return task_id * 2

        with ContextAwareThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_task, i) for i in range(10)]
            results = [f.result() for f in futures]
    """

    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any):
        """提交任务到线程池（自动清理上下文）

        Args:
            fn: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Future: 任务的 Future 对象
        """
        @functools.wraps(fn)
        def wrapped_fn(*args, **kwargs):
            try:
                # 执行任务
                return fn(*args, **kwargs)
            finally:
                # 任务结束后自动清理上下文
                try:
                    logger.clear_context()
                except Exception:
                    # 清理失败不应该影响任务结果
                    pass

        return super().submit(wrapped_fn, *args, **kwargs)


class ContextAwareProcessPoolExecutor(ProcessPoolExecutor):
    """上下文感知的进程池执行器（实验性功能）

    ⚠️ 注意: contextvars 不会自动跨进程传递！

    此执行器会尝试传递 trace_id 到子进程，但有以下限制:
    1. 只能传递简单的字符串类型的 trace_id
    2. 不能传递完整的上下文对象
    3. 需要在子进程中手动设置 trace_id

    建议:
    - 如果需要跨进程的链路追踪，建议显式传递 trace_id 作为参数
    - 或使用消息队列等外部存储

    使用示例:
        from loggers.utils import ContextAwareProcessPoolExecutor
        from loggers import logger

        def process_task(task_id, trace_id=None):
            # 如果提供了 trace_id，手动设置
            if trace_id:
                logger.set_trace_id(trace_id)

            logger.info(f"Processing task {task_id}")
            return task_id * 2

        # 需要显式传递 trace_id
        trace_id = logger.get_trace_id()

        with ContextAwareProcessPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(process_task, i, trace_id=trace_id)
                for i in range(10)
            ]
            results = [f.result() for f in futures]
    """

    def __init__(self, max_workers: Optional[int] = None, **kwargs):
        """初始化进程池执行器

        Args:
            max_workers: 最大工作进程数
            **kwargs: 其他参数传递给 ProcessPoolExecutor
        """
        super().__init__(max_workers=max_workers, **kwargs)

        # 输出警告信息
        import sys
        print(
            "⚠️  ContextAwareProcessPoolExecutor: contextvars 不会自动跨进程传递！",
            file=sys.stderr
        )
        print(
            "   建议显式传递 trace_id 作为函数参数。",
            file=sys.stderr
        )


def context_cleanup_decorator(func: Callable[..., T]) -> Callable[..., T]:
    """装饰器：自动清理日志上下文

    用于普通函数，确保执行结束后清理上下文。
    特别适用于线程池中的任务函数。

    使用示例:
        from loggers.utils import context_cleanup_decorator
        from loggers import logger

        @context_cleanup_decorator
        def process_task(task_id):
            logger.info(f"Processing task {task_id}")
            return task_id * 2

        # 标准 ThreadPoolExecutor 也能安全使用
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_task, i) for i in range(10)]
            results = [f.result() for f in futures]
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        finally:
            try:
                logger.clear_context()
            except Exception:
                pass

    return wrapper
