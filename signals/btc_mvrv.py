import cloudscraper
import numpy as np
import pandas as pd
from Signal_Template import SignalTemplate
import time 
from collections import deque
import statistics

class mvrv(SignalTemplate):
    def __init__(self, weight=0.5, ticker='BTC', signal_update_frequency_seconds=3600, window_size=7, buy_threshold=0.6, buy_exit_threshold=0.35):
        super().__init__(weight, ticker, signal_update_frequency_seconds)
        self.window_size = window_size
        self.z=0

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
        # self.history.append(latest)
        return df
    
    def get_signal(self):
        # f=int(time.time()*1e3)-3600*0*1000
        df=self.data()
        cur=df.iloc[-1]
        z=(cur-df.mean())/df.std()
        if self.z<-0.9:
            self.signal=1
        elif (self.z>-0.9):# or self.z<-1.5):
            self.signal=0
        


