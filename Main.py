import logging.config
import math
import time
from configparser import ConfigParser

from huobi import HuobiServices

import pandas as pd


def truncate(number, digits) -> float:
    stepper = pow(10.0, digits)
    return math.trunc(stepper * number) / stepper


# 日志对象
logging.config.fileConfig('logging.conf')

logger = logging.getLogger('main')

parser = ConfigParser()
parser.read("system_config.conf")
confDict = {section: dict(parser.items(section)) for section in parser.sections()}

baseCurrency = confDict["coin_trading"]["base_currency"]
quoteCurrency = confDict["coin_trading"]["quote_currency"]
minimalPrice = float(confDict["coin_trading"]["minimal_price"])
maximumPrice = float(confDict["coin_trading"]["maximum_price"])
sleepTime = float(confDict["coin_trading"]["sleep_time"])

# 获取交易对信息
symbols = None

while(symbols is None):
    symbols = HuobiServices.get_symbols()
    logger.info('sleep %s second' % sleepTime)
    time.sleep(sleepTime)

symbolsDF = pd.DataFrame(HuobiServices.get_symbols()["data"])
symbolsDict = symbolsDF.loc[
    (symbolsDF["base-currency"] == baseCurrency) & (symbolsDF["quote-currency"] == quoteCurrency)].set_index(
    "base-currency").to_dict()

baseCurrencyAmountPrecision = symbolsDict["amount-precision"][baseCurrency]

while (True):

    # 获取账户余额
    balance = HuobiServices.get_balance()
    if balance is None:
        continue

    currencyList = balance["data"]["list"]
    df = pd.DataFrame(currencyList)

    balanceDict = df.loc[(df["currency"].isin([baseCurrency, quoteCurrency])) & (df["type"] == "trade")].set_index(
        'currency').to_dict()[
        "balance"]

    baseCurrencyBalance = truncate(float(balanceDict[baseCurrency]), baseCurrencyAmountPrecision)

    logger.info('latest balance %s ' % balanceDict)

    # 获取火币的最新价格
    huobiLatestPrice = HuobiServices.get_latest_price(baseCurrency + quoteCurrency)
    if huobiLatestPrice is None:
        continue
    logger.info('latest price %s ' % huobiLatestPrice)

    if huobiLatestPrice["price"] < minimalPrice and baseCurrencyBalance <= 0.0:
        logger.info('buy at price %s ' % huobiLatestPrice["price"])
        buyAmount = round(huobiLatestPrice["price"] * 10, baseCurrencyAmountPrecision)
        logger.info('buy amount %s ' % buyAmount)
        buyResponse = HuobiServices.send_order(buyAmount, "api", baseCurrency + quoteCurrency, "buy-market")

        if buyResponse["status"] == "error":
            logger.info('buy fail with error message %s ' % buyResponse["err-msg"])
        else:
            logger.info("buy success")

    if baseCurrencyBalance > 0.0 and huobiLatestPrice["price"] > maximumPrice:
        logger.info('sell at price %s ' % huobiLatestPrice["price"])
        logger.info('sell amount %s ' % baseCurrencyBalance)
        sellResponse = HuobiServices.send_order(baseCurrencyBalance, "api", baseCurrency + quoteCurrency, "sell-market")
        if sellResponse["status"] == "error":
            logger.info('sell fail with error message %s ' % sellResponse["err-msg"])
        else:
            logger.info("sell success")

    logger.info('sleep %s second' % sleepTime)
    time.sleep(sleepTime)
