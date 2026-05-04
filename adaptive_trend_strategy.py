from collections import deque

from tick_strategy_base import TickStrategyBase


class AdaptiveTrendStrategy(TickStrategyBase):
    def __init__(
        self,
        engine,
        fast_window=600,
        slow_window=3600,
        entry_threshold=6.0,
        exit_threshold=1.0,
        expected_profit_ticks=80,
        stop_loss_ticks=30,
        trailing_start_ticks=30,
        trailing_stop_ticks=18,
        max_holding_ticks=20000,
        cooldown_ticks=300,
        min_tick_volume=1,
        obi_threshold=0.0,
        obi_weight=0.0,
        trade_direction="both",
        is_ideal=False,
        min_depth=5,
        max_spread=8.0,
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
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.trailing_start_ticks = trailing_start_ticks
        self.trailing_stop_ticks = trailing_stop_ticks
        self.cooldown_ticks = cooldown_ticks
        self.min_tick_volume = min_tick_volume
        self.obi_threshold = obi_threshold
        self.obi_weight = obi_weight
        self.trade_direction = trade_direction

        self.fast_prices = deque()
        self.slow_prices = deque()
        self.fast_sum = 0.0
        self.slow_sum = 0.0
        self.cooldown_left = 0
        self.best_price = None
        self.last_signal_score = 0.0

    def on_tick(self, tick):
        current_price = tick["last_price"]
        self._update_windows(current_price)

        if len(self.slow_prices) < self.slow_window:
            return

        signal_score = self._signal_score(tick)
        self.last_signal_score = signal_score

        if self.current_position != 0:
            self._handle_adaptive_position(tick, signal_score)
            self.pnl_history.append(self.total_pnl)
            return

        if self.cooldown_left > 0:
            self.cooldown_left -= 1
            self.pnl_history.append(self.total_pnl)
            return

        if not self._passes_market_filter(tick, current_price):
            self.pnl_history.append(self.total_pnl)
            return

        if tick.get("tick_volume", 1) < self.min_tick_volume:
            self.pnl_history.append(self.total_pnl)
            return

        obi = self.calculate_obi(tick)
        if self.obi_threshold > 0 and abs(obi) < self.obi_threshold:
            self.pnl_history.append(self.total_pnl)
            return

        if signal_score >= self.entry_threshold and self.trade_direction in ("both", "long"):
            self._open_adaptive_position(tick, "BUY", 1)
        elif signal_score <= -self.entry_threshold and self.trade_direction in ("both", "short"):
            self._open_adaptive_position(tick, "SELL", -1)

        self.pnl_history.append(self.total_pnl)

    def _update_windows(self, price):
        self.fast_prices.append(price)
        self.fast_sum += price
        if len(self.fast_prices) > self.fast_window:
            self.fast_sum -= self.fast_prices.popleft()

        self.slow_prices.append(price)
        self.slow_sum += price
        if len(self.slow_prices) > self.slow_window:
            self.slow_sum -= self.slow_prices.popleft()

    def _signal_score(self, tick):
        fast_ma = self.fast_sum / len(self.fast_prices)
        slow_ma = self.slow_sum / len(self.slow_prices)
        trend_ticks = (fast_ma - slow_ma) / self.engine.price_tick
        obi = self.calculate_obi(tick)
        return trend_ticks + self.obi_weight * obi

    def _open_adaptive_position(self, tick, action, position):
        self._open_position(tick, action, position)
        if self.current_position != 0:
            self.best_price = self.entry_price

    def _handle_adaptive_position(self, tick, signal_score):
        self.ticks_held += 1
        current_price = tick["last_price"]
        close_reason = None

        if self.current_position == 1:
            self.best_price = max(self.best_price, current_price)
            favorable_ticks = (self.best_price - self.entry_price) / self.engine.price_tick
            drawdown_from_best = (self.best_price - current_price) / self.engine.price_tick
            open_profit_ticks = (current_price - self.entry_price) / self.engine.price_tick

            if open_profit_ticks >= self.expected_profit_ticks:
                close_reason = "take_profit"
            elif open_profit_ticks <= -self.stop_loss_ticks:
                close_reason = "stop_loss"
            elif favorable_ticks >= self.trailing_start_ticks and drawdown_from_best >= self.trailing_stop_ticks:
                close_reason = "trailing_stop"
            elif signal_score <= -self.exit_threshold:
                close_reason = "signal_reversal"
        else:
            self.best_price = min(self.best_price, current_price)
            favorable_ticks = (self.entry_price - self.best_price) / self.engine.price_tick
            drawdown_from_best = (current_price - self.best_price) / self.engine.price_tick
            open_profit_ticks = (self.entry_price - current_price) / self.engine.price_tick

            if open_profit_ticks >= self.expected_profit_ticks:
                close_reason = "take_profit"
            elif open_profit_ticks <= -self.stop_loss_ticks:
                close_reason = "stop_loss"
            elif favorable_ticks >= self.trailing_start_ticks and drawdown_from_best >= self.trailing_stop_ticks:
                close_reason = "trailing_stop"
            elif signal_score >= self.exit_threshold:
                close_reason = "signal_reversal"

        if close_reason is None and self.ticks_held >= self.max_holding_ticks:
            close_reason = "timeout"

        if close_reason:
            action = "SELL" if self.current_position == 1 else "BUY"
            success, result = self.engine.match_order(action, 1)
            if success:
                self._close_position(tick, result, close_reason)
                self.cooldown_left = self.cooldown_ticks
                self.best_price = None
