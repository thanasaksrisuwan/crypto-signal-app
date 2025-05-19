import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Header.css';

const Header = ({ selectedSymbol, onSymbolChange }) => {
  // สถานะสำหรับรายการสัญลักษณ์ที่ใช้ได้
  const [availableSymbols, setAvailableSymbols] = useState([]);
  // โหลดรายการสัญลักษณ์ที่ใช้ได้จาก API
  const [isLoading, setIsLoading] = useState(false);
  
  const fetchAvailableSymbols = async () => {
    setIsLoading(true);
    try {
      // พยายามใช้ API endpoint ใหม่ก่อน
      const response = await axios.get('/api/symbols');
      if (response.data && response.data.success && response.data.symbols) {
        setAvailableSymbols(response.data.symbols);
        return;
      }
      
      // ถ้าไม่สำเร็จ ลองใช้ endpoint เดิม
      const oldResponse = await axios.get('/available-symbols');
      if (oldResponse.data && oldResponse.data.symbols) {
        setAvailableSymbols(oldResponse.data.symbols);
      }
    } catch (error) {
      console.error('ไม่สามารถโหลดรายการสัญลักษณ์ได้:', error);
      // ถ้าไม่สามารถโหลดได้ ใช้ค่าเริ่มต้นจาก SRS
      setAvailableSymbols(['BTCUSDT', 'ETHUSDT']);
    } finally {
      setIsLoading(false);
    }
  };
  
  // โหลดรายการสัญลักษณ์เมื่อคอมโพเนนต์ถูกโหลด
  useEffect(() => {
    fetchAvailableSymbols();
  }, []);
  
  // จัดการการเปลี่ยนสัญลักษณ์
  const handleSymbolChange = (event) => {
    const newSymbol = event.target.value;
    onSymbolChange(newSymbol);
  };
  
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="logo">
          <span className="logo-icon">📊</span>
          <h1>Crypto Signal Dashboard</h1>        </div>
        <div className="symbol-selector">
          <label htmlFor="symbol-select">เลือกคู่เทรด:</label>
          <div className="select-container">
            <select 
              id="symbol-select" 
              value={selectedSymbol} 
              onChange={handleSymbolChange}
              disabled={isLoading}
            >
            {availableSymbols.map(symbol => (
              <option key={symbol} value={symbol}>{symbol}</option>
            ))}
            </select>
            <button 
              className="refresh-button" 
              onClick={fetchAvailableSymbols} 
              disabled={isLoading}
              title="รีเฟรชรายการสัญลักษณ์"
            >
              {isLoading ? '⟳' : '↻'}
            </button>
          </div>
        </div>
        
        <div className="current-time">
          {new Date().toLocaleString()}
        </div>
      </div>
    </header>
  );
};

export default Header;