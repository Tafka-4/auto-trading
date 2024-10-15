import pandas as pd
import numpy as np
import logging
import time
from binance.client import Client
from binance.enums import *
from datetime import datetime

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s',
                    handlers=[
                        logging.FileHandler('rsi_trading.log'),
                        logging.StreamHandler()
                    ])

API_KEY = ''
API_SECRET = ''

client = Client(API_KEY, API_SECRET)

client.API_URL = 'https://testnet.binance.vision/api'

symbol = 'BTCUSDT'
in_position = False
entry_price = None

trade_history = []

RSI_PERIOD = 14

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def place_order(order_type, quantity):
    try:
        if order_type == 'buy':
            logging.info("매수 주문 실행")
            order = client.create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logging.info(order)
        elif order_type == 'sell':
            logging.info("매도 주문 실행")
            order = client.create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logging.info(order)
        return order
    except Exception as e:
        logging.error(f"주문 실패: {e}")
        return None

def get_current_price():
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        logging.error(f"가격 가져오기 실패: {e}")
        return None

def run_bot():
    global in_position, entry_price

    while True:
        try:
            klines = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_15MINUTE, limit=100)
            data = pd.DataFrame(klines, columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'Close time', 'Quote asset volume', 'Number of trades',
                'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
            ])
            data['Close'] = data['Close'].astype(float)
            data['Close time'] = pd.to_datetime(data['Close time'], unit='ms')

            rsi = calculate_rsi(data['Close'], RSI_PERIOD).iloc[-1]
            logging.info(f"현재 RSI: {rsi:.2f}")

            current_price = get_current_price()
            if current_price is None:
                time.sleep(60)
                continue

            usdt_balance = float(client.get_asset_balance(asset='USDT')['free'])
            btc_balance = float(client.get_asset_balance(asset='BTC')['free'])

            if rsi < RSI_OVERSOLD and not in_position:
                quantity = (usdt_balance * 0.99) / current_price  
                quantity = float('{:.6f}'.format(quantity))
                if quantity > 0:
                    order = place_order('buy', quantity)
                    if order:
                        in_position = True
                        entry_price = current_price
                        logging.info(f"매수 주문 완료: 가격={current_price}, 수량={quantity}")
                else:
                    logging.info("매수 실패: USDT 잔고 부족")

            elif rsi > RSI_OVERBOUGHT and in_position:
                quantity = btc_balance * 0.99 
                quantity = float('{:.6f}'.format(quantity))
                if quantity > 0:
                    order = place_order('sell', quantity)
                    if order:
                        in_position = False
                        logging.info(f"매도 주문 완료: 가격={current_price}, 수량={quantity}")
                else:
                    logging.info("매도 실패: BTC 잔고 부족")

            time.sleep(900) 
        except Exception as e:
            logging.error(f"에러 발생: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("RSI 기반 실시간 거래 봇 시작")
    run_bot()
