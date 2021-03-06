from datetime import datetime
from pathlib import Path
from pprint import pprint

import jesse.indicators as ta
import numpy as np
import pandas as pd
from jesse import utils
from jesse.strategies import Strategy


class AstroStrategyMA(Strategy):

    def __init__(self):
        super().__init__()
        self.vars['attempts'] = {}

    def before(self):
        if self.index == 0:
            here = Path(__file__).parent
            # Dynamically determine the right csv from the self.symbol and shift the index 1 day.
            symbol_parts = self.symbol.split("-")
            astro_indicator_path = here / './ml-{}-USD-daily-index.csv'.format(symbol_parts[0])
            df_astro = pd.read_csv(astro_indicator_path, parse_dates=['Date'], index_col=0).tshift(periods=1, freq='D')
            # Slice not needed data
            now = datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)
            df_astro = df_astro.loc[now:]
            # Dynamically determine the timeframe we need to resample those data to.
            self.vars['raw_astro_data'] = df_astro.resample(
                self.timeframe.replace("m", "T").replace("h", "H")
            ).fillna("pad")
            candle_timestamps = pd.DataFrame(index=pd.to_datetime(self.candles[-50:, 0], unit='ms'))
            self.vars['astro_data'] = candle_timestamps.merge(self.vars['raw_astro_data'], how='left', left_index=True, right_index=True)

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
        self.exit_on_reversal()
        self.update_trailing_stop()

    def exit_on_reversal(self):
        if (self.is_long and self.is_bear_start()) or (self.is_short and self.is_bull_start()):
            self.liquidate()

    # Move the SL following the trend.
    def update_trailing_stop(self):
        if self.position.pnl <= 0:
            return

        # Only move it if we are still in a trend
        if (self.is_long and self.price > self.fast_ma[-1]):
            stop = self.price - self.atr * self.hp['trailing_stop_atr_rate']
            if stop < self.price:
                self.stop_loss = self.position.qty, stop

        if (self.is_short and self.price < self.fast_ma[-1]):
            stop = self.price + self.atr * self.hp['trailing_stop_atr_rate']
            if stop > self.price:
                self.stop_loss = self.position.qty, stop

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

    def is_bull_start(self):
        result = utils.crossed(self.fast_ma, self.slow_ma, "above")
        return result

    def is_bear_start(self):
        result = utils.crossed(self.fast_ma, self.slow_ma, "below")
        return result

    @property
    def atr(self):
        return ta.atr(self.candles, period=self.hp['atr_period'])

    @property
    def entry_atr(self):
        return ta.atr(self.candles, period=self.hp['entry_atr_period'])

    @property
    def stop_loss_long(self):
        exit = self.price - self.atr * self.hp['stop_loss_atr_rate']
        if exit >= self.vars['entry']:
            exit = self.vars['entry'] * 0.98
        return exit

    @property
    def stop_loss_short(self):
        exit = self.price + self.atr * self.hp['stop_loss_atr_rate']
        if exit <= self.vars['entry']:
            exit = self.vars['entry'] * 1.02
        return exit

    @property
    def daily_candles(self):
        return self.get_candles(self.exchange, self.symbol, '1D')

    @property
    def daily_atr_average(self):
        daily_atr = ta.atr(self.daily_candles, self.hp['atr_take_profit_period'])
        return daily_atr

    @property
    def fast_ma(self):
        return ta.sma(self.candles, self.hp['fast_ma_period'], "close", True)

    @property
    def slow_ma(self):
        return ta.sma(self.candles, self.hp['slow_ma_period'], "close", True)

    @property
    def astro_signal(self):
        return self.vars['astro_data']['Action'].iloc[-1]

    def position_size(self, entry, stop):
        max_qty = utils.size_to_qty(0.25 * self.capital, entry, precision=6, fee_rate=self.fee_rate)

        return max_qty

    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Genetic
    # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    def hyperparameters(self):
        return [
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.1, 'max': 1.0, 'default': 0.1},
            {'name': 'trailing_stop_atr_rate', 'type': float, 'min': 10, 'max': 20, 'default': 15},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 4, 'default': 2},
            {'name': 'atr_period', 'type': int, 'min': 5, 'max': 40, 'default': 30},
            {'name': 'entry_atr_period', 'type': int, 'min': 5, 'max': 20, 'default': 15},
            {'name': 'fast_ma_period', 'type': int, 'min': 20, 'max': 40, 'default': 30},
            {'name': 'slow_ma_period', 'type': int, 'min': 40, 'max': 80, 'default': 60},
            {'name': 'max_day_attempts', 'type': int, 'min': 1, 'max': 3, 'default': 1},
            {'name': 'atr_take_profit_period', 'type': int, 'min': 7, 'max': 21, 'default': 10},
        ]
