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

    def current_candle_date(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)

    def current_candle_hour(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).hour

    def before(self):
        if self.index == 0:
            here = Path(__file__).parent
            # Dynamically determine the right csv from the self.symbol and shift the index 1 day.
            symbol_parts = self.symbol.split("-")
            astro_indicator_path = here / './ml-{}-USD-daily-index.csv'.format(symbol_parts[0])
            self.vars['astro_data'] = pd.read_csv(astro_indicator_path, parse_dates=['Date'], index_col=0)

        # Filter past data.
        candle_date = self.current_candle_date()
        self.vars['astro_data'] = self.vars['astro_data'].loc[candle_date:]

    def increase_entry_attempt(self):
        candle_date = str(datetime.fromtimestamp(self.current_candle[0] / 1000).date())
        # Init date attempts counter.
        if candle_date not in self.vars['attempts']:
            self.vars['attempts'][candle_date] = 0

        # Count the entry attempt.
        self.vars['attempts'][candle_date] += 1

    def are_attempts_exceeded(self) -> bool:
        candle_date = str(datetime.fromtimestamp(self.current_candle[0] / 1000).date())

        if candle_date not in self.vars['attempts']:
            return False

        # Limit to N entry attempt per day.
        if self.vars['attempts'][candle_date] >= self.hp['max_day_attempts']:
            return True

    def should_long(self) -> bool:
        entry_decision = self.astro_signal == "buy" and self.is_bull_start()

        if self.are_attempts_exceeded():
            return False

        if entry_decision:
            self.increase_entry_attempt()

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
        take_profit = self.position_price(price) - (self.daily_atr_average * self.hp['take_profit_atr_rate'])
        return take_profit

    def take_profit_long(self, price=-1):
        take_profit = self.position_price(price) + (self.daily_atr_average * self.hp['take_profit_atr_rate'])
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
        candle_hour = self.current_candle_hour()
        # Use next day signal after 10 hours due the fact that astro models are train with
        # mid price (OHLC / 4) so the price action predicted by next day could start at noon.
        signal_start_index = 0
        if candle_hour >= self.hp['astro_signal_shift_hour']:
            signal_start_index = 1

        # Select next N signals in order to determine that there is astro energy trend.
        signal_end_index = signal_start_index + 1
        signals = self.vars['astro_data'].iloc[signal_start_index:signal_end_index]
        count_signals = len(signals)
        buy_signals = signals[signals['Action'] == 'buy']
        sell_signals = signals[signals['Action'] == 'sell']

        if (count_signals == len(buy_signals)):
            return 'buy'
        elif (count_signals == len(sell_signals)):
            return 'sell'

        return 'neutral'

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
            {'name': 'take_profit_atr_rate', 'type': int, 'min': 2, 'max': 10, 'default': 3},
            {'name': 'atr_period', 'type': int, 'min': 5, 'max': 40, 'default': 30},
            {'name': 'entry_atr_period', 'type': int, 'min': 5, 'max': 20, 'default': 15},
            {'name': 'atr_take_profit_period', 'type': int, 'min': 7, 'max': 21, 'default': 10},
            {'name': 'fast_ma_period', 'type': int, 'min': 20, 'max': 40, 'default': 30},
            {'name': 'slow_ma_period', 'type': int, 'min': 40, 'max': 80, 'default': 60},
            {'name': 'max_day_attempts', 'type': int, 'min': 1, 'max': 3, 'default': 1},
            {'name': 'astro_signal_shift_hour', 'type': int, 'min': 0, 'max': 23, 'default': 8},
        ]
