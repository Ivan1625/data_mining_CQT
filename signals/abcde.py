import cloudscraper
import numpy as np
import pandas as pd
from Signal_Template import SignalTemplate
import time 
from collections import deque
import statistics

class mvrv(SignalTemplate):
    def __init__(self, weight, ticker='ETH', signal_update_frequency_seconds=3600, window_size=7):
        super().__init__(weight, ticker, signal_update_frequency_seconds)
        self.window_size = window_size

    def data(self):
        f=int(time.time()*1e3)
        scraper = cloudscraper.create_scraper()
        url=f'https://api.cryptoquant.com/live/v4/charts/61adf26d56f85872fa84fa96?window=DAY&from=1131638400000&to={f}&limit=70000'
        response=scraper.get(url)
        latest=response.json()['result']['data']
        df=pd.DataFrame(latest)
        df.columns=['t','mvrv']
        df['mvrv']=df['mvrv'].diff().diff()
        df['t']=pd.to_datetime(df['t'],unit='ms')
        df=df.iloc[-9:-4]
        return df
    
    def get_signal(self):
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
            return 0
