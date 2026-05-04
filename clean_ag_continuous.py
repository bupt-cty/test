import argparse
from pathlib import Path

import pandas as pd


SESSION_STARTS = [
    ("09:00:00", "10:15:00"),
    ("10:30:00", "11:30:00"),
    ("13:30:00", "15:00:00"),
    ("21:00:00", "23:59:59"),
    ("00:00:00", "02:30:00"),
]


def is_trading_time(dt):
    t = dt.time()
    for start, end in SESSION_STARTS:
        if pd.Timestamp(start).time() <= t <= pd.Timestamp(end).time():
            return True
    return False


def build_datetime(df):
    trade_date = pd.to_datetime(df["TradingDay"].astype(str), format="%Y%m%d", errors="coerce")
    update_time = pd.to_datetime(df["UpdateTime"].astype(str), format="%H:%M:%S", errors="coerce").dt.time
    night_mask = update_time >= pd.Timestamp("21:00:00").time()
    calendar_date = trade_date.where(~night_mask, trade_date - pd.Timedelta(days=1))
    date_str = calendar_date.dt.strftime("%Y%m%d")
    time_str = df["UpdateTime"].astype(str)
    ms_str = df["UpdateMillisec"].fillna(0).astype(int).astype(str).str.zfill(3)
    return pd.to_datetime(date_str + " " + time_str + "." + ms_str, errors="coerce")


def clean_one_file(path):
    df = pd.read_csv(path)
    required = [
        "TradingDay",
        "InstrumentID",
        "UpdateTime",
        "UpdateMillisec",
        "LastPrice",
        "Volume",
        "BidPrice1",
        "BidVolume1",
        "AskPrice1",
        "AskVolume1",
        "Turnover",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")

    df = df[required].copy()
    df["datetime"] = build_datetime(df)
    df = df.dropna(subset=["datetime"])
    df = df[df["datetime"].apply(is_trading_time)].copy()
    df = df.sort_values("datetime")
    df = df.drop_duplicates(subset=["datetime"], keep="last")

    df["last_price"] = pd.to_numeric(df["LastPrice"], errors="coerce")
    df["volume"] = pd.to_numeric(df["Volume"], errors="coerce")
    df["amount"] = pd.to_numeric(df["Turnover"], errors="coerce")
    df["bid_price1"] = pd.to_numeric(df["BidPrice1"], errors="coerce")
    df["bid_volume1"] = pd.to_numeric(df["BidVolume1"], errors="coerce")
    df["ask_price1"] = pd.to_numeric(df["AskPrice1"], errors="coerce")
    df["ask_volume1"] = pd.to_numeric(df["AskVolume1"], errors="coerce")

    df = df.dropna(
        subset=[
            "last_price",
            "volume",
            "amount",
            "bid_price1",
            "bid_volume1",
            "ask_price1",
            "ask_volume1",
        ]
    )

    valid_mask = (
        (df["ask_price1"] > df["bid_price1"])
        & (df["bid_price1"] > 0)
        & (df["ask_volume1"] > 0)
        & (df["bid_volume1"] > 0)
    )
    df = df[valid_mask].copy()

    df["tick_volume"] = df["volume"].diff().fillna(0)
    df["tick_amount"] = df["amount"].diff().fillna(0)
    df.loc[df["tick_volume"] < 0, "tick_volume"] = 0
    df.loc[df["tick_amount"] < 0, "tick_amount"] = 0

    output_cols = [
        "datetime",
        "last_price",
        "volume",
        "amount",
        "bid_price1",
        "bid_volume1",
        "ask_price1",
        "ask_volume1",
        "tick_volume",
        "tick_amount",
    ]
    return df[output_cols].reset_index(drop=True)


def parse_args():
    parser = argparse.ArgumentParser(description="Clean Ag continuous futures CSV files under src/.")
    parser.add_argument(
        "--input-dir",
        default="src",
        help="Directory containing raw CSV files.",
    )
    parser.add_argument(
        "--pattern",
        default="ag主力连续_*.csv",
        help="Filename pattern to match raw CSV files.",
    )
    parser.add_argument(
        "--output",
        default="data/ag_202604_cleaned.csv",
        help="Merged cleaned CSV output path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = Path(args.input_dir)
    files = sorted(input_dir.glob(args.pattern))
    if not files:
        raise FileNotFoundError(f"No files matched {args.pattern} in {input_dir}")

    cleaned_parts = []
    for path in files:
        part = clean_one_file(path)
        if not part.empty:
            part["source_file"] = path.name
            cleaned_parts.append(part)
            print(f"{path.name}: rows={len(part)}")
        else:
            print(f"{path.name}: empty_after_clean")

    if not cleaned_parts:
        raise RuntimeError("No usable rows after cleaning.")

    merged = pd.concat(cleaned_parts, ignore_index=True)
    merged["datetime"] = pd.to_datetime(merged["datetime"], errors="coerce")
    merged = merged.dropna(subset=["datetime"])
    merged = merged.sort_values("datetime")
    merged = merged.drop_duplicates(subset=["datetime"], keep="last")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(args.output, index=False, encoding="utf-8-sig")

    print(f"saved={args.output}")
    print(f"rows={len(merged)}")
    print(f"start={merged['datetime'].min()}")
    print(f"end={merged['datetime'].max()}")
    print(f"days={merged['datetime'].dt.date.nunique()}")
    print(f"columns={list(merged.columns)}")


if __name__ == "__main__":
    main()
