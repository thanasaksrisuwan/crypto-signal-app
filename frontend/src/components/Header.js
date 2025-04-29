import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './Header.css';

const Header = ({ selectedSymbol, onSymbolChange }) => {
  // สถานะสำหรับรายการสัญลักษณ์ที่ใช้ได้
  const [availableSymbols, setAvailableSymbols] = useState([]);
  
  // โหลดรายการสัญลักษณ์ที่ใช้ได้จาก API
  useEffect(() => {
    const fetchAvailableSymbols = async () => {
      try {
        const response = await axios.get('/available-symbols');
        if (response.data && response.data.symbols) {
          setAvailableSymbols(response.data.symbols);
        }
      } catch (error) {
        console.error('ไม่สามารถโหลดรายการสัญลักษณ์ได้:', error);
        // ถ้าไม่สามารถโหลดได้ ใช้ค่าเริ่มต้นจาก SRS
        setAvailableSymbols(['BTCUSDT', 'ETHUSDT']);
      }
    };
    
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
          <h1>Crypto Signal Dashboard</h1>
        </div>
        
        <div className="symbol-selector">
          <label htmlFor="symbol-select">เลือกคู่เทรด:</label>
          <select 
            id="symbol-select" 
            value={selectedSymbol} 
            onChange={handleSymbolChange}
          >
            {availableSymbols.map(symbol => (
              <option key={symbol} value={symbol}>{symbol}</option>
            ))}
          </select>
        </div>
        
        <div className="current-time">
          {new Date().toLocaleString()}
        </div>
      </div>
    </header>
  );
};

export default Header;