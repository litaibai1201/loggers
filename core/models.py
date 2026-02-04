# -*- coding: utf-8 -*-
"""
@文件: models.py
@说明: 日志数据模型定义
@时间: 2024
"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict


class ServiceModel(BaseModel):
    """服务信息模型"""
    name: str
    environment: str

    model_config = ConfigDict(extra="forbid")


class TraceModel(BaseModel):
    """链路追踪ID模型"""
    id: str

    model_config = ConfigDict(extra="forbid")


class TransactionModel(BaseModel):
    """事务ID模型"""
    id: str

    model_config = ConfigDict(extra="forbid")


class HTTPRequestModel(BaseModel):
    """HTTP请求模型"""
    method: str
    path: str
    headers: Dict[str, Any]
    body: Any

    model_config = ConfigDict(extra="forbid")


class HTTPResponseModel(BaseModel):
    """HTTP响应模型"""
    status_code: int
    body: Any
    event_duration: float

    model_config = ConfigDict(extra="forbid")


class DatabaseModel(BaseModel):
    """数据库操作模型 - 扩展版本"""
    statement: str
    statement_type: Optional[str] = None  # SELECT, INSERT, UPDATE, DELETE
    table: Optional[str] = None  # 操作的表名
    status: str
    duration: float
    row_count: Optional[int] = None  # 返回或影响的行数
    db_name: Optional[str] = None  # 数据库名称

    model_config = ConfigDict(extra="forbid")


class StackFrameModel(BaseModel):
    """堆栈帧模型 - ELK优化"""
    file: str  # 文件路径
    line: int  # 行号
    function: str  # 函数名
    code: Optional[str] = None  # 代码片段

    model_config = ConfigDict(extra="forbid")


class ErrorModel(BaseModel):
    """
    错误信息模型 - ELK优化版本

    支持两种使用方式:
    1. 传统方式: 只传 message 和 stack_trace (兼容旧代码)
    2. ELK优化: 传 message, error_type, stack_frames 等结构化字段
    """
    message: str
    error_type: Optional[str] = None  # 异常类型 (如 ValueError, TypeError)
    error_code: Optional[str] = None  # 业务错误代码

    # 结构化堆栈信息 - ELK 友好 ⭐
    stack_frames: Optional[List[StackFrameModel]] = None  # 结构化堆栈帧数组

    # 关键错误位置信息 - 便于 Kibana 搜索和过滤 ⭐
    error_file: Optional[str] = None  # 错误发生的文件
    error_line: Optional[int] = None  # 错误发生的行号
    error_function: Optional[str] = None  # 错误发生的函数

    # 完整文本堆栈 - 备用(可选)
    stack_trace: Optional[str] = None  # 完整的 traceback 文本
    stack_trace_text: Optional[str] = None  # 别名,与 stack_trace 相同

    context: Optional[Dict[str, Any]] = None  # 错误上下文

    model_config = ConfigDict(extra="allow")  # 允许额外字段,向后兼容


class LogModel(BaseModel):
    """主日志模型 - 定义完整的日志结构"""
    message: str  # 日志消息（必需）
    event: Optional[str] = None  # 事件名称（可选）
    category: Optional[Literal[
        "http",
        "business",
        "database",
        "validation",
        "error",
        "performance",
        "audit"
    ]] = None  # 分类（可选）
    service: Optional[ServiceModel] = None
    client_ip: Optional[str] = None
    trace: Optional[TraceModel] = None
    transaction: Optional[TransactionModel] = None
    req: Optional[HTTPRequestModel] = None
    resp: Optional[HTTPResponseModel] = None
    db: Optional[DatabaseModel] = None
    custom: Optional[Dict[str, Any]] = None
    error: Optional[ErrorModel] = None

    model_config = ConfigDict(extra="allow")  # 允许额外字段，提供更大灵活性
