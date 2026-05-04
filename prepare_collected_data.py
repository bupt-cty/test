import argparse
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
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


def load_and_validate(path):
    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"])
    df = df.sort_values("datetime")
    df = df.drop_duplicates(subset=["datetime"], keep="last")
    return df.reset_index(drop=True)


def summarize(df):
    if df.empty:
        return {
            "rows": 0,
            "start": None,
            "end": None,
            "days": 0,
            "bad_spread_rows": 0,
        }

    return {
        "rows": int(len(df)),
        "start": str(df["datetime"].min()),
        "end": str(df["datetime"].max()),
        "days": int(df["datetime"].dt.date.nunique()),
        "bad_spread_rows": int((df["bid_price1"] >= df["ask_price1"]).sum()),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare locally collected tick CSV data for backtesting.")
    parser.add_argument("--input", required=True, help="Collected CSV path.")
    parser.add_argument("--output", required=True, help="Cleaned CSV output path.")
    return parser.parse_args()


def main():
    args = parse_args()
    df = load_and_validate(Path(args.input))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    info = summarize(df)
    print(f"saved={args.output}")
    for key, value in info.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
