from Signal_Template import SignalTemplate
import requests
import json
import time
import pandas as pd
import numpy as np
from collections import deque
from datetime import datetime, timedelta, timezone
import ccxt
import okx.MarketData as MarketData

class HyperliquidETHDataFeed:
    def __init__(self):
        self.hyperliquid_url = "https://api.hyperliquid.xyz/info"
        self.okx_url = "https://www.okx.com/api/v5/market/candles?instId=ETH-USDT&bar=1D&limit=1"
    
    def fetch_ohlcv(self, exchange, symbol, timeframe, start_date, end_date, RATE_LIMIT_DELAY=0.05):
        try:
            start_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)
            
            all_data = []
            since = start_ts
            
            while since < end_ts:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=100)
                if not ohlcv:
                    break
                
                # Safety check
                last_timestamp = ohlcv[-1][0]
                if last_timestamp <= since:
                    break
                    
                all_data.extend(ohlcv)
                since = last_timestamp + 1
                
                time.sleep(RATE_LIMIT_DELAY)
            
            df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC')
            
            df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
            
            return df[['timestamp', 'close']]
        
        except Exception as e:
            return None

class HyOKX(SignalTemplate):
    def __init__(self, weight, ticker, signal_update_frequency_seconds, logger, window_size=5, sell_threshold=1.2, buy_threshold=-1, sell_exit_threshold=1.1, buy_exit_threshold=-1):
        super().__init__(weight, ticker, signal_update_frequency_seconds)
        self.window_size = window_size
        self.hyperliquid_window = deque([], maxlen=2)
        self.okx_window = deque([], maxlen=2)
        self.spread_window = deque([], maxlen=self.window_size)
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.buy_exit_threshold = buy_exit_threshold
        self.sell_exit_threshold = sell_exit_threshold

        self.datafeed = HyperliquidETHDataFeed()
        self.hyperliquid_symbol = 'ETH/USDC:USDC'
        self.okx_symbol = 'ETH/USDT'

    def initialize_window(self):
        try:
            TIMEFRAME = '1d'
            END_DATE = (datetime.now() - timedelta(days=1, hours=8)).replace(tzinfo=timezone.utc)
            START_DATE = END_DATE - timedelta(days=6)

            okx = ccxt.okx({
                'enableRateLimit': True,
            })

            hyperliquid = ccxt.hyperliquid({
                'enableRateLimit': True,
            })

            df_hyperliquid = self.datafeed.fetch_ohlcv(hyperliquid, self.hyperliquid_symbol, TIMEFRAME, START_DATE, END_DATE)
            df_okx = self.datafeed.fetch_ohlcv(okx, self.okx_symbol, TIMEFRAME, START_DATE, END_DATE)

            hyperliquid_window = df_hyperliquid['close'].apply(lambda x:int(x))
            okx_window = df_okx['close'].apply(lambda x:int(x))

            self.hyperliquid_window.extend(hyperliquid_window.to_list()[-2:])
            self.okx_window.extend(okx_window.to_list()[-2:])

            self.spread_window.extend((okx_window.diff().dropna() - hyperliquid_window.diff().dropna()).to_list())
            
            return True
        
        except Exception as e:
            return False

    def get_rolling_ratio(self)-> float:
        window_array = np.array(self.spread_window, dtype=float)
        mean = window_array.mean()
        std = window_array.std(ddof=1)
        rolling_ratio = (window_array[-1] - mean) / std if std !=0 else 0.0

        return rolling_ratio
    
    def get_signal(self):
        # TODO
        if not self.initialize_window():
            return 0

        if len(self.spread_window) < self.window_size:
            return 0

        rolling_ratio = self.get_rolling_ratio()
        if self.signal == 0: 
            if rolling_ratio > self.sell_threshold:
                return -1
            elif rolling_ratio < self.buy_threshold:
                return 1
            
        elif self.signal == 1 and rolling_ratio > self.buy_exit_threshold:
            return 0 
        
        elif self.signal == -1 and rolling_ratio < self.sell_exit_threshold:
            return 0
        
        return self.signal
        
