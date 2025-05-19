import redis
import json
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import pickle
import zlib
from functools import wraps
import os
from dotenv import load_dotenv
from .redis_manager import get_redis_client

load_dotenv()

class CacheManager:
    """ตัวจัดการแคชสำหรับ Redis ที่มีประสิทธิภาพ"""
    
    def __init__(self):
        """เริ่มต้นการเชื่อมต่อ Redis พร้อมการตั้งค่าที่เหมาะสม"""
        # ใช้ Redis client จาก connection pool
        self.redis = get_redis_client(decode_responses=False)  # จำเป็นสำหรับการใช้ pickle
        
        # ตั้งค่าเริ่มต้นสำหรับ cache
        self.default_ttl = 300  # 5 นาที
        self.compression_threshold = 1024  # 1KB
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'compression_savings': 0,
            'access_counts': {}  # เก็บสถิติการเข้าถึงแต่ละ key
        }
        
        # ปรับแต่งการใช้หน่วยความจำเมื่อเริ่มต้น
        self._configure_memory_policy()
    
    def _configure_memory_policy(self):
        """ตั้งค่านโยบายการจัดการหน่วยความจำ Redis"""
        try:
            self.redis.config_set('maxmemory-policy', 'volatile-lru')
            self.redis.config_set('maxmemory-samples', 10)
        except Exception as e:
            print(f"⚠️ ไม่สามารถตั้งค่านโยบายหน่วยความจำได้: {e}")

    def _compress_data(self, data: bytes) -> tuple[bytes, bool]:
        """บีบอัดข้อมูลถ้าขนาดเกินกำหนด"""
        if len(data) > self.compression_threshold:
            compressed = zlib.compress(data)
            if len(compressed) < len(data):
                self.cache_stats['compression_savings'] += len(data) - len(compressed)
                return compressed, True
        return data, False

    def _decompress_data(self, data: bytes, is_compressed: bool) -> bytes:
        """คลายการบีบอัดข้อมูล"""
        return zlib.decompress(data) if is_compressed else data

    def set_market_data(self, symbol: str, interval: str, data: Dict[str, Any], ttl: int = None) -> None:
        """บันทึกข้อมูลตลาดพร้อมการบีบอัด"""
        key = f"market:{symbol}:{interval}"
        try:
            pickled_data = pickle.dumps(data)
            compressed_data, is_compressed = self._compress_data(pickled_data)
            
            pipeline = self.redis.pipeline()
            pipeline.set(
                key,
                compressed_data,
                ex=ttl or self.default_ttl
            )
            pipeline.set(
                f"{key}:compressed",
                "1" if is_compressed else "0",
                ex=ttl or self.default_ttl
            )
            pipeline.execute()
        except Exception as e:
            print(f"⚠️ ข้อผิดพลาดในการบันทึกแคช: {e}")

    def get_market_data(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """ดึงข้อมูลตลาดจากแคช"""
        key = f"market:{symbol}:{interval}"
        try:
            pipeline = self.redis.pipeline()
            pipeline.get(key)
            pipeline.get(f"{key}:compressed")
            data, is_compressed = pipeline.execute()
            
            if data is None:
                self.cache_stats['misses'] += 1
                return None
                
            self.cache_stats['hits'] += 1
            
            # เพิ่มการนับจำนวนการเข้าถึงแต่ละ key
            self.cache_stats['access_counts'][key] = self.cache_stats['access_counts'].get(key, 0) + 1
            
            # ปรับ TTL ตามความถี่ในการใช้งาน (adaptive TTL)
            access_count = self.cache_stats['access_counts'][key]
            if access_count > 10:
                # ข้อมูลที่เข้าถึงบ่อย ให้อยู่ในแคชนานขึ้น
                self.redis.expire(key, self.default_ttl * 2)
                self.redis.expire(f"{key}:compressed", self.default_ttl * 2)
            
            is_compressed = bool(int(is_compressed or 0))
            decompressed_data = self._decompress_data(data, is_compressed)
            return pickle.loads(decompressed_data)
            
        except Exception as e:
            print(f"⚠️ ข้อผิดพลาดในการดึงข้อมูลจากแคช: {e}")
            return None

    def cache_technical_indicator(self, func):
        """Decorator สำหรับแคชผลลัพธ์ของตัวบ่งชี้ทางเทคนิค"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            # สร้าง cache key จากพารามิเตอร์
            cache_key = f"indicator:{func.__name__}:{hash(str(args))}"
            
            # พยายามดึงจากแคช
            result = self.get_market_data(cache_key, "")
            if result is not None:
                return result
            
            # คำนวณและบันทึกลงแคช
            result = func(*args, **kwargs)
            self.set_market_data(cache_key, "", result)
            return result
            
        return wrapper

    def batch_cache_update(self, updates: List[Dict[str, Any]]) -> None:
        """
        อัปเดตแคชหลายรายการพร้อมกัน พร้อมกำหนดเวลาหมดอายุตามความสำคัญของข้อมูล
        
        Args:
            updates: รายการอัพเดทข้อมูลแคช มีรูปแบบ {'symbol', 'interval', 'data', 'ttl', 'priority'}
        """
        pipeline = self.redis.pipeline()
        
        for update in updates:
            key = f"market:{update['symbol']}:{update['interval']}"
            pickled_data = pickle.dumps(update['data'])
            compressed_data, is_compressed = self._compress_data(pickled_data)
            
            # กำหนด TTL ให้เหมาะสมตามความสำคัญและความถี่ในการใช้งาน
            priority = update.get('priority', 'normal')
            ttl = update.get('ttl')
            
            if ttl is None:
                # ปรับ TTL ตามประเภทข้อมูล
                if priority == 'high':  # ข้อมูลสำคัญมาก เช่นสัญญาณปัจจุบัน
                    ttl = 900  # 15 นาที
                elif priority == 'normal':  # ข้อมูลปกติ
                    ttl = self.default_ttl  # 5 นาที
                elif priority == 'low':  # ข้อมูลประวัติศาสตร์
                    ttl = 3600  # 1 ชั่วโมง
            
            pipeline.set(
                key,
                compressed_data,
                ex=ttl
            )
            pipeline.set(
                f"{key}:compressed",
                "1" if is_compressed else "0",
                ex=ttl
            )
            
        pipeline.execute()

    def cleanup_old_keys(self, pattern: str = "market:*", batch_size: int = 1000) -> None:
        """ทำความสะอาดคีย์เก่าเพื่อประหยัดหน่วยความจำ"""
        cursor = 0
        while True:
            cursor, keys = self.redis.scan(cursor, pattern, batch_size)
            if keys:
                self.redis.delete(*keys)
            if cursor == 0:
                break

    def get_cache_stats(self) -> Dict[str, int]:
        """ดึงสถิติการใช้งานแคช"""
        return {
            **self.cache_stats,
            'memory_used': self.redis.info()['used_memory'],
            'total_keys': self.redis.dbsize()
        }

    def optimize_memory(self) -> None:
        """ปรับแต่งการใช้หน่วยความจำของ Redis"""
        self.redis.config_set('maxmemory', '1gb')
        self.redis.config_set('maxmemory-policy', 'allkeys-lru')
        self.redis.config_set('maxmemory-samples', 10)

# สร้าง singleton instance
cache_manager = CacheManager()
