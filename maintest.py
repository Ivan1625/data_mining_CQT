#!/usr/bin/env python3
import time, logging, threading
from typing import Dict
from exe import Execution
# ---------- import your strategy ----------
from signals.hybinance import HyBinance
from signals.hyokx import HyOKX
from signals.btc_address import ActiveAddressBTC

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(threadName)s] %(message)s")
log = logging.getLogger("master")

# ---------- config ----------
COIN_WEIGHTS = {"BTC": 0.2, "ETH": 0.8}

# ---------- shared ----------
latest_target: Dict[str, float] = {}          # latest consensus
target_lock   = threading.Lock()              # guards writes
stop_all      = threading.Event()

def build_consensus(strategies):
    votes = {}
    for s in strategies:
        votes.setdefault(s.ticker, []).append(s.signal * s.weight)
    return {coin: max(sum(v) / len(v), 0) for coin, v in votes.items()}

# ---------- start-up ----------
def main():
    hybinance = HyBinance(1, "ETH", 60)
    hyokx = HyOKX(1, "ETH", 60)
    activeaddressBTC = ActiveAddressBTC(1, "BTC", 60)
    strats = [hybinance, hyokx, activeaddressBTC]

    st_threads = [threading.Thread(target=s.get_signal_thread, daemon=True, name=f"Strat-{i}")
                  for i, s in enumerate(strats)]
    for t in st_threads:
        t.start()

    exe = Execution(COIN_WEIGHTS)

    while True:
        print(f"len of strats: {len(strats)}")
        for i,s in enumerate(strats):
            print(f"{time.time()}: [{i}] {s.signal}")
        exe.send_order(build_consensus(strats))
        time.sleep(10)

if __name__ == "__main__":
    main()
