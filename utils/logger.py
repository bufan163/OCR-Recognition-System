import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import os

from config import settings


def setup_logger(name: str = None, log_file: str = None) -> logging.Logger:
    """设置日志记录器"""
    
    # 创建日志目录
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取或创建logger
    logger_name = name or "ocr_system"
    logger = logging.getLogger(logger_name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 创建格式化器
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器 - 按大小轮转
    file_path = log_file or settings.log_file
    file_handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 错误日志文件处理器
    error_file_path = file_path.replace('.log', '_error.log')
    error_handler = RotatingFileHandler(
        filename=error_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    # 防止日志传播到根logger
    logger.propagate = False
    
    return logger


def setup_access_logger() -> logging.Logger:
    """设置访问日志记录器"""
    logger = logging.getLogger("access")
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 访问日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 访问日志文件处理器 - 按天轮转
    log_dir = Path(settings.log_file).parent
    access_log_path = log_dir / "access.log"
    
    access_handler = TimedRotatingFileHandler(
        filename=access_log_path,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(formatter)
    logger.addHandler(access_handler)
    
    logger.propagate = False
    return logger


def setup_performance_logger() -> logging.Logger:
    """设置性能日志记录器"""
    logger = logging.getLogger("performance")
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 性能日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 性能日志文件处理器
    log_dir = Path(settings.log_file).parent
    perf_log_path = log_dir / "performance.log"
    
    perf_handler = RotatingFileHandler(
        filename=perf_log_path,
        maxBytes=50 * 1024 * 1024,  # 50MB
        backupCount=3,
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.setFormatter(formatter)
    logger.addHandler(perf_handler)
    
    logger.propagate = False
    return logger


def log_api_request(endpoint: str, method: str, user_id: int = None, 
                   response_time: float = None, status_code: int = None,
                   request_size: int = None, response_size: int = None):
    """记录API请求日志"""
    access_logger = setup_access_logger()
    
    log_data = {
        "endpoint": endpoint,
        "method": method,
        "user_id": user_id,
        "response_time": f"{response_time:.3f}s" if response_time else None,
        "status_code": status_code,
        "request_size": request_size,
        "response_size": response_size,
        "timestamp": datetime.now().isoformat()
    }
    
    # 过滤None值
    log_data = {k: v for k, v in log_data.items() if v is not None}
    
    access_logger.info(f"API Request: {log_data}")


def log_ocr_performance(engine: str, file_size: int, processing_time: float,
                       page_count: int = 1, success: bool = True,
                       error_message: str = None):
    """记录OCR性能日志"""
    perf_logger = setup_performance_logger()
    
    log_data = {
        "engine": engine,
        "file_size_mb": round(file_size / 1024 / 1024, 2),
        "processing_time": f"{processing_time:.3f}s",
        "page_count": page_count,
        "avg_time_per_page": f"{processing_time / page_count:.3f}s",
        "success": success,
        "error": error_message,
        "timestamp": datetime.now().isoformat()
    }
    
    # 过滤None值
    log_data = {k: v for k, v in log_data.items() if v is not None}
    
    level = logging.INFO if success else logging.ERROR
    perf_logger.log(level, f"OCR Performance: {log_data}")


def log_user_activity(user_id: int, activity: str, details: dict = None):
    """记录用户活动日志"""
    logger = setup_logger("user_activity")
    
    log_data = {
        "user_id": user_id,
        "activity": activity,
        "details": details or {},
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info(f"User Activity: {log_data}")


def log_system_event(event_type: str, message: str, level: str = "INFO",
                     details: dict = None):
    """记录系统事件日志"""
    logger = setup_logger("system")
    
    log_data = {
        "event_type": event_type,
        "message": message,
        "details": details or {},
        "timestamp": datetime.now().isoformat()
    }
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, f"System Event: {log_data}")


def log_security_event(event_type: str, user_id: int = None, ip_address: str = None,
                      details: dict = None):
    """记录安全事件日志"""
    security_logger = logging.getLogger("security")
    
    if not security_logger.handlers:
        security_logger.setLevel(logging.WARNING)
        
        # 安全日志格式
        formatter = logging.Formatter(
            fmt='%(asctime)s - SECURITY - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 安全日志文件处理器
        log_dir = Path(settings.log_file).parent
        security_log_path = log_dir / "security.log"
        
        security_handler = RotatingFileHandler(
            filename=security_log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        security_handler.setLevel(logging.WARNING)
        security_handler.setFormatter(formatter)
        security_logger.addHandler(security_handler)
        
        security_logger.propagate = False
    
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "ip_address": ip_address,
        "details": details or {},
        "timestamp": datetime.now().isoformat()
    }
    
    security_logger.warning(f"Security Event: {log_data}")


class LoggerMixin:
    """日志记录混入类"""
    
    @property
    def logger(self):
        if not hasattr(self, '_logger'):
            self._logger = setup_logger(self.__class__.__name__)
        return self._logger


def log_performance(operation: str, duration: float, details: dict = None):
    """记录性能日志的通用函数"""
    perf_logger = setup_performance_logger()
    
    log_data = {
        "operation": operation,
        "duration": f"{duration:.3f}s",
        "details": details or {},
        "timestamp": datetime.now().isoformat()
    }
    
    perf_logger.info(f"Performance: {log_data}")


# 创建默认logger实例
default_logger = setup_logger()