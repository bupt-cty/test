from tick_strategy_base import TickStrategyBase


class CombinedObiMomentumStrategy(TickStrategyBase):
    def __init__(
        self,
        engine,
        momentum_window=90,
        obi_threshold=0.7,
        expected_profit_ticks=8,
        stop_loss_ticks=5,
        max_holding_ticks=300,
        is_ideal=False,
        is_mean_reversion=True,
        entry_threshold=1.5,
        obi_weight=2.0,
        min_depth=1,
        max_spread=2.0,
        spread_multiplier=1.0,
        spread_addition=0.0,
    ):
        super().__init__(
            engine=engine,
            expected_profit_ticks=expected_profit_ticks,
            stop_loss_ticks=stop_loss_ticks,
            max_holding_ticks=max_holding_ticks,
            is_ideal=is_ideal,
            min_depth=min_depth,
            max_spread=max_spread,
            spread_multiplier=spread_multiplier,
            spread_addition=spread_addition,
        )
        self.momentum_window = momentum_window
        self.obi_threshold = obi_threshold
        self.is_mean_reversion = is_mean_reversion
        self.entry_threshold = entry_threshold
        self.obi_weight = obi_weight
        self.price_history = []

    def on_tick(self, tick):
        self.price_history.append(tick["last_price"])
        if len(self.price_history) > self.momentum_window:
            self.price_history.pop(0)

        if len(self.price_history) < self.momentum_window:
            return

        if self._handle_position(tick):
            return

        current_price = tick["last_price"]
        if not self._passes_market_filter(tick, current_price):
            self.pnl_history.append(self.total_pnl)
            return

        momentum = current_price - self.price_history[0]
        obi = self.calculate_obi(tick)
        buy_signal, sell_signal = self._generate_signal(momentum, obi)

        if buy_signal:
            self._open_position(tick, "BUY", 1)
        elif sell_signal:
            self._open_position(tick, "SELL", -1)

        self.pnl_history.append(self.total_pnl)

    def _generate_signal(self, momentum, obi):
        momentum_score = momentum / self.engine.price_tick
        obi_score = self.obi_weight * obi
        signal_score = momentum_score + obi_score

        if abs(obi) < self.obi_threshold:
            return False, False

        if self.is_mean_reversion:
            if signal_score >= self.entry_threshold:
                return False, True
            if signal_score <= -self.entry_threshold:
                return True, False
        else:
            if signal_score >= self.entry_threshold:
                return True, False
            if signal_score <= -self.entry_threshold:
                return False, True

        return False, False


TickMomentumStrategy = CombinedObiMomentumStrategy
