"""
env_example.py - ตัวอย่างการใช้งาน env_manager สำหรับจัดการตัวแปรสภาพแวดล้อม

ไฟล์นี้แสดงตัวอย่างการใช้งาน env_manager ที่เราสร้างขึ้น เพื่อเข้าถึงตัวแปรสภาพแวดล้อมต่าง ๆ
และแสดงวิธีการเพิ่มตัวแปรใหม่ที่อาจจำเป็นสำหรับโปรเจค
"""
import logging
import logging
import os
import sys

# นำเข้าโมดูลจัดการตัวแปรสภาพแวดล้อมที่เราสร้างไว้ (แก้ไขเส้นทางให้ถูกต้อง)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
import env_manager as env

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def showEnvironmentUsage():
    """
    แสดงตัวอย่างการใช้งาน env_manager เพื่อเข้าถึงตัวแปรสภาพแวดล้อม
    """
    # ตัวอย่างการใช้ฟังก์ชัน getenv โดยตรง
    debug_mode = env.getenv("DEBUG_MODE", False, bool)
    logger.info(f"Debug Mode: {debug_mode} (type: {type(debug_mode)})")

    # ตัวอย่างการใช้ฟังก์ชันเฉพาะทางที่เราสร้างไว้
    redis_config = env.get_redis_config()
    logger.info(f"Redis Host: {redis_config['host']}")
    logger.info(f"Redis Port: {redis_config['port']} (type: {type(redis_config['port'])})")

    # ตัวอย่างการใช้งาน influxdb config
    influxdb_config = env.get_influxdb_config()
    logger.info(f"InfluxDB URL: {influxdb_config['url']}")
    logger.info(f"InfluxDB Bucket: {influxdb_config['bucket']}")

    # ตัวอย่างการใช้งาน notification config
    notification_config = env.get_notification_config()
    # แสดงเฉพาะว่ามีหรือไม่มีค่า เพื่อความปลอดภัย
    has_line_token = bool(notification_config['line_notify_token'])
    has_discord_webhook = bool(notification_config['discord_webhook_url'])
    logger.info(f"Has Line Notify Token: {has_line_token}")
    logger.info(f"Has Discord Webhook URL: {has_discord_webhook}")

    # ตัวอย่างการใช้งาน trade config
    trade_config = env.get_trade_config()
    logger.info(f"Trade Mode: {trade_config['mode']}")
    logger.info(f"Max Positions: {trade_config['max_positions']} (type: {type(trade_config['max_positions'])})")
    logger.info(f"Risk Percentage: {trade_config['risk_percentage']} (type: {type(trade_config['risk_percentage'])})")

def addCustomEnvironmentVariable():
    """
    ตัวอย่างการเพิ่มตัวแปรสภาพแวดล้อมใหม่ในโค้ด
    
    ขั้นตอน:
    1. เพิ่มตัวแปรใน .env หรือ .env.example
    2. เพิ่มฟังก์ชันเข้าถึงตัวแปรใน env_manager.py (ทำเอง)
    3. ใช้งานเหมือนตัวอย่างด้านล่าง
    """
    # สมมติว่าได้เพิ่ม CUSTOM_API_KEY ใน .env แล้ว
    custom_api_key = env.getenv("CUSTOM_API_KEY", "")
    if custom_api_key:
        logger.info("Custom API Key is configured")
    else:
        logger.info("Custom API Key is not configured")

    # สมมติว่าได้เพิ่ม MAX_CONNECTIONS ใน .env แล้ว
    max_connections = env.getenv("MAX_CONNECTIONS", 10, int)
    logger.info(f"Max Connections: {max_connections} (type: {type(max_connections)})")

if __name__ == "__main__":
    logger.info("===== ตัวอย่างการใช้งาน env_manager =====")
    showEnvironmentUsage()
    
    logger.info("\n===== ตัวอย่างการเพิ่มตัวแปรใหม่ =====")
    addCustomEnvironmentVariable()
