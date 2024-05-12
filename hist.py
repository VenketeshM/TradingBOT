import yfinance as yf
import numpy as np
import pandas as pd
import ta
import ta.momentum
import ta.trend
from time import sleep
import logging
from binance.um_futures import UMFutures
from binance.error import ClientError
from keys import key, secret

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
TP = 0.3  # Take profit percentage
SL = 0.1  # Stop loss percentage
VOLUME = 10  # Volume for one order
LEVERAGE = 10  # Leverage
MARGIN_TYPE = 'ISOLATED'  # Margin type ('ISOLATED' or 'CROSS')
QTY = 100  # Amount of concurrent opened positions

# Initialize Binance client
client = UMFutures(key=key, secret=secret)

# Function to get candles for the needed symbol
def fetch_klines(symbol, interval='15m'):
    try:
        resp = pd.DataFrame(client.klines(symbol, interval))
        resp = resp.iloc[:,:6]
        resp.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
        resp = resp.set_index('Time')
        resp.index = pd.to_datetime(resp.index, unit='ms')
        resp = resp.astype(float)
        return resp
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)
        return None

# Function to get balance in USDT
def get_balance_usdt():
    try:
        response = client.balance(recvWindow=6000)
        for elem in response:
            if elem['asset'] == 'USDT':
                return float(elem['balance'])
        raise ValueError("USDT balance not found in response.")
    except (ClientError, ValueError) as e:
        logging.error("Error:", exc_info=True)
        return None

# Function to set leverage for the needed symbol
def set_leverage(symbol, level):
    try:
        response = client.change_leverage(symbol=symbol, leverage=level, recvWindow=6000)
        logging.info(response)
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)

# Function to set margin type for the needed symbol
def set_margin_type(symbol, type):
    try:
        response = client.change_margin_type(symbol=symbol, marginType=type, recvWindow=6000)
        logging.info(response)
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)

# Function to open new order with the last price, and set TP and SL
def open_order(symbol, side):
    price = float(client.ticker_price(symbol)['price'])
    if symbol != 'BTCUSDT':
        logging.warning("Trading is limited to BTCUSDT only.")
        return

    qty = VOLUME / price
    try:
        if side == 'buy':
            resp1 = client.new_order(symbol=symbol, side='BUY', type='MARKET', quantity=qty)
        elif side == 'sell':
            resp1 = client.new_order(symbol=symbol, side='SELL', type='MARKET', quantity=qty)
        logging.info(f"{symbol} {side} placing order: {resp1}")
        sleep(2)
        sl_price = round(price - price * SL, 2) if side == 'buy' else round(price + price * SL, 2)
        resp2 = client.new_order(symbol=symbol, side='SELL' if side == 'buy' else 'BUY',
                                 type='STOP_MARKET', quantity=qty, stopPrice=sl_price)
        logging.info(f"Stop loss order: {resp2}")
        sleep(2)
        tp_price = round(price + price * TP, 2) if side == 'buy' else round(price - price * TP, 2)
        resp3 = client.new_order(symbol=symbol, side='SELL' if side == 'buy' else 'BUY',
                                 type='TAKE_PROFIT_MARKET', quantity=qty, stopPrice=tp_price)
        logging.info(f"Take profit order: {resp3}")
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)

# Function to get current positions
def get_positions():
    try:
        response = client.get_position_risk()
        positions = [elem['symbol'] for elem in response if float(elem['positionAmt']) != 0]
        return positions
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)
        return []

# Function to check open orders
def check_orders():
    try:
        response = client.get_orders(recvWindow=6000)
        orders = [elem['symbol'] for elem in response]
        return orders
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)
        return []

# Function to close open orders for the needed symbol
def close_open_orders(symbol):
    try:
        response = client.cancel_open_orders(symbol=symbol, recvWindow=6000)
        logging.info(response)
    except ClientError as ce:
        logging.error("Binance API error:", exc_info=True)

# Strategy function to determine trading signals
def get_signal(symbol):
    klines = fetch_klines(symbol)
    if klines is None:
        logging.warning(f"Failed to fetch klines for {symbol}")
        return 'none'

    rsi = ta.momentum.RSIIndicator(klines['Close']).rsi()
    rsi_k = ta.momentum.StochRSIIndicator(klines['Close']).stochrsi_k()
    rsi_d = ta.momentum.StochRSIIndicator(klines['Close']).stochrsi_d()
    ema = ta.trend.ema_indicator(klines['Close'], window=200)

    if (rsi.iloc[-1] < 40 and ema.iloc[-1] < klines['Close'].iloc[-1] and
        rsi_k.iloc[-1] < 20 and rsi_k.iloc[-3] < rsi_d.iloc[-3] and
        rsi_k.iloc[-2] < rsi_d.iloc[-2] and rsi_k.iloc[-1] > rsi_d.iloc[-1]):
        return 'up'
    elif (rsi.iloc[-1] > 60 and ema.iloc[-1] > klines['Close'].iloc[-1] and
        rsi_k.iloc[-1] > 80 and rsi_k.iloc[-3] > rsi_d.iloc[-3] and
        rsi_k.iloc[-2] > rsi_d.iloc[-2] and rsi_k.iloc[-1] < rsi_d.iloc[-1]):
        return 'down'
    else:
        return 'none'

# Main trading loop
def main():
    symbol = input("Enter the symbol you want to trade (e.g., BTCUSDT): ").upper()

    while True:
        balance = get_balance_usdt()
        sleep(1)
        if balance is None:
            logging.warning('Cannot connect to API. Check IP, restrictions, or wait some time')
        else:
            logging.info(f"My balance is: {balance} USDT")
            positions = get_positions()
            logging.info(f'You have {len(positions)} opened positions: {positions}')
            orders = check_orders()
            logging.info(f'Open orders: {orders}')
            for order in orders:
                if order not in positions:
                    close_open_orders(order)
            if len(positions) < QTY:
                signal = get_signal(symbol)
                if signal == 'up' and symbol not in positions:
                    logging.info(f'Found BUY signal for {symbol}')
                    set_margin_type(symbol, MARGIN_TYPE)
                    sleep(1)
                    set_leverage(symbol, LEVERAGE)
                    sleep(1)
                    logging.info(f'Placing order for {symbol}')
                    open_order(symbol, 'buy')
                    sleep(10)
                elif signal == 'down' and symbol not in positions:
                    logging.info(f'Found SELL signal for {symbol}')
                    set_margin_type(symbol, MARGIN_TYPE)
                    sleep(1)
                    set_leverage(symbol, LEVERAGE)
                    sleep(1)
                    logging.info(f'Placing order for {symbol}')
                    open_order(symbol, 'sell')
                    sleep(10)
        logging.info('Waiting 3 min')
        sleep(180)

# Call the main function to start the trading bot
if __name__ == "__main__":
    main()
