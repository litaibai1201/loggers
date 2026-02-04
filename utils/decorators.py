# -*- coding: utf-8 -*-
"""
@文件: decorators.py
@说明: 通用日志装饰器 - 用于性能监控和自动日志记录
@时间: 2024
"""
import functools
import time
from typing import Callable, Optional

from ..core.context import logger


class LogExecutionTime:
    """执行时间装饰器 - 记录函数执行时间

    适用于任何需要监控执行时间的函数，不限于数据库操作。
    """

    @staticmethod
    def track(
        slow_threshold: Optional[float] = None,
        category: str = "performance"
    ) -> Callable:
        """
        装饰器：追踪函数执行时间

        Args:
            slow_threshold: 慢执行阈值（秒），超过此值会记录warning日志。默认为None（不检查）
            category: 日志分类，默认为 "performance"

        Usage:
            @LogExecutionTime.track(slow_threshold=1.0)
            def search_employees(keyword):
                # 函数体
                pass

            @LogExecutionTime.track(slow_threshold=0.5, category="business")
            def process_order(order_id):
                # 函数体
                pass
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()

                try:
                    result = func(*args, **kwargs)
                    duration = time.time() - start_time

                    # 如果设置了阈值且超过阈值，记录警告日志
                    if slow_threshold is not None and duration > slow_threshold:
                        logger.warning(
                            f"函数执行缓慢: {func.__name__}",
                            category=category,
                            custom={
                                "function": func.__name__,
                                "module": func.__module__,
                                "duration": round(duration, 3),
                                "threshold": slow_threshold,
                                "args_count": len(args),
                                "kwargs_keys": list(kwargs.keys()),
                                "status": "slow"
                            }
                        )
                    else:
                        # 正常执行，记录 info 日志
                        logger.info(
                            f"函数执行完成: {func.__name__}",
                            category=category,
                            custom={
                                "function": func.__name__,
                                "module": func.__module__,
                                "duration": round(duration, 3),
                                "status": "success"
                            }
                        )

                    return result

                except Exception as e:
                    duration = time.time() - start_time
                    logger.error(
                        f"函数执行失败: {func.__name__}",
                        error=e,
                        custom={
                            "function": func.__name__,
                            "duration": round(duration, 3),
                            "status": "failed"
                        }
                    )
                    raise

            return wrapper
        return decorator
