import requests
import pandas as pd
import numpy as np
from Signal_Template import SignalTemplate

class GlassnodeScraper:
    def __init__(self, url, unit='s'):
        self.url = url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Cookie": "_ga_YYWW6JR31S=GS2.1.s1749024057$o2$g1$t1749024132$j51$l0$h0; _hjSessionUser_1425107=eyJpZCI6IjBhMjhlNDFlLWFiZDItNWQ1My05M2FiLTA3YWI4MGYxMGRkOSIsImNyZWF0ZWQiOjE3NDk2MTEyOTYzNzksImV4aXN0aW5nIjp0cnVlfQ==; _ga_HJE430PTJT=GS2.1.s1755182126$o6$g1$t1755184628$j58$l0$h0; _gcl_au=1.1.185577310.1757523604; _gid=GA1.2.2127059702.1763826526; _gat_UA-129287447-1=1; _hjSession_1425107=eyJpZCI6ImZiZjdhMjY1LWE3NjQtNGFiMi1hNGJhLWIzYmUyOWNkN2NiZCIsImMiOjE3NjM4MjY1Mjg1MTksInMiOjAsInIiOjAsInNiIjowLCJzciI6MCwic2UiOjAsImZzIjowLCJzcCI6MX0=; _ga=GA1.2.1373200150.1761115258; _ga_M9YVRZCN8G=GS2.1.s1763826526$o8$g1$t1763826557$j29$l0$h0; _ga_MT5MWT6847=GS2.1.s1763826526$o8$g1$t1763826557$j29$l0$h0; _s=MTc2MzgyNjU1N3xLSjVYZk5zcVcyMUVWb09wVkd2OUpwcGM3NEVSbWpYQWZvdjAxU0Rla1NzRUkwanREUDF4MmdudmxaR0dmM289fMUUBfUCW30U366silkBIUPi14iBspky9teTCtBptTZN"
        }
        self.unit = unit
    
    def get_data(self):
        r = requests.get(url=self.url, headers=self.headers)
        return r.json()
    
    def get_DataFrame(self):
        data = self.get_data()
        df = pd.DataFrame(data)
        df = df.rename(columns={"t": "Date"})
        df['Date'] = pd.to_datetime(df['Date'], unit=self.unit)
        return df
    
class ActiveAddressBTC(SignalTemplate):
    def __init__(self, weight, ticker, signal_update_frequency_seconds, window_size=4, buy_threshold=0.6, buy_exit_threshold=0.35):
        super().__init__(weight, ticker, signal_update_frequency_seconds)
        self.window_size = window_size
        self.diff_window = pd.DataFrame()
        self.buy_threshold = buy_threshold
        self.buy_exit_threshold = buy_exit_threshold
        self.url = 'https://api.glassnode.com/v1/metrics/addresses/active_count?a=BTC&i=24h&referrer=dashboards'

        self.datafeed = GlassnodeScraper(self.url)

    def initialize_window(self):
        try:
            df = self.datafeed.get_DataFrame().iloc[-self.window_size-2:-1]
            df['v'] = df['v'].diff()
            df = df.dropna()
            self.diff_window = df[['v']].copy()
            
            return True
        
        except Exception as e:
            return False

    def get_rolling_ratio(self)-> float:
        window_array = np.array(self.diff_window['v'], dtype=float)
        mean = window_array.mean()
        std = window_array.std(ddof=1)
        rolling_ratio = (window_array[-1] - mean) / std if std !=0 else 0.0

        return rolling_ratio
    
    def get_signal(self):
        # TODO
        # if not self.initialize_window():
        #     return 0

        # if len(self.diff_window) < self.window_size - 2:
        #     return 0
            
        # rolling_ratio = self.get_rolling_ratio()
        # print(f"{self.ticker}| {self.last_updated}: {rolling_ratio}")
        # if self.signal == 0: 
        #     if rolling_ratio > self.buy_threshold:
        #         return 1
            
        # elif self.signal == 1 and rolling_ratio < self.buy_exit_threshold:
        #     return 0 
        
        # return self.signal
        return -1
