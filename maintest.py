# for 
#     tickerratio
#     signal thread
#     exe


# exe.send_order(target_posiiton
#                )


#!/usr/bin/env python3
import time, logging, threading
from typing import Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(threadName)s] %(message)s")
log = logging.getLogger("master")

# ---------- config ----------
UPDATE_SEC   = 1
COIN_WEIGHTS = {"BTC": 0.40, "ETH": 0.35, "BNB": 0.25}
STRATS_PER_COIN = 5

# ---------- shared ----------
latest_target: Dict[str, float] = {}          # latest consensus
target_lock   = threading.Lock()              # guards writes
stop_all      = threading.Event()

# ---------- import your strategy ----------
from strategies import TestStrategy

def build_strategies() -> list:
    strats = []
    for coin, weight in COIN_WEIGHTS.items():
        for _ in range(STRATS_PER_COIN):
            strats.append(TestStrategy(weight / STRATS_PER_COIN, coin, update_sec=5))
    return strats

def build_consensus(strategies):
    votes = {}
    for s in strategies:
        votes.setdefault(s.ticker, []).append(s.get_signal())
    return {coin: sum(v) / len(v) for coin, v in votes.items()}

# ---------- master loop ----------
def master_loop(strategies):
    while not stop_all.is_set():
        cons = build_consensus(strategies)
        with target_lock:
            latest_target.clear()
            latest_target.update(cons)
        time.sleep(UPDATE_SEC)

# ---------- executor thread ----------
class DictExecutor(threading.Thread):
    def __init__(self, stop_evt):
        super().__init__(daemon=False, name="DictExecutor")
        self.stop   = stop_evt
        self.rate   = RateLimiter(5, 1)
        from exe import Execution
        self.broker = Execution(ticker_ratio={})

    def run(self):
        last = {coin: -1.0 for coin in COIN_WEIGHTS}
        while not self.stop.is_set():
            time.sleep(1)                       # tick aligned
            with target_lock:
                current = latest_target.copy()  # atomic snapshot
            for coin, frac in current.items():
                if abs(frac - last.get(coin, -1)) > 0.001:
                    last[coin] = frac
                    self.send(coin, frac)

    def send(self, coin: str, frac: float):
        side = 1 if frac > 0.5 else 0
        self.rate.wait()
        # ---- convert fraction to coin qty ----
        ticker = self.broker.get_ticker(pair=f"{coin}/USD")
        price  = float(ticker['Data'][f"{coin}/USD"]['LastPrice'])
        usd    = COIN_WEIGHTS[coin] * frac
        qty    = usd / price
        log.info("ORDER %s %s %.4f", coin, "BUY" if side else "SELL", qty)
        self.broker.place_order(coin=coin, side=1 if side else -1, qty=qty, price=None)

# ---------- rate limiter ----------
class RateLimiter:
    def __init__(self, rate, per):
        self.min_int = per / rate
        self.lock    = threading.Lock()
        self.last    = 0.0
    def wait(self):
        with self.lock:
            now = time.time()
            sleep = self.min_int - (now - self.last)
            if sleep > 0:
                time.sleep(sleep)
            self.last = time.time()

# ---------- start-up ----------
def main():
    strats = build_strategies()
    st_threads = [threading.Thread(target=s.run, daemon=True, name=f"Strat-{i}")
                  for i, s in enumerate(strats)]
    for t in st_threads:
        t.start()

    exec_th = DictExecutor(stop_all)
    exec_th.start()

    try:
        master_loop(strats)
    finally:
        stop_all.set()
        for t in st_threads:
            t.join(timeout=7)
        exec_th.join(timeout=5)
        log.info("Shutdown complete")

if __name__ == "__main__":
    main()