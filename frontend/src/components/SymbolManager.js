import React, { useState, useEffect } from 'react';
import './SymbolManager.css';
import axios from 'axios';

/**
 * คอมโพเนนต์สำหรับจัดการสัญลักษณ์คริปโตที่รองรับในระบบ
 * ช่วยให้ผู้ใช้สามารถเพิ่มหรือลบคู่เทรดผ่านทาง UI ได้
 * 
 * @returns {JSX.Element} คอมโพเนนต์ SymbolManager
 */
const SymbolManager = () => {
  // สถานะสำหรับรายการสัญลักษณ์ที่มีอยู่
  const [symbols, setSymbols] = useState([]);
  
  // สถานะสำหรับสัญลักษณ์ใหม่ที่จะเพิ่ม
  const [newSymbol, setNewSymbol] = useState('');
  
  // สถานะสำหรับข้อความแสดงผลการทำงาน
  const [message, setMessage] = useState('');
  
  // สถานะสำหรับประเภทข้อความ (success, error, info)
  const [messageType, setMessageType] = useState('');
  
  // สถานะสำหรับการโหลดข้อมูล
  const [isLoading, setIsLoading] = useState(false);

  // โหลดรายการสัญลักษณ์เมื่อคอมโพเนนต์ถูกโหลด
  useEffect(() => {
    fetchSymbols();
  }, []);

  /**
   * ดึงรายการสัญลักษณ์ทั้งหมดจาก API
   */
  const fetchSymbols = async () => {
    setIsLoading(true);
    try {
      const response = await axios.get('/api/symbols');
      
      if (response.data.success) {
        setSymbols(response.data.symbols);
        clearMessage();
      } else {
        showMessage(response.data.message, 'error');
      }
    } catch (error) {
      showMessage(`เกิดข้อผิดพลาดในการโหลดสัญลักษณ์: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * เพิ่มสัญลักษณ์ใหม่ไปยังระบบ
   */
  const addSymbol = async () => {
    // ตรวจสอบข้อมูลนำเข้า
    if (!newSymbol.trim()) {
      showMessage('กรุณากรอกสัญลักษณ์ที่ต้องการเพิ่ม', 'error');
      return;
    }

    setIsLoading(true);
    try {
      // ปรับให้เป็นรูปแบบมาตรฐาน (ตัวพิมพ์ใหญ่)
      const formattedSymbol = newSymbol.trim().toUpperCase();
      
      // ตรวจสอบว่าลงท้ายด้วย USDT หรือไม่
      if (!formattedSymbol.endsWith('USDT')) {
        showMessage('สัญลักษณ์ต้องลงท้ายด้วย USDT (เช่น BTCUSDT)', 'error');
        setIsLoading(false);
        return;
      }
      
      // เรียกใช้ API เพื่อเพิ่มสัญลักษณ์
      const response = await axios.post('/api/symbols/add', {
        symbol: formattedSymbol
      });
      
      if (response.data.success) {
        // อัปเดตรายการและแสดงข้อความสำเร็จ
        setSymbols(response.data.symbols);
        showMessage(`เพิ่มสัญลักษณ์ ${formattedSymbol} สำเร็จ`, 'success');
        setNewSymbol(''); // ล้างช่องกรอกข้อมูล
      } else {
        showMessage(response.data.message, 'error');
      }
    } catch (error) {
      showMessage(`เกิดข้อผิดพลาดในการเพิ่มสัญลักษณ์: ${error.message}`, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * ลบสัญลักษณ์ออกจากระบบ
   * @param {string} symbol สัญลักษณ์ที่ต้องการลบ
   */
  const removeSymbol = async (symbol) => {
    if (symbols.length <= 1) {
      showMessage('ไม่สามารถลบสัญลักษณ์สุดท้ายได้', 'error');
      return;
    }
    
    if (window.confirm(`คุณต้องการลบสัญลักษณ์ ${symbol} ใช่หรือไม่?`)) {
      setIsLoading(true);
      try {
        const response = await axios.post('/api/symbols/remove', { symbol });
        
        if (response.data.success) {
          setSymbols(response.data.symbols);
          showMessage(`ลบสัญลักษณ์ ${symbol} สำเร็จ`, 'success');
        } else {
          showMessage(response.data.message, 'error');
        }
      } catch (error) {
        showMessage(`เกิดข้อผิดพลาดในการลบสัญลักษณ์: ${error.message}`, 'error');
      } finally {
        setIsLoading(false);
      }
    }
  };

  /**
   * แสดงข้อความแจ้งเตือนและกำหนดประเภท
   * @param {string} text ข้อความที่ต้องการแสดง
   * @param {string} type ประเภทของข้อความ (success, error, info)
   */
  const showMessage = (text, type) => {
    setMessage(text);
    setMessageType(type);
    
    // ล้างข้อความอัตโนมัติหลังจาก 5 วินาที
    setTimeout(() => {
      clearMessage();
    }, 5000);
  };

  /**
   * ล้างข้อความแจ้งเตือน
   */
  const clearMessage = () => {
    setMessage('');
    setMessageType('');
  };

  /**
   * จัดการการกด Enter ในช่องกรอกข้อมูล
   * @param {Event} e เหตุการณ์คีย์บอร์ด
   */
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      addSymbol();
    }
  };

  return (
    <div className="symbol-manager">
      <h3>จัดการสัญลักษณ์คู่เทรด</h3>
      
      {message && (
        <div className={`message ${messageType}`}>
          {message}
          <button className="close-btn" onClick={clearMessage}>×</button>
        </div>
      )}
      
      <div className="symbols-container">
        <h4>สัญลักษณ์ที่มีอยู่ ({symbols.length})</h4>
        
        <div className="symbols-list">
          {symbols.map(symbol => (
            <div key={symbol} className="symbol-item">
              <span>{symbol}</span>
              <button 
                className="remove-btn" 
                onClick={() => removeSymbol(symbol)}
                disabled={isLoading || symbols.length <= 1}
              >
                ลบ
              </button>
            </div>
          ))}
          
          {symbols.length === 0 && !isLoading && (
            <div className="empty-message">ไม่พบสัญลักษณ์ที่รองรับ</div>
          )}
          
          {isLoading && (
            <div className="loading">กำลังโหลด...</div>
          )}
        </div>
      </div>
      
      <div className="add-symbol-container">
        <h4>เพิ่มสัญลักษณ์ใหม่</h4>
        <div className="add-symbol-form">
          <input
            type="text"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="เช่น BTCUSDT, ETHUSDT"
            disabled={isLoading}
          />
          <button 
            className="add-btn" 
            onClick={addSymbol}
            disabled={isLoading || !newSymbol.trim()}
          >
            เพิ่ม
          </button>
        </div>
        
        <p className="help-text">
          สัญลักษณ์ต้องอยู่ในรูปแบบ <code>[ชื่อเหรียญ]USDT</code> เช่น BTCUSDT, ETHUSDT, ADAUSDT
        </p>
      </div>
    </div>
  );
};

export default SymbolManager;
