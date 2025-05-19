import os
import sys
import argparse
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
from typing import Dict, List, Tuple, Optional, Any, Generator
import statistics
import gc
import psutil
import mmap
from contextlib import contextmanager
from dataclasses import dataclass
from typing import NamedTuple
import threading
from concurrent.futures import ThreadPoolExecutor

from .logger import LoggerFactory, log_execution_time, error_logger, MetricsLogger
from .signal_processor import grade_signal
from .influxdb_storage import InfluxDBStorage

# Initialize loggers
logger = LoggerFactory.get_logger('backtesting')
metrics = MetricsLogger('backtesting')

@dataclass
class ChunkConfig:
    """Configuration for data chunking"""
    size: int = 1000  # Number of candles per chunk
    overlap: int = 100  # Overlap between chunks to maintain continuity
    max_chunks: int = 10  # Maximum number of chunks to process at once

class PriceData(NamedTuple):
    """Immutable price data structure"""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class MemoryOptimizedBacktester:
    """Memory-optimized backtesting system"""
    
    def __init__(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """Initialize backtester with memory monitoring"""
        self.symbol = symbol
        self.logger = logger
        self.metrics = metrics
        
        # Set time range
        now = datetime.now()
        self.end_time = datetime.strptime(end_date, "%Y-%m-%d") if end_date else now
        self.start_time = datetime.strptime(start_date, "%Y-%m-%d") if start_date else now - timedelta(days=30)
        
        self.start_timestamp = int(self.start_time.timestamp() * 1000)
        self.end_timestamp = int(self.end_time.timestamp() * 1000)
        
        # Memory management settings
        self.chunk_config = ChunkConfig()
        self.data_file = None
        self.mmap_file = None
        
        # Initialize metrics
        self._record_memory_usage("initialization")
    
    def _record_memory_usage(self, operation: str):
        """Record memory usage metrics"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        self.metrics.record_metric(f'memory_usage_{operation}', {
            'rss': memory_info.rss,  # Resident Set Size
            'vms': memory_info.vms,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'timestamp': datetime.now().isoformat()
        })
    
    @contextmanager
    def _memory_managed_operation(self, operation: str):
        """Context manager for memory-intensive operations"""
        start_memory = psutil.Process(os.getpid()).memory_info().rss
        try:
            yield
        finally:
            end_memory = psutil.Process(os.getpid()).memory_info().rss
            delta_memory = end_memory - start_memory
            
            self.metrics.record_metric(f'memory_delta_{operation}', {
                'start': start_memory,
                'end': end_memory,
                'delta': delta_memory,
                'timestamp': datetime.now().isoformat()
            })
            
            if delta_memory > 100 * 1024 * 1024:  # If delta > 100MB
                gc.collect()  # Force garbage collection
    
    def _create_data_chunks(self, data: pd.DataFrame) -> Generator[pd.DataFrame, None, None]:
        """Create overlapping data chunks for processing"""
        chunk_size = self.chunk_config.size
        overlap = self.chunk_config.overlap
        
        for i in range(0, len(data), chunk_size - overlap):
            chunk = data.iloc[i:i + chunk_size].copy()
            if len(chunk) < 50:  # Minimum size for analysis
                continue
            yield chunk
    
    @log_execution_time()
    def load_historical_data(self) -> pd.DataFrame:
        """Load historical data with memory optimization"""
        with self._memory_managed_operation("data_loading"):
            try:
                storage = InfluxDBStorage()
                query = f"""
                    from(bucket: "crypto_data")
                        |> range(start: {self.start_timestamp}, stop: {self.end_timestamp})
                        |> filter(fn: (r) => r["symbol"] == "{self.symbol}")
                        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                """
                
                # Load data in chunks
                chunk_size = 10000
                all_data = []
                
                for chunk in storage.query_chunks(query, chunk_size):
                    df_chunk = pd.DataFrame(chunk)
                    all_data.append(df_chunk)
                    
                    # Monitor memory
                    if len(all_data) >= self.chunk_config.max_chunks:
                        combined = pd.concat(all_data, ignore_index=True)
                        all_data = [combined]
                        gc.collect()
                
                df = pd.concat(all_data, ignore_index=True)
                return df
                
            except Exception as e:
                self.logger.error(f"Error loading historical data: {e}")
                error_logger.log_error(e, {
                    'component': 'backtesting',
                    'operation': 'load_historical_data',
                    'symbol': self.symbol
                })
                raise
    
    @log_execution_time()
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators with memory optimization"""
        with self._memory_managed_operation("indicator_calculation"):
            try:
                results = []
                
                # Process data in chunks
                for chunk in self._create_data_chunks(data):
                    # Calculate indicators for chunk
                    chunk_result = self._calculate_chunk_indicators(chunk)
                    results.append(chunk_result)
                    
                    # Clean up chunk memory
                    del chunk
                    gc.collect()
                
                # Combine results
                return pd.concat(results, ignore_index=True)
                
            except Exception as e:
                self.logger.error(f"Error calculating indicators: {e}")
                error_logger.log_error(e, {
                    'component': 'backtesting',
                    'operation': 'calculate_indicators',
                    'symbol': self.symbol
                })
                raise
    
    def _calculate_chunk_indicators(self, chunk: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators for a single chunk"""
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Calculate indicators in parallel
            ema_future = executor.submit(self._calculate_emas, chunk)
            sma_future = executor.submit(self._calculate_smas, chunk)
            rsi_future = executor.submit(self._calculate_rsi, chunk)
            
            # Get results
            chunk['ema9'], chunk['ema21'] = ema_future.result()
            chunk['sma20'], chunk['sma50'] = sma_future.result()
            chunk['rsi'] = rsi_future.result()
            
        return chunk
    
    def _calculate_emas(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculate EMAs using numpy for memory efficiency"""
        closes = data['close'].values
        alpha9 = 2 / (9 + 1)
        alpha21 = 2 / (21 + 1)
        
        ema9 = np.zeros_like(closes)
        ema21 = np.zeros_like(closes)
        
        ema9[0] = closes[0]
        ema21[0] = closes[0]
        
        for i in range(1, len(closes)):
            ema9[i] = alpha9 * closes[i] + (1 - alpha9) * ema9[i-1]
            ema21[i] = alpha21 * closes[i] + (1 - alpha21) * ema21[i-1]
        
        return pd.Series(ema9), pd.Series(ema21)
    
    def _calculate_smas(self, data: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculate SMAs using rolling window"""
        closes = data['close']
        return closes.rolling(20).mean(), closes.rolling(50).mean()
    
    def _calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI using numpy for memory efficiency"""
        closes = data['close'].values
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.zeros_like(closes)
        avg_losses = np.zeros_like(closes)
        
        # Initialize averages
        avg_gains[period] = np.mean(gains[:period])
        avg_losses[period] = np.mean(losses[:period])
        
        # Calculate remaining values
        for i in range(period + 1, len(closes)):
            avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains[i-1]) / period
            avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = avg_gains[period:] / (avg_losses[period:] + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return pd.Series([None] * period + rsi.tolist())
    
    @log_execution_time()
    def analyze_performance(self, signals_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze trading performance with memory optimization"""
        with self._memory_managed_operation("performance_analysis"):
            try:
                results = {
                    'total_signals': len(signals_df),
                    'signal_distribution': {},
                    'profit_loss': 0.0,
                    'win_rate': 0.0,
                    'trades': []
                }
                
                # Process signals in chunks
                for chunk in self._create_data_chunks(signals_df):
                    chunk_results = self._analyze_chunk_performance(chunk)
                    self._merge_chunk_results(results, chunk_results)
                    
                    # Clean up chunk memory
                    del chunk
                    gc.collect()
                
                # Calculate final statistics
                self._calculate_final_statistics(results)
                return results
                
            except Exception as e:
                self.logger.error(f"Error analyzing performance: {e}")
                error_logger.log_error(e, {
                    'component': 'backtesting',
                    'operation': 'analyze_performance',
                    'symbol': self.symbol
                })
                raise
    
    def cleanup(self):
        """Clean up resources and temporary files"""
        try:
            if self.mmap_file:
                self.mmap_file.close()
            if self.data_file:
                os.unlink(self.data_file)
            
            # Force garbage collection
            gc.collect()
            
            # Record final memory state
            self._record_memory_usage("cleanup")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            error_logger.log_error(e, {
                'component': 'backtesting',
                'operation': 'cleanup'
            })
