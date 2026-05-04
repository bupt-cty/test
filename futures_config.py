from dataclasses import dataclass


@dataclass(frozen=True)
class FuturesContractConfig:
    symbol: str
    exchange: str
    contract_multiplier: float
    price_tick: float
    commission_open: float
    commission_today: float
    commission_yesterday: float
    margin_rate: float = 0.0
    commission_mode: str = "rate"
    description: str = ""

    @property
    def tick_value(self):
        return self.price_tick * self.contract_multiplier

    def to_engine_kwargs(self):
        return {
            "contract_symbol": self.symbol,
            "contract_multiplier": self.contract_multiplier,
            "price_tick": self.price_tick,
            "commission_open": self.commission_open,
            "commission_today": self.commission_today,
            "commission_yesterday": self.commission_yesterday,
            "commission_mode": self.commission_mode,
            "margin_rate": self.margin_rate,
        }


# AG: Shanghai Futures Exchange silver futures. Fees are kept configurable
# because exchange and broker rates can change; update these fields for a
# specific paper run if an official fee table is cited.
AG_CONFIG = FuturesContractConfig(
    symbol="AG",
    exchange="SHFE",
    contract_multiplier=15.0,
    price_tick=1.0,
    commission_open=0.0001,
    commission_today=0.0,
    commission_yesterday=0.0001,
    margin_rate=0.12,
    description="SHFE silver futures, 15 kg per lot, 1 yuan/kg tick.",
)
