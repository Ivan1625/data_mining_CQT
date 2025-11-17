import cloudscraper
import numpy as np
import pandas as pd
from Signal_Template import SignalTemplate
import time 
from collections import deque
import statistics

class mvrv(SignalTemplate):
    def __init__(self, weight, ticker='BTC', signal_update_frequency_seconds=40, window_size=7):
        super().__init__(weight, ticker, signal_update_frequency_seconds)
        self.window_size = window_size

    def data(self):
        f=int(time.time()*1e3)
        scraper = cloudscraper.create_scraper()
        url=f'https://api.cryptoquant.com/live/v4/charts/61a601c545de34521f1dcc7a?window=DAY&from=1131379200000&to={f}&limit=70000'
        response=scraper.get(url)
        latest=response.json()['result']['data']
        df=pd.DataFrame(latest)
        df.columns=['t','mvrv']
        df['t']=pd.to_datetime(df['t'],unit='ms')
        df=df.iloc[-8:-1]
        return df
    
    def get_signal(self):
        retries=3
        for attempt in range(retries):
            try:
                df=self.data()
                df1=df['mvrv']
                cur=df.iloc[-1]['mvrv']
                z=(cur-df1.mean())/df1.std()
                print(f"z: {z}")
                if z<-0.9:
                    return 1
                else:
                    return 0
            except Exception as e:
                if attempt<retries-1:
                    time.sleep(10)
                else:
                    return self.signal
    
    
