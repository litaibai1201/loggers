# -*- coding: utf-8 -*-
"""
@文件: log_conf.py
@说明: 日志系统配置
@时间: 2024
"""

LOGGING_CONFIG = {
    # 服务配置
    'service_name': 'AIML_DATASET_SERVICE',
    'environment': 'prd',  # dev, test, prd

    # 队列处理器配置 (用于 AsyncIO 和高并发场景)
    # 设置为 True 启用非阻塞日志记录，推荐用于:
    # - FastAPI/AsyncIO 应用
    # - 高并发 Flask 应用
    # 设置为 False 使用传统方式，推荐用于:
    # - 多进程应用 (Gunicorn with multiple workers)
    # - 低并发 CLI 工具
    'use_queue_handler': False,

    # 队列大小 (-1 表示无限制)
    'queue_size': -1,

    # 日志配置
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple_msg': {
            'format': '%(message)s'
        },
        'basic_format': {
            'format': '[%(asctime)s][%(filename)s][%(lineno)s][%(levelname)s][%(thread)d] - %(message)s'
        },
    },
    'handlers': {
        # 默认应用日志
        'file_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'formatter': 'simple_msg',
            'level': 'DEBUG',
            'filename': 'logs/myapp.log',
            'when': 'D',
            'interval': 1,
            'backupCount': 14,
            'maxBytes': 200 * 1024 * 1024,
            'encoding': 'utf-8',
            'use_gzip': False,
        },
        # 错误日志
        'error_file_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'formatter': 'basic_format',
            'level': 'ERROR',
            'filename': 'logs/error.log',
            'when': 'D',
            'interval': 1,
            'backupCount': 7,
            'maxBytes': 200 * 1024 * 1024,
            'encoding': 'utf-8',
            'use_gzip': False,
        },
        # 测试日志
        'test_handler': {
            'class': 'concurrent_log_handler.ConcurrentTimedRotatingFileHandler',
            'formatter': 'simple_msg',
            'level': 'DEBUG',
            'filename': 'logs/test.log',
            'when': 'D',
            'interval': 1,
            'backupCount': 7,
            'maxBytes': 200 * 1024 * 1024,
            'encoding': 'utf-8',
            'use_gzip': False,
        },
    },
    'loggers': {
        # 默认 logger
        'my.custom': {
            'handlers': ['file_handler', 'error_file_handler'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'my.custom.error': {
            'handlers': ['error_file_handler'],
            'level': 'ERROR',
            'propagate': False,
        },
        # 测试日志
        'test': {
            'handlers': ['test_handler', 'error_file_handler'],
            'level': 'DEBUG',
            'propagate': False,
        }
    }
}
