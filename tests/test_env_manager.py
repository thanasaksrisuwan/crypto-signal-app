import unittest
import os
import tempfile
import shutil
from unittest.mock import patch
import sys
import pathlib

# สร้าง path ไปยังโฟลเดอร์หลักของแอปพลิเคชัน
parent_dir = str(pathlib.Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from app import env_manager

class TestEnvManager(unittest.TestCase):
    """ทดสอบฟังก์ชันในโมดูล env_manager"""

    def setUp(self):
        """เตรียมสภาพแวดล้อมสำหรับการทดสอบ"""
        # สร้างโฟลเดอร์ชั่วคราวสำหรับการทดสอบ
        self.test_dir = tempfile.mkdtemp()
        
        # สร้างไฟล์ .env จำลองสำหรับการทดสอบ
        self.test_env_file = os.path.join(self.test_dir, ".env.test")
        with open(self.test_env_file, "w") as f:
            f.write("AVAILABLE_SYMBOLS=BTCUSDT,ETHUSDT\n")
            f.write("DEBUG_MODE=True\n")
        
        # เก็บค่าเดิมของ _env_cache เพื่อคืนค่าหลังการทดสอบ
        self._original_env_cache = env_manager._env_cache.copy()
        
        # ล้าง cache
        env_manager._env_cache.clear()

    def tearDown(self):
        """ทำความสะอาดหลังการทดสอบ"""
        # ลบโฟลเดอร์ชั่วคราว
        shutil.rmtree(self.test_dir)
        
        # คืนค่า cache เดิม
        env_manager._env_cache.clear()
        env_manager._env_cache.update(self._original_env_cache)

    @patch("app.env_manager.find_dotenv")
    def test_get_available_symbols(self, mock_find_dotenv):
        """ทดสอบฟังก์ชัน get_available_symbols"""
        # จำลองการอ่านค่าจากไฟล์ .env
        mock_find_dotenv.return_value = self.test_env_file
        
        with patch.dict(os.environ, {"AVAILABLE_SYMBOLS": "BTCUSDT,ETHUSDT"}):
            symbols = env_manager.get_available_symbols()
            self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT"])
        
        # ทดสอบกรณีไม่มีค่าใน .env
        with patch.dict(os.environ, {}, clear=True):
            symbols = env_manager.get_available_symbols()
            self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT"])  # ต้องได้ค่าเริ่มต้น

    @patch("app.env_manager.find_dotenv")
    @patch("app.env_manager.set_key")
    def test_add_symbol(self, mock_set_key, mock_find_dotenv):
        """ทดสอบฟังก์ชัน add_symbol"""
        # จำลองการหาและแก้ไขไฟล์ .env
        mock_find_dotenv.return_value = self.test_env_file
        
        with patch.dict(os.environ, {"AVAILABLE_SYMBOLS": "BTCUSDT,ETHUSDT"}):
            # ทดสอบการเพิ่มสัญลักษณ์ใหม่
            result = env_manager.add_symbol("DOGEUSDT")
            self.assertTrue(result)
            mock_set_key.assert_called_once_with(self.test_env_file, "AVAILABLE_SYMBOLS", "BTCUSDT,ETHUSDT,DOGEUSDT")
            
            # รีเซ็ต mock
            mock_set_key.reset_mock()
            
            # ทดสอบการเพิ่มสัญลักษณ์ที่มีอยู่แล้ว
            result = env_manager.add_symbol("BTCUSDT")
            self.assertFalse(result)
            mock_set_key.assert_not_called()

    @patch("app.env_manager.find_dotenv")
    @patch("app.env_manager.set_key")
    def test_remove_symbol(self, mock_set_key, mock_find_dotenv):
        """ทดสอบฟังก์ชัน remove_symbol"""
        # จำลองการหาและแก้ไขไฟล์ .env
        mock_find_dotenv.return_value = self.test_env_file
        
        with patch.dict(os.environ, {"AVAILABLE_SYMBOLS": "BTCUSDT,ETHUSDT"}):
            # ทดสอบการลบสัญลักษณ์ที่มีอยู่
            result = env_manager.remove_symbol("ETHUSDT")
            self.assertTrue(result)
            mock_set_key.assert_called_once_with(self.test_env_file, "AVAILABLE_SYMBOLS", "BTCUSDT")
            
            # รีเซ็ต mock
            mock_set_key.reset_mock()
            
            # ทดสอบการลบสัญลักษณ์ที่ไม่มีอยู่
            result = env_manager.remove_symbol("DOGEUSDT")
            self.assertFalse(result)
            mock_set_key.assert_not_called()
            
            # ทดสอบการลบสัญลักษณ์สุดท้าย
            with patch.dict(os.environ, {"AVAILABLE_SYMBOLS": "BTCUSDT"}):
                result = env_manager.remove_symbol("BTCUSDT")
                self.assertFalse(result)
                mock_set_key.assert_not_called()

if __name__ == "__main__":
    unittest.main()
