from datetime import datetime
from pathlib import Path
from pprint import pprint

import jesse.indicators as ta
import numpy as np
from jesse import utils
from jesse.strategies import Strategy


class AstroStrategyMA(Strategy):

    def __init__(self):
        super().__init__()

        here = Path(__file__).parent

        self.vars['astro_data'] = np.genfromtxt(here / './ml-BTC-USD-daily-index.csv', dtype=None, delimiter=",",
                                                names=True,
                                                encoding='UTF-8',
                                                converters={0: lambda s: datetime.strptime(s, "%Y-%m-%d")})

        self.vars['attempts'] = {}
        # print(self.vars['astro_data'])

    def should_long(self) -> bool:
        entry_decision = self.astro_signal == "buy" and self.is_bull_start()
        candle_date = str(datetime.fromtimestamp(self.current_candle[0] / 1000).date())

        # Init date attempts counter.
        if candle_date not in self.vars['attempts']:
            self.vars['attempts'][candle_date] = 0

        # Limit to N entry attempt per day.
        if self.vars['attempts'][candle_date] >= self.hp['max_day_attempts']:
            return False

        # Count the entry attempt.
        if entry_decision:
            self.vars['attempts'][candle_date] += 1

        return entry_decision

    def should_short(self) -> bool:
        return False

    def filters(self):
        # candle_date = datetime.fromtimestamp(self.current_candle[0] / 1000)
        return []

    def go_long(self):
        entry = self.price + self.entry_atr * self.hp['entry_stop_atr_rate']
        self.vars['entry'] = entry
        stop = self.stop_loss_long
        position_size = self.position_size(entry, stop)
        self.buy = position_size, entry
        self.stop_loss = position_size, stop
        take_profit = self.take_profit_long(entry)
        self.take_profit = position_size, take_profit

    def go_short(self):
        entry = self.price - self.entry_atr * self.hp['entry_stop_atr_rate']
        self.vars['entry'] = entry
        stop = self.stop_loss_short
        position_size = self.position_size(entry, stop)
        take_profit = self.take_profit_short(entry)
        self.sell = position_size, entry
        self.stop_loss = position_size, stop
        self.take_profit = position_size, take_profit

    def should_cancel(self) -> bool:
        return False

    def update_position(self):
        if (self.is_long and self.is_bear_start()) or (self.is_short and self.is_bull_start()):
            self.liquidate()

    ################################################################
    # # # # # # # # # # # # # indicators # # # # # # # # # # # # # #
    ################################################################

    def position_price(self, price = -1):
        if price == -1:
            price = self.price

        return price

    def take_profit_short(self, price=-1):
        take_profit = self.position_price(price) - (self.daily_atr_average * 2)
        return take_profit

    def take_profit_long(self, price=-1):
        take_profit = self.position_price(price) + (self.daily_atr_average * 2)
        return take_profit

    @property
    def atr(self):
        return ta.atr(self.candles, period=self.hp['atr_period'])

    @property
    def entry_atr(self):
        return ta.atr(self.candles, period=self.hp['entry_atr_period'])

    @property
    def stop_loss_long(self):
        exit = self.price - self.atr * self.hp['stop_loss_atr_rate']
        if exit <= self.vars['entry']:
            exit = self.vars['entry'] * 0.98
        return exit

    @property
    def daily_candles(self):
        return self.get_candles(self.exchange, self.symbol, '1D')

    @property
    def daily_atr_average(self):
        daily_atr = ta.atr(self.daily_candles, self.hp['atr_take_profit_period'])
        return daily_atr

    @property
    def stop_loss_short(self):
        exit = self.price + self.atr * self.hp['stop_loss_atr_rate']
        if exit <= self.vars['entry']:
            exit = self.vars['entry'] * 1.02
        return exit

    def is_bull_start(self):
        fast_ma = ta.sma(self.candles, self.hp['fast_ma_period'], "close", True)
        slow_ma = ta.sma(self.candles, self.hp['slow_ma_period'], "close", True)
        result = utils.crossed(fast_ma, slow_ma, "above")
        return result

    def is_bear_start(self):
        fast_ma = ta.sma(self.candles, self.hp['fast_ma_period'], "close", True)
        slow_ma = ta.sma(self.candles, self.hp['slow_ma_period'], "close", True)
        result = utils.crossed(fast_ma, slow_ma, "below")
        return result

    @property
    def astro_signal(self):
        now = datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)
        # print(now)
        signal_idx = np.where(self.vars['astro_data']['Date'] == now)[0] + 1
        # print(self.vars['astro_data']['Date'][signal_idx])
        return self.vars['astro_data']['Action'][signal_idx]

    def position_size(self, entry, stop):
        max_qty = utils.size_to_qty(0.25 * self.capital, entry, precision=6, fee_rate=self.fee_rate)

        return max_qty

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Genetic
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def hyperparameters(self):
        return [
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.1, 'max': 1.0, 'default': 0.1},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 4, 'default': 2},
            {'name': 'take_profit', 'type': int, 'min': 1, 'max': 20, 'default': 5},
            {'name': 'atr_period', 'type': int, 'min': 5, 'max': 40, 'default': 30},
            {'name': 'entry_atr_period', 'type': int, 'min': 5, 'max': 40, 'default': 15},
            {'name': 'fast_ma_period', 'type': int, 'min': 20, 'max': 40, 'default': 30},
            {'name': 'slow_ma_period', 'type': int, 'min': 40, 'max': 80, 'default': 60},
            {'name': 'max_day_attempts', 'type': int, 'min': 1, 'max': 3, 'default': 1},
            {'name': 'atr_take_profit_period', 'type': int, 'min': 7, 'max': 21, 'default': 10},
        ]
