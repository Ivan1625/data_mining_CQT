#!/usr/bin/env python3
import time, logging, threading
import requests
import ast
from typing import Dict
from exe import Execution
# ---------- import your strategy ----------
from signals.hybinance import HyBinance
from signals.hyokx import HyOKX
from signals.btc_address import ActiveAddressBTC
from signals.depositor_eth import Depositor_ETH
from signals.btc_mvrv import mvrv
from signals.hmm import hmm_signal
from signals.abcde import mvrv as etht
from signals.ada import adatvs 
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(threadName)s] %(message)s")
log = logging.getLogger("master")

# ---------- config ----------
try:
    gist_id = '4994d64b301f85d2d2013e3eb6f5ab26'
    api_url = f"https://api.github.com/gists/{gist_id}"
    r = requests.get(api_url)
    data = r.json()
    d=data['files']['gistfile1.txt']['content']
    COIN_WEIGHTS = ast.literal_eval(d)
except:
    COIN_WEIGHTS = {"BTC": 0.2, "ETH": 0.3, "SOL": 0.1, "BNB": 0.1, "SUI": 0.1, "XRP": 0.1, "ADA": 0.1}
# COIN_WEIGHTS = {'ZEC':0}

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
    # hybinance = HyBinance(1, "ETH", 60)
    # hyokx = HyOKX(1, "ETH", 60)
    # activeaddressBTC = ActiveAddressBTC(1, "BTC", 60)
    # depositorETH_5 = Depositor_ETH(1, "ETH", 60)
    # depositorETH_15 = Depositor_ETH(1, "ETH", 60, window_size=15, buy_threshold=0.7, buy_exit_threshold=0.55)
    mvrv_btc=mvrv(1)
    # tvseth=etht(1)
    # activeaddressSOL = ActiveAddressBTC(1, "SOL", 60)
    # activeaddressBNB = ActiveAddressBTC(1, "BNB", 60)
    # depositorSUI_5 = Depositor_ETH(1, "SUI", 60)
    # depositorSUI_15 = Depositor_ETH(1, "SUI", 60, window_size=15, buy_threshold=0.7, buy_exit_threshold=0.55)
    # depositorXRP_15 = Depositor_ETH(1, "XRP", 60, window_size=15, buy_threshold=0.7, buy_exit_threshold=0.55)
    # adatvsada=adatvs(1)


    # strats = [hybinance, hyokx, activeaddressBTC, depositorETH_5, depositorETH_15, mvrv_btc,tvseth, activeaddressSOL, activeaddressBNB, depositorSUI_5,
              # depositorSUI_15, depositorXRP_15, adatvsada]/
    strats = [mvrv_btc]

    st_threads = [threading.Thread(target=s.get_signal_thread, daemon=True, name=f"Strat-{i}")
                  for i, s in enumerate(strats)]
    for t in st_threads:
        t.start()

    exe = Execution(COIN_WEIGHTS)

    while True:
        print(f"len of strats: {len(strats)}")
        for i,s in enumerate(strats):
            print(f"{time.time()}: [{i}] {s.signal}")
        curbtc=exe.get_portfolio_value(spec='ZEC')
        try:
            print(f"current_nav:{curbtc[0]}")
            print(f"coin weights: {COIN_WEIGHTS}")
            print(curbtc[1])
        except:
            print('nth')
        # print(f"current_nav_btc:{curbtc[1]}")
        # print(f"current_btc_to_nav:{curbtc[2]}")
        # print(f"current_btc_to_(nav_btc):{curbtc[3]}")
        # cureth=exe.get_portfolio_value(spec='ETH')
        # print(f"current_nav:{cureth[0]}")
        # print(f"current_nav_eth:{cureth[1]}")
        # print(f"current_eth_to_nav:{cureth[2]}")
        # print(f"current_eth_to_(nav_eth):{cureth[3]}")
        # cureth=exe.get_portfolio_value(spec='SOL')
        # # print(f"current_nav:{cureth[0]}")
        # print(f"current_nav_sol:{cureth[1]}")
        # print(f"current_sol_to_nav:{cureth[2]}")
        # print(f"current_sol_to_(nav_sol):{cureth[3]}")
        # cureth=exe.get_portfolio_value(spec='SUI')
        # # print(f"current_nav:{cureth[0]}")
        # print(f"current_nav_sui:{cureth[1]}")
        # print(f"current_sui_to_nav:{cureth[2]}")
        # print(f"current_sui_to_(nav_sui):{cureth[3]}")
        # cureth=exe.get_portfolio_value(spec='BNB')
        # # print(f"current_nav:{cureth[0]}")
        # print(f"current_nav_bnb:{cureth[1]}")
        # print(f"current_bnb_to_nav:{cureth[2]}")
        # print(f"current_bnb_to_(nav_bnb):{cureth[3]}")
        # cureth=exe.get_portfolio_value(spec='XRP')
        # # print(f"current_nav:{cureth[0]}")
        # print(f"current_nav_xrp:{cureth[1]}")
        # print(f"current_xrp_to_nav:{cureth[2]}")
        # print(f"current_xrp_to_(nav_xrp):{cureth[3]}")
        # cureth=exe.get_portfolio_value(spec='ADA')
        # # print(f"current_nav:{cureth[0]}")
        # print(f"current_nav_ada:{cureth[1]}")
        # print(f"current_ada_to_nav:{cureth[2]}")
        # print(f"current_ada_to_(nav_ada):{cureth[3]}")

        
        exe.send_order(build_consensus(strats))
        
        time.sleep(10)

if __name__ == "__main__":
    main()
