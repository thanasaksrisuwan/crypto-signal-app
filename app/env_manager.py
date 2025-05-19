"""
env_manager.py - จัดการการโหลดและการเข้าถึงตัวแปรสภาพแวดล้อม (Environment Variables)

โมดูลนี้รวมศูนย์การจัดการตัวแปรสภาพแวดล้อมสำหรับแอปพลิเคชัน โดยโหลด .env file เพียงครั้งเดียว
และให้ฟังก์ชันสำหรับการเข้าถึงค่าต่างๆ ด้วยการตรวจสอบประเภทและค่าเริ่มต้นที่เหมาะสม
"""
import os
import logging
from typing import Any, Dict, Union, Optional, TypeVar, cast, List
from dotenv import load_dotenv, set_key, find_dotenv
import json

# กำหนดตัวแปร Type สำหรับช่วยในการ type hinting
T = TypeVar('T')

# สร้าง logger สำหรับโมดูลนี้
logger = logging.getLogger(__name__)

# โหลด .env file ทันทีเมื่อนำเข้าโมดูล
load_dotenv()

# แคชค่าสำหรับตัวแปรที่ใช้บ่อย
_env_cache: Dict[str, Any] = {}

def getenv(key: str, default: Optional[T] = None, as_type: type = str) -> Union[str, int, float, bool, dict, list, T, None]:
    """
    ดึงค่าตัวแปรสภาพแวดล้อมพร้อมกับแปลงประเภทข้อมูล
    
    Args:
        key: ชื่อของตัวแปรสภาพแวดล้อม
        default: ค่าเริ่มต้นถ้าไม่พบตัวแปร (None ถ้าไม่ได้กำหนด)
        as_type: ประเภทข้อมูลที่ต้องการแปลงเป็น (str, int, float, bool, dict, list)
    
    Returns:
        ค่าตัวแปรสภาพแวดล้อมที่แปลงเป็นประเภทข้อมูลที่กำหนด
    
    Raises:
        ValueError: ถ้าไม่สามารถแปลงค่าเป็นประเภทข้อมูลที่ระบุได้
    """
    # ตรวจสอบแคชก่อนเพื่อหลีกเลี่ยงการเรียกซ้ำ
    cache_key = f"{key}_{as_type.__name__}"
    if cache_key in _env_cache:
        return _env_cache[cache_key]
    
    value = os.getenv(key)
    
    # ถ้าไม่พบค่า ให้คืนค่าเริ่มต้น
    if value is None:
        return default
    
    try:
        # แปลงค่าตามประเภทที่ต้องการ
        if as_type == bool:
            # แปลงสตริงเป็นค่าตรรกะ
            parsed_value = value.lower() in ('true', '1', 'yes', 'y', 't')
        elif as_type == int:
            parsed_value = int(value)
        elif as_type == float:
            parsed_value = float(value)
        elif as_type == dict:
            parsed_value = json.loads(value)
        elif as_type == list:
            parsed_value = json.loads(value)
        else:
            # สำหรับ string หรือประเภทอื่น ๆ
            parsed_value = as_type(value)
        
        # เก็บค่าที่แปลงแล้วในแคช
        _env_cache[cache_key] = parsed_value
        return parsed_value
        
    except (ValueError, json.JSONDecodeError) as e:
        logger.error(f"ไม่สามารถแปลงค่า '{key}={value}' เป็น {as_type.__name__}: {e}")
        return default

# ฟังก์ชันสำหรับตัวแปรสภาพแวดล้อมทั่วไป
def get_debug_mode() -> bool:
    """ดึงค่า DEBUG_MODE จากตัวแปรสภาพแวดล้อม"""
    return getenv("DEBUG_MODE", False, bool)

# ฟังก์ชันสำหรับดึงสัญลักษณ์คริปโตที่รองรับ
def get_available_symbols() -> List[str]:
    """
    ดึงรายการสัญลักษณ์คริปโตที่รองรับจากตัวแปรสภาพแวดล้อม
    
    Returns:
        รายการสัญลักษณ์คริปโตที่รองรับ (เช่น ["BTCUSDT", "ETHUSDT"])
    """
    default_symbols = ["BTCUSDT", "ETHUSDT"]
    env_symbols = getenv("AVAILABLE_SYMBOLS", None, str)
    
    # ถ้าไม่มีการกำหนดในไฟล์ .env ให้ใช้ค่าเริ่มต้น
    if env_symbols is None:
        return default_symbols
    
    # แยกสัญลักษณ์ด้วยเครื่องหมายคอมม่า
    symbols = [symbol.strip().upper() for symbol in env_symbols.split(",")]
    
    # ถ้าหลังจากแยกแล้วไม่มีสัญลักษณ์ใด ให้ใช้ค่าเริ่มต้น
    if not symbols or all(not symbol for symbol in symbols):
        return default_symbols
    
    return symbols

