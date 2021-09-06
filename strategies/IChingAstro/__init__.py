from datetime import datetime
from pathlib import Path

import jesse.indicators as ta
import numpy as np
import pandas as pd
from jesse import utils
from jesse.strategies import Strategy, cached


class IChingAstro(Strategy):

    def before(self):
        self.prepare_symbol()

        if self.index == 0:
            self.load_astro_data()

            # Filter past data.
        candle_date = self.current_candle_date()
        self.vars['astro_asset'] = self.vars['astro_asset'].loc[candle_date:]

    def should_long(self) -> bool:
        return self.signal == 1 and self.is_bull_astro_signal

    def should_short(self) -> bool:
        return self.signal == 1 and self.is_bear_astro_signal

    def go_long(self):
        entry = self.price + self.entry_atr * self.hp['entry_stop_atr_rate']
        stop = self.stop_loss_long(entry)
        take_profit = self.take_profit_long(entry)
        qty = self.position_size(entry, stop)
        self.buy = qty, entry
        self.take_profit = qty, take_profit
        self.stop_loss = qty, stop

    def go_short(self):
        entry = self.price - self.entry_atr * self.hp['entry_stop_atr_rate']
        # sometimes an extreme ATR value can lead to a negative price
        if entry <= 0:
            entry = self.price
        stop = self.stop_loss_short(entry)
        take_profit = self.take_profit_short(entry)
        qty = self.position_size(entry, stop)
        self.sell = qty, entry
        self.take_profit = qty, take_profit
        self.stop_loss = qty, stop

    def update_position(self):
        if self.is_long and self.signal == -1 and self.is_bear_astro_signal:
            self.liquidate()

        if self.is_short and self.signal == -1 and self.is_bull_astro_signal:
            self.liquidate()

    def should_cancel(self) -> bool:
        return True

    def take_profit_long(self, entry):
        take_profit = entry + self.take_profit_atr * self.hp['take_profit_atr_rate']
        if take_profit <= entry:
            # fallback to donchian channel
            take_profit = self.dc.upperband
        if take_profit <= entry:
            take_profit = entry * 1.1
        return take_profit

    def take_profit_short(self, entry):
        take_profit = entry - self.take_profit_atr * self.hp['take_profit_atr_rate']
        # sometimes an extreme ATR value can lead to a negative price
        if take_profit <= 0 or take_profit >= entry:
            # fallback to donchian channel
            take_profit = self.dc.lowerband
        if take_profit >= entry:
            take_profit = entry * 0.9
        return take_profit

    def stop_loss_long(self, entry):
        exit = entry - self.stop_atr * self.hp['stop_loss_atr_rate']
        # sometimes an extreme ATR value can lead to a negative price
        if exit <= 0 or exit >= entry:
            # fallback to donchian channel
            exit = self.dc.lowerband
        if exit >= entry:
            exit = entry * 0.9
        return exit

    def stop_loss_short(self, entry):
        exit = entry + (self.stop_atr * self.hp['stop_loss_atr_rate'])
        if exit <= entry:
            # fallback to donchian channel
            exit = self.dc.upperband
        if exit <= entry:
            exit = entry * 1.1
        return exit

    def position_size(self, entry, stop):
        return utils.risk_to_qty(
            self.capital,
            self.hp['risk'],
            entry,
            stop,
            precision=6,
            fee_rate=self.fee_rate,
        )


    ################################################################
    # # # # # # # # # # # # # indicators # # # # # # # # # # # # # #
    ################################################################

    def generate_symbol_from_price(self, candles):
        symbol = []
        for candle in candles:
            if self.sum_digits(candle) % 2 == 0:
                # even
                symbol.append(0)
            else:
                # odd
                symbol.append(1)
        return symbol

    def generate_symbol_from_returns(self, candles):
        symbol = []
        for candle in candles:
            if self.sum_digits(candle) % 2 == 0:
                # even
                symbol.append(0)
            else:
                # odd
                symbol.append(1)
        return symbol

    def generate_symbol_from_log_returns(self, candles):
        symbol = []
        for candle in np.log(candles):
            if self.sum_digits(candle) % 2 == 0:
                # even
                symbol.append(0)
            else:
                # odd
                symbol.append(1)
        return symbol

    def generate_symbol_from_color(self, candles):
        symbol = []
        # maybe reverse order reversed(candles)
        for candle in candles:
            open = candle[1]
            close = candle[2]
            high = candle[3]
            low = candle[4]
            if close < open or (close == open and low < high):
                # even / yin
                # green candle
                symbol.append(0)
            else:
                # odd / yang
                # red candle
                symbol.append(1)
        return symbol

    def symbol_name_hexagram(self, symbol):

        # http:#www.jamesfengshui.com/meaning-of-i-ching-64-hexagram/
        # http://the-iching.com/hexagram_1

        yin = np.where(np.array(symbol) == 0, 1, 0)
        yang = np.where(np.array(symbol) == 1, 1, 0)

        # Hexagrams Define
        if yang[0] and yang[1] and yang[2] and yang[3] and yang[4] and yang[5]:
            # 1 Creative
            name = "Creative"
        elif yin[0] and yin[1] and yin[2] and yin[3] and yin[4] and yin[5]:
            # 2 Receptive
            name = "Receptive"
        elif yin[0] and yang[1] and yin[2] and yin[3] and yin[4] and yang[5]:
            # 3 Delifficulty
            name = "Delifficulty"
        elif yang[0] and yin[1] and yin[2] and yin[3] and yang[4] and yin[5]:
            # 4 Folly
            name = "Folly"
        elif yin[0] and yang[1] and yin[2] and yang[3] and yang[4] and yang[5]:
            # 5 Waiting
            name = "Waiting"
        elif yang[0] and yang[1] and yang[2] and yin[3] and yang[4] and yin[5]:
            # 6 Conflict
            name = "Conflict"
        elif yin[0] and yin[1] and yin[2] and yin[3] and yang[4] and yin[5]:
            # 7 Army
            name = " Army"
        elif yin[0] and yang[1] and yin[2] and yin[3] and yin[4] and yin[5]:
            # 8 Union
            name = "Union"
        elif yang[0] and yang[1] and yin[2] and yang[3] and yang[4] and yang[5]:
            # 9 SmallTaming
            name = "SmallTaming"
        elif yang[0] and yang[1] and yang[2] and yin[3] and yang[4] and yang[5]:
            # 10 Treading
            name = "Treading"
        elif yin[0] and yin[1] and yin[2] and yang[3] and yang[4] and yang[5]:
            # 11 Peace
            name = "Peace"
        elif yang[0] and yang[1] and yang[2] and yin[3] and yin[4] and yin[5]:
            # 12 Standstill
            name = "Standstill"
        elif yang[0] and yang[1] and yang[2] and yang[3] and yin[4] and yang[5]:
            # 13 Fellowship
            name = "Fellowship"
        elif yang[0] and yin[1] and yang[2] and yang[3] and yang[4] and yang[5]:
            # 14 possession
            name = "Possesion"
        elif yin[0] and yin[1] and yin[2] and yang[3] and yin[4] and yin[5]:
            # 15 Modesty
            name = "Modesty"
        elif yin[0] and yin[1] and yang[2] and yin[3] and yin[4] and yin[5]:
            # 16 Enthusiasm
            name = "Enthusiasm"
        elif yin[0] and yang[1] and yang[2] and yin[3] and yin[4] and yang[5]:
            # 17 Following
            name = "Following"
        elif yang[0] and yin[1] and yin[2] and yang[3] and yang[4] and yin[5]:
            # 18 Decay
            name = "Decay"
        elif yin[0] and yin[1] and yin[2] and yin[3] and yang[4] and yang[5]:
            # 19 Approach
            name = "Approach"
        elif yang[0] and yang[1] and yin[2] and yin[3] and yin[4] and yin[5]:
            # 20 View
            name = "View"
        elif yang[0] and yin[1] and yang[2] and yin[3] and yin[4] and yang[5]:
            # 21 Biting
            name = "Biting"
        elif yang[0] and yin[1] and yin[2] and yang[3] and yin[4] and yang[5]:
            # 22 Grace
            name = "Grace"
        elif yang[0] and yin[1] and yin[2] and yin[3] and yin[4] and yin[5]:
            # 23 Splitting
            name = "Splitting"
        elif yin[0] and yin[1] and yin[2] and yin[3] and yin[4] and yang[5]:
            # 24 Return
            name = "Return"
        elif yang[0] and yang[1] and yang[2] and yin[3] and yin[4] and yang[5]:
            # 25 Innocence
            name = "Innocence"
        elif yang[0] and yin[1] and yin[2] and yang[3] and yang[4] and yang[5]:
            # 26 GreatTaming
            name = "GreatTaming"
        elif yang[0] and yin[1] and yin[2] and yin[3] and yin[4] and yang[5]:
            # 27 Mouth
            name = "Mouth"
        elif yin[0] and yang[1] and yang[2] and yang[3] and yang[4] and yin[5]:
            # 28 Preponderance
            name = "Preponderance"
        elif yin[0] and yang[1] and yin[2] and yin[3] and yang[4] and yin[5]:
            # 29 Abysmal
            name = "Abysmal"
        elif yang[0] and yin[1] and yang[2] and yang[3] and yin[4] and yang[5]:
            # 30 Clinging
            name = "Clinging"
        elif yin[0] and yang[1] and yang[2] and yang[3] and yin[4] and yin[5]:
            # 31 Influence
            name = "Influence"
        elif yin[0] and yin[1] and yang[2] and yang[3] and yang[4] and yin[5]:
            # 32 Duration
            name = "Duration"
        elif yang[0] and yang[1] and yang[2] and yang[3] and yin[4] and yin[5]:
            # 33 Retreat
            name = "Retreat"
        elif yin[0] and yin[1] and yang[2] and yang[3] and yang[4] and yang[5]:
            # 34 Power
            name = "Power"
        elif yang[0] and yin[1] and yang[2] and yin[3] and yin[4] and yin[5]:
            # 35 Progress
            name = "Progress"
        elif yin[0] and yin[1] and yin[2] and yang[3] and yin[4] and yang[5]:
            # 36 Darkening
            name = "Darkening"
        elif yang[0] and yang[1] and yin[2] and yang[3] and yin[4] and yang[5]:
            # 37 Family
            name = "Family"
        elif yang[0] and yin[1] and yang[2] and yin[3] and yang[4] and yang[5]:
            # 38 Opposition
            name = "Opposition"
        elif yin[0] and yang[1] and yin[2] and yang[3] and yin[4] and yin[5]:
            # 39 Obsturction
            name = "Obsturction"
        elif yin[0] and yin[1] and yang[2] and yin[3] and yang[4] and yin[5]:
            # 40 Deliverance
            name = "Deliverance"
        elif yang[0] and yin[1] and yin[2] and yin[3] and yang[4] and yang[5]:
            # 41 Decrease
            name = "Decrease"
        elif yang[0] and yang[1] and yin[2] and yin[3] and yin[4] and yang[5]:
            # 42 Increase
            name = "Increase"
        elif yin[0] and yang[1] and yang[2] and yang[3] and yang[4] and yang[5]:
            # 43 Resoluteness
            name = "Resoluteness"
        elif yang[0] and yang[1] and yang[2] and yang[3] and yang[4] and yin[5]:
            # 44 Coming
            name = "Coming"
        elif yin[0] and yang[1] and yang[2] and yin[3] and yin[4] and yin[5]:
            # 45 Gathering
            name = "Gathering"
        elif yin[0] and yin[1] and yin[2] and yang[3] and yang[4] and yin[5]:
            # 46 Pushing
            name = "Pushing"
        elif yin[0] and yang[1] and yang[2] and yin[3] and yang[4] and yin[5]:
            # 47 Oppresion
            name = "Oppresion"
        elif yin[0] and yang[1] and yin[2] and yang[3] and yang[4] and yin[5]:
            # 48 Well
            name = "Well"
        elif yin[0] and yang[1] and yang[2] and yang[3] and yin[4] and yang[5]:
            # 49 Revolution
            name = "Revolution"
        elif yang[0] and yin[1] and yang[2] and yang[3] and yang[4] and yin[5]:
            # 50 Cauldron
            name = "Cauldron"
        elif yin[0] and yin[1] and yang[2] and yin[3] and yin[4] and yang[5]:
            # 51 Arousing
            name = "Arousing"
        elif yang[0] and yin[1] and yin[2] and yang[3] and yin[4] and yin[5]:
            # 52 Still
            name = "Still"
        elif yang[0] and yang[1] and yin[2] and yang[3] and yin[4] and yin[5]:
            # 53 Development
            name = "Development"
        elif yin[0] and yin[1] and yang[2] and yin[3] and yang[4] and yang[5]:
            # 54 Marrying
            name = "Marrying"
        elif yin[0] and yin[1] and yang[2] and yang[3] and yin[4] and yang[5]:
            # 55 Abundance
            name = "Abundance"
        elif yang[0] and yin[1] and yang[2] and yang[3] and yin[4] and yin[5]:
            # 56 Wanderer
            name = "Wanderer"
        elif yang[0] and yang[1] and yin[2] and yang[3] and yang[4] and yin[5]:
            # 57 Gentle
            name = "Gentle"
        elif yin[0] and yang[1] and yang[2] and yin[3] and yang[4] and yang[5]:
            # 58 Joyous
            name = "Joyous"
        elif yang[0] and yang[1] and yin[2] and yin[3] and yang[4] and yin[5]:
            # 59 Dispersion
            name = "Dispersion"
        elif yin[0] and yang[1] and yin[2] and yin[3] and yang[4] and yang[5]:
            # 60 Limitation
            name = "Limitation"
        elif yang[0] and yang[1] and yin[2] and yin[3] and yang[4] and yang[5]:
            # 61 Truth
            name = "Truth"
        elif yin[0] and yin[1] and yang[2] and yang[3] and yin[4] and yin[5]:
            # 62 Small
            name = "Small"
        elif yin[0] and yang[1] and yin[2] and yang[3] and yin[4] and yang[5]:
            # 63 After
            name = "After"
        elif yang[0] and yin[1] and yang[2] and yin[3] and yang[4] and yin[5]:
            # 64 Before
            name = "Before"
        else:
            raise ValueError(f"Hexagram not found. Error in binary symbol: {symbol}")

        return name

    def symbol_name_trigram(self, symbol):

        # http://www.jamesfengshui.com/meaning-of-i-ching-64-hexagram/
        # http://the-iching.com/hexagram_1

        yin = np.where(np.array(symbol) == 0, 1, 0)
        yang = np.where(np.array(symbol) == 1, 1, 0)

        # Trigrams Define
        if yang[0] and yang[1] and yang[2]:
            # 1 Heaven
            name = "Heaven"
        elif yin[0] and yin[1] and yin[2]:
            # 2 Earth
            name = "Earth"
        elif yin[0] and yin[1] and yang[2]:
            # 3 Thunder
            name = "Thunder"
        elif yin[0] and yang[1] and yin[2]:
            # 4 Water
            name = "Water"
        elif yang[0] and yin[1] and yin[2]:
            # 5 Mountain
            name = "Mountain"
        elif yang[0] and yang[1] and yin[2]:
            # 6 Wind
            name = "Wind"
        elif yang[0] and yin[1] and yang[2]:
            # 7 Fire
            name = "Fire"
        elif yin[0] and yang[1] and yang[2]:
            # 8 Lake
            name = "Lake"
        else:
            raise ValueError(f"Trigram not found. Error in binary symbol: {symbol}")

        return name

    def symbol_name_bigram(self, symbol):

        # http://www.jamesfengshui.com/meaning-of-i-ching-64-hexagram/
        # http://the-iching.com/hexagram_1

        yin = np.where(np.array(symbol) == 0, 1, 0)
        yang = np.where(np.array(symbol) == 1, 1, 0)

        # Bigram Define
        if yang[0] and yang[1]:
            # 1 Summer
            name = "Summer"
        elif yin[0] and yang[1]:
            # 2 Spring
            name = "Spring"
        elif yang[0] and yin[1]:
            # 3 Fall
            name = "Fall"
        elif yin[0] and yin[1]:
            # 4 Winter
            name = "Winter"
        else:
            raise ValueError(f"Bigram not found. Error in binary symbol: {symbol}")

        return name

    @property
    def yin_or_yang_trigram(self):
        name = self.symbol_name_trigram(self.vars['trigram'])
        if name in ["Heaven", "Lake", "Fire", "Thunder"]:
            return -1
        elif name in ["Wind", "Water", "Mountain", "Earth"]:
            return 1
        else:
            raise ValueError(f"Yin Yang not determined for {name}.")

    @property
    def yin_or_yang_bigram(self):
        name = self.symbol_name_bigram(self.vars['bigram'])
        if name in ["Summer", "Spring"]:
            return -1
        elif name in ["Fall", "Winter"]:
            return 1
        else:
            raise ValueError(f"Yin Yang not determined for {name}.")


    @property
    def signal(self):
        if self.yin_or_yang_trigram == 1 or self.yin_or_yang_bigram == 1:
            return 1
        elif self.yin_or_yang_trigram == -1 or self.yin_or_yang_bigram == -1:
            return -1
        return 0

    def generate_symbol(self, candles):
        # also try returns (percentage) / log (returns)
        if self.hp['symbol_method'] == 0:
            return self.generate_symbol_from_color(candles)
        elif self.hp['symbol_method'] == 1:
            return self.generate_symbol_from_returns(candles)
        elif self.hp['symbol_method'] == 2:
            return self.generate_symbol_from_log_returns(candles)
        elif self.hp['symbol_method'] == 3:
            return self.generate_symbol_from_price(candles)

    def prepare_symbol(self):
        candles = self.candles
        if self.hp['symbol_method'] in [1, 2]:
            candles = utils.prices_to_returns(self.candles[:, 2])
        elif self.hp['symbol_method'] == 3:
            candles = self.candles[:, 2]

        hexagram = self.generate_symbol(candles[-6:])
        trigram = self.generate_symbol(candles[-3:])
        bigram = self.generate_symbol(candles[-2:])

        self.vars['hexagram'] = hexagram
        self.vars['trigram'] = trigram
        self.vars['bigram'] = bigram

    def current_candle_date(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)

    def current_candle_hour(self) -> int:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).hour

    def load_astro_data(self):
        here = Path(__file__).parent
        # Dynamically determine the right csv from the self.symbol and shift the index 1 day.
        symbol_parts = self.symbol.split('-')
        astro_asset_indicator_path = here / './ml-{}-USD-daily-index.csv'.format(symbol_parts[0])
        self.vars['astro_asset'] = pd.read_csv(astro_asset_indicator_path, parse_dates=['Date'], index_col=0)

    def astro_indicator_day_index(self):
        candle_hour = self.current_candle_hour()
        # Use next day signal after shift hour due the fact that astro models are train with
        # mid price (OHLC / 4) so the price action predicted by next day is lagged.
        day_index = 0
        if candle_hour >= self.hp['astro_signal_shift_hour']:
            day_index = 1
        return day_index

    def astro_signal_period_decision(self, astro_indicator):
        start_index = self.astro_indicator_day_index()
        # Select next N signals in order to determine that there is astro energy trend.
        end_index = start_index + self.hp['astro_signal_trend_period']
        signals = astro_indicator.iloc[start_index:end_index]
        count_signals = len(signals)
        buy_signals = signals[signals['Action'] == 'buy']
        sell_signals = signals[signals['Action'] == 'sell']

        if (count_signals == len(buy_signals)):
            return 'buy'
        elif (count_signals == len(sell_signals)):
            return 'sell'

        return 'neutral'

    @property
    def astro_asset_signal(self):
        return self.astro_signal_period_decision(self.vars['astro_asset'])

    @property
    def is_bull_astro_signal(self) -> bool:
        if (self.hp['enable_astro_signal'] == 1):
            return self.astro_asset_signal == 'buy'
        return True

    @property
    def is_bear_astro_signal(self) -> bool:
        if (self.hp['enable_astro_signal'] == 1):
            return self.astro_asset_signal == 'sell'
        return True

    @property
    def anchor_candles(self):
        return self.get_candles(self.exchange, self.symbol, "1D")

    @property
    @cached
    def take_profit_atr(self):
        return ta.atr(self.candles, self.hp['take_profit_atr_period'])

    @property
    @cached
    def stop_atr(self):
        return ta.atr(self.candles, self.hp['stop_atr_period'])

    @property
    @cached
    def entry_atr(self):
        return ta.atr(self.candles, self.hp['entry_atr_period'])

    @property
    @cached
    def dc(self):
        return ta.donchian(self.candles, period=self.hp['stop_dc_period'])

    def sum_digits(self, integ):
        if integ == np.nan:
            return np.nan
        integ = int(integ)
        if integ <= 9:
            return integ
        res = sum(divmod(integ, 10))
        return self.sum_digits(res)

    ###############################################################
    # # # # # # # # # # # # # filters # # # # # # # # # # # # # # #
    ###############################################################

    def filters(self):
        return []

    def hyperparameters(self):
        return [
            {'name': 'entry_atr_period', 'type': int, 'min': 10, 'max': 50, 'default': 38},
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.1, 'max': 1.0, 'default': 0.168354},
            {'name': 'stop_atr_period', 'type': int, 'min': 10, 'max': 50, 'default': 28},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 5, 'default': 4.74684},
            {'name': 'trailing_stop_atr_rate', 'type': float, 'min': 1, 'max': 20, 'default': 14.4684},
            {'name': 'take_profit_atr_period', 'type': int, 'min': 10, 'max': 50, 'default': 32},
            {'name': 'take_profit_atr_rate', 'type': int, 'min': 2, 'max': 10, 'default': 2},
            {'name': 'max_day_attempts', 'type': int, 'min': 1, 'max': 5, 'default': 4},
            {'name': 'astro_signal_trend_period', 'type': int, 'min': 1, 'max': 5, 'default': 2},
            {'name': 'astro_signal_shift_hour', 'type': int, 'min': 0, 'max': 23, 'default': 4},
            {'name': 'enable_astro_signal', 'type': int, 'min': 0, 'max': 1, 'default': 1},
            {'name': 'symbol_method', 'type': int, min: 0, max: 1, 'default': 0},
        ]
