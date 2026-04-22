"""
Data center geographic + size visualization.

Usage:
    python visualize_datacenters.py path/to/data.csv [output.png]

Reads a CSV or TSV data center dataset and produces a 4-panel figure:
  1. US map: lat/long scatter, marker size = facility_size_sqft, color = status
  2. MW vs facility size (log-log) with status hue
  3. Top 15 states by operating + proposed MW (stacked bar)
  4. Community pushback rate by project status
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------- config ----------

STATUS_COLORS = {
    "Operating": "#2b8a3e",
    "Approved/Permitted/Under construction": "#1c7ed6",
    "Expanding": "#0b7285",
    "Proposed": "#f08c00",
    "Suspended": "#868e96",
    "Cancelled": "#c92a2a",
    "Unknown": "#adb5bd",
}

US_BOUNDS = dict(lon_min=-125, lon_max=-66, lat_min=24, lat_max=50)


# ---------- loading & cleaning ----------

def sniff_delimiter(path: str) -> str:
    """Pick tab vs comma by counting occurrences in the header line. csv.Sniffer
    is unreliable on files with long free-text cells, so we do it manually."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.strip():
                return "\t" if line.count("\t") >= line.count(",") else ","
    return ","


def load(path: str) -> pd.DataFrame:
    delim = sniff_delimiter(path)
    print(f"Detected delimiter: {'TAB' if delim == chr(9) else 'COMMA'}")

    # index_col=False prevents pandas from promoting the first column to a
    # row index when rows have a trailing delimiter.
    df = pd.read_csv(
        path,
        sep=delim,
        dtype=str,
        skip_blank_lines=True,
        engine="python",
        on_bad_lines="skip",
        index_col=False,
        encoding="utf-8",
        encoding_errors="replace",
    )
    df.columns = [c.strip() for c in df.columns]

    print(f"Loaded {len(df):,} rows with {len(df.columns)} columns")
    if "lat" not in df.columns:
        print("\nERROR: no 'lat' column found. First 10 column names are:")
        for c in list(df.columns)[:10]:
            print(f"    {c!r}")
        print("\nIf your lat/long columns are named differently (e.g. "
              "'Latitude', 'LAT'), rename them in the source file or edit "
              "this script.")
        sys.exit(1)

    return df


def to_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.replace(r"[,\$]", "", regex=True).str.strip(),
        errors="coerce",
    )


def parse_mw(series: pd.Series) -> pd.Series:
    """MW field has ranges ('200-400'), '>3,000', and '1,000+'. Take midpoint
    of ranges; strip '+', '>', and commas; return float MW."""
    def one(val):
        if not isinstance(val, str):
            return np.nan
        s = val.replace(",", "").replace("+", "").replace(">", "").strip()
        if not s:
            return np.nan
        if "-" in s:
            parts = [p.strip() for p in s.split("-") if p.strip()]
            try:
                nums = [float(p) for p in parts]
                return sum(nums) / len(nums)
            except ValueError:
                return np.nan
        try:
            return float(s)
        except ValueError:
            return np.nan
    return series.apply(one)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["lat"] = to_float(df["lat"])
    df["long"] = to_float(df["long"])
    df["sqft"] = to_float(df.get("facility_size_sqft", pd.Series(dtype=str)))
    df["mw"] = parse_mw(df.get("mw", pd.Series(dtype=str)))
    df["status"] = df.get("status", "Unknown").fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    df["state"] = df.get("state", "").fillna("").astype(str).str.strip()
    df["pushback"] = df.get("community_pushback", "").fillna("").astype(str).str.strip().str.lower()
    return df


# ---------- plotting ----------

def panel_map(ax, df):
    m = df.dropna(subset=["lat", "long"])
    m = m[
        (m["long"].between(US_BOUNDS["lon_min"], US_BOUNDS["lon_max"]))
        & (m["lat"].between(US_BOUNDS["lat_min"], US_BOUNDS["lat_max"]))
    ].copy().reset_index(drop=True)

    # Compute sizes aligned to m's positional order (after reset_index).
    sqft = m["sqft"].fillna(0).to_numpy()
    sizes = np.where(sqft > 0, 4 + np.sqrt(sqft) / 40, 6)
    sizes = np.clip(sizes, 4, 400)
    m["_size"] = sizes

    for status, color in STATUS_COLORS.items():
        sub = m[m["status"] == status]
        if sub.empty:
            continue
        ax.scatter(
            sub["long"], sub["lat"],
            s=sub["_size"],
            c=color, alpha=0.55,
            edgecolors="white", linewidths=0.3,
            label=f"{status} (n={len(sub)})",
        )

    ax.set_xlim(US_BOUNDS["lon_min"], US_BOUNDS["lon_max"])
    ax.set_ylim(US_BOUNDS["lat_min"], US_BOUNDS["lat_max"])
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("US Data Center Locations\n(marker size ~ sqrt facility sqft, color = status)", fontsize=12)
    ax.legend(loc="lower left", fontsize=7, framealpha=0.9, markerscale=0.6)
    ax.grid(True, alpha=0.2, linestyle=":")
    ax.set_aspect(1.3)


