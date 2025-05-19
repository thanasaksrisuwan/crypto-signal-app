import json
import redis
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from typing import Dict, Any, List, Optional

import os
import sys

# นำเข้าโมดูลจัดการตัวแปรสภาพแวดล้อม
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
import env_manager as env

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("notification_service")

# ตั้งค่าการเชื่อมต่อ Redis
redis_config = env.get_redis_config()
REDIS_SIGNAL_CHANNEL = "crypto_signals:signals"

# ตั้งค่าการส่งอีเมล
SMTP_SERVER = env.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = env.getenv("SMTP_PORT", 587, int)
SMTP_USERNAME = env.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = env.getenv("SMTP_PASSWORD", "")
EMAIL_RECIPIENTS = env.getenv("EMAIL_RECIPIENTS", "").split(",") if env.getenv("EMAIL_RECIPIENTS") else []

# ตั้งค่า Webhook
notification_config = env.get_notification_config()
WEBHOOK_URL = env.getenv("WEBHOOK_URL", "")

class NotificationService:
    """บริการแจ้งเตือนที่ส่งการแจ้งเตือนเมื่อได้รับสัญญาณการซื้อขายใหม่"""
    
    def __init__(self):
        """เริ่มต้นบริการแจ้งเตือนด้วยการเชื่อมต่อกับ Redis"""
        self.redis_client = redis.Redis(
            host=redis_config["host"],
            port=redis_config["port"],
            password=redis_config["password"],
            decode_responses=True
        )
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(REDIS_SIGNAL_CHANNEL)
        logger.info("บริการแจ้งเตือนเริ่มต้นแล้ว และกำลังฟังช่อง %s", REDIS_SIGNAL_CHANNEL)
    
    def send_email_notification(self, signal: Dict[str, Any]) -> bool:
        """
        ส่งการแจ้งเตือนทางอีเมล
        
        Args:
            signal: ข้อมูลสัญญาณที่จะส่ง
            
        Returns:
            สถานะความสำเร็จของการส่ง
        """
        if not SMTP_USERNAME or not SMTP_PASSWORD or not EMAIL_RECIPIENTS:
            logger.warning("ไม่ได้กำหนดค่า SMTP หรือผู้รับอีเมล")
            return False
        
        try:
            # สร้างข้อความ
            subject = f"🚨 สัญญาณการซื้อขาย: {signal['category'].upper()} สำหรับ {signal['symbol']}"
            
            # สร้างเนื้อหาอีเมลแบบ HTML
            emoji = self._get_category_emoji(signal['category'])
            color = self._get_category_color(signal['category'])
            
            html_content = f"""
            <html>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #333;">{emoji} สัญญาณการซื้อขายคริปโต</h2>
                    <div style="border-left: 4px solid {color}; padding: 10px; background-color: #f9f9f9; margin: 20px 0;">
                        <h3 style="color: {color}; margin: 0;">{signal['category'].upper()}</h3>
                        <p style="font-size: 18px; margin: 10px 0;">สัญลักษณ์: <strong>{signal['symbol']}</strong></p>
                        <p>ราคาปัจจุบัน: ${signal['price']:.2f}</p>
                        <p>การคาดการณ์: {signal['forecast_pct']:.2f}%</p>
                        <p>ความมั่นใจ: {signal['confidence'] * 100:.1f}%</p>
                    </div>
                    <div style="font-size: 12px; color: #999; margin-top: 30px;">
                        <p>ข้อมูลนี้เป็นเพียงการวิเคราะห์เชิงเทคนิค ไม่ใช่คำแนะนำในการลงทุน</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # สร้างข้อความอีเมล
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = SMTP_USERNAME
            msg['To'] = ", ".join(EMAIL_RECIPIENTS)
            
            msg.attach(MIMEText(html_content, 'html'))
            
            # ส่งอีเมล
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info("ส่งการแจ้งเตือนทางอีเมลสำเร็จ: %s", subject)
            return True
            
        except Exception as e:
            logger.error("เกิดข้อผิดพลาดในการส่งอีเมล: %s", str(e))
            return False
    
    def send_webhook_notification(self, signal: Dict[str, Any]) -> bool:
        """
        ส่งการแจ้งเตือนผ่าน webhook
        
        Args:
            signal: ข้อมูลสัญญาณที่จะส่ง
            
        Returns:
            สถานะความสำเร็จของการส่ง
        """
        if not WEBHOOK_URL:
            logger.warning("ไม่ได้กำหนดค่า WEBHOOK_URL")
            return False
        
        try:
            # สร้างข้อมูลที่จะส่ง
            payload = {
                "signal_type": signal['category'],
                "symbol": signal['symbol'],
                "price": signal['price'],
                "forecast_pct": signal['forecast_pct'],
                "confidence": signal['confidence'],
                "timestamp": signal['timestamp'],
                "indicators": signal.get('indicators', {})
            }
            
            # ส่งข้อมูลไปยัง webhook
            response = requests.post(
                WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code < 400:
                logger.info("ส่งการแจ้งเตือน webhook สำเร็จ: %s", response.status_code)
                return True
            else:
                logger.error("การส่ง webhook ล้มเหลว: %s - %s", response.status_code, response.text)
                return False
                
        except Exception as e:
            logger.error("เกิดข้อผิดพลาดในการส่ง webhook: %s", str(e))
            return False
    
    def send_discord_notification(self, signal: Dict[str, Any]) -> bool:
        """
        ส่งการแจ้งเตือนไปยัง Discord ผ่าน webhook
        
        Args:
            signal: ข้อมูลสัญญาณที่จะส่ง
            
        Returns:
            สถานะความสำเร็จของการส่ง
        """
        if not DISCORD_WEBHOOK_URL:
            logger.warning("ไม่ได้กำหนดค่า DISCORD_WEBHOOK_URL")
            return False
        
        try:
            # สร้าง embed สำหรับ Discord
            emoji = self._get_category_emoji(signal['category'])
            color = self._get_discord_color(signal['category'])
            
            embed = {
                "title": f"{emoji} สัญญาณ {signal['category'].upper()} สำหรับ {signal['symbol']}",
                "color": color,
                "fields": [
                    {"name": "ราคาปัจจุบัน", "value": f"${signal['price']:.2f}", "inline": True},
                    {"name": "การคาดการณ์", "value": f"{signal['forecast_pct']:.2f}%", "inline": True},
                    {"name": "ความมั่นใจ", "value": f"{signal['confidence'] * 100:.1f}%", "inline": True}
                ],
                "footer": {"text": "ข้อมูลนี้เป็นเพียงการวิเคราะห์เชิงเทคนิค ไม่ใช่คำแนะนำในการลงทุน"}
            }
            
            # เพิ่มข้อมูลตัวชี้วัดถ้ามี
            if 'indicators' in signal and signal['indicators']:
                indicators_text = "\n".join([
                    f"• EMA9: {signal['indicators'].get('ema9', 'N/A'):.2f}" if signal['indicators'].get('ema9') else "• EMA9: N/A",
                    f"• EMA21: {signal['indicators'].get('ema21', 'N/A'):.2f}" if signal['indicators'].get('ema21') else "• EMA21: N/A",
                    f"• RSI14: {signal['indicators'].get('rsi14', 'N/A'):.2f}" if signal['indicators'].get('rsi14') else "• RSI14: N/A"
                ])
                embed["fields"].append({"name": "ตัวชี้วัดเทคนิคอล", "value": indicators_text, "inline": False})
            
            # สร้าง payload สำหรับส่งไปยัง Discord
            payload = {
                "username": "Crypto Signal Bot",
                "embeds": [embed]
            }
            
            # ส่งข้อมูลไปยัง Discord webhook
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code < 400:
                logger.info("ส่งการแจ้งเตือน Discord สำเร็จ: %s", response.status_code)
                return True
            else:
                logger.error("การส่ง Discord webhook ล้มเหลว: %s - %s", response.status_code, response.text)
                return False
                
        except Exception as e:
            logger.error("เกิดข้อผิดพลาดในการส่ง Discord webhook: %s", str(e))
            return False
    
    def _get_category_emoji(self, category: str) -> str:
        """รับอีโมจิที่เหมาะสมสำหรับประเภทสัญญาณ"""
        emoji_map = {
            "strong buy": "🚀",
            "weak buy": "📈",
            "hold": "⏸️",
            "weak sell": "📉",
            "strong sell": "⚠️"
        }
        return emoji_map.get(category.lower(), "🔔")
    
    def _get_category_color(self, category: str) -> str:
        """รับสีที่เหมาะสมสำหรับประเภทสัญญาณ"""
        color_map = {
            "strong buy": "#00b33c",  # เขียวเข้ม
            "weak buy": "#66cc66",    # เขียวอ่อน
            "hold": "#b3b3b3",        # เทา
            "weak sell": "#ff9980",   # แดงอ่อน
            "strong sell": "#ff3300"  # แดงเข้ม
        }
        return color_map.get(category.lower(), "#b3b3b3")
    
    def _get_discord_color(self, category: str) -> int:
        """รับรหัสสี int สำหรับ Discord embed"""
        color_map = {
            "strong buy": 0x00b33c,  # เขียวเข้ม
            "weak buy": 0x66cc66,    # เขียวอ่อน
            "hold": 0xb3b3b3,        # เทา
            "weak sell": 0xff9980,   # แดงอ่อน
            "strong sell": 0xff3300  # แดงเข้ม
        }
        return color_map.get(category.lower(), 0xb3b3b3)
    
    def process_message(self, message: Dict) -> None:
        """
        ประมวลผลข้อความที่ได้รับจาก Redis PubSub และส่งการแจ้งเตือนที่เหมาะสม
        
        Args:
            message: ข้อความจาก Redis
        """
        try:
            if message['type'] == 'message':
                # แปลง string เป็น JSON
                signal_data = json.loads(message['data'])
                
                # ส่งการแจ้งเตือนเฉพาะเมื่อไม่ใช่สัญญาณ "hold"
                if signal_data.get('category', '').lower() != 'hold':
                    logger.info("ได้รับสัญญาณ %s สำหรับ %s ที่ความมั่นใจ %.2f%%", 
                               signal_data.get('category', ''), 
                               signal_data.get('symbol', ''), 
                               signal_data.get('confidence', 0) * 100)
                    
                    # ส่งการแจ้งเตือนผ่านช่องทางต่างๆ
                    self.send_email_notification(signal_data)
                    self.send_webhook_notification(signal_data)
                    self.send_discord_notification(signal_data)
        except Exception as e:
            logger.error("เกิดข้อผิดพลาดในการประมวลผลข้อความ: %s", str(e))
    
    def start(self) -> None:
        """เริ่มต้นบริการแจ้งเตือนและรอรับข้อความจาก Redis PubSub"""
        logger.info("เริ่มต้นการทำงานของบริการแจ้งเตือน...")
        
        try:
            for message in self.pubsub.listen():
                self.process_message(message)
        except KeyboardInterrupt:
            logger.info("หยุดบริการแจ้งเตือนเนื่องจากการยกเลิกจากผู้ใช้")
        except Exception as e:
            logger.error("เกิดข้อผิดพลาดในบริการแจ้งเตือน: %s", str(e))
        finally:
            # ทำความสะอาดทรัพยากร
            self.pubsub.unsubscribe()
            logger.info("บริการแจ้งเตือนถูกปิดลง")

if __name__ == "__main__":
    notification_service = NotificationService()
    notification_service.start()