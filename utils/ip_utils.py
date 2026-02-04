# -*- coding: utf-8 -*-
"""
@文件: ip_utils.py
@说明: IP 地址获取工具
@时间: 2024
"""
from typing import Optional, Union


def get_real_ip_from_flask() -> Optional[str]:
    """从 Flask 请求中获取真实客户端 IP

    优先级:
    1. X-Forwarded-For (代理/负载均衡器设置)
    2. X-Real-IP (Nginx 等反向代理设置)
    3. request.remote_addr (直连 IP)

    Returns:
        客户端真实 IP,如果无法获取则返回 None
    """
    try:
        from flask import request

        # 1. 优先从 X-Forwarded-For 获取(可能包含多个 IP,取第一个)
        if request.headers.get('X-Forwarded-For'):
            # X-Forwarded-For: client, proxy1, proxy2
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()

        # 2. 从 X-Real-IP 获取
        if request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP').strip()

        # 3. 直接从 request 获取
        if request.remote_addr:
            return request.remote_addr

        return None
    except (ImportError, RuntimeError):
        # Flask 未安装或不在请求上下文中
        return None


def get_real_ip_from_fastapi(request) -> Optional[str]:
    """从 FastAPI 请求中获取真实客户端 IP

    Args:
        request: FastAPI Request 对象

    Returns:
        客户端真实 IP,如果无法获取则返回 None
    """
    try:
        # 1. 优先从 X-Forwarded-For 获取
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        # 2. 从 X-Real-IP 获取
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()

        # 3. 从 client 获取
        if request.client and request.client.host:
            return request.client.host

        return None
    except Exception:
        return None


def get_real_ip_from_django() -> Optional[str]:
    """从 Django 请求中获取真实客户端 IP

    Returns:
        客户端真实 IP,如果无法获取则返回 None
    """
    try:
        from django.http import HttpRequest
        # 尝试从线程本地存储获取当前请求
        import threading
        request = getattr(threading.current_thread(), 'request', None)

        if not request or not isinstance(request, HttpRequest):
            return None

        # 1. 优先从 X-Forwarded-For 获取
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        # 2. 从 X-Real-IP 获取
        real_ip = request.META.get('HTTP_X_REAL_IP')
        if real_ip:
            return real_ip.strip()

        # 3. 从 REMOTE_ADDR 获取
        return request.META.get('REMOTE_ADDR')
    except (ImportError, AttributeError):
        return None


def get_real_ip(request=None) -> Optional[str]:
    """自动检测框架并获取真实客户端 IP

    Args:
        request: 可选的请求对象(用于 FastAPI 等需要显式传递的框架)

    Returns:
        客户端真实 IP,如果无法获取则返回 None

    使用示例:
        # Flask 应用
        from loggers.utils.ip_utils import get_real_ip
        client_ip = get_real_ip()
        logger.info("用户登录", client_ip=client_ip)

        # FastAPI 应用
        @app.get("/api/test")
        async def test(request: Request):
            client_ip = get_real_ip(request)
            logger.info("API 调用", client_ip=client_ip)
    """
    # 如果提供了 request 对象,尝试从中提取 IP
    if request is not None:
        # 检测是否是 FastAPI Request
        if hasattr(request, 'client') and hasattr(request, 'headers'):
            ip = get_real_ip_from_fastapi(request)
            if ip:
                return ip

    # 尝试从 Flask 获取
    ip = get_real_ip_from_flask()
    if ip:
        return ip

    # 尝试从 Django 获取
    ip = get_real_ip_from_django()
    if ip:
        return ip

    return None
