# src/execution.py
import os
from typing import Dict, Optional
from dotenv import load_dotenv
import requests
import hashlib
import hmac
import time


# Load .env (for local dev; in AWS, use Secrets Manager)
load_dotenv()

BASE_URL = "https://mock-api.roostoo.com"
# API_KEY = os.getenv("ROOSTOO_API_KEY")
# SECRET_KEY = os.getenv("ROOSTOO_SECRET_KEY")

API_KEY = "wzVdBhwUlDOB4hhpPIKxh0GSlvUnxWQXpoU7t0o69INPArXcyg0poWOa6m8gtayO"
SECRET_KEY = "vcXTcCASuT1qnlG9DPvG7kZfBJTPTvl0IErYG2QbgRYjgwwwmHxzovJVAjfgEJkp"

BASE_URL = "https://mock-api.roostoo.com"


class Execution:
    def __init__(self, current_position,target_position, ticker_ratio):#,dry_run: bool = True):

        self.signal=target_position
        self.current=current_position 
        self.ratio=ticker_ratio


    def generate_signature(self,params):
        query_string = '&'.join(["{}={}".format(k, params[k])
                                for k in sorted(params.keys())])
        us = SECRET_KEY.encode('utf-8')
        m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def get_server_time(self):
        r = requests.get(
            BASE_URL + "/v3/serverTime",
        )
        print(r.status_code, r.text)
        return r.json()

    def get_ex_info(self):
        r = requests.get(
            BASE_URL + "/v3/exchangeInfo",
        )
        print(r.status_code, r.text)
        return r.json()


    def get_ticker(self,pair=None):
        payload = {
            "timestamp": int(time.time()),
        }
        if pair:
            payload["pair"] = pair

        r = requests.get(
            BASE_URL + "/v3/ticker",
            params=payload,
        )
        print(r.status_code, r.text)
        return r.json()


    def get_balance(self):
        payload = {
            "timestamp": int(time.time()) * 1000,
        }

        r = requests.get(
            BASE_URL + "/v3/balance",
            params=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)
        return r.json()


    def place_order(self,coin, side, qty, price=None):
        payload = {
            "timestamp": int(time.time()) * 1000,
            "pair": coin + "/USD",
            "side": side,
            "quantity": qty,
        }

        if not price:
            payload['type'] = "MARKET"
        else:
            payload['type'] = "LIMIT"
            payload['price'] = price

        r = requests.post(
            BASE_URL + "/v3/place_order",
            data=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)


    def cancel_order(self,coin):
        payload = {
            "timestamp": int(time.time()) * 1000,
            # "order_id": 77,
            "pair": "BNB/USD",
        }

        r = requests.post(
            BASE_URL + "/v3/cancel_order",
            data=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)


    def query_order(self):
        payload = {
            "timestamp": int(time.time())*1000,
            # "order_id": 77,
            # "pair": "DASH/USD",
            # "pending_only": True,
        }

        r = requests.post(
            BASE_URL + "/v3/query_order",
            data=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)


    def pending_count(self):
        payload = {
            "timestamp": int(time.time()) * 1000,
        }

        r = requests.get(
            BASE_URL + "/v3/pending_count",
            params=payload,
            headers={"RST-API-KEY": API_KEY,
                    "MSG-SIGNATURE": self.generate_signature(payload)}
        )
        print(r.status_code, r.text)
        return r.json()
    
    def calculate(self):
        r=self.get_balance()
        cash=r['SpotWallet']['USD']['Free']
        signals = {}

        all_assets = set(self.current.keys()) | set(self.signal.keys())
    
        for asset in all_assets:
            curr = self.current.get(asset, 0)
            targ = self.signal.get(asset, 0)
            delta = targ - curr
            signals[asset] = delta

        return signals
    
    def get_portfolio_value(self) -> float:

        # 1. Get balance
        balance_resp = self.get_balance()
        wallet = balance_resp.get("SpotWallet", {})  # or "SpotWallet" if needed

        total_value = 0.0

        # 2. Loop through each asset in wallet
        for asset, balances in wallet.items():
            free_amount = balances.get("Free", 0.0)

            if asset == "USD":
                # USD value is just the amount
                usd_value = free_amount
                # print(f"USD: {free_amount} → ${usd_value:,.2f}")
                total_value += usd_value
            else:
                # For crypto assets: get price via ticker
                try:
                    pair = f"{asset}/USD"
                    ticker_resp = self.get_ticker(pair=pair)
                    
                    # Parse price from response
                    # Assume response is like: {"price": "60234.56", ...}
                    # or {"data": {"price": "60234.56"}}
                    price = None
                    # if "price" in ticker_resp:
                    #     price = float(ticker_resp["price"])
                    price = float(ticker_resp["Data"][pair]["LastPrice"])

                    usd_value = free_amount * price
                    # print(f"{asset}: {free_amount} @ ${price:,.2f} = ${usd_value:,.2f}")
                    total_value += usd_value

                except Exception as e:
                    print(f"❌ Error fetching price for {asset}: {e}")
                    continue

        print(f"✅ Total Portfolio Value: ${total_value:,.2f}")
        return total_value
            
    
    def send_order(self):
        signals=self.calculate()
        target_usd = {}
        total_value=self.get_portfolio_value()
        for asset, ratio in self.ratio.items():
            target_usd[asset] = total_value * ratio
            print(target_usd[asset])
            # print(f"Target {asset} value: ${target_usd[asset]:,.2f} ({ratio:.1%})")
        for asset, ratio in signals.items():
            target=target_usd[asset]*ratio
            print(target)
            # self.place_order(coin=asset,side=ratio/abs(ratio),qty=target)


