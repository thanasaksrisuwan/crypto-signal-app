"""
Redis Connection Manager - สร้าง Redis connection pool เพื่อใช้ร่วมกันในแอพพลิเคชัน
"""
import redis
import os
from dotenv import load_dotenv
from typing import Optional

# โหลด environment variables
load_dotenv()

# ตั้งค่าการเชื่อมต่อกับ Redis
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

class RedisManager:
    """
    จัดการการเชื่อมต่อกับ Redis ด้วย Connection Pool สำหรับใช้ร่วมกันทั้งแอปพลิเคชัน
    ช่วยลดการสร้างและปิดการเชื่อมต่อซ้ำซ้อน
    """
    
    _instance = None
    _pool = None
    _text_pool = None  # สำหรับ decode_responses=True
    
    @staticmethod
    def get_instance():
        """
        รับ singleton instance ของ RedisManager
        
        Returns:
            RedisManager: instance ที่ใช้ร่วมกัน
        """
        if RedisManager._instance is None:
            RedisManager._instance = RedisManager()
        return RedisManager._instance
    
    def __init__(self):
        """เริ่มต้น connection pool สำหรับ Redis"""
        if RedisManager._pool is not None:
            return
            
        # สร้าง pool สำหรับข้อมูลไบนารี (สำหรับใช้กับ pickle และการบีบอัด)
        self._pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=False,
            max_connections=20,
            socket_timeout=5,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        
        # สร้าง pool สำหรับข้อความ (สำหรับใช้กับ JSON)
        self._text_pool = redis.ConnectionPool(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
            max_connections=20,
            socket_timeout=5,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
    
    def get_redis_client(self, decode_responses: bool = False) -> redis.Redis:
        """
        รับ Redis client ที่ใช้ connection pool
        
        Args:
            decode_responses: True เพื่อแปลงข้อมูลเป็น string โดยอัตโนมัติ (เหมาะสำหรับ JSON)
            
        Returns:
            redis.Redis: client ที่ใช้ connection pool
        """
        if decode_responses:
            return redis.Redis(connection_pool=self._text_pool)
        else:
            return redis.Redis(connection_pool=self._pool)
    
    def ping(self) -> bool:
        """
        ทดสอบการเชื่อมต่อกับ Redis
        
        Returns:
            bool: True ถ้าเชื่อมต่อได้สำเร็จ
        """
        try:
            client = self.get_redis_client()
            return client.ping()
        except redis.RedisError:
            return False

    def close(self):
        """ปิดการเชื่อมต่อ Redis pools"""
        if self._pool:
            self._pool.disconnect()
        if self._text_pool:
            self._text_pool.disconnect()

# สร้าง singleton instance ที่พร้อมใช้งาน
redis_manager = RedisManager.get_instance()

# ฟังก์ชันสำหรับใช้งานจากภายนอก
def get_redis_client(decode_responses: bool = False) -> redis.Redis:
    """
    รับ Redis client ที่ใช้ connection pool จาก singleton instance
    
    Args:
        decode_responses: True เพื่อแปลงข้อมูลเป็น string โดยอัตโนมัติ (เหมาะสำหรับ JSON)
        
    Returns:
        redis.Redis: client ที่ใช้ connection pool
    """
    return redis_manager.get_redis_client(decode_responses)

def check_redis_connection() -> bool:
    """
    ตรวจสอบการเชื่อมต่อกับ Redis
    
    Returns:
        bool: True ถ้าเชื่อมต่อได้สำเร็จ
    """
    return redis_manager.ping()
