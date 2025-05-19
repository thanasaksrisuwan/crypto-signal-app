# การจัดการตัวแปรสภาพแวดล้อม (Environment Variables) ในแอปพลิเคชัน

แอปพลิเคชันของเราได้ใช้ระบบการจัดการตัวแปรสภาพแวดล้อมแบบศูนย์กลาง เพื่อให้ทุกส่วนของแอปพลิเคชันเข้าถึงข้อมูลการตั้งค่าเดียวกัน โดยไม่ต้องโหลด `.env` ซ้ำซ้อนในแต่ละไฟล์

## วิธีการใช้งาน

### 1. เตรียมไฟล์ .env

สร้างไฟล์ `.env` ที่ root directory ของโปรเจค โดยคัดลอกจาก `.env.example` และแก้ไขค่าต่าง ๆ ตามความต้องการ:

```bash
cp .env.example .env
```

### 2. การเข้าถึงตัวแปรสภาพแวดล้อมในโค้ด

นำเข้าโมดูล env_manager และใช้ฟังก์ชันที่มีอยู่:

```python
import os
import sys

# นำเข้าโมดูลจัดการตัวแปรสภาพแวดล้อม
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
import env_manager as env

# ดึงค่าตัวแปรโดยตรง
debug_mode = env.getenv("DEBUG_MODE", False, bool)
port = env.getenv("BACKEND_PORT", 8000, int)

# ใช้ฟังก์ชันดึงการตั้งค่าเป็นกลุ่ม
redis_config = env.get_redis_config()
print(f"Redis host: {redis_config['host']}")
```

### 3. ฟังก์ชันที่มีให้ใช้งาน

โมดูล `env_manager` มีฟังก์ชันให้ใช้งานดังนี้:

#### ฟังก์ชันพื้นฐาน

- `getenv(key, default=None, as_type=str)` - ดึงค่าตัวแปรพร้อมแปลงประเภทข้อมูล

#### ฟังก์ชันดึงการตั้งค่าเป็นกลุ่ม

- `get_redis_config()` - ดึงการตั้งค่า Redis ทั้งหมด
- `get_influxdb_config()` - ดึงการตั้งค่า InfluxDB ทั้งหมด
- `get_binance_config()` - ดึงการตั้งค่า Binance API
- `get_backend_config()` - ดึงการตั้งค่า Backend
- `get_notification_config()` - ดึงการตั้งค่าการแจ้งเตือน
- `get_trade_config()` - ดึงการตั้งค่าการเทรด

### 4. ประเภทข้อมูลที่รองรับ

ฟังก์ชัน `getenv` สามารถแปลงประเภทข้อมูลได้ดังนี้:

- `str` - ค่าข้อความ (ค่าเริ่มต้น)
- `int` - จำนวนเต็ม
- `float` - จำนวนทศนิยม
- `bool` - ค่าตรรกะ (True/False)
- `dict` - ข้อมูลแบบ dictionary (อ่านจาก JSON string)
- `list` - ข้อมูลแบบรายการ (อ่านจาก JSON string)

### 5. การเพิ่มตัวแปรใหม่

เมื่อต้องการเพิ่มตัวแปรสภาพแวดล้อมใหม่:

1. เพิ่มตัวแปรในไฟล์ `.env` และ `.env.example`
2. ถ้าต้องการฟังก์ชันเฉพาะทาง ให้เพิ่มฟังก์ชันใน `env_manager.py` 

ตัวอย่างการเพิ่มฟังก์ชันใหม่:

```python
def get_logging_config() -> Dict[str, Any]:
    """ดึงการตั้งค่าการบันทึกล็อก"""
    return {
        "log_level": getenv("LOG_LEVEL", "INFO"),
        "log_dir": getenv("LOG_DIR", "logs"),
        "max_log_size": getenv("MAX_LOG_SIZE", 10, int),
    }
```

### 6. การแคช (Caching)

โมดูล `env_manager` มีการแคชค่าที่เรียกใช้บ่อยเพื่อเพิ่มประสิทธิภาพ ไม่ต้องกังวลเรื่องการเรียกใช้งานซ้ำซ้อน

## ตัวอย่างการใช้งาน

ดูตัวอย่างการใช้งานเพิ่มเติมได้ที่ไฟล์ `env_example.py`

---

## หมายเหตุสำหรับการพัฒนา

### การทดสอบ (Testing)

เมื่อเขียนการทดสอบอัตโนมัติ คุณสามารถแทนที่ค่าสภาพแวดล้อมได้โดยการตั้งค่า environment variables โดยตรงในโค้ด:

```python
import os
os.environ["DEBUG_MODE"] = "False"
```

หรือใช้ไฟล์ `.env.test` แยกต่างหาก และโหลดก่อนที่จะเรียกใช้ `env_manager`:

```python
from dotenv import load_dotenv
load_dotenv(".env.test")
```

### การดีบัก (Debugging)

หากต้องการตรวจสอบว่าค่าจาก `.env` ถูกโหลดอย่างถูกต้องหรือไม่ คุณสามารถเรียกใช้ `env_example.py` เพื่อดูค่าทั้งหมดที่โหลดได้:

```bash
python app/env_example.py
```
