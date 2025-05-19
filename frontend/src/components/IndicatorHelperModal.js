import React from 'react';
import { rsiInfo, macdInfo, emaInfo, smaInfo } from './enhanced-indicators';
import './IndicatorHelperModal.css';

/**
 * แสดงหน้าต่างช่วยเหลือเกี่ยวกับตัวบ่งชี้ทางเทคนิค
 * @param {Object} props - พารามิเตอร์ของคอมโพเนนต์
 * @param {boolean} props.isOpen - สถานะการแสดงหน้าต่าง
 * @param {Function} props.onClose - ฟังก์ชันเรียกเมื่อปิดหน้าต่าง
 * @param {Function} props.onSelectIndicator - ฟังก์ชันเรียกเมื่อเลือกตัวบ่งชี้
 */
const IndicatorHelperModal = ({ isOpen, onClose, onSelectIndicator }) => {
  if (!isOpen) return null;

  const indicators = [rsiInfo, macdInfo, emaInfo, smaInfo];

  /**
   * เลือกตัวบ่งชี้และปิดหน้าต่าง
   * @param {string} indicatorType - ประเภทตัวบ่งชี้ที่เลือก
   */
  const handleSelectIndicator = (indicatorType) => {
    if (onSelectIndicator) {
      onSelectIndicator(indicatorType);
    }
    onClose();
  };

  return (
    <div className="indicator-helper-overlay">
      <div className="indicator-helper-modal">
        <div className="indicator-helper-header">
          <h3>ตัวบ่งชี้ทางเทคนิค</h3>
          <button className="close-button" onClick={onClose}>×</button>
        </div>
        
        <div className="indicator-helper-content">
          {indicators.map((indicator, index) => (
            <div key={index} className="indicator-item">
              <h4>{indicator.name}</h4>
              <p>{indicator.description}</p>
              
              <div className="indicator-interpretation">
                <h5>การตีความ:</h5>
                <ul>
                  {indicator.interpretation.map((item, idx) => (
                    <li key={idx}>{item.value}</li>
                  ))}
                </ul>
              </div>
              
              {indicator.formula && (
                <div className="indicator-formula">
                  <h5>สูตรคำนวณ:</h5>
                  <pre>{indicator.formula}</pre>
                </div>
              )}
              
              <div className="indicator-action">
                <button 
                  className="indicator-select-button"
                  onClick={() => handleSelectIndicator(indicator.name.split(' ')[0].toLowerCase())}
                >
                  {indicator === rsiInfo ? 'แสดง RSI' : 
                   indicator === macdInfo ? 'แสดง MACD' :
                   indicator === emaInfo ? 'เลือก EMA' :
                   'เลือก SMA'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default IndicatorHelperModal;
