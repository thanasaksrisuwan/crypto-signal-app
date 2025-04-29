import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

// สร้าง root element และแสดงแอปพลิเคชัน
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// รายงานการวัดประสิทธิภาพเว็บ
reportWebVitals();