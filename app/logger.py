import logging
import logging.handlers
import os
import json
import traceback
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, Union

class LoggerFactory:
    """Factory class สำหรับสร้างและจัดการ loggers"""
    
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def get_logger(cls, name: str, log_file: str = None) -> logging.Logger:
        """
        สร้างหรือดึง logger ที่มีอยู่
        
        Args:
            name: ชื่อของ logger
            log_file: ที่อยู่ไฟล์ log (ถ้าไม่ระบุจะใช้ logs/{name}.log)
        """
        if name in cls._loggers:
            return cls._loggers[name]
            
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        # สร้างโฟลเดอร์ logs ถ้ายังไม่มี
        os.makedirs('logs', exist_ok=True)
        
        # ตั้งค่า file handler
        log_file = log_file or f'logs/{name}.log'
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # ตั้งค่า console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # กำหนดรูปแบบ log
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # เพิ่ม handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        cls._loggers[name] = logger
        return logger

class ErrorLogger:
    """คลาสสำหรับจัดการการบันทึก error logs"""
    
    def __init__(self, name: str):
        self.logger = LoggerFactory.get_logger(name)
        
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """
        บันทึกข้อผิดพลาดพร้อมข้อมูลเพิ่มเติม
        
        Args:
            error: Exception ที่เกิดขึ้น
            context: ข้อมูลเพิ่มเติมที่เกี่ยวข้องกับข้อผิดพลาด
        """
        error_info = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        
        self.logger.error(
            f"Error occurred: {error_info['error_type']}\n"
            f"Message: {error_info['error_message']}\n"
            f"Context: {json.dumps(error_info['context'], indent=2)}\n"
            f"Traceback:\n{error_info['traceback']}"
        )

def log_execution_time(logger: Optional[logging.Logger] = None):
    """
    Decorator สำหรับบันทึกเวลาที่ใช้ในการทำงานของฟังก์ชัน
    
    Args:
        logger: Logger ที่จะใช้บันทึก (ถ้าไม่ระบุจะสร้างใหม่)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            
            nonlocal logger
            if logger is None:
                logger = LoggerFactory.get_logger(func.__module__)
                
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.debug(
                    f"Function '{func.__name__}' executed in {execution_time:.3f} seconds"
                )
                return result
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Function '{func.__name__}' failed after {execution_time:.3f} seconds\n"
                    f"Error: {str(e)}\n"
                    f"Traceback:\n{traceback.format_exc()}"
                )
                raise
                
        return wrapper
    return decorator

class MetricsLogger:
    """คลาสสำหรับบันทึกและติดตามเมตริกต่างๆ"""
    
    def __init__(self, name: str):
        self.logger = LoggerFactory.get_logger(f"{name}_metrics")
        self.metrics: Dict[str, Any] = {}
        
    def record_metric(self, name: str, value: Union[int, float, str, dict]) -> None:
        """
        บันทึกค่าเมตริก
        
        Args:
            name: ชื่อเมตริก
            value: ค่าที่จะบันทึก
        """
        self.metrics[name] = value
        self.logger.info(f"Metric {name}: {json.dumps(value)}")
        
    def get_metrics(self) -> Dict[str, Any]:
        """ดึงค่าเมตริกทั้งหมด"""
        return self.metrics.copy()
        
    def reset_metrics(self) -> None:
        """รีเซ็ตค่าเมตริกทั้งหมด"""
        self.metrics.clear()

# สร้าง global error logger
error_logger = ErrorLogger('system')

# ตัวอย่างการใช้งาน
if __name__ == "__main__":
    # ทดสอบ basic logging
    logger = LoggerFactory.get_logger('test')
    logger.info("Test log message")
    
    # ทดสอบ error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_logger.log_error(e, {'test_context': 'example'})
        
    # ทดสอบ execution time logging
    @log_execution_time()
    def test_function():
        return "Test successful"
        
    test_function()
    
    # ทดสอบ metrics logging
    metrics_logger = MetricsLogger('test')
    metrics_logger.record_metric('test_metric', {'value': 100, 'unit': 'ms'})
