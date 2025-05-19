import os
import psutil
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import json
from dataclasses import dataclass
import gc
import weakref

from .redis_manager import get_redis_client
from .logger import LoggerFactory, MetricsLogger

@dataclass
class MemoryThresholds:
    """ค่าขีดจำกัดการใช้หน่วยความจำสำหรับการแจ้งเตือน"""
    warning_percent: float = 75.0
    critical_percent: float = 90.0
    warning_rss_mb: float = 1024.0  # 1GB
    critical_rss_mb: float = 2048.0  # 2GB

class EnhancedMemoryMonitor:
    """บริการตรวจสอบและปรับแต่งการใช้หน่วยความจำที่มีประสิทธิภาพ"""
    
    def __init__(self, check_interval: int = 60):
        """
        เริ่มต้นตัวตรวจสอบหน่วยความจำ
        
        Args:
            check_interval: ช่วงเวลาระหว่างการตรวจสอบในวินาที
        """
        self.logger = LoggerFactory.get_logger('memory_monitor')
        self.metrics = MetricsLogger('memory_monitor')
        self.check_interval = check_interval
        self.thresholds = MemoryThresholds()
        self.monitoring = False
        self.monitor_thread = None
        
        # ใช้ Redis client จาก connection pool
        try:
            self.redis = get_redis_client(decode_responses=True)
        except Exception as e:
            self.logger.error(f"ไม่สามารถเชื่อมต่อกับ Redis ได้: {e}")
            self.redis = None
            
        # ติดตามรายการอ้างอิงวัตถุขนาดใหญ่
        self.large_objects: List[weakref.ref] = []
        
        # กำหนดเกณฑ์สำหรับ memory leak detection
        self.last_memory_readings = []
        self.leak_detection_threshold = 0.05  # 5% เพิ่มขึ้นอย่างต่อเนื่อง
    
    def start(self):
        """เริ่มการตรวจสอบหน่วยความจำ"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info("เริ่มการตรวจสอบหน่วยความจำ")
    
    def stop(self):
        """หยุดการตรวจสอบหน่วยความจำ"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join()
        self.logger.info("หยุดการตรวจสอบหน่วยความจำ")
    
    def _monitor_loop(self):
        """วงรอบการตรวจสอบหลัก"""
        while self.monitoring:
            try:
                self._check_memory()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบหน่วยความจำ: {e}")
    
    def _check_memory(self):
        """ตรวจสอบการใช้หน่วยความจำปัจจุบันและดำเนินการหากจำเป็น"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            
            # คำนวณการใช้หน่วยความจำ
            rss_mb = memory_info.rss / (1024 * 1024)
            vms_mb = memory_info.vms / (1024 * 1024)
            percent_used = process.memory_percent()
            
            # บันทึกเพื่อตรวจสอบ memory leak
            self.last_memory_readings.append(rss_mb)
            if len(self.last_memory_readings) > 10:
                self.last_memory_readings.pop(0)
                self._detect_memory_leak()
            
            # บันทึกเมตริก
            memory_data = {
                'rss_mb': rss_mb,
                'vms_mb': vms_mb,
                'percent_used': percent_used,
                'system_total_mb': system_memory.total / (1024 * 1024),
                'system_available_mb': system_memory.available / (1024 * 1024),
                'system_percent': system_memory.percent,
                'timestamp': datetime.now().isoformat()
            }
            
            self.metrics.record_metric('memory_usage', memory_data)
            
            # บันทึกใน Redis
            if self.redis:
                self.redis.setex(
                    'memory_monitor:latest',
                    3600,  # หมดอายุใน 1 ชั่วโมง
                    json.dumps(memory_data)
                )
                
                # บันทึกข้อมูลประวัติ
                self.redis.lpush(
                    'memory_monitor:history',
                    json.dumps(memory_data)
                )
                self.redis.ltrim('memory_monitor:history', 0, 1000)  # เก็บบันทึกล่าสุด 1000 รายการ
            
            # ตรวจสอบเกณฑ์การใช้หน่วยความจำ
            self._check_thresholds(rss_mb, percent_used)
            
            # ตรวจสอบวัตถุขนาดใหญ่
            if rss_mb > self.thresholds.warning_rss_mb:
                self._track_large_objects()
            
        except Exception as e:
            self.logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบหน่วยความจำ: {e}")
            
    def _detect_memory_leak(self):
        """
        ตรวจหา memory leak โดยวิเคราะห์แนวโน้มการใช้หน่วยความจำ
        """
        if len(self.last_memory_readings) < 5:
            return
            
        # ตรวจสอบการเพิ่มขึ้นอย่างต่อเนื่อง
        is_increasing = all(
            self.last_memory_readings[i] < self.last_memory_readings[i+1]
            for i in range(len(self.last_memory_readings)-1)
        )
        
        if is_increasing:
            # คำนวณอัตราการเพิ่มขึ้น
            first = self.last_memory_readings[0]
            last = self.last_memory_readings[-1]
            growth_rate = (last - first) / first
            
            if growth_rate > self.leak_detection_threshold:
                self.logger.warning(
                    f"ตรวจพบ memory leak ที่อาจเกิดขึ้น: อัตราการเติบโต {growth_rate:.2%} จาก {len(self.last_memory_readings)} ครั้งที่ตรวจสอบล่าสุด"
                )
                self._analyze_object_growth()
                
                # บันทึกเหตุการณ์
                self.metrics.record_metric('memory_alert', {
                    'type': 'potential_leak',
                    'growth_rate': growth_rate,
                    'readings': self.last_memory_readings,
                    'timestamp': datetime.now().isoformat()
                })
                
    def _track_large_objects(self):
        """
        ติดตามวัตถุขนาดใหญ่ในหน่วยความจำโดยใช้ weakref เพื่อไม่ให้กระทบกับ garbage collection
        """
        # ล้างการอ้างอิงที่ไม่มีชีวิตแล้ว
        self.large_objects = [ref for ref in self.large_objects if ref() is not None]
        
        # ติดตามวัตถุขนาดใหญ่ที่เพิ่งสร้าง
        threshold_bytes = 10 * 1024 * 1024  # 10MB
        new_large_objects = 0
        
        for obj in gc.get_objects():
            try:
                if not isinstance(obj, (str, bytes, bytearray)):
                    continue
                    
                size = obj.__sizeof__()
                if size > threshold_bytes:
                    # ตรวจสอบว่าเราไม่ได้ติดตามวัตถุนี้อยู่แล้ว
                    if not any(ref() is obj for ref in self.large_objects if ref() is not None):
                        self.large_objects.append(weakref.ref(obj))
                        new_large_objects += 1
                        
                        # บันทึกข้อมูลเพิ่มเติมเกี่ยวกับวัตถุขนาดใหญ่
                        self.metrics.record_metric('large_object', {
                            'type': type(obj).__name__,
                            'size_mb': size / (1024 * 1024),
                            'timestamp': datetime.now().isoformat()
                        })
            except Exception:
                # ข้ามวัตถุที่ไม่สามารถตรวจสอบขนาดได้
                pass
                
        if new_large_objects > 0:
            self.logger.info(f"ติดตามวัตถุขนาดใหญ่ใหม่ {new_large_objects} รายการ, รวมทั้งหมด: {len(self.large_objects)}")
            
    def _analyze_object_growth(self):
        """
        วิเคราะห์การเติบโตของวัตถุโดยใช้ garbage collector
        """
        gc.collect()
        
        type_counts = {}
        total_by_type = {}
        
        # นับจำนวนวัตถุแยกตามประเภท
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
            
            try:
                size = obj.__sizeof__()
                total_by_type[obj_type] = total_by_type.get(obj_type, 0) + size
            except Exception:
                pass
                
        # หา 10 ประเภทวัตถุที่มีจำนวนมากที่สุด
        top_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # บันทึกข้อมูลการวิเคราะห์
        analysis = {
            'top_types_by_count': [{'type': t, 'count': c} for t, c in top_types],
            'top_types_by_size': [
                {'type': t, 'size_mb': s / (1024 * 1024)} 
                for t, s in sorted(total_by_type.items(), key=lambda x: x[1], reverse=True)[:10]
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info(f"การวิเคราะห์หน่วยความจำ: ประเภทหลักตามจำนวน: {top_types}")
        self.metrics.record_metric('memory_analysis', analysis)
        
        if self.redis:
            self.redis.setex(
                'memory_monitor:analysis',
                3600 * 24,  # หมดอายุใน 24 ชั่วโมง
                json.dumps(analysis)
            )
    
    def _check_thresholds(self, rss_mb: float, percent_used: float):
        """ตรวจสอบว่าการใช้หน่วยความจำเกินค่าขีดจำกัดหรือไม่"""
        if (percent_used > self.thresholds.critical_percent or 
            rss_mb > self.thresholds.critical_rss_mb):
            self.logger.critical(
                f"การใช้หน่วยความจำวิกฤต: {percent_used:.1f}% ({rss_mb:.0f}MB)"
            )
            self._handle_critical_memory()
        elif (percent_used > self.thresholds.warning_percent or 
              rss_mb > self.thresholds.warning_rss_mb):
            self.logger.warning(
                f"การใช้หน่วยความจำสูง: {percent_used:.1f}% ({rss_mb:.0f}MB)"
            )
            self._handle_warning_memory()
    
    def _handle_warning_memory(self):
        """จัดการเมื่อการใช้หน่วยความจำถึงระดับเตือน"""
        # เรียกใช้ garbage collection
        gc.collect()
        
        # บันทึกการดำเนินการ
        self.metrics.record_metric('memory_action', {
            'level': 'warning',
            'action': 'gc_collect',
            'timestamp': datetime.now().isoformat()
        })
    
    def _handle_critical_memory(self):
        """จัดการเมื่อการใช้หน่วยความจำถึงระดับวิกฤต"""
        # ทำความสะอาดหน่วยความจำอย่างเข้มงวด
        gc.collect()
        gc.collect()  # รอบที่สอง
        
        # ล้างแคชต่าง ๆ
        if self.redis:
            try:
                # ล้างแคชที่ไม่สำคัญ
                self.redis.delete('market_data:cache:*')
                self.redis.delete('technical_indicators:cache:*')
            except Exception as e:
                self.logger.error(f"ไม่สามารถล้างแคช Redis ได้: {e}")
        
        # บันทึกการดำเนินการ
        self.metrics.record_metric('memory_action', {
            'level': 'critical',
            'action': 'aggressive_cleanup',
            'timestamp': datetime.now().isoformat()
        })
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """ดึงสถิติหน่วยความจำปัจจุบัน"""
        process = psutil.Process()
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()
        
        return {
            'process': {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent(),
                'num_threads': process.num_threads(),
                'num_fds': process.num_fds() if hasattr(process, 'num_fds') else None
            },
            'system': {
                'total_mb': system_memory.total / (1024 * 1024),
                'available_mb': system_memory.available / (1024 * 1024),
                'percent': system_memory.percent,
                'swap_mb': psutil.swap_memory().total / (1024 * 1024)
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def get_historical_stats(self, limit: int = 100) -> list:
        """ดึงสถิติหน่วยความจำย้อนหลัง"""
        if not self.redis:
            return []
            
        try:
            history = self.redis.lrange('memory_monitor:history', 0, limit - 1)
            return [json.loads(item) for item in history]
        except Exception as e:
            self.logger.error(f"ไม่สามารถดึงสถิติย้อนหลังได้: {e}")
            return []
    
    def cleanup(self):
        """ทำความสะอาดทรัพยากร"""
        self.stop()
        if self.redis:
            try:
                self.redis.close()
            except Exception as e:
                self.logger.error(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อ Redis: {e}")

# สร้างอินสแตนซ์ singleton
enhanced_memory_monitor = EnhancedMemoryMonitor()
