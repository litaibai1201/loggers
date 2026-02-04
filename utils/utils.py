# -*- coding: utf-8 -*-
"""
@文件: utils.py
@说明: 日志工具函数
@时间: 2024
"""
import time
import traceback
from typing import Any, Callable, Optional, TypeVar

from ..core.context import logger


T = TypeVar("T")


class DatabaseLogger:
    """数据库操作日志记录器"""

    @staticmethod
    def log_query(
        sql: str,
        status: str = "success",
        duration: Optional[float] = None,
        event: str = None,
        statement_type: str = None,
    ) -> None:
        """记录数据库查询

        Args:
            sql: SQL 语句
            status: 状态（success/fail）
            duration: 执行时长
            event: 事件名称（可选，默认自动生成）
            statement_type: SQL 类型（可选，如 SELECT, INSERT）
        """

        # 使用新 API
        if status == "success":
            logger.info(
                "数据库查询成功",
                custom={
                    "sql": sql[:500],  # 限制长度
                    "statement": statement_type or "QUERY",
                    "status": status,
                    "duration": duration or 0.0,
                    "db_name": "oracle_db"
                }
            )
        else:
            logger.warning(
                "数据库查询失败",
                custom={
                    "sql": sql[:500],
                    "statement": statement_type or "QUERY",
                    "status": status,
                    "duration": duration or 0.0,
                    "db_name": "oracle_db"
                }
            )

    @staticmethod
    def log_error(
        sql: str,
        error_message: str,
        event: str = None,
    ) -> None:
        """记录数据库错误

        Args:
            sql: SQL 语句
            error_message: 错误消息
            event: 事件名称（可选，默认自动生成）
        """

        # 使用新 API
        logger.error(
            f"Database operation failed: {error_message}",
            custom={
                "message": error_message,
                "error_type": "DatabaseError",
                "context": {
                    "sql": sql[:500],  # 限制长度
                    "operation": event or "database_operation"
                }
            }
        )


class LogExecutionTime:
    """执行时间日志装饰器"""

    @staticmethod
    def track(event: str = "operation") -> Callable:
        """装饰函数以跟踪执行时间"""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            def wrapper(*args, **kwargs) -> T:
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = round(time.time() - start_time, 3)

                    # 使用新 API
                    logger.info(
                        f"函数 {func.__name__} 执行成功",
                        custom={
                            "function": func.__name__,
                            "duration": duration,
                            "status": "success",
                            "event": event
                        }
                    )
                    return result
                except Exception as e:
                    duration = round(time.time() - start_time, 3)

                    # 使用新 API
                    logger.error(
                        f"Function {func.__name__} failed: {str(e)}",
                        error= e,
                        custom={
                            "message": f"Function {func.__name__} failed",
                            "error_type": type(e).__name__,
                            "context": {
                                "function": func.__name__,
                                "duration": duration,
                                "event": event
                            }
                        }
                    )
                    raise

            return wrapper

        return decorator
