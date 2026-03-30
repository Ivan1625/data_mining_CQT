import time
from abc import ABC, abstractmethod

class SignalTemplate(ABC):
    def __init__(self, weight: float, ticker: str, update_frequency: int):
        self.weight = weight
        self.ticker = ticker
        self.update_frequency = update_frequency
        self.signal = 0
        self.last_updated = 0
        self.buy_price = None
        self.is_stoploss = False
    
    def get_signal_thread(self):
        while True:
            self.signal = self.get_signal()
            self.last_updated = time.time()
            time.sleep(self.update_frequency)

    def enforce_stoploss(self):
        self.is_stoploss = True

    @abstractmethod
    def get_signal(self):
        raise NotImplementedError
