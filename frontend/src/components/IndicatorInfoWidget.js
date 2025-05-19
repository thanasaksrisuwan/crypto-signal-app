import React, { useState } from 'react';
import { indicatorHelpText, tradingStyleGuide } from './technical-indicators-guide';
import './IndicatorInfoWidget.css';

/**
 * คอมโพเนนต์สำหรับแสดงข้อมูลและคำแนะนำเกี่ยวกับตัวบ่งชี้ทางเทคนิค
 * @returns {JSX.Element} คอมโพเนนต์ React
 */
const IndicatorInfoWidget = () => {
  const [selectedTab, setSelectedTab] = useState('indicators');
  const [selectedIndicator, setSelectedIndicator] = useState('rsi');
  const [selectedStyle, setSelectedStyle] = useState('dayTrading');

  /**
   * เปลี่ยนแท็บที่กำลังแสดง
   * @param {string} tabName - ชื่อแท็บที่ต้องการแสดง
   */
  const changeTab = (tabName) => {
    setSelectedTab(tabName);
  };

  return (
    <div className="indicator-info-widget">
      <div className="widget-header">
        <h3>คู่มือตัวบ่งชี้ทางเทคนิค</h3>
        <div className="tab-selector">
          <button 
            className={`tab-btn ${selectedTab === 'indicators' ? 'active' : ''}`}
            onClick={() => changeTab('indicators')}
          >
            ตัวบ่งชี้
          </button>
          <button 
            className={`tab-btn ${selectedTab === 'styles' ? 'active' : ''}`}
            onClick={() => changeTab('styles')}
          >
            สไตล์การเทรด
          </button>
        </div>
      </div>

      <div className="widget-content">
        {selectedTab === 'indicators' ? (
          <>
            <div className="indicator-selector">
              <button 
                className={`indicator-btn ${selectedIndicator === 'rsi' ? 'active' : ''}`}
                onClick={() => setSelectedIndicator('rsi')}
              >
                RSI
              </button>
              <button 
                className={`indicator-btn ${selectedIndicator === 'macd' ? 'active' : ''}`}
                onClick={() => setSelectedIndicator('macd')}
              >
                MACD
              </button>
              <button 
                className={`indicator-btn ${selectedIndicator === 'ema' ? 'active' : ''}`}
                onClick={() => setSelectedIndicator('ema')}
              >
                EMA
              </button>
              <button 
                className={`indicator-btn ${selectedIndicator === 'sma' ? 'active' : ''}`}
                onClick={() => setSelectedIndicator('sma')}
              >
                SMA
              </button>
            </div>
            <div className="indicator-info">
              <pre>{indicatorHelpText.showIndicatorInfo(selectedIndicator)}</pre>
            </div>
          </>
        ) : (
          <>
            <div className="style-selector">
              {Object.keys(tradingStyleGuide).map((style) => (
                <button 
                  key={style}
                  className={`style-btn ${selectedStyle === style ? 'active' : ''}`}
                  onClick={() => setSelectedStyle(style)}
                >
                  {tradingStyleGuide[style].name}
                </button>
              ))}
            </div>
            <div className="style-info">
              <h4>{tradingStyleGuide[selectedStyle].name}</h4>
              <div className="style-detail">
                <h5>ตัวบ่งชี้ที่แนะนำ:</h5>
                <ul>
                  {tradingStyleGuide[selectedStyle].indicators.map((indicator, index) => (
                    <li key={index}>{indicator}</li>
                  ))}
                </ul>
              </div>
              <div className="style-detail">
                <h5>กรอบเวลาที่แนะนำ:</h5>
                <ul>
                  {tradingStyleGuide[selectedStyle].timeframes.map((timeframe, index) => (
                    <li key={index}>{timeframe}</li>
                  ))}
                </ul>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default IndicatorInfoWidget;
