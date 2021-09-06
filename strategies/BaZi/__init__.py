from datetime import datetime, timedelta, date
from pathlib import Path

import ephem
import jesse.indicators as ta
import numpy as np
import pandas as pd
from jesse import utils
from jesse.strategies import Strategy, cached


class BaZi(Strategy):

    def __init__(self):
        super().__init__()

    @property
    def current_candle_date(self) -> datetime:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).replace(hour=0, minute=0, second=0, microsecond=0)

    @property
    def now_candle_date(self) -> datetime:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=2)

    @property
    def current_candle_hour(self) -> int:
        return datetime.fromtimestamp(self.candles[-1, 0] / 1000).hour

    def load_bazi_data(self):
        here = Path(__file__).parent

        # https://en.wikibooks.org/wiki/Ba_Zi/Hsia_Calendar
        bazi_calendar_path = here / './bazi.csv'

        # https://en.wikibooks.org/wiki/Ba_Zi/Earthly_Branches
        bazi_earthly = here / './bazi_earthly_branches.csv'

        # https://en.wikibooks.org/wiki/Ba_Zi/Heavenly_Stems
        bazi_heavenly = here / './bazi_heavenly_stems.csv'

        # https://en.wikibooks.org/wiki/Ba_Zi/Seasonal_Cycle
        bazi_seasons = here / './bazi_seasons.csv'

        # https://en.wikibooks.org/wiki/Ba_Zi/Hour_Pillar
        bazi_hour_pillar = here / './bazi_hour_pillar.csv'

        bazi_iching = here / './bazi_iching.csv'

        # https://www.hko.gov.hk/en/gts/time/stemsandbranches.htm
        bazi_relationship_day_hour_stem = here / './bazi_relationship_day_hour_stem.csv'
        bazi_relationship_year_month_stem = here / './bazi_relationship_year_month_stem.csv'

        # Na Yin http://www.fengshuimestari.fi/Na_Yin.html
        bazi_wuxing_nayin = here / './bazi_wuxing_nayin.csv'

        self.vars['bazi'] = pd.read_csv(bazi_calendar_path, sep=',', parse_dates={'date': ['Year', 'Month', 'Day']},
                                        index_col="date").loc[:self.now_candle_date]
        # self.vars['bazi'].info()

        export = pd.read_csv(bazi_calendar_path, sep=',', parse_dates={'date': ['Year', 'Month', 'Day']},
                             index_col="date").loc[date(year=2019, month=1, day=1):date(year=2022, month=12, day=31)]

        # Todo: Try local solar time / shift hours for europe (or BTC Birthplace) - as Calendar origin in China.
        # See discussion here: https://fivearts.info/fivearts/index.php?topic=13681.0

        self.vars['bazi_earthly'] = pd.read_csv(bazi_earthly, sep=',', index_col="S/N")
        # self.vars['bazi_earthly'].info()

        self.vars['bazi_heavenly'] = pd.read_csv(bazi_heavenly, sep=',', index_col="S/N")
        # self.vars['bazi_heavenly'].info()

        self.vars['bazi_seasons'] = pd.read_csv(bazi_seasons, sep=',', index_col="Numeral")
        # self.vars['bazi_seasons'].info()

        self.vars['bazi_iching'] = pd.read_csv(bazi_iching, sep=';', index_col="H_E")
        # self.vars['bazi_iching'].info()

        self.vars['bazi_relationship_day_hour_stem'] = pd.read_csv(bazi_relationship_day_hour_stem, sep=';',
                                                                   index_col=[0])
        # self.vars['bazi_relationship_day_hour_stem'].info()

        self.vars['bazi_relationship_year_month_stem'] = pd.read_csv(bazi_relationship_year_month_stem, sep=';',
                                                                     index_col=[0])
        # self.vars['bazi_relationship_year_month_stem'].info()

        self.vars['bazi_hour_pillar'] = pd.read_csv(bazi_hour_pillar, sep=';', index_col=[0])
        # self.vars['bazi_hour_pillar'].info()

        self.vars['bazi_wuxing_nayin'] = pd.read_csv(bazi_wuxing_nayin, sep=';', index_col=[0])
        # self.vars['bazi_wuxing_nayin'].info()

        m = self.vars['bazi_earthly']['Yin/Yang'].to_dict()
        m2 = self.vars['bazi_earthly']['Five Elements'].to_dict()
        export['EB of Day'] = export['EB of Day'].replace(m2)
        export.sort_values(by=['date'])
        str = '("' + '","'.join(export['EB of Day']) + '")'

        with open("eb_element.txt", "w") as text_file:
            text_file.write(str)

    def before(self):
        if self.index == 0:
            self.load_bazi_data()

        # Filter past data.
        candle_date = self.current_candle_date
        self.vars['bazi'] = self.vars['bazi'].loc[candle_date:]

    def should_long(self) -> bool:
        return self.is_bull_bazi_signal and self.vmacd > 0

    def should_short(self) -> bool:
        return self.is_bear_bazi_signal and self.vmacd < 0

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

        if self.is_long and self.is_bear_bazi_signal and self.vmacd < 0:
            self.liquidate()

        if self.is_short and self.is_bull_bazi_signal and self.vmacd > 0:
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
            self.capital, 3, entry, stop, precision=6, fee_rate=self.fee_rate
        )


    ################################################################
    # # # # # # # # # # # # # indicators # # # # # # # # # # # # # #
    ################################################################

    @property
    def take_profit_atr(self):
        return ta.atr(self.candles, self.hp['take_profit_atr_period'])

    @property
    def stop_atr(self):
        return ta.atr(self.candles, self.hp['stop_atr_period'])

    @property
    def entry_atr(self):
        return ta.atr(self.candles, self.hp['entry_atr_period'])

    @property
    def dc(self):
        return ta.donchian(self.candles, period=self.hp['stop_dc_period'])

    def bazi_indicator_day_index(self):
        candle_hour = self.current_candle_hour
        # Use next day signal after shift hour due the fact that bazi might work shifted
        # mid price (OHLC / 4) so the price action predicted by next day is lagged.
        day_index = 0
        if candle_hour >= self.hp['bazi_signal_shift_hour']:
            day_index = 1
        return day_index

    def bazi_signal_period_decision(self, bazi_indicator):
        start_index = self.bazi_indicator_day_index()
        # Select next N signals in order to determine that there is bazi energy trend.
        end_index = start_index + self.hp['bazi_signal_trend_period']
        signals = bazi_indicator.iloc[start_index:end_index]
        count_signals = len(signals)

        flying_star_of_year = self.get_flying_star(signals['HS of Year'][start_index])

        elements = []

        # year
        # elements.append(self.get_heavenly_element(signals['HS of Year'][start_index]))
        # elements.append(self.get_earthly_element(signals['EB of Year'][start_index]))

        # month
        # elements.append(self.get_heavenly_element(signals['HS of Month'][start_index]))
        # elements.append(self.get_earthly_element(signals['EB of Month'][start_index]))

        # BTC = metal
        for ind in signals.index:
            # day

            # heaxagram_day = self.get_heaxagram(self.get_heavenly_notation(signals['HS of Day'][ind]), self.get_earthly_notation(signals['HS of Day'][ind]))
            hs = self.get_heavenly_element(signals['HS of Day'][ind])
            eb = self.get_earthly_element(signals['EB of Day'][ind])

            elements.append(hs)
            elements.append(eb)

        # water weakens fire -> good
        # metal good
        # earth amplifies metal -> good
        # wood amplifies fire -> bad
        # fire bad

        metal_count = elements.count("Metal")
        earth_count = elements.count("Earth")
        water_count = elements.count("Water")
        fire_count = elements.count("Fire")
        wood_count = elements.count("Wood")

        score = metal_count + water_count + earth_count - fire_count - wood_count

        if score > 0:
            return 1
        elif score < 0:
            return -1

        return 0

    def get_heavenly_element(self, index_number):
        return self.vars['bazi_heavenly'].loc[self.vars['bazi_heavenly'].index == index_number, 'Five Elements'].item()

    def get_heavenly_yin_yang(self, index_number):
        return self.vars['bazi_heavenly'].loc[self.vars['bazi_heavenly'].index == index_number, 'Yin/Yang'].item()

    def get_earthly_element(self, index_number):
        return self.vars['bazi_earthly'].loc[self.vars['bazi_earthly'].index == index_number, 'Five Elements'].item()

    def get_earthly_yin_yang(self, index_number):
        return self.vars['bazi_earthly'].loc[self.vars['bazi_earthly'].index == index_number, 'Yin/Yang'].item()

    def get_heavenly_notation(self, index_number):
        return self.vars['bazi_heavenly'].loc[self.vars['bazi_heavenly'].index == index_number, 'Notation'].item()

    def get_earthly_notation(self, index_number):
        return self.vars['bazi_earthly'].loc[self.vars['bazi_earthly'].index == index_number, 'Notation'].item()

    def get_heaxagram(self, heavenly_stem, earthly_branch):
        # As there are 64 hexagrams (Gua) and only 60 combinations of Heavenly Stems and Earthly Branches, a one-to-one match is not possible. To obtain a match with the 64 hexagrams, 4 pairs of Heavenly Stems and Earthly Branches are repeated. These four repeated pairs are marked by underlining the "GN" and "Pinyin" values in the above table, namely G1, G27, G31 and G57.
        return self.vars['bazi_iching'].loc[self.vars[
                                                'bazi_iching'].index == f'{heavenly_stem.replace("S", "")}_{earthly_branch.replace("B", "")}', 'Binary'].item()

    def get_flying_star(self, center: int):

        # Center -> Northwest -> West - Northeast -> South -> North -> Southwest -> East -> Southeast

        print(self.flying_star_of_year)
        current_count = center

        for i in range(8):
            current_count += 1
            if current_count == 10:
                current_count = 1
            if i == 0:
                northwest = current_count
            elif i == 1:
                west = current_count
            elif i == 2:
                northeast = current_count
            elif i == 3:
                south = current_count
            elif i == 4:
                north = current_count
            elif i == 5:
                southwest = current_count
            elif i == 6:
                east = current_count
            elif i == 7:
                southeast = current_count

        flying_star_chart = np.array(
            [[southeast, south, southwest],
             [east, center, west],
             [northeast, north, northwest]]
        )

    @property
    @cached
    def candle_stick_to_trigram(self):
        open = self.candles[:, 1]
        close = self.candles[:, 2]
        high = self.candles[:, 3]
        low = self.candles[:, 4]

        bearish = close > open
        bullish = close < open
        # https://de.tradingview.com/script/Cwv7H00X/

        # maybe use talib - as wick size / shadow percentage is important
        if bearish and high == close and low == open:
            # Bullish Marubozu
            # maybe add puffer for equal

            # yin == 1 yang == 0
            trigram = "Earth"
            symbol = [1, 1, 1]
        elif bullish and high == open and low == close:
            # Bearish Marubozu
            # maybe add puffer for equal
            trigram = "Heaven"
            symbol = [0, 0, 0]
        elif bearish and high == close and low < open:
            # Bullish Hammer
            trigram = "Mountain"
            symbol = [0, 1, 1]
        elif bullish and high == open and low < close:
            # Bearish Hammer
            trigram = "Fire"
            symbol = [0, 1, 0]
        elif bearish and low == open and high > close:
            # Bullish Inverted Hammer
            trigram = "Water"
            symbol = [1, 0, 1]
        elif bullish and low == close and high > open:
            # Bearish Inverted Hammer
            trigram = "Lake"
            symbol = [1, 0, 0]
        elif bearish and high > close and low < open:
            # Bullish Spinning Top
            trigram = "Wind"
            symbol = [0, 0, 1]
        elif bullish and high > open and low < close:
            # Bearish Spinning Top
            trigram = "Thunder"
            symbol = [1, 1, 0]

        return self.bazi_signal_period_decision(self.vars['bazi'])

    @property
    @cached
    def bazi_signal(self):
        return self.bazi_signal_period_decision(self.vars['bazi'])

    def solartime(self):
        # Source for birthplace of BTC: https://astralharmony.com/blog/astrology-bitcoin-series-part-two/
        # As discussed in my previous Bitcoin article, I believe that the correct astrological birth chart for Bitcoin should be based on the Satoshi White Paper released on October 31, 2008, which I have rectified to Van Nuys, CA (11:10 AM).
        name = "Van Nuys"
        sun = ephem.Sun()
        observer = ephem.city(name)
        observer.date = '1978/10/3 11:32'
        sun.compute(observer)
        # sidereal time == ra (right ascension) is the highest point (noon)
        hour_angle = observer.sidereal_time() - sun.ra
        return ephem.hours(hour_angle + ephem.hours('12:00')).norm  # norm for 24h

    @property
    def is_bull_bazi_signal(self) -> bool:
        if (self.hp['enable_bazi_signal'] == 1):
            return self.bazi_signal == 1
        return True

    @property
    def is_bear_bazi_signal(self) -> bool:
        if (self.hp['enable_bazi_signal'] == 1):
            return self.bazi_signal == -1
        return True

    @property
    def vmacd(self):
        return ta.vwmacd(self.candles).hist

    @property
    def anchor_candles(self):
        return self.get_candles(self.exchange, self.symbol, utils.anchor_timeframe(self.timeframe))

    def watch_list(self):
        return [
            ('trend_direction', self.trend_direction),
        ]

    ###############################################################
    # # # # # # # # # # # # # filters # # # # # # # # # # # # # # #
    ###############################################################

    def filters(self):
        return [
        ]

    def hyperparameters(self):
        return [
            {'name': 'entry_stop_atr_rate', 'type': float, 'min': 0.02, 'max': 1.5, 'default': 0.3},
            {'name': 'stop_loss_atr_rate', 'type': float, 'min': 1, 'max': 4, 'default': 1.7},
            {'name': 'take_profit_atr_rate', 'type': int, 'min': 1, 'max': 15, 'default': 10},
            {'name': 'entry_atr_period', 'type': int, 'min': 2, 'max': 50, 'default': 28},
            {'name': 'stop_atr_period', 'type': int, 'min': 5, 'max': 50, 'default': 5},
            {'name': 'take_profit_atr_period', 'type': int, 'min': 5, 'max': 50, 'default': 20},
            {'name': 'stop_dc_period', 'type': int, 'min': 10, 'max': 50, 'default': 41},
            # {'name': 'risk', 'type': int, 'min': 1, 'max': 10, 'default': 3},
            {'name': 'bazi_signal_trend_period', 'type': int, 'min': 1, 'max': 5, 'default': 2},
            {'name': 'bazi_signal_shift_hour', 'type': int, 'min': 0, 'max': 23, 'default': 0},
            {'name': 'enable_bazi_signal', 'type': int, 'min': 0, 'max': 1, 'default': 1},
        ]
