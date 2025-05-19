import requests
import json
import time
import sys

# URL ของ API
API_BASE = "http://localhost:8000"

def print_with_color(text, color_code):
    """พิมพ์ข้อความพร้อมสีตามที่กำหนด"""
    print(f"\033[{color_code}m{text}\033[0m")

def print_success(text):
    """พิมพ์ข้อความแจ้งสำเร็จ"""
    print_with_color(f"✅ {text}", 92)  # สีเขียว

def print_error(text):
    """พิมพ์ข้อความแจ้งข้อผิดพลาด"""
    print_with_color(f"❌ {text}", 91)  # สีแดง

def print_info(text):
    """พิมพ์ข้อความทั่วไป"""
    print_with_color(f"ℹ️ {text}", 94)  # สีน้ำเงิน

def print_title(text):
    """พิมพ์หัวข้อ"""
    print("\n" + "="*50)
    print_with_color(f"🔍 {text}", 96)  # สีฟ้า
    print("="*50)

def get_current_symbols():
    """ดึงรายการสัญลักษณ์ที่มีอยู่ในปัจจุบัน"""
    try:
        response = requests.get(f"{API_BASE}/api/symbols")
        return response.json()
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาดในการดึงรายการสัญลักษณ์: {e}")
        return None

def add_symbol(symbol):
    """เพิ่มสัญลักษณ์ใหม่"""
    try:
        response = requests.post(f"{API_BASE}/api/symbols/add", json={"symbol": symbol})
        return response.json()
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาดในการเพิ่มสัญลักษณ์: {e}")
        return None

def remove_symbol(symbol):
    """ลบสัญลักษณ์"""
    try:
        response = requests.post(f"{API_BASE}/api/symbols/remove", json={"symbol": symbol})
        return response.json()
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาดในการลบสัญลักษณ์: {e}")
        return None

def run_tests():
    """ทดสอบการทำงานของระบบจัดการสัญลักษณ์"""
    # ทดสอบการดึงรายการสัญลักษณ์
    print_title("ทดสอบการดึงรายการสัญลักษณ์")
    result = get_current_symbols()
    
    if result and result["success"]:
        print_success(f"ดึงรายการสัญลักษณ์สำเร็จ: {', '.join(result['symbols'])}")
        initial_symbols = result["symbols"]
    else:
        print_error("ไม่สามารถดึงรายการสัญลักษณ์ได้")
        return
    
    # ทดสอบการเพิ่มสัญลักษณ์
    print_title("ทดสอบการเพิ่มสัญลักษณ์")
    
    test_symbols = ["DOGEUSDT", "XRPUSDT", "SOLUSDT"]
    
    for symbol in test_symbols:
        if symbol in initial_symbols:
            print_info(f"สัญลักษณ์ {symbol} มีอยู่แล้ว ทำการลบเพื่อทดสอบ")
            remove_result = remove_symbol(symbol)
            if not (remove_result and remove_result["success"]):
                print_error(f"ไม่สามารถลบสัญลักษณ์ {symbol} เพื่อเตรียมทดสอบได้")
                continue
                
        print_info(f"กำลังเพิ่มสัญลักษณ์ {symbol}...")
        add_result = add_symbol(symbol)
        
        if add_result and add_result["success"]:
            print_success(f"เพิ่มสัญลักษณ์ {symbol} สำเร็จ")
            print_info(f"รายการสัญลักษณ์ปัจจุบัน: {', '.join(add_result['symbols'])}")
            
            # ตรวจสอบว่าสัญลักษณ์ถูกเพิ่มจริง
            if symbol in add_result["symbols"]:
                print_success(f"ยืนยันว่าสัญลักษณ์ {symbol} ถูกเพิ่มในระบบแล้ว")
            else:
                print_error(f"สัญลักษณ์ {symbol} ไม่ถูกเพิ่มในระบบตามที่คาดหวัง")
        else:
            print_error(f"ไม่สามารถเพิ่มสัญลักษณ์ {symbol} ได้: {add_result['message'] if add_result else 'Unknown error'}")
    
    # ทดสอบการลบสัญลักษณ์
    print_title("ทดสอบการลบสัญลักษณ์")
    
    for symbol in test_symbols:
        print_info(f"กำลังลบสัญลักษณ์ {symbol}...")
        remove_result = remove_symbol(symbol)
        
        if remove_result and remove_result["success"]:
            print_success(f"ลบสัญลักษณ์ {symbol} สำเร็จ")
            print_info(f"รายการสัญลักษณ์ปัจจุบัน: {', '.join(remove_result['symbols'])}")
            
            # ตรวจสอบว่าสัญลักษณ์ถูกลบจริง
            if symbol not in remove_result["symbols"]:
                print_success(f"ยืนยันว่าสัญลักษณ์ {symbol} ถูกลบออกจากระบบแล้ว")
            else:
                print_error(f"สัญลักษณ์ {symbol} ยังคงอยู่ในระบบแม้จะทำการลบแล้ว")
        else:
            print_error(f"ไม่สามารถลบสัญลักษณ์ {symbol} ได้: {remove_result['message'] if remove_result else 'Unknown error'}")
    
    # คืนค่ารายการสัญลักษณ์กลับไปเป็นค่าเริ่มต้น
    print_title("คืนค่ารายการสัญลักษณ์กลับไปเป็นค่าเริ่มต้น")
    
    # ดึงรายการสัญลักษณ์ปัจจุบัน
    current = get_current_symbols()
    if not (current and current["success"]):
        print_error("ไม่สามารถดึงรายการสัญลักษณ์ปัจจุบันได้")
        return
    
    current_symbols = current["symbols"]
    
    # ลบสัญลักษณ์ที่ไม่ได้อยู่ในรายการเริ่มต้น
    for symbol in current_symbols:
        if symbol not in initial_symbols:
            print_info(f"ลบสัญลักษณ์ {symbol} ที่ไม่ได้อยู่ในรายการเริ่มต้น")
            remove_symbol(symbol)
    
    # เพิ่มสัญลักษณ์ที่อยู่ในรายการเริ่มต้นแต่ไม่มีในปัจจุบัน
    for symbol in initial_symbols:
        if symbol not in current_symbols:
            print_info(f"เพิ่มสัญลักษณ์ {symbol} ที่อยู่ในรายการเริ่มต้น")
            add_symbol(symbol)
    
    # ตรวจสอบสถานะสุดท้าย
    final = get_current_symbols()
    if final and final["success"]:
        print_success(f"รายการสัญลักษณ์สุดท้าย: {', '.join(final['symbols'])}")
        
        # ตรวจสอบว่าตรงกับรายการเริ่มต้นหรือไม่
        is_match = set(final["symbols"]) == set(initial_symbols)
        if is_match:
            print_success("คืนค่ารายการสัญลักษณ์กลับไปเป็นค่าเริ่มต้นสำเร็จ")
        else:
            print_error("รายการสัญลักษณ์สุดท้ายไม่ตรงกับรายการเริ่มต้น")
            print_info(f"รายการเริ่มต้น: {', '.join(initial_symbols)}")
            print_info(f"รายการสุดท้าย: {', '.join(final['symbols'])}")
    else:
        print_error("ไม่สามารถดึงรายการสัญลักษณ์สุดท้ายได้")
    
    print_title("การทดสอบเสร็จสมบูรณ์")

if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print_info("\nยกเลิกการทดสอบ")
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาดไม่คาดคิด: {e}")
        sys.exit(1)
