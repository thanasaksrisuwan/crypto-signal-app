import React, { useState, useEffect } from 'react';
import './App.css';
import SignalDashboard from './components/SignalDashboard';
import SignalHistory from './components/SignalHistory';
import UserSettings from './components/UserSettings';
import Header from './components/Header';

function App() {
  // สถานะสำหรับสัญลักษณ์ที่เลือกปัจจุบัน
  const [selectedSymbol, setSelectedSymbol] = useState('BTCUSDT');
  
  // สถานะสำหรับการตั้งค่าผู้ใช้
  const [userSettings, setUserSettings] = useState({
    confidenceThreshold: 0.6,  // เริ่มต้นที่ 60%
    showWeakSignals: true,     // แสดงสัญญาณอ่อนโดยค่าเริ่มต้น
  });
  
  // โหลดการตั้งค่าจาก localStorage เมื่อเริ่มต้นแอป
  useEffect(() => {
    const savedSettings = localStorage.getItem('userSettings');
    const savedSymbol = localStorage.getItem('selectedSymbol');
    
    if (savedSettings) {
      setUserSettings(JSON.parse(savedSettings));
    }
    
    if (savedSymbol) {
      setSelectedSymbol(savedSymbol);
    }
  }, []);
  
  // บันทึกการตั้งค่าเมื่อมีการเปลี่ยนแปลง
  useEffect(() => {
    localStorage.setItem('userSettings', JSON.stringify(userSettings));
  }, [userSettings]);
  
  // บันทึกสัญลักษณ์ที่เลือกเมื่อมีการเปลี่ยนแปลง
  useEffect(() => {
    localStorage.setItem('selectedSymbol', selectedSymbol);
  }, [selectedSymbol]);
  
  // จัดการการเปลี่ยนแปลงการตั้งค่า
  const handleSettingsChange = (newSettings) => {
    setUserSettings({ ...userSettings, ...newSettings });
  };
  
  // จัดการการเปลี่ยนสัญลักษณ์
  const handleSymbolChange = (symbol) => {
    setSelectedSymbol(symbol);
  };
  
  return (
    <div className="App">
      <Header 
        selectedSymbol={selectedSymbol} 
        onSymbolChange={handleSymbolChange} 
      />
      
      <div className="dashboard-container">
        <div className="main-content">
          <SignalDashboard 
            symbol={selectedSymbol}
            settings={userSettings}
          />
          <SignalHistory 
            symbol={selectedSymbol} 
            settings={userSettings}
          />
        </div>
        
        <div className="sidebar">
          <UserSettings 
            settings={userSettings}
            onSettingsChange={handleSettingsChange}
          />
        </div>
      </div>
    </div>
  );
}

export default App;