def add_symbol(symbol: str) -> bool:
    """
    เพิ่มสัญลักษณ์คริปโตใหม่ไปยังรายการที่รองรับ
    
    Args:
        symbol: สัญลักษณ์คริปโตที่ต้องการเพิ่ม (เช่น "BTCUSDT")
    
    Returns:
        bool: True ถ้าเพิ่มสำเร็จ, False ถ้าสัญลักษณ์มีอยู่แล้วหรือเกิดข้อผิดพลาด
    """
    try:
        # รูปแบบสัญลักษณ์ให้เป็นตัวพิมพ์ใหญ่
        symbol = symbol.strip().upper()
        
        # ดึงรายการสัญลักษณ์ปัจจุบัน
        current_symbols = get_available_symbols()
        
        # ตรวจสอบว่ามีอยู่แล้วหรือไม่
        if symbol in current_symbols:
            logger.info(f"สัญลักษณ์ {symbol} มีอยู่ในรายการแล้ว")
            return False
        
        # เพิ่มสัญลักษณ์ใหม่และบันทึกกลับไปยัง .env
        new_symbols = current_symbols + [symbol]
        symbols_str = ",".join(new_symbols)
        
        # หาที่อยู่ไฟล์ .env
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("ไม่พบไฟล์ .env")
            return False
        
        # บันทึกการเปลี่ยนแปลง
        set_key(dotenv_path, "AVAILABLE_SYMBOLS", symbols_str)
        
        # ล้างแคช
        _env_cache.pop(f"AVAILABLE_SYMBOLS_str", None)
        
        logger.info(f"เพิ่มสัญลักษณ์ {symbol} สำเร็จ")
        return True
    
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการเพิ่มสัญลักษณ์: {e}")
        return False

def remove_symbol(symbol: str) -> bool:
    """
    ลบสัญลักษณ์คริปโตออกจากรายการที่รองรับ
    
    Args:
        symbol: สัญลักษณ์คริปโตที่ต้องการลบ (เช่น "BTCUSDT")
    
    Returns:
        bool: True ถ้าลบสำเร็จ, False ถ้าไม่พบสัญลักษณ์หรือเกิดข้อผิดพลาด
    """
    try:
        # รูปแบบสัญลักษณ์ให้เป็นตัวพิมพ์ใหญ่
        symbol = symbol.strip().upper()
        
        # ดึงรายการสัญลักษณ์ปัจจุบัน
        current_symbols = get_available_symbols()
        
        # ตรวจสอบว่ามีสัญลักษณ์ในรายการหรือไม่
        if symbol not in current_symbols:
            logger.info(f"ไม่พบสัญลักษณ์ {symbol} ในรายการ")
            return False
        
        # ต้องเหลืออย่างน้อย 1 สัญลักษณ์
        if len(current_symbols) <= 1:
            logger.warning("ไม่สามารถลบสัญลักษณ์สุดท้ายได้")
            return False
        
        # ลบสัญลักษณ์และบันทึกกลับไปยัง .env
        new_symbols = [s for s in current_symbols if s != symbol]
        symbols_str = ",".join(new_symbols)
        
        # หาที่อยู่ไฟล์ .env
        dotenv_path = find_dotenv()
        if not dotenv_path:
            logger.error("ไม่พบไฟล์ .env")
            return False
        
        # บันทึกการเปลี่ยนแปลง
        set_key(dotenv_path, "AVAILABLE_SYMBOLS", symbols_str)
        
        # ล้างแคช
        _env_cache.pop(f"AVAILABLE_SYMBOLS_str", None)
        
        logger.info(f"ลบสัญลักษณ์ {symbol} สำเร็จ")
        return True
    
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในการลบสัญลักษณ์: {e}")
        return False

# ฟังก์ชันสำหรับการตั้งค่า Redis
def get_redis_config() -> Dict[str, Any]:
    """ดึงการตั้งค่า Redis ทั้งหมด"""
    return {
        "host": getenv("REDIS_HOST", "localhost"),
        "port": getenv("REDIS_PORT", 6379, int),
        "password": getenv("REDIS_PASSWORD", None),
    }

# ฟังก์ชันสำหรับการตั้งค่า InfluxDB
def get_influxdb_config() -> Dict[str, Any]:
    """ดึงการตั้งค่า InfluxDB ทั้งหมด"""
    return {
        "url": getenv("INFLUXDB_URL", "http://localhost:8086"),
        "token": getenv("INFLUXDB_TOKEN", ""),
        "org": getenv("INFLUXDB_ORG", ""),
        "bucket": getenv("INFLUXDB_BUCKET", "crypto_signals"),
    }

# ฟังก์ชันสำหรับการตั้งค่า Binance API
def get_binance_config() -> Dict[str, str]:
    """ดึงการตั้งค่า Binance API ทั้งหมด"""
    return {
        "api_key": getenv("BINANCE_API_KEY", ""),
        "api_secret": getenv("BINANCE_API_SECRET", ""),
    }

# ฟังก์ชันสำหรับการตั้งค่า Backend
def get_backend_config() -> Dict[str, Any]:
    """ดึงการตั้งค่า Backend ทั้งหมด"""
    return {
        "host": getenv("BACKEND_HOST", "0.0.0.0"),
        "port": getenv("BACKEND_PORT", 8000, int),
    }

# ฟังก์ชันสำหรับการตั้งค่าการแจ้งเตือน
def get_notification_config() -> Dict[str, str]:
    """ดึงการตั้งค่าการแจ้งเตือนทั้งหมด"""
    return {
        "line_notify_token": getenv("LINE_NOTIFY_TOKEN", ""),
        "telegram_bot_token": getenv("TELEGRAM_BOT_TOKEN", ""),
        "discord_webhook_url": getenv("DISCORD_WEBHOOK_URL", ""),
    }

# ฟังก์ชันสำหรับการตั้งค่าการเทรด
def get_trade_config() -> Dict[str, Any]:
    """ดึงการตั้งค่าการเทรดทั้งหมด"""
    return {
        "mode": getenv("TRADE_MODE", "test"),
        "max_positions": getenv("MAX_POSITIONS", 5, int),
        "risk_percentage": getenv("RISK_PERCENTAGE", 1.0, float),
    }