def panel_mw_vs_size(ax, df):
    m = df.dropna(subset=["mw", "sqft"])
    m = m[(m["mw"] > 0) & (m["sqft"] > 0)]

    for status, color in STATUS_COLORS.items():
        sub = m[m["status"] == status]
        if sub.empty:
            continue
        ax.scatter(sub["sqft"], sub["mw"], c=color, alpha=0.6, s=25,
                   edgecolors="white", linewidths=0.3, label=status)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Facility size (sqft, log)")
    ax.set_ylabel("Power capacity (MW, log)")
    ax.set_title("Power Density: MW vs Facility Size", fontsize=12)
    ax.grid(True, which="both", alpha=0.2, linestyle=":")

    x = np.array([1e4, 3e7])
    ax.plot(x, x / 4000, "--", color="black", alpha=0.35, label="~250 W/sqft reference")
    ax.legend(loc="upper left", fontsize=7, framealpha=0.9)


def panel_top_states(ax, df):
    live_statuses = {"Operating", "Expanding", "Approved/Permitted/Under construction"}
    sub = df.dropna(subset=["mw"]).copy()
    sub["bucket"] = np.where(
        sub["status"].isin(live_statuses), "Built / under construction", "Proposed / other"
    )
    pivot = sub.groupby(["state", "bucket"])["mw"].sum().unstack(fill_value=0)
    if pivot.empty:
        ax.text(0.5, 0.5, "no MW data", transform=ax.transAxes, ha="center", va="center", color="#888")
        ax.set_title("Top 15 States by Aggregate Data Center MW", fontsize=12)
        return
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=True).tail(15)

    y = np.arange(len(pivot))
    built = pivot.get("Built / under construction", pd.Series(0, index=pivot.index))
    proposed = pivot.get("Proposed / other", pd.Series(0, index=pivot.index))

    ax.barh(y, built, color="#1c7ed6", label="Built / under construction")
    ax.barh(y, proposed, left=built, color="#f08c00", label="Proposed / other")
    ax.set_yticks(y)
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("Total MW (GW = 1,000 MW)")
    ax.set_title("Top 15 States by Aggregate Data Center MW", fontsize=12)
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(True, axis="x", alpha=0.2, linestyle=":")

    for i, total in enumerate(pivot["total"]):
        ax.text(total, i, f"  {total:,.0f}", va="center", fontsize=7, color="#333")


def panel_pushback(ax, df):
    order = [
        "Proposed",
        "Approved/Permitted/Under construction",
        "Operating",
        "Expanding",
        "Suspended",
        "Cancelled",
    ]
    rows = []
    for status in order:
        sub = df[df["status"] == status]
        if sub.empty:
            continue
        yes = (sub["pushback"] == "yes").sum()
        total = len(sub)
        rows.append((status, yes, total, yes / total * 100 if total else 0))

    rows.sort(key=lambda r: r[3])
    labels = [r[0] for r in rows]
    pct = [r[3] for r in rows]
    counts = [f"{r[1]}/{r[2]}" for r in rows]

    colors = [STATUS_COLORS.get(l, "#868e96") for l in labels]
    y = np.arange(len(labels))
    ax.barh(y, pct, color=colors, alpha=0.85)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("% of projects with documented community pushback")
    ax.set_title("Community Pushback Rate by Project Status", fontsize=12)
    ax.grid(True, axis="x", alpha=0.2, linestyle=":")
    for i, (p, c) in enumerate(zip(pct, counts)):
        ax.text(p + 0.5, i, f"{p:.0f}%  ({c})", va="center", fontsize=8, color="#333")
    if pct:
        ax.set_xlim(0, max(pct) * 1.25 + 5)
    else:
        ax.text(0.5, 0.5, "no pushback data", transform=ax.transAxes,
                ha="center", va="center", color="#888")


def main():
    if len(sys.argv) < 2:
        print("usage: python visualize_datacenters.py data.csv [output_prefix]")
        print("  writes <prefix>_map.png and <prefix>_power_density.png")
        sys.exit(1)

    src = Path(sys.argv[1])
    prefix = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("datacenters")

    df = clean(load(str(src)))
    print(f"  with coords:   {df['lat'].notna().sum():,}")
    print(f"  with sqft:     {df['sqft'].notna().sum():,}")
    print(f"  with MW:       {df['mw'].notna().sum():,}")
    print(f"  pushback=yes:  {(df['pushback'] == 'yes').sum():,}")

    # Panel 1: geographic map. Square-ish aspect, a bit wider than tall.
    fig1, ax1 = plt.subplots(figsize=(12, 8))
    panel_map(ax1, df)
    fig1.tight_layout()
    out1 = prefix.with_name(f"{prefix.name}_map.png")
    fig1.savefig(out1, dpi=150, bbox_inches="tight")
    print(f"Wrote {out1.resolve()}")
    plt.close(fig1)

    # Panel 2: MW vs sqft scatter.
    fig2, ax2 = plt.subplots(figsize=(10, 8))
    panel_mw_vs_size(ax2, df)
    fig2.tight_layout()
    out2 = prefix.with_name(f"{prefix.name}_power_density.png")
    fig2.savefig(out2, dpi=150, bbox_inches="tight")
    print(f"Wrote {out2.resolve()}")
    plt.close(fig2)


if __name__ == "__main__":
    main()