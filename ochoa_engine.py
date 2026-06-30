"""
ochoa_engine.py
═══════════════════════════════════════════════════════════════════════════
A book-faithful scoring engine built directly from Frank Ochoa's
"Secrets of a Pivot Boss" (2010) — the Central Pivot Range (CPR), the four
Special Price-Based (SPB) reversal setups, the Camarilla Equation, and the
Money Zone (Market Profile) framework.

This module is INTENTIONALLY separate from the legacy composite scorer in
scan_cpr_multi_tf(). It does not blend in generic indicators (RSI/VWAP/
Stochastic/3-10 Oscillator) as primary signal drivers — those appear only
as small confirmation nudges, exactly the supporting role Ochoa gives
volume and momentum in the book. The core logic is 100% pivot/price-action
based, matching his stated philosophy that pure price is the leading
indicator.

Every rule below is cited to the specific book mechanic it encodes, in the
comments, so the engine can be audited against the source material.

PUBLIC ENTRY POINT
──────────────────
    score_ochoa_signal(df, interval) -> dict | None

Returns a structured signal dict (or None if no qualifying setup), with:
    side, score, day_type, cpr_width_pct, narrow_bonus_applied,
    setups_fired: [ {name, side, points, detail}, ... ],
    camarilla, money_zone, entry, sl, t1, t2, t3, rr1, rr2
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# SECTION 1 — CPR CORE  (Ch. 1–2 of the book: "Understanding Markets" /
#             the Central Pivot Range itself)
# ═══════════════════════════════════════════════════════════════════════

def compute_cpr_core(df: pd.DataFrame) -> dict:
    """
    Standard CPR from the prior completed bar.
    P = (H+L+C)/3 ; BC = (H+L)/2 ; TC = (P-BC)+P
    """
    ref = df.iloc[-2]
    H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
    P  = (H + L + C) / 3
    BC = (H + L) / 2
    TC = (P - BC) + P
    width_pct = abs(TC - BC) / P * 100 if P else 0.0
    return {"H": H, "L": L, "C": C, "P": P, "BC": BC, "TC": TC, "width_pct": width_pct}


def classify_day_type(width_pct: float, two_day_overlap: bool) -> str:
    """
    Published CPR-width interpretation of Ochoa's framework:
      < 0.25%             -> Trending  (high-conviction narrow CPR)
      < 0.50%             -> Moderate  (narrow CPR, still trending-biased)
      >= 0.50% + overlap  -> Sideways  (wide + sits inside/around prior CPR)
      >= 0.50% no overlap -> Volatile  (wide but directional structure intact)
    """
    if width_pct < 0.25:
        return "Trending"
    if width_pct < 0.50:
        return "Moderate"
    if two_day_overlap:
        return "Sideways"
    return "Volatile"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 2 — TWO-DAY CPR / PIVOT RANGE RELATIONSHIPS
#             (Ch. 2 "Daily CPR Width and Range Relationships" — Ochoa
#              describes 7 distinct two-day relationships; we model the
#              ones that are mechanically checkable from OHLC alone)
# ═══════════════════════════════════════════════════════════════════════

def two_day_cpr_relationship(today: dict, prior: dict) -> dict:
    """
    today / prior: dicts with BC, TC from compute_cpr_core().

    Relationships modeled (per the book):
      1. Higher Value (current range fully above prior)   -> most bullish
      2. Lower Value  (current range fully below prior)   -> most bearish
      3. Outside Value (current range fully engulfs prior) -> sideways bias,
         more so if current range is also notably WIDER than prior
      4. Inside Value (current range fully inside prior)   -> compression,
         breakout setup — especially if current CPR is also narrow
      5. Unchanged / heavy overlap                         -> dichotomy:
         quiet range-bound OR a coiled breakout, resolved by the open
    """
    t_bc, t_tc = today["BC"], today["TC"]
    p_bc, p_tc = prior["BC"], prior["TC"]
    t_w = abs(t_tc - t_bc)
    p_w = abs(p_tc - p_bc)

    overlap = not (t_tc < p_bc or t_bc > p_tc)

    if t_bc > p_tc:
        return {"relation": "Higher Value", "bias": "Bullish", "overlap": False,
                "detail": "Current CPR entirely above prior day's CPR — most bullish two-day relationship"}
    if t_tc < p_bc:
        return {"relation": "Lower Value", "bias": "Bearish", "overlap": False,
                "detail": "Current CPR entirely below prior day's CPR — most bearish two-day relationship"}
    if t_bc <= p_bc and t_tc >= p_tc and t_w > p_w * 1.05:
        return {"relation": "Outside Value", "bias": "Sideways", "overlap": True,
                "detail": "Current CPR engulfs prior CPR and is wider — sideways/range bias"}
    if t_bc >= p_bc and t_tc <= p_tc and t_w < p_w * 0.95:
        return {"relation": "Inside Value", "bias": "Coiled", "overlap": True,
                "detail": "Current CPR sits fully inside prior CPR and is narrower — compression, breakout setup"}
    return {"relation": "Unchanged/Overlap", "bias": "Neutral", "overlap": overlap,
            "detail": "Two-day CPR largely unchanged — resolved by how the session opens"}


# ═══════════════════════════════════════════════════════════════════════
# SECTION 3 — THE FOUR SPB (SPECIAL PRICE-BASED) REVERSAL SETUPS
#             (Ch. 2 "Engaging the Setup" — Wick / Extreme / Outside / Doji)
# ═══════════════════════════════════════════════════════════════════════

def _candle_geo(row) -> dict:
    o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
    rng  = max(h - l, 1e-9)
    body = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    close_pct_from_low = (c - l) / rng * 100       # 0 = closed at low, 100 = closed at high
    return dict(o=o, h=h, l=l, c=c, rng=rng, body=body,
                upper_wick=upper_wick, lower_wick=lower_wick,
                close_pct_from_low=close_pct_from_low,
                bull=c > o, bear=c < o)


def detect_wick_reversal(df: pd.DataFrame, wick_body_ratio: float = 2.5,
                          close_pct_threshold: float = 35.0) -> dict | None:
    """
    THE WICK REVERSAL SETUP — book rule (Ch. 2):
      • Wick must be at least 2:1 vs body (Ochoa personally prefers 2.5:1–3.5:1)
      • Close must fall within `close_pct_threshold`% of the candle's range,
        measured from the relevant extreme:
            bullish reversal wick -> close in BOTTOM 35% zone is wrong;
            per the book, a bullish reversal wick has a long LOWER wick and
            closes in the top portion of the range (commonly cited as
            "within 35% of the high" for a 35%-close-percentage read, i.e.
            close_pct_from_low >= 100 - close_pct_threshold)
            bearish reversal wick -> long UPPER wick, close near the low
            (close_pct_from_low <= close_pct_threshold)
    Default 2.5:1 reflects Ochoa's own stated preference, not just the bare
    2:1 minimum, to filter weaker candles as he recommends.
    """
    if len(df) < 1:
        return None
    g = _candle_geo(df.iloc[-1])
    if g["body"] <= 0:
        return None

    # Bullish reversal wick: long lower wick, small upper wick, closes high in range
    if (g["lower_wick"] >= wick_body_ratio * g["body"] and
            g["upper_wick"] <= g["body"] * 0.5 and
            g["close_pct_from_low"] >= (100 - close_pct_threshold)):
        ratio = g["lower_wick"] / g["body"]
        return {"name": "Wick Reversal (Bullish)", "side": "BUY",
                "ratio": round(ratio, 2),
                "close_pct": round(g["close_pct_from_low"], 1),
                "detail": f"Lower wick {ratio:.1f}x body, closed in top "
                          f"{100 - g['close_pct_from_low']:.0f}% zone of range"}

    # Bearish reversal wick: long upper wick, small lower wick, closes low in range
    if (g["upper_wick"] >= wick_body_ratio * g["body"] and
            g["lower_wick"] <= g["body"] * 0.5 and
            g["close_pct_from_low"] <= close_pct_threshold):
        ratio = g["upper_wick"] / g["body"]
        return {"name": "Wick Reversal (Bearish)", "side": "SELL",
                "ratio": round(ratio, 2),
                "close_pct": round(g["close_pct_from_low"], 1),
                "detail": f"Upper wick {ratio:.1f}x body, closed in bottom "
                          f"{g['close_pct_from_low']:.0f}% zone of range"}
    return None


def detect_extreme_reversal(df: pd.DataFrame, lookback: int = 10,
                             size_mult: float = 2.0) -> dict | None:
    """
    THE EXTREME REVERSAL SETUP — book rule (Ch. 2), TWO-BAR pattern:
      Bar 1 (the "extreme bar"):
        • Range is 50-100% larger than the average range of the lookback
          window (book figure; we use a configurable multiplier, default
          2.0x average to keep the higher-conviction end of that range)
        • Body covers a meaningful portion of the bar's range (i.e. it's a
          real directional bar, not an inside doji)
      Bar 2 (confirmation):
        • Must OPPOSE bar 1's direction: if bar 1 closed bullish (C>O),
          bar 2 must close bearish (C<O), and vice-versa.
    This is the "rubber band" snap-back: an over-extended, oversized move
    that fails to get continuation on the very next bar.
    """
    if len(df) < lookback + 2:
        return None
    bar1 = _candle_geo(df.iloc[-2])
    bar2 = _candle_geo(df.iloc[-1])

    avg_range = float((df["High"] - df["Low"]).iloc[-(lookback + 2):-2].mean())
    if avg_range <= 0:
        return None

    bar1_oversized = bar1["rng"] >= size_mult * avg_range
    bar1_directional = bar1["body"] >= bar1["rng"] * 0.5   # real body, not a doji
    opposes = (bar1["bull"] and bar2["bear"]) or (bar1["bear"] and bar2["bull"])

    if bar1_oversized and bar1_directional and opposes:
        side = "BUY" if bar1["bear"] else "SELL"   # fade bar 1's direction
        return {"name": f"Extreme Reversal ({'Bullish' if side=='BUY' else 'Bearish'})",
                "side": side,
                "bar1_size_mult": round(bar1["rng"] / avg_range, 2),
                "detail": f"Bar1 range {bar1['rng']/avg_range:.1f}x avg "
                          f"({'bullish' if bar1['bull'] else 'bearish'}), "
                          f"bar2 closed opposite ({'bullish' if bar2['bull'] else 'bearish'})"}
    return None


def detect_outside_reversal(df: pd.DataFrame, lookback: int = 10,
                             size_mult: float = 1.25) -> dict | None:
    """
    THE OUTSIDE REVERSAL SETUP — book rule (Ch. 2):
      The current bar's range fully ENGULFS the prior bar's range
      (high > prior high AND low < prior low — a true "outside bar" in the
      classic sense), is moderately oversized vs the recent average, and
      CLOSES back inside / opposite to the breach direction — signalling
      a false-breakout fade rather than genuine follow-through.
    """
    if len(df) < lookback + 1:
        return None
    cur  = _candle_geo(df.iloc[-1])
    prev = _candle_geo(df.iloc[-2])
    avg_range = float((df["High"] - df["Low"]).iloc[-(lookback + 1):-1].mean())
    if avg_range <= 0:
        return None

    is_outside_bar = cur["h"] > prev["h"] and cur["l"] < prev["l"]
    oversized = cur["rng"] >= size_mult * avg_range

    if is_outside_bar and oversized:
        # Bullish outside reversal: swept below prior low, closed back above prior open
        if cur["l"] < prev["l"] and cur["c"] > prev["o"]:
            return {"name": "Outside Reversal (Bullish)", "side": "BUY",
                    "detail": "Bar swept below prior low and prior high, "
                              "closed back above prior open — false breakdown fade"}
        # Bearish outside reversal: swept above prior high, closed back below prior open
        if cur["h"] > prev["h"] and cur["c"] < prev["o"]:
            return {"name": "Outside Reversal (Bearish)", "side": "SELL",
                    "detail": "Bar swept above prior high and below prior low, "
                              "closed back below prior open — false breakout fade"}
    return None


def detect_doji_reversal(df: pd.DataFrame, sma_period: int = 10,
                          doji_threshold_pct: float = 10.0,
                          confirm_window: int = 2) -> dict | None:
    """
    THE DOJI REVERSAL SETUP — book rule (Ch. 2):
      1. |Open - Close| <= 10% of the candle's range (true doji)
      2. Bullish doji: doji's HIGH must be below the 10-period SMA of close
         Bearish doji: doji's LOW must be above the 10-period SMA of close
      3. Confirmation within the next `confirm_window` bars:
           bullish -> a bar closes ABOVE the doji's high
           bearish -> a bar closes BELOW the doji's low
    We scan backwards up to `confirm_window` bars for an unconfirmed doji
    so the setup can fire on the confirmation bar itself, exactly as a
    trader would only act once confirmation prints.
    """
    if len(df) < sma_period + confirm_window + 1:
        return None
    sma = df["Close"].rolling(sma_period).mean()

    for back in range(1, confirm_window + 1):
        doji_idx = -1 - back
        if abs(doji_idx) > len(df):
            continue
        d = _candle_geo(df.iloc[doji_idx])
        if d["body"] > d["rng"] * (doji_threshold_pct / 100.0):
            continue   # not a doji

        sma_at_doji = sma.iloc[doji_idx]
        if np.isnan(sma_at_doji):
            continue

        confirm_slice = df.iloc[doji_idx + 1:] if doji_idx + 1 < 0 else df.iloc[0:0]
        if confirm_slice.empty:
            continue

        # Bullish doji: high below 10-SMA, then a later close above doji high
        if d["h"] < sma_at_doji:
            if (confirm_slice["Close"] > d["h"]).any():
                return {"name": "Doji Reversal (Bullish)", "side": "BUY",
                        "detail": f"Doji formed below {sma_period}-SMA, "
                                  f"confirmed by a close above doji high within {confirm_window} bars"}
        # Bearish doji: low above 10-SMA, then a later close below doji low
        if d["l"] > sma_at_doji:
            if (confirm_slice["Close"] < d["l"]).any():
                return {"name": "Doji Reversal (Bearish)", "side": "SELL",
                        "detail": f"Doji formed above {sma_period}-SMA, "
                                  f"confirmed by a close below doji low within {confirm_window} bars"}
    return None


# ═══════════════════════════════════════════════════════════════════════
# SECTION 4 — THE CAMARILLA EQUATION  (Ch. 7 "Introducing the Camarilla
#             Equation" — H1-H4 / L1-L4 from prior session's H/L/C)
# ═══════════════════════════════════════════════════════════════════════

def compute_camarilla(df: pd.DataFrame) -> dict:
    """
    Standard Camarilla — Fibonacci-derived multipliers on prior session's
    range, anchored to prior close:
        H4 = C + Range*0.55   H3 = C + Range*0.275
        H2 = C + Range*0.183  H1 = C + Range*0.0916
        L1 = C - Range*0.0916 L2 = C - Range*0.183
        L3 = C - Range*0.275  L4 = C - Range*0.55
    H3/L3 = the reversal layer (fade against the level).
    H4/L4 = the breakout layer (trade with a confirmed break).
    H5/L5 used as the breakout target (H5 = H4 + (H4-H3) range projection).
    """
    ref = df.iloc[-2]
    H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
    rng = H - L
    if rng <= 0:
        return {}
    h1 = C + rng * 0.0916
    h2 = C + rng * 0.183
    h3 = C + rng * 0.275
    h4 = C + rng * 0.55
    l1 = C - rng * 0.0916
    l2 = C - rng * 0.183
    l3 = C - rng * 0.275
    l4 = C - rng * 0.55
    h5 = h4 + (h4 - h3)
    l5 = l4 - (l3 - l4)
    return {"H1": round(h1, 2), "H2": round(h2, 2), "H3": round(h3, 2),
            "H4": round(h4, 2), "H5": round(h5, 2),
            "L1": round(l1, 2), "L2": round(l2, 2), "L3": round(l3, 2),
            "L4": round(l4, 2), "L5": round(l5, 2)}


def classify_camarilla_setup(ltp: float, cam: dict) -> dict | None:
    """
    Book rule (Ch. 7 "Standard Third Layer Reversal" / "Fourth Layer Breakout"):
      • Price at/through H3 but below H4  -> H3 Reversal SELL setup
        (target L3, stop just above H4)
      • Price at/through L3 but above L4  -> L3 Reversal BUY setup
        (target H3, stop just below L4)
      • Price breaks beyond H4            -> H4 Breakout BUY setup
        (target H5, stop just below H3)
      • Price breaks beyond L4            -> L4 Breakout SELL setup
        (target L5, stop just above L3)
    """
    if not cam:
        return None
    if ltp >= cam["H4"]:
        return {"setup": "H4 Breakout", "side": "BUY",
                "target": cam["H5"], "stop": cam["H3"],
                "detail": "Price broke above H4 — Camarilla breakout long, target H5"}
    if cam["H3"] <= ltp < cam["H4"]:
        return {"setup": "H3 Reversal", "side": "SELL",
                "target": cam["L3"], "stop": cam["H4"],
                "detail": "Price testing H3 resistance — Camarilla reversal short, target L3"}
    if ltp <= cam["L4"]:
        return {"setup": "L4 Breakout", "side": "SELL",
                "target": cam["L5"], "stop": cam["L3"],
                "detail": "Price broke below L4 — Camarilla breakout short, target L5"}
    if cam["L4"] < ltp <= cam["L3"]:
        return {"setup": "L3 Reversal", "side": "BUY",
                "target": cam["H3"], "stop": cam["L4"],
                "detail": "Price testing L3 support — Camarilla reversal long, target H3"}
    return None


# ═══════════════════════════════════════════════════════════════════════
# SECTION 5 — THE MONEY ZONE  (Ch. 3 "Introducing the Money Zone" —
#             Market Profile POC / Value Area High / Value Area Low)
# ═══════════════════════════════════════════════════════════════════════

def money_zone_bias(ltp: float, mz: dict) -> str | None:
    """
    Book rule: price above VAH = value migrating up (bullish);
    price below VAL = value migrating down (bearish);
    price inside VAH-VAL = balanced, no directional edge from MZ alone.
    """
    if not mz:
        return None
    if ltp > mz.get("VAH", float("inf")):
        return "Bullish"
    if ltp < mz.get("VAL", float("-inf")):
        return "Bearish"
    return "Balanced"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 6 — THE SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════

# Point weights — calibrated so that Narrow-CPR + Two-Day Non-Overlap
# (Ochoa's single highest-conviction combination) dominates the score,
# per the user's instruction to heavily favor (but not hard-gate) Narrow
# CPR setups.
WEIGHTS = {
    "cpr_position":        3,   # price above/below TC/BC — the core CPR signal
    "virgin_cpr":           2,   # untouched CPR — high quality per the book
    "narrow_cpr_trending":  4,   # width < 0.25% (Trending day type)
    "narrow_cpr_moderate":  2,   # width < 0.50% (Moderate day type)
    "two_day_higher_lower": 4,   # Higher/Lower Value relationship (most convicted)
    "two_day_inside_coil":  3,   # Inside Value + narrow = coiled breakout
    "two_day_outside_wide": -3,  # Outside Value + wider = sideways penalty
    "sideways_penalty":    -4,  # Day Type == Sideways
    "wick_reversal":        4,   # true book-rule wick reversal
    "extreme_reversal":     5,   # true two-bar extreme reversal — rare, high value
    "outside_reversal":     4,   # true outside-bar fade
    "doji_reversal":         3,   # confirmed doji reversal
    "camarilla_h3l3":       2,   # Camarilla 3rd-layer reversal aligns with side
    "camarilla_h4l4":       3,   # Camarilla 4th-layer breakout aligns with side
    "money_zone_align":      2,   # price outside Value Area, aligned with side
}


def score_ochoa_signal(df: pd.DataFrame, interval: str = "1d",
                        compute_market_profile_fn=None) -> dict | None:
    """
    Main entry point. `df` must be a normalised OHLCV DataFrame (same
    contract as scan_cpr_multi_tf's _normalise_df output) with at least
    ~25 bars of history (more is better for the Extreme Reversal lookback
    and the Money Zone profile).

    `compute_market_profile_fn` — optionally pass the app's existing
    compute_market_profile() so this module doesn't need to reimplement
    Market Profile; if omitted, Money Zone scoring is simply skipped.

    Returns None if no directional setups fire at all (pure Neutral).
    """
    if df is None or df.empty or len(df) < 15:
        return None

    close = df["Close"]
    ltp = float(close.iloc[-1])

    cpr = compute_cpr_core(df)
    P, BC, TC, width_pct = cpr["P"], cpr["BC"], cpr["TC"], cpr["width_pct"]

    # ── Two-day CPR relationship ────────────────────────────────────────
    two_day = None
    if len(df) >= 4:
        prior_window = df.iloc[:-1]
        prior_cpr = compute_cpr_core(prior_window)
        two_day = two_day_cpr_relationship(cpr, prior_cpr)

    overlap = two_day["overlap"] if two_day else False
    day_type = classify_day_type(width_pct, overlap)

    setups = []
    bull_pts = 0.0
    bear_pts = 0.0

    def add(side: str, pts: float, name: str, detail: str):
        nonlocal bull_pts, bear_pts
        if side == "BUY":
            bull_pts += pts
        else:
            bear_pts += pts
        setups.append({"name": name, "side": side, "points": pts, "detail": detail})

    # ── 1. CPR position (core signal) ───────────────────────────────────
    if ltp > TC:
        add("BUY", WEIGHTS["cpr_position"], "CPR Position", "Price trading above TC")
    elif ltp < BC:
        add("SELL", WEIGHTS["cpr_position"], "CPR Position", "Price trading below BC")

    # ── 2. Virgin CPR ────────────────────────────────────────────────────
    inside_recent = ((close.iloc[-12:-2] >= BC) & (close.iloc[-12:-2] <= TC)).any() if len(df) >= 12 else False
    virgin = not inside_recent
    if virgin and ltp > TC:
        add("BUY", WEIGHTS["virgin_cpr"], "Virgin CPR", "Untouched CPR breached to the upside")
    elif virgin and ltp < BC:
        add("SELL", WEIGHTS["virgin_cpr"], "Virgin CPR", "Untouched CPR breached to the downside")

    # ── 3. Narrow CPR weighting — heavy bonus, not a gate ───────────────
    narrow_bonus_applied = False
    if day_type == "Trending":
        bonus_side = "BUY" if bull_pts >= bear_pts else "SELL"
        if bull_pts > 0 or bear_pts > 0:
            add(bonus_side, WEIGHTS["narrow_cpr_trending"], "Narrow CPR (Trending)",
                f"CPR width {width_pct:.3f}% — high-conviction trending day")
            narrow_bonus_applied = True
    elif day_type == "Moderate":
        bonus_side = "BUY" if bull_pts >= bear_pts else "SELL"
        if bull_pts > 0 or bear_pts > 0:
            add(bonus_side, WEIGHTS["narrow_cpr_moderate"], "Narrow CPR (Moderate)",
                f"CPR width {width_pct:.3f}% — moderate trending bias")
            narrow_bonus_applied = True

    # ── 4. Two-Day CPR Relationship ─────────────────────────────────────
    if two_day:
        rel = two_day["relation"]
        if rel == "Higher Value":
            add("BUY", WEIGHTS["two_day_higher_lower"], "Two-Day CPR: Higher Value", two_day["detail"])
        elif rel == "Lower Value":
            add("SELL", WEIGHTS["two_day_higher_lower"], "Two-Day CPR: Lower Value", two_day["detail"])
        elif rel == "Inside Value":
            side = "BUY" if ltp >= P else "SELL"
            add(side, WEIGHTS["two_day_inside_coil"], "Two-Day CPR: Inside Value (Coiled)", two_day["detail"])
        elif rel == "Outside Value":
            bull_pts = max(0.0, bull_pts + WEIGHTS["two_day_outside_wide"])
            bear_pts = max(0.0, bear_pts + WEIGHTS["two_day_outside_wide"])
            setups.append({"name": "Two-Day CPR: Outside Value (penalty)", "side": "—",
                            "points": WEIGHTS["two_day_outside_wide"], "detail": two_day["detail"]})

    if day_type == "Sideways":
        bull_pts = max(0.0, bull_pts + WEIGHTS["sideways_penalty"])
        bear_pts = max(0.0, bear_pts + WEIGHTS["sideways_penalty"])
        setups.append({"name": "Sideways Day (penalty)", "side": "—",
                        "points": WEIGHTS["sideways_penalty"],
                        "detail": f"CPR width {width_pct:.2f}% + overlapping prior CPR"})

    # ── 5. The four SPB reversal setups ─────────────────────────────────
    wick = detect_wick_reversal(df)
    if wick:
        add(wick["side"], WEIGHTS["wick_reversal"], wick["name"], wick["detail"])

    extreme = detect_extreme_reversal(df)
    if extreme:
        add(extreme["side"], WEIGHTS["extreme_reversal"], extreme["name"], extreme["detail"])

    outside = detect_outside_reversal(df)
    if outside:
        add(outside["side"], WEIGHTS["outside_reversal"], outside["name"], outside["detail"])

    doji = detect_doji_reversal(df)
    if doji:
        add(doji["side"], WEIGHTS["doji_reversal"], doji["name"], doji["detail"])

    # ── 6. Camarilla Equation ───────────────────────────────────────────
    cam = compute_camarilla(df)
    cam_setup = classify_camarilla_setup(ltp, cam) if cam else None
    if cam_setup:
        w = WEIGHTS["camarilla_h4l4"] if "Breakout" in cam_setup["setup"] else WEIGHTS["camarilla_h3l3"]
        add(cam_setup["side"], w, f"Camarilla {cam_setup['setup']}", cam_setup["detail"])

    # ── 7. Money Zone (optional — needs compute_market_profile_fn) ─────
    mz = None
    if compute_market_profile_fn is not None:
        mz = compute_market_profile_fn(df)
        mz_bias = money_zone_bias(ltp, mz) if mz else None
        if mz_bias == "Bullish":
            add("BUY", WEIGHTS["money_zone_align"], "Money Zone", f"Price above VAH ({mz.get('VAH')})")
        elif mz_bias == "Bearish":
            add("SELL", WEIGHTS["money_zone_align"], "Money Zone", f"Price below VAL ({mz.get('VAL')})")

    # ── Resolve side ─────────────────────────────────────────────────────
    if bull_pts == 0 and bear_pts == 0:
        return None
    if bull_pts == bear_pts:
        return None

    side = "BUY" if bull_pts > bear_pts else "SELL"
    score = round(max(bull_pts, bear_pts), 2)
    confidence_pct = round(max(bull_pts, bear_pts) / max(bull_pts + bear_pts, 1e-9) * 100, 1)

    # ── Trade levels — pivot-based, per the book's risk framework:
    #     "if you buy at TC, stop must be below the Pivot; target the next
    #      resistance/Camarilla layer" ─────────────────────────────────
    atr = float((df["High"] - df["Low"]).rolling(14).mean().iloc[-1])
    if np.isnan(atr) or atr <= 0:
        atr = float((df["High"] - df["Low"]).iloc[-5:].mean())
    if np.isnan(atr) or atr <= 0:
        return None   # no usable volatility reference — can't size a trade safely

    MIN_RR = 1.0  # a target closer than 1R of risk isn't a tradable target

    if side == "BUY":
        entry = round(max(ltp, TC), 2)
        sl = round(min(BC, P - atr * 0.1), 2)
        risk = abs(entry - sl)
        if risk <= 0:
            return None
        cam_t1 = cam.get("H3") if cam else None
        cam_t2 = cam.get("H4") if cam else None
        cam_t3 = cam.get("H5") if cam else None
        # Use Camarilla level only if it clears MIN_RR; else fall back to ATR projection
        t1 = round(cam_t1, 2) if (cam_t1 and cam_t1 > entry and (cam_t1 - entry) / risk >= MIN_RR) else round(entry + atr, 2)
        t2 = round(cam_t2, 2) if (cam_t2 and cam_t2 > entry and (cam_t2 - entry) / risk >= MIN_RR * 1.5) else round(entry + atr * 2, 2)
        t3 = round(cam_t3, 2) if (cam_t3 and cam_t3 > entry and (cam_t3 - entry) / risk >= MIN_RR * 2) else round(entry + atr * 3, 2)
    else:
        entry = round(min(ltp, BC), 2)
        sl = round(max(TC, P + atr * 0.1), 2)
        risk = abs(entry - sl)
        if risk <= 0:
            return None
        cam_t1 = cam.get("L3") if cam else None
        cam_t2 = cam.get("L4") if cam else None
        cam_t3 = cam.get("L5") if cam else None
        t1 = round(cam_t1, 2) if (cam_t1 and cam_t1 < entry and (entry - cam_t1) / risk >= MIN_RR) else round(entry - atr, 2)
        t2 = round(cam_t2, 2) if (cam_t2 and cam_t2 < entry and (entry - cam_t2) / risk >= MIN_RR * 1.5) else round(entry - atr * 2, 2)
        t3 = round(cam_t3, 2) if (cam_t3 and cam_t3 < entry and (entry - cam_t3) / risk >= MIN_RR * 2) else round(entry - atr * 3, 2)

    # Enforce monotonic target spacing — T1/T2/T3 may come from independent
    # sources (Camarilla vs ATR fallback) and can otherwise land out of order
    if side == "BUY":
        t1, t2, t3 = sorted([t1, t2, t3])
    else:
        t1, t2, t3 = sorted([t1, t2, t3], reverse=True)

    rr1 = round(abs(t1 - entry) / risk, 2)
    rr2 = round(abs(t2 - entry) / risk, 2)

    if rr1 < MIN_RR:
        return None   # quality gate — no signal with sub-1R reward is worth surfacing

    return {
        "side": side,
        "score": score,
        "confidence_pct": confidence_pct,
        "day_type": day_type,
        "cpr_width_pct": round(width_pct, 3),
        "narrow_bonus_applied": narrow_bonus_applied,
        "two_day_relation": two_day["relation"] if two_day else None,
        "setups_fired": setups,
        "camarilla": cam,
        "camarilla_setup": cam_setup,
        "money_zone": mz,
        "entry": entry, "sl": sl,
        "t1": t1, "t2": t2, "t3": t3,
        "rr1": rr1, "rr2": rr2,
        "P": round(P, 2), "BC": round(BC, 2), "TC": round(TC, 2),
        "virgin_cpr": virgin,
    }


def score_ochoa_batch(sym_data: dict, interval: str,
                       compute_market_profile_fn=None) -> pd.DataFrame:
    """
    Convenience batch wrapper — mirrors the row-schema the legacy
    scan_cpr_multi_tf produces so it can be dropped into the same
    downstream UI/Telegram/Forward-Testing code paths with minimal glue.

    sym_data: {symbol: normalised_OHLCV_DataFrame}
    """
    rows = []
    for sym, df in sym_data.items():
        try:
            sig = score_ochoa_signal(df, interval, compute_market_profile_fn)
        except Exception:
            sig = None
        if not sig:
            continue
        fired_names = " · ".join(s["name"] for s in sig["setups_fired"][:3])
        rows.append({
            "Symbol":      sym,
            "LTP":         round(float(df["Close"].iloc[-1]), 2),
            "Pattern":     "Bullish" if sig["side"] == "BUY" else "Bearish",
            "Strength%":   sig["confidence_pct"],
            "Ochoa Score": sig["score"],
            "Day Type":    sig["day_type"],
            "CPR Width%":  sig["cpr_width_pct"],
            "Narrow Bonus":"⭐ Yes" if sig["narrow_bonus_applied"] else "—",
            "Two-Day":     sig["two_day_relation"] or "—",
            "Virgin CPR":  "⭐ Yes" if sig["virgin_cpr"] else "—",
            "Setups":      fired_names,
            "Camarilla":   sig["camarilla_setup"]["setup"] if sig["camarilla_setup"] else "—",
            "Entry":       sig["entry"], "SL": sig["sl"],
            "T1": sig["t1"], "T2": sig["t2"], "T3": sig["t3"],
            "RR1": sig["rr1"], "RR2": sig["rr2"],
            "P": sig["P"], "BC": sig["BC"], "TC": sig["TC"],
            "_setups_detail": sig["setups_fired"],
        })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values(["Ochoa Score", "CPR Width%"], ascending=[False, True]).reset_index(drop=True)
