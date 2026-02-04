# -*- coding: utf-8 -*-
"""
@文件: stack_parser.py
@说明: 堆栈信息解析器 - 将 traceback 转换为 ELK 友好的结构化数据
@时间: 2024
"""
import re
import traceback
from typing import List, Dict, Any, Optional, Tuple


class StackFrame:
    """堆栈帧数据结构"""
    def __init__(
        self,
        file: str,
        line: int,
        function: str,
        code: Optional[str] = None
    ):
        self.file = file
        self.line = line
        self.function = function
        self.code = code

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "file": self.file,
            "line": self.line,
            "function": self.function
        }
        if self.code:
            result["code"] = self.code
        return result


class StackTraceParser:
    """堆栈信息解析器"""

    # 匹配堆栈帧的正则表达式
    # 示例: File "/path/to/file.py", line 123, in function_name
    FRAME_PATTERN = re.compile(
        r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\S+)'
    )

    @classmethod
    def parse_traceback(cls, tb_string: str) -> List[Dict[str, Any]]:
        """
        解析 traceback 字符串为结构化堆栈帧列表

        Args:
            tb_string: traceback 字符串

        Returns:
            堆栈帧列表,每个帧包含 file, line, function, code

        Example:
            >>> tb = '''Traceback (most recent call last):
            ...   File "/app/main.py", line 10, in main
            ...     result = process()
            ...   File "/app/process.py", line 5, in process
            ...     raise ValueError("error")
            ... ValueError: error'''
            >>> frames = StackTraceParser.parse_traceback(tb)
            >>> frames[0]
            {
                'file': '/app/main.py',
                'line': 10,
                'function': 'main',
                'code': 'result = process()'
            }
        """
        frames = []
        lines = tb_string.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # 匹配堆栈帧信息
            match = cls.FRAME_PATTERN.search(line)
            if match:
                file_path = match.group(1)
                line_num = int(match.group(2))
                function_name = match.group(3)

                # 获取下一行代码
                code_snippet = None
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not cls.FRAME_PATTERN.search(next_line):
                        code_snippet = next_line

                frame = StackFrame(
                    file=file_path,
                    line=line_num,
                    function=function_name,
                    code=code_snippet
                )
                frames.append(frame.to_dict())

            i += 1

        return frames

    @classmethod
    def extract_error_location(cls, tb_string: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """
        提取错误的主要发生位置(最内层的堆栈帧)

        Args:
            tb_string: traceback 字符串

        Returns:
            (file_path, line_number, function_name) 元组

        Example:
            >>> tb = "File \"/app/main.py\", line 10, in main\\n..."
            >>> file, line, func = StackTraceParser.extract_error_location(tb)
            >>> file
            '/app/main.py'
            >>> line
            10
        """
        frames = cls.parse_traceback(tb_string)
        if frames:
            # 返回最后一个堆栈帧(最内层,即实际错误位置)
            last_frame = frames[-1]
            return (
                last_frame.get('file'),
                last_frame.get('line'),
                last_frame.get('function')
            )
        return None, None, None

    @classmethod
    def extract_exception_info(cls, tb_string: str) -> Tuple[Optional[str], Optional[str]]:
        """
        提取异常类型和消息

        Args:
            tb_string: traceback 字符串

        Returns:
            (exception_type, exception_message) 元组

        Example:
            >>> tb = "...\\nValueError: Invalid value"
            >>> exc_type, exc_msg = StackTraceParser.extract_exception_info(tb)
            >>> exc_type
            'ValueError'
            >>> exc_msg
            'Invalid value'
        """
        lines = tb_string.strip().split('\n')
        if not lines:
            return None, None

        # 最后一行通常是异常信息
        last_line = lines[-1].strip()

        # 匹配异常类型和消息: ExceptionType: message
        match = re.match(r'(\w+(?:\.\w+)*?):\s*(.*)', last_line)
        if match:
            exception_type = match.group(1)
            exception_message = match.group(2)
            return exception_type, exception_message

        return None, last_line

    @classmethod
    def format_for_elk(
        cls,
        exception: Exception,
        include_full_traceback: bool = True,
        max_frames: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        格式化异常为 ELK 友好的结构

        Args:
            exception: Python 异常对象
            include_full_traceback: 是否包含完整的文本 traceback
            max_frames: 最大堆栈帧数量(None表示无限制)

        Returns:
            ELK 优化的错误字典

        Example:
            >>> try:
            ...     raise ValueError("test error")
            ... except Exception as e:
            ...     error_dict = StackTraceParser.format_for_elk(e)
            >>> error_dict.keys()
            dict_keys(['message', 'error_type', 'stack_frames', 'error_file', ...])
        """
        # 获取完整的 traceback 文本
        # 使用 format_exception 从异常对象获取，而不是 format_exc()
        import sys
        if hasattr(exception, '__traceback__') and exception.__traceback__ is not None:
            # 从异常对象的 __traceback__ 属性获取
            tb_text = ''.join(traceback.format_exception(
                type(exception),
                exception,
                exception.__traceback__
            ))
        else:
            # 如果没有 traceback，尝试使用 format_exc()
            # 这种情况下只能获取当前的异常堆栈（如果在except块中）
            tb_text = traceback.format_exc()
            # 如果不在异常上下文中，format_exc()会返回"NoneType: None"
            if tb_text.strip() == "NoneType: None":
                tb_text = f"{type(exception).__name__}: {str(exception)}"

        # 解析堆栈帧
        stack_frames = cls.parse_traceback(tb_text)

        # 限制堆栈帧数量
        if max_frames and len(stack_frames) > max_frames:
            stack_frames = stack_frames[-max_frames:]

        # 提取错误位置
        error_file, error_line, error_function = cls.extract_error_location(tb_text)

        # 提取异常信息
        exc_type, exc_msg = cls.extract_exception_info(tb_text)
        if exc_type is None:
            exc_type = type(exception).__name__
        if exc_msg is None:
            exc_msg = str(exception)

        # 构建 ELK 友好的错误字典
        error_dict = {
            "message": exc_msg,
            "error_type": exc_type,
            "stack_frames": stack_frames,
            "error_file": error_file,
            "error_line": error_line,
            "error_function": error_function,
        }

        # 可选:包含完整文本(用于备查)
        if include_full_traceback:
            error_dict["stack_trace_text"] = tb_text

        return error_dict

    @classmethod
    def format_traceback_string(
        cls,
        tb_string: str,
        include_full_text: bool = True,
        max_frames: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        格式化 traceback 字符串为 ELK 友好的结构

        Args:
            tb_string: traceback 字符串
            include_full_text: 是否包含完整的文本
            max_frames: 最大堆栈帧数量

        Returns:
            ELK 优化的错误字典
        """
        # 解析堆栈帧
        stack_frames = cls.parse_traceback(tb_string)

        # 限制堆栈帧数量
        if max_frames and len(stack_frames) > max_frames:
            stack_frames = stack_frames[-max_frames:]

        # 提取错误位置
        error_file, error_line, error_function = cls.extract_error_location(tb_string)

        # 提取异常信息
        exc_type, exc_msg = cls.extract_exception_info(tb_string)

        # 构建错误字典
        error_dict = {
            "message": exc_msg or "Unknown error",
            "error_type": exc_type,
            "stack_frames": stack_frames,
            "error_file": error_file,
            "error_line": error_line,
            "error_function": error_function,
        }

        # 可选:包含完整文本
        if include_full_text:
            error_dict["stack_trace_text"] = tb_string

        return error_dict

    @classmethod
    def simplify_file_path(cls, file_path: str, keep_levels: int = 3) -> str:
        """
        简化文件路径,保留最后几级目录

        Args:
            file_path: 完整文件路径
            keep_levels: 保留的目录层级数

        Returns:
            简化后的路径

        Example:
            >>> StackTraceParser.simplify_file_path(
            ...     "/home/ubuntu/autoML_server/data_preprocess_client/sdk.py",
            ...     keep_levels=3
            ... )
            'data_preprocess_client/sdk.py'
        """
        parts = file_path.split('/')
        if len(parts) <= keep_levels:
            return file_path
        return '/'.join(parts[-keep_levels:])
