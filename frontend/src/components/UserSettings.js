import React, { useState } from 'react';
import './UserSettings.css';
import SymbolManager from './SymbolManager';

// คอมโพเนนต์การตั้งค่าผู้ใช้
const UserSettings = ({ settings, onSettingsChange }) => {
  // จัดการการเปลี่ยนแปลงระดับความเชื่อมั่น
  const handleConfidenceChange = (event) => {
    const newValue = parseFloat(event.target.value);
    onSettingsChange({ confidenceThreshold: newValue });
  };
  
  // จัดการการเปลี่ยนแปลงการแสดงสัญญาณอ่อน
  const handleWeakSignalsChange = (event) => {
    const newValue = event.target.checked;
    onSettingsChange({ showWeakSignals: newValue });
  };
  
  return (
    <div className="user-settings-container">
      <h3>การตั้งค่า</h3>
      
      <div className="settings-group">
        <label className="settings-label">ระดับความเชื่อมั่นขั้นต่ำ</label>
        <div className="settings-control">
          <input 
            type="range" 
            min="0" 
            max="1" 
            step="0.05" 
            value={settings.confidenceThreshold} 
            onChange={handleConfidenceChange} 
            className="confidence-slider"
          />
          <span className="confidence-value">{(settings.confidenceThreshold * 100).toFixed(0)}%</span>
        </div>
        <p className="settings-description">
          แสดงเฉพาะสัญญาณที่มีความเชื่อมั่นสูงกว่าค่านี้
        </p>
      </div>
      
      <div className="settings-group">
        <label className="settings-label">การแสดงสัญญาณ</label>
        <div className="settings-control checkbox-control">
          <input 
            type="checkbox" 
            id="show-weak-signals" 
            checked={settings.showWeakSignals} 
            onChange={handleWeakSignalsChange} 
          />
          <label htmlFor="show-weak-signals">แสดงสัญญาณอ่อน (Weak Buy/Sell)</label>
        </div>
        <p className="settings-description">
          เปิดใช้เพื่อแสดงสัญญาณอ่อน (weak buy/sell) ในหน้าจอและประวัติ
        </p>
      </div>
        {/* การจัดการสัญลักษณ์ */}
      <div className="settings-group">
        <SymbolManager />
      </div>
      
      <div className="settings-info">
        <h4>ข้อมูลการตั้งค่า</h4>
        <p>การตั้งค่าจะถูกบันทึกอัตโนมัติในเบราว์เซอร์ของคุณและจะถูกใช้ในการเข้าชมครั้งต่อไป</p>
        <p>การตั้งค่าเหล่านี้จะกรองเฉพาะการแสดงผลในหน้าจอ ไม่กระทบกับการเก็บข้อมูลใดๆ</p>
        <p>การเพิ่มหรือลบสัญลักษณ์จะมีผลกับระบบทันที และจะถูกบันทึกในไฟล์ .env</p>
      </div>
    </div>
  );
};

export default UserSettings;