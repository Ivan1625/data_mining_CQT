# src/execution.py
import os
from typing import Dict, Optional
from dotenv import load_dotenv
import requests
import hashlib
import hmac
import time
import numpy as np
import math
from decimal import Decimal, ROUND_DOWN

# Load .env (for local dev; in AWS, use Secrets Manager)
# load_dotenv()

BASE_URL = "https://mock-api.roostoo.com"
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("API_SECRET")

# API_KEY = "wzVdBhwUlDOB4hhpPIKxh0GSlvUnxWQXpoU7t0o69INPArXcyg0poWOa6m8gtayO"
# SECRET_KEY = "vcXTcCASuT1qnlG9DPvG7kZfBJTPTvl0IErYG2QbgRYjgwwwmHxzovJVAjfgEJkp"


class Execution:
    def __init__(self, ticker_ratio):
        self.ratio=ticker_ratio

    def print(self):
        print(API_KEY)
    def generate_signature(self,params):
        query_string = '&'.join(["{}={}".format(k, params[k]) for k in sorted(params.keys())])
        us = SECRET_KEY.encode('utf-8')
        m = hmac.new(us, query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def get_server_time(self):
        r = requests.get(    BASE_URL + "/v3/serverTime",        )
        # print(r.status_code, r.text)
        return r.json()

    def get_ex_info(self):
        r = requests.get(
            BASE_URL + "/v3/exchangeInfo",
        )
        # print(r.status_code, r.text)
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
        # print(r.status_code, r.text)
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
        # print(r.status_code, r.text)
        return r.json()


    def place_order(self,coin, side, qty, price=None):
        if side==1:
            side='BUY'
        elif side==-1:
            side='SELL'
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
        return r.status_code


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
    
    def get_portfolio_value(self,bal=None,tick=None,spec=None) -> float:
        balance_resp = bal if bal is not None else self.get_balance()
        wallet = balance_resp.get("SpotWallet", {})  
        total_value = 0.0
        ticker=tick if tick is not None else self.get_ticker()
        for asset, balances in wallet.items():
                free_amount = balances.get("Free", 0.0)
                if asset == "USD":
                    total_value += free_amount
                else:
                    try:
                        pair = f"{asset}/USD"
                        price = float(ticker['Data'][pair]['LastPrice'])
                        usd_value = free_amount * price
                        total_value += usd_value
                    except Exception as e:
                        print(f" Error fetching price for {asset}: {e}")
                        continue
        if spec==None:
            return total_value
        else: 
            try:
                value=wallet[spec]['Free']*ticker['Data'][f"{spec}/USD"]['LastPrice']
                proportion_p=value/total_value
                proportion_t=value/(total_value*self.ratio[spec])
                return total_value,value, proportion_p, proportion_t
            except:
                return total_value,0,0,0
            

    def send_order(self, target_position:Dict):
        self.signal=target_position
        coin_lot = {}
        r=self.get_balance()
        tick=self.get_ticker()
        info=self.get_ex_info()
        i=3
        total_value=self.get_portfolio_value(bal=r,tick=tick)
        for asset, ratio in self.ratio.items():
            coin_lot[asset] = total_value * (0.995+0.003)*ratio #prevent fail order due to overlapping capital
        cash=r['SpotWallet']['USD']['Free']
        all_assets = set(self.signal.keys()) # assume signal contain all potential coin 
        for asset in all_assets:
            if asset == "USD": continue  
            curr = r['SpotWallet'].get(asset, {}).get("Free", 0.0)
            price = tick['Data'][f"{asset}/USD"]['LastPrice']
            curr=price*curr
            des=self.signal[asset]*coin_lot[asset]
            targ=des-curr
            if abs(targ)>total_value*0.03:
                if des!=0:
                    step=10**(-info['TradePairs'][f"{asset}/USD"]['AmountPrecision']) 
                    qty=np.sign(targ)*max(math.floor(abs((targ)/price)/step)*step,math.ceil(abs(1/price)/step)*step)
                    # print(cash)
                    cash=cash-targ*(1+0.001)
                    print("-------------")
                    print(f"targ: {targ} | curr: {curr}")
                    print(f"{asset}: {qty*price}") 
                    print("-------------")
                    st=self.place_order(coin=asset,side=np.sign(qty),qty=abs(qty))
                    # time.sleep(0.2)
                elif des==0:
                    st=self.clear_all(spec=asset,bal=r)
                if st==200:
                    i+=1
                if i%5==0:
                    time.sleep(1)
            else:
                continue

    def clear_all(self,spec=None,bal=None):
        r= bal if bal is not None else self.get_balance()
        all_assets=set(self.ratio.keys())
        i=1 if bal==None else 0
        if spec==None:
            for asset in all_assets:
                if asset == "USD": continue  
                curr = r['SpotWallet'].get(asset, {}).get("Free", 0.0)
                if curr!=0:
                    self.place_order(coin=asset,side=np.sign(-1),qty=abs(curr))
                    i+=1
                    if i%5==0:
                        time.sleep(1)
        else:
            curr = r['SpotWallet'].get(spec, {}).get("Free", 0.0)
            if curr!=0:
                st=self.place_order(coin=spec,side=np.sign(-1),qty=abs(curr))
                # print('?')
                return st
