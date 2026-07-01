import streamlit as st
import pandas as pd
import os
try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH = True
except ImportError:
    _HAS_AUTOREFRESH = False

def _tg_creds():
    cfg = st.session_state.get("telegram_cfg", {})
    return cfg.get("bot_token", ""), cfg.get("chat_id", "")

def _send_telegram(message: str) -> bool:
    import requests as _req
    bot_token, chat_id = _tg_creds()
    if not bot_token or not chat_id:
        return False
    try:
        resp = _req.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def _tg_trade_msg(pos: dict, event_type: str = "ENTRY") -> str:
    side = pos.get("side","BUY"); emoji = "🟢" if side=="BUY" else "🔴"
    pnl  = pos.get("pnl",0);     pe    = "✅" if pnl>=0 else "❌"
    if event_type == "ENTRY":
        return (f"⚡ <b>AUTO TRADE ENTERED</b>\n{emoji} <b>{side} {pos.get('symbol','')}</b>  [{pos.get('tf','')}]\n"
                f"━━━━━━━━━━━━━━━━━━━━\n💰 Entry  : ₹{pos.get('entry',0):,.2f}\n"
                f"🎯 Target : ₹{pos.get('target',0):,.2f}\n🛑 SL     : ₹{pos.get('sl',0):,.2f}\n"
                f"📦 Qty    : {pos.get('qty',0)}\n💵 Cost   : ₹{pos.get('cost',0):,.0f}\n"
                f"📊 R:R    : {pos.get('rr',0)}x\n━━━━━━━━━━━━━━━━━━━━\n<i>PivotVault AI · Forward Testing</i>")
    return (f"{pe} <b>TRADE CLOSED — {event_type}</b>\n{emoji} <b>{side} {pos.get('symbol','')}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n💰 Entry : ₹{pos.get('entry',0):,.2f}\n"
            f"🏁 Exit  : ₹{pos.get('exit_px',0):,.2f}\n{pe} P&L   : ₹{pnl:,.2f}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n<i>PivotVault AI · Forward Testing</i>")


def _tg_signal_msg(r, tf_tag: str, source: str = "Scanner") -> str:
    """
    Build a rich Telegram message for a single CPR signal.
    Accepts both DataFrame rows (Title-case keys) and Top5 dicts (lowercase keys).
    """
    # Key aliases: scan DataFrames use Title case, Top5 dicts use lowercase
    _ALIASES = {
        "Pattern":   ["Pattern",   "side"],
        "Symbol":    ["Symbol",    "symbol"],
        "Entry":     ["Entry",     "entry",  "ltp"],
        "T1":        ["T1",        "t1"],
        "T2":        ["T2",        "t2"],
        "SL":        ["SL",        "sl"],
        "RR1":       ["RR1",       "rr1"],
        "Strength%": ["Strength%", "strength"],
        "Candle":    ["Candle",    "candle"],
        "RSI":       ["RSI",       "rsi"],
        "HMA":       ["HMA",       "hma"],
        "Vol Surge": ["Vol Surge", "vol"],
        "CPR Width%":["CPR Width%","cpr_w",  "cprw"],
        "Day Type":  ["Day Type",  "day_type"],
        "Rationale": ["Rationale", "rationale"],
    }
    def _g(key, default=0):
        for k in _ALIASES.get(key, [key]):
            try:
                v = r[k] if hasattr(r, "__getitem__") else getattr(r, k, None)
                if v is not None:
                    return v
            except Exception:
                pass
        return default

    # Determine side — Top5 dicts have "BUY"/"SELL" in "side"; DataFrames have "Bullish"/"Bearish" in "Pattern"
    _raw_side = None
    try:
        _raw_side = r.get("side") if hasattr(r, "get") else None
    except Exception:
        pass
    pattern = str(_g("Pattern", ""))
    if _raw_side in ("BUY", "SELL"):
        side = _raw_side
    elif pattern == "Bullish":
        side = "BUY"
    else:
        side = "SELL"

    emoji    = "🟢" if side == "BUY" else "🔴"
    sym      = str(_g("Symbol",    ""))
    entry    = float(_g("Entry",   0))
    t1       = float(_g("T1",      0))
    t2       = float(_g("T2",      0))
    sl       = float(_g("SL",      0))
    rr1      = float(_g("RR1",     0))
    strength = float(_g("Strength%", 0))
    candle   = str(_g("Candle",   "—"))
    rsi      = float(_g("RSI",     0))
    hma      = str(_g("HMA",      "—"))
    vol      = str(_g("Vol Surge", "—"))
    cpr_w    = float(_g("CPR Width%", 0))
    day_type = str(_g("Day Type", "—"))
    rationale= str(_g("Rationale", ""))

    tf_map = {
        "15m": "⚡ 15 Min", "30m": "⏱️ 30 Min", "1h": "🕐 1 Hour",
        "1d":  "📅 Daily",  "1wk": "📆 Weekly",  "1mo": "🗓️ Monthly",
    }
    tf_label = tf_map.get(tf_tag, tf_tag.upper())
    sl_pct   = abs(entry - sl) / entry * 100 if entry > 0 else 0
    rr_emoji = "🏆" if rr1 >= 3 else ("✅" if rr1 >= 2 else "⚠️")

    msg_lines = [
        f"{emoji} <b>{side} SIGNAL — {sym}</b>  [{tf_label}]  📡 {source}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"💰 Entry   : ₹{entry:,.2f}",
        f"🎯 T1      : ₹{t1:,.2f}",
        f"🎯 T2      : ₹{t2:,.2f}",
        f"🛑 SL      : ₹{sl:,.2f}  ({sl_pct:.2f}%)",
        f"{rr_emoji} R:R     : {rr1:.1f}x",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 Strength: {strength:.0f}%",
        f"🕯️ Candle  : {candle}",
        f"📈 RSI     : {rsi:.1f}   HMA: {hma}",
        f"📦 Volume  : {vol}",
        f"📐 CPR W   : {cpr_w:.2f}%   Day: {day_type}",
    ]
    if rationale:
        msg_lines.append(f"💡 {rationale[:80]}")
    msg_lines.append("━━━━━━━━━━━━━━━━━━━━")
    msg_lines.append("<i>PivotVault AI · CPR Scanner</i>")
    return "\n".join(msg_lines)


def _tg_send_scan_signals(result, tf_tag: str, source: str = "Scanner"):
    """
    Send a Telegram notification for EVERY non-neutral signal in a scan result.
    Called after every manual or auto scan regardless of timeframe.
    Respects the notify_signals setting in Telegram config.
    """
    if not st.session_state.get("telegram_cfg", {}).get("notify_signals", True):
        return
    if result is None or (hasattr(result, "empty") and result.empty):
        return
    try:
        directional = result[result["Pattern"] != "Neutral"] if "Pattern" in result.columns else result
        if directional.empty:
            return
        total = len(directional)
        bull  = (directional["Pattern"] == "Bullish").sum() if "Pattern" in directional.columns else 0
        bear  = total - bull
        tf_map = {
            "15m": "⚡ 15 Min", "30m": "⏱️ 30 Min", "1h": "🕐 1 Hour",
            "1d": "📅 Daily",  "1wk": "📆 Weekly",  "1mo": "🗓️ Monthly",
        }
        tf_label = tf_map.get(tf_tag, tf_tag.upper())
        # ── Summary message ────────────────────────────────────────────────
        summary = (
            f"📡 <b>CPR SCAN COMPLETE — {tf_label}</b>  [{source}]\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 Bullish: {bull}   🔴 Bearish: {bear}   Total: {total}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>Individual signals follow below ↓</i>"
        )
        _send_telegram(summary)
        # ── Per-signal messages ────────────────────────────────────────────
        for _, row in directional.iterrows():
            msg = _tg_signal_msg(row, tf_tag, source)
            _send_telegram(msg)
    except Exception:
        pass

import numpy as np
import secrets
import re
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from io import StringIO
from datetime import datetime, timedelta
import time
import smtplib
try:
    from mobile_patch import inject_mobile
    _MOBILE_PATCH = True
except ImportError:
    _MOBILE_PATCH = False
import io
import base64
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, KeepTogether)
from reportlab.platypus import PageBreak
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit.components.v1 as _stc
from concurrent.futures import ThreadPoolExecutor, as_completed

# ══════════════════════════════════════════════════════════════
#  STRATEGY NAMING ENGINE
#  Generates a unique, readable strategy name from signal params
# ══════════════════════════════════════════════════════════════

def _build_strategy_name(s: dict) -> str:
    """
    Build a unique strategy name from signal parameters.
    Format: [SIDE]-[CPR_ZONE]-[CANDLE]-[RSI_ZONE]-[HMA]-[VOL]-[TF]
    Example: BUY · CPR Breakout · Hammer · RSI Momentum · HMA Rising · Vol Surge · 15M
    """
    parts = []

    side    = s.get("side", "BUY")
    candle  = s.get("candle", "—")
    rsi     = float(s.get("rsi", 50) or 50)
    hma     = str(s.get("hma", "—"))
    vol     = str(s.get("vol", "—"))
    cpr_w   = float(s.get("cpr_w", 1.0) or 1.0)
    strength= int(s.get("strength", 60) or 60)
    rr      = float(s.get("rr1", 2.0) or 2.0)
    ltp     = float(s.get("ltp", 0) or 0)
    entry   = float(s.get("entry", 0) or 0)
    tf      = s.get("tf", "")

    # ── CPR Zone ─────────────────────────────────────────────────────────
    if cpr_w < 0.3:
        cpr_zone = "Narrow CPR"
    elif cpr_w < 0.8:
        cpr_zone = "CPR Breakout"
    elif cpr_w < 1.5:
        cpr_zone = "CPR Expansion"
    else:
        cpr_zone = "Wide CPR"

    # ── RSI Zone ─────────────────────────────────────────────────────────
    if side == "BUY":
        if rsi >= 60:    rsi_zone = "RSI Momentum"
        elif rsi >= 50:  rsi_zone = "RSI Bullish"
        elif rsi >= 40:  rsi_zone = "RSI Recovery"
        else:            rsi_zone = "RSI Oversold"
    else:
        if rsi <= 40:    rsi_zone = "RSI Momentum"
        elif rsi <= 50:  rsi_zone = "RSI Bearish"
        elif rsi <= 60:  rsi_zone = "RSI Rejection"
        else:            rsi_zone = "RSI Overbought"

    # ── HMA signal ───────────────────────────────────────────────────────
    hma_tag = ""
    if "Rising" in hma or "↑" in hma or "above" in hma.lower():
        hma_tag = "HMA↑"
    elif "Falling" in hma or "↓" in hma or "below" in hma.lower():
        hma_tag = "HMA↓"

    # ── Volume ───────────────────────────────────────────────────────────
    vol_tag = ""
    if "Surge" in vol or "High" in vol or "surge" in vol.lower():
        vol_tag = "VolSurge"
    elif "Above" in vol or "above" in vol.lower():
        vol_tag = "VolUp"

    # ── Candle tag ────────────────────────────────────────────────────────
    candle_short = {
        "Hammer":           "Hammer",
        "Inverted Hammer":  "Inv.Hammer",
        "Bullish Engulfing":"Bull.Engulf",
        "Bearish Engulfing":"Bear.Engulf",
        "Doji":             "Doji",
        "Morning Star":     "MorningStar",
        "Evening Star":     "EveningStar",
        "Shooting Star":    "ShootStar",
        "Hanging Man":      "HangingMan",
        "Piercing Line":    "PiercingLine",
        "Dark Cloud Cover": "DarkCloud",
        "Bullish Harami":   "Bull.Harami",
        "Bearish Harami":   "Bear.Harami",
    }.get(candle, candle[:10] if candle != "—" else "")

    # ── Timeframe short ───────────────────────────────────────────────────
    tf_short = {"⚡ 15 Min": "15M", "🕐 1 Hour": "1H"}.get(tf, tf[:3])

    # ── R:R tier ─────────────────────────────────────────────────────────
    if   rr >= 3.0: rr_tag = "RR3+"
    elif rr >= 2.0: rr_tag = "RR2+"
    else:           rr_tag = "RR1+"

    # ── Strength tier ────────────────────────────────────────────────────
    if   strength >= 85: grade = "A+"
    elif strength >= 75: grade = "A"
    elif strength >= 65: grade = "B+"
    elif strength >= 55: grade = "B"
    else:                grade = "C"

    # ── Assemble strategy ID ─────────────────────────────────────────────
    core = f"{side} · {cpr_zone} · {rsi_zone}"
    if candle_short: core += f" · {candle_short}"
    extras = [x for x in [hma_tag, vol_tag] if x]
    if extras:       core += " · " + " + ".join(extras)
    core += f" [{tf_short}] [{rr_tag}] [Grade:{grade}]"

    return core


def _strategy_short_id(s: dict) -> str:
    """Short 2-3 word strategy ID for use in button labels and headers."""
    side   = s.get("side","BUY")
    cpr_w  = float(s.get("cpr_w", 1.0) or 1.0)
    candle = s.get("candle","")
    rsi    = float(s.get("rsi", 50) or 50)

    if cpr_w < 0.5:   cpr_part = "NarrowCPR"
    elif cpr_w < 1.0: cpr_part = "CPRBreak"
    else:             cpr_part = "WideCPR"

    candle_map = {
        "Hammer":"HMR","Inverted Hammer":"IHMR","Bullish Engulfing":"BENG",
        "Bearish Engulfing":"BENG","Doji":"DOJI","Morning Star":"MSTR",
        "Evening Star":"ESTR","Shooting Star":"SSTR","Dark Cloud Cover":"DCC",
    }
    c_tag = candle_map.get(candle, "")

    rsi_tag = "MOM" if (side=="BUY" and rsi>=60) or (side=="SELL" and rsi<=40) else "NEUT"

    parts = [p for p in [cpr_part, c_tag, rsi_tag] if p]
    return f"{side[:1]}-{'-'.join(parts)}"


# ══════════════════════════════════════════════════════════════
#  UPSTOX FREE DATA FEED
#  Free tier: Historical OHLCV + Market quotes (no WebSocket)
#  Docs: https://upstox.com/developer/api-documentation/
# ══════════════════════════════════════════════════════════════

UPSTOX_BASE = "https://api.upstox.com/v2"

# ── PVAIv2: GLOBAL TRADING CONSTANTS ────────────────────────────────────────
# Minimum SL distance from entry — signals with tighter SL are skipped.
# Analysis of 46 forward-test trades: 17/18 SL hits had <0.5% SL distance.
PVAI_MIN_SL_PCT   = 0.50   # 0.50% minimum SL distance from entry
PVAI_MIN_RR       = 1.5    # Minimum reward-to-risk ratio
PVAI_ATR_SL_MULT  = 0.8    # ATR multiplier for SL (was 0.1 — too tight)
PVAI_ENTRY_GATE_H = 9      # Auto-trade entry gate: no trades before 09:45 IST
PVAI_ENTRY_GATE_M = 45
# ────────────────────────────────────────────────────────────────────────────
UPSTOX_HFT_BASE = "https://api-hft.upstox.com/v2"   # High-speed order endpoint
UPSTOX_GTT_BASE = "https://api.upstox.com/v3"        # GTT orders endpoint

# ══════════════════════════════════════════════════════════════════════════════
#  UPSTOX ORDER EXECUTION ENGINE
#  Compliant with SEBI Feb 2025 circular — human-confirmed orders only.
#  Flow: Signal → Preview card → User clicks → Market order + GTT SL/Target
# ══════════════════════════════════════════════════════════════════════════════

def _upstox_headers() -> dict:
    token = st.session_state.get("upstox_access_token", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

def upstox_place_order(symbol: str, side: str, qty: int,
                       order_type: str = "MARKET",
                       price: float = 0.0,
                       product: str = "I") -> dict:
    """
    Place a market/limit order on Upstox.
    product: "I" = intraday MIS, "D" = delivery CNC
    Returns {"success": bool, "order_id": str, "message": str}
    """
    instrument_key = _upstox_instrument_key(symbol)
    payload = {
        "quantity":          qty,
        "product":           product,
        "validity":          "DAY",
        "price":             price,
        "tag":               "PIVOTVAULT",
        "instrument_key":    instrument_key,
        "order_type":        order_type,
        "transaction_type":  side.upper(),   # "BUY" or "SELL"
        "disclosed_quantity": 0,
        "trigger_price":     0,
        "is_amo":            False,
    }
    try:
        r = requests.post(
            f"{UPSTOX_HFT_BASE}/order/place",
            headers=_upstox_headers(),
            json=payload,
            timeout=8,
        )
        data = r.json()
        if r.status_code == 200 and data.get("status") == "success":
            order_id = data.get("data", {}).get("order_id", "")
            return {"success": True, "order_id": order_id,
                    "message": f"Order placed: {order_id}"}
        else:
            err = data.get("errors", [{}])
            msg = err[0].get("message", str(data)) if err else str(data)
            return {"success": False, "order_id": "", "message": msg}
    except Exception as e:
        return {"success": False, "order_id": "", "message": str(e)}


def upstox_place_gtt(symbol: str, side: str, qty: int,
                     sl_price: float, t1_price: float, t2_price: float = 0.0,
                     product: str = "I") -> dict:
    """
    Place GTT orders for SL and Target after entry is confirmed.
    Creates two GTT rules:
      - SL:  trigger when price goes BELOW sl_price → SELL
      - T1:  trigger when price goes ABOVE t1_price → SELL (for BUY trades)
    Returns {"success": bool, "gtt_ids": [...], "message": str}
    """
    instrument_key = _upstox_instrument_key(symbol)
    exit_side = "SELL" if side.upper() == "BUY" else "BUY"

    # SL GTT
    sl_trigger  = "BELOW" if side.upper() == "BUY" else "ABOVE"
    # T1 GTT
    t1_trigger  = "ABOVE" if side.upper() == "BUY" else "BELOW"

    gtt_ids  = []
    messages = []

    for trigger_type, trigger_price, label in [
        (sl_trigger, sl_price,  "SL"),
        (t1_trigger, t1_price,  "T1"),
    ]:
        payload = {
            "type":              "SINGLE",
            "quantity":          qty,
            "product":           product,
            "instrument_key":    instrument_key,
            "transaction_type":  exit_side,
            "rules": [{
                "strategy":      "EXIT",
                "trigger_type":  trigger_type,
                "trigger_price": round(trigger_price, 2),
            }],
        }
        try:
            r = requests.post(
                f"{UPSTOX_GTT_BASE}/order/gtt/place",
                headers=_upstox_headers(),
                json=payload,
                timeout=8,
            )
            data = r.json()
            if r.status_code == 200 and data.get("status") == "success":
                gid = data.get("data", {}).get("id", "")
                gtt_ids.append(gid)
                messages.append(f"{label} GTT set @ ₹{trigger_price} (id:{gid})")
            else:
                err = data.get("errors", [{}])
                msg = err[0].get("message", str(data)) if err else str(data)
                messages.append(f"{label} GTT FAILED: {msg}")
        except Exception as e:
            messages.append(f"{label} GTT error: {str(e)}")

    success = len(gtt_ids) == 2
    return {
        "success":  success,
        "gtt_ids":  gtt_ids,
        "message":  " | ".join(messages),
    }


def upstox_get_order_status(order_id: str) -> dict:
    """Poll status of a single order."""
    try:
        r = requests.get(
            f"{UPSTOX_HFT_BASE}/order/details",
            headers=_upstox_headers(),
            params={"order_id": order_id},
            timeout=5,
        )
        data = r.json()
        if r.status_code == 200:
            od = data.get("data", {})
            return {
                "status":    od.get("status","UNKNOWN"),
                "avg_price": od.get("average_price", 0.0),
                "qty":       od.get("filled_quantity", 0),
                "message":   od.get("status_message",""),
            }
    except Exception:
        pass
    return {"status": "UNKNOWN", "avg_price": 0.0, "qty": 0, "message": ""}


def upstox_cancel_gtt(gtt_id: str) -> bool:
    """Cancel a GTT order (used when EOD auto-closing real positions)."""
    try:
        r = requests.delete(
            f"{UPSTOX_GTT_BASE}/order/gtt/cancel",
            headers=_upstox_headers(),
            params={"id": gtt_id},
            timeout=5,
        )
        return r.status_code == 200 and r.json().get("status") == "success"
    except Exception:
        return False


def upstox_get_positions() -> list:
    """Get current day open positions from Upstox."""
    try:
        r = requests.get(
            f"{UPSTOX_HFT_BASE}/portfolio/short-term-positions",
            headers=_upstox_headers(),
            timeout=5,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception:
        pass
    return []


def upstox_get_funds() -> dict:
    """Get available margin/cash from Upstox."""
    try:
        r = requests.get(
            f"{UPSTOX_HFT_BASE}/user/get-funds-and-margin",
            headers=_upstox_headers(),
            params={"segment": "SEC"},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            eq   = data.get("equity", {})
            return {
                "available":  eq.get("available_margin", 0.0),
                "used":       eq.get("used_margin",      0.0),
                "total":      eq.get("net",              0.0),
            }
    except Exception:
        pass
    return {"available": 0.0, "used": 0.0, "total": 0.0}




# ── Upstox auto-renewal via TOTP (Time-based) ─────────────────────────────
# Upstox supports TOTP-based login for programmatic daily token renewal.
# This uses your Upstox login credentials + TOTP secret to get a new token
# automatically every day without manual intervention.


def upstox_get_live_ltp_batch(symbols: list) -> dict:
    """
    Fetch live LTP for multiple symbols in one Upstox API call.
    Returns {symbol: ltp} dict. Uses market-quote/ltp endpoint for speed.
    No @st.cache_data — uses session_state for token (can't cache).
    """
    if not _upstox_connected() or not symbols:
        return {}
    try:
        keys = ",".join([_upstox_instrument_key(s) for s in symbols[:50]])
        r = requests.get(
            f"{UPSTOX_BASE}/market-quote/ltp",
            headers={
                "Authorization": f"Bearer {st.session_state.get('upstox_access_token','')}",
                "Accept": "application/json",
            },
            params={"instrument_key": keys},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            result = {}
            for key, val in data.items():
                # key is like "NSE_EQ:RELIANCE"
                sym = key.split(":")[-1].split("|")[-1]
                result[sym] = round(float(val.get("last_price", 0)), 2)
            return result
    except Exception:
        pass
    return {}

def _upstox_connected() -> bool:
    """Return True if a valid Upstox access token is in session state."""
    token = st.session_state.get("upstox_access_token", "").strip()
    return bool(token and len(token) > 20)   # Upstox tokens are JWTs but length varies

def _upstox_has_credentials() -> bool:
    """True if API key+secret saved (even if token expired)."""
    key    = st.session_state.get("upstox_api_key","")
    secret = st.session_state.get("upstox_api_secret","")
    return bool(key and secret)


def _upstox_redirect_uri() -> str:
    """Detect correct redirect URI based on where the app is running."""
    try:
        ctx = getattr(st, "context", None)
        if ctx and hasattr(ctx, "headers"):
            host = dict(ctx.headers).get("host", "")
            if host and "localhost" not in host and "127.0.0.1" not in host:
                return f"https://{host}"
    except Exception:
        pass
    return "http://localhost:8501"

# ── Upstox ISIN map — correct instrument keys for NSE stocks ─────────────
UPSTOX_ISIN_MAP = {
    "RELIANCE":    "INE002A01018", "TCS":         "INE467B01029",
    "HDFCBANK":    "INE040A01034", "INFY":        "INE009A01021",
    "ICICIBANK":   "INE090A01021", "SBIN":        "INE062A01020",
    "HINDUNILVR":  "INE030A01027", "BAJFINANCE":  "INE296A01024",
    "BHARTIARTL":  "INE397D01024", "KOTAKBANK":   "INE237A01028",
    "LT":          "INE018A01030", "ASIANPAINT":  "INE021A01026",
    "AXISBANK":    "INE238A01034", "MARUTI":      "INE585B01010",
    "TITAN":       "INE280A01028", "SUNPHARMA":   "INE044A01036",
    "WIPRO":       "INE075A01022", "HCLTECH":     "INE860A01027",
    "ADANIENT":    "INE423A01024", "NTPC":        "INE733E01010",
    "TATAMOTORS":  "INE155A01022", "ONGC":        "INE213A01029",
    "POWERGRID":   "INE752E01010", "COALINDIA":   "INE522F01014",
    "TATASTEEL":   "INE081A01020", "JSWSTEEL":    "INE019A01038",
    "HINDALCO":    "INE038A01020", "ULTRACEMCO":  "INE481G01011",
    "NESTLEIND":   "INE239A01016", "TECHM":       "INE669C01036",
    "BAJAJFINSV":  "INE918I01026", "DRREDDY":     "INE089A01023",
    "CIPLA":       "INE059A01026", "DIVISLAB":    "INE361B01024",
    "ITC":         "INE154A01025", "BPCL":        "INE029A01011",
    "GRASIM":      "INE047A01021", "INDUSINDBK":  "INE095A01012",
    "EICHERMOT":   "INE066A01021", "HEROMOTOCO":  "INE158A01026",
    "M&M":         "INE101A01026", "BRITANNIA":   "INE216A01030",
}

UPSTOX_INDEX_KEYS = {
    "^NSEI":    "NSE_INDEX|Nifty 50",
    "^BSESN":   "BSE_INDEX|SENSEX",
    "^NSEBANK": "NSE_INDEX|Nifty Bank",
}

# NSE Symbol → Upstox instrument key (NSE_EQ|ISIN)
# Upstox accepts both ISIN format AND trading symbol format: NSE_EQ|SYMBOL
# The correct format for v2 API is: NSE_EQ|ISIN
# For simplicity and broad coverage we use the symbol-based key which works for most stocks
# Full ISIN list: https://upstox.com/developer/api-documentation/instruments
UPSTOX_INSTRUMENT_KEYS = {
    "RELIANCE":    "NSE_EQ|INE002A01018",
    "TCS":         "NSE_EQ|INE467B01029",
    "HDFCBANK":    "NSE_EQ|INE040A01034",
    "INFY":        "NSE_EQ|INE009A01021",
    "ICICIBANK":   "NSE_EQ|INE090A01021",
    "SBIN":        "NSE_EQ|INE062A01020",
    "HINDUNILVR":  "NSE_EQ|INE030A01027",
    "BAJFINANCE":  "NSE_EQ|INE296A01024",
    "BHARTIARTL":  "NSE_EQ|INE397D01024",
    "KOTAKBANK":   "NSE_EQ|INE237A01028",
    "LT":          "NSE_EQ|INE018A01030",
    "ASIANPAINT":  "NSE_EQ|INE021A01026",
    "AXISBANK":    "NSE_EQ|INE238A01034",
    "MARUTI":      "NSE_EQ|INE585B01010",
    "TITAN":       "NSE_EQ|INE280A01028",
    "SUNPHARMA":   "NSE_EQ|INE044A01036",
    "WIPRO":       "NSE_EQ|INE075A01022",
    "HCLTECH":     "NSE_EQ|INE860A01027",
    "ADANIENT":    "NSE_EQ|INE423A01024",
    "NTPC":        "NSE_EQ|INE733E01010",
    "POWERGRID":   "NSE_EQ|INE752E01010",
    "ULTRACEMCO":  "NSE_EQ|INE481G01011",
    "NESTLEIND":   "NSE_EQ|INE239A01016",
    "TECHM":       "NSE_EQ|INE669C01036",
    "BAJAJFINSV":  "NSE_EQ|INE918I01026",
    "ONGC":        "NSE_EQ|INE213A01029",
    "JSWSTEEL":    "NSE_EQ|INE019A01038",
    "TATASTEEL":   "NSE_EQ|INE081A01020",
    "TATAMOTORS":  "NSE_EQ|INE306A01021",
    "M&M":         "NSE_EQ|INE101A01026",
    "HINDALCO":    "NSE_EQ|INE038A01020",
    "COALINDIA":   "NSE_EQ|INE522F01014",
    "DIVISLAB":    "NSE_EQ|INE361B01024",
    "DRREDDY":     "NSE_EQ|INE089A01023",
    "CIPLA":       "NSE_EQ|INE059A01026",
    "EICHERMOT":   "NSE_EQ|INE066A01021",
    "GRASIM":      "NSE_EQ|INE047A01021",
    "BPCL":        "NSE_EQ|INE029A01011",
    "INDUSINDBK":  "NSE_EQ|INE095A01012",
    "APOLLOHOSP":  "NSE_EQ|INE437A01024",
    "SBILIFE":     "NSE_EQ|INE123W01016",
    "HDFCLIFE":    "NSE_EQ|INE795G01014",
    "ADANIPORTS":  "NSE_EQ|INE742F01042",
    "TATACONSUM":  "NSE_EQ|INE192A01025",
    "BRITANNIA":   "NSE_EQ|INE216A01030",
    "HEROMOTOCO":  "NSE_EQ|INE158A01026",
    "BAJAJ-AUTO":  "NSE_EQ|INE917I01010",
    "ITC":         "NSE_EQ|INE154A01025",
    "SHRIRAMFIN":  "NSE_EQ|INE721A01013",
    "BEL":         "NSE_EQ|INE263A01024",
}

def _upstox_instrument_key(symbol: str) -> str:
    """Get Upstox instrument key for a symbol. Returns ISIN-based key if known."""
    return UPSTOX_INSTRUMENT_KEYS.get(symbol.upper(), f"NSE_EQ|{symbol.upper()}")

# Correct Upstox interval strings
UPSTOX_INTERVAL_MAP = {
    "1m":  "1minute",  "3m":  "3minute",  "5m":  "5minute",
    "10m": "10minute", "15m": "15minute", "30m": "30minute",
    "1h":  "60minute", "1d":  "day",
    "1wk": "week",     "1mo": "month",
}


def upstox_get_quote(instrument_key: str) -> dict:
    """Live LTP + OHLC via Upstox Market Quote API."""
    if not _upstox_connected():
        return {}
    try:
        r = requests.get(
            f"{UPSTOX_BASE}/market-quote/quotes",
            headers=_upstox_headers(),
            params={"instrument_key": instrument_key},
            timeout=5,
        )
        if r.status_code != 200:
            return {}
        data = r.json().get("data", {})
        q    = data.get(instrument_key) or (list(data.values())[0] if data else {})
        ohlc = q.get("ohlc", {})
        return {
            "ltp":        round(q.get("last_price", 0), 2),
            "open":       round(ohlc.get("open",  0), 2),
            "high":       round(ohlc.get("high",  0), 2),
            "low":        round(ohlc.get("low",   0), 2),
            "close":      round(ohlc.get("close", 0), 2),
            "volume":     q.get("volume", 0),
            "change":     round(q.get("net_change", 0), 2),
            "pct_change": round(q.get("net_change",0)/max(ohlc.get("close",1),1)*100, 2),
        }
    except Exception:
        return {}

def upstox_get_historical(symbol: str, interval: str = "1d",
                           from_date: str = "", to_date: str = "") -> pd.DataFrame:
    """
    Fetch historical OHLCV from Upstox using correct ISIN key + interval.
    Supports: 1m 3m 5m 10m 15m 30m 1h 1d 1wk 1mo
    """
    if not _upstox_connected():
        return pd.DataFrame()

    instrument_key = _upstox_instrument_key(symbol)
    up_interval    = UPSTOX_INTERVAL_MAP.get(interval, "day")

    if not from_date:
        from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")

    url = f"{UPSTOX_BASE}/historical-candle/{instrument_key}/{up_interval}/{to_date}/{from_date}"

    try:
        r = requests.get(url, headers=_upstox_headers(), timeout=15)
        if r.status_code != 200:
            return pd.DataFrame()
        candles = r.json().get("data", {}).get("candles", [])
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles,
                          columns=["Datetime","Open","High","Low","Close","Volume","OI"])
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        df = df.set_index("Datetime").sort_index()
        return df[["Open","High","Low","Close","Volume"]].astype(float)
    except Exception:
        return pd.DataFrame()

def upstox_get_index_quote(yf_ticker: str) -> dict:
    inst_key = UPSTOX_INDEX_KEYS.get(yf_ticker)
    if not inst_key:
        return {}
    return upstox_get_quote(inst_key)

def upstox_get_ltp(symbol: str) -> float:
    """
    Get LTP — Upstox primary feed, yfinance guaranteed fallback.
    NEVER blocks or errors when Upstox token is missing/expired.
    yfinance always provides data so the app stays live on every refresh.
    """
    # Layer 1: Upstox live (only when token present and valid)
    if _upstox_connected():
        try:
            q = upstox_get_quote(_upstox_instrument_key(symbol))
            ltp = q.get("ltp", 0.0)
            if ltp and float(ltp) > 0:
                return round(float(ltp), 2)
        except Exception:
            pass   # silently fall through — never block the app

    # Layer 2: yfinance fast_info (near real-time, always available)
    suffix = "" if is_us_symbol(symbol) else ".NS"
    try:
        fi  = yf.Ticker(symbol + suffix).fast_info
        ltp = float(getattr(fi, "last_price", 0) or
                    getattr(fi, "regularMarketPrice", 0) or 0)
        if ltp > 0:
            return round(ltp, 2)
    except Exception:
        pass

    # Layer 3: yfinance history last close (ultimate fallback)
    try:
        hist = yf.Ticker(symbol + suffix).history(period="2d", interval="1d")
        if not hist.empty:
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = [c[0] for c in hist.columns]
            hist.columns = [str(c).strip().title() for c in hist.columns]
            if "Close" in hist.columns:
                return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 0.0


# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="PivotVault AI",
    layout="wide",
    page_icon="🏦",
    initial_sidebar_state="expanded",
)

# Mobile PWA injection
if _MOBILE_PATCH:
    inject_mobile()

# ─────────────────────────────────────────────
#  CUSTOM CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap');

/* ── GLOBAL ── */
html,body{font-family:'DM Sans',sans-serif !important;background:#f0f4e8 !important;color:#0e1308 !important;}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:#f0f4e8 !important;}
[data-testid="stVerticalBlock"]{background:transparent !important;}
.block-container{background:#f0f4e8 !important;padding:0.3rem 0.75rem 2rem !important;max-width:1440px !important;}
#MainMenu,footer{visibility:hidden !important;}
header[data-testid="stHeader"]{background:transparent !important;border-bottom:none !important;}
section[data-testid="stSidebar"]{display:none !important;}
[data-testid="collapsedControl"]{display:none !important;}
button[data-testid="baseButton-header"]{display:none !important;}

/* ── TYPOGRAPHY ── */
h1,h2,h3,h4{font-family:'DM Sans',sans-serif !important;color:#0e1308 !important;font-weight:700 !important;}
p,span,label,li,td,th,div{font-family:'DM Sans',sans-serif !important;}
code,pre,[class*="mono"]{font-family:'DM Mono',monospace !important;}

/* ── BUTTONS — light olive, NOT dark ── */
.stButton > div > button {
    background    : #ffffff !important;
    border        : 1.5px solid #b8c89a !important;
    color         : #2e3d1a !important;
    font-family   : 'DM Sans',sans-serif !important;
    font-size     : 0.85rem !important;
    font-weight   : 600 !important;
    border-radius : 7px !important;
    padding       : 0.45rem 0.9rem !important;
    min-height    : 38px !important;
    cursor        : pointer !important;
    box-shadow    : none !important;
    transition    : background 0.15s,border-color 0.15s !important;
}
.stButton > div > button:hover {
    background    : #dce8c4 !important;
    border-color  : #638534 !important;
    color         : #1e2c0d !important;
}
.stButton > div > button:active {background:#c8d8a8 !important;}

/* ── INPUTS ── */
input[type="text"],input[type="password"],input[type="number"],
.stTextInput input,.stNumberInput input {
    background:#fff !important;border:1.5px solid #b8c89a !important;
    border-radius:7px !important;color:#0e1308 !important;
    font-family:'DM Mono',monospace !important;font-size:15px !important;min-height:40px !important;
}
input:focus{border-color:#3d5a1c !important;box-shadow:0 0 0 2px rgba(61,90,28,0.15) !important;outline:none !important;}

/* ── SELECTBOX ── */
div[data-baseweb="select"] > div {
    background:#fff !important;border:1.5px solid #b8c89a !important;
    border-radius:7px !important;color:#0e1308 !important;min-height:40px !important;
}
div[data-baseweb="select"] span,div[data-baseweb="select"] div{color:#0e1308 !important;background:transparent !important;}
ul[data-baseweb="menu"],div[data-baseweb="popover"] > div{background:#fff !important;border:1.5px solid #b8c89a !important;border-radius:9px !important;}
li[role="option"]{background:transparent !important;color:#0e1308 !important;font-size:0.85rem !important;min-height:38px !important;}
li[role="option"]:hover{background:#f0f4e8 !important;}
li[aria-selected="true"]{background:#e4f0d0 !important;font-weight:700 !important;}

/* ── METRICS ── */
div[data-testid="metric-container"]{
    background:#fff !important;border:1.5px solid #b8c89a !important;
    border-radius:10px !important;padding:0.85rem 1rem !important;
    border-top:3px solid #638534 !important;
}
div[data-testid="metric-container"] label{font-family:'DM Mono',monospace !important;font-size:0.72rem !important;color:#4a5e32 !important;text-transform:uppercase !important;letter-spacing:0.06em !important;}
div[data-testid="metric-container"] [data-testid="stMetricValue"]{font-family:'DM Mono',monospace !important;font-size:1.4rem !important;font-weight:700 !important;color:#0e1308 !important;}

/* ── TABS ── */
.stTabs [data-baseweb="tab-list"]{background:#e8f0d8 !important;border-bottom:2px solid #b8c89a !important;border-radius:9px 9px 0 0 !important;}
.stTabs [data-baseweb="tab"]{background:transparent !important;border:none !important;color:#4a5e32 !important;font-size:0.85rem !important;font-weight:600 !important;padding:0.6rem 1rem !important;border-bottom:3px solid transparent !important;min-height:42px !important;}
.stTabs [data-baseweb="tab"]:hover{color:#1e2c0d !important;background:rgba(61,90,28,0.05) !important;}
.stTabs [aria-selected="true"]{color:#1e2c0d !important;border-bottom-color:#3d5a1c !important;font-weight:700 !important;}
.stTabs [data-baseweb="tab-panel"]{background:#fff !important;border:1.5px solid #b8c89a !important;border-top:none !important;border-radius:0 0 9px 9px !important;padding:1rem !important;}

/* ── DATAFRAME ── */
[data-testid="stDataFrameContainer"]{background:#fff !important;border:1.5px solid #b8c89a !important;border-radius:9px !important;}

/* ── EXPANDER ── */
[data-testid="stExpander"]{background:#fff !important;border:1.5px solid #b8c89a !important;border-radius:9px !important;}
[data-testid="stExpander"] summary{color:#0e1308 !important;font-weight:600 !important;font-size:0.88rem !important;min-height:42px !important;}

/* ── ALERTS ── */
[data-testid="stInfo"]{background:#e4f0d0 !important;border-left:4px solid #3d5a1c !important;border-radius:7px !important;}
[data-testid="stSuccess"]{background:#e4f5e8 !important;border-left:4px solid #1a6b2e !important;border-radius:7px !important;}
[data-testid="stWarning"]{background:#fdf3d4 !important;border-left:4px solid #7a5800 !important;border-radius:7px !important;}
[data-testid="stError"]{background:#fbe8e6 !important;border-left:4px solid #9e2018 !important;border-radius:7px !important;}

/* ── MULTISELECT ── */
[data-baseweb="tag"]{background:#e4f0d0 !important;border-radius:5px !important;color:#1e2c0d !important;}

/* ── DIVIDERS ── */
hr{border-color:#b8c89a !important;margin:0.75rem 0 !important;}

/* ── ANIMATIONS ── */
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
@keyframes slideIn{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}
.live-dot{display:inline-block;width:8px;height:8px;background:#1a6b2e;border-radius:50%;margin-right:6px;animation:pulse 1.8s infinite;}
.title-bar{display:flex;align-items:center;gap:0.75rem;margin-bottom:1rem;animation:slideIn 0.25s ease;}
.title-bar h1{margin:0 !important;font-size:1.35rem !important;color:#0e1308 !important;font-weight:800 !important;}

/* ── SCROLLBARS ── */
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:#e8f0d8;}
::-webkit-scrollbar-thumb{background:#8da86e;border-radius:4px;}

/* ── MOBILE ── */
@media(max-width:768px){
    .block-container{padding:0.3rem 0.5rem 1rem !important;}
    .stButton > div > button{min-height:44px !important;font-size:0.9rem !important;}
    input{font-size:16px !important;}
}
</style>
""", unsafe_allow_html=True)

# ── PWA: manifest + service worker + install prompt ─────────────────────
st.markdown("""
<link rel="manifest" href="data:application/json;base64,eyJuYW1lIjoiUGl2b3RWYXVsdCBBSSIsInNob3J0X25hbWUiOiJQaXZvdFZhdWx0IiwiZGVzY3JpcHRpb24iOiJDUFIgUGl2b3QgQm9zcyBUcmFkaW5nIEFwcCIsInN0YXJ0X3VybCI6Ii4iLCJkaXNwbGF5Ijoic3RhbmRhbG9uZSIsImJhY2tncm91bmRfY29sb3IiOiIjZjBmNGU4IiwidGhlbWVfY29sb3IiOiIjM2Q1YTFjIiwib3JpZW50YXRpb24iOiJhbnkiLCJpY29ucyI6W3sic3JjIjoiLi9hcHAvc3RhdGljL2ljb24tMTkyLnBuZyIsInNpemVzIjoiMTkyeDE5MiIsInR5cGUiOiJpbWFnZS9wbmcifSx7InNyYyI6Ii4vYXBwL3N0YXRpYy9pY29uLTUxMi5wbmciLCJzaXplcyI6IjUxMng1MTIiLCJ0eXBlIjoiaW1hZ2UvcG5nIn1dfQ==">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="PivotVault AI">
<meta name="theme-color" content="#3d5a1c">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link rel="apple-touch-icon" href="./app/static/icon-192.png">
<script>
(function registerSW() {
    if (!('serviceWorker' in navigator)) return;
    var SW_SRC = `
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil(clients.claim());});
self.addEventListener('fetch',e=>{
    if(e.request.method!=='GET')return;
    e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
});
self.addEventListener('push',e=>{
    var d=e.data?e.data.json():{};
    e.waitUntil(self.registration.showNotification(d.title||'PivotVault AI',{
        body:d.body||'',icon:d.icon||'/app/static/icon-192.png',tag:d.tag||'pv',requireInteraction:false
    }));
});
`;
    var blob = new Blob([SW_SRC],{type:'application/javascript'});
    var swUrl = URL.createObjectURL(blob);
    navigator.serviceWorker.register(swUrl,{scope:'/'}).then(function(reg){
        window.pvSWReg = reg;
        // Store reg globally for push notification use
        window.pvNotify = function(title, body, tag) {
            if(reg.active) {
                reg.active.postMessage({type:'NOTIFY',title:title,body:body,tag:tag});
            } else if(Notification.permission==='granted') {
                new Notification(title,{body:body,icon:'/app/static/icon-192.png',tag:tag});
            }
        };
    }).catch(function(){});
})();

// ── Install prompt banner ────────────────────────────────────────────────────
(function installPrompt() {
    var deferredPrompt = null;
    window.addEventListener('beforeinstallprompt', function(e) {
        e.preventDefault();
        deferredPrompt = e;
        var bar = document.getElementById('pv-install-bar');
        if (bar) bar.style.display = 'flex';
    });
    window.pvInstallApp = function() {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function(r) {
            deferredPrompt = null;
            var bar = document.getElementById('pv-install-bar');
            if (bar) bar.style.display = 'none';
        });
    };
    // Hide bar if already installed (standalone mode)
    if (window.matchMedia('(display-mode: standalone)').matches || navigator.standalone) {
        setTimeout(function() {
            var bar = document.getElementById('pv-install-bar');
            if (bar) bar.style.display = 'none';
        }, 500);
    }
})();
</script>

<!-- Install prompt bar -->
<div id="pv-install-bar" style="display:none;align-items:center;gap:12px;
    background:linear-gradient(90deg,#1a2e0a,#3d6b1a);
    color:#f0f8e8;padding:10px 16px;border-radius:10px;margin-bottom:8px;
    font-family:DM Sans,sans-serif;font-size:0.82rem;font-weight:600;
    box-shadow:0 3px 12px rgba(30,60,10,0.25);">
    <span style="font-size:1.3rem;">📲</span>
    <span style="flex:1;">Install <b>PivotVault AI</b> on your phone for instant access!</span>
    <button onclick="pvInstallApp()" style="background:#5a9a28;color:#fff;border:none;
        border-radius:6px;padding:6px 14px;font-size:0.8rem;font-weight:700;cursor:pointer;">
        ➕ Install App
    </button>
    <button onclick="document.getElementById('pv-install-bar').style.display='none'"
        style="background:transparent;color:#b8d89a;border:none;font-size:1.1rem;cursor:pointer;">✕</button>
</div>
""", unsafe_allow_html=True)


# ── Global notification bootstrap (injected once per page load) ───────────
# Must use window.parent to escape Streamlit's iframe sandbox
st.markdown("""
<script>
(function() {
    // Always work on the TOP window, not the iframe
    var win = window.parent || window;

    // Expose helper functions on parent window so any iframe can call them
    win._pvNotify = function(title, body, tag) {
        if (!("Notification" in win)) return;
        if (win.Notification.permission === "granted") {
            var n = new win.Notification(title, {
                body: body,
                icon: "/static/icon-192.png",
                tag:  tag || "pivotvault",
                requireInteraction: false,
                silent: false,
            });
            n.onclick = function() { win.focus(); n.close(); };
        }
    };

    win._pvRequestNotif = function(cb) {
        if (!("Notification" in win)) {
            if (cb) cb(false);
            return;
        }
        if (win.Notification.permission === "granted") {
            if (cb) cb(true);
            return;
        }
        win.Notification.requestPermission().then(function(p) {
            if (cb) cb(p === "granted");
        });
    };

    // Store permission state on parent
    win._pvNotifEnabled = (
        "Notification" in win &&
        win.Notification.permission === "granted"
    );

    // Auto-request permission after 2s if not yet decided
    if ("Notification" in win && win.Notification.permission === "default") {
        setTimeout(function() {
            win.Notification.requestPermission().then(function(p) {
                win._pvNotifEnabled = (p === "granted");
                if (p === "granted") {
                    new win.Notification("🏦 PivotVault AI", {
                        body: "Trade signal notifications enabled!",
                        icon: "/static/icon-192.png",
                        tag:  "pv-welcome",
                    });
                }
            });
        }, 2000);
    }
})();
</script>
""", unsafe_allow_html=True)

# ── Global notification permission manager ────────────────────────────────
# Injected on every page load — uses window.parent to escape Streamlit iframe
st.markdown("""
<script>
(function initPVNotif() {
    // Must use window.parent to escape Streamlit iframe
    var w = window.parent || window;

    // Store permission state globally
    w._pvNotifReady = false;

    function checkAndRequest() {
        if (!("Notification" in w)) return;
        if (w.Notification.permission === "granted") {
            w._pvNotifReady = true;
            return;
        }
        if (w.Notification.permission === "default") {
            // Auto-request after 1s — browser requires user gesture
            // so we store a flag and show a button instead
            w._pvNeedPermission = true;
        }
    }

    // Global function to fire a notification from anywhere in the app
    w.pvNotify = function(title, body, tag) {
        if (!("Notification" in w)) return;
        if (w.Notification.permission === "granted") {
            try {
                var n = new w.Notification(title, {
                    body: body,
                    icon: "/static/icon-192.png",
                    tag:  tag || "pivotvault",
                    requireInteraction: true,
                    silent: false,
                });
                n.onclick = function() { w.focus(); n.close(); };
            } catch(e) { console.log("Notif error:", e); }
        }
    };

    checkAndRequest();
})();
</script>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
#  SESSION STATE  +  PERSISTENT LOGIN
#  Session survives page refresh via local JSON.
#  Cleared only when user explicitly logs out.
# ─────────────────────────────────────────────

# ── Persistent storage paths — multi-location fallback ───────────────────────
# Primary: app/data/ folder (survives Streamlit Cloud hot reloads)
# Fallback: home dir, /tmp
_APP_DIR   = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR  = os.path.join(_APP_DIR, "data")
try:
    os.makedirs(_DATA_DIR, exist_ok=True)
except Exception:
    _DATA_DIR = os.path.expanduser("~")   # fallback to home if data/ not writable

_SESSION_FILE = os.path.join(_DATA_DIR, "pivotvault_session.json")
_CREDS_FILE   = os.path.join(_DATA_DIR, "pivotvault_creds.json")

def _all_creds_paths():
    return [
        _CREDS_FILE,
        os.path.join(os.path.expanduser("~"), ".pivotvault_creds.json"),
        "/tmp/pivotvault_creds.json",
    ]

def _all_session_paths():
    return [
        _SESSION_FILE,
        os.path.join(os.path.expanduser("~"), ".pivotvault_session.json"),
        "/tmp/pivotvault_session.json",
    ]

def _load_credentials():
    """Load credentials from disk — checks all 3 file locations + st.secrets fallback.
    Restores: Upstox token, broker keys, Telegram config, SL filter, scanner market.
    App stays fully functional on every page refresh without re-entering the token."""
    # ── 1. Try all file locations ─────────────────────────────────────────────
    data = {}
    for path in _all_creds_paths():
        try:
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
                if data:
                    break   # found a valid file — stop looking
        except Exception:
            continue

    if data:
        # Broker keys (excluding token — handled separately below)
        for k in ["upstox_api_key","upstox_api_secret",
                  "zerodha_api_key","zerodha_api_secret","zerodha_access_token",
                  "broker","broker_connected"]:
            if k in data and not st.session_state.get(k):
                st.session_state[k] = data[k]
        # Upstox token — ALWAYS restore from file.
        # Empty string in session_state (after logout/refresh) must NOT block restore.
        # Token is pasted once at 9 AM and must survive logout/refresh all day.
        if data.get("upstox_access_token"):
            st.session_state["upstox_access_token"] = data["upstox_access_token"]
        # Telegram
        if "telegram_cfg" in data and not st.session_state.get("telegram_cfg"):
            st.session_state["telegram_cfg"] = data["telegram_cfg"]
        # SL filter settings
        for k in ["ft_sl_min_pct","ft_sl_max_pct","ft_sl_filter_enabled"]:
            if k in data and k not in st.session_state:
                st.session_state[k] = data[k]
        # Scanner market preference
        for k in ["scanner_market","scanner_market_global"]:
            if k in data and k not in st.session_state:
                st.session_state[k] = data[k]
        # Tab visibility — restore which pages are toggled on
        if data.get("tab_visibility") and "tab_visibility" not in st.session_state:
            st.session_state["tab_visibility"] = data["tab_visibility"]

    # ── 2. st.secrets fallback — wins for Telegram + Upstox keys ─────────────
    # This survives ALL restarts since secrets are stored on Streamlit Cloud
    try:
        _sec = st.secrets
        # Telegram from secrets
        if not st.session_state.get("telegram_cfg") or \
                not st.session_state["telegram_cfg"].get("bot_token"):
            _tg = _sec.get("telegram", {})
            if _tg and _tg.get("bot_token"):
                st.session_state["telegram_cfg"] = {
                    "bot_token":      str(_tg.get("bot_token","")),
                    "chat_id":        str(_tg.get("chat_id","")),
                    "notify_entry":   bool(_tg.get("notify_entry", True)),
                    "notify_t1":      bool(_tg.get("notify_t1",    True)),
                    "notify_t2":      bool(_tg.get("notify_t2",    True)),
                    "notify_sl":      bool(_tg.get("notify_sl",    True)),
                    "notify_signals": bool(_tg.get("notify_signals",True)),
                }
        # Upstox API key/secret from secrets (NOT access token — that's daily)
        _up = _sec.get("upstox", {})
        if _up:
            if _up.get("api_key") and not st.session_state.get("upstox_api_key"):
                st.session_state["upstox_api_key"]    = str(_up["api_key"])
            if _up.get("api_secret") and not st.session_state.get("upstox_api_secret"):
                st.session_state["upstox_api_secret"] = str(_up["api_secret"])
            # Also restore token from secrets if stored there (optional advanced setup)
            if _up.get("access_token") and not st.session_state.get("upstox_access_token"):
                st.session_state["upstox_access_token"] = str(_up["access_token"])
        # App defaults from secrets
        _app = _sec.get("app", {})
        if _app.get("default_balance") and not st.session_state.get("_ft_balance_set"):
            st.session_state["_ft_default_balance"] = float(_app["default_balance"])
    except Exception:
        pass   # st.secrets not available (local dev) — silent fail


def _load_session():
    """
    Load persisted session from disk on every app startup/refresh.
    Force-restores auth state so browser refresh never logs the user out.
    Reads from all 3 storage locations and picks the freshest valid session.
    """
    data = {}
    # Try all session file locations — pick freshest valid one
    for path in _all_session_paths():
        try:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                with open(path) as f:
                    d = json.load(f)
                if d and d.get("logged_in"):  # only restore if it was a logged-in session
                    data = d
                    break
        except Exception:
            continue

    if data:
        # Force-overwrite auth keys — even if defaults already set logged_in=False
        for k in ["logged_in", "username", "user_email", "user_phone",
                  "user_id", "current_page"]:
            if k in data:
                st.session_state[k] = data[k]

    # Always load broker credentials (persisted permanently)
    _load_credentials()


def _save_credentials():
    """Persist broker credentials + Upstox token to ALL storage locations (triple-backup).
    Token is saved so browser refresh / mobile switch never loses it."""
    try:
        data = {k: st.session_state.get(k,"") for k in
                ["upstox_api_key","upstox_api_secret","upstox_access_token",
                 "zerodha_api_key","zerodha_api_secret","zerodha_access_token",
                 "broker","broker_connected",
                 # SL filter settings — persist across sessions
                 "ft_sl_min_pct","ft_sl_max_pct","ft_sl_filter_enabled",
                 # Scanner market preference
                 "scanner_market","scanner_market_global",
                 ]}
        # Persist tab visibility toggles so they survive logout/refresh
        if st.session_state.get("tab_visibility"):
            data["tab_visibility"] = st.session_state["tab_visibility"]
        if st.session_state.get("telegram_cfg"):
            data["telegram_cfg"] = st.session_state["telegram_cfg"]
        data["creds_saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = json.dumps(data)
        for path in _all_creds_paths():
            try:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w") as f:
                    f.write(payload)
            except Exception:
                pass
    except Exception:
        pass


def _upstox_token_expired() -> bool:
    """
    Check if Upstox token is expired by making a lightweight API call.
    Returns True if token needs refresh.
    """
    token = st.session_state.get("upstox_access_token","")
    if not token or not token.startswith("eyJ"):
        return False  # No token — not expired, just not set
    try:
        import base64 as _b64
        # Decode JWT payload (middle part) to check expiry
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1] + "==" * (4 - len(parts[1]) % 4)
            payload     = json.loads(_b64.b64decode(payload_b64).decode())
            exp         = payload.get("exp", 0)
            if exp > 0:
                from datetime import timezone as _tzcheck
                now_ts = datetime.now(_tzcheck.utc).timestamp()
                return now_ts > exp
    except Exception:
        pass
    return False

def _save_session():
    """Persist auth state to all 3 storage locations — survives refresh/restart."""
    try:
        data = {k: st.session_state.get(k,"") for k in
                ["logged_in","username","user_email","user_phone",
                 "user_id","current_page"]}
        payload = json.dumps(data)
        for path in _all_session_paths():
            try:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                with open(path, "w") as f:
                    f.write(payload)
            except Exception:
                pass
        _save_credentials()
    except Exception:
        pass

def _clear_session():
    """Delete persisted session from ALL 3 storage locations on logout."""
    for path in _all_session_paths():
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

defaults = {
    # Auth
    'logged_in':           False,
    'username':            '',
    'user_id':             None,
    'user_email':          '',
    'user_phone':          '',
    'auth_mode':           'login',
    'otp_code':            '',
    'otp_target':          '',
    # Navigation
    'current_page':        'Market Snapshot',
    # Broker / API
    'broker':              'none',
    'zerodha_api_key':     '',
    'zerodha_api_secret':  '',
    'zerodha_access_token':'',
    'upstox_api_key':      '',
    'upstox_api_secret':   '',
    'upstox_access_token': '',
    'broker_connected':    False,
    # Scanner results
    'cpr_scan_df':         None,
    'cpr_scan_15m':        None,
    'cpr_scan_30m':        None,
    'cpr_scan_1h':         None,
    'cpr_scan_1d':         None,
    'cpr_scan_1wk':        None,
    'cpr_scan_1mo':        None,
    'pending_signals':     [],
    'price_alerts':        {},
    'alert_notifications': [],
    # Paper trading (legacy)
    'paper_trades':        [],
    'paper_balance':       10000000.0,   # ₹1 Crore
    'paper_positions':     {},
    # Forward Testing
    '_ft_loaded':          False,
    '_ft':                 {},
    'ft_confirm_reset':    False,
    'ft_low_bal_alert':    False,
    'ft_pending_signal':   None,
    # Live order execution
    'upstox_live_orders':  [],
    'upstox_order_log':    [],
    'upstox_order_preview':None,
    'oe_pending_signal':   None,
    # Watchlist
    'watchlist':           [],
    'wl_data':             {},
    'wl_last_refresh':     None,
    # Misc
    'smtp_cfg':            {"host": "smtp.gmail.com", "port": 587, "sender": "", "password": ""},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
#  DATA HELPERS
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_nse500_list() -> pd.DataFrame:
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame({
            "Symbol": ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
                       "WIPRO", "TATAMOTORS", "SBIN", "AXISBANK", "LT"],
            "Industry": ["Energy", "IT", "IT", "Financial Services", "Financial Services",
                         "IT", "Auto", "Financial Services", "Financial Services", "Construction"],
            "Company Name": ["Reliance Industries", "TCS", "Infosys", "HDFC Bank", "ICICI Bank",
                             "Wipro", "Tata Motors", "SBI", "Axis Bank", "L&T"],
        })


@st.cache_data(ttl=3600)
def fetch_nifty200_list() -> list:
    """Fetch Nifty 200 symbols from NSE. Falls back to hardcoded top-200 subset."""
    url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = df.columns.str.strip()
        return df["Symbol"].dropna().tolist()
    except Exception:
        # Hardcoded Nifty 200 fallback (top liquid stocks)
        return [
            "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL",
            "KOTAKBANK","ITC","LT","AXISBANK","ASIANPAINT","MARUTI","WIPRO","ULTRACEMCO",
            "BAJFINANCE","NESTLEIND","TITAN","SUNPHARMA","POWERGRID","NTPC","TECHM","HCLTECH",
            "TATAMOTORS","ONGC","COALINDIA","JSWSTEEL","TATASTEEL","ADANIPORTS","BAJAJFINSV",
            "HINDALCO","GRASIM","CIPLA","DIVISLAB","DRREDDY","EICHERMOT","BPCL","HEROMOTOCO",
            "BRITANNIA","INDUSINDBK","M&M","APOLLOHOSP","TATACONSUM","PIDILITIND","SIEMENS",
            "DABUR","GODREJCP","BERGEPAINT","HAVELLS","MUTHOOTFIN","LUPIN","BIOCON","TORNTPHARM",
            "BOSCHLTD","COLPAL","MARICO","ICICIPRULI","SBILIFE","HDFCLIFE",
            "SHREECEM","AMBUJACEM","ACC","VEDL","SAIL","NMDC","IOCL","HINDPETRO","PGHL",
            "TATAPOWER","ADANIENT","ADANITRANS","ADANIGREEN",
            "NAUKRI","ZOMATO","PAYTM","DMART","IRCTC","MOTHERSON","BALKRISIND","CONCOR",
            "CHOLAFIN","MANAPPURAM","RECLTD","PFC","CANBK","BANKBARODA","PNB","FEDERALBNK",
            "IDFCFIRSTB","RBLBANK","BANDHANBNK","INDHOTEL","JUBLFOOD","DOMINOS","VOLTAS",
            "WHIRLPOOL","BLUEDART","DELHIVERY","ZYDUSLIFE","ALKEM","AUROPHARMA","CADILAHC",
            "GLENMARK","IPCA","LALPATHLAB","METROPOLIS","THYROCARE","FORTIS","MAXHEALTH",
            "NARAYANA","AARTIIND","DEEPAKNI","SRF","PIDILITIND","AIAENG","CUMMINSIND",
            "THERMAX","ABB","BHEL","BEL","HAL","BEML","MFSL","LICHSGFIN","HDFCAMC","NIPPONLIFE",
            "UTIAMC","ABCAPITAL","ICICIGI","NIACL","GICRE","STARHEALTH","PGHH","EMAMILTD",
            "JYOTHYLAB","VSTIND","RADICO","UNITDSPR","TATACOMM","LTTS","MPHASIS","COFORGE",
            "PERSISTENT","ZENSARTECH","HEXAWARE","KPITTECH","TATAELXSI","INFY","OFSS",
            "RAMCOCEM","JKCEMENT","PRISM","HEIDELBERG","BIRLASOFT","MINDTREE","SRTRANSFIN",
            "SUNDARMFIN","SCUF","AUBANK","UJJIVAN","EQUITAS","SURYODAY","ESAFSFB",
            "CROMPTON","ORIENTELEC","POLYCAB","FINOLEX","KEI","STERLITE","KPIL","NCC","AHLUCONT",
            "PNCINFRA","IRB","SADBHAV","ASHOKA","KNRCON","GPPL","ADANIPORTS",
            "MUNDRAPORT","RITES","IRFC","HUDCO","NBCC","DLF","PRESTIGE","OBEROIRLTY",
            "GODREJPROP","PHOENIXLTD","BRIGADE","SOBHA","SUNTECK","MAHINDCIE","SCHAEFFLER",
        ]


# ══════════════════════════════════════════════════════════════════════════════
#  US MARKET STOCK LISTS — Dow 30 + Nasdaq 100
# ══════════════════════════════════════════════════════════════════════════════

_DOW30_SYMBOLS = [
    "AAPL","AMGN","AXP","BA","CAT","CRM","CSCO","CVX","DIS","DOW",
    "GS","HD","HON","IBM","INTC","JNJ","JPM","KO","MCD","MMM",
    "MRK","MSFT","NKE","PG","TRV","UNH","V","VZ","WBA","WMT",
]

_NASDAQ100_SYMBOLS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","COST",
    "NFLX","AMD","ADBE","PEP","CSCO","TMUS","QCOM","INTC","INTU","AMGN",
    "AMAT","HON","BKNG","VRTX","SBUX","GILD","ADI","PANW","LRCX","MDLZ",
    "REGN","KLAC","SNPS","CDNS","MELI","ASML","CRWD","ABNB","MNST","KDP",
    "ORLY","FTNT","CTAS","CHTR","MRVL","CPRT","ROP","WDAY","DXCM","PCAR",
    "ODFL","PAYX","ROST","AEP","FAST","CEG","IDXX","VRSK","BIIB","ANSS",
    "FANG","EXC","CTSH","DLTR","XEL","EA","BKR","CSGP","GFS","GEHC",
    "ON","ZS","TEAM","DDOG","ALGN","SIRI","WBD","ILMN","TTD","ZM",
    "DOCU","OKTA","PINS","SNAP","UBER","COIN","RBLX","HOOD","SOFI","PLTR",
    "AFRM","DASH","MDB","SNOW","BILL","RIVN","LCID","U","TWLO","OKTA",
]

_NIFTY50_SYMBOLS = [
    "RELIANCE","TCS","HDFCBANK","ICICIBANK","INFY","SBIN","BHARTIARTL",
    "KOTAKBANK","ITC","LT","AXISBANK","ASIANPAINT","MARUTI","WIPRO","ULTRACEMCO",
    "BAJFINANCE","NESTLEIND","TITAN","SUNPHARMA","POWERGRID","NTPC","TECHM","HCLTECH",
    "TATAMOTORS","ONGC","COALINDIA","JSWSTEEL","TATASTEEL","ADANIPORTS","BAJAJFINSV",
    "HINDALCO","GRASIM","CIPLA","DIVISLAB","DRREDDY","EICHERMOT","BPCL","HEROMOTOCO",
    "BRITANNIA","INDUSINDBK","M&M","APOLLOHOSP","TATACONSUM","ADANIENT","HDFCLIFE",
    "SBILIFE","SHRIRAMFIN","BEL","TRENT","WIPRO",
]

# ── Nifty 100 = Nifty 50 + Next 50 most liquid large-caps ────────────────
_NIFTY100_SYMBOLS = _NIFTY50_SYMBOLS + [
    "VEDL","SIEMENS","HAVELLS","PIDILITIND","DABUR","GODREJCP","COLPAL","MARICO",
    "BERGEPAINT","MUTHOOTFIN","CHOLAFIN","RECLTD","PFC","BANKBARODA","CANBK","PNB",
    "FEDERALBNK","IDFCFIRSTB","RBLBANK","BAJAJ-AUTO","HEROMOTOCO","EICHERMOT",
    "BOSCHLTD","MOTHERSON","BALKRISIND","CONCOR","INDHOTEL","JUBLFOOD","VOLTAS",
    "ZOMATO","NAUKRI","DMART","IRCTC","TATACOMM","LTTS","MPHASIS","COFORGE",
    "PERSISTENT","TATAELXSI","OFSS","KPITTECH","ZYDUSLIFE","ALKEM","LUPIN",
    "TORNTPHARM","AUROPHARMA","IPCA","LALPATHLAB","ABB","BHEL","HAL","NHPC",
]

_US_SET = set(_DOW30_SYMBOLS + _NASDAQ100_SYMBOLS)

def is_us_symbol(sym: str) -> bool:
    """True if symbol is a US stock (no .NS suffix needed for yfinance)."""
    return sym.upper() in _US_SET

def get_market_list(market: str) -> list:
    """Return symbol list for selected market toggle.
    Default is NSE 500 (broadest liquid universe for scanning).
    Dow 30 / Nasdaq 100 are available as testing toggles (yfinance, no .NS suffix).
    """
    if market == "🇮🇳 Nifty 50":
        return _NIFTY50_SYMBOLS
    elif market == "🇮🇳 Nifty 100":
        return _NIFTY100_SYMBOLS
    elif market == "🇺🇸 Dow 30":
        return _DOW30_SYMBOLS
    elif market == "🇺🇸 Nasdaq 100":
        return _NASDAQ100_SYMBOLS
    elif market == "🇮🇳 Nifty 200":
        return fetch_nifty200_list()
    elif market == "🇮🇳 NSE 500":
        # Fetch live NSE 500 list; fallback handled inside fetch_nse500_list()
        _df = fetch_nse500_list()
        return _df["Symbol"].dropna().tolist()
    else:
        # default everywhere = NSE 500
        _df = fetch_nse500_list()
        return _df["Symbol"].dropna().tolist()


@st.cache_data(ttl=3600)
def fetch_nifty200_by_marketcap() -> list:
    """
    Returns Nifty 200 symbols sorted by market cap (highest first).
    Fetches market cap from yfinance info in batches.
    Falls back to a pre-ranked hardcoded list if fetch fails.
    """
    # Pre-ranked Nifty 200 by approximate market cap (as of 2025)
    RANKED = [
        "RELIANCE","TCS","HDFCBANK","BHARTIARTL","ICICIBANK","INFY","SBIN","LICI",
        "HINDUNILVR","ITC","LT","BAJFINANCE","HCLTECH","KOTAKBANK","MARUTI","SUNPHARMA",
        "AXISBANK","TITAN","ADANIENT","ADANIPORTS","ASIANPAINT","WIPRO","ULTRACEMCO",
        "NTPC","POWERGRID","NESTLEIND","TATAMOTORS","BAJAJFINSV","JSWSTEEL","TATASTEEL",
        "COALINDIA","ONGC","BPCL","TECHM","HINDALCO","GRASIM","M&M","INDUSINDBK",
        "CIPLA","DRREDDY","DIVISLAB","EICHERMOT","HEROMOTOCO","BRITANNIA",
        "APOLLOHOSP","TATACONSUM","PIDILITIND","SIEMENS","DABUR","GODREJCP","HAVELLS",
        "BERGEPAINT","ICICIPRULI","SBILIFE","HDFCLIFE","SHREECEM","AMBUJACEM","VEDL",
        "SAIL","NMDC","IOCL","HINDPETRO","TATAPOWER","ADANIGREEN","ADANITRANS",
        "NAUKRI","ZOMATO","DMART","IRCTC","CHOLAFIN","RECLTD","PFC","BANKBARODA",
        "CANBK","PNB","FEDERALBNK","IDFCFIRSTB","MUTHOOTFIN","LUPIN","BIOCON",
        "TORNTPHARM","BOSCHLTD","COLPAL","MARICO","INDHOTEL","JUBLFOOD","VOLTAS",
        "MOTHERSON","BALKRISIND","CONCOR","MANAPPURAM","BANDHANBNK","RBLBANK",
        "ZYDUSLIFE","ALKEM","AUROPHARMA","GLENMARK","IPCA","LALPATHLAB","FORTIS",
        "MAXHEALTH","ABB","BHEL","BEL","HAL","BEML","LICHSGFIN","HDFCAMC",
        "NIPPONLIFE","UTIAMC","ABCAPITAL","ICICIGI","NIACL","GICRE","STARHEALTH",
        "PGHH","EMAMILTD","JYOTHYLAB","RADICO","TATACOMM","LTTS","MPHASIS","COFORGE",
        "PERSISTENT","TATAELXSI","OFSS","RAMCOCEM","JKCEMENT","KPITTECH","BIRLASOFT",
        "SRF","DEEPAKNI","AARTIIND","CUMMINSIND","THERMAX","CROMPTON","POLYCAB",
        "KEI","FINOLEX","KPIL","NCC","IRB","DLF","PRESTIGE","OBEROIRLTY",
        "GODREJPROP","PHOENIXLTD","BRIGADE","SOBHA","SCHAEFFLER",
        "ACC","HEIDELBERG","PRISM","UNITDSPR","VSTIND","PAYTM","DELHIVERY",
        "BLUEDART","UJJIVAN","EQUITAS","AUBANK","SRTRANSFIN","SUNDARMFIN",
        "SCUF","ORIENTELEC","NHPC","SJVN","NBCC","HUDCO","IRFC","RITES","GPPL",
        "AHLUCONT","PNCINFRA","KNRCON","ASHOKA","SADBHAV","NAKODA",
        "NARAYANA","METROPOLIS","THYROCARE","LALPATHLAB","PGHL","SUNTECK","MAHINDCIE",
    ]

    # Use pre-ranked list (avoids slow yfinance calls on every load)
    try:
        n200_set = set(fetch_nifty200_list())
        ranked = [s for s in RANKED if s in n200_set]
        extras = [s for s in fetch_nifty200_list() if s not in set(RANKED)]
        return ranked + sorted(extras)
    except Exception:
        return RANKED


@st.cache_data(ttl=60)
def get_market_movers():
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }
        session.get("https://www.nseindia.com", headers=headers, timeout=8)
        time.sleep(0.5)

        def _fetch(endpoint):
            r = session.get(
                f"https://www.nseindia.com/api/live-analysis-variations?index={endpoint}",
                headers=headers, timeout=8,
            )
            r.raise_for_status()
            return r.json()

        def _parse(j):
            data = j.get("NIFTY", {}).get("data", [])
            df = pd.DataFrame(data)
            if df.empty:
                return df
            rename = {}
            for c in df.columns:
                cl = c.lower()
                if "symbol" in cl:                      rename[c] = "Symbol"
                elif "ltp" in cl:                       rename[c] = "LTP"
                elif "net" in cl or "percent" in cl:    rename[c] = "Chg %"
            df = df.rename(columns=rename)
            keep = [c for c in ["Symbol", "LTP", "Chg %"] if c in df.columns]
            return df[keep].head(10)

        return _parse(_fetch("gainers")), _parse(_fetch("loosers"))
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


@st.cache_data(ttl=15)
def fetch_index_data(ticker: str, upstox_token: str = "") -> dict:
    """
    Fetch live index price — dual feed, upstox_token as param (no session_state in cache).
    Priority: Upstox → NSE API → yfinance
    """
    # ── Method 0: Upstox if token provided ────────────────────────────────
    if upstox_token:
        try:
            q = upstox_get_index_quote(ticker)
            if q and q.get("ltp") and float(q.get("ltp",0)) > 0:
                return {
                    "ltp":    q["ltp"],
                    "change": q.get("pct_change", 0),
                    "prev":   q.get("close", 0),
                    "high":   q.get("high", q["ltp"]),
                    "low":    q.get("low",  q["ltp"]),
                    "source": "Upstox",
                }
        except Exception:
            pass

    # NSE API mapping
    NSE_MAP = {
        "^NSEI":    "NIFTY 50",
        "^BSESN":   None,
        "^NSEBANK": "NIFTY BANK",
    }

    # ── Method 1: NSE India API (real-time) ──────────────────────────────
    try:
        nse_name = NSE_MAP.get(ticker)
        if nse_name:
            session = requests.Session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/122 Safari/537.36",
                "Accept": "application/json",
                "Referer": "https://www.nseindia.com/",
                "Accept-Language": "en-US,en;q=0.9",
            }
            # Set cookie first
            session.get("https://www.nseindia.com", headers=headers, timeout=5)
            r = session.get(
                f"https://www.nseindia.com/api/allIndices",
                headers=headers, timeout=5,
            )
            if r.status_code == 200:
                data = r.json().get("data", [])
                for item in data:
                    if item.get("index") == nse_name:
                        ltp  = round(float(item["last"]), 2)
                        prev = round(float(item["previousClose"]), 2)
                        chg  = round(float(item["percentChange"]), 2)
                        return {"ltp": ltp, "change": chg, "prev": prev,
                                "high": round(float(item.get("high", ltp)), 2),
                                "low":  round(float(item.get("low",  ltp)), 2)}
    except Exception:
        pass

    # ── Method 2: yfinance fast_info (near real-time) ─────────────────────
    try:
        fi  = yf.Ticker(ticker).fast_info
        ltp = round(float(fi.last_price), 2)
        prev = round(float(fi.previous_close), 2)
        chg  = round((ltp - prev) / prev * 100, 2) if prev else 0
        return {"ltp": ltp, "change": chg, "prev": prev}
    except Exception:
        pass

    # ── Method 3: yfinance history (delayed ~15 min, last resort) ────────
    try:
        hist = yf.Ticker(ticker).history(period="5d", interval="1m")
        if len(hist) >= 2:
            ltp  = round(float(hist["Close"].iloc[-1]), 2)
            prev = round(float(hist["Close"].iloc[-2]), 2)
            chg  = round((ltp - prev) / prev * 100, 2)
            return {"ltp": ltp, "change": chg}
    except Exception:
        pass

    return {"ltp": None, "change": None}


def refresh_watchlist_prices(symbols: list) -> dict:
    result = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym + ".NS").history(period="2d")
            if len(hist) >= 2:
                ltp  = round(hist["Close"].iloc[-1], 2)
                prev = hist["Close"].iloc[-2]
                chg  = round(((ltp - prev) / prev) * 100, 2)
                result[sym] = {"ltp": ltp, "change": chg}
            elif len(hist) == 1:
                result[sym] = {"ltp": round(hist["Close"].iloc[-1], 2), "change": 0.0}
        except Exception:
            result[sym] = {"ltp": None, "change": None}
    return result


# ─────────────────────────────────────────────
#  PIVOT BOSS — FRANK OCHOA METHODOLOGY
# ─────────────────────────────────────────────

def compute_pivot_points(df: pd.DataFrame, pivot_type: str = "Traditional") -> dict:
    """
    Compute pivot points from prior completed candle.
    Supports: Traditional, Woodie, Camarilla, DeMark, Fibonacci.
    """
    if df.empty or len(df) < 2:
        return {}
    ref  = df.iloc[-2]
    H, L, C, O = ref["High"], ref["Low"], ref["Close"], ref["Open"]
    rng  = H - L
    pivots = {}

    if pivot_type == "Traditional":
        P = (H + L + C) / 3
        pivots = {
            "R3": round(H + 2 * (P - L), 2),
            "R2": round(P + rng, 2),
            "R1": round(2 * P - L, 2),
            "P":  round(P, 2),
            "S1": round(2 * P - H, 2),
            "S2": round(P - rng, 2),
            "S3": round(L - 2 * (H - P), 2),
        }

    elif pivot_type == "Woodie":
        P = (H + L + 2 * C) / 4
        pivots = {
            "R3": round(H + 2 * (P - L), 2),
            "R2": round(P + rng, 2),
            "R1": round(2 * P - L, 2),
            "P":  round(P, 2),
            "S1": round(2 * P - H, 2),
            "S2": round(P - rng, 2),
            "S3": round(L - 2 * (H - P), 2),
        }

    elif pivot_type == "Camarilla":
        P = (H + L + C) / 3
        pivots = {
            "R4": round(C + rng * 1.1 / 2, 2),
            "R3": round(C + rng * 1.1 / 4, 2),
            "R2": round(C + rng * 1.1 / 6, 2),
            "R1": round(C + rng * 1.1 / 12, 2),
            "P":  round(P, 2),
            "S1": round(C - rng * 1.1 / 12, 2),
            "S2": round(C - rng * 1.1 / 6, 2),
            "S3": round(C - rng * 1.1 / 4, 2),
            "S4": round(C - rng * 1.1 / 2, 2),
        }

    elif pivot_type == "DeMark":
        if C < O:
            X = H + 2 * L + C
        elif C > O:
            X = 2 * H + L + C
        else:
            X = H + L + 2 * C
        P = X / 4
        pivots = {
            "R1": round(X / 2 - L, 2),
            "P":  round(P, 2),
            "S1": round(X / 2 - H, 2),
        }

    elif pivot_type == "Fibonacci":
        P = (H + L + C) / 3
        pivots = {
            "R3": round(P + 1.000 * rng, 2),
            "R2": round(P + 0.618 * rng, 2),
            "R1": round(P + 0.382 * rng, 2),
            "P":  round(P, 2),
            "S1": round(P - 0.382 * rng, 2),
            "S2": round(P - 0.618 * rng, 2),
            "S3": round(P - 1.000 * rng, 2),
        }

    return pivots


def compute_cpr(df: pd.DataFrame) -> dict:
    """
    Central Pivot Range (CPR) — Frank Ochoa's core tool.
    Narrow CPR = trending; Wide CPR = range-bound.
    """
    if df.empty or len(df) < 2:
        return {}
    ref  = df.iloc[-2]
    H, L, C = ref["High"], ref["Low"], ref["Close"]
    P  = (H + L + C) / 3
    BC = (H + L) / 2
    TC = (P - BC) + P
    width_pct = abs(TC - BC) / P * 100

    if width_pct < 0.25:
        bias  = "Narrow — Strong Trending Day Expected"
        color = "bull"
    elif width_pct < 0.5:
        bias  = "Moderate — Mild Trend Possible"
        color = "neut"
    else:
        bias  = "Wide — Range-Bound Day Expected"
        color = "bear"

    return {
        "Pivot":  round(P, 2),
        "TC":     round(TC, 2),
        "BC":     round(BC, 2),
        "Width%": round(width_pct, 3),
        "Bias":   bias,
        "Color":  color,
    }


def compute_virgin_cprs(df: pd.DataFrame) -> list:
    """
    Virgin CPRs: Prior CPR bands that price never re-visited.
    These are Ochoa's high-conviction magnet levels.
    """
    result = []
    if len(df) < 3:
        return result
    for i in range(2, min(len(df), 15)):
        ref  = df.iloc[i - 1]
        H, L, C = ref["High"], ref["Low"], ref["Close"]
        P  = (H + L + C) / 3
        BC = (H + L) / 2
        TC = (P - BC) + P
        future  = df.iloc[i:]
        touched = ((future["High"] >= BC) & (future["Low"] <= TC)).any()
        result.append({
            "Date":   df.index[i - 1].strftime("%d-%b"),
            "TC":     round(TC, 2),
            "BC":     round(BC, 2),
            "Virgin": not touched,
        })
    return result


def compute_market_profile(df: pd.DataFrame, bins: int = 60) -> dict:
    """
    Simplified Market Profile: POC, Value Area High, Value Area Low.
    Uses volume-at-price histogram over the full lookback window.
    """
    if df.empty or "Volume" not in df.columns:
        return {}
    try:
        prices, vols = [], []
        for _, row in df.iterrows():
            ticks = np.linspace(row["Low"], row["High"], 10)
            v_per = row["Volume"] / 10
            prices.extend(ticks)
            vols.extend([v_per] * 10)

        counts, edges = np.histogram(prices, bins=bins, weights=vols)
        poc_idx = int(np.argmax(counts))
        poc     = round((edges[poc_idx] + edges[poc_idx + 1]) / 2, 2)

        # Value Area = 70% of total volume centred on POC
        target = counts.sum() * 0.70
        lo = hi = poc_idx
        accum   = counts[poc_idx]
        while accum < target:
            ext_lo = counts[lo - 1] if lo > 0            else 0
            ext_hi = counts[hi + 1] if hi < len(counts)-1 else 0
            if ext_lo == 0 and ext_hi == 0:
                break
            if ext_lo >= ext_hi and lo > 0:
                lo -= 1; accum += counts[lo]
            elif hi < len(counts) - 1:
                hi += 1; accum += counts[hi]
            else:
                lo -= 1; accum += counts[lo]

        vah = round((edges[hi] + edges[hi + 1]) / 2, 2)
        val = round((edges[lo] + edges[lo + 1]) / 2, 2)
        return {"POC": poc, "VAH": vah, "VAL": val}
    except Exception:
        return {}


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    All Pivot Boss indicators:
    - 3/10 Oscillator (Ochoa's momentum signature)
    - HMA-20 (Hull MA for trend)
    - ATR-14
    - RSI-14
    - Stochastic 14,3,3
    """
    df = df.copy()
    close, high, low = df["Close"], df["High"], df["Low"]

    # 3/10 Oscillator ──────────────────────────────────────────────────────────
    df["MA3"]   = close.rolling(3).mean()
    df["MA10"]  = close.rolling(10).mean()
    df["DIFF"]  = df["MA3"] - df["MA10"]
    df["SIG16"] = df["DIFF"].rolling(16).mean()
    df["HIST"]  = df["DIFF"] - df["SIG16"]

    # Hull Moving Average ──────────────────────────────────────────────────────
    def wma(s, n):
        w = np.arange(1, n + 1)
        return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)

    def hma(s, n=20):
        return wma(2 * wma(s, n // 2) - wma(s, n), int(np.sqrt(n)))

    df["HMA20"]  = hma(close, 20)
    df["HMA_UP"] = df["HMA20"] > df["HMA20"].shift(1)

    # ATR ─────────────────────────────────────────────────────────────────────
    df["TR"] = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = df["TR"].rolling(14).mean()

    # RSI ─────────────────────────────────────────────────────────────────────
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    df["RSI14"] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))

    # Stochastic ──────────────────────────────────────────────────────────────
    lo14 = low.rolling(14).min()
    hi14 = high.rolling(14).max()
    df["STOCH_K"] = 100 * (close - lo14) / (hi14 - lo14).replace(0, np.nan)
    df["STOCH_D"] = df["STOCH_K"].rolling(3).mean()

    return df


def full_pivot_boss_analysis(df: pd.DataFrame, pivot_type: str) -> dict:
    """Master analysis: runs all Pivot Boss tools and produces a signal dict."""
    if df.empty or len(df) < 20:
        return {}

    df_ind  = compute_indicators(df)
    pivots  = compute_pivot_points(df, pivot_type)
    cpr     = compute_cpr(df)
    mp      = compute_market_profile(df)
    virgins = compute_virgin_cprs(df)

    last = df_ind.iloc[-1]
    prev = df_ind.iloc[-2]
    ltp  = round(float(last["Close"]), 2)

    # CPR position
    if cpr:
        if   ltp > cpr["TC"]: cpr_pos, cpr_col = "Bullish (Above CPR)",    "bull"
        elif ltp < cpr["BC"]: cpr_pos, cpr_col = "Bearish (Below CPR)",    "bear"
        else:                 cpr_pos, cpr_col = "Inside CPR (Neutral)",   "neut"
    else:
        cpr_pos, cpr_col = "N/A", "neut"

    # Nearest pivot
    nearest = None
    if pivots:
        nearest = min(pivots.items(), key=lambda kv: abs(ltp - kv[1]))

    # 3/10 Oscillator signal
    d_now, d_prev = float(last["DIFF"]),  float(prev["DIFF"])
    s_now, s_prev = float(last["SIG16"]), float(prev["SIG16"])
    if   d_now > s_now and d_prev <= s_prev: osc_sig, osc_col = "Bullish Crossover ▲", "bull"
    elif d_now < s_now and d_prev >= s_prev: osc_sig, osc_col = "Bearish Crossover ▼", "bear"
    elif d_now > 0:                          osc_sig, osc_col = "Positive Momentum",   "bull"
    elif d_now < 0:                          osc_sig, osc_col = "Negative Momentum",   "bear"
    else:                                    osc_sig, osc_col = "Neutral",              "neut"

    # HMA
    hma_up = bool(last["HMA_UP"])
    hma_sig, hma_col = ("Uptrend ▲", "bull") if hma_up else ("Downtrend ▼", "bear")

    # RSI
    rsi = round(float(last["RSI14"]), 1) if not np.isnan(last["RSI14"]) else None
    if rsi:
        if   rsi >= 70: rsi_sig, rsi_col = "Overbought", "bear"
        elif rsi <= 30: rsi_sig, rsi_col = "Oversold",   "bull"
        else:           rsi_sig, rsi_col = "Neutral",    "neut"
    else:
        rsi_sig, rsi_col = "N/A", "neut"

    # Stochastic
    stk = round(float(last["STOCH_K"]), 1) if not np.isnan(last["STOCH_K"]) else None
    std = round(float(last["STOCH_D"]), 1) if not np.isnan(last["STOCH_D"]) else None

    # ATR
    atr     = round(float(last["ATR14"]), 2) if not np.isnan(last["ATR14"]) else None
    atr_pct = round(atr / ltp * 100, 2) if atr else None

    # Overall bias
    bull_n = sum([cpr_col == "bull", osc_col == "bull", hma_col == "bull", rsi_col == "bull"])
    bear_n = sum([cpr_col == "bear", osc_col == "bear", hma_col == "bear", rsi_col == "bear"])
    if   bull_n >= 3: overall, ov_col = "BULLISH",        "bull"
    elif bear_n >= 3: overall, ov_col = "BEARISH",        "bear"
    else:             overall, ov_col = "NEUTRAL / MIXED", "neut"

    return dict(
        ltp=ltp, pivots=pivots, cpr=cpr,
        cpr_position=cpr_pos, cpr_col=cpr_col,
        market_profile=mp, virgin_cprs=virgins,
        osc_sig=osc_sig, osc_col=osc_col,
        hma_sig=hma_sig, hma_col=hma_col,
        rsi=rsi, rsi_sig=rsi_sig, rsi_col=rsi_col,
        stoch_k=stk, stoch_d=std,
        atr=atr, atr_pct=atr_pct,
        nearest=nearest,
        overall=overall, ov_col=ov_col,
        df_ind=df_ind,
    )


# ─────────────────────────────────────────────
#  CHART BUILDERS
# ─────────────────────────────────────────────
def build_pivot_boss_chart(df: pd.DataFrame, symbol: str,
                            analysis: dict, pivot_type: str) -> go.Figure:
    """
    4-panel Pivot Boss chart:
    Row 1 (55%): Candles + HMA + Pivot levels + CPR band + POC/VAH/VAL
    Row 2 (18%): 3/10 Oscillator (histogram + Diff + Signal)
    Row 3 (14%): RSI-14
    Row 4 (13%): Volume
    """
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.18, 0.14, 0.13],
        vertical_spacing=0.02,
    )
    df_ind = analysis.get("df_ind", df)
    pivots = analysis.get("pivots", {})
    cpr    = analysis.get("cpr", {})
    mp     = analysis.get("market_profile", {})

    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Price",
        increasing_line_color="#00e5a0", decreasing_line_color="#ff4d6a",
        increasing_fillcolor="rgba(0,229,160,0.15)", decreasing_fillcolor="rgba(255,77,106,0.15)",
        line=dict(width=1), showlegend=False,
    ), row=1, col=1)

    # HMA
    if "HMA20" in df_ind.columns:
        fig.add_trace(go.Scatter(
            x=df_ind.index, y=df_ind["HMA20"],
            name="HMA(20)", line=dict(color="#4d7cfe", width=1.5, dash="dot"),
        ), row=1, col=1)

    # CPR band
    if cpr:
        x0, x1 = df.index[0], df.index[-1]
        fig.add_trace(go.Scatter(
            x=[x0, x1, x1, x0], y=[cpr["TC"], cpr["TC"], cpr["BC"], cpr["BC"]],
            fill="toself", fillcolor="rgba(29,78,216,0.05)",
            line=dict(color="rgba(77,124,254,0)", width=0),
            name="CPR Band", showlegend=True, mode="lines",
        ), row=1, col=1)
        for label, val, col in [("TC", cpr["TC"], "#4d7cfe"),
                                  ("P",  cpr["Pivot"], "#aab4d4"),
                                  ("BC", cpr["BC"], "#4d7cfe")]:
            fig.add_hline(y=val, line=dict(color=col, width=1, dash="dash"),
                          annotation_text=f"  {label} {val}",
                          annotation_font=dict(size=9, color=col), row=1, col=1)

    # Pivot levels
    color_map = {
        "R1": "#ff8c69", "R2": "#ff6b6b", "R3": "#ff4d6a", "R4": "#cc2e47",
        "S1": "#69ffb8", "S2": "#3dffa0", "S3": "#00e5a0", "S4": "#00b880",
    }
    for k, v in pivots.items():
        if k == "P":
            continue
        c = color_map.get(k, "#888")
        fig.add_hline(y=v, line=dict(color=c, width=0.8, dash="dot"),
                      annotation_text=f"  {k} {v}",
                      annotation_font=dict(size=9, color=c), row=1, col=1)

    # Market Profile
    for k, v, c in [("POC", mp.get("POC"), "#f5a623"),
                    ("VAH", mp.get("VAH"), "#b0b8d0"),
                    ("VAL", mp.get("VAL"), "#b0b8d0")]:
        if v:
            fig.add_hline(y=v, line=dict(color=c, width=1.2, dash="longdash"),
                          annotation_text=f"  {k} {v}",
                          annotation_font=dict(size=9, color=c), row=1, col=1)

    # 3/10 Oscillator
    if "HIST" in df_ind.columns:
        hist_vals   = df_ind["HIST"].fillna(0)
        hist_colors = ["#00e5a0" if v >= 0 else "#ff4d6a" for v in hist_vals]
        fig.add_trace(go.Bar(
            x=df_ind.index, y=hist_vals,
            marker_color=hist_colors, opacity=0.65, showlegend=False,
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df_ind.index, y=df_ind["DIFF"],
            name="Diff(3-10)", line=dict(color="#00e5a0", width=1.2),
        ), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=df_ind.index, y=df_ind["SIG16"],
            name="Signal(16)", line=dict(color="#f5a623", width=1.2, dash="dot"),
        ), row=2, col=1)
        fig.add_hline(y=0, line=dict(color="#1e2330", width=1), row=2, col=1)

    # RSI
    if "RSI14" in df_ind.columns:
        fig.add_trace(go.Scatter(
            x=df_ind.index, y=df_ind["RSI14"],
            name="RSI(14)", line=dict(color="#4d7cfe", width=1.2), showlegend=False,
        ), row=3, col=1)
        for level, color in [(70, "rgba(220,38,38,0.15)"), (30, "rgba(22,163,74,0.15)"), (50, "#1e2330")]:
            fig.add_hline(y=level, line=dict(color=color, width=0.8, dash="dot"), row=3, col=1)

    # Volume
    vol_colors = ["#00e5a0" if c >= o else "#ff4d6a"
                  for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker_color=vol_colors, opacity=0.55, showlegend=False,
    ), row=4, col=1)

    # Layout — clean, professional light theme
    fig.update_layout(
        height=820,
        paper_bgcolor="#ffffff",
        plot_bgcolor="#fafbfc",
        font=dict(family="IBM Plex Mono", color="#5a6a80", size=10),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0,
            font=dict(size=9, color="#1a2332"),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#dce3ed", borderwidth=1,
        ),
        margin=dict(l=10, r=100, t=40, b=10),
        xaxis_rangeslider_visible=False,
        title=dict(
            text=f"<b>{symbol}</b>  ·  {pivot_type} Pivots",
            font=dict(family="IBM Plex Mono", size=13, color="#1a2332"),
            x=0.01,
        ),
        shapes=[],   # clean baseline
    )
    # Shared axis styling
    axis_style = dict(
        showgrid=True, gridcolor="#eef0f4", gridwidth=1,
        showline=True, linecolor="#dce3ed", linewidth=1,
        zeroline=False, tickfont=dict(size=9, color="#8a9ab0"),
        ticks="outside", ticklen=3,
    )
    for i in range(1, 5):
        fig.update_xaxes(**axis_style, row=i, col=1)
        fig.update_yaxes(**axis_style, row=i, col=1)
    # Row labels
    fig.update_yaxes(title_text="3/10 OSC", title_font=dict(size=8, color="#8a9ab0"), row=2, col=1)
    fig.update_yaxes(title_text="RSI 14",   title_font=dict(size=8, color="#8a9ab0"), row=3, col=1)
    fig.update_yaxes(title_text="Volume",   title_font=dict(size=8, color="#8a9ab0"), row=4, col=1)
    # Add subtle row separator lines
    for row_y in [0.55, 0.73, 0.87]:
        fig.add_hline(y=0, line=dict(color="#eef0f4", width=1))
    return fig


def build_stoch_chart(df_ind: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["STOCH_K"],
                             name="%K", line=dict(color="#00e5a0", width=1.2)))
    fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["STOCH_D"],
                             name="%D", line=dict(color="#f5a623", width=1.2, dash="dot")))
    for level, color in [(80, "rgba(220,38,38,0.15)"), (20, "rgba(22,163,74,0.15)"), (50, "#1e2330")]:
        fig.add_hline(y=level, line=dict(color=color, width=0.8, dash="dot"))
    fig.update_layout(
        height=200, paper_bgcolor="#f0f4f8", plot_bgcolor="#ffffff",
        font=dict(family="IBM Plex Mono", color="#475569", size=10),
        margin=dict(l=0, r=60, t=28, b=0),
        legend=dict(orientation="h", font=dict(size=10), bgcolor="rgba(255,255,255,0.9)"),
        title=dict(text="Stochastic (14, 3, 3)", font=dict(size=11, color="#d4daf0")),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e2e8f0")
    fig.update_yaxes(showgrid=True, gridcolor="#e2e8f0")
    return fig


# ─────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────

def render_lw_chart(symbol: str, tf_label: str, analysis: dict,
                    pivot_type: str, height: int = 660):
    """
    TradingView Lightweight Charts v4.1.1 (free, open-source — unpkg CDN).
    Renders a professional candlestick chart with:
    - Live OHLCV data from yfinance
    - CPR band (TC/P/BC) as horizontal lines
    - All pivot levels (R1/R2/R3/S1/S2/S3)
    - Market Profile (POC/VAH/VAL)
    - Volume bars
    - Overall bias header
    """
    import json

    # ── Get price data ────────────────────────────────────────────────────
    TF_MAP = {
        "5 Min":   ("5d",  "5m"),
        "15 Min":  ("10d", "15m"),
        "30 Min":  ("20d", "30m"),
        "1 Hour":  ("60d", "1h"),
        "4 Hour":  ("90d", "1h"),
        "Daily":   ("1y",  "1d"),
        "Weekly":  ("5y",  "1wk"),
        "Monthly": ("10y", "1mo"),
    }
    period, interval = TF_MAP.get(tf_label, ("1y","1d"))

    try:
        df_raw = yf.Ticker(symbol + ".NS").history(period=period, interval=interval)
        df_raw.index = df_raw.index.tz_localize(None)
        if df_raw.empty or len(df_raw) < 5:
            st.warning("No price data available.")
            return
    except Exception as e:
        st.error(f"Data error: {e}")
        return

    # ── Build candlestick data (LW Charts format) ─────────────────────────
    candles = []
    volumes = []
    for ts, row in df_raw.iterrows():
        t = int(ts.timestamp())
        candles.append({
            "time": t,
            "open":  round(float(row["Open"]),  2),
            "high":  round(float(row["High"]),  2),
            "low":   round(float(row["Low"]),   2),
            "close": round(float(row["Close"]), 2),
        })
        volumes.append({
            "time":  t,
            "value": int(row["Volume"]),
            "color": "#16a34a44" if float(row["Close"]) >= float(row["Open"]) else "#dc262644",
        })

    # ── Pivot & CPR levels ────────────────────────────────────────────────
    cpr     = analysis.get("cpr", {})
    pivots  = analysis.get("pivots", {})
    mp      = analysis.get("market_profile", {})
    ltp     = analysis.get("ltp", 0)
    overall = analysis.get("overall", "NEUTRAL")
    ov_col  = analysis.get("ov_col", "neut")
    bias_color = {"bull":"#16a34a","bear":"#dc2626","neut":"#d97706"}.get(ov_col,"#888")

    # Build price lines config for LW Charts
    price_lines = []

    PIVOT_COLORS = {
        "R3":"#ff2222","R2":"#ff5555","R1":"#ff9999",
        "P":"#888888",
        "S1":"#99ff99","S2":"#55ff55","S3":"#22ff22",
        "R4":"#cc0000","S4":"#00cc00",
    }

    for k, v in pivots.items():
        price_lines.append({
            "price": v, "color": PIVOT_COLORS.get(k,"#888888"),
            "lineWidth": 1, "lineStyle": 1,
            "axisLabelVisible": True,
            "title": k,
        })

    if cpr:
        price_lines.append({"price": cpr.get("TC",0),    "color":"#4d7cfe","lineWidth":2,"lineStyle":0,"axisLabelVisible":True,"title":"TC"})
        price_lines.append({"price": cpr.get("Pivot",0), "color":"#8899bb","lineWidth":1,"lineStyle":1,"axisLabelVisible":True,"title":"P"})
        price_lines.append({"price": cpr.get("BC",0),    "color":"#4d7cfe","lineWidth":2,"lineStyle":0,"axisLabelVisible":True,"title":"BC"})

    if mp:
        price_lines.append({"price": mp.get("POC",0), "color":"#f5a623","lineWidth":2,"lineStyle":2,"axisLabelVisible":True,"title":"POC"})
        price_lines.append({"price": mp.get("VAH",0), "color":"#94a3b8","lineWidth":1,"lineStyle":2,"axisLabelVisible":True,"title":"VAH"})
        price_lines.append({"price": mp.get("VAL",0), "color":"#94a3b8","lineWidth":1,"lineStyle":2,"axisLabelVisible":True,"title":"VAL"})

    # ── Serialize to JSON ─────────────────────────────────────────────────
    candles_json     = json.dumps(candles)
    volumes_json     = json.dumps(volumes)
    price_lines_json = json.dumps(price_lines)

    # CPR band fill
    tc_val = cpr.get("TC", 0)
    bc_val = cpr.get("BC", 0)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#f7f9f2; font-family:'IBM Plex Mono',monospace; }}

.hdr {{
    display:flex; align-items:center; justify-content:space-between;
    padding:8px 14px; background:#ffffff;
    border-bottom:1px solid #dce3ed;
}}
.hdr-left {{ display:flex; align-items:baseline; gap:10px; }}
.sym {{ font-size:1rem; font-weight:700; color:#1a1f0e; }}
.tf  {{ font-size:0.72rem; color:#5a6a48; }}
.ltp {{ font-size:0.9rem; font-weight:600; color:#1a1f0e; }}
.bias {{
    background:{bias_color}18; color:{bias_color};
    border:1px solid {bias_color}44;
    border-radius:4px; padding:3px 10px;
    font-size:0.7rem; font-weight:700; letter-spacing:0.06em;
}}

.legend {{
    display:flex; flex-wrap:wrap; gap:8px;
    padding:5px 14px; background:#ffffff;
    border-bottom:1px solid #eef0f4;
    font-size:0.65rem;
}}
.leg-item {{ display:flex; align-items:center; gap:4px; color:#5a6a48; }}
.leg-dot  {{ width:10px; height:3px; border-radius:2px; flex-shrink:0; }}

#chart {{ width:100%; height:{height}px; }}
</style>
</head>
<body>

<div class="hdr">
  <div class="hdr-left">
    <span class="sym">{symbol}</span>
    <span class="tf">{tf_label} · {pivot_type}</span>
    <span class="ltp">₹{ltp:,.2f}</span>
  </div>
  <span class="bias">{overall}</span>
</div>

<div class="legend">
  <div class="leg-item"><div class="leg-dot" style="background:#4d7cfe;height:2px;"></div>CPR Band</div>
  <div class="leg-item"><div class="leg-dot" style="background:#ff5555;"></div>Resistance</div>
  <div class="leg-item"><div class="leg-dot" style="background:#55ff55;"></div>Support</div>
  <div class="leg-item"><div class="leg-dot" style="background:#f5a623;"></div>POC</div>
  <div class="leg-item"><div class="leg-dot" style="background:#94a3b8;"></div>Value Area</div>
</div>

<div id="chart"></div>

<script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
<script>
const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
    width:  document.getElementById('chart').clientWidth,
    height: {height},
    layout: {{
        background:  {{ type: 'solid', color: '#ffffff' }},
        textColor:   '#5a6a80',
        fontSize:    11,
        fontFamily:  "'IBM Plex Mono', monospace",
    }},
    grid: {{
        vertLines:  {{ color: '#f0f2f5', style: 1 }},
        horzLines:  {{ color: '#f0f2f5', style: 1 }},
    }},
    crosshair: {{
        mode: LightweightCharts.CrosshairMode.Normal,
        vertLine:  {{ color: '#1a6b3c44', width: 1, style: 1, labelBackgroundColor: '#1a6b3c' }},
        horzLine:  {{ color: '#1a6b3c44', width: 1, style: 1, labelBackgroundColor: '#1a6b3c' }},
    }},
    rightPriceScale: {{
        borderColor: '#dce3ed',
        scaleMargins: {{ top: 0.05, bottom: 0.25 }},
    }},
    timeScale: {{
        borderColor:     '#dce3ed',
        timeVisible:     true,
        secondsVisible:  false,
        barSpacing:      8,
    }},
    localization: {{
        priceFormatter: p => '\u20b9' + p.toFixed(2),
    }},
}});

// ── Candlestick series ─────────────────────────────────────────────
const candleSeries = chart.addCandlestickSeries({{
    upColor:           '#16a34a',
    downColor:         '#dc2626',
    borderUpColor:     '#16a34a',
    borderDownColor:   '#dc2626',
    wickUpColor:       '#16a34a',
    wickDownColor:     '#dc2626',
}});
candleSeries.setData({candles_json});

// ── Add pivot + CPR price lines ────────────────────────────────────
const priceLines = {price_lines_json};
priceLines.forEach(function(pl) {{
    if (pl.price && pl.price > 0) {{
        candleSeries.createPriceLine(pl);
    }}
}});

// ── CPR band shading ───────────────────────────────────────────────
// Draw as a band between TC and BC using two area series
const tcVal = {tc_val};
const bcVal = {bc_val};
if (tcVal > 0 && bcVal > 0) {{
    const cprBandUpper = chart.addLineSeries({{
        color: 'rgba(77,124,254,0.5)',
        lineWidth: 2,
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
    }});
    const cprBandLower = chart.addLineSeries({{
        color: 'rgba(77,124,254,0.5)',
        lineWidth: 2,
        lineStyle: 0,
        priceLineVisible: false,
        lastValueVisible: false,
    }});
    const allTimes = {candles_json}.map(c => c.time);
    cprBandUpper.setData(allTimes.map(t => ({{ time: t, value: tcVal }})));
    cprBandLower.setData(allTimes.map(t => ({{ time: t, value: bcVal }})));
}}

// ── Volume series (bottom pane) ────────────────────────────────────
const volSeries = chart.addHistogramSeries({{
    priceFormat:      {{ type: 'volume' }},
    priceScaleId:     'volume',
    scaleMargins:     {{ top: 0.8, bottom: 0 }},
}});
volSeries.priceScale().applyOptions({{
    scaleMargins: {{ top: 0.8, bottom: 0 }},
}});
volSeries.setData({volumes_json});

// ── Responsive resize ──────────────────────────────────────────────
new ResizeObserver(entries => {{
    for (const entry of entries) {{
        const {{ width, height }} = entry.contentRect;
        chart.applyOptions({{ width, height }});
    }}
}}).observe(document.getElementById('chart'));

// Fit content on load
chart.timeScale().fitContent();

// ── Crosshair tooltip ─────────────────────────────────────────────
const tooltip = document.createElement('div');
tooltip.style.cssText = 'position:absolute;top:50px;left:14px;z-index:99;background:#1e293b;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:0.7rem;pointer-events:none;line-height:1.6;display:none;';
document.body.appendChild(tooltip);

chart.subscribeCrosshairMove(param => {{
    if (!param.time || !param.seriesData.has(candleSeries)) {{
        tooltip.style.display = 'none';
        return;
    }}
    const d = param.seriesData.get(candleSeries);
    const chg = d.close - d.open;
    const pct  = ((chg / d.open) * 100).toFixed(2);
    const col  = chg >= 0 ? '#16a34a' : '#dc2626';
    tooltip.style.display = 'block';
    tooltip.innerHTML =
        '<span style="color:#8a9a78;">O</span> ₹' + d.open.toLocaleString('en-IN', {{minimumFractionDigits:2}}) + ' &nbsp;' +
        '<span style="color:#8a9a78;">H</span> ₹' + d.high.toLocaleString('en-IN', {{minimumFractionDigits:2}}) + ' &nbsp;' +
        '<span style="color:#8a9a78;">L</span> ₹' + d.low.toLocaleString('en-IN', {{minimumFractionDigits:2}}) + ' &nbsp;' +
        '<span style="color:#8a9a78;">C</span> <b style="color:' + col + ';">₹' + d.close.toLocaleString('en-IN', {{minimumFractionDigits:2}}) + '</b>' +
        ' <span style="color:' + col + ';">(' + (chg >= 0 ? '+' : '') + pct + '%)</span>';
}});
</script>
</body>
</html>"""

    _stc.html(html, height=height + 75, scrolling=False)


def sig_badge(label: str, kind: str) -> str:
    css = {"bull": "sig-bull", "bear": "sig-bear", "neut": "sig-neut"}.get(kind, "sig-neut")
    return f'<span class="signal-badge {css}">{label}</span>'


# ── Market hours (India + USA) ─────────────────────────────────────────────────
#  NSE  : Mon–Fri  09:15–15:30 IST  (UTC+5:30)
#  NYSE/NASDAQ: Mon–Fri  09:30–16:00 EST  (UTC-5) / EDT (UTC-4, Mar–Nov)
# ───────────────────────────────────────────────────────────────────────────────

def _ist_now():
    from datetime import timezone as _tz
    return datetime.now(_tz(timedelta(hours=5, minutes=30)))

def _est_now():
    """Return current time in US Eastern — auto-adjusts for EDT/EST."""
    import time as _time
    # DST: 2nd Sun Mar → 1st Sun Nov  → EDT (UTC-4); else EST (UTC-5)
    from datetime import timezone as _tz
    now_utc = datetime.now(_tz.utc)
    # Determine offset: EDT = -4, EST = -5
    year = now_utc.year
    # 2nd Sunday of March
    mar1  = datetime(year, 3, 1)
    dst_start = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    # 1st Sunday of November
    nov1  = datetime(year, 11, 1)
    dst_end   = nov1  + timedelta(days=(6 - nov1.weekday())  % 7)
    utc_naive = now_utc.replace(tzinfo=None)
    in_dst    = dst_start <= utc_naive < dst_end
    offset    = timedelta(hours=-4 if in_dst else -5)
    return datetime.now(_tz(offset))

def is_market_open(market: str = "india") -> bool:
    """
    Check if market is open.
    market: 'india'  → NSE   Mon–Fri 09:15–15:30 IST
            'us'     → NYSE  Mon–Fri 09:30–16:00 EST/EDT
    """
    if market == "us":
        now = _est_now()
        if now.weekday() >= 5: return False
        o = now.replace(hour=9,  minute=30, second=0, microsecond=0)
        c = now.replace(hour=16, minute=0,  second=0, microsecond=0)
        return o <= now <= c
    else:  # india (default)
        now = _ist_now()
        if now.weekday() >= 5: return False
        o = now.replace(hour=9,  minute=15, second=0, microsecond=0)
        c = now.replace(hour=15, minute=30, second=0, microsecond=0)
        return o <= now <= c

def is_auto_trade_open(market: str = "india") -> bool:
    """
    Safe auto-trade window (avoids volatile open + pre-close).
    India: 09:45–14:45 IST  |  US: 09:45–15:45 EST/EDT
    """
    if market == "us":
        now = _est_now()
        if now.weekday() >= 5: return False
        o = now.replace(hour=9,  minute=45, second=0, microsecond=0)
        c = now.replace(hour=15, minute=45, second=0, microsecond=0)
        return o <= now <= c
    else:
        now = _ist_now()
        if now.weekday() >= 5: return False
        # Optimal window: skip first 15 min volatility + last 30 min pre-close
        # 09:45–14:45 IST — Frank Ochoa's highest probability trading window
        o = now.replace(hour=9,  minute=45, second=0, microsecond=0)
        c = now.replace(hour=14, minute=45, second=0, microsecond=0)
        return o <= now <= c

def get_market_status(market: str = "india") -> dict:
    """
    Returns full status dict for market header display.
    market: 'india' or 'us'
    """
    if market == "us":
        now      = _est_now()
        tz_label = "EDT" if abs(now.utcoffset().total_seconds()/3600 + 4) < 0.1 else "EST"
        is_open  = is_market_open("us")
        wday     = now.weekday()
        if is_open:
            closes = now.replace(hour=16, minute=0, second=0, microsecond=0)
            mins   = int((closes - now).total_seconds() // 60)
            note   = f"🟢 NYSE/NASDAQ OPEN · Closes {closes.strftime('%I:%M %p')} {tz_label} · {mins}m left"
        else:
            if wday >= 5:   note = f"🔴 US Market CLOSED · Opens Monday 9:30 AM {tz_label}"
            elif now.hour < 9 or (now.hour == 9 and now.minute < 30):
                             note = f"🔴 Pre-Market · Opens 9:30 AM {tz_label} today"
            else:            note = f"🔴 US Market CLOSED · Opens tomorrow 9:30 AM {tz_label}"
        return {"open": is_open, "note": note, "time": now.strftime(f"%d %b %Y  %H:%M {tz_label}"), "tz": tz_label}
    else:
        now      = _ist_now()
        is_open  = is_market_open("india")
        wday     = now.weekday()
        if is_open:
            closes = now.replace(hour=15, minute=30, second=0, microsecond=0)
            mins   = int((closes - now).total_seconds() // 60)
            note   = f"🟢 NSE OPEN · Closes 3:30 PM IST · {mins}m left"
        else:
            if wday >= 5:   note = "🔴 NSE CLOSED · Opens Monday 9:15 AM IST"
            elif now.hour < 9 or (now.hour == 9 and now.minute < 15):
                             note = "🔴 Pre-Market · Opens 9:15 AM IST today"
            else:            note = "🔴 NSE CLOSED · Opens tomorrow 9:15 AM IST"
        return {"open": is_open, "note": note, "time": now.strftime("%d %b %Y  %H:%M IST"), "tz": "IST"}



def _show_token_refresh_popup():
    """Show optional Upstox token refresh — non-blocking info banner.
    App continues working via yfinance even without token.
    Token is optional — only needed for faster live data and real order execution.
    """
    if not st.session_state.get("logged_in"):
        return

    # Only show if user has saved API keys (means they intentionally set up Upstox)
    # but the token is now expired/missing. Don't show to users who never set Upstox up.
    api_key = st.session_state.get("upstox_api_key", "")
    if not api_key:
        return  # User never configured Upstox — no popup needed, yfinance just works

    token_expired = not _upstox_connected() or _upstox_token_expired()
    if not token_expired:
        return  # Token is fine — no popup needed

    # Non-blocking collapsible banner (not a page blocker)
    with st.expander("📡 Upstox token expired — click to refresh (optional, yfinance is live)", expanded=False):
        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:0.76rem;color:#4a5e32;"
            "padding:0.3rem 0;'>"
            "Your Upstox token has expired. The app continues working with yfinance data (15-min delay). "
            "Paste today's token below to restore real-time Upstox feed and live order execution."
            "</div>",
            unsafe_allow_html=True,
        )
        col1, col2 = st.columns([4, 1])
        with col1:
            new_token = st.text_input(
                "Paste new Upstox access token",
                key="token_refresh_input",
                type="password",
                placeholder="eyJ0eXAiOiJKV1Qi...",
                label_visibility="collapsed",
            )
        with col2:
            if st.button("✅ Activate", key="token_refresh_btn", use_container_width=True):
                t = (new_token or "").strip()
                if t and t.startswith("eyJ") and len(t) > 100:
                    st.session_state["upstox_access_token"] = t
                    st.session_state["broker_connected"]    = True
                    st.session_state["upstox_token_expired"]= False
                    _save_credentials()
                    st.cache_data.clear()
                    st.success("✅ Token updated! Live Upstox feed restored.")
                    st.rerun()
                else:
                    st.error("Invalid token. Must start with 'eyJ' and be 500+ characters.")


def _check_daily_token_reminder():
    """
    Send Telegram reminder at 9:00 AM IST on weekdays to update Upstox token.
    - Only fires Mon–Fri
    - Only once per calendar day
    - Skips if token is already valid
    - Skips if Telegram not configured
    """
    from datetime import timezone as _tz
    IST   = _tz(timedelta(hours=5, minutes=30))
    now   = datetime.now(IST)

    # Skip weekends
    if now.weekday() >= 5:
        return

    # Only fire between 9:00 AM and 9:30 AM IST
    if not (now.hour == 9 and now.minute < 30):
        return

    # Skip if already sent today
    _today = now.strftime("%Y-%m-%d")
    if st.session_state.get("_tg_token_reminder_date") == _today:
        return

    # Skip if Upstox token is already valid
    if _upstox_connected():
        st.session_state["_tg_token_reminder_date"] = _today
        return

    # Skip if Telegram not configured
    _bt, _ci = _tg_creds()
    if not _bt or not _ci:
        return

    # Build and send reminder
    _day_name = now.strftime("%A")
    _date_str = now.strftime("%d %b %Y")
    msg = (
        "\U0001f511 <b>PivotVault AI - Daily Token Reminder</b>\n"
        "--------------------\n"
        f"Good morning! Today is <b>{_day_name}, {_date_str}</b>\n\n"
        "Please update your <b>Upstox Access Token</b>\n"
        "before markets open.\n\n"
        "<b>Steps:</b>\n"
        "1. Open Upstox Developer Console\n"
        "2. Generate today's Access Token\n"
        "3. Open PivotVault AI\n"
        "4. Go to Settings - Broker Settings\n"
        "5. Paste token and click Save\n\n"
        "\U0001f550 Markets open at <b>9:45 AM IST</b>\n"
        "\u26a1 Auto-trading starts at <b>9:45 AM IST</b>"
    )
    ok = _send_telegram(msg)
    if ok:
        st.session_state["_tg_token_reminder_date"] = _today


def render_market_header():
    from datetime import timezone
    IST    = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(IST)
    _scan_mkt = st.session_state.get("scanner_market_global",
                  st.session_state.get("scanner_market", "🇮🇳 NSE 500"))
    _mkt_key  = "us" if _scan_mkt in ("🇺🇸 Dow 30", "🇺🇸 Nasdaq 100") else "india"
    open_  = is_market_open(_mkt_key)
    _mkt_status_india = get_market_status("india")
    _mkt_status_us    = get_market_status("us")

    # Data feed status — yfinance always live; Upstox optional enhancement
    _upstox_ok = _upstox_connected()
    _feed_label = "📡 Upstox Live + yfinance" if _upstox_ok else "📊 yfinance (always live · Upstox optional)"
    _feed_color = "#1a6b2e" if _upstox_ok else "#4a5e32"

    # Non-blocking optional Upstox token refresh (collapsed by default)
    _show_token_refresh_popup()

    # Show Upstox renewal error if any (non-blocking)
    renewal_err = st.session_state.pop("upstox_renewal_error", None)
    if renewal_err:
        st.warning(f"♻️ Upstox auto-renewal: {renewal_err[:80]} — yfinance is still active.", icon="ℹ️")

    # Show price alert notifications
    alert_notifs = st.session_state.pop("alert_notifications", [])
    for sym, msg in alert_notifs:
        st.toast(f"🔔 {msg}", icon="🎯")

    # Market status pill + data feed badge + refresh button
    status_col, feed_col, refresh_col = st.columns([5, 3, 1])
    with status_col:
        dot_color = "#16a34a" if open_ else "#dc2626"
        status    = "LIVE · NSE Open" if open_ else "Market Closed"
        next_info = ""
        if not open_:
            next_info = f" · {_mkt_status_india['note']} | {_mkt_status_us['note']}"
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;padding:0.3rem 0;"
            f"font-family:IBM Plex Mono,monospace;font-size:0.72rem;'>"
            f"<span style='width:8px;height:8px;border-radius:50%;background:{dot_color};"
            f"display:inline-block;{'animation:pulse 1.5s infinite;' if open_ else ''}'></span>"
            f"<span style='color:{dot_color};font-weight:600;'>{status}</span>"
            f"<span style='color:#8a9a78;'>{next_info}</span>"
            f"<span style='color:#8a9a78;margin-left:auto;'>"
            f"{now_ist.strftime('%d %b %Y  %H:%M:%S IST')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with feed_col:
        st.markdown(
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;"
            f"color:{_feed_color};padding:0.35rem 0;text-align:center;'>"
            f"{_feed_label}</div>",
            unsafe_allow_html=True,
        )
    with refresh_col:
        if st.button("🔄 Refresh", use_container_width=True, key="global_refresh"):
            st.cache_data.clear()
            st.rerun()

    # Auto-refresh using streamlit-autorefresh (reliable on Streamlit Cloud)
    if open_ and _HAS_AUTOREFRESH:
        st_autorefresh(interval=30_000, limit=None, key="mkt_autorefresh")
    elif open_ and not _HAS_AUTOREFRESH:
        st.caption("💡 Install streamlit-autorefresh for live auto-refresh")

    # Index metrics
    indices = {"NIFTY 50": "^NSEI", "SENSEX": "^BSESN", "NIFTY BANK": "^NSEBANK"}
    cols = st.columns(len(indices))
    for col, (name, ticker) in zip(cols, indices.items()):
        d = fetch_index_data(ticker, upstox_token=st.session_state.get('upstox_access_token',''))
        ltp, chg = d.get("ltp"), d.get("change")
        if ltp is not None:
            hi  = d.get("high")
            lo  = d.get("low")
            sub = f"H:{hi:,.0f}  L:{lo:,.0f}" if hi and lo else ""
            col.metric(
                name,
                f"{ltp:,.2f}",
                f"{'+' if chg and chg >= 0 else ''}{chg}%" if chg is not None else "—",
            )
            if sub:
                col.caption(sub)
        else:
            col.metric(name, "—", "—")


def render_movers_table(df: pd.DataFrame, title: str, color: str):
    st.markdown(
        f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.72rem;"
        f"letter-spacing:0.08em;text-transform:uppercase;color:{color};"
        f"margin-bottom:0.5rem;'>{title}</div>", unsafe_allow_html=True,
    )
    if df.empty:
        st.caption("Data unavailable — NSE API may require VPN / direct browser session.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


@st.cache_data(ttl=180)
def fetch_heatmap_performance(symbols: list, max_stocks: int = 120) -> pd.DataFrame:
    """
    Batch-fetch 1-day % change for up to `max_stocks` NSE symbols using
    yfinance download (single request = much faster than per-ticker calls).
    Returns a DataFrame with columns: Symbol, Change%.
    """
    sample  = symbols[:max_stocks]
    tickers = [s + ".NS" for s in sample]
    result  = []
    try:
        raw = yf.download(
            tickers, period="2d", interval="1d",
            group_by="ticker", auto_adjust=True,
            progress=False, threads=True,
        )
        for sym, ticker in zip(sample, tickers):
            try:
                if len(tickers) == 1:
                    closes = raw["Close"]
                else:
                    closes = raw[ticker]["Close"]
                closes = closes.dropna()
                if len(closes) >= 2:
                    chg = round((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2] * 100, 2)
                    result.append({"Symbol": sym, "Change%": chg})
                else:
                    result.append({"Symbol": sym, "Change%": 0.0})
            except Exception:
                result.append({"Symbol": sym, "Change%": 0.0})
    except Exception:
        result = [{"Symbol": s, "Change%": 0.0} for s in sample]

    return pd.DataFrame(result)


def build_sector_treemap(nse500: pd.DataFrame, perf_df: pd.DataFrame) -> go.Figure:
    """
    Sector-level only treemap.
    Uses plain Industry names as both ids and labels so on_select returns
    a clean, matchable sector name string.
    """
    df = nse500.copy()
    if not perf_df.empty:
        df = df.merge(perf_df[["Symbol", "Change%"]], on="Symbol", how="left")
        df["Change%"] = df["Change%"].fillna(0.0)
    else:
        df["Change%"] = 0.0

    sector_df = (
        df.groupby("Industry")
        .agg(
            Avg_Change=("Change%", "mean"),
            Stock_Count=("Symbol", "count"),
            Gainers=("Change%", lambda x: (x > 0).sum()),
            Losers=("Change%",  lambda x: (x < 0).sum()),
        )
        .reset_index()
    )
    sector_df["Avg_Change"] = sector_df["Avg_Change"].round(2)
    clamp = 5.0
    sector_df["ColorVal"] = sector_df["Avg_Change"].clip(-clamp, clamp)

    # Display text on tile: sector name + change (shown inside tile)
    def _tile_text(row):
        chg   = row["Avg_Change"]
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
        return f"{row['Industry']}<br>{arrow}{abs(chg):.2f}%"

    sector_df["TileText"] = sector_df.apply(_tile_text, axis=1)

    # Build customdata as list-of-lists (not np.column_stack) to preserve types
    customdata = [
        [row["Industry"], float(row["Avg_Change"]),
         int(row["Gainers"]), int(row["Losers"]), int(row["Stock_Count"])]
        for _, row in sector_df.iterrows()
    ]

    fig = go.Figure(go.Treemap(
        # ids = plain sector name → this is what on_select returns as point_index label
        ids=sector_df["Industry"].tolist(),
        labels=sector_df["TileText"].tolist(),
        parents=[""] * len(sector_df),
        values=sector_df["Stock_Count"].tolist(),
        customdata=customdata,
        marker=dict(
            colors=sector_df["ColorVal"].tolist(),
            colorscale=[
                [0.00, "#7b0020"],
                [0.20, "#c0392b"],
                [0.40, "#e74c3c"],
                [0.50, "#1e2330"],
                [0.60, "#1a6640"],
                [0.80, "#27ae60"],
                [1.00, "#00e5a0"],
            ],
            cmin=-clamp,
            cmax=clamp,
            line=dict(width=2, color="#0d0f14"),
            colorbar=dict(
                title=dict(text="Avg 1D %", font=dict(size=10, family="IBM Plex Mono")),
                tickfont=dict(size=9, family="IBM Plex Mono"),
                thickness=12, len=0.65,
            ),
        ),
        hovertemplate=(
            "<b>%{id}</b><br>"
            "Avg Change: %{customdata[1]:+.2f}%<br>"
            "▲ Gainers: %{customdata[2]}  ▼ Losers: %{customdata[3]}<br>"
            "Total Stocks: %{customdata[4]}<br>"
            "<i>Click to see top gainers & losers</i>"
            "<extra></extra>"
        ),
        textfont=dict(family="IBM Plex Mono", size=12, color="#ffffff"),
        textposition="middle center",
    ))

    fig.update_layout(
        paper_bgcolor="#f0f4f8",
        margin=dict(l=0, r=0, t=0, b=0),
        height=480,
        font=dict(family="IBM Plex Mono", color="#d4daf0"),
    )
    return fig


# ─────────────────────────────────────────────
#  PAGES
# ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
#  USER CREDENTIALS — Admin Login
# ══════════════════════════════════════════════════════════════

USERS = {
    # ── Primary Admin ─────────────────────────────────────────────
    "umeshbhatia.ca@gmail.com": {"pin": "0919", "name": "Umesh Bhatia", "phone": "9999999999", "role": "admin"},
}
_PHONE_MAP = {v["phone"]: k for k, v in USERS.items()}

def generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)

def verify_login(identifier: str, pin: str) -> tuple:
    idf = identifier.strip().lower()
    if idf in _PHONE_MAP:
        idf = _PHONE_MAP[idf]
    u = USERS.get(idf)
    if u and u["pin"] == pin.strip():
        return True, {"id": idf, "name": u["name"], "email": idf, "phone": u["phone"]}
    return False, {}

def get_user_by_email(email: str) -> dict:
    u = USERS.get(email.lower().strip())
    if u:
        return {"id": email, "name": u["name"], "email": email, "phone": u["phone"]}
    return {}

# Stub functions — keep API compatible so rest of code doesn't break
def create_user(name, email, phone, pin, google_id=None):
    return False, "Contact admin to get access."

def reset_pin(email, new_pin):
    return False, "PIN reset disabled in demo mode."

def db_watchlist_get(user_id):   return []
def db_watchlist_add(user_id, symbol): return False
def db_watchlist_remove(user_id, symbol): return False
def db_save_signals(user_id, signals): pass


def page_login():
    """Login page — PIN login + Telegram OTP login."""

    import random as _rnd

    st.markdown("""
    <div style="text-align:center;padding:2rem 1rem 1.5rem;">
        <div style="font-size:2.8rem;margin-bottom:0.4rem;">🏦</div>
        <div style="font-family:'DM Sans',sans-serif;font-size:2rem;font-weight:800;
                    color:#1a1f0e;letter-spacing:-0.03em;">
            PivotVault <span style="color:#4e6130;">AI</span>
        </div>
        <div style="font-family:'DM Mono',monospace;font-size:0.7rem;color:#8a9a78;
                    letter-spacing:0.12em;text-transform:uppercase;margin-top:4px;">
            Indian Equity Intelligence · Pivot Boss Methodology
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        method = st.radio("Login Method",
                          ["🔢 PIN Login", "📱 Telegram OTP"],
                          horizontal=True,
                          label_visibility="collapsed",
                          key="login_method")

        # ── DIVIDER ────────────────────────────────────────────────────────────
        st.markdown("<hr style='margin:0.6rem 0;border-color:#e0e8d0;'>",
                    unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════════════════════
        # METHOD 1 — PIN LOGIN
        # ══════════════════════════════════════════════════════════════════════
        if "PIN" in method:
            identifier = st.text_input("Email",
                placeholder="umeshbhatia.ca@gmail.com", key="login_id")
            pin = st.text_input("4-Digit PIN", type="password",
                max_chars=4, placeholder="••••", key="login_pin")

            if st.button("🔓 Sign In", use_container_width=True, key="btn_login",
                         type="primary"):
                if not identifier or not pin:
                    st.error("Enter email and PIN.")
                else:
                    ok, user = verify_login(identifier, pin)
                    if ok:
                        st.session_state["logged_in"]  = True
                        st.session_state["username"]   = user["name"]
                        st.session_state["user_id"]    = user["email"]
                        st.session_state["user_email"] = user["email"]
                        st.session_state["user_phone"] = user.get("phone","")
                        _save_session()   # persist — survives browser refresh
                        st.rerun()
                    else:
                        st.error("❌ Wrong email or PIN.")

        # ══════════════════════════════════════════════════════════════════════
        # METHOD 2 — TELEGRAM OTP LOGIN
        # ══════════════════════════════════════════════════════════════════════
        else:
            # ── Step 1: Request OTP ───────────────────────────────────────────
            if not st.session_state.get("tg_otp_code"):

                st.markdown("""
                <div style='background:#f0f9f0;border:1.5px solid #b8dfc0;border-radius:10px;
                            padding:1rem;margin-bottom:1rem;font-family:DM Sans,sans-serif;
                            font-size:0.85rem;color:#1e3a1e;'>
                    <b>📱 How it works:</b><br>
                    1. Click <b>Send OTP to Telegram</b><br>
                    2. A 6-digit code appears in your <b>Telegram bot chat</b><br>
                    3. Enter the code here to login ✅
                </div>
                """, unsafe_allow_html=True)

                # Check if Telegram is configured
                # _tg_creds() returns (bot_token, chat_id) tuple
                _tg_bt, _tg_ci = _tg_creds()
                _tg_ready = bool(_tg_bt and _tg_ci)

                if not _tg_ready:
                    st.warning("⚠️ Telegram not configured. "
                               "Please login with PIN first, then set up Telegram in Settings.")
                else:
                    st.markdown(
                        f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
                        f"color:#4a5e32;margin-bottom:0.75rem;text-align:center;'>"
                        f"OTP will be sent to your Telegram bot</div>",
                        unsafe_allow_html=True)

                    if st.button("📲 Send OTP to Telegram",
                                 use_container_width=True,
                                 key="btn_tg_otp",
                                 type="primary"):
                        # Generate 6-digit OTP
                        otp = str(_rnd.randint(100000, 999999))
                        st.session_state["tg_otp_code"]    = otp
                        st.session_state["tg_otp_expires"] = (
                            datetime.now() + timedelta(minutes=5)).strftime("%H:%M:%S")

                        # Send via Telegram bot
                        msg = (
                            "\U0001f510 <b>PivotVault AI - Login OTP</b>\n"
                            "--------------------\n"
                            "Your one-time login code:\n\n"
                            f"<code>  {otp}  </code>\n\n"
                            f"Valid for 5 minutes\n"
                            f"Expires at: {st.session_state.get('tg_otp_expires','')}\n\n"
                            "If you did not request this, ignore it."
                        )
                        ok = _send_telegram(msg)
                        if ok:
                            st.success("✅ OTP sent to Telegram! Check your bot chat.")
                            st.rerun()
                        else:
                            st.session_state["tg_otp_code"] = ""
                            st.error("❌ Failed to send OTP. Check Telegram settings.")

            # ── Step 2: Enter + Verify OTP ────────────────────────────────────
            else:
                _expires = st.session_state.get("tg_otp_expires", "")
                st.markdown(
                    f"<div style='background:#fff8e1;border:1.5px solid #ffe082;"
                    f"border-radius:10px;padding:0.75rem;margin-bottom:0.75rem;"
                    f"font-family:DM Mono,monospace;font-size:0.78rem;color:#5a4000;"
                    f"text-align:center;'>"
                    f"⏱ OTP sent to Telegram · Expires <b>{_expires}</b>"
                    f"</div>",
                    unsafe_allow_html=True)

                entered = st.text_input("Enter 6-digit OTP from Telegram",
                    max_chars=6,
                    placeholder="_ _ _ _ _ _",
                    key="tg_otp_entered")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Verify & Login",
                                 use_container_width=True,
                                 key="btn_tg_verify",
                                 type="primary"):
                        # Check expiry
                        try:
                            exp_t = datetime.strptime(_expires, "%H:%M:%S").replace(
                                year=datetime.now().year,
                                month=datetime.now().month,
                                day=datetime.now().day)
                            expired = datetime.now() > exp_t
                        except Exception:
                            expired = False

                        if expired:
                            st.session_state["tg_otp_code"] = ""
                            st.error("⌛ OTP expired. Please request a new one.")
                            st.rerun()
                        elif entered.strip() == st.session_state.get("tg_otp_code",""):
                            # ✅ Valid OTP — log in as admin
                            _admin = list(USERS.keys())[0]
                            _udata = USERS[_admin]
                            st.session_state.update({
                                "logged_in":  True,
                                "username":   _udata["name"],
                                "user_id":    _admin,
                                "user_email": _admin,
                                "user_phone": _udata.get("phone",""),
                                "tg_otp_code": "",
                            })
                            _save_session()
                            # Send confirmation to Telegram
                            _send_telegram(
                                "Login Successful - PivotVault AI\n"
                                "--------------------\n"
                                f"User: {_udata['name']} logged in via Telegram OTP\n"
                                f"Time: {datetime.now().strftime('%d %b %Y %I:%M %p')}"
                            )
                            st.rerun()
                        else:
                            st.error("❌ Wrong OTP. Please check and try again.")

                with c2:
                    if st.button("🔄 New OTP",
                                 use_container_width=True,
                                 key="btn_tg_resend"):
                        st.session_state["tg_otp_code"] = ""
                        st.rerun()



def page_market_snapshot(nse500: pd.DataFrame):
    st.markdown(
        '<div class="title-bar"><span class="live-dot"></span><h1 style="color:#1a1f0e;">Market Snapshot</h1>'
        f'<span class="ts" style="color:#5a6a48;">{datetime.now().strftime("%d %b %Y  %H:%M")}</span></div>',
        unsafe_allow_html=True,
    )
    gainers, losers = get_market_movers()
    c1, c2 = st.columns(2)
    with c1: render_movers_table(gainers, "▲ Top Gainers", "#00e5a0")
    with c2: render_movers_table(losers,  "▼ Top Losers",  "#ff4d6a")
    st.divider()

    # ── Performance Heatmap ───────────────────────────────────────────────────
    hm_col, legend_col = st.columns([5, 1])
    with hm_col:
        st.markdown(
            "<div style='font-family:IBM Plex Mono,monospace;font-size:0.72rem;"
            "letter-spacing:0.08em;text-transform:uppercase;color:#5a6a48;"
            "margin-bottom:0.4rem;'>"
            "<span class='live-dot'></span>"
            "Sectoral Heatmap · Nifty 500 · Colour = Avg 1-Day % Change · Click a sector for detail</div>",
            unsafe_allow_html=True,
        )
    with legend_col:
        st.markdown(
            "<div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;"
            "color:#5a6a48;padding-top:0.1rem;line-height:1.9;'>"
            "<span style='color:#2d7a3a;'>■</span> Strong Gain<br>"
            "<span style='color:#27ae60;'>■</span> Gain<br>"
            "<span style='color:#e2e8f0;border:1px solid #333;'>■</span> Flat<br>"
            "<span style='color:#e74c3c;'>■</span> Loss<br>"
            "<span style='color:#7b0020;'>■</span> Strong Loss"
            "</div>",
            unsafe_allow_html=True,
        )

    symbols = nse500["Symbol"].dropna().tolist()

    with st.spinner("Fetching live performance data for heatmap…"):
        perf_df = fetch_heatmap_performance(symbols, max_stocks=120)

    # (summary metrics removed — detail shown below on sector click)

    # ── Build sector lookup once (used both for chart and detail panel) ────────
    df_merged = nse500.merge(perf_df[["Symbol","Change%"]], on="Symbol", how="left") if not perf_df.empty else nse500.copy()
    df_merged["Change%"] = df_merged.get("Change%", pd.Series(0.0, index=df_merged.index)).fillna(0.0)
    valid_sectors = set(df_merged["Industry"].dropna().unique())

    # ── Treemap — sector level only, click to drill down ─────────────────────
    fig = build_sector_treemap(nse500, perf_df)

    # Persist selected sector across reruns in session_state
    if "heatmap_sector" not in st.session_state:
        st.session_state["heatmap_sector"] = None

    selection = st.plotly_chart(
        fig,
        use_container_width=True,
        on_select="rerun",
        key="sector_heatmap",
    )

    # ── Parse click — try every field Streamlit/Plotly might return ──────────
    clicked_sector = None
    try:
        if selection:
            # Streamlit wraps the event as either a dict or an object
            sel_data = selection if isinstance(selection, dict) else vars(selection)
            inner    = sel_data.get("selection") or sel_data
            pts      = inner.get("points") or inner.get("point_indices") or []

            if pts:
                pt = pts[0] if isinstance(pts[0], dict) else {}

                # Try every field that might carry the sector name
                candidates = [
                    pt.get("id"),
                    pt.get("label"),
                    pt.get("text"),
                    # customdata is a list; index 0 = Industry
                    (pt.get("customdata") or [None])[0],
                    pt.get("hovertext"),
                ]

                for c in candidates:
                    if c and isinstance(c, str):
                        # Strip any HTML tags from label field
                        import re as _re
                        clean = _re.sub(r"<[^>]+>", "", c).split("\n")[0].strip()
                        if clean and clean in valid_sectors:
                            clicked_sector = clean
                            break
    except Exception:
        pass

    # Persist across reruns (on_select causes rerun which clears local vars)
    if clicked_sector:
        st.session_state["heatmap_sector"] = clicked_sector
    clicked_sector = st.session_state.get("heatmap_sector")

    # ── Sector detail panel — shown directly beneath heatmap on click ──────────
    if clicked_sector and not perf_df.empty:
        sector_stocks = df_merged[df_merged["Industry"] == clicked_sector].copy()

        if not sector_stocks.empty:
            top_g = sector_stocks.nlargest(5, "Change%")
            top_l = sector_stocks.nsmallest(5, "Change%")
            avg_chg = sector_stocks["Change%"].mean()
            col_fg  = "#00e5a0" if avg_chg >= 0 else "#ff4d6a"

            # Thin header bar — sector name + avg change + clear button
            hdr1, hdr2 = st.columns([5, 1])
            with hdr1:
                arrow = "▲" if avg_chg > 0 else "▼"
                st.markdown(
                    f"<div style='font-family:IBM Plex Mono,monospace;padding:0.5rem 0;"
                    f"border-bottom:1px solid #dce3ed;margin-bottom:0.6rem;'>"
                    f"<span style='font-size:1rem;font-weight:700;color:#1a1f0e;'>"
                    f"{clicked_sector}</span>"
                    f"<span style='font-size:0.8rem;color:{col_fg};margin-left:1rem;'>"
                    f"{arrow} {avg_chg:+.2f}% avg  ·  {len(sector_stocks)} stocks</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with hdr2:
                if st.button("✕ Clear", key="clear_sector"):
                    st.session_state["heatmap_sector"] = None
                    st.rerun()

            d1, d2 = st.columns(2)
            with d1:
                st.markdown(
                    f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.7rem;"
                    f"letter-spacing:0.08em;text-transform:uppercase;color:#2d7a3a;"
                    f"margin-bottom:0.35rem;'>▲ Top 5 Gainers</div>",
                    unsafe_allow_html=True,
                )
                g_rows = [{"Symbol": r["Symbol"], "Change %": f"+{r['Change%']:.2f}%"}
                          for _, r in top_g.iterrows()]
                st.dataframe(pd.DataFrame(g_rows), use_container_width=True, hide_index=True)

            with d2:
                st.markdown(
                    f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.7rem;"
                    f"letter-spacing:0.08em;text-transform:uppercase;color:#c0392b;"
                    f"margin-bottom:0.35rem;'>▼ Top 5 Losers</div>",
                    unsafe_allow_html=True,
                )
                l_rows = [{"Symbol": r["Symbol"], "Change %": f"{r['Change%']:.2f}%"}
                          for _, r in top_l.iterrows()]
                st.dataframe(pd.DataFrame(l_rows), use_container_width=True, hide_index=True)

    else:
        st.markdown(
            "<div style='font-family:IBM Plex Mono,monospace;font-size:0.72rem;"
            "color:#8a9a78;text-align:center;padding:0.55rem;"
            "border:1px dashed #e2e8f0;border-radius:6px;margin-top:0.25rem;'>"
            "👆  Click any sector tile to see its Top 5 Gainers &amp; Losers</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
#  NARROW CPR SCANNER
# ─────────────────────────────────────────────
def generate_stock_pdf(symbol: str, tf_label: str, pivot_type: str,
                       analysis: dict, trade_levels: dict) -> bytes:
    """
    Build a professional A4 PDF report for a single stock's Pivot Boss analysis.
    Includes: Overall Bias, CPR, Pivot Grid, Market Profile,
              Short/Medium/Long term targets & stop-losses, and reasoning narrative.
    Returns PDF as bytes.
    """
    buf = io.BytesIO()

    # ── Colour palette ────────────────────────────────────────────────────────
    DARK        = colors.HexColor("#0d1a0a")
    OLIVE       = colors.HexColor("#3d4a1e")
    OLIVE_LIGHT = colors.HexColor("#e8eddf")
    OLIVE_MID   = colors.HexColor("#b5c77a")
    GREEN       = colors.HexColor("#1a7a4a")
    RED         = colors.HexColor("#c0392b")
    AMBER       = colors.HexColor("#d97706")
    BLUE        = colors.HexColor("#2563eb")
    SLATE       = colors.HexColor("#475569")
    LIGHT_GREY  = colors.HexColor("#f8fafc")
    BORDER      = colors.HexColor("#e2e8f0")
    WHITE       = colors.white

    overall = analysis.get("overall", "NEUTRAL")
    ov_col  = analysis.get("ov_col", "neut")
    BIAS_COLOR = GREEN if ov_col == "bull" else (RED if ov_col == "bear" else AMBER)

    ltp    = analysis.get("ltp", 0)
    cpr    = analysis.get("cpr", {})
    pivots = analysis.get("pivots", {})
    mp     = analysis.get("market_profile", {})
    tl     = trade_levels  # short / medium / long

    # ── Document setup ────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm,  bottomMargin=16*mm,
        title=f"PivotVault AI — {symbol} Analysis",
        author="PivotVault AI",
    )
    W = A4[0] - 36*mm   # usable width

    styles = getSampleStyleSheet()

    # Custom styles
    def S(name, font="Helvetica", **kw):
        return ParagraphStyle(name, fontName=font, **kw)

    s_title    = S("title",    fontSize=20, textColor=DARK,   leading=24, spaceAfter=2)
    s_sub      = S("sub",      fontSize=9,  textColor=SLATE,  leading=13, spaceAfter=6)
    s_h2       = S("h2",       fontSize=12, textColor=OLIVE,  leading=16, spaceBefore=10, spaceAfter=4,
                   font="Helvetica-Bold")
    s_h3       = S("h3",       fontSize=10, textColor=DARK,   leading=14, spaceBefore=6,  spaceAfter=3,
                   font="Helvetica-Bold")
    s_body     = S("body",     fontSize=9,  textColor=SLATE,  leading=14, spaceAfter=4)
    s_bull     = S("bull",     fontSize=10, textColor=GREEN,  leading=14, font="Helvetica-Bold")
    s_bear     = S("bear",     fontSize=10, textColor=RED,    leading=14, font="Helvetica-Bold")
    s_neut     = S("neut",     fontSize=10, textColor=AMBER,  leading=14, font="Helvetica-Bold")
    s_cell     = S("cell",     fontSize=8,  textColor=DARK,   leading=11)
    s_cell_b   = S("cell_b",   fontSize=8,  textColor=DARK,   leading=11, font="Helvetica-Bold")
    s_cell_g   = S("cell_g",   fontSize=8,  textColor=GREEN,  leading=11, font="Helvetica-Bold")
    s_cell_r   = S("cell_r",   fontSize=8,  textColor=RED,    leading=11, font="Helvetica-Bold")
    s_cell_hdr = S("cell_hdr", fontSize=8,  textColor=WHITE,  leading=11, font="Helvetica-Bold",
                   alignment=TA_CENTER)
    s_disc     = S("disc",     fontSize=7,  textColor=colors.HexColor("#94a3b8"),
                   leading=10, spaceAfter=0)

    def cell(txt, style=None):
        return Paragraph(str(txt), style or s_cell)

    def hdr(txt):
        return Paragraph(txt, s_cell_hdr)

    story = []

    # ════════════════════════════════════════════════════════════════
    # HEADER BLOCK
    # ════════════════════════════════════════════════════════════════
    header_data = [[
        Paragraph(f"<b>{symbol}</b>", ParagraphStyle("ht", fontSize=22,
                  textColor=WHITE, leading=26, fontName="Helvetica-Bold")),
        Paragraph(
            f"LTP &nbsp;<b>Rs.{ltp:,.2f}</b><br/>"
            f"{tf_label} &nbsp;|&nbsp; {pivot_type} Pivots<br/>"
            f"{cpr.get('Bias','')}<br/>"
            f"Generated: {datetime.now().strftime('%d %b %Y  %H:%M')}",
            ParagraphStyle("hs", fontSize=8, textColor=OLIVE_LIGHT,
                           leading=13, fontName="Helvetica"),
        ),
        Paragraph(
            f"<b>{overall}</b>",
            ParagraphStyle("hb", fontSize=14, textColor=WHITE, leading=18,
                           fontName="Helvetica-Bold", alignment=TA_RIGHT),
        ),
    ]]
    header_tbl = Table(header_data, colWidths=[W*0.32, W*0.42, W*0.26])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), OLIVE),
        ("ROUNDEDCORNERS", [6]),
        ("PADDING",     (0,0), (-1,-1), 10),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("LINEBELOW",   (0,0), (-1,0), 1, OLIVE_MID),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 8*mm))

    # ════════════════════════════════════════════════════════════════
    # CPR + PIVOT LEVELS  (side by side)
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("Central Pivot Range (CPR)", s_h2))
    story.append(HRFlowable(width=W, thickness=1, color=OLIVE_MID, spaceAfter=4))

    cpr_data = [
        [hdr("Level"), hdr("Value"), hdr("Width %"), hdr("CPR Bias")],
        [cell("Pivot (P)"),  cell(f"Rs.{cpr.get('Pivot',0):,.2f}"),
         cell(f"{cpr.get('Width%',0):.3f}%"),
         Paragraph(cpr.get("Bias","—"), s_bull if ov_col=="bull" else (s_bear if ov_col=="bear" else s_neut))],
        [cell("Top CPR (TC)"),  cell(f"Rs.{cpr.get('TC',0):,.2f}"),  cell(""), cell("")],
        [cell("Bot CPR (BC)"),  cell(f"Rs.{cpr.get('BC',0):,.2f}"),  cell(""), cell("")],
    ]
    cpr_tbl = Table(cpr_data, colWidths=[W*0.22, W*0.22, W*0.22, W*0.34])
    cpr_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  OLIVE),
        ("BACKGROUND",    (0,1), (-1,-1), LIGHT_GREY),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GREY]),
        ("GRID",          (0,0), (-1,-1), 0.5, BORDER),
        ("PADDING",       (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(cpr_tbl)
    story.append(Spacer(1, 5*mm))

    # ── Pivot Grid ────────────────────────────────────────────────────────────
    story.append(Paragraph("Pivot Level Grid", s_h2))
    story.append(HRFlowable(width=W, thickness=1, color=OLIVE_MID, spaceAfter=4))

    sorted_pivots = sorted(pivots.items(), key=lambda x: x[1], reverse=True) if pivots else []
    piv_rows = [[hdr("Level"), hdr("Price (Rs.)"), hdr("vs LTP"), hdr("Role")]]
    for lbl, val in sorted_pivots:
        diff     = val - ltp
        diff_pct = diff / ltp * 100
        role     = "Resistance" if val > ltp else ("Support" if val < ltp else "At Price")
        arr      = "+" if diff >= 0 else ""
        r_style  = s_cell_g if role == "Support" else (s_cell_r if role == "Resistance" else s_cell_b)
        piv_rows.append([
            cell(lbl, s_cell_b),
            cell(f"Rs.{val:,.2f}"),
            Paragraph(f"{arr}{diff_pct:.2f}%", s_cell_g if diff >= 0 else s_cell_r),
            Paragraph(role, r_style),
        ])
    piv_tbl = Table(piv_rows, colWidths=[W*0.15, W*0.25, W*0.25, W*0.35])
    piv_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  OLIVE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GREY]),
        ("GRID",          (0,0), (-1,-1), 0.5, BORDER),
        ("PADDING",       (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(piv_tbl)
    story.append(Spacer(1, 5*mm))

    # ── Market Profile ────────────────────────────────────────────────────────
    if mp:
        story.append(Paragraph("Market Profile", s_h2))
        story.append(HRFlowable(width=W, thickness=1, color=OLIVE_MID, spaceAfter=4))
        mp_data = [
            [hdr("POC"), hdr("Value Area High (VAH)"), hdr("Value Area Low (VAL)")],
            [cell(f"Rs.{mp.get('POC',0):,.2f}", s_cell_b),
             cell(f"Rs.{mp.get('VAH',0):,.2f}"),
             cell(f"Rs.{mp.get('VAL',0):,.2f}")],
        ]
        mp_tbl = Table(mp_data, colWidths=[W/3, W/3, W/3])
        mp_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), OLIVE),
            ("BACKGROUND", (0,1), (-1,1), LIGHT_GREY),
            ("GRID",       (0,0), (-1,-1), 0.5, BORDER),
            ("PADDING",    (0,0), (-1,-1), 5),
            ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(mp_tbl)
        story.append(Spacer(1, 5*mm))

    # ════════════════════════════════════════════════════════════════
    # TRADE PLAN  — Short / Medium / Long
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("Trade Plan — Targets & Stop-Loss", s_h2))
    story.append(HRFlowable(width=W, thickness=1, color=OLIVE_MID, spaceAfter=4))

    if tl:
        sh = tl.get("short",  {})
        md = tl.get("medium", {})
        lg = tl.get("long",   {})
        pat = tl.get("pattern","")
        PAT_COL = GREEN if pat == "Bullish" else RED

        plan_data = [
            [hdr("Horizon"), hdr("Entry"), hdr("Target 1"),
             hdr("Target 2"), hdr("Target 3"), hdr("Stop Loss"), hdr("R:R")],
            # Short
            [Paragraph("<b>Short Term</b><br/><font size='7' color='#94a3b8'>1 – 3 Days</font>",
                       ParagraphStyle("stl", fontSize=8, leading=12, textColor=DARK)),
             cell(f"Rs.{sh.get('entry',0):,.2f}"),
             Paragraph(f"Rs.{sh.get('target',0):,.2f}",
                       ParagraphStyle("tg", fontSize=8, textColor=PAT_COL, fontName="Helvetica-Bold", leading=11)),
             cell("—"), cell("—"),
             Paragraph(f"Rs.{sh.get('sl',0):,.2f}",
                       ParagraphStyle("sl", fontSize=8, textColor=RED, fontName="Helvetica-Bold", leading=11)),
             cell(f"{sh.get('rr',0)}x", s_cell_b)],
            # Medium
            [Paragraph("<b>Medium Term</b><br/><font size='7' color='#94a3b8'>1 – 4 Weeks</font>",
                       ParagraphStyle("stl2", fontSize=8, leading=12, textColor=DARK)),
             cell(f"Rs.{md.get('entry',0):,.2f}"),
             Paragraph(f"Rs.{md.get('target1',0):,.2f}",
                       ParagraphStyle("tg2", fontSize=8, textColor=PAT_COL, fontName="Helvetica-Bold", leading=11)),
             Paragraph(f"Rs.{md.get('target2',0):,.2f}",
                       ParagraphStyle("tg3", fontSize=8, textColor=PAT_COL, fontName="Helvetica-Bold", leading=11)),
             cell("—"),
             Paragraph(f"Rs.{md.get('sl',0):,.2f}",
                       ParagraphStyle("sl2", fontSize=8, textColor=RED, fontName="Helvetica-Bold", leading=11)),
             cell(f"{md.get('rr',0)}x", s_cell_b)],
            # Long
            [Paragraph("<b>Long Term</b><br/><font size='7' color='#94a3b8'>1 – 3 Months</font>",
                       ParagraphStyle("stl3", fontSize=8, leading=12, textColor=DARK)),
             cell(f"Rs.{lg.get('entry',0):,.2f}"),
             Paragraph(f"Rs.{lg.get('target1',0):,.2f}",
                       ParagraphStyle("tg4", fontSize=8, textColor=PAT_COL, fontName="Helvetica-Bold", leading=11)),
             Paragraph(f"Rs.{lg.get('target2',0):,.2f}",
                       ParagraphStyle("tg5", fontSize=8, textColor=PAT_COL, fontName="Helvetica-Bold", leading=11)),
             Paragraph(f"Rs.{lg.get('target3',0):,.2f}",
                       ParagraphStyle("tg6", fontSize=8, textColor=PAT_COL, fontName="Helvetica-Bold", leading=11)),
             Paragraph(f"Rs.{lg.get('sl',0):,.2f}",
                       ParagraphStyle("sl3", fontSize=8, textColor=RED, fontName="Helvetica-Bold", leading=11)),
             cell(f"{lg.get('rr',0)}x", s_cell_b)],
        ]
        plan_col_w = [W*0.18, W*0.13, W*0.13, W*0.13, W*0.13, W*0.15, W*0.15]
        plan_tbl = Table(plan_data, colWidths=plan_col_w)
        plan_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  OLIVE),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GREY, WHITE]),
            ("GRID",          (0,0), (-1,-1), 0.5, BORDER),
            ("PADDING",       (0,0), (-1,-1), 5),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LINEABOVE",     (0,1), (-1,1), 1.5, PAT_COL),
        ]))
        story.append(plan_tbl)
        story.append(Spacer(1, 5*mm))

        # Also show full R1-R3 / S1-S3 reference
        ref_data = [
            [hdr("R3"), hdr("R2"), hdr("R1"), hdr("PIVOT"), hdr("S1"), hdr("S2"), hdr("S3")],
            [cell(f"Rs.{tl.get('R3',0):,.2f}", s_cell_r),
             cell(f"Rs.{tl.get('R2',0):,.2f}", s_cell_r),
             cell(f"Rs.{tl.get('R1',0):,.2f}", s_cell_r),
             cell(f"Rs.{tl.get('pivot',0):,.2f}", s_cell_b),
             cell(f"Rs.{tl.get('S1',0):,.2f}", s_cell_g),
             cell(f"Rs.{tl.get('S2',0):,.2f}", s_cell_g),
             cell(f"Rs.{tl.get('S3',0):,.2f}", s_cell_g)],
        ]
        ref_tbl = Table(ref_data, colWidths=[W/7]*7)
        ref_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), OLIVE),
            ("BACKGROUND", (0,1), (-1,1), LIGHT_GREY),
            ("GRID",       (0,0), (-1,-1), 0.5, BORDER),
            ("PADDING",    (0,0), (-1,-1), 5),
            ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(ref_tbl)

    story.append(Spacer(1, 6*mm))

    # ════════════════════════════════════════════════════════════════
    # SIGNAL SUMMARY
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("Signal Summary", s_h2))
    story.append(HRFlowable(width=W, thickness=1, color=OLIVE_MID, spaceAfter=4))

    sig_data = [
        [hdr("Indicator"), hdr("Signal"), hdr("Bias")],
        [cell("CPR Position"),      cell(analysis.get("cpr_position","—")),
         Paragraph(analysis.get("cpr_col","neut").upper(),
                   s_bull if analysis.get("cpr_col")=="bull" else
                   (s_bear if analysis.get("cpr_col")=="bear" else s_neut))],
        [cell("3/10 Oscillator"),   cell(analysis.get("osc_sig","—")),
         Paragraph(analysis.get("osc_col","neut").upper(),
                   s_bull if analysis.get("osc_col")=="bull" else
                   (s_bear if analysis.get("osc_col")=="bear" else s_neut))],
        [cell("HMA-20 Trend"),      cell(analysis.get("hma_sig","—")),
         Paragraph(analysis.get("hma_col","neut").upper(),
                   s_bull if analysis.get("hma_col")=="bull" else
                   (s_bear if analysis.get("hma_col")=="bear" else s_neut))],
        [cell("RSI-14"),
         cell(f"{analysis.get('rsi','—')} — {analysis.get('rsi_sig','—')}"),
         Paragraph(analysis.get("rsi_col","neut").upper(),
                   s_bull if analysis.get("rsi_col")=="bull" else
                   (s_bear if analysis.get("rsi_col")=="bear" else s_neut))],
    ]
    sig_tbl = Table(sig_data, colWidths=[W*0.28, W*0.46, W*0.26])
    sig_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0),  OLIVE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GREY]),
        ("GRID",          (0,0), (-1,-1), 0.5, BORDER),
        ("PADDING",       (0,0), (-1,-1), 5),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 6*mm))

    # ════════════════════════════════════════════════════════════════
    # NARRATIVE ANALYSIS
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("Analysis Narrative", s_h2))
    story.append(HRFlowable(width=W, thickness=1, color=OLIVE_MID, spaceAfter=5))

    # Build narrative paragraphs
    def narrative_para(text):
        return Paragraph(text, s_body)

    # 1. Overall bias
    bias_word = "bullish" if ov_col=="bull" else ("bearish" if ov_col=="bear" else "neutral / mixed")
    story.append(narrative_para(
        f"<b>Overall Bias:</b>  The Pivot Boss analysis on <b>{symbol}</b> on the "
        f"<b>{tf_label}</b> timeframe using <b>{pivot_type}</b> pivots indicates a "
        f"<b>{overall}</b> setup. The current LTP of <b>Rs.{ltp:,.2f}</b> is positioned "
        f"{'above the Top CPR (TC), signalling bullish control' if ltp > cpr.get('TC',ltp) else ('below the Bottom CPR (BC), signalling bearish control' if ltp < cpr.get('BC',ltp) else 'inside the CPR band, indicating indecision')}."
    ))

    # 2. CPR width narrative
    w = cpr.get("Width%", 0)
    if w < 0.25:
        cpr_narr = (f"The CPR width of <b>{w:.3f}%</b> is <b>Narrow</b>, a key Pivot Boss setup. "
                    "Frank Ochoa identifies narrow CPR days as high-probability trending days — "
                    "price typically breaks decisively in one direction and does not look back.")
    elif w < 0.5:
        cpr_narr = (f"The CPR width of <b>{w:.3f}%</b> is <b>Moderate</b>. "
                    "A mild trend is possible, but the stock may see some consolidation "
                    "around the CPR zone before committing to a direction.")
    else:
        cpr_narr = (f"The CPR width of <b>{w:.3f}%</b> is <b>Wide</b>, indicating a "
                    "range-bound session is likely. Price may oscillate between TC and BC "
                    "without a strong directional move.")
    story.append(narrative_para(f"<b>CPR Analysis:</b>  {cpr_narr}"))

    # 3. Momentum narrative
    story.append(narrative_para(
        f"<b>Momentum (3/10 Oscillator):</b>  {analysis.get('osc_sig','—')}. "
        "The 3/10 oscillator is Frank Ochoa's primary momentum tool. "
        + ("A bullish crossover or positive histogram confirms upside momentum is building."
           if analysis.get("osc_col")=="bull" else
           "A bearish crossover or negative histogram warns that downside momentum is dominant."
           if analysis.get("osc_col")=="bear" else
           "The oscillator is near neutral — no strong momentum signal.")
    ))

    # 4. HMA narrative
    story.append(narrative_para(
        f"<b>Trend Filter (HMA-20):</b>  {analysis.get('hma_sig','—')}. "
        "The Hull Moving Average (HMA-20) eliminates lag and gives a cleaner trend read. "
        + ("A rising HMA confirms the short-term trend is up, supporting long positions."
           if analysis.get("hma_col")=="bull" else
           "A declining HMA confirms the short-term trend is down, supporting short positions.")
    ))

    # 5. RSI narrative
    rsi_val = analysis.get("rsi")
    if rsi_val:
        if rsi_val >= 70:
            rsi_narr = f"RSI at <b>{rsi_val}</b> is in overbought territory. Momentum is stretched — watch for reversal signals near resistance."
        elif rsi_val <= 30:
            rsi_narr = f"RSI at <b>{rsi_val}</b> is oversold. A bounce or recovery is possible if price holds key support."
        elif rsi_val >= 55:
            rsi_narr = f"RSI at <b>{rsi_val}</b> is in bullish territory (above 55), indicating buyers have the upper hand."
        elif rsi_val <= 45:
            rsi_narr = f"RSI at <b>{rsi_val}</b> is in bearish territory (below 45), indicating sellers remain in control."
        else:
            rsi_narr = f"RSI at <b>{rsi_val}</b> is neutral — no extreme reading."
        story.append(narrative_para(f"<b>RSI-14:</b>  {rsi_narr}"))

    # 6. Market Profile narrative
    if mp:
        poc = mp.get("POC", 0)
        if abs(poc - ltp) / ltp < 0.01:
            mp_narr = (f"Price is trading near the Point of Control (POC) at Rs.{poc:,.2f}, "
                       "indicating high-volume price acceptance. A breakout above or breakdown "
                       "below POC could trigger an impulsive move.")
        elif ltp > poc:
            mp_narr = (f"Price is trading above the POC (Rs.{poc:,.2f}), suggesting buyers "
                       "are in control of the value area. POC acts as key support on a pullback.")
        else:
            mp_narr = (f"Price is trading below the POC (Rs.{poc:,.2f}), suggesting sellers "
                       "are in control. A reclaim of POC would be needed to shift the bias.")
        story.append(narrative_para(f"<b>Market Profile:</b>  {mp_narr}"))

    # 7. Trade plan summary
    if tl:
        sh = tl.get("short",  {})
        md = tl.get("medium", {})
        lg = tl.get("long",   {})
        direction = "long (buy)" if ov_col == "bull" else "short (sell)"
        story.append(narrative_para(
            f"<b>Trade Plan Summary:</b>  Based on the above analysis, the suggested bias is "
            f"<b>{direction}</b> on {symbol}. "
            f"Short-term traders (1–3 days) can target <b>Rs.{sh.get('target',0):,.2f}</b> with a "
            f"stop at <b>Rs.{sh.get('sl',0):,.2f}</b> (R:R {sh.get('rr',0)}x). "
            f"Medium-term traders (1–4 weeks) have targets at "
            f"<b>Rs.{md.get('target1',0):,.2f}</b> and <b>Rs.{md.get('target2',0):,.2f}</b> "
            f"with a stop at <b>Rs.{md.get('sl',0):,.2f}</b> (R:R {md.get('rr',0)}x). "
            f"Long-term investors (1–3 months) can look towards "
            f"<b>Rs.{lg.get('target1',0):,.2f}</b> / <b>Rs.{lg.get('target2',0):,.2f}</b> / "
            f"<b>Rs.{lg.get('target3',0):,.2f}</b> with a stop at "
            f"<b>Rs.{lg.get('sl',0):,.2f}</b> (R:R {lg.get('rr',0)}x)."
        ))

    story.append(Spacer(1, 6*mm))

    # ════════════════════════════════════════════════════════════════
    # DISCLAIMER
    # ════════════════════════════════════════════════════════════════
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=4))
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by PivotVault AI using the Frank Ochoa Pivot Boss "
        "methodology. Targets and stop-losses are derived from pivot point mathematics and ATR-based "
        "volatility. This report is for educational and informational purposes only and does NOT "
        "constitute financial advice. Always consult a SEBI-registered investment advisor before "
        "making any trading or investment decisions. Past performance is not indicative of future results.",
        s_disc,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()

def compute_trade_levels(symbol: str, ltp: float, tc: float, bc: float,
                         pivot: float, pattern: str) -> dict:
    """Compute trade targets and SL from pivot levels and ATR."""
    try:
        df = yf.Ticker(symbol + ".NS").history(period="60d", interval="1d")
        try:
            if df.index.tz is not None:
                df.index = df.index.tz_convert('Asia/Kolkata').tz_localize(None)
            else:
                df.index = df.index.tz_localize(None)
        except Exception:
            pass
        if df.empty or len(df) < 15:
            return {}
        close, high, low = df["Close"], df["High"], df["Low"]
        tr  = pd.concat([high-low,(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
        atr = float(tr.rolling(14).mean().iloc[-1])
        wk52h = float(high.tail(252).max()) if len(high)>=252 else float(high.max())
        wk52l = float(low.tail(252).min())  if len(low)>=252  else float(low.min())
        ref = df.iloc[-2]
        H2,L2,C2 = float(ref["High"]),float(ref["Low"]),float(ref["Close"])
        P  = (H2+L2+C2)/3
        R1 = 2*P-L2; R2 = P+(H2-L2); R3 = H2+2*(P-L2)
        S1 = 2*P-H2; S2 = P-(H2-L2); S3 = L2-2*(H2-P)
        if pattern == "Bullish":
            sh = {"entry":round(ltp,2),"target":round(min(R1,ltp+atr*1.5),2),"sl":round(max(bc,ltp-atr*0.8),2)}
            sh["rr"] = round((sh["target"]-sh["entry"])/max(sh["entry"]-sh["sl"],0.01),2)
            md = {"entry":round(ltp,2),"target1":round(R1,2),"target2":round(R2,2),"sl":round(S1,2)}
            md["rr"] = round((md["target2"]-md["entry"])/max(md["entry"]-md["sl"],0.01),2)
            lg = {"entry":round(ltp,2),"target1":round(R2,2),"target2":round(R3,2),"target3":round(min(wk52h,R3+atr*5),2),"sl":round(S2,2)}
            lg["rr"] = round((lg["target2"]-lg["entry"])/max(lg["entry"]-lg["sl"],0.01),2)
        else:
            sh = {"entry":round(ltp,2),"target":round(max(S1,ltp-atr*1.5),2),"sl":round(min(tc,ltp+atr*0.8),2)}
            sh["rr"] = round((sh["entry"]-sh["target"])/max(sh["sl"]-sh["entry"],0.01),2)
            md = {"entry":round(ltp,2),"target1":round(S1,2),"target2":round(S2,2),"sl":round(R1,2)}
            md["rr"] = round((md["entry"]-md["target2"])/max(md["sl"]-md["entry"],0.01),2)
            lg = {"entry":round(ltp,2),"target1":round(S2,2),"target2":round(S3,2),"target3":round(max(wk52l,S3-atr*5),2),"sl":round(R2,2)}
            lg["rr"] = round((lg["entry"]-lg["target2"])/max(lg["sl"]-lg["entry"],0.01),2)
        return {"symbol":symbol,"ltp":ltp,"pattern":pattern,"pivot":round(P,2),"tc":round(tc,2),"bc":round(bc,2),
                "atr":round(atr,2),"R1":round(R1,2),"R2":round(R2,2),"R3":round(R3,2),
                "S1":round(S1,2),"S2":round(S2,2),"S3":round(S3,2),
                "52wH":round(wk52h,2),"52wL":round(wk52l,2),"short":sh,"medium":md,"long":lg}
    except Exception:
        return {}


@st.cache_data(ttl=60)
def fetch_stock_history(symbol: str, period: str = "1y", interval: str = "1d",
                        upstox_token: str = "") -> pd.DataFrame:
    # ── Try Upstox first (free, accurate, NSE data) ───────────────────────
    if upstox_token:
        try:
            # Map period to from_date
            period_days = {
                "5d":60,"10d":10,"15d":15,"20d":20,"30d":30,
                "60d":60,"90d":90,"1y":365,"2y":730,"5y":1825,"10y":3650,
            }
            days = period_days.get(period, 365)
            from_dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            to_dt   = datetime.now().strftime("%Y-%m-%d")
            df = upstox_get_historical(symbol, interval, from_dt, to_dt)
            if not df.empty:
                return df
        except Exception:
            pass
    # ── Fallback: yfinance ────────────────────────────────────────────────
    try:
        df = yf.Ticker(symbol + ".NS").history(period=period, interval=interval)
        if not df.empty:
            try:
                if df.index.tz is not None:
                    df.index = df.index.tz_convert('Asia/Kolkata').tz_localize(None)
                else:
                    df.index = df.index.tz_localize(None)
            except Exception:
                pass
            return df
    except Exception:
        pass
    return pd.DataFrame()


def send_report_email(to_email: str, smtp_host: str, smtp_port: int,
                      sender_email: str, sender_password: str,
                      html_body: str, scan_date: str) -> tuple:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"PivotVault AI — CPR Report {scan_date}"
        msg["From"]    = sender_email
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html"))
        ctx = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as s:
                s.login(sender_email, sender_password)
                s.sendmail(sender_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.ehlo(); s.starttls(context=ctx); s.login(sender_email, sender_password)
                s.sendmail(sender_email, to_email, msg.as_string())
        return True, "Sent!"
    except Exception as e:
        return False, str(e)


def page_pivot_boss(nse500: pd.DataFrame):
    """★  Full Frank Ochoa / Pivot Boss analysis page."""
    _nse500_df = fetch_nse500_list()
    st.markdown(
        '<div class="title-bar"><span class="live-dot"></span>'
        '<h1>Pivot Boss Analysis</h1>'
        '<span style="font-family:IBM Plex Mono,monospace;font-size:0.68rem;'
        'color:#5a6a48;margin-left:0.5rem;">Frank Ochoa Methodology</span>'
        f'<span class="ts" style="color:#5a6a48;">{datetime.now().strftime("%d %b %Y  %H:%M")}</span></div>',
        unsafe_allow_html=True,
    )

    symbols = sorted(_nse500_df["Symbol"].dropna().tolist())

    # ── Controls ─────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([3, 1.5, 1.5, 1])
    with c1:
        symbol = st.selectbox("Symbol", symbols, key="pb_sym",
                              label_visibility="collapsed")
    with c2:
        tf_label = st.selectbox(
            "Timeframe",
            ["5 Min", "15 Min", "30 Min", "1 Hour", "4 Hour",
             "Daily", "Weekly", "Monthly"],
            index=5, key="pb_tf", label_visibility="collapsed",
        )
    with c3:
        pivot_type = st.selectbox(
            "Pivot Type",
            ["Traditional", "Woodie", "Camarilla", "DeMark", "Fibonacci"],
            key="pb_pt", label_visibility="collapsed",
        )
    with c4:
        run_btn = st.button("▶  Analyse")

    TF_MAP = {
        "5 Min":   ("5d",  "5m",   False),
        "15 Min":  ("10d", "15m",  False),
        "30 Min":  ("20d", "30m",  False),
        "1 Hour":  ("60d", "1h",   False),
        "4 Hour":  ("90d", "1h",   True),   # resample 1h → 4h
        "Daily":   ("1y",  "1d",   False),
        "Weekly":  ("5y",  "1wk",  False),
        "Monthly": ("10y", "1mo",  False),
    }
    period, interval, resample_4h = TF_MAP[tf_label]
    st.divider()

    with st.spinner(f"Loading {symbol} [{tf_label}] …"):
        df = fetch_stock_history(symbol, period, interval, upstox_token=st.session_state.get('upstox_access_token',''))
        if resample_4h and not df.empty:
            df = df.resample("4h").agg({
                "Open": "first", "High": "max",
                "Low": "min",    "Close": "last", "Volume": "sum",
            }).dropna()

    if df.empty or len(df) < 20:
        st.warning("Not enough data for this timeframe. Try Daily or a longer period.")
        return

    analysis = full_pivot_boss_analysis(df, pivot_type)
    if not analysis:
        st.warning("Analysis failed.")
        return

    ltp    = analysis["ltp"]
    cpr    = analysis["cpr"]
    mp     = analysis["market_profile"]
    pivots = analysis["pivots"]

    # ── Overall Bias Banner ───────────────────────────────────────────────────
    bias_palette = {
        "bull": ("#edf7ee", "#00e5a0"),
        "bear": ("#fdf0ee", "#ff4d6a"),
        "neut": ("#fdf9ec", "#f5a623"),
    }
    bg, fg = bias_palette.get(analysis["ov_col"], ("#141720", "#d4daf0"))
    st.markdown(
        f"<div style='background:{bg};border:1px solid {fg}33;border-left:4px solid {fg};"
        f"border-radius:6px;padding:0.75rem 1.25rem;margin-bottom:1rem;'>"
        f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;color:{fg}88;"
        f"letter-spacing:0.12em;text-transform:uppercase;'>Overall Bias  ·  {tf_label}  ·  {pivot_type}</span><br>"
        f"<span style='font-family:IBM Plex Mono,monospace;font-size:1.3rem;font-weight:700;color:{fg};'>"
        f"{analysis['overall']}</span>"
        f"<span style='font-family:IBM Plex Mono,monospace;font-size:0.8rem;color:{fg}aa;margin-left:1.5rem;'>"
        f"LTP ₹{ltp:,.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Main Chart ─────────────────────────────────────────────────────────
    chart_tab1, chart_tab2 = st.tabs(["📊 LW Chart + Pivots", "📈 Multi-Panel (Oscillators)"])
    with chart_tab1:
        render_lw_chart(symbol, tf_label, analysis, pivot_type, height=650)
    with chart_tab2:
        fig = build_pivot_boss_chart(df, symbol, analysis, pivot_type)
        st.plotly_chart(fig, use_container_width=True)

    # ── Signal Cards ──────────────────────────────────────────────────────────
    st.markdown("<h3 style='font-size:0.9rem;margin:1rem 0 0.5rem;'>Signal Summary</h3>",
                unsafe_allow_html=True)
    ca, cb, cc, cd = st.columns(4)

    with ca:
        cpr_detail = (
            f"TC {cpr['TC']} · P {cpr['Pivot']} · BC {cpr['BC']}<br>"
            f"Width: {cpr['Width%']}%<br>{cpr['Bias']}"
        ) if cpr else ""
        st.markdown(
            f"<div class='pb-card'>"
            f"<div class='pb-card-title'>Central Pivot Range (CPR)</div>"
            f"<div class='pb-card-value pb-{analysis['cpr_col']}'>{analysis['cpr_position']}</div>"
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.73rem;color:#5a6a48;"
            f"margin-top:0.4rem;'>{cpr_detail}</div></div>",
            unsafe_allow_html=True,
        )

    with cb:
        st.markdown(
            f"<div class='pb-card'>"
            f"<div class='pb-card-title'>3/10 Oscillator</div>"
            f"<div class='pb-card-value pb-{analysis['osc_col']}'>{analysis['osc_sig']}</div>"
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.73rem;color:#5a6a48;"
            f"margin-top:0.4rem;'>Ochoa's momentum gauge<br>3-MA minus 10-MA vs 16-Signal</div>"
            f"</div>", unsafe_allow_html=True,
        )

    with cc:
        st.markdown(
            f"<div class='pb-card'>"
            f"<div class='pb-card-title'>HMA(20) Trend</div>"
            f"<div class='pb-card-value pb-{analysis['hma_col']}'>{analysis['hma_sig']}</div>"
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.73rem;color:#5a6a48;"
            f"margin-top:0.4rem;'>Hull Moving Average<br>Low-lag trend direction filter</div>"
            f"</div>", unsafe_allow_html=True,
        )

    with cd:
        rsi_val   = f"{analysis['rsi']}" if analysis["rsi"] else "—"
        stoch_txt = (f"Stoch %K {analysis['stoch_k']} / %D {analysis['stoch_d']}"
                     if analysis["stoch_k"] else "")
        st.markdown(
            f"<div class='pb-card'>"
            f"<div class='pb-card-title'>RSI (14)</div>"
            f"<div class='pb-card-value pb-{analysis['rsi_col']}'>"
            f"{rsi_val} · {analysis['rsi_sig']}</div>"
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.73rem;color:#5a6a48;"
            f"margin-top:0.4rem;'>{stoch_txt}</div></div>",
            unsafe_allow_html=True,
        )

    # ── Pivot Levels + Market Profile ─────────────────────────────────────────
    st.markdown(f"<h3 style='font-size:0.9rem;margin:1rem 0 0.5rem;'>"
                f"{pivot_type} Pivot Levels</h3>", unsafe_allow_html=True)
    col_piv, col_mp = st.columns(2)

    with col_piv:
        if pivots:
            rows = []
            for k, v in sorted(pivots.items(), key=lambda x: x[1], reverse=True):
                dist  = round((v - ltp) / ltp * 100, 2)
                arrow = "▲" if v > ltp else "▼"
                star  = " ★" if analysis.get("nearest") and analysis["nearest"][0] == k else ""
                rows.append({"Level": k + star, "Price": v,
                             "Distance": f"{arrow} {abs(dist)}%"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with col_mp:
        st.markdown(
            "<div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;"
            "letter-spacing:0.1em;text-transform:uppercase;color:#5a6a48;"
            "margin-bottom:0.5rem;'>Market Profile (Volume at Price)</div>",
            unsafe_allow_html=True,
        )
        if mp:
            for label, val, col in [
                ("POC — Point of Control", mp.get("POC"), "#f5a623"),
                ("VAH — Value Area High",  mp.get("VAH"), "#b0b8d0"),
                ("VAL — Value Area Low",   mp.get("VAL"), "#b0b8d0"),
            ]:
                if val:
                    dist = round((val - ltp) / ltp * 100, 2)
                    arr  = "▲" if val > ltp else "▼"
                    st.markdown(
                        f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.8rem;"
                        f"padding:0.3rem 0;border-bottom:1px solid #dce3ed;'>"
                        f"<span style='color:{col};'>{label}</span>"
                        f"<b style='color:#1a1f0e;float:right;'>{val} "
                        f"<span style='color:#5a6a48;font-size:0.7rem;'>{arr}{abs(dist)}%</span>"
                        f"</b></div>",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("Market profile unavailable.")

    # ── ATR + Nearest Pivot + Signals ─────────────────────────────────────────
    st.divider()
    v1, v2, v3 = st.columns(3)

    with v1:
        st.markdown(
            f"<div class='pb-card'><div class='pb-card-title'>ATR(14) Volatility</div>"
            f"<div class='pb-card-value pb-neut'>"
            f"{'₹' + str(analysis['atr']) if analysis['atr'] else '—'}</div>"
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.73rem;color:#5a6a48;margin-top:0.4rem;'>"
            f"{'% of price: ' + str(analysis['atr_pct']) + '%' if analysis['atr_pct'] else ''}"
            f"</div></div>", unsafe_allow_html=True,
        )

    with v2:
        nl = analysis.get("nearest")
        st.markdown(
            f"<div class='pb-card'><div class='pb-card-title'>Nearest Pivot ★</div>"
            f"<div class='pb-card-value pb-neut'>"
            f"{nl[0] + '  ₹' + str(nl[1]) if nl else '—'}</div>"
            f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.73rem;color:#5a6a48;margin-top:0.4rem;'>"
            f"Immediate support / resistance</div></div>", unsafe_allow_html=True,
        )

    with v3:
        badges = (
            sig_badge(analysis["osc_sig"],      analysis["osc_col"])
            + sig_badge(analysis["hma_sig"],     analysis["hma_col"])
            + sig_badge(analysis["rsi_sig"],     analysis["rsi_col"])
            + sig_badge(analysis["cpr_position"].split("(")[0].strip(), analysis["cpr_col"])
        )
        st.markdown(
            f"<div class='pb-card'><div class='pb-card-title'>Active Signals</div>"
            f"<div style='margin-top:0.4rem;'>{badges}</div></div>",
            unsafe_allow_html=True,
        )

    # ── Virgin CPRs ────────────────────────────────────────────────────────────
    virgins = [v for v in analysis.get("virgin_cprs", []) if v["Virgin"]]
    if virgins:
        st.divider()
        st.markdown(
            "<h3 style='font-size:0.9rem;margin:1rem 0 0.25rem;'>🔲 Virgin CPR Levels</h3>"
            "<div style='font-family:IBM Plex Mono,monospace;font-size:0.72rem;color:#5a6a48;"
            "margin-bottom:0.5rem;'>Untouched CPR bands — Ochoa's high-significance price magnets</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(virgins)[["Date", "TC", "BC"]],
                     use_container_width=True, hide_index=True)

    # ── Stochastic ────────────────────────────────────────────────────────────
    # Stochastic is embedded in TV chart above; show Plotly fallback only
    df_ind = analysis.get("df_ind")
    _TV_CHARTS = False  # TradingView charts not used — using built-in Plotly
    if not _TV_CHARTS and df_ind is not None and "STOCH_K" in df_ind.columns:
        st.divider()
        st.plotly_chart(build_stoch_chart(df_ind), use_container_width=True)

    # ════════════════════════════════════════════════════════════════════════
    #  PDF REPORT — Trade Plan with Targets & Stop-Loss
    # ════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown(
        '<div class="title-bar" style="margin-top:0.25rem;">'
        '<h2 style="font-size:1.05rem;margin:0;">📄  Download Analysis Report (PDF)</h2>'
        '<span style="font-family:IBM Plex Mono,monospace;font-size:0.65rem;'
        'color:#5a6a48;margin-left:0.75rem;">'
        'Short Term · Medium Term · Long Term Targets · Stop-Loss · Narrative</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    pdf_col1, pdf_col2 = st.columns([2, 1])
    with pdf_col1:
        pdf_pattern = st.selectbox(
            "Trade Direction for PDF",
            ["Auto (from analysis)", "Bullish", "Bearish"],
            key="pdf_pattern",
            label_visibility="collapsed",
        )
    with pdf_col2:
        gen_pdf_btn = st.button("📄  Generate PDF Report", key="gen_pdf_btn",
                                use_container_width=True)

    if gen_pdf_btn:
        # Determine pattern
        if pdf_pattern == "Auto (from analysis)":
            auto_pat = "Bullish" if analysis.get("ov_col") == "bull" else "Bearish"
        else:
            auto_pat = pdf_pattern

        with st.spinner("Computing trade levels & building PDF…"):
            # Compute trade levels
            tl = compute_trade_levels(
                symbol=symbol,
                ltp=ltp,
                tc=cpr.get("TC", ltp),
                bc=cpr.get("BC", ltp),
                pivot=cpr.get("Pivot", ltp),
                pattern=auto_pat,
            )

            if not tl:
                st.error("Could not compute trade levels. Try again or switch to Daily timeframe.")
            else:
                pdf_bytes = generate_stock_pdf(
                    symbol=symbol,
                    tf_label=tf_label,
                    pivot_type=pivot_type,
                    analysis=analysis,
                    trade_levels=tl,
                )

                # Inline preview of key trade levels
                sh = tl.get("short",  {})
                md = tl.get("medium", {})
                lg = tl.get("long",   {})
                col_fg = "#00e5a0" if auto_pat == "Bullish" else "#ff4d6a"
                arrow  = "▲" if auto_pat == "Bullish" else "▼"

                st.markdown(
                    f"<div style='background:#edf7ee;border:1px solid {col_fg}33;"
                    f"border-left:4px solid {col_fg};border-radius:8px;"
                    f"padding:1rem 1.5rem;margin:0.5rem 0;'>"

                    f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.65rem;"
                    f"letter-spacing:0.12em;text-transform:uppercase;color:{col_fg}88;'>"
                    f"{arrow} {auto_pat} Trade Plan  ·  {symbol}</div>"

                    f"<div style='display:flex;gap:2rem;margin-top:0.6rem;flex-wrap:wrap;'>"

                    f"<div><div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;"
                    f"color:#5a6a48;text-transform:uppercase;'>Short Term (1-3d)</div>"
                    f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.9rem;"
                    f"color:#1a1f0e;'>T: <span style='color:{col_fg};font-weight:700;'>"
                    f"₹{sh.get('target',0):,.2f}</span>"
                    f" &nbsp; SL: <span style='color:#c0392b;'>₹{sh.get('sl',0):,.2f}</span>"
                    f" &nbsp; R:R <b>{sh.get('rr',0)}x</b></div></div>"

                    f"<div><div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;"
                    f"color:#5a6a48;text-transform:uppercase;'>Medium Term (1-4w)</div>"
                    f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.9rem;"
                    f"color:#1a1f0e;'>T1: <span style='color:{col_fg};font-weight:700;'>"
                    f"₹{md.get('target1',0):,.2f}</span>"
                    f" T2: <span style='color:{col_fg};font-weight:700;'>₹{md.get('target2',0):,.2f}</span>"
                    f" &nbsp; SL: <span style='color:#c0392b;'>₹{md.get('sl',0):,.2f}</span>"
                    f" &nbsp; R:R <b>{md.get('rr',0)}x</b></div></div>"

                    f"<div><div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;"
                    f"color:#5a6a48;text-transform:uppercase;'>Long Term (1-3m)</div>"
                    f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.9rem;"
                    f"color:#1a1f0e;'>T1: <span style='color:{col_fg};font-weight:700;'>"
                    f"₹{lg.get('target1',0):,.2f}</span>"
                    f" T2: <span style='color:{col_fg};font-weight:700;'>₹{lg.get('target2',0):,.2f}</span>"
                    f" T3: <span style='color:{col_fg};font-weight:700;'>₹{lg.get('target3',0):,.2f}</span>"
                    f" &nbsp; SL: <span style='color:#c0392b;'>₹{lg.get('sl',0):,.2f}</span>"
                    f" &nbsp; R:R <b>{lg.get('rr',0)}x</b></div></div>"

                    f"</div></div>",
                    unsafe_allow_html=True,
                )

                st.download_button(
                    label=f"⬇️  Download {symbol} PDF Report",
                    data=pdf_bytes,
                    file_name=f"PivotVault_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_download_btn",
                )

    # ── Methodology footnote ──────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<div style='font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#8a9a78;line-height:1.8;'>"
        "📖  Based on <i>Secrets of a Pivot Boss</i> by Frank Ochoa.  "
        "Tools implemented: CPR · 3/10 Oscillator · Virgin CPRs · Market Profile (POC/VAH/VAL) · "
        "HMA Trend Filter · ATR · RSI · Stochastic.  "
        "For educational purposes only — not financial advice.</div>",
        unsafe_allow_html=True,
    )


def page_watchlist():
    st.markdown("""
    <div class="title-bar">
        <span style="font-size:1.5rem;">⭐</span>
        <h1 style="color:#1a1f0e;">Watchlist</h1>
    </div>
    """, unsafe_allow_html=True)

    _nse500_wl = sorted(fetch_nse500_list()["Symbol"].dropna().tolist())
    wl       = st.session_state.get("watchlist", [])

    # ── Always-visible stock selector ────────────────────────────────────
    st.markdown("<div style='font-family:DM Mono,monospace;font-size:0.72rem;color:#5a6a48;margin-bottom:4px;'>Select stocks from NSE 500</div>", unsafe_allow_html=True)
    selected = st.multiselect(
        "wl_stocks",
        options=_nse500_wl,
        default=[s for s in wl if s in _nse500_wl],
        placeholder="Search — RELIANCE, TCS, INFY…",
        label_visibility="collapsed",
        key="wl_multiselect",
    )
    ac1, ac2, ac3, ac4 = st.columns([2, 1.5, 1.5, 1.5])
    with ac1:
        if st.button("Save Watchlist", use_container_width=True, key="wl_save"):
            st.session_state["watchlist"] = list(selected)
            st.session_state["wl_data"]   = {}
            st.rerun()
    with ac2:
        if st.button("Refresh Prices", use_container_width=True, key="wl_refresh"):
            with st.spinner("Fetching…"):
                st.session_state["wl_data"]         = refresh_watchlist_prices(selected)
                st.session_state["wl_last_refresh"] = datetime.now()
            st.rerun()
    with ac3:
        if st.button("Clear All", use_container_width=True, key="wl_clear"):
            st.session_state["watchlist"] = []
            st.session_state["wl_data"]   = {}
            st.rerun()
    with ac4:
        last = st.session_state.get("wl_last_refresh")
        if last:
            st.caption(f"Updated {last.strftime('%H:%M:%S')}")

    # Reload wl after possible save
    wl = st.session_state.get("watchlist", [])

    if not wl:
        st.markdown(
            "<div style='text-align:center;padding:3rem 1rem;margin-top:1rem;"
            "background:#f7f9f2;border:2px dashed #dae0cb;border-radius:12px;"
            "font-family:DM Mono,monospace;'>"
            "<div style='font-size:2rem;'>⭐</div>"
            "<div style='font-size:0.95rem;font-weight:700;color:#1a1f0e;margin-top:0.5rem;'>Watchlist is empty</div>"
            "<div style='font-size:0.8rem;color:#5a6a48;margin-top:0.4rem;'>"
            "Select stocks above and click Save Watchlist</div></div>",
            unsafe_allow_html=True,
        )
        return

    # ── Build active signals map (15m + 1h only) ─────────────────────────
    active_signals = {}
    for tf_key, tf_label, tf_col in [("cpr_scan_15m","15Min","#e67e22"),("cpr_scan_1h","1Hour","#2980b9")]:
        raw = st.session_state.get(tf_key)
        df  = raw if isinstance(raw, pd.DataFrame) else pd.DataFrame()
        if df.empty: continue
        for _, r in df.iterrows():
            sym = r["Symbol"]
            if sym not in active_signals: active_signals[sym] = []
            active_signals[sym].append({
                "tf": tf_label, "tf_col": tf_col,
                "side": "BUY" if r["Pattern"]=="Bullish" else "SELL",
                "entry": r["Entry"], "t1": r["T1"], "t2": r.get("T2",r["T1"]),
                "sl": r["SL"], "rr1": r["RR1"], "rr": r["RR1"],
                "strength": int(r["Strength%"]), "candle": r.get("Candle","—"),
            })

    # Auto-fetch prices
    if not st.session_state.get("wl_data") and wl:
        with st.spinner("Fetching live prices…"):
            st.session_state["wl_data"]         = refresh_watchlist_prices(wl)
            st.session_state["wl_last_refresh"] = datetime.now()
    data = st.session_state.get("wl_data", {})

    live_count = sum(1 for s in wl if s in active_signals)

    st.divider()

    # Summary metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Watchlist",    f"{len(wl)} stocks")
    m2.metric("Live Signals", f"{live_count} stocks")
    m3.metric("Watching",     f"{len(wl)-live_count} stocks")

    # Signal alert banner
    if live_count:
        st.markdown(
            f"<div style='background:#edf7ee;border:1px solid #b8dfc0;"
            f"border-left:4px solid #2d7a3a;border-radius:8px;"
            f"padding:0.6rem 1rem;margin:0.5rem 0;font-family:DM Mono,monospace;"
            f"font-size:0.78rem;display:flex;align-items:center;gap:10px;'>"
            f"<span class='live-dot'></span>"
            f"<b style='color:#2d7a3a;'>{live_count} stock(s) have LIVE signals now!</b></div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No watchlist stocks have active signals. Run CPR Scanner (15Min/1Hour) to generate signals.")
        if st.button("Go to CPR Scanner", key="wl_go_scanner"):
            st.session_state["current_page"] = "Scanner & Signals"
            st.rerun()

    st.divider()

    # ── Stocks WITH live signals ──────────────────────────────────────────
    wl_live  = [s for s in wl if s in active_signals]
    wl_quiet = [s for s in wl if s not in active_signals]

    if wl_live:
        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
            "color:#2d7a3a;font-weight:700;letter-spacing:0.08em;"
            "text-transform:uppercase;margin-bottom:0.75rem;'>"
            "🔔 LIVE SIGNALS</div>",
            unsafe_allow_html=True,
        )
        for sym in wl_live:
            d       = data.get(sym, {})
            ltp     = d.get("ltp")
            chg     = d.get("change")
            sigs    = active_signals[sym]
            ltp_str = f"Rs.{ltp:,.2f}" if ltp else "—"
            chg_col = "#2d7a3a" if chg and chg >= 0 else "#c0392b"
            chg_str = f"{'+' if chg and chg>=0 else ''}{chg:.2f}%" if chg is not None else "—"

            # Signal detail per timeframe
            sig_info = ""
            for sg in sigs:
                bull  = sg["side"]=="BUY"
                ac    = "#2d7a3a" if bull else "#c0392b"
                tc    = sg["tf_col"]
                rc    = "#2d7a3a" if sg["rr1"]>=2 else ("#b8860b" if sg["rr1"]>=1.5 else "#c0392b")
                sig_info += (
                    f"<div style='display:flex;flex-wrap:wrap;gap:5px;margin-top:6px;'>"
                    f"<span style='background:{tc}18;color:{tc};border:1px solid {tc}44;"
                    f"border-radius:12px;padding:1px 8px;font-size:0.65rem;font-weight:700;'>{sg['tf']}</span>"
                    f"<span style='background:{'#edf7ee' if bull else '#fdf0ee'};"
                    f"color:{ac};border:1px solid {'#b8dfc0' if bull else '#f0c0b8'};"
                    f"border-radius:20px;padding:1px 8px;font-size:0.65rem;font-weight:700;'>"
                    f"{'▲ BUY' if bull else '▼ SELL'}</span>"
                    f"<span style='font-size:0.67rem;color:#5a6a48;background:#f7f9f2;"
                    f"border:1px solid #dae0cb;border-radius:5px;padding:2px 7px;'>"
                    f"Entry {sg['entry']}</span>"
                    f"<span style='font-size:0.67rem;color:#2d7a3a;background:#edf7ee;"
                    f"border:1px solid #b8dfc0;border-radius:5px;padding:2px 7px;'>T1 {sg['t1']}</span>"
                    f"<span style='font-size:0.67rem;color:#c0392b;background:#fdf0ee;"
                    f"border:1px solid #f0c0b8;border-radius:5px;padding:2px 7px;'>SL {sg['sl']}</span>"
                    f"<span style='font-size:0.67rem;color:{rc};background:{rc}12;"
                    f"border:1px solid {rc}33;border-radius:5px;padding:2px 7px;font-weight:700;'>"
                    f"R:R {sg['rr1']}x</span>"
                    f"<span style='font-size:0.67rem;color:#5a6a48;background:#f7f9f2;"
                    f"border:1px solid #dae0cb;border-radius:5px;padding:2px 7px;'>"
                    f"{sg['strength']}% {sg['candle']}</span>"
                    f"</div>"
                )

            st.markdown(
                f"<div style='background:#ffffff;border:1px solid #b8dfc0;"
                f"border-left:4px solid #2d7a3a;border-radius:10px;"
                f"padding:0.85rem 1rem;margin-bottom:0.4rem;"
                f"box-shadow:0 2px 8px rgba(45,122,58,0.08);'>"
                f"<div style='display:flex;align-items:center;flex-wrap:wrap;"
                f"gap:8px;font-family:DM Mono,monospace;'>"
                f"<span style='font-size:1rem;font-weight:900;color:#1a1f0e;'>{sym}</span>"
                f"<span style='font-size:0.92rem;font-weight:700;color:#1a1f0e;'>{ltp_str}</span>"
                f"<span style='font-size:0.82rem;font-weight:600;color:{chg_col};'>{chg_str}</span>"
                f"</div>{sig_info}</div>",
                unsafe_allow_html=True,
            )
            for sg in sigs:
                _trade_buttons({**sg, "symbol": sym,
                                "t2": sg.get("t2", sg["t1"]),
                                "t3": sg.get("t1"), "rr1": sg["rr1"]})

    # ── Stocks WITHOUT signals ─────────────────────────────────────────────
    if wl_quiet:
        if wl_live: st.divider()
        st.markdown(
            f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
            f"color:#8a9a78;letter-spacing:0.08em;text-transform:uppercase;"
            f"margin-bottom:0.6rem;'>Watching — No Signal ({len(wl_quiet)})</div>",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for i, sym in enumerate(wl_quiet):
            d       = data.get(sym, {})
            ltp     = d.get("ltp")
            chg     = d.get("change")
            ltp_str = f"Rs.{ltp:,.2f}" if ltp else "—"
            chg_col = "#2d7a3a" if chg and chg >= 0 else "#c0392b"
            chg_str = f"{'+' if chg and chg>=0 else ''}{chg:.2f}%" if chg is not None else "—"
            with cols[i % 2]:
                st.markdown(
                    f"<div style='background:#ffffff;border:1px solid #dae0cb;"
                    f"border-left:3px solid #dae0cb;border-radius:8px;"
                    f"padding:0.6rem 0.9rem;margin-bottom:0.4rem;"
                    f"font-family:DM Mono,monospace;"
                    f"display:flex;align-items:center;justify-content:space-between;'>"
                    f"<b style='font-size:0.9rem;color:#1a1f0e;'>{sym}</b>"
                    f"<span style='font-size:0.85rem;font-weight:700;color:#1a1f0e;'>{ltp_str}</span>"
                    f"<span style='font-size:0.78rem;font-weight:600;color:{chg_col};'>{chg_str}</span>"
                    f"<span style='font-size:0.6rem;color:#8a9a78;'>watching</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.divider()
    with st.expander("Remove stocks from watchlist", expanded=False):
        if wl:
            rcols = st.columns(min(len(wl), 5))
            for i, sym in enumerate(wl):
                with rcols[i % 5]:
                    if st.button(f"x {sym}", key=f"rm_{sym}", use_container_width=True):
                        st.session_state["watchlist"].remove(sym)
                        if isinstance(st.session_state.get("wl_data"), dict):
                            st.session_state["wl_data"].pop(sym, None)
                        st.rerun()



# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────

# ═══════════════════════════════════════════════════════════════════
#  MULTI-TIMEFRAME CPR SCANNER  (new standalone tab)
# ═══════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────
#  FRANK OCHOA — CANDLESTICK PATTERN DETECTOR
# ─────────────────────────────────────────────────────────────────────

def detect_candlestick_pattern(df: pd.DataFrame) -> tuple:
    """
    Detect key Frank Ochoa / classic candlestick patterns on last 3 candles.
    Returns (pattern_name, signal_direction, pattern_strength_bonus)
    Based on: Bullish/Bearish Engulfing, Hammer, Shooting Star,
              Doji at CPR, Morning/Evening Star, Inside Bar, Pin Bar.
    """
    if len(df) < 3:
        return ("None", "neut", 0)

    c0 = df.iloc[-1]   # current candle
    c1 = df.iloc[-2]   # prev candle
    c2 = df.iloc[-3]   # 2 candles ago

    O0,H0,L0,C0 = float(c0["Open"]),float(c0["High"]),float(c0["Low"]),float(c0["Close"])
    O1,H1,L1,C1 = float(c1["Open"]),float(c1["High"]),float(c1["Low"]),float(c1["Close"])
    O2,H2,L2,C2 = float(c2["Open"]),float(c2["High"]),float(c2["Low"]),float(c2["Close"])

    body0 = abs(C0 - O0)
    body1 = abs(C1 - O1)
    body2 = abs(C2 - O2)
    rng0  = H0 - L0 if H0 > L0 else 1e-9
    rng1  = H1 - L1 if H1 > L1 else 1e-9

    upper_wick0 = H0 - max(O0, C0)
    lower_wick0 = min(O0, C0) - L0
    upper_wick1 = H1 - max(O1, C1)
    lower_wick1 = min(O1, C1) - L1

    bull0 = C0 > O0
    bear0 = C0 < O0
    bull1 = C1 > O1
    bear1 = C1 < O1

    # ── 1. Bullish Engulfing at CPR ──────────────────────────────────────────
    # Ochoa: When price engulfs prior candle after touching BC — powerful bull signal
    if (bear1 and bull0 and
        O0 <= C1 and C0 >= O1 and
        body0 > body1 * 1.1):
        return ("Bullish Engulfing", "bull", 15)

    # ── 2. Bearish Engulfing at CPR ──────────────────────────────────────────
    if (bull1 and bear0 and
        O0 >= C1 and C0 <= O1 and
        body0 > body1 * 1.1):
        return ("Bearish Engulfing", "bear", 15)

    # ── 3. Hammer (bullish reversal) ─────────────────────────────────────────
    # Long lower wick >= 2x body, small upper wick, at support / BC
    if (lower_wick0 >= 2 * body0 and
        upper_wick0 <= body0 * 0.4 and
        body0 > 0 and
        lower_wick0 >= rng0 * 0.55):
        return ("Hammer", "bull", 12)

    # ── 4. Shooting Star (bearish reversal) ──────────────────────────────────
    # Long upper wick >= 2x body, small lower wick, at resistance / TC
    if (upper_wick0 >= 2 * body0 and
        lower_wick0 <= body0 * 0.4 and
        body0 > 0 and
        upper_wick0 >= rng0 * 0.55):
        return ("Shooting Star", "bear", 12)

    # ── 5. Doji (indecision — strong at CPR) ─────────────────────────────────
    # Ochoa: Doji inside CPR = explosive breakout coming
    if body0 <= rng0 * 0.1 and rng0 > 0:
        return ("Doji at CPR", "neut", 8)

    # ── 6. Morning Star (3-candle bullish reversal) ───────────────────────────
    if (bear2 and body2 > 0 and
        abs(C1 - O1) <= min(body2, body0) * 0.3 and  # small middle
        bull0 and C0 > (O2 + C2) / 2):
        return ("Morning Star", "bull", 18)

    # ── 7. Evening Star (3-candle bearish reversal) ───────────────────────────
    if (bull2 and body2 > 0 and
        abs(C1 - O1) <= min(body2, body0) * 0.3 and
        bear0 and C0 < (O2 + C2) / 2):
        return ("Evening Star", "bear", 18)

    # ── 8. Inside Bar (Ochoa: compression before breakout) ───────────────────
    if H0 < H1 and L0 > L1:
        direction = "bull" if bull1 else "bear"
        return ("Inside Bar", direction, 10)

    # ── 9. Pin Bar / Rejection Candle ────────────────────────────────────────
    # Tail >= 3x body — strong rejection at key level
    if lower_wick0 >= 3 * body0 and body0 > 0:
        return ("Bull Pin Bar", "bull", 14)
    if upper_wick0 >= 3 * body0 and body0 > 0:
        return ("Bear Pin Bar", "bear", 14)

    # ── 10. Strong Bullish / Bearish candle (Marubozu) ───────────────────────
    if bull0 and body0 >= rng0 * 0.85:
        return ("Bullish Marubozu", "bull", 10)
    if bear0 and body0 >= rng0 * 0.85:
        return ("Bearish Marubozu", "bear", 10)

    return ("None", "neut", 0)


def compute_rr_levels(ltp: float, pattern_dir: str, tc: float, bc: float,
                      P: float, R1: float, R2: float, R3: float,
                      S1: float, S2: float, S3: float, atr: float) -> dict:
    """
    Compute Entry, Target, Stop-Loss and Risk:Reward ratio
    using Frank Ochoa pivot-based methodology.

    Ochoa Rule:
    - Bull: Entry above TC, SL below BC (or 0.5 ATR below entry)
    - Bear: Entry below BC, SL above TC (or 0.5 ATR above entry)
    - Targets: R1/R2/R3 for bull, S1/S2/S3 for bear
    - Minimum acceptable R:R = 1.5x
    """
    if pattern_dir == "bull":
        entry  = round(tc + atr * 0.1, 2)           # slight buffer above TC
        sl     = round(min(bc, ltp - atr * 0.5), 2)  # below BC or 0.5 ATR
        risk   = max(entry - sl, atr * 0.25)
        tgt1   = round(R1, 2)
        tgt2   = round(R2, 2)
        tgt3   = round(R3, 2)
        rr1    = round((tgt1 - entry) / risk, 2) if risk > 0 else 0
        rr2    = round((tgt2 - entry) / risk, 2) if risk > 0 else 0
        trail_sl = round(entry + (tgt1 - entry) * 0.5, 2)  # trail after 50% to T1
    else:
        entry  = round(bc - atr * 0.1, 2)
        sl     = round(max(tc, ltp + atr * 0.5), 2)
        risk   = max(sl - entry, atr * 0.25)
        tgt1   = round(S1, 2)
        tgt2   = round(S2, 2)
        tgt3   = round(S3, 2)
        rr1    = round((entry - tgt1) / risk, 2) if risk > 0 else 0
        rr2    = round((entry - tgt2) / risk, 2) if risk > 0 else 0
        trail_sl = round(entry - (entry - tgt1) * 0.5, 2)

    return {
        "entry": entry, "sl": sl, "risk": round(risk, 2),
        "tgt1": tgt1, "tgt2": tgt2, "tgt3": tgt3,
        "rr1": rr1, "rr2": rr2, "trail_sl": trail_sl,
    }
@st.cache_data(ttl=900, show_spinner=False)
def _cached_yf_batch(tickers_str: str, period: str, interval: str) -> bytes:
    """
    Module-level cached yfinance download.
    Returns the raw DataFrame serialised as parquet bytes so st.cache_data can hash it.
    Cached for 15 min — repeated scans (auto-refresh, re-runs) reuse this, zero network.
    """
    import io
    try:
        raw = yf.download(
            tickers_str,
            period=period,
            interval=interval,
            auto_adjust=True,
            progress=False,
            group_by="ticker",
            threads=True,
            repair=False,
            timeout=30,
        )
        if raw is None or raw.empty:
            return b""
        buf = io.BytesIO()
        raw.to_parquet(buf)
        return buf.getvalue()
    except Exception:
        return b""




@st.cache_data(ttl=900, show_spinner=False)
def scan_cpr_multi_tf(symbols: list, interval: str, period: str,
                      max_stocks: int = 200) -> pd.DataFrame:
    """
    Frank Ochoa CPR Scanner — Enhanced with Upstox data + strategy rationale.
    Timeframes: 15m / 30m / 1h / 1d / 1wk / 1mo
    Upstox used for data if token is active, else yfinance fallback.
    Each row includes a human-readable strategy rationale for backtest reference.
    """
    rows = []

    def _normalise_df(df: pd.DataFrame) -> pd.DataFrame:
        """Standardise any OHLCV DataFrame regardless of source/version."""
        if df is None or df.empty:
            return pd.DataFrame()
        try:
            # Flatten MultiIndex columns (yfinance >= 0.2.50)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] if isinstance(c, tuple) else str(c)
                               for c in df.columns]
            # Normalise column names to Title case
            df.columns = [str(c).strip().split("(")[0].strip().title()
                          for c in df.columns]
            # Fix timezone-aware index
            if hasattr(df.index, "tz") and df.index.tz is not None:
                try:
                    df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
                except Exception:
                    try:
                        df.index = df.index.tz_localize(None)
                    except Exception:
                        pass
            # Must have OHLCV
            if not {"Open","High","Low","Close","Volume"}.issubset(set(df.columns)):
                return pd.DataFrame()
            # Drop rows with NaN in key columns
            df = df.dropna(subset=["Open","High","Low","Close"])
            # Ensure numeric
            for col in ["Open","High","Low","Close","Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["Open","High","Low","Close"])
            return df
        except Exception:
            return pd.DataFrame()

    yf_interval_map = {
        "15m":"15m","30m":"30m","1h":"60m",
        "1d":"1d","1wk":"1wk","1mo":"1mo"
    }
    yf_iv = yf_interval_map.get(interval, interval)

    def _batch_fetch_yfinance(sym_batch: list) -> dict:
        """Use module-level cached download — zero network on repeat calls."""
        import io
        result = {}
        if not sym_batch:
            return result
        try:
            ticker_map = {
                (s if is_us_symbol(s) else s + ".NS"): s
                for s in sym_batch
            }
            tickers_str = " ".join(sorted(ticker_map.keys()))  # sorted = stable cache key
            raw_bytes = _cached_yf_batch(tickers_str, period, yf_iv)
            if not raw_bytes:
                return result
            raw = pd.read_parquet(io.BytesIO(raw_bytes))
            if raw.empty:
                return result
            if len(sym_batch) == 1:
                df = _normalise_df(raw.copy())
                sym = sym_batch[0]
                if not df.empty and len(df) >= 10:
                    result[sym] = df
            else:
                top_level = (raw.columns.get_level_values(0).unique().tolist()
                             if isinstance(raw.columns, pd.MultiIndex) else [])
                for ticker_sym, sym in ticker_map.items():
                    try:
                        if ticker_sym in top_level:
                            df = _normalise_df(raw[ticker_sym].copy())
                            if not df.empty and len(df) >= 10:
                                result[sym] = df
                    except Exception:
                        pass
        except Exception:
            pass
        return result

    def _fetch_upstox(sym: str) -> pd.DataFrame:
        """Fetch from Upstox historical API -- NSE stocks only; skip US symbols."""
        if is_us_symbol(sym):
            return pd.DataFrame()
        if not _upstox_connected() and not _upstox_has_credentials():
            return pd.DataFrame()
        try:
            lb_map = {"15m":"60d","30m":"90d","1h":"180d",
                      "1d":"365d","1wk":"730d","1mo":"1825d"}
            days    = int(lb_map.get(interval,"90d").replace("d",""))
            from_dt = (datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
            to_dt   = datetime.now().strftime("%Y-%m-%d")
            df      = upstox_get_historical(sym, interval, from_dt, to_dt)
            return _normalise_df(df)
        except Exception:
            return pd.DataFrame()

    sym_list = symbols[:max_stocks]
    sym_data = {}

    # ── Batch-fetch ALL 500 symbols via yfinance — chunked + parallel ───────────
    # yf.download() fetches a batch in ONE HTTP session. We split into 3 chunks
    # and run them in parallel threads so all 500 are done in ~the time of one.
    CHUNK = 200   # 200 tickers per batch call
    batches = [sym_list[i:i + CHUNK] for i in range(0, len(sym_list), CHUNK)]

    with ThreadPoolExecutor(max_workers=min(3, len(batches))) as _pool:
        _futs = {_pool.submit(_batch_fetch_yfinance, b): b for b in batches}
        for _fut in as_completed(_futs):
            try:
                sym_data.update(_fut.result())
            except Exception:
                pass

    # Upstox historical removed from scan loop (slow per-symbol calls).
    # Live LTP from Upstox is applied AFTER scoring on final signals only.

    # ── Fast WMA (numpy, no rolling apply) ─────────────────────────────────────
    def _wma_np(arr: np.ndarray, n: int) -> np.ndarray:
        """Weighted moving average — pure numpy, ~50x faster than rolling apply."""
        out = np.full(len(arr), np.nan)
        w   = np.arange(1, n + 1, dtype=float)
        ws  = w.sum()
        for i in range(n - 1, len(arr)):
            out[i] = np.dot(arr[i - n + 1:i + 1], w) / ws
        return out

    # ── Per-symbol scoring function (runs in parallel) ──────────────────────────
    def _score_symbol(sym):
        """Score one symbol. Returns a row-dict or None if filtered/errored."""
        try:
            df = sym_data.get(sym, pd.DataFrame())
            if df.empty or len(df) < 10:
                return None

            close  = df["Close"];  high = df["High"]
            low_s  = df["Low"];    vol  = df["Volume"]

            # ── CPR from prior completed candle ──────────────────────────────
            ref   = df.iloc[-2]
            H, L, C = float(ref["High"]), float(ref["Low"]), float(ref["Close"])
            P   = (H + L + C) / 3
            BC  = (H + L) / 2
            TC  = (P - BC) + P
            width = abs(TC - BC) / P * 100 if P else 0

            # CPR width limits per timeframe — Ochoa: narrow = trending day
            # 30M is primary (best quality), 15M tighter, 1H slightly wider
            if interval == "15m":   max_width = 2.0   # tight for scalp
            elif interval == "30m": max_width = 1.5   # 30M primary — strictest
            elif interval == "1h":  max_width = 2.5   # swing — allow wider
            else:                   max_width = 2.0
            if width > max_width:
                return None

            ltp = float(close.iloc[-1])

            # ── Pivot levels ─────────────────────────────────────────────────
            R1 = round(2*P-L,2);  R2 = round(P+(H-L),2);  R3 = round(H+2*(P-L),2)
            S1 = round(2*P-H,2);  S2 = round(P-(H-L),2);  S3 = round(L-2*(H-P),2)

            # ── HMA-20 ───────────────────────────────────────────────────────
            def wma(s, n):
                w = np.arange(1, n+1)
                return s.rolling(n).apply(lambda x: np.dot(x,w)/w.sum(), raw=True)
            hma    = wma(2*wma(close,10)-wma(close,20), 4)
            hma_up = bool(hma.iloc[-1]>hma.iloc[-2]) if len(hma.dropna())>=2 else None

            # ── 3/10 Oscillator ──────────────────────────────────────────────
            diff         = close.rolling(3).mean() - close.rolling(10).mean()
            sig16        = diff.rolling(16).mean()
            hist_val     = float(diff.iloc[-1]-sig16.iloc[-1]) if not np.isnan(diff.iloc[-1]) else 0
            osc_cross_bull = bool(diff.iloc[-1]>sig16.iloc[-1] and diff.iloc[-2]<=sig16.iloc[-2])
            osc_cross_bear = bool(diff.iloc[-1]<sig16.iloc[-1] and diff.iloc[-2]>=sig16.iloc[-2])

            # ── RSI-14 ───────────────────────────────────────────────────────
            delta = close.diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rsi   = float(100-(100/(1+gain.iloc[-1]/max(loss.iloc[-1],1e-9))))

            # ── ATR-14 ───────────────────────────────────────────────────────
            tr  = pd.concat([high-low_s,(high-close.shift()).abs(),(low_s-close.shift()).abs()],axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])

            # ── VWAP (20-bar) ────────────────────────────────────────────────
            tp   = (high+low_s+close)/3
            vwap = (tp*vol).rolling(20).sum()/vol.rolling(20).sum()
            above_vwap = bool(ltp>float(vwap.iloc[-1])) if not np.isnan(vwap.iloc[-1]) else None

            # ── Volume ───────────────────────────────────────────────────────
            vol_avg   = float(vol.rolling(20).mean().iloc[-1])
            vol_cur   = float(vol.iloc[-1])
            vol_surge = vol_cur > vol_avg*1.5 if vol_avg>0 else False

            # ── Stochastic %K (14,3) ─────────────────────────────────────────
            lo14 = low_s.rolling(14).min()
            hi14 = high.rolling(14).max()
            stk  = float(100*(close.iloc[-1]-lo14.iloc[-1])/max(hi14.iloc[-1]-lo14.iloc[-1],1e-9))
            stk_prev = float(100*(close.iloc[-2]-lo14.iloc[-2])/max(hi14.iloc[-2]-lo14.iloc[-2],1e-9))

            # ── Candlestick ──────────────────────────────────────────────────
            candle_name, candle_dir, candle_bonus = detect_candlestick_pattern(df)

            # ── Virgin CPR check ─────────────────────────────────────────────
            # CPR is virgin if price never closed inside it in last 10 bars
            inside_cpr = ((close.iloc[-12:-2] >= BC) & (close.iloc[-12:-2] <= TC)).any()
            virgin_cpr = not inside_cpr

            # ── Two-Day CPR Relationship (Frank Ochoa) ───────────────────────
            # Compare today's CPR with yesterday's CPR
            # Overlapping CPR → choppy/sideways day — avoid breakout trades
            # Non-overlapping CPR → trending day — high probability breakout
            if len(df) >= 4:
                ref_prev  = df.iloc[-3]
                H2p, L2p, C2p = float(ref_prev["High"]), float(ref_prev["Low"]), float(ref_prev["Close"])
                P2p  = (H2p + L2p + C2p) / 3
                BC2p = (H2p + L2p) / 2
                TC2p = (P2p - BC2p) + P2p
                # Overlap check: today's CPR overlaps yesterday's
                cpr_overlap   = not (TC < BC2p or BC > TC2p)
                cpr_above_prev = BC > TC2p   # today's CPR entirely above yesterday → strong bull
                cpr_below_prev = TC < BC2p   # today's CPR entirely below yesterday → strong bear
            else:
                cpr_overlap = False
                cpr_above_prev = cpr_below_prev = False

            # ── CPR Day-Type Classifier ───────────────────────────────────────
            if width < 0.25:
                day_type = "Trending"     # Narrow CPR → expect strong trend
            elif width < 0.5:
                day_type = "Moderate"
            elif cpr_overlap:
                day_type = "Sideways"     # Wide + overlapping → avoid
            else:
                day_type = "Volatile"

            # ── ATR Bar-Size for Extreme/Outside Reversal ────────────────────
            bar_sizes  = (high - low_s).rolling(10).mean()
            avg_bar    = float(bar_sizes.iloc[-1]) if not np.isnan(bar_sizes.iloc[-1]) else atr
            cur_bar    = float(high.iloc[-1] - low_s.iloc[-1])
            bar_mult   = cur_bar / avg_bar if avg_bar > 0 else 0

            # ── Extreme Reversal (Rubber Band) — Ochoa SPB Setup ─────────────
            # Price over-extended (bar_mult >= 2×) snapping back toward CPR
            extreme_bull = (bar_mult >= 2.0 and bear0 and ltp < BC and
                            float(low_s.iloc[-1]) < float(low_s.iloc[-5:-2].min()))
            extreme_bear = (bar_mult >= 2.0 and bull0 and ltp > TC and
                            float(high.iloc[-1]) > float(high.iloc[-5:-2].max()))

            # ── Outside Reversal (False Breakout Fade) — Ochoa SPB Setup ─────
            # Bar sweeps beyond prev H/L then reverses back inside
            outside_bull = (bar_mult >= 1.25 and
                            float(low_s.iloc[-1])  < float(low_s.iloc[-2]) and
                            float(close.iloc[-1])  > float(open.iloc[-2] if "Open" in df else close.iloc[-2]))
            outside_bear = (bar_mult >= 1.25 and
                            float(high.iloc[-1])   > float(high.iloc[-2]) and
                            float(close.iloc[-1])  < float(open.iloc[-2] if "Open" in df else close.iloc[-2]))

            # ── Frank Ochoa Scoring ──────────────────────────────────────────
            bull_pts = bear_pts = 0
            bull_reasons = []; bear_reasons = []

            # 1. CPR Position — core signal (3 pts)
            if ltp > TC:
                bull_pts += 3; bull_reasons.append("Price above CPR")
            elif ltp < BC:
                bear_pts += 3; bear_reasons.append("Price below CPR")

            # Virgin CPR bonus (2 pts) — highest quality setup
            if virgin_cpr and ltp > TC:
                bull_pts += 2; bull_reasons.append("Virgin CPR breakout")
            elif virgin_cpr and ltp < BC:
                bear_pts += 2; bear_reasons.append("Virgin CPR breakdown")

            # 2. HMA trend (2 pts)
            if hma_up is True:
                bull_pts += 2; bull_reasons.append("HMA trending up")
            elif hma_up is False:
                bear_pts += 2; bear_reasons.append("HMA trending down")

            # 3. 3/10 Oscillator (2 pts fresh cross, 1 pt continuation)
            if osc_cross_bull:
                bull_pts += 2; bull_reasons.append("3/10 bullish crossover")
            elif osc_cross_bear:
                bear_pts += 2; bear_reasons.append("3/10 bearish crossover")
            elif hist_val > 0:
                bull_pts += 1; bull_reasons.append("3/10 osc positive")
            else:
                bear_pts += 1; bear_reasons.append("3/10 osc negative")

            # 4. RSI zone (1 pt)
            if rsi >= 55:
                bull_pts += 1; bull_reasons.append(f"RSI {round(rsi,0)} bullish zone")
            elif rsi <= 45:
                bear_pts += 1; bear_reasons.append(f"RSI {round(rsi,0)} bearish zone")

            # 5. VWAP (1 pt)
            if above_vwap is True:
                bull_pts += 1; bull_reasons.append("Above VWAP")
            elif above_vwap is False:
                bear_pts += 1; bear_reasons.append("Below VWAP")

            # 6. Volume surge (1 pt)
            if vol_surge:
                if ltp >= P:
                    bull_pts += 1; bull_reasons.append("Volume surge bullish")
                else:
                    bear_pts += 1; bear_reasons.append("Volume surge bearish")

            # 7. Stochastic (1 pt)
            if stk < 25 and stk > stk_prev:
                bull_pts += 1; bull_reasons.append("Stoch oversold reversal")
            elif stk > 75 and stk < stk_prev:
                bear_pts += 1; bear_reasons.append("Stoch overbought reversal")

            # 8. Candlestick (2 pts)
            if candle_dir == "bull":
                bull_pts += 2; bull_reasons.append(f"{candle_name} pattern")
            elif candle_dir == "bear":
                bear_pts += 2; bear_reasons.append(f"{candle_name} pattern")

            # 8b. Wick Reversal at CPR (Ochoa SPB Setup — +3 pts)
            # Hammer/Pin Bar forming within 0.5×ATR of BC (bull) or TC (bear)
            _near_bc = abs(ltp - BC) <= atr * 0.5
            _near_tc = abs(ltp - TC) <= atr * 0.5
            if candle_name in ("Hammer", "Bull Pin Bar", "Morning Star", "Bullish Engulfing") and _near_bc:
                bull_pts += 3; bull_reasons.append(f"Wick Reversal at CPR BC ({candle_name})")
            elif candle_name in ("Shooting Star", "Bear Pin Bar", "Evening Star", "Bearish Engulfing") and _near_tc:
                bear_pts += 3; bear_reasons.append(f"Wick Reversal at CPR TC ({candle_name})")

            # 9. Pivot position bonus (1 pt)
            if ltp > P:
                bull_pts += 1; bull_reasons.append("Above Pivot P")
            elif ltp < P:
                bear_pts += 1; bear_reasons.append("Below Pivot P")

            # 10. CPR width bonus — narrow CPR = stronger signal (1 pt)
            if width < 0.25:
                if bull_pts >= bear_pts: bull_pts += 1; bull_reasons.append("Narrow CPR (<0.25%)")
                else: bear_pts += 1; bear_reasons.append("Narrow CPR (<0.25%)")

            # 11. Two-Day CPR Relationship (Ochoa — 3 pts, highest conviction)
            if cpr_above_prev:
                bull_pts += 3; bull_reasons.append("CPR above prior (trending bull day)")
            elif cpr_below_prev:
                bear_pts += 3; bear_reasons.append("CPR below prior (trending bear day)")
            elif cpr_overlap:
                # Overlapping CPR — PENALISE breakout signals (choppy day risk)
                bull_pts = max(0, bull_pts - 2)
                bear_pts = max(0, bear_pts - 2)
                bull_reasons.append("⚠️ Overlapping CPR (sideways risk)")
                bear_reasons.append("⚠️ Overlapping CPR (sideways risk)")

            # 12. Extreme Reversal / Outside Reversal bonus (2 pts each)
            if extreme_bull:
                bull_pts += 2; bull_reasons.append("Extreme reversal — rubber band bull")
            elif extreme_bear:
                bear_pts += 2; bear_reasons.append("Extreme reversal — rubber band bear")
            if outside_bull:
                bull_pts += 2; bull_reasons.append("Outside reversal — false breakdown fade")
            elif outside_bear:
                bear_pts += 2; bear_reasons.append("Outside reversal — false breakout fade")

            total = bull_pts + bear_pts
            if   bull_pts > bear_pts: pattern_main = "Bullish"; reasons = bull_reasons
            elif bear_pts > bull_pts: pattern_main = "Bearish"; reasons = bear_reasons
            else:                     pattern_main = "Neutral"; reasons = []

            strength = round(max(bull_pts, bear_pts) / max(total, 1) * 100)

            if pattern_main == "Neutral":
                return None

            # ── Targets & SL ─────────────────────────────────────────────────
            trade_dir = "bull" if pattern_main == "Bullish" else "bear"
            if trade_dir == "bull":
                entry = round(TC + atr*0.05, 2)
                if candle_name in ("Hammer","Bull Pin Bar","Bullish Engulfing","Morning Star"):
                    sl = round(min(BC, float(df["Low"].iloc[-1])) - atr*0.8, 2)  # PVAIv2: wider SL (was 0.1x)
                else:
                    sl = round(BC - atr*0.1, 2)
                risk = max(entry-sl, atr*0.2)
                t1, t2, t3 = R1, R2, R3
                if candle_name in ("Morning Star","Bullish Engulfing","Bullish Marubozu"):
                    t1 = R1 if R1>entry else R2
            else:
                entry = round(BC - atr*0.05, 2)
                if candle_name in ("Shooting Star","Bear Pin Bar","Bearish Engulfing","Evening Star"):
                    sl = round(max(TC, float(df["High"].iloc[-1])) + atr*0.8, 2)  # PVAIv2: wider SL (was 0.1x)
                else:
                    sl = round(TC + atr*0.1, 2)
                risk = max(sl-entry, atr*0.2)
                t1, t2, t3 = S1, S2, S3
                if candle_name in ("Evening Star","Bearish Engulfing","Bearish Marubozu"):
                    t1 = S1 if S1<entry else S2

            rr1 = round(abs(t1-entry)/risk, 2) if risk>0 else 0
            rr2 = round(abs(t2-entry)/risk, 2) if risk>0 else 0

            # ── PVAIv2: MINIMUM SL DISTANCE FILTER ─────────────────────────
            # Skip signals where SL is <0.5% from entry.
            # Trade analysis 27-Mar-2026: 17/18 SL hits had <0.5% SL distance.
            # Normal intraday noise / bid-ask spread triggers these immediately.
            _sl_dist_pct = abs(entry - sl) / entry * 100 if entry > 0 else 0
            if _sl_dist_pct < 0.50:
                return None  # SL too tight — normal noise will hit it, skip signal

            # ── PVAIv2: MINIMUM RR GATE ─────────────────────────────────────
            # After applying wider ATR-based SL, ensure reward still justifies risk.
            if rr1 < 1.5:
                return None  # Reward/Risk < 1.5x after wider SL — not worth taking

            cpr_type = "Narrow" if width<0.25 else ("Moderate" if width<0.5 else "Wide")

            # ── Strategy rationale string ────────────────────────────────────
            # Used in signal card + backtest reference
            top3 = reasons[:3] if len(reasons) >= 3 else reasons
            rationale = " · ".join(top3)
            if virgin_cpr:
                rationale = "⭐ Virgin CPR · " + rationale
            # Append Day Type and CPR overlap to rationale
            rationale += f" | {day_type} Day"
            if cpr_above_prev or cpr_below_prev:
                rationale += " | Non-Overlap CPR"
            if extreme_bull or extreme_bear:
                rationale += " | Extreme Reversal"
            if outside_bull or outside_bear:
                rationale += " | Outside Reversal"

            # ── Frank Ochoa Strategy Classifier ─────────────────────────
            # Match signal to the BEST fitting named strategy based on
            # conditions actually triggered — in priority order
            def _classify_strategy():
                # P1: Two-Day CPR Non-Overlap (highest conviction trending day)
                if (cpr_above_prev or cpr_below_prev) and width < 0.5:
                    return "Two-Day CPR Non-Overlap"
                # P2: Extreme Reversal (Rubber Band)
                if extreme_bull or extreme_bear:
                    return "Extreme Reversal (Rubber Band)"
                # P3: Outside Reversal (False Breakout Fade)
                if outside_bull or outside_bear:
                    return "Outside Reversal (False Breakout Fade)"
                # P4: Wick Reversal at CPR
                if candle_name in ("Hammer","Bull Pin Bar","Bullish Engulfing",
                                   "Shooting Star","Bear Pin Bar","Bearish Engulfing",
                                   "Morning Star","Evening Star"):
                    _near_bc = abs(ltp - BC) <= atr * 0.5
                    _near_tc = abs(ltp - TC) <= atr * 0.5
                    if _near_bc or _near_tc:
                        return "Wick Reversal at CPR"
                # P5: Virgin CPR Weekly Magnet
                if virgin_cpr and width < 0.5:
                    return "Virgin CPR Breakout"
                # P6: CPR Narrow Breakout (width < 0.5%, trending day)
                if width < 0.5 and day_type in ("Trending","Moderate"):
                    return "CPR Narrow Breakout"
                # P7: 3/10 Oscillator Cross
                if osc_cross_bull or osc_cross_bear:
                    return "3/10 Oscillator Cross"
                # P8: RSI + CPR Confluence
                if (pattern_main == "Bullish" and rsi >= 50) or                    (pattern_main == "Bearish" and rsi <= 50):
                    return "RSI + CPR Confluence"
                # P9: Candlestick + CPR
                if candle_name not in ("None","—",""):
                    return "Candlestick + CPR"
                # P10: HMA Trend Follower
                if hma_up is not None:
                    return "HMA Trend Follower"
                # Default
                return "CPR Signal"

            strat_name = _classify_strategy()
            strat_name = _build_strategy_name({
                "side":       pattern_main,
                "tf":         interval,
                "candle":     candle_name,
                "rsi":        round(rsi,1),
                "hma":        "▲" if hma_up else "▼",
                "vol":        "✅" if vol_surge else "—",
                "cpr_w":      round(width,3),
                "strength":   min(strength,100),
                "rr1":        rr1,
                "ltp":        ltp,
                "entry":      entry,
                "day_type":   day_type,
                "tf_label":   interval,
            })
            # Prepend strategy classification to name
            strat_name = f"{_classify_strategy()} — {strat_name}"

            rows.append({
                "Symbol":     sym,
                "LTP":        round(ltp,2),
                "CPR Width%": round(width,3),
                "CPR Type":   cpr_type,
                "Virgin CPR": "⭐ Yes" if virgin_cpr else "—",
                "Strategy":   strat_name,
                "Rationale":  rationale,
                "TC":         round(TC,2),  "BC": round(BC,2),  "Pivot P": round(P,2),
                "R1": R1,  "R2": R2,  "R3": R3,
                "S1": S1,  "S2": S2,  "S3": S3,
                "Pattern":    pattern_main,
                "Candle":     candle_name,
                "Strength%":  min(strength,100),
                "Day Type":   day_type,
                "CPR Overlap":cpr_overlap,
                "RSI":        round(rsi,1),
                "HMA":        "▲" if hma_up else "▼",
                "ATR":        round(atr,2),
                "Stoch%K":    round(stk,1),
                "Vol Surge":  "✅" if vol_surge else "—",
                "Osc Cross":  "🔼" if osc_cross_bull else ("🔽" if osc_cross_bear else "—"),
                "Entry":      entry,
                "SL":         sl,
                "T1":         round(t1,2),  "T2": round(t2,2),  "T3": round(t3,2),
                "RR1":        rr1,           "RR2": rr2,
                "Risk Rs":    round(risk,2),
            })
        except Exception:
            return None

    # ── Parallel scoring across all symbols ─────────────────────────────────────
    rows = []
    _score_workers = min(8, len(sym_list))   # capped — Streamlit Cloud has a low thread ulimit
    with ThreadPoolExecutor(max_workers=_score_workers) as _sp:
        for row in _sp.map(_score_symbol, sym_list):
            if row is not None:
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    df_out = pd.DataFrame(rows)
    df_out = df_out.sort_values(["Strength%","CPR Width%"], ascending=[False,True]).reset_index(drop=True)

    # ── Upstox live LTP enrichment on final signals only (NOT all 500 stocks) ──
    # One batch call for the ~10-50 signal symbols → fast, no slowdown at all.
    if _upstox_connected() and "Symbol" in df_out.columns:
        try:
            sig_syms = df_out["Symbol"].dropna().tolist()
            ltp_map  = upstox_get_live_ltp_batch(sig_syms)
            if ltp_map:
                df_out["Entry"] = df_out.apply(
                    lambda r: round(ltp_map.get(r["Symbol"], r["Entry"]), 2), axis=1
                )
        except Exception:
            pass

    return df_out


def build_scanner_pdf(top_bull: pd.DataFrame, top_bear: pd.DataFrame,
                      tf_choice: str, scan_time_str: str) -> bytes:
    """Build CPR Scanner PDF report. Returns bytes."""
    import io as _io
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_c
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle as PS

    buf  = _io.BytesIO()
    doc  = SimpleDocTemplate(buf, pagesize=A4,
                              leftMargin=14*mm, rightMargin=14*mm,
                              topMargin=13*mm,  bottomMargin=13*mm)
    W    = A4[0] - 28*mm

    OLIVE  = rl_c.HexColor("#1e293b")
    GREEN  = rl_c.HexColor("#16a34a")
    RED    = rl_c.HexColor("#dc2626")
    AMBER  = rl_c.HexColor("#d97706")
    LIGHT  = rl_c.HexColor("#f8fafc")
    BORDER = rl_c.HexColor("#e2e8f0")
    WHITE  = rl_c.white

    s_title = PS("t", fontSize=15, fontName="Helvetica-Bold",
                 textColor=rl_c.HexColor("#1a2332"), leading=20, spaceAfter=3)
    s_sub   = PS("s", fontSize=8,  fontName="Helvetica",
                 textColor=rl_c.HexColor("#5a6a80"), leading=12, spaceAfter=8)
    s_h     = PS("h", fontSize=9,  fontName="Helvetica-Bold",
                 textColor=rl_c.HexColor("#1a2332"), leading=13, spaceBefore=8, spaceAfter=4)
    s_disc  = PS("d", fontSize=7,  fontName="Helvetica",
                 textColor=rl_c.HexColor("#94a3b8"), leading=10)

    story = []
    story.append(Paragraph("PivotVault AI — CPR Scanner Report", s_title))
    story.append(Paragraph(
        f"{tf_choice}  ·  Frank Ochoa Strategy  ·  {scan_time_str}", s_sub))
    story.append(HRFlowable(width=W, thickness=1, color=BORDER, spaceAfter=5))

    def _tbl(df, direction):
        is_bull = direction == "Bullish"
        hdr_c   = GREEN if is_bull else RED
        arrow   = "▲" if is_bull else "▼"
        story.append(Paragraph(
            f"{arrow} {direction} Setups — Top 10 · Pivot-Based Targets · Frank Ochoa", s_h))
        if df.empty:
            story.append(Paragraph(f"No {direction} setups found.", s_disc))
            return
        hdrs = ["Symbol","LTP","Score","Candle","Entry","T1","T2","SL","R:R","RSI","CPR%"]
        data = [hdrs]
        for _, r in df.iterrows():
            rr   = r.get("RR1", 0)
            data.append([
                str(r["Symbol"]),
                f"Rs.{r['LTP']:,.2f}",
                f"{int(r['Strength%'])}%",
                str(r.get("Candle","—")),
                f"Rs.{r['Entry']:,.2f}",
                f"Rs.{r['T1']:,.2f}",
                f"Rs.{r['T2']:,.2f}",
                f"Rs.{r['SL']:,.2f}",
                f"{rr}x",
                str(r["RSI"]),
                f"{r.get('CPR Width%',0):.3f}%",
            ])
        cw = [W*0.1,W*0.09,W*0.07,W*0.13,W*0.09,W*0.09,W*0.09,W*0.08,W*0.07,W*0.08,W*0.1]
        tbl = Table(data, colWidths=cw, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), OLIVE),
            ("TEXTCOLOR",     (0,0), (-1,0), WHITE),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,-1), 7),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT]),
            ("GRID",          (0,0), (-1,-1), 0.4, BORDER),
            ("PADDING",       (0,0), (-1,-1), 4),
            ("TEXTCOLOR",     (2,1), (2,-1),  hdr_c),
            ("FONTNAME",      (2,1), (2,-1),  "Helvetica-Bold"),
            ("TEXTCOLOR",     (4,1), (6,-1),  hdr_c),
            ("TEXTCOLOR",     (7,1), (7,-1),  RED),
            ("FONTNAME",      (0,1), (0,-1),  "Helvetica-Bold"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 5*mm))

    _tbl(top_bull, "Bullish")
    _tbl(top_bear, "Bearish")
    story.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=3))
    story.append(Paragraph(
        "DISCLAIMER: Educational/informational purposes only. Not financial advice. "
        "Entry/Target/SL levels derived from Frank Ochoa Pivot Boss methodology + ATR-14. "
        "Always use proper risk management. Consult a SEBI-registered advisor.",
        s_disc,
    ))
    doc.build(story)
    buf.seek(0)
    return buf.read()


def send_scanner_pdf_email(pdf_bytes: bytes, to_email: str, tf_label: str,
                           scan_time: str, smtp_cfg: dict) -> tuple:
    """Send CPR Scanner PDF as email attachment."""
    import smtplib, ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text    import MIMEText
    from email.mime.base    import MIMEBase
    from email              import encoders
    try:
        msg            = MIMEMultipart()
        msg["Subject"] = f"PivotVault AI — CPR Scanner {tf_label} — {scan_time}"
        msg["From"]    = smtp_cfg["sender"]
        msg["To"]      = to_email

        body = MIMEText(
            f"<html><body style='font-family:monospace;'>"
            f"<h2 style='color:#1a1f0e;'>PivotVault AI — CPR Scanner Auto-Report</h2>"
            f"<p style='color:#5a6a48;'>{tf_label} &nbsp;|&nbsp; {scan_time}</p>"
            f"<p>Please find the latest CPR Scanner report attached as PDF.</p>"
            f"<p style='color:#2d7a3a;'>Scan completed automatically. Top 10 Bullish + Top 10 Bearish stocks.</p>"
            f"<hr/>"
            f"<p style='color:#8a9a78;font-size:0.8em;'>For educational purposes only. Not financial advice.</p>"
            f"</body></html>",
            "html"
        )
        msg.attach(body)

        # Attach PDF
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        fname = f"PivotVault_Scanner_{scan_time.replace(' ','_').replace(':','')}.pdf"
        part.add_header("Content-Disposition", f"attachment; filename={fname}")
        msg.attach(part)

        ctx = ssl.create_default_context()
        if smtp_cfg["port"] == 465:
            with smtplib.SMTP_SSL(smtp_cfg["host"], 465, context=ctx) as s:
                s.login(smtp_cfg["sender"], smtp_cfg["password"])
                s.sendmail(smtp_cfg["sender"], to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as s:
                s.ehlo(); s.starttls(context=ctx)
                s.login(smtp_cfg["sender"], smtp_cfg["password"])
                s.sendmail(smtp_cfg["sender"], to_email, msg.as_string())
        return True, "✅ Auto-report sent!"
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════
#  BROKER INTEGRATION — Zerodha Kite · Upstox · Groww
# ══════════════════════════════════════════════════════════════

def _zerodha_place_order(symbol: str, side: str, qty: int,
                          order_type: str = "MARKET") -> tuple:
    """Place order via Zerodha Kite API. Returns (success, order_id/error)."""
    try:
        from kiteconnect import KiteConnect
        api_key      = st.session_state.get("zerodha_api_key", "")
        access_token = st.session_state.get("zerodha_access_token", "")
        if not api_key or not access_token:
            return False, "Zerodha not configured. Add API key & access token in ⚙️ Broker Settings."
        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)
        tx = kite.TRANSACTION_TYPE_BUY if side == "BUY" else kite.TRANSACTION_TYPE_SELL
        order_id = kite.place_order(
            tradingsymbol   = symbol,
            exchange        = kite.EXCHANGE_NSE,
            transaction_type= tx,
            quantity        = qty,
            order_type      = kite.ORDER_TYPE_MARKET,
            product         = kite.PRODUCT_MIS,
            variety         = kite.VARIETY_REGULAR,
        )
        return True, str(order_id)
    except ImportError:
        return False, "kiteconnect not installed. Run: pip install kiteconnect"
    except Exception as e:
        return False, str(e)


def _upstox_place_order(symbol: str, side: str, qty: int) -> tuple:
    """Place order via Upstox API v2. Returns (success, order_id/error)."""
    try:
        import upstox_client
        access_token = st.session_state.get("upstox_access_token", "")
        if not access_token:
            return False, "Upstox not configured. Add access token in ⚙️ Broker Settings."
        config = upstox_client.Configuration()
        config.access_token = access_token
        api = upstox_client.OrderApi(upstox_client.ApiClient(config))
        req = upstox_client.PlaceOrderRequest(
            quantity        = qty,
            product         = "I",
            validity        = "DAY",
            price           = 0,
            tag             = "PivotVault",
            instrument_token= f"NSE_EQ|{symbol}",
            order_type      = "MARKET",
            transaction_type= side,
            disclosed_quantity = 0,
            trigger_price   = 0,
            is_amo          = False,
        )
        res = api.place_order(req, "2.0")
        return True, str(res.data.order_id)
    except ImportError:
        return False, "upstox-python-sdk not installed. Run: pip install upstox-python-sdk"
    except Exception as e:
        return False, str(e)


def _render_groww_signals(signals: list):
    """
    Show trade signal popup cards with:
    - Desktop browser notification
    - Groww deep link
    - Zerodha one-click order
    - Upstox one-click order
    - Paper trade button
    """
    import json
    broker      = st.session_state.get("broker", "none")
    signals_json = json.dumps(signals)

    groww_html = f"""
<style>
@keyframes slideDown {{
    from {{ opacity:0; transform:translateY(-30px) scale(0.96); }}
    to   {{ opacity:1; transform:translateY(0) scale(1); }}
}}
@keyframes glow {{
    0%,100% {{ box-shadow: 0 0 0 0 rgba(78,97,48,0.4); }}
    50%      {{ box-shadow: 0 0 0 8px rgba(78,97,48,0); }}
}}
.pv-signal-popup {{
    position: fixed; top: 16px; right: 16px;
    z-index: 999999;
    display: flex; flex-direction: column; gap: 10px;
    max-width: 360px; width: 92vw;
}}
.pv-signal-card {{
    background: #fff;
    border-radius: 14px;
    padding: 14px 15px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.18);
    animation: slideDown 0.3s cubic-bezier(.2,.8,.3,1);
    border-top: 4px solid #4e6130;
    font-family: DM Sans, sans-serif;
    position: relative;
}}
.pv-signal-card.bear {{ border-top-color: #c0392b; }}
.pv-sc-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }}
.pv-sc-sym {{ font-size:1.05rem; font-weight:800; color:#1a1f0e; }}
.pv-sc-badge {{
    border-radius:20px; padding:2px 10px;
    font-size:0.7rem; font-weight:700; letter-spacing:0.06em;
}}
.bull-badge {{ background:#edf7ee; color:#2d7a3a; border:1px solid #b8dfc0; }}
.bear-badge {{ background:#fdf0ee; color:#c0392b; border:1px solid #f0c0b8; }}
.pv-sc-levels {{
    display:grid; grid-template-columns:1fr 1fr 1fr;
    gap:5px; margin-bottom:8px;
}}
.pv-sc-lev {{
    background:#f7f9f2; border-radius:7px;
    padding:5px 3px; text-align:center;
}}
.pv-sc-ll {{ font-size:0.58rem; color:#8a9a78; text-transform:uppercase; letter-spacing:0.07em; font-family:DM Mono,monospace; }}
.pv-sc-lv {{ font-size:0.82rem; font-weight:700; color:#1a1f0e; font-family:DM Mono,monospace; }}
.pv-sc-meta {{ font-size:0.68rem; color:#8a9a78; font-family:DM Mono,monospace; margin-bottom:10px; }}
.pv-broker-btns {{ display:flex; flex-direction:column; gap:6px; }}
.pv-btn {{
    display:block; width:100%; padding:9px 0;
    border:none; border-radius:8px;
    font-size:0.82rem; font-weight:700;
    cursor:pointer; text-align:center;
    text-decoration:none; color:#fff !important;
    transition:opacity 0.15s, transform 0.1s;
    letter-spacing:0.02em;
}}
.pv-btn:hover {{ opacity:0.88; transform:scale(0.99); }}
.btn-groww  {{ background:linear-gradient(135deg,#00b386,#007a60); animation:glow 2.5s ease infinite; }}
.btn-zerodha {{ background:linear-gradient(135deg,#387ed1,#2563b0); }}
.btn-upstox  {{ background:linear-gradient(135deg,#7c3aed,#5b21b6); }}
.btn-paper   {{ background:linear-gradient(135deg,#f59e0b,#d97706); }}
.btn-bear-groww   {{ background:linear-gradient(135deg,#e74c3c,#c0392b); }}
.btn-bear-zerodha {{ background:linear-gradient(135deg,#e74c3c,#991b1b); }}
.btn-bear-upstox  {{ background:linear-gradient(135deg,#db2777,#9d174d); }}
.pv-dismiss {{
    position:absolute; top:8px; right:10px;
    background:none; border:none; font-size:0.95rem;
    cursor:pointer; color:#8a9a78; padding:2px 5px;
}}
.pv-dismiss:hover {{ color:#c0392b; }}
.pv-notif-bar {{
    background:#1a1f0e; color:#f4f7ec;
    border-radius:10px; padding:9px 13px;
    font-size:0.76rem; font-family:DM Mono,monospace;
    display:flex; align-items:center; gap:8px;
    animation:slideDown 0.2s ease;
}}
.pv-notif-bar button {{
    margin-left:auto; background:#4e6130; color:#fff;
    border:none; border-radius:6px;
    padding:4px 10px; font-size:0.73rem;
    font-family:DM Mono,monospace; cursor:pointer; font-weight:700;
}}
</style>

<div class="pv-signal-popup" id="pvPopup"></div>

<script>
var PV_SIGNALS   = {signals_json};
var PV_BROKER    = "{broker}";

function growwUrl(sym) {{
    return "https://groww.in/stocks/" + sym.toLowerCase() + "-share-price";
}}
function zerodhaUrl(sym, side) {{
    // Zerodha Kite web order form deep link
    return "https://kite.zerodha.com/orders?exchange=NSE&tradingsymbol=" +
           sym + "&transaction_type=" + side;
}}
function upstoxUrl(sym, side) {{
    return "https://pro.upstox.com/stocks/details/NSE/" + sym;
}}

function buildCards() {{
    var popup = document.getElementById("pvPopup");
    if (!popup) return;
    popup.innerHTML = "";

    var w = window.parent || window;
    if (!w._pvNotifEnabled && w.Notification && w.Notification.permission !== "denied") {{
        var bar = document.createElement("div");
        bar.className = "pv-notif-bar";
        bar.innerHTML = "🔔 Enable desktop notifications for instant trade alerts &nbsp;<button onclick=\"reqNotif()\">Allow</button>";
        popup.appendChild(bar);
    }}

    PV_SIGNALS.forEach(function(sig, idx) {{
        var bull = sig.side === "BUY";
        var card = document.createElement("div");
        card.className = "pv-signal-card" + (bull ? "" : " bear");
        card.id = "pvCard" + idx;

        var btns = "";

        // Groww button (always show)
        btns += "<a href=\"" + growwUrl(sig.symbol) + "\" target=\"_blank\" class=\"pv-btn " +
                (bull ? "btn-groww" : "btn-bear-groww") + "\">" +
                (bull ? "🟢 Buy on Groww" : "🔴 Sell on Groww") + "</a>";

        // Zerodha button
        btns += "<a href=\"" + zerodhaUrl(sig.symbol, sig.side) + "\" target=\"_blank\" class=\"pv-btn " +
                (bull ? "btn-zerodha" : "btn-bear-zerodha") + "\">" +
                "⚡ " + sig.side + " on Zerodha Kite</a>";

        // Upstox button
        btns += "<a href=\"" + upstoxUrl(sig.symbol, sig.side) + "\" target=\"_blank\" class=\"pv-btn " +
                (bull ? "btn-upstox" : "btn-bear-upstox") + "\">" +
                "💜 " + sig.side + " on Upstox</a>";

        // Paper trade button
        btns += "<button class=\"pv-btn btn-paper\" onclick=\"paperTrade(" + idx + ")\">" +
                "📝 Paper Trade (Test)</button>";

        card.innerHTML =
            "<button class=\"pv-dismiss\" onclick=\"dismissCard(" + idx + ")\">✕</button>" +
            "<div class=\"pv-sc-head\">" +
            "  <span class=\"pv-sc-sym\">" + sig.symbol + "</span>" +
            "  <span class=\"pv-sc-badge " + (bull ? "bull-badge" : "bear-badge") + "\">" + sig.side + "</span>" +
            "</div>" +
            "<div class=\"pv-sc-levels\">" +
            "  <div class=\"pv-sc-lev\"><div class=\"pv-sc-ll\">Entry</div><div class=\"pv-sc-lv\">₹" + sig.entry + "</div></div>" +
            "  <div class=\"pv-sc-lev\"><div class=\"pv-sc-ll\">Target</div><div class=\"pv-sc-lv\">₹" + sig.t1 + "</div></div>" +
            "  <div class=\"pv-sc-lev\"><div class=\"pv-sc-ll\">SL</div><div class=\"pv-sc-lv\">₹" + sig.sl + "</div></div>" +
            "</div>" +
            "<div class=\"pv-sc-meta\">R:R " + sig.rr + "x · Strength " + sig.strength + "% · " + sig.candle + "</div>" +
            "<div class=\"pv-broker-btns\">" + btns + "</div>";

        popup.appendChild(card);

        // Desktop notification — use parent window to escape iframe sandbox
        (function() {{
            var w = window.parent || window;
            if (w._pvNotify) {{
                w._pvNotify(
                    (bull ? "🟢 BUY" : "🔴 SELL") + " — " + sig.symbol + " (" + sig.strength + "%)",
                    "Entry ₹" + sig.entry + "  T1 ₹" + sig.t1 + "  SL ₹" + sig.sl + "  R:R " + sig.rr + "x",
                    "pv-" + sig.symbol
                );
            }} else if (w.Notification && w.Notification.permission === "granted") {{
                var n = new w.Notification(
                    (bull ? "🟢 BUY" : "🔴 SELL") + " — " + sig.symbol + " (" + sig.strength + "%)",
                    {{ body: "Entry ₹" + sig.entry + "  T1 ₹" + sig.t1 + "  SL ₹" + sig.sl + "  R:R " + sig.rr + "x",
                       icon: "/static/icon-192.png", tag: "pv-" + sig.symbol, requireInteraction: false }}
                );
                n.onclick = function() {{ w.focus(); n.close(); }};
            }}
        }})();
    }});

    setTimeout(function() {{
        var p = document.getElementById("pvPopup");
        if (p) p.style.opacity = "0.3";
    }}, 90000);
}}

function dismissCard(idx) {{
    var c = document.getElementById("pvCard" + idx);
    if (c) {{ c.style.transform = "translateX(110%)"; c.style.opacity = "0";
               c.style.transition = "all 0.3s"; setTimeout(function(){{ c.remove(); }}, 300); }}
}}

function paperTrade(idx) {{
    var sig = PV_SIGNALS[idx];
    // Store in sessionStorage for paper trade tab to pick up
    var trades = JSON.parse(sessionStorage.getItem("pv_paper_queue") || "[]");
    trades.push(sig);
    sessionStorage.setItem("pv_paper_queue", JSON.stringify(trades));
    alert("📝 Paper trade queued for " + sig.symbol + " " + sig.side +
          " @ ₹" + sig.entry + "\nGo to Test Trading tab to see result.");
    dismissCard(idx);
}}

function reqNotif() {{
    var w = window.parent || window;
    if (w._pvRequestNotif) {{
        w._pvRequestNotif(function(ok) {{
            w._pvNotifEnabled = ok;
            if (ok) buildCards();
        }});
    }} else if (w.Notification) {{
        w.Notification.requestPermission().then(function(p) {{
            w._pvNotifEnabled = (p === "granted");
            if (p === "granted") buildCards();
        }});
    }}
}}

buildCards();
</script>
"""
    st.markdown(groww_html, unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════════════════════
#  TOP 5 BEST TRADES ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def _signal_rank_score_global(row, tf_tag: str) -> float:
    try:
        s    = float(row.get("Strength%",   0) or 0)
        rr   = float(row.get("RR1",         1.0) or 1.0)
        cw   = float(row.get("CPR Width%",  1.0) or 1.0)
        dt   = str(row.get("Day Type",      ""))
        ov   = bool(row.get("CPR Overlap",  False))
        cn   = str(row.get("Candle",        ""))
        rsi  = float(row.get("RSI",         50) or 50)
        hma  = str(row.get("HMA",           ""))
        vol  = str(row.get("Vol Surge",     ""))
        side = str(row.get("Pattern",       ""))
    except Exception:
        return 0.0
    score = (s * 0.35) + (rr * 15)
    if cw < 0.25:   score += 20
    elif cw < 0.5:  score += 10
    elif cw > 1.0:  score -= 10
    if dt == "Trending":    score += 25
    elif dt == "Moderate":  score += 10
    elif dt == "Sideways":  score -= 40
    elif dt == "Volatile":  score -= 5
    if ov: score -= 30
    _premium = {
        "Morning Star": 20, "Evening Star": 20,
        "Bullish Engulfing": 18, "Bearish Engulfing": 18,
        "Bull Pin Bar": 15, "Bear Pin Bar": 15,
        "Hammer": 12, "Shooting Star": 12,
        "Bullish Marubozu": 8, "Bearish Marubozu": 8,
        "Inside Bar": 5, "Doji at CPR": 3,
    }
    score += _premium.get(cn, 0)
    if side == "Bullish" and rsi >= 55:   score += 8
    elif side == "Bearish" and rsi <= 45: score += 8
    elif side == "Bullish" and rsi <= 40: score -= 5
    elif side == "Bearish" and rsi >= 60: score -= 5
    if ("\u25b2" in hma and side == "Bullish") or ("\u25bc" in hma and side == "Bearish"):
        score += 10
    if "\u2705" in vol: score += 8
    if   "30m" in tf_tag: score += 15
    elif "1h"  in tf_tag: score += 8
    elif "15m" in tf_tag: score += 5
    try:
        return round(score, 2)
    except Exception:
        return 0.0


def _get_top5_best_trades(market_list: list) -> list:
    # Top 5 now scans 30m + 1h only (15m dropped) — cuts parallel scan load by 1/3.
    # Periods match the optimized values used by the manual scanner.
    TF_SCAN_CONFIGS = [
        {"interval": "30m", "period": "7d",   "tag": "30m", "label": "\u23f1\ufe0f 30 Min", "color": "#ea580c"},
        {"interval": "1h",  "period": "14d",  "tag": "1h",  "label": "\U0001f55010 1 Hour", "color": "#1d4ed8"},
    ]
    def _scan_one_tf(cfg):
        try:
            result = scan_cpr_multi_tf(
                market_list, interval=cfg["interval"],
                period=cfg["period"], max_stocks=len(market_list),
            )
            if result is None or result.empty: return []
            if "Pattern" not in result.columns: return []
            directional = result[result["Pattern"] != "Neutral"].copy()
            if directional.empty: return []
            # ── BEST-SETUP QUALITY GATES (same as Trade Signals feed) ──────────
            directional["_sl_dist_pct"]   = (abs(directional["Entry"] - directional["SL"])
                                              / directional["Entry"].replace(0, np.nan) * 100)
            directional["_spot_dist_pct"] = (abs(directional["LTP"] - directional["Entry"])
                                              / directional["Entry"].replace(0, np.nan) * 100)
            directional = directional[
                (directional["RR1"]            >= 2.0) &
                (directional["Strength%"]      >= 75)  &
                (directional["_sl_dist_pct"]   >= 0.50) &
                (directional["_spot_dist_pct"] >= 0.25)
            ].copy()
            if directional.empty: return []
            directional["_tf_tag"]     = cfg["tag"]
            directional["_tf_label"]   = cfg["label"]
            directional["_tf_color"]   = cfg["color"]
            directional["_rank_score"] = directional.apply(
                lambda row: _signal_rank_score_global(row, cfg["tag"]), axis=1)
            return directional.to_dict("records")
        except Exception:
            return []
    all_signals = []
    # Sequential — _cached_yf_batch means no extra network cost per timeframe.
    # Avoids nested thread pool explosion that crashes Streamlit Cloud containers.
    for cfg in TF_SCAN_CONFIGS:
        try:
            all_signals.extend(_scan_one_tf(cfg))
        except Exception:
            pass
    if not all_signals: return []
    all_signals.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
    seen, top5 = set(), []
    for sig in all_signals:
        sym = sig.get("Symbol", "")
        if sym and sym not in seen:
            seen.add(sym); top5.append(sig)
        if len(top5) >= 5: break
    return top5

def page_scanner_signals(nse500: pd.DataFrame):
    """CPR Scanner + Trade Signals merged."""
    import json
    tab_scan, tab_sig = st.tabs(["📡  Scanner", "🎯  Trade Signals"])
    with tab_scan:
        # ── Global Market Toggle (persisted across refresh) ───────────────
        # Default: NSE 500. Nifty 100 also available. Dow 30 / Nasdaq 100 for US testing.
        # Choice is saved to disk so it survives page refresh and mobile switch.
        _MARKETS     = ["🇮🇳 NSE 500", "🇮🇳 Nifty 100",
                        "🇺🇸 Dow 30", "🇺🇸 Nasdaq 100"]
        _saved_mkt   = st.session_state.get("scanner_market_global",
                        st.session_state.get("scanner_market", "🇮🇳 NSE 500"))
        # Migrate legacy values (Nifty 100 stays valid; NSE 500 is new default)
        if _saved_mkt not in _MARKETS:
            _saved_mkt = "🇮🇳 NSE 500"

        _market = st.radio(
            "Scan universe",
            _MARKETS,
            index=_MARKETS.index(_saved_mkt),
            horizontal=True,
            key="mkt_radio_global",
            label_visibility="collapsed",
        )
        # Persist selection immediately so refresh / mobile keeps it
        if _market != _saved_mkt:
            st.session_state["scanner_market"]        = _market
            st.session_state["scanner_market_global"] = _market
            _save_credentials()   # write to disk right now
            st.rerun()

        _is_us = _market in ("🇺🇸 Dow 30", "🇺🇸 Nasdaq 100")
        # US markets only live during US hours (9:30 AM–4:00 PM EST/EDT)
        if _is_us and not is_market_open("us"):
            st.warning("🇺🇸 US markets closed — Dow/Nasdaq scanning available 9:30 PM–4:00 AM IST")
            return
        _feed  = "yfinance (US, no token needed)" if _is_us else "yfinance / Upstox fallback"
        _sym_count = len(get_market_list(_market))
        st.markdown(
            f"<div style='background:#f0f4e8;border-left:3px solid #4e6130;"
            f"border-radius:6px;padding:0.4rem 0.9rem;margin-bottom:0.5rem;"
            f"font-family:DM Mono,monospace;font-size:0.72rem;color:#5a6a48;'>"
            f"📊 Scanning <b>{_market}</b> &nbsp;·&nbsp; {_sym_count} symbols &nbsp;·&nbsp; "
            f"{'<b>$USD</b> · ' if _is_us else '<b>₹INR</b> · '}"
            f"{_feed} &nbsp;·&nbsp; "
            f"{'⚠️ US market — yfinance only, no Upstox needed' if _is_us else '✅ Data always live via yfinance'}"
            f"</div>", unsafe_allow_html=True)
        st.divider()
        st.markdown("<div style='font-family:DM Mono,monospace;font-size:0.72rem;color:#5a6a48;"
            "padding:0.4rem 0.9rem;margin-bottom:0.5rem;background:#f0f4e8;"
            "border-radius:6px;border-left:3px solid #4e6130;'>"
            "⚡ <b>30 Min &amp; 1 Hour</b> → Auto-scan + Forward Testing &nbsp;|&nbsp; "
            "🖐 <b>1d / 1wk / 1mo</b> → Manual execution required &nbsp;|&nbsp; "
            "📡 <b>Data feed:</b> yfinance always active (Upstox enhances speed when token present)</div>",
            unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════════════
        #  🏆 TOP 5 BEST TRADES — AUTO-SCANNED ACROSS 30m · 1H (15m dropped for speed)
        # ═══════════════════════════════════════════════════════════════════
        _TOP5_KEY      = "top5_best_trades"
        _TOP5_TIME_KEY = "top5_best_trades_time"
        _top5_age      = time.time() - st.session_state.get(_TOP5_TIME_KEY, 0)
        _top5_needs    = _top5_age >= 900

        _th1, _th2 = st.columns([5, 1])
        with _th1:
            st.markdown(
                "<div style='font-family:IBM Plex Mono,monospace;'>"
                "<span style='font-size:1.5rem;'>🏆</span> "
                "<b style='font-size:1rem;color:#1a1f0e;'>Top 5 Best Trades</b> "
                "<span style='font-size:0.68rem;color:#5a6a48;'>"
                "Auto-ranked across ⏱️30m · 🕐1H · Frank Ochoa Score · Refreshes every 15 min"
                "</span></div>", unsafe_allow_html=True)
        with _th2:
            if st.button("🔄 Refresh Top 5", key="refresh_top5_btn", use_container_width=True):
                _top5_needs = True
                st.session_state.pop(_TOP5_KEY, None)

        if _top5_needs or _TOP5_KEY not in st.session_state:
            _mkt_list = get_market_list(st.session_state.get("scanner_market", "🇮🇳 NSE 500"))
            with st.spinner("⚡ Scanning 30m · 1H in parallel for best setups…"):
                _top5_result = _get_top5_best_trades(_mkt_list)
            st.session_state[_TOP5_KEY]      = _top5_result
            st.session_state[_TOP5_TIME_KEY] = time.time()
            _top5_age = 0
            # ── Telegram: notify every Top 5 signal ──────────────────────
            if _top5_result:
                _tg_cfg = st.session_state.get("telegram_cfg", {})
                if _tg_cfg.get("notify_signals", True):
                    _tf_grp = {}
                    for _ts in _top5_result:
                        _ttag = _ts.get("_tf_tag", "—")
                        _tf_grp.setdefault(_ttag, []).append(_ts)
                    for _ttag, _tsigs in _tf_grp.items():
                        _tf_map = {"30m":"⏱️ 30 Min","1h":"🕐 1 Hour"}
                        _tf_lbl = _tf_map.get(_ttag, _ttag.upper())
                        _summary = (
                            f"🏆 <b>TOP SIGNALS — {_tf_lbl}</b>  [Auto Scan · Top 5]\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"🟢 Bullish: {sum(1 for x in _tsigs if x.get('Pattern','')=='Bullish')}   "
                            f"🔴 Bearish: {sum(1 for x in _tsigs if x.get('Pattern','')=='Bearish')}   "
                            f"Total: {len(_tsigs)}\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"<i>Individual signals follow below ↓</i>"
                        )
                        _send_telegram(_summary)
                        for _ts2 in _tsigs:
                            _send_telegram(_tg_signal_msg(_ts2, _ttag, "Top 5 Auto Scan"))

        _top5_trades = st.session_state.get(_TOP5_KEY, [])

        if not _top5_trades:
            st.info("📡 No top trades found — click **🔄 Refresh Top 5** to scan all 3 timeframes.")
        else:
            _age_min = int(_top5_age / 60)
            st.markdown(
                "<div style='font-family:IBM Plex Mono,monospace;font-size:0.68rem;color:#5a6a48;"
                "margin-bottom:0.6rem;'>✅ Last scanned <b>" + str(_age_min) + " min ago</b> · "
                "Showing <b>" + str(len(_top5_trades)) + "</b> best unique setups</div>",
                unsafe_allow_html=True)

            _medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            _t5cols = st.columns(min(5, len(_top5_trades)))
            for _idx, _sig in enumerate(_top5_trades):
                _is_bull  = _sig.get("Pattern","") == "Bullish"
                _hc       = "#16a34a" if _is_bull else "#dc2626"
                _hbg      = "#edf7ee" if _is_bull else "#fdf0ee"
                _hbd      = "#b8dfc0" if _is_bull else "#f0c0b8"
                _arrow    = "▲" if _is_bull else "▼"
                _side_lbl = "BUY" if _is_bull else "SELL"
                _tf_lbl   = _sig.get("_tf_label","")
                _tf_color = _sig.get("_tf_color","#5a6a48")
                _tf_tag   = _sig.get("_tf_tag","")
                _score    = _sig.get("_rank_score", 0)
                _sym      = _sig.get("Symbol","")
                _rr       = float(_sig.get("RR1", 0))
                _str      = int(_sig.get("Strength%", 0))
                _candle   = _sig.get("Candle","—")
                _rsi      = float(_sig.get("RSI", 50))
                _hma      = str(_sig.get("HMA","—"))
                _vol      = str(_sig.get("Vol Surge","—"))
                _entry    = float(_sig.get("Entry", 0))
                _t1       = float(_sig.get("T1", 0))
                _t2       = float(_sig.get("T2", 0))
                _sl       = float(_sig.get("SL", 0))
                _sl_pct   = abs(_entry - _sl) / _entry * 100 if _entry > 0 else 0
                _day_type = str(_sig.get("Day Type",""))
                _cpr_w    = float(_sig.get("CPR Width%", 0))
                _rr_col   = "#16a34a" if _rr >= 2.0 else ("#d97706" if _rr >= 1.5 else "#dc2626")
                _medal    = _medals[_idx] if _idx < 5 else f"#{_idx+1}"
                if   _score >= 100: _grade, _gc = "A+","#16a34a"
                elif _score >= 80:  _grade, _gc = "A", "#16a34a"
                elif _score >= 65:  _grade, _gc = "B+","#d97706"
                elif _score >= 50:  _grade, _gc = "B", "#d97706"
                else:               _grade, _gc = "C", "#dc2626"

                with _t5cols[_idx]:
                    _card = (
                        "<div style='background:#fff;border:1.5px solid " + _hbd + ";"
                        "border-top:4px solid " + _hc + ";border-radius:10px;"
                        "padding:0.75rem 0.8rem;margin-bottom:0.3rem;"
                        "box-shadow:0 2px 10px rgba(0,0,0,0.07);'>"
                        "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.4rem;'>"
                        "<span style='font-size:1.1rem;'>" + _medal + "</span>"
                        "<span style='background:" + _tf_color + "18;color:" + _tf_color + ";"
                        "font-family:IBM Plex Mono,monospace;font-size:0.58rem;font-weight:700;"
                        "padding:2px 6px;border-radius:4px;border:1px solid " + _tf_color + "44;'>"
                        + _tf_lbl + "</span></div>"
                        "<div style='font-family:IBM Plex Mono,monospace;font-size:1rem;font-weight:700;color:#1a1f0e;'>"
                        "<span style='color:" + _hc + ";'>" + _arrow + "</span> " + _sym + "</div>"
                        "<div style='font-family:IBM Plex Mono,monospace;font-size:0.62rem;color:#5a6a48;margin-bottom:0.4rem;'>"
                        + _candle + " · RSI " + str(int(_rsi)) + " · " + _day_type + "</div>"
                        "<div style='background:#f1f5f9;border-radius:3px;height:4px;margin-bottom:0.45rem;'>"
                        "<div style='background:" + _hc + ";width:" + str(min(_str,100)) + "%;height:100%;border-radius:3px;'></div></div>"
                        "<div style='background:#f7f9f2;border-radius:6px;padding:0.35rem 0.5rem;"
                        "font-family:IBM Plex Mono,monospace;font-size:0.63rem;margin-bottom:0.4rem;line-height:1.8;'>"
                        "<div>Entry <b style='color:#1a1f0e;'>₹" + f"{_entry:,.2f}" + "</b></div>"
                        "<div>T1 <b style='color:" + _hc + ";'>₹" + f"{_t1:,.2f}" + "</b>"
                        " · T2 <b style='color:" + _hc + ";'>₹" + f"{_t2:,.2f}" + "</b></div>"
                        "<div>SL <b style='color:#c0392b;'>₹" + f"{_sl:,.2f}" + "</b>"
                        " <span style='color:#e74c3c;font-size:0.58rem;'>(" + f"{_sl_pct:.2f}" + "%)</span></div></div>"
                        "<div style='display:flex;flex-wrap:wrap;gap:3px;"
                        "font-family:IBM Plex Mono,monospace;font-size:0.6rem;margin-bottom:0.3rem;'>"
                        "<span style='background:#f7f9f2;border:1px solid #dae0cb;border-radius:3px;padding:1px 5px;color:" + _rr_col + ";font-weight:700;'>R:R " + f"{_rr:.1f}" + "x</span>"
                        "<span style='background:" + _hbg + ";border:1px solid " + _hbd + ";border-radius:3px;padding:1px 5px;color:" + _hc + ";font-weight:700;'>" + str(_str) + "%</span>"
                        "<span style='background:#fff8ed;border:1px solid #f0d070;border-radius:3px;padding:1px 5px;color:" + _gc + ";font-weight:700;'>" + _grade + "</span>"
                        "<span style='background:#f7f9f2;border:1px solid #dae0cb;border-radius:3px;padding:1px 5px;color:#5a6a48;'>Score " + f"{_score:.0f}" + "</span>"
                        "</div></div>")
                    st.markdown(_card, unsafe_allow_html=True)

                    _btn_type = "primary" if _idx == 0 else "secondary"
                    _btn_lbl  = ("⭐ Trade #1 · " if _idx == 0 else f"Trade #{_idx+1} · ") + _sym
                    if st.button(_btn_lbl,
                                 key=f"top5_trade_{_idx}_{_sym}_{_tf_tag}",
                                 use_container_width=True, type=_btn_type):
                        _msig = {
                            "symbol": _sym, "side": _side_lbl,
                            "entry": _entry, "sl": _sl, "t1": _t1, "t2": _t2,
                            "rr1": _rr, "tf": _tf_tag,
                            "strategy": _sig.get("Strategy","CPR"),
                            "strength": _str, "candle": _candle,
                            "day_type": _day_type, "cpr_w": _cpr_w,
                            "rsi": _rsi, "hma": _hma, "vol": _vol,
                            "ltp": _entry, "rank_score": _score,
                        }
                        ft_add_signal(_msig, source=f"🏆 Top5·Rank#{_idx+1}·{_tf_tag.upper()}")
                        _tg_p = {"symbol":_sym,"side":_side_lbl,"entry":_entry,
                                 "target":_t1,"sl":_sl,"qty":1,"cost":_entry,
                                 "rr":_rr,"tf":_tf_tag,"pnl":0}
                        _send_telegram(_tg_trade_msg(_tg_p,"ENTRY"))
                        st.success(f"✅ **{_sym}** ({_tf_lbl}) added to Forward Testing!")

        st.divider()

        # ── Manual TF scanner continues below ─────────────────────────────
        TF_CONFIG = {
            "⚡ 15 Min  — Fast Scalping":   {"interval":"15m","period":"5d", "tag":"15m","refresh":900,   "color":"#7c3aed","bg":"#f5f3ff","label":"Fast Scalping",  "refresh_label":"15 min"},
            "⏱️ 30 Min  — Momentum":        {"interval":"30m","period":"7d", "tag":"30m","refresh":1800,  "color":"#ea580c","bg":"#fff7ed","label":"Momentum",       "refresh_label":"30 min"},
            "🕐 1 Hour  — Swing Scalping":  {"interval":"1h", "period":"14d", "tag":"1h", "refresh":3600,  "color":"#1d4ed8","bg":"#eff6ff","label":"Swing Scalping", "refresh_label":"1 hour"},
            "📅 1 Day   — Swing Trading":   {"interval":"1d", "period":"45d","tag":"1d", "refresh":14400, "color":"#1a6b3c","bg":"#edf7ee","label":"Swing Trading",  "refresh_label":"4 hours"},
            "📆 1 Week  — Positional":      {"interval":"1wk","period":"1y",  "tag":"1wk","refresh":86400, "color":"#d97706","bg":"#fdf9ec","label":"Positional",     "refresh_label":"24 hours"},
            "🗓️ 1 Month — Prime Trading":   {"interval":"1mo","period":"2y",  "tag":"1mo","refresh":86400, "color":"#dc2626","bg":"#fdf0ee","label":"Prime Trading",  "refresh_label":"24 hours"},
        }

        # ── Header ────────────────────────────────────────────────────────────────
        st.markdown("""
        <div style="display:flex;align-items:center;gap:14px;margin-bottom:1.25rem;
                    padding:1.25rem 1.5rem;background:#ffffff;border:1px solid #dae0cb;
                    border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
            <div style="font-size:2rem;">📡</div>
            <div style="flex:1;">
                <div style="font-family:'IBM Plex Mono',monospace;font-size:1.1rem;
                            font-weight:700;color:#1a1f0e;">CPR Scanner</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.68rem;
                            color:#5a6a48;letter-spacing:0.08em;text-transform:uppercase;margin-top:2px;">
                    NSE 500 · All CPR Setups · Best 10 Bullish + 10 Bearish · Pivot-Based Targets
                </div>
            </div>
            <div id="countdown-wrap" style="text-align:right;font-family:'IBM Plex Mono',monospace;">
                <div style="font-size:0.62rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.07em;">Next refresh in</div>
                <div id="countdown" style="font-size:1.3rem;font-weight:700;color:#1a6b3c;">—</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Notification bar — device-aware ─────────────────────────────────────
        st.markdown("""
        <div id="pvNBar" style="border-radius:9px;padding:9px 14px;
             margin-bottom:0.75rem;font-family:DM Mono,monospace;font-size:0.76rem;
             border:1.5px solid #b8c89a;background:#f0f4e8;min-height:38px;">
            <div id="pvNContent"></div>
        </div>
        <script>
        (function(){
            var w  = window.parent||window;
            var ua = navigator.userAgent||"";
            var isIOS     = /iPhone|iPad|iPod/i.test(ua);
            var isAndroid = /Android/i.test(ua);
            var isPWA     = window.matchMedia("(display-mode:standalone)").matches||
                            window.navigator.standalone===true;
            var isMobile  = isIOS||isAndroid;
            var el = document.getElementById("pvNContent");
            if(!el) return;

            function render(){
                if(isIOS && !isPWA){
                    el.innerHTML = "📱 <b>iOS:</b> Notifications not supported in Safari. "
                        +"<span style='color:#7a5800;'>Add to Home Screen (PWA) to enable.</span>";
                    return;
                }
                if(!("Notification" in w)){
                    el.innerHTML = "⚠️ Browser doesn't support notifications. Use Chrome/Edge.";
                    return;
                }
                var p = w.Notification.permission;
                if(p==="granted"){
                    document.getElementById("pvNBar").style.background="#e4f5e8";
                    document.getElementById("pvNBar").style.borderColor="#8dcc9a";
                    el.innerHTML = "<span style='color:#1a6b2e;font-weight:700;'>✅ Notifications active</span>"
                        +" · <span style='color:#2e3d1a;'>"+(isMobile?"Android Chrome":"Desktop browser")+"</span>"
                        +" <button onclick='pvSendTest()' style='margin-left:8px;background:#1a6b2e;"
                        +"color:#fff;border:none;border-radius:5px;padding:3px 10px;"
                        +"font-size:0.72rem;cursor:pointer;font-weight:700;'>🧪 Test</button>";
                } else if(p==="denied"){
                    document.getElementById("pvNBar").style.background="#fbe8e6";
                    document.getElementById("pvNBar").style.borderColor="#dc9090";
                    el.innerHTML = "❌ Notifications blocked. "
                        +(isAndroid?"Chrome → 3-dot menu → Site settings → Notifications → Allow."
                        :"Browser Settings → Notifications → Allow this site.");
                } else {
                    el.innerHTML = "🔔 Enable "+(isMobile?"mobile":"desktop")+" notifications for instant signal alerts"
                        +" <button onclick='pvAskNotif()' style='margin-left:8px;background:#3d5a1c;"
                        +"color:#fff;border:none;border-radius:5px;padding:3px 10px;"
                        +"font-size:0.72rem;cursor:pointer;font-weight:700;'>Allow</button>";
                }
            }
            window.pvAskNotif = function(){
                w.Notification.requestPermission().then(function(){ render(); });
            };
            window.pvSendTest = function(){
                try{
                    var n = new w.Notification("🧪 PivotVault AI — Test",{
                        body:"RELIANCE BUY · Entry ₹2,850 · T1 ₹2,920 · SL ₹2,800 · R:R 2.1x",
                        icon:"/static/icon-192.png", tag:"pv-test"
                    });
                    n.onclick=function(){w.focus();n.close();};
                    el.innerHTML="<span style='color:#1a6b2e;font-weight:700;'>"
                        +"✅ Test sent! Check your "+(isMobile?"phone":"desktop")+".</span>";
                    setTimeout(render,3500);
                }catch(e){ el.innerHTML="❌ "+e.message; }
            };
            render();
        })();
        </script>
        """, unsafe_allow_html=True)

        # ── Timeframe selector ────────────────────────────────────────────────────
        c1, c2 = st.columns([4, 1])
        with c1:
            tf_choice = st.selectbox(
                "Timeframe",
                list(TF_CONFIG.keys()),
                index=2,
                label_visibility="collapsed",
                key="scanner_tf",
            )
        with c2:
            manual_btn = st.button("🔄 Scan Now", use_container_width=True, key="run_cpr_scan_btn")

        cfg        = TF_CONFIG[tf_choice]
        tf_col     = cfg["color"]
        tf_bg      = cfg["bg"]
        tf_tag     = cfg["tag"]
        refresh_s  = cfg["refresh"]

        scan_key      = f"cpr_scan_{tf_tag}"
        scan_time_key = f"cpr_scan_time_{tf_tag}"

        now           = time.time()
        last_scan     = st.session_state.get(scan_time_key, 0)
        age           = now - last_scan
        needs_refresh = manual_btn or (age >= refresh_s) or (scan_key not in st.session_state)

        # ── Run scan only for selected timeframe ──────────────────────────────────
        if needs_refresh:
            # Warn if Upstox not connected — yfinance may be blocked on Streamlit Cloud
            if not _upstox_connected():
                st.info(
                    "💡 **Tip:** Connect your Upstox API token in ⚙️ Broker Settings for reliable data. "
                    "yfinance may be rate-limited on Streamlit Cloud.",
                    icon="ℹ️",
                )
            upstox_live  = _upstox_connected()
            has_creds    = _upstox_has_credentials()
            n_stocks     = 500 if upstox_live else (500 if has_creds else 500)

            if has_creds and not upstox_live:
                st.warning(
                    "⚠️ Upstox token expired — scanner will use yfinance. "
                    "Paste today's token above to restore Upstox live feed.",
                    icon="🔑",
                )

            src_label = "📡 Upstox Live" if upstox_live else "📊 yfinance (15-min delay)"
            with st.spinner(f"Scanning {n_stocks} stocks · {tf_tag.upper()} · {src_label}…"):
                try:
                    result = scan_cpr_multi_tf(
                        get_market_list(st.session_state.get("scanner_market", "🇮🇳 NSE 500")),
                        interval=cfg["interval"],
                        period=cfg["period"],
                        max_stocks=n_stocks,
                    )
                    if result.empty:
                        st.warning(
                            f"⚠️ No setups found on {tf_tag.upper()}. "
                            f"{'Market may be closed — data is from last session.' if not is_market_open('us' if st.session_state.get('scanner_market','') in ('🇺🇸 Dow 30','🇺🇸 Nasdaq 100') else 'india') else 'All stocks filtered out — try a different timeframe.'}"
                        )
                    else:
                        st.toast(f"✅ {len(result)} setups found · {src_label}", icon="📡")
                        # ── Send Telegram for ALL signals, ALL timeframes ──
                        _src = "Auto Scan" if not manual_btn else "Manual Scan"
                        _tg_send_scan_signals(result, tf_tag, source=_src)
                except Exception as e:
                    st.error(f"Scanner error: {str(e)[:150]}. Check your connection or try a different timeframe.")
                    result = pd.DataFrame()
            st.session_state[scan_key]      = result
            st.session_state[scan_time_key] = now

            # ── Rank signals & Auto-trade BEST 3 only ────────────────────
            if not result.empty and tf_tag in ("15m","30m","1h"):

                def _signal_rank_score(row):
                    """
                    Composite rank score — Frank Ochoa weighted.
                    Higher score = better quality signal.
                    """
                    s   = float(row.get("Strength%",   0))
                    rr  = float(row.get("RR1",         1.0))
                    cw  = float(row.get("CPR Width%",  1.0))
                    dt  = str(row.get("Day Type",      ""))
                    ov  = bool(row.get("CPR Overlap",  False))
                    cn  = str(row.get("Candle",        ""))
                    rsi = float(row.get("RSI",         50))
                    hma = str(row.get("HMA",           ""))
                    vol = str(row.get("Vol Surge",     ""))
                    side= str(row.get("Pattern",       ""))

                    score = (s * 0.35) + (rr * 15)

                    # CPR Width — narrower = better (trending day)
                    if cw < 0.25:   score += 20
                    elif cw < 0.5:  score += 10
                    elif cw > 1.0:  score -= 10

                    # Day Type bonus/penalty (Ochoa Two-Day CPR)
                    if dt == "Trending":    score += 25
                    elif dt == "Moderate":  score += 10
                    elif dt == "Sideways":  score -= 40
                    elif dt == "Volatile":  score -= 5

                    # Overlap heavy penalty
                    if ov: score -= 30

                    # Candle quality bonus
                    _premium = {
                        "Morning Star": 20, "Evening Star": 20,
                        "Bullish Engulfing": 18, "Bearish Engulfing": 18,
                        "Bull Pin Bar": 15, "Bear Pin Bar": 15,
                        "Hammer": 12, "Shooting Star": 12,
                        "Bullish Marubozu": 8, "Bearish Marubozu": 8,
                        "Inside Bar": 5, "Doji at CPR": 3,
                    }
                    score += _premium.get(cn, 0)

                    # RSI alignment
                    if side == "Bullish" and rsi >= 55:    score += 8
                    elif side == "Bearish" and rsi <= 45:  score += 8
                    elif side == "Bullish" and rsi <= 40:  score -= 5
                    elif side == "Bearish" and rsi >= 60:  score -= 5

                    # HMA alignment
                    if ("▲" in hma and side == "Bullish") or ("▼" in hma and side == "Bearish"):
                        score += 10

                    # Volume surge
                    if "✅" in vol: score += 8

                    # Timeframe bonus — 30M is primary (highest quality CPR signals)
                    _tf = str(row.get("tf",""))
                    if   "30m" in _tf or "30M" in _tf: score += 15  # primary TF
                    elif "1h"  in _tf or "1H"  in _tf: score += 8   # swing TF
                    elif "15m" in _tf or "15M" in _tf: score += 5   # scalp TF

                    return round(score, 2)

                # Compute rank score for every directional signal
                if "Pattern"    not in result.columns: result["Pattern"]    = "Neutral"
                if "Strength%"  not in result.columns: result["Strength%"]  = 0.0
                if "CPR Width%" not in result.columns: result["CPR Width%"] = 0.0
                ranked = result[result["Pattern"] != "Neutral"].copy()
                if not ranked.empty:
                    ranked["🏆 Rank Score"] = ranked.apply(_signal_rank_score, axis=1)
                    ranked["🤖 Auto"]        = ""   # will be filled below
                    ranked = ranked.sort_values("🏆 Rank Score", ascending=False).reset_index(drop=True)
                    ranked.index = ranked.index + 1  # rank 1 = best

                    # Store ranked result for scanner UI display
                    st.session_state[f"ranked_scan_{tf_tag}"] = ranked

                    # ── TOP 3 AUTO-TRADE only ──────────────────────────────────
                    # Max 1 trade per symbol per day — no duplicate entries
                    _today   = datetime.now().strftime("%Y-%m-%d")
                    _ft_evts = _ft_state().get("events", [])
                    _traded_today = set(
                        e.get("symbol","") for e in _ft_evts
                        if e.get("type","") == "ENTRY"
                        and str(e.get("time","")).startswith(_today)
                    )
                    auto_traded = 0
                    for _ri, row in ranked.iterrows():
                        sig = {
                            "symbol":     row.get("Symbol",""),
                            "side":       "BUY" if row.get("Pattern","") == "Bullish" else "SELL",
                            "entry":      row.get("Entry",   row.get("LTP",0)),
                            "sl":         row.get("SL",      0),
                            "t1":         row.get("T1",      0),
                            "t2":         row.get("T2",      0),
                            "rr1":        row.get("RR1",     2.0),
                            "tf":         tf_tag,
                            "rationale":  row.get("Rationale", row.get("Strategy","CPR")),
                            "strategy":   row.get("Strategy","CPR"),
                            "strength":   row.get("Strength%",0),
                            "candle":     row.get("Candle","—"),
                            "day_type":   row.get("Day Type",""),
                            "cpr_overlap":row.get("CPR Overlap", False),
                            "rsi":        row.get("RSI", 50),
                            "hma":        row.get("HMA","—"),
                            "vol":        row.get("Vol Surge","—"),
                            "cprw":       row.get("CPR Width%", 1.0),
                            "ltp":        row.get("LTP", 0),
                            "rank_score": row.get("🏆 Rank Score", 0),
                        }
                        _strength = float(sig.get("strength", 0))
                        _rr       = float(sig.get("rr1", 0))
                        _overlap  = sig.get("cpr_overlap", False)
                        _day_type = sig.get("day_type", "")

                        # Block sideways + enforce quality gate
                        if _overlap and _day_type == "Sideways":
                            continue
                        # Frank Ochoa optimal params:
                        # Strength >= 75%, RR >= 2.0, Non-sideways day
                        if not (_strength >= 75 and _rr >= 2.0):
                            continue

                        # ── MIN SL DISTANCE FILTER (0.50%) ──────────────────
                        # Prevents noise-triggered SL hits on tight stops
                        # Based on forward test analysis: 17/18 SL hits had SL% < 0.50%
                        _entry_px = float(sig.get("entry", 0))
                        _sl_px    = float(sig.get("sl",    0))
                        _sl_pct   = abs(_entry_px - _sl_px) / _entry_px * 100 if _entry_px > 0 else 0
                        if _sl_pct < 0.50:
                            continue   # SL too tight — skip, noise will hit it

                        if not (sig["symbol"] and sig["entry"] and sig["sl"] and sig["t1"]):
                            continue

                        # Skip if this symbol already traded today
                        if sig["symbol"] in _traded_today:
                            ranked.loc[_ri, "🤖 Auto"] = "⏭ Done Today"
                            continue

                        if auto_traded < 3:
                            # ── AUTO-TRADE GATE: Only 30m + 1h timeframes ──
                            # 15m excluded — too noisy, tight SL, high false signals
                            if tf_tag not in ("30m", "1h"):
                                continue
                            ft_add_signal(sig, source=f"🤖 Auto·Top3 · {tf_tag.upper()}")
                            ranked.loc[_ri, "🤖 Auto"] = "🤖 Auto"
                            _traded_today.add(sig["symbol"])
                            auto_traded += 1
                        # Rest are available for manual trade — marked in ranked table

                    # Update stored ranked result with Auto markers
                    st.session_state[f"ranked_scan_{tf_tag}"] = ranked

            last_scan = now

            # ── Always sync ALL timeframes to canonical keys for Trade Signals tab ──
            # Includes manual scans (1d/1wk/1mo) so every scan appears in signals
            st.session_state[f"cpr_scan_{tf_tag}"]      = result
            st.session_state[f"cpr_scan_time_{tf_tag}"] = now

            # ── Store signals + fire desktop notifications ────────────────────────
            if not result.empty:
                if "Pattern" not in result.columns: result["Pattern"] = "Neutral"
                top3_bull = result[result["Pattern"]=="Bullish"].head(3)
                top3_bear = result[result["Pattern"]=="Bearish"].head(3)
                notif_signals = []
                for _, r in top3_bull.iterrows():
                    notif_signals.append({
                        "symbol": r["Symbol"], "side": "BUY",
                        "entry": r["Entry"], "t1": r["T1"], "sl": r["SL"],
                        "rr": r["RR1"], "strength": int(r["Strength%"]),
                        "candle": r.get("Candle","—"),
                    })
                for _, r in top3_bear.iterrows():
                    notif_signals.append({
                        "symbol": r["Symbol"], "side": "SELL",
                        "entry": r["Entry"], "t1": r["T1"], "sl": r["SL"],
                        "rr": r["RR1"], "strength": int(r["Strength%"]),
                        "candle": r.get("Candle","—"),
                    })
                st.session_state["pending_signals"] = notif_signals
                # Also update the per-tag scan time key used by Trade Signals tab
                st.session_state[f"cpr_scan_time_{tf_tag}"] = now

                # ── Fire desktop notifications via window.parent ──────────────────
                # window.parent escapes the Streamlit iframe — works on Chrome/Edge/Firefox
                notif_js_list = json.dumps([
                    {"sym": s["symbol"], "side": s["side"],
                     "entry": s["entry"], "t1": s["t1"], "sl": s["sl"],
                     "rr": s["rr"], "str": s["strength"]}
                    for s in notif_signals[:6]
                ])
                st.markdown(f"""
    <script>
    (function fireNotifs() {{
        var sigs = {notif_js_list};
        var w    = window.parent || window;
        if (!("Notification" in w)) return;
        if (w.Notification.permission !== "granted") {{
            // Flash the allow button if not granted
            var btn = document.getElementById("pv-allow-btn");
            if (btn) {{
                btn.style.animation = "none";
                btn.style.background = "#c0392b";
                btn.innerText = "⚠️ Allow Notifications!";
            }}
            return;
        }}
        sigs.forEach(function(s, i) {{
            setTimeout(function() {{
                var emoji = s.side === "BUY" ? "🟢" : "🔴";
                w.pvNotify(
                    emoji + " " + s.side + " Signal — " + s.sym + " (" + s.str + "%)",
                    "Entry ₹" + s.entry + "  |  T1 ₹" + s.t1 + "  |  SL ₹" + s.sl + "  |  R:R " + s.rr + "x",
                    "pv-" + s.sym
                );
            }}, i * 800);  // Stagger by 800ms so they don't all fire at once
        }});
    }})();
    </script>
    """, unsafe_allow_html=True)

        scan_df  = st.session_state.get(scan_key, pd.DataFrame())
        elapsed  = int(now - last_scan)
        remaining = max(0, refresh_s - elapsed)

        # ── Countdown JS ──────────────────────────────────────────────────────────
        st.markdown(f"""
        <script>
        (function() {{
            var secs = {remaining};
            function pad(n) {{ return n < 10 ? "0"+n : n; }}
            function fmt(s) {{
                if (s >= 3600) return pad(Math.floor(s/3600))+"h "+pad(Math.floor((s%3600)/60))+"m";
                return pad(Math.floor(s/60))+":"+pad(s%60);
            }}
            function tick() {{
                if (secs <= 0) {{ window.location.reload(); return; }}
                var el = document.getElementById("countdown");
                if (el) el.innerText = fmt(secs);
                secs--;
                setTimeout(tick, 1000);
            }}
            tick();
        }})();
        </script>
        """, unsafe_allow_html=True)

        # ── Status bar ────────────────────────────────────────────────────────────
        scan_dt = datetime.fromtimestamp(last_scan).strftime("%d %b  %H:%M:%S") if last_scan else "—"
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:1rem;flex-wrap:wrap;"
            f"font-family:IBM Plex Mono,monospace;font-size:0.72rem;color:#5a6a48;"
            f"margin-bottom:1rem;padding:0.5rem 0.9rem;background:{tf_bg};"
            f"border:1px solid {tf_col}33;border-left:3px solid {tf_col};border-radius:6px;'>"
            f"<span style='color:{tf_col};font-weight:700;'>{tf_choice}</span>"
            f"<span>Last scan: <b>{scan_dt}</b></span>"
            f"<span>Auto-refresh: every <b>{cfg['refresh_label']}</b></span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if scan_df.empty:
            st.warning("⚠️ Scanner returned no results. Click 🔄 Scan Now to retry.")
            with st.expander("🔍 Debug — What to check if scanner shows no data"):
                st.markdown("""
    **Common causes:**

    1. **First run** — Click **🔄 Scan Now** manually to trigger the first scan.

    2. **yfinance rate limit** — NSE/yfinance blocks frequent requests from cloud IPs.
       Connect Upstox in ⚙️ Broker Settings for live data that always works.

    3. **Weekend / market closed** — Scanner still works but data is from last trading day.

    4. **All CPR widths > 2%** — All stocks filtered out. Try switching to **1 Day** timeframe
       which typically has more narrow CPR setups.

    5. **Streamlit Cloud cold start** — Wait 30 seconds then click Scan Now.
                """)
                st.code("Connect Upstox → ⚙️ Broker Settings → Paste your Access Token → Save")
            pass  # empty state — stay in tab

        # ── All bullish & bearish — no strength cutoff ────────────────────────────
        if "Pattern"    not in scan_df.columns: scan_df["Pattern"]    = "Neutral"
        if "CPR Width%" not in scan_df.columns: scan_df["CPR Width%"] = 0.0
        if "Strength%"  not in scan_df.columns: scan_df["Strength%"]  = 0.0
        all_bull = scan_df[scan_df["Pattern"] == "Bullish"].copy()
        all_bear = scan_df[scan_df["Pattern"] == "Bearish"].copy()

        # ── Summary metrics ───────────────────────────────────────────────────────
        n_scanned = len(scan_df)
        n_narrow  = int((scan_df["CPR Width%"] < 0.25).sum())
        n_bull    = len(all_bull)
        n_bear    = len(all_bear)
        n_qual    = n_bull + n_bear   # all directional stocks

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("📊 Scanned",   n_scanned)
        m2.metric("🎯 Narrow CPR", n_narrow)
        m3.metric("📈 Directional", n_qual)
        m4.metric("🟢 Bullish",   n_bull)
        m5.metric("🔴 Bearish",   n_bear)

        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

        if n_qual == 0:
            st.markdown(
                f"<div style='text-align:center;padding:2rem;background:#f7f9f2;"
                f"border:2px dashed #dce3ed;border-radius:10px;"
                f"font-family:IBM Plex Mono,monospace;font-size:0.82rem;color:#8a9a78;'>"
                f"Scanned <b>{n_scanned}</b> stocks on {tf_tag.upper()} — no directional CPR setups found right now.<br>"
                f"<span style='font-size:0.72rem;'>All CPR widths may be > 2%, or no RSI/HMA confirmation. "
                f"Try switching to 📅 1 Day timeframe or 🔄 Scan Now again.</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            pass  # empty state — stay in tab

        # ── Top 10 each side — sorted by Strength then tightest CPR ──────────────
        top_bull = all_bull.sort_values(["Strength%","CPR Width%"], ascending=[False,True]).head(10) if not all_bull.empty else pd.DataFrame()
        top_bear = all_bear.sort_values(["Strength%","CPR Width%"], ascending=[False,True]).head(10) if not all_bear.empty else pd.DataFrame()

        def _cards(df, direction):
            is_bull = direction == "Bullish"
            hc  = "#16a34a" if is_bull else "#dc2626"
            hbg = "#edf7ee" if is_bull else "#fdf0ee"
            hbd = "#b8dfc0" if is_bull else "#f0c0b8"
            arr = "▲" if is_bull else "▼"

            if df.empty:
                return (f"<div style='padding:2rem;text-align:center;background:#f7f9f2;"
                        f"border:2px dashed #dce3ed;border-radius:10px;"
                        f"font-family:IBM Plex Mono,monospace;font-size:0.78rem;color:#8a9a78;'>"
                        f"No {direction} picks match criteria on this timeframe</div>")

            html = (f"<div style='font-family:IBM Plex Mono,monospace;font-size:0.75rem;"
                    f"font-weight:700;color:{hc};letter-spacing:0.05em;text-transform:uppercase;"
                    f"padding:0.5rem 0.9rem;background:{hbg};border:1px solid {hbd};"
                    f"border-left:4px solid {hc};border-radius:6px;margin-bottom:0.6rem;'>"
                    f"{arr} Top 10 {direction} · Narrow CPR · Frank Ochoa Strategy</div>")

            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for rank, (_, row) in enumerate(df.iterrows(), 1):
                prob     = int(row["Strength%"])
                rsi_c    = "#16a34a" if row["RSI"] >= 55 else ("#dc2626" if row["RSI"] <= 45 else "#d97706")
                medal    = medals.get(rank, f"#{rank}")
                candle   = str(row.get("Candle", "None"))
                candle_icon = "🕯️" if candle != "None" else ""
                rr1      = float(row.get("RR1", 0))
                rr2      = float(row.get("RR2", 0))
                rr_col   = "#16a34a" if rr1 >= 2 else ("#d97706" if rr1 >= 1.5 else "#dc2626")
                osc      = str(row.get("Osc Cross", "—"))
                vol      = str(row.get("Vol Surge", "—"))
                cpr_w    = float(row.get("CPR Width%", 0))

                html += (
                    f'<div style="background:#fff;border:1px solid {hbd};border-radius:10px;'
                    f'padding:0.85rem 1rem;margin-bottom:0.5rem;box-shadow:0 1px 5px rgba(0,0,0,0.05);">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.4rem;">'
                    f'<div style="display:flex;align-items:center;gap:8px;">'
                    f'<span style="font-size:1rem;">{medal}</span>'
                    f'<div>'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.95rem;font-weight:700;color:#1a1f0e;">{row["Symbol"]}</div>'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:#5a6a48;">'
                    f'&#8377;{row["LTP"]:,.2f} &nbsp;·&nbsp; ATR &#8377;{row["ATR"]:,.2f} &nbsp;·&nbsp; {candle_icon} {candle}</div>'
                    f'</div></div>'
                    f'<div style="text-align:right;">'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:1rem;font-weight:700;color:{hc};">{prob}%</div>'
                    f'<div style="font-family:IBM Plex Mono,monospace;font-size:0.62rem;color:#5a6a48;">Strength</div>'
                    f'</div></div>'
                    f'<div style="background:#f1f5f9;border-radius:3px;height:5px;margin-bottom:0.5rem;">'
                    f'<div style="background:{hc};width:{prob}%;height:100%;border-radius:3px;"></div></div>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.45rem;'
                    f'padding:0.4rem 0.6rem;background:#f7f9f2;border-radius:6px;'
                    f'font-family:IBM Plex Mono,monospace;font-size:0.68rem;">'
                    f'<span style="color:#5a6a48;">Entry <b style="color:#1a1f0e;">&#8377;{row["Entry"]:,.2f}</b></span>'
                    f'<span>|</span>'
                    f'<span style="color:#5a6a48;">T1 <b style="color:{hc};">&#8377;{row["T1"]:,.2f}</b></span>'
                    f'<span style="color:#5a6a48;">T2 <b style="color:{hc};">&#8377;{row["T2"]:,.2f}</b></span>'
                    f'<span>|</span>'
                    f'<span style="color:#5a6a48;">SL <b style="color:#c0392b;">&#8377;{row["SL"]:,.2f}</b> ' + (f'<span style="color:#e74c3c;font-size:0.65rem">({round(abs(row.get("Entry",0)-row["SL"])/row.get("Entry",1)*100,2):.2f}%)</span>' if row.get("Entry",0)>0 else '') + f'</span>'
                    f'<span>|</span>'
                    f'<span style="color:#5a6a48;">R:R <b style="color:{rr_col};">{rr1}x / {rr2}x</b></span>'
                    f'</div>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:0.3rem;">'
                    f'<span style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:#1a1f0e;">CPR {cpr_w:.3f}%</span>'
                    f'<span style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:#1a1f0e;">TC &#8377;{row["TC"]:,.2f} / BC &#8377;{row["BC"]:,.2f}</span>'
                    f'<span style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:{hc};">HMA {row["HMA"]}</span>'
                    f'<span style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:{rsi_c};">RSI {row["RSI"]}</span>'
                    f'<span style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:#1a1f0e;">Osc {osc}</span>'
                    f'<span style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:#1a1f0e;">Vol {vol}</span>'
                    f'<span style="background:{hbg};border:1px solid {hbd};border-radius:4px;padding:0.15rem 0.45rem;font-family:IBM Plex Mono,monospace;font-size:0.67rem;color:{hc};font-weight:600;">{arr} NARROW</span>'
                    f'</div></div>'
                )
            return html

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown(_cards(top_bull, "Bullish"), unsafe_allow_html=True)
        with col_r:
            st.markdown(_cards(top_bear, "Bearish"), unsafe_allow_html=True)

        # Full results table
        if n_qual > 0:
            with st.expander(f"📋 All {n_qual} stocks ({n_bull} Bullish + {n_bear} Bearish)", expanded=False):
                # ── Ranked Signal Table — Best 3 Auto + Rest Manual ─────
                _ranked_key = f"ranked_scan_{tf_tag}"
                if st.session_state.get(_ranked_key) is not None and not st.session_state[_ranked_key].empty:
                    ranked_df = st.session_state[_ranked_key].copy()
                    st.markdown("#### 🏆 Signal Rankings — Sorted by Frank Ochoa Quality Score")
                    # Colour-coded badge for auto vs manual
                    def _auto_badge(v):
                        return "🤖 AUTO" if v == "🤖 Auto" else "👤 Manual"
                    if "🤖 Auto" in ranked_df.columns:
                        ranked_df["Trade"] = ranked_df["🤖 Auto"].apply(_auto_badge)
                    # Show key columns
                    _rcols = [c for c in ["Trade","🏆 Rank Score","Symbol","Pattern","Strength%",
                                          "Candle","Day Type","RR1","Entry","T1","SL","RSI","HMA",
                                          "Vol Surge","CPR Width%"] if c in ranked_df.columns]
                    st.dataframe(
                        ranked_df[_rcols].rename(columns={"Pattern":"Side","CPR Width%":"CPR W%"}),
                        use_container_width=True,
                        hide_index=False,
                        height=min(500, 60 + len(ranked_df) * 38),
                    )
                    # Manual trade buttons for non-auto signals
                    _manual_sigs = ranked_df[ranked_df.get("🤖 Auto","") != "🤖 Auto"] if "🤖 Auto" in ranked_df.columns else ranked_df
                    if not _manual_sigs.empty:
                        st.markdown("##### 👤 Manual Trade — Click to enter any signal into Forward Testing")
                        _mcols = st.columns(min(4, len(_manual_sigs)))
                        for _mi, (_ri, _mr) in enumerate(_manual_sigs.iterrows()):
                            _side_icon = "🟢" if _mr.get("Pattern","") == "Bullish" else "🔴"
                            with _mcols[_mi % len(_mcols)]:
                                if st.button(
                                    f"{_side_icon} #{_ri} {_mr.get('Symbol','')}\n"
                                    f"Str:{int(_mr.get('Strength%',0))}% RR:{_mr.get('RR1',0):.1f}x",
                                    key=f"manual_ft_{tf_tag}_{_ri}_{_mr.get('Symbol','')}",
                                    use_container_width=True,
                                ):
                                    _msig = {
                                        "symbol":  _mr.get("Symbol",""),
                                        "side":    "BUY" if _mr.get("Pattern","") == "Bullish" else "SELL",
                                        "entry":   _mr.get("Entry", _mr.get("LTP",0)),
                                        "sl":      _mr.get("SL", 0),
                                        "t1":      _mr.get("T1", 0),
                                        "t2":      _mr.get("T2", 0),
                                        "rr1":     _mr.get("RR1", 2.0),
                                        "tf":      tf_tag,
                                        "strategy":_mr.get("Strategy","CPR"),
                                        "strength":_mr.get("Strength%",0),
                                        "candle":  _mr.get("Candle","—"),
                                        "rank_score": _mr.get("🏆 Rank Score", 0),
                                    }
                                    ft_add_signal(_msig, source=f"👤 Manual · Rank#{_ri} · {tf_tag.upper()}")
                                    st.success(f"✅ {_mr.get('Symbol','')} added to Forward Testing!")
                    st.divider()

                disp = scan_df[scan_df["Pattern"] != "Neutral"].sort_values(["Strength%","CPR Width%"], ascending=[False,True]).copy()
                for c in ["LTP","Entry","T1","T2","T3","SL","TC","BC"]:
                    if c in disp.columns:
                        disp[c] = disp[c].apply(lambda x: f"Rs.{x:,.2f}")
                disp["CPR Width%"] = disp["CPR Width%"].apply(lambda x: f"{x:.3f}%" if isinstance(x, float) else x)
                disp["Strength%"]  = disp["Strength%"].apply(lambda x: f"{x}%")
                show_cols = [c for c in ["Symbol","LTP","Strength%","Candle","Entry","T1","T2","SL","RR1","RR2","RSI","HMA","Vol Surge","CPR Width%"] if c in disp.columns]
                st.dataframe(disp[show_cols], use_container_width=True, hide_index=True)

        # ═══════════════════════════════════════════════════════════════════
        #  SEND REPORT
        # ═══════════════════════════════════════════════════════════════════
        st.divider()
        st.markdown(
            "<div style='font-family:IBM Plex Mono,monospace;font-size:0.9rem;font-weight:700;"
            "color:#1a1f0e;margin-bottom:0.75rem;'>📤  Send / Download Scanner Report</div>",
            unsafe_allow_html=True,
        )

        scan_time_str = datetime.now().strftime("%d %b %Y  %H:%M")

        # Build /* WhatsApp removed */essage text
        def _wa_text(bull_df, bear_df, tf_lbl, scan_t):
            lines = [
                "🏦 *PivotVault AI — CPR Scanner*",
                f"📅 {tf_lbl}  |  {scan_t}",
                "🔍 Frank Ochoa Strategy  |  Narrow CPR  |  R:R >= 1.5x",
                "",
                "🟢 *BULLISH SETUPS*",
            ]
            if bull_df.empty:
                lines.append("No bullish picks found.")
            else:
                for i, (_, r) in enumerate(bull_df.head(10).iterrows(), 1):
                    lines.append(
                        f"{i}. *{r['Symbol']}* Rs.{r['LTP']:,.2f}  Score {int(r['Strength%'])}%  "
                        f"{r.get('Candle','—')}  "
                        f"Entry Rs.{r['Entry']:,.2f}  T1 Rs.{r['T1']:,.2f}  SL Rs.{r['SL']:,.2f}  R:R {r['RR1']}x"
                    )
            lines += ["", "🔴 *BEARISH SETUPS*"]
            if bear_df.empty:
                lines.append("No bearish picks found.")
            else:
                for i, (_, r) in enumerate(bear_df.head(10).iterrows(), 1):
                    lines.append(
                        f"{i}. *{r['Symbol']}* Rs.{r['LTP']:,.2f}  Score {int(r['Strength%'])}%  "
                        f"{r.get('Candle','—')}  "
                        f"Entry Rs.{r['Entry']:,.2f}  T1 Rs.{r['T1']:,.2f}  SL Rs.{r['SL']:,.2f}  R:R {r['RR1']}x"
                    )
            lines += ["", "⚠️ Educational use only. Not financial advice.", "📱 Sent via PivotVault AI"]
            return "\n".join(lines)

        # Build HTML email body
        def _html_email(bull_df, bear_df, tf_lbl, scan_t):
            def _tbl_rows(df, is_bull):
                if df.empty:
                    return "<tr><td colspan='9' style='padding:8px;color:#8a9a78;font-style:italic;'>No qualifying stocks found.</td></tr>"
                hc = "#16a34a" if is_bull else "#dc2626"
                out = ""
                for _, r in df.iterrows():
                    rr_c = "#16a34a" if r.get("RR1",0)>=2 else ("#d97706" if r.get("RR1",0)>=1.5 else "#dc2626")
                    out += (
                        f"<tr style='border-bottom:1px solid #f1f5f9;'>"
                        f"<td style='padding:7px 5px;font-weight:700;font-family:Courier New,monospace;color:#1a1f0e;'>{r['Symbol']}</td>"
                        f"<td style='padding:7px 5px;font-size:0.83rem;'>Rs.{r['LTP']:,.2f}</td>"
                        f"<td style='padding:7px 5px;color:{hc};font-weight:700;'>{int(r['Strength%'])}%</td>"
                        f"<td style='padding:7px 5px;font-size:0.8rem;'>{r.get('Candle','—')}</td>"
                        f"<td style='padding:7px 5px;font-size:0.8rem;'>Rs.{r['Entry']:,.2f}</td>"
                        f"<td style='padding:7px 5px;color:{hc};'>Rs.{r['T1']:,.2f} / Rs.{r['T2']:,.2f}</td>"
                        f"<td style='padding:7px 5px;color:#c0392b;'>Rs.{r['SL']:,.2f}</td>"
                        f"<td style='padding:7px 5px;color:{rr_c};font-weight:700;'>{r.get('RR1',0)}x</td>"
                        f"<td style='padding:7px 5px;color:#5a6a48;'>{r['RSI']}</td>"
                        f"</tr>"
                    )
                return out

            TH = "background:#1e293b;color:#e2e8f0;padding:7px 5px;text-align:left;font-size:0.7rem;letter-spacing:0.06em;text-transform:uppercase;"
            TBLS = "width:100%;border-collapse:collapse;font-family:Courier New,monospace;font-size:0.82rem;"
            HDR_COL = "background:linear-gradient(135deg,#0d1f0a,#1a4a10)"

            return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#f1f5f9;">
    <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 10px;">
    <table width="700" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
    <tr><td style="{HDR_COL};padding:22px 26px;">
      <div style="font-family:Courier New,monospace;font-size:1.25rem;font-weight:700;color:#e8eddf;">🏦 PivotVault AI — CPR Scanner</div>
      <div style="font-family:Courier New,monospace;font-size:0.72rem;color:#b5c77a;margin-top:4px;letter-spacing:0.07em;text-transform:uppercase;">{tf_lbl} · Frank Ochoa Strategy · {scan_t}</div>
    </td></tr>
    <tr><td style="padding:20px 22px;">
      <div style="font-family:Courier New,monospace;font-size:0.72rem;font-weight:700;color:#2d7a3a;border-left:4px solid #16a34a;padding-left:8px;margin-bottom:10px;text-transform:uppercase;letter-spacing:0.07em;">▲ BULLISH SETUPS</div>
      <table style="{TBLS}"><tr><th style="{TH}">Symbol</th><th style="{TH}">LTP</th><th style="{TH}">Score</th><th style="{TH}">Candle</th><th style="{TH}">Entry</th><th style="{TH}">T1 / T2</th><th style="{TH}">SL</th><th style="{TH}">R:R</th><th style="{TH}">RSI</th></tr>
      {_tbl_rows(bull_df, True)}</table>
      <div style="font-family:Courier New,monospace;font-size:0.72rem;font-weight:700;color:#c0392b;border-left:4px solid #dc2626;padding-left:8px;margin:18px 0 10px;text-transform:uppercase;letter-spacing:0.07em;">▼ BEARISH SETUPS</div>
      <table style="{TBLS}"><tr><th style="{TH}">Symbol</th><th style="{TH}">LTP</th><th style="{TH}">Score</th><th style="{TH}">Candle</th><th style="{TH}">Entry</th><th style="{TH}">T1 / T2</th><th style="{TH}">SL</th><th style="{TH}">R:R</th><th style="{TH}">RSI</th></tr>
      {_tbl_rows(bear_df, False)}</table>
    </td></tr>
    <tr><td style="padding:12px 22px 20px;"><div style="background:#f7f9f2;border-radius:6px;padding:10px 14px;font-size:0.68rem;color:#8a9a78;line-height:1.6;font-family:Courier New,monospace;">⚠️ For educational purposes only. Not financial advice. Entry/Target/SL from Frank Ochoa Pivot Boss + ATR-14. Always use proper risk management.</div></td></tr>
    </table></td></tr></table></body></html>"""

        rtab1, rtab2, rtab3 = st.tabs(["📧 /* Gmail removed *// Email", "💬 WhatsApp", "⬇️ Download PDF"])

        with rtab1:
            st.markdown("<div style='font-family:IBM Plex Mono,monospace;font-size:0.75rem;color:#5a6a48;margin-bottom:0.75rem;'>Send report to any Gmail or SMTP email inbox.</div>", unsafe_allow_html=True)
            cfg = st.session_state.get("smtp_cfg", {"host": "smtp.gmail.com", "port": 587, "sender": "", "password": ""})
            with st.expander("⚙️ SMTP Settings", expanded=not bool(cfg.get("sender"))):
                sc1, sc2 = st.columns(2)
                with sc1:
                    nh = st.text_input("SMTP Host",     value=cfg["host"],     key="sc_host")
                    ns = st.text_input("Sender Email",  value=cfg["sender"],   key="sc_sender")
                with sc2:
                    np = st.selectbox("Port", [587, 465], index=0 if cfg["port"] == 587 else 1, key="sc_port")
                    nw = st.text_input("App Password",  value=cfg["password"], type="password", key="sc_pwd",
                                       help="Gmail: Google Account → Security → App Passwords (not your normal password)")
                if st.button("💾 Save", key="sc_save"):
                    st.session_state["smtp_cfg"] = {"host": nh, "port": np, "sender": ns, "password": nw}
                    st.success("SMTP settings saved!")

            ec1, ec2 = st.columns([3, 1])
            with ec1:
                to_em = st.text_input("Recipient Email", placeholder="you@gmail.com", label_visibility="collapsed", key="sc_to")
            with ec2:
                send_em = st.button("📧 Send", use_container_width=True, key="sc_send_em")

            if send_em:
                cfg2 = st.session_state.get("smtp_cfg", {})
                if not to_em.strip():
                    st.error("Enter recipient email address.")
                elif not cfg2.get("sender") or not cfg2.get("password"):
                    st.error("Configure SMTP settings above first.")
                else:
                    body = _html_email(top_bull, top_bear, tf_choice, scan_time_str)
                    with st.spinner("Sending email…"):
                        ok, msg = send_report_email(to_em.strip(), cfg2["host"], cfg2["port"], cfg2["sender"], cfg2["password"], body, scan_time_str)
                    if ok:
                        st.success(f"✅ Report sent to {to_em.strip()}")
                    else:
                        st.error(f"❌ {msg}")
                        st.caption("Gmail tip: use an App Password not your regular password. Requires 2FA enabled.")

        with rtab2:
            st.markdown("<div style='font-family:IBM Plex Mono,monospace;font-size:0.75rem;color:#5a6a48;margin-bottom:0.75rem;'>Share scanner results via WhatsApp.</div>", unsafe_allow_html=True)
            wa_msg = _wa_text(top_bull, top_bear, tf_choice, scan_time_str)
            st.text_area("Message Preview (copy or use button below)", wa_msg, height=200, key="wa_prev")
            wc1, wc2 = st.columns([3, 1])
            with wc1:
                wa_ph = st.text_input("Phone number with country code", placeholder="919876543210", label_visibility="collapsed", key="wa_ph")
            with wc2:
                wa_go = st.button("💬 Open WhatsApp", use_container_width=True, key="wa_go")
            if wa_go and wa_ph.strip():
                import urllib.parse as _up
                wa_url = "https://wa.me/" + wa_ph.strip().replace("+","") + "?text=" + _up.quote(wa_msg)
                st.markdown(
                    f"<a href='{wa_url}' target='_blank' style='display:inline-block;background:#25d366;color:#fff;"
                    f"font-family:IBM Plex Mono,monospace;font-size:0.82rem;font-weight:600;"
                    f"padding:0.55rem 1.5rem;border-radius:8px;text-decoration:none;margin-top:0.5rem;'>"
                    f"💬 Open WhatsApp →</a>",
                    unsafe_allow_html=True,
                )
                st.caption("Opens WhatsApp with message pre-filled. Just tap Send.")
            elif wa_go:
                st.warning("Enter phone number with country code (e.g. 919876543210)")
            st.caption("💡 You can also copy the message above and paste into any chat — WhatsApp, Telegram, SMS, etc.")

        with rtab3:
            st.markdown(
                "<div style='font-family:IBM Plex Mono,monospace;font-size:0.75rem;color:#5a6a48;"
                "margin-bottom:0.75rem;'>Download the scanner report as a PDF. "
                "Download a snapshot of the current scan results.</div>",
                unsafe_allow_html=True,
            )
            if st.button("📄 Generate & Download PDF", use_container_width=True, key="sc_gen_pdf"):
                with st.spinner("Building PDF…"):
                    try:
                        pdf_bytes = build_scanner_pdf(top_bull, top_bear, tf_choice, scan_time_str)
                        st.download_button(
                            label=f"⬇️ Download PDF — {tf_tag.upper()} Scanner",
                            data=pdf_bytes,
                            file_name=f"PivotVault_Scanner_{tf_tag}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="sc_pdf_dl",
                        )
                        st.success("PDF ready — click button above to download!")
                    except Exception as ex:
                        st.error(f"PDF error: {ex}")

        # ── Footer ────────────────────────────────────────────────────────────────

            # ── Footer ────────────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="background:#f7f9f2;border:1px solid #dae0cb;border-radius:10px;
                    padding:0.9rem 1.1rem;margin-top:0.75rem;
                    font-family:IBM Plex Mono,monospace;font-size:0.7rem;color:#5a6a48;line-height:1.9;">
        <b style="color:#1a1f0e;">Auto-Refresh Schedule</b><br>
        ⚡ 15 Min chart → refreshes every <b>15 minutes</b> &nbsp;|&nbsp;
        🕐 1 Hour chart → refreshes every <b>1 hour</b> &nbsp;|&nbsp;
        📅 1 Day chart → refreshes every <b>4 hours</b> &nbsp;|&nbsp;
        📆 1 Week / 🗓️ 1 Month → refresh every <b>24 hours</b><br>
        <b style="color:#1a1f0e;">Filter:</b> Narrow CPR &lt; 0.25% · Strength 85–100% · Top 10 per direction · NSE 500
        </div>
        """, unsafe_allow_html=True)

    with tab_sig:
        st.markdown("<div style='font-family:DM Mono,monospace;font-size:0.72rem;color:#5a6a48;"
            "padding:0.4rem 0.9rem;margin-bottom:0.75rem;background:#f0f4e8;"
            "border-radius:6px;border-left:3px solid #4e6130;'>"
            "⚡ All scans (manual + auto, all timeframes) appear here &nbsp;|&nbsp; "
            "🧪 <b>Fwd Test</b> = paper trade &nbsp;|&nbsp; "
            "🤖 <b>Auto Trade</b> = instant FT entry + Upstox order &nbsp;|&nbsp; "
            "🕐 Auto window: <b>9:45–14:45 IST</b> · Str≥75% · RR≥2.0</div>",
            unsafe_allow_html=True)
        import json

        # ── Header ────────────────────────────────────────────────────────────
        h1, h2 = st.columns([5, 1])
        with h1:
            st.markdown("""
            <div class="title-bar">
                <span style="font-size:1.5rem;">🔔</span>
                <h1 style="color:#1a1f0e;">Trade Signals</h1>
                <span style="margin-left:auto;background:#edf7ee;border:1px solid #b8dfc0;
                             color:#2d7a3a;padding:3px 12px;border-radius:20px;
                             font-family:DM Mono,monospace;font-size:0.72rem;font-weight:700;">
                    LIVE · CPR SCANNER SYNC
                </span>
            </div>
            """, unsafe_allow_html=True)
        with h2:
            # Notification enable button — calls window.parent
            st.markdown("""
            <button onclick="(function(){
                var w = window.parent || window;
                if (!w.Notification) { alert('Notifications not supported in this browser.'); return; }
                w.Notification.requestPermission().then(function(p){
                    if (p === 'granted') {
                        w._pvNotifEnabled = true;
                        new w.Notification('🏦 PivotVault AI', {
                            body: 'Trade signal notifications are now ON!',
                            icon: '/static/icon-192.png',
                            tag:  'pv-enable'
                        });
                    } else {
                        alert('Notification permission denied. Please allow notifications in your browser settings.');
                    }
                });
            })()"
            style="width:100%;padding:8px 6px;background:#4e6130;color:#fff;
                   border:none;border-radius:8px;font-family:DM Sans,sans-serif;
                   font-size:0.75rem;font-weight:700;cursor:pointer;
                   transition:opacity 0.2s;" id="notif-enable-btn">
            🔔 Enable Alerts
            </button>
            <script>
            // Update button text based on current permission
            (function checkPerm(){
                var w = window.parent || window;
                var btn = document.getElementById("notif-enable-btn");
                if (!btn) { setTimeout(checkPerm, 300); return; }
                if (w.Notification && w.Notification.permission === "granted") {
                    btn.style.background = "#2d7a3a";
                    btn.innerText = "✅ Alerts ON";
                } else if (w.Notification && w.Notification.permission === "denied") {
                    btn.style.background = "#c0392b";
                    btn.innerText = "🔕 Blocked";
                    btn.title = "Allow notifications in browser settings (🔒 icon in address bar)";
                }
            })();
            </script>
            """, unsafe_allow_html=True)

        # ── Auto-refresh: inherit from scanner (15m & 1h only) ────────────────
        if _HAS_AUTOREFRESH and is_market_open():
            st_autorefresh(interval=15_000, limit=None, key="signals_autorefresh")
        # Also track 30m scan time
        if 'cpr_scan_time_30m' not in st.session_state:
            st.session_state['cpr_scan_time_30m'] = 0

        # ── Pull data from CPR scanner session state ──────────────────────────
        # ── Pull signals from ALL scans (auto + manual) ────────────────────────
        # tf_filter_key must match the multiselect options exactly
        TF_LABELS = {
            "cpr_scan_15m":  ("⚡ 15 Min",  "#7c3aed", "15m",  "⚡ 15 Min"),
            "cpr_scan_30m":  ("⏱️ 30 Min",  "#ea580c", "30m",  "⏱️ 30 Min"),
            "cpr_scan_1h":   ("🕐 1 Hour",  "#1d4ed8", "1h",   "🕐 1 Hour"),
            "cpr_scan_1d":   ("📅 Daily",   "#0f766e", "1d",   "📅 Daily"),
            "cpr_scan_1wk":  ("📆 Weekly",  "#b45309", "1wk",  "📆 Weekly"),
            "cpr_scan_1mo":  ("🗓️ Monthly", "#be185d", "1mo",  "🗓️ Monthly"),
        }

        all_signals = []
        scan_times  = {}

        for key, (label, color, tag, tf_filter_key) in TF_LABELS.items():
            _raw = st.session_state.get(key)
            df = _raw if isinstance(_raw, pd.DataFrame) else pd.DataFrame()
            ts = st.session_state.get(f"cpr_scan_time_{tag}", 0)
            if not df.empty:
                scan_times[label] = datetime.fromtimestamp(ts).strftime("%d %b %H:%M") if ts else "—"
                for _, r in df.iterrows():
                    # ── BEST-SETUP QUALITY GATES ────────────────────────────
                    # Only signals passing ALL four rules reach the signals feed:
                    #  1. R:R >= 2.0   2. Strength >= 75%
                    #  3. SL distance >= 0.50% from entry
                    #  4. Spot/LTP vs Entry distance >= 0.25% (entry not already blown through)
                    _rr1_val   = float(r.get("RR1", 0) or 0)
                    _str_val   = float(r.get("Strength%", 0) or 0)
                    _entry_val = float(r.get("Entry", 0) or 0)
                    _sl_val    = float(r.get("SL", 0) or 0)
                    _ltp_val   = float(r.get("LTP", 0) or 0)

                    if _entry_val <= 0:
                        continue
                    _sl_dist_pct   = abs(_entry_val - _sl_val)  / _entry_val * 100
                    _spot_dist_pct = abs(_ltp_val   - _entry_val) / _entry_val * 100 if _ltp_val > 0 else 0

                    if _rr1_val < 2.0:
                        continue                       # Rule 1: R:R >= 2.0
                    if _str_val < 75:
                        continue                       # Rule 2: Strength >= 75%
                    if _sl_dist_pct < 0.50:
                        continue                       # Rule 3: SL >= 0.50% from entry
                    if _spot_dist_pct < 0.25:
                        continue                       # Rule 4: Spot must be >=0.25% from entry
                                                        #         (price hasn't already run past the trigger)

                    _sig = {
                        "tf":       tf_filter_key,   # matches multiselect options exactly
                        "tf_label": label,            # full label with AUTO badge for display
                        "tf_color": color,
                        "symbol":   r["Symbol"],
                        "side":     "BUY"  if r["Pattern"] == "Bullish" else "SELL",
                        "ltp":      r["LTP"],
                        "entry":    r["Entry"],
                        "t1":       r["T1"],
                        "t2":       r["T2"],
                        "t3":       r["T3"],
                        "sl":       r["SL"],
                        "rr1":      r["RR1"],
                        "rr2":      r.get("RR2", 0),
                        "strength": int(r["Strength%"]),
                        "candle":   r.get("Candle", "—"),
                        "rsi":       r.get("RSI", 0),
                        "hma":       r.get("HMA", "—"),
                        "vol":       r.get("Vol Surge", "—"),
                        "cpr_w":     r.get("CPR Width%", 0),
                        "cpr_type":  r.get("CPR Type", "—"),
                        "virgin_cpr":r.get("Virgin CPR","—") == "⭐ Yes",
                        "atr":       r.get("ATR", 0),
                        "stoch":     r.get("Stoch%K", "—"),
                        "rationale": r.get("Rationale",""),
                        "sl_dist_pct":   round(_sl_dist_pct, 2),
                        "spot_dist_pct": round(_spot_dist_pct, 2),
                    }
                    _sig["strategy_name"] = _build_strategy_name(_sig)
                    _sig["strategy_id"]   = _strategy_short_id(_sig)
                    all_signals.append(_sig)

        # ── Status bar ────────────────────────────────────────────────────────
        if not all_signals:
            st.markdown("""
            <div style="text-align:center;padding:3rem 1rem;background:#f7f9f2;
                        border:2px dashed #dae0cb;border-radius:12px;
                        font-family:DM Mono,monospace;">
                <div style="font-size:2rem;margin-bottom:0.75rem;">📡</div>
                <div style="font-size:1rem;font-weight:700;color:#1a1f0e;margin-bottom:0.5rem;">
                    No signals yet
                </div>
                <div style="font-size:0.82rem;color:#5a6a48;">
                    Go to <b>📡 CPR Scanner</b> → select any timeframe
                    → click <b>🔄 Scan Now</b><br>
                    All signals (manual or auto, any timeframe) appear here automatically.
                </div>
            </div>
            """, unsafe_allow_html=True)
            # Quick scan shortcut buttons
            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                if st.button("📡 Go to CPR Scanner → Run Scan", use_container_width=True, key="goto_scanner"):
                    st.session_state["current_page"] = "Scanner & Signals"
                    st.rerun()
            return

        # Scan time info
        time_pills = " &nbsp;·&nbsp; ".join(
            f"<span style='color:{TF_LABELS[k][1] if k in TF_LABELS else '#5a6a48'};font-weight:700;'>{label}</span> "
            f"<span style='color:#8a9a78;'>scanned {t}</span>"
            for label, t in scan_times.items()
        ) if scan_times else ""

        # Staleness check
        now_ts   = time.time()
        now_ts   = time.time()
        # Check if any active scan is stale (intraday = 30min, daily+ = 4hr)
        def _is_stale(tag, intraday_secs):
            ts = st.session_state.get(f"cpr_scan_time_{tag}", 0)
            return ts > 0 and (now_ts - ts) > intraday_secs
        any_stale = any([
            _is_stale("15m",  1800), _is_stale("30m",  3600),
            _is_stale("1h",   7200), _is_stale("1d",  14400),
            _is_stale("1wk", 86400), _is_stale("1mo", 86400),
        ])

        if any_stale:
            st.warning(
                "⚠️ Some signals may be stale — go to 📡 Scanner and run a fresh scan "
                "before acting on these signals.",
                icon="⏰",
            )

        st.markdown(
            f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
            f"color:#5a6a48;margin-bottom:1rem;padding:0.5rem 0.9rem;"
            f"background:#f7f9f2;border:1px solid #dae0cb;border-radius:8px;"
            f"border-left:3px solid #4e6130;display:flex;flex-wrap:wrap;gap:12px;align-items:center;'>"
            f"<span class='live-dot'></span>"
            f"<span style='font-weight:700;color:#4e6130;'>LIVE SIGNALS</span>"
            f"{time_pills}"
            f"<span style='margin-left:auto;color:#8a9a78;'>{len(all_signals)} signals total</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── Filters ───────────────────────────────────────────────────────────
        fc1, fc2, fc3, fc4 = st.columns([2, 2, 1.5, 1.5])
        with fc1:
            tf_filter = st.multiselect("Timeframe", ["⚡ 15 Min","⏱️ 30 Min","🕐 1 Hour","📅 Daily","📆 Weekly","🗓️ Monthly"],
                                        default=["⚡ 15 Min","⏱️ 30 Min","🕐 1 Hour","📅 Daily","📆 Weekly","🗓️ Monthly"],
                                        key="sig_tf_filter", label_visibility="collapsed")
        with fc2:
            side_filter = st.radio("Direction", ["All","BUY only","SELL only"],
                                    horizontal=True, key="sig_side_filter", label_visibility="collapsed")
        with fc3:
            min_str = st.slider("Min Strength%", 0, 100, 75, key="sig_min_str")
        with fc4:
            min_rr = st.slider("Min R:R", 0.0, 5.0, 2.0, step=0.1, key="sig_min_rr")

        st.caption(
            "✅ Best-Setup filter active: R:R ≥ 2.0 · Strength ≥ 75% · "
            "SL ≥ 0.50% from entry · Spot price ≥ 0.25% from entry "
            "(entry not already run past). Sliders above narrow further."
        )

        # Apply filters
        filtered = [s for s in all_signals
                    if (not tf_filter or s["tf"] in tf_filter)
                    and (side_filter == "All"
                         or (side_filter == "BUY only"  and s["side"] == "BUY")
                         or (side_filter == "SELL only" and s["side"] == "SELL"))
                    and s["strength"] >= min_str
                    and s["rr1"] >= min_rr]

        # Sort: strength desc, then CPR width asc
        filtered.sort(key=lambda x: (-x["strength"], x["cpr_w"]))

        if not filtered:
            st.info(f"No signals match current filters. Try reducing Min Strength or Min R:R.")
            return

        bull_sigs = [s for s in filtered if s["side"] == "BUY"]
        bear_sigs = [s for s in filtered if s["side"] == "SELL"]

        st.markdown(
            f"<div style='font-family:DM Mono,monospace;font-size:0.75rem;color:#5a6a48;"
            f"margin-bottom:0.75rem;'>Showing <b>{len(filtered)}</b> signals — "
            f"<span style='color:#2d7a3a;font-weight:700;'>▲ {len(bull_sigs)} Bullish</span> &nbsp;"
            f"<span style='color:#c0392b;font-weight:700;'>▼ {len(bear_sigs)} Bearish</span></div>",
            unsafe_allow_html=True,
        )

        broker = st.session_state.get("broker", "none")

        # ── Signal cards ──────────────────────────────────────────────────────
        def _signal_card_html(s: dict) -> str:
            bull    = s["side"] == "BUY"
            ac      = "#2d7a3a" if bull else "#c0392b"
            bg      = "#edf7ee" if bull else "#fdf0ee"
            bdr     = "#b8dfc0" if bull else "#f0c0b8"
            arrow   = "▲" if bull else "▼"
            rr_col  = "#2d7a3a" if s["rr1"] >= 2 else ("#b8860b" if s["rr1"] >= 1.5 else "#c0392b")
            str_w   = min(s["strength"], 100)
            tf_c    = s["tf_color"]
            return f"""
    <div style="background:#ffffff;border:1px solid #dae0cb;border-radius:12px;
                padding:1rem 1.1rem;border-top:4px solid {ac};
                box-shadow:0 2px 10px rgba(50,70,20,0.07);
                animation:slideIn 0.25s ease;font-family:DM Sans,sans-serif;">
      <!-- Strategy name badge -->
      <div style="font-family:DM Mono,monospace;font-size:0.68rem;font-weight:700;
                  color:{ac};background:{bg};border:1px solid {bdr};
                  border-radius:6px;padding:3px 8px;margin-bottom:7px;
                  letter-spacing:0.03em;line-height:1.4;">
        🎯 {s.get('strategy_name','—')}
      </div>
      <!-- Header row -->
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <span style="font-size:1.1rem;font-weight:900;color:#1a1f0e;">{s['symbol']}</span>
          <span style="background:{bg};color:{ac};border:1px solid {bdr};
                       border-radius:20px;padding:2px 9px;font-size:0.68rem;font-weight:700;">
            {arrow} {s['side']}
          </span>
          <span style="background:{tf_c}18;color:{tf_c};border:1px solid {tf_c}44;
                       border-radius:12px;padding:1px 7px;font-size:0.65rem;font-weight:700;">
            {s.get('tf_label', s['tf'])}
          </span>
        </div>
        <span style="font-family:DM Mono,monospace;font-size:0.72rem;color:#5a6a48;">
          LTP ₹{s['ltp']:,.2f}
        </span>
      </div>
      <!-- Strategy name banner -->
      <div style="background:{'rgba(26,107,46,0.07)' if bull else 'rgba(158,32,24,0.07)'};
                  border-left:3px solid {ac};border-radius:0 6px 6px 0;
                  padding:4px 10px;margin-bottom:8px;
                  font-family:DM Mono,monospace;font-size:0.68rem;
                  color:{ac};font-weight:700;letter-spacing:0.02em;
                  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        🎯 {s.get('strategy_name','—')}
      </div>
      <!-- Level pills -->
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-bottom:8px;">
        <div style="background:#f7f9f2;border-radius:7px;padding:5px 3px;text-align:center;">
          <div style="font-size:0.58rem;color:#8a9a78;font-family:DM Mono,monospace;text-transform:uppercase;">Entry</div>
          <div style="font-size:0.8rem;font-weight:700;color:#1a1f0e;font-family:DM Mono,monospace;">₹{s['entry']}</div>
        </div>
        <div style="background:#f7f9f2;border-radius:7px;padding:5px 3px;text-align:center;">
          <div style="font-size:0.58rem;color:#8a9a78;font-family:DM Mono,monospace;text-transform:uppercase;">T1</div>
          <div style="font-size:0.8rem;font-weight:700;color:#2d7a3a;font-family:DM Mono,monospace;">₹{s['t1']}</div>
        </div>
        <div style="background:#f7f9f2;border-radius:7px;padding:5px 3px;text-align:center;">
          <div style="font-size:0.58rem;color:#8a9a78;font-family:DM Mono,monospace;text-transform:uppercase;">T2</div>
          <div style="font-size:0.8rem;font-weight:700;color:#2d7a3a;font-family:DM Mono,monospace;">₹{s['t2']}</div>
        </div>
        <div style="background:#f7f9f2;border-radius:7px;padding:5px 3px;text-align:center;">
          <div style="font-size:0.58rem;color:#8a9a78;font-family:DM Mono,monospace;text-transform:uppercase;">SL</div>
          <div style="font-size:0.8rem;font-weight:700;color:#c0392b;font-family:DM Mono,monospace;">₹{s['sl']}</div>
        </div>
        <div style="background:{rr_col}15;border-radius:7px;padding:5px 3px;text-align:center;border:1px solid {rr_col}33;">
          <div style="font-size:0.58rem;color:#8a9a78;font-family:DM Mono,monospace;text-transform:uppercase;">R:R</div>
          <div style="font-size:0.8rem;font-weight:700;color:{rr_col};font-family:DM Mono,monospace;">{s['rr1']}x</div>
        </div>
      </div>
      <!-- Strategy rationale -->
      <div style="font-family:DM Mono,monospace;font-size:0.68rem;color:#4a5e32;
                  background:#f5f8ed;border-radius:5px;padding:4px 7px;
                  margin-bottom:6px;border-left:3px solid {ac};">
        {s.get('rationale','') or (s['candle'] + ' · RSI ' + str(s['rsi']) + ' · HMA ' + str(s['hma']))}
      </div>
      <!-- Strength bar -->
      <div style="margin-bottom:6px;">
        <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
          <span style="font-family:DM Mono,monospace;font-size:0.65rem;color:#8a9a78;">
            Vol {s['vol']} &nbsp;·&nbsp; Stoch {s.get('stoch','—')} &nbsp;·&nbsp;
            {('⭐ Virgin CPR' if s.get('virgin_cpr') else 'CPR ' + s.get('cpr_type',''))}
          </span>
          <span style="font-family:DM Mono,monospace;font-size:0.72rem;font-weight:800;color:{ac};">
            {s['strength']}%
          </span>
        </div>
        <div style="background:#e8eddf;border-radius:4px;height:6px;overflow:hidden;">
          <div style="background:{ac};width:{str_w}%;height:100%;border-radius:4px;
                      transition:width 0.5s;"></div>
        </div>
      </div>
    </div>"""

        # Render in 2-column grid (bull left, bear right on desktop)
        if bull_sigs and bear_sigs:
            col_bull, col_bear = st.columns(2)
            with col_bull:
                st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
                            f"color:#2d7a3a;font-weight:700;margin-bottom:0.5rem;'>▲ BULLISH ({len(bull_sigs)})</div>",
                            unsafe_allow_html=True)
                for s in bull_sigs:
                    st.markdown(_signal_card_html(s), unsafe_allow_html=True)
                    _trade_buttons(s)
            with col_bear:
                st.markdown(f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
                            f"color:#c0392b;font-weight:700;margin-bottom:0.5rem;'>▼ BEARISH ({len(bear_sigs)})</div>",
                            unsafe_allow_html=True)
                for s in bear_sigs:
                    st.markdown(_signal_card_html(s), unsafe_allow_html=True)
                    _trade_buttons(s)
        else:
            for s in filtered:
                st.markdown(_signal_card_html(s), unsafe_allow_html=True)
                _trade_buttons(s)

        # Desktop notifications for new signals
        if filtered:
            notif_js = json.dumps([{
                "symbol":s["symbol"],"side":s["side"],
                "entry":s["entry"],"t1":s["t1"],"sl":s["sl"],
                "rr":s["rr1"],"strength":s["strength"],"candle":s["candle"]
            } for s in filtered[:6]])
            st.markdown(f"""
            <script>
            (function(){{
                var sigs = {notif_js};
                var w = window.parent || window;
                if (w._pvNotifEnabled || (w.Notification && w.Notification.permission === "granted")) {{
                    sigs.forEach(function(s){{
                        if (w._pvNotify) {{
                            w._pvNotify(
                                (s.side==="BUY"?"🟢 BUY":"🔴 SELL")+" — "+s.symbol+" ("+s.strength+"%)",
                                "Entry ₹"+s.entry+"  T1 ₹"+s.t1+"  SL ₹"+s.sl+"  R:R "+s.rr+"x",
                                "pv-"+s.symbol
                            );
                        }} else {{
                            var n = new w.Notification(
                                (s.side==="BUY"?"🟢 BUY":"🔴 SELL")+" — "+s.symbol+" ("+s.strength+"%)",
                                {{body:"Entry ₹"+s.entry+"  T1 ₹"+s.t1+"  SL ₹"+s.sl+"  R:R "+s.rr+"x",
                                  icon:"/static/icon-192.png",tag:"pv-"+s.symbol,requireInteraction:false}}
                            );
                        }}
                    }});
                }}
            }})();
            </script>
            """, unsafe_allow_html=True)

        st.caption("⚠️ Signals from CPR Scanner (15Min + 1Hour). Frank Ochoa Pivot methodology. Not financial advice.")



def _trade_buttons(s: dict):
    """
    Broker buttons + Fwd Test button.
    When a broker button is clicked:
      - Opens broker in new tab for order placement
      - Simultaneously logs a PENDING trade in Forward Testing
      - Forward Testing then polls live price to auto-trigger SL/Target
      - On trigger, event is recorded with timestamp + P&L
    """
    from datetime import timezone as _tz
    bull     = s["side"] == "BUY"
    sym      = s["symbol"]
    mkt_open = is_market_open()
    up_live  = _upstox_connected()
    IST      = _tz(timedelta(hours=5, minutes=30))
    now_ist  = datetime.now(IST)

    if not mkt_open:
        if now_ist.weekday() >= 5:        next_open = "Opens Monday 9:15 AM IST"
        elif now_ist.hour < 9 or (now_ist.hour == 9 and now_ist.minute < 15):
                                           next_open = "Opens today 9:15 AM IST"
        else:                              next_open = "Opens tomorrow 9:15 AM IST"
    else:
        next_open = ""

    # Status bar
    from datetime import timezone as _tzs
    _ISTs   = _tzs(timedelta(hours=5, minutes=30))
    _now_s  = datetime.now(_ISTs)
    _auto_ok = is_auto_trade_open()

    if mkt_open and _auto_ok:
        status_html = ("<span style='color:#1a6b2e;font-weight:700;'>● NSE Open</span>"
                       " · 🇮🇳 9:45–14:45 IST | 🇺🇸 9:45–15:45 EST — ACTIVE")
    elif mkt_open and not _auto_ok:
        status_html = ("<span style='color:#b8860b;font-weight:700;'>● Pre-open phase</span>"
                       " · 🇮🇳 Auto trades from 9:45 AM IST | 🇺🇸 Opens 9:45 AM EST")
    elif up_live:
        status_html = f"<span style='color:#7c3aed;font-weight:700;'>● Upstox Live</span> · {next_open}"
    else:
        status_html = f"<span style='color:#b8860b;font-weight:700;'>● Market Closed</span> · {next_open}"
    st.markdown(
        f"<div style='font-family:DM Mono,monospace;font-size:0.65rem;"
        f"color:#2e3d1a;margin-bottom:5px;'>{status_html}</div>",
        unsafe_allow_html=True,
    )

    # URLs
    groww_url  = f"https://groww.in/search?q={sym}"
    kite_url   = f"https://kite.zerodha.com/?q={sym}"
    upstox_url = f"https://pro.upstox.com/stocks/details/NSE/{sym}"

    btn_style = ("display:block;text-align:center;padding:8px 0;"
                 "border-radius:7px;font-size:0.78rem;font-weight:700;"
                 "text-decoration:none;font-family:DM Sans,sans-serif;")
    lock_style= ("display:block;text-align:center;padding:8px 0;"
                 "background:#e8eddf;color:#8a9a78;border-radius:7px;"
                 "font-size:0.72rem;font-weight:600;font-family:DM Sans,sans-serif;"
                 "cursor:not-allowed;border:1px dashed #b8c89a;")

    def _log_broker_trade(broker_name: str):
        """Log this signal as a Forward Test trade when broker button is clicked."""
        try:
            ltp = _ft_get_ltp(sym)
            if not ltp: ltp = s.get("entry", 0)
        except Exception:
            ltp = s.get("entry", 0)
        if not ltp: return

        # Load FT data
        if not st.session_state.get("ft_loaded"):
            saved = _ft_load()
            st.session_state["ft_trades"]  = saved["trades"]
            st.session_state["ft_balance"] = saved["balance"]
            st.session_state["ft_start"]   = saved.get("starting", 10000000.0)
            st.session_state["ft_loaded"]  = True

        bal = st.session_state.get("ft_balance", 10000000.0)
        qty = max(1, int(bal * 0.05 / max(ltp, 1)))
        cost= round(ltp * qty, 2)
        if cost > bal:
            qty  = max(1, int(bal * 0.02 / max(ltp, 1)))
            cost = round(ltp * qty, 2)
        if cost > bal:
            st.toast(f"⚠️ Insufficient Forward Test balance for {sym}", icon="⚠️")
            return

        trade = {
            "id":         len(st.session_state.get("ft_trades", [])) + 1,
            "symbol":     sym,
            "side":       s["side"],
            "entry":      ltp,
            "qty":        qty,
            "sl":         s.get("sl",  round(ltp * (0.98 if bull else 1.02), 2)),
            "target":     s.get("t1",  round(ltp * (1.03 if bull else 0.97), 2)),
            "t2":         s.get("t2",  round(ltp * (1.06 if bull else 0.94), 2)),
            "rr":         s.get("rr1", 2.0),
            "cost":       cost,
            "status":     "OPEN",
            "pnl":        0.0,
            "ltp":        ltp,
            "exit_px":    None,
            "exit_time":  None,
            "source":     f"{broker_name} · {s.get('tf','—')}",
            "strategy":   s.get("rationale", s.get("strategy","CPR Signal"))[:50],
            "opened_at":  datetime.now().strftime("%d %b %H:%M:%S"),
        }
        trades = st.session_state.get("ft_trades", [])
        trades.append(trade)
        bal -= cost
        st.session_state["ft_trades"]  = trades
        st.session_state["ft_balance"] = round(bal, 2)
        _ft_save({"trades": trades, "balance": round(bal, 2),
                  "starting": st.session_state.get("ft_start", 100000.0)})
        st.toast(f"📋 {broker_name} trade logged in Forward Test — {sym} {s['side']} {qty}× @ ₹{ltp}", icon="✅")

    # ── 5 columns: Groww | Zerodha | Upstox | 🧪 Fwd Test | 🤖 Auto Trade ────
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        if mkt_open:
            ac = "#00b386" if bull else "#e74c3c"
            st.markdown(
                f"<a href='{groww_url}' target='_blank' "
                f"style='{btn_style}background:{ac};color:#fff;'>"
                f"{'🟢' if bull else '🔴'} Groww</a>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"<div style='{lock_style}' title='{next_open}'>🔒 Groww</div>",
                        unsafe_allow_html=True)

    with c2:
        if mkt_open:
            st.markdown(
                f"<a href='{kite_url}' target='_blank' "
                f"style='{btn_style}background:#387ed1;color:#fff;'>⚡ Zerodha</a>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"<div style='{lock_style}' title='{next_open}'>🔒 Zerodha</div>",
                        unsafe_allow_html=True)

    with c3:
        if up_live and mkt_open:
            if st.button(
                f"{'🟢' if bull else '🔴'} Upstox Order",
                key=f"upstox_order_{sym}_{s['side']}_{s['tf']}",
                use_container_width=True,
            ):
                st.session_state["upstox_order_preview"] = {
                    "symbol": sym, "side": s["side"],
                    "sl": s.get("sl",0), "t1": s.get("t1",0), "t2": s.get("t2",0),
                    "rr": s.get("rr1",2.0), "tf": s.get("tf","—"),
                    "strategy": s.get("rationale","CPR Signal")[:50],
                    "strength": s.get("strength",0),
                }
                st.rerun()
        elif up_live and not mkt_open:
            st.markdown(f"<div style='{lock_style}' title='{next_open}'>🔒 Upstox</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(
                f"<div title='Connect Upstox in ⚙️ Broker Settings' "
                f"style='{lock_style}border-color:#c8a0f0;color:#9a6cc8;'>💜 Upstox</div>",
                unsafe_allow_html=True,
            )

    with c4:
        if st.button("🧪 Fwd Test", key=f"fwd_{sym}_{s['side']}_{s['tf']}",
                     use_container_width=True):
            try:
                live = _ft_get_ltp(sym) or s.get("entry", 0)
            except Exception:
                live = s.get("entry", 0)
            st.session_state["ft_pending_signal"] = {
                "symbol":   sym,
                "side":     s["side"],
                "entry":    live,
                "sl":       s.get("sl",    0),
                "t1":       s.get("t1",    0),
                "t2":       s.get("t2",    0),
                "rr1":      s.get("rr1",   2.0),
                "tf":       s.get("tf",    "—"),
                "strength": s.get("strength", 0),
                "candle":   s.get("candle",   "—"),
                "rationale":s.get("rationale","CPR Signal"),
                "strategy": s.get("strategy", s.get("rationale","CPR Signal"))[:50],
                "source":   f"🖐 Manual · {s.get('tf','—')}",
            }
            st.session_state["current_page"] = "Forward Testing"
            st.rerun()

    with c5:
        # 🤖 Auto Trade — immediately executes via ft_add_signal (same as scanner auto)
        _auto_key = f"auto_{sym}_{s['side']}_{s['tf']}"
        if _auto_ok and mkt_open:
            if st.button("🤖 Auto Trade", key=_auto_key, use_container_width=True,
                         help="Instantly add to Forward Testing auto-trader (respects SL & target)"):
                try:
                    live = _ft_get_ltp(sym) or s.get("entry", 0)
                except Exception:
                    live = s.get("entry", 0)
                _sig_auto = {
                    "symbol":    sym,
                    "side":      s["side"],
                    "entry":     live or s.get("entry", 0),
                    "sl":        s.get("sl",  0),
                    "t1":        s.get("t1",  0),
                    "t2":        s.get("t2",  0),
                    "rr1":       s.get("rr1", 2.0),
                    "tf":        s.get("tf",  "—"),
                    "strength":  s.get("strength", 0),
                    "candle":    s.get("candle",   "—"),
                    "rationale": s.get("rationale","CPR Signal"),
                    "strategy":  s.get("strategy", s.get("rationale","CPR Signal"))[:50],
                    "ltp":       live or s.get("ltp", 0),
                    "cprw":      s.get("cpr_w", 1.0),
                }
                ft_add_signal(_sig_auto, source=f"🤖 Manual·AutoTrade · {s.get('tf','—').upper()}")
                if up_live:
                    # Also place real Upstox order if connected
                    try:
                        _qty = max(1, int(st.session_state.get("ft_balance", 100000) * 0.05 / max(live, 1)))
                        _ord = upstox_place_order(sym, s["side"], _qty)
                        if _ord["success"]:
                            st.toast(f"✅ 🤖 {sym} {s['side']} order placed on Upstox! Order ID: {_ord['order_id']}", icon="🤖")
                        else:
                            st.toast(f"🤖 Added to FT. Upstox order failed: {_ord['message'][:60]}", icon="⚠️")
                    except Exception as _oe:
                        st.toast(f"🤖 {sym} added to Forward Testing (Upstox: {str(_oe)[:50]})", icon="🤖")
                else:
                    st.toast(f"🤖 {sym} {s['side']} auto-added to Forward Testing!", icon="🤖")
                _send_telegram(_tg_trade_msg({
                    "symbol": sym, "side": s["side"], "entry": live,
                    "target": s.get("t1",0), "sl": s.get("sl",0),
                    "qty": 1, "cost": live, "rr": s.get("rr1",2.0), "pnl": 0,
                    "tf": s.get("tf","—"),
                }, "ENTRY"))
                st.rerun()
        elif mkt_open and not _auto_ok:
            st.markdown(
                f"<div style='{lock_style}' title='Auto trade window: 9:45–14:45 IST'>⏰ Auto Opens 9:45</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='{lock_style}' title='{next_open}'>🔒 Auto Trade</div>",
                unsafe_allow_html=True,
            )

    preview = st.session_state.get("upstox_order_preview")
    if preview and preview.get("symbol") == sym:
        try:    ltp = _ft_get_ltp(sym) or s.get("entry",0)
        except: ltp = s.get("entry",0)
        qty  = 100
        cost = round(ltp * qty, 2)
        sl   = preview.get("sl",0)
        t1   = preview.get("t1",0)
        t2   = preview.get("t2",0)
        risk = round(abs(ltp-sl)*qty,2) if sl else 0
        rew  = round(abs(t1-ltp)*qty,2) if t1 else 0
        funds= upstox_get_funds()
        avail= funds.get("available",0)

        st.markdown(
            f"<div style='background:#1a1f0e;border-radius:12px;"
            f"padding:1rem 1.25rem;margin:0.5rem 0;border:2px solid #7c3aed;'>"
            f"<div style='font-family:DM Mono,monospace;font-size:0.65rem;"
            f"color:#c8a0f0;letter-spacing:0.1em;text-transform:uppercase;"
            f"margin-bottom:0.6rem;'>⚡ Order Preview — Human Confirmation Required</div>"
            f"<div style='display:grid;grid-template-columns:repeat(3,1fr);"
            f"gap:8px;font-family:DM Mono,monospace;font-size:0.78rem;"
            f"color:#f8faf0;margin-bottom:0.75rem;'>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>SYMBOL</div><b style='font-size:1rem;'>{sym}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>SIDE</div><b style='color:{'#4dbb6a' if bull else '#f08080'};font-size:1rem;'>{preview['side']}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>QTY</div><b style='font-size:1rem;'>{qty}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>ENTRY (MARKET)</div><b>₹{ltp:,.2f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>COST</div><b>₹{cost:,.0f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>AVAIL MARGIN</div><b style='color:{'#4dbb6a' if avail>cost else '#f08080'}'>₹{avail:,.0f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>SL GTT</div><b style='color:#f08080;'>₹{sl:,.2f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>T1 GTT</div><b style='color:#4dbb6a;'>₹{t1:,.2f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>T2</div><b style='color:#4dbb6a;'>₹{t2:,.2f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>MAX RISK</div><b style='color:#f08080;'>₹{risk:,.0f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>REWARD T1</div><b style='color:#4dbb6a;'>₹{rew:,.0f}</b></div>"
            f"<div><div style='color:#7da048;font-size:0.62rem;'>R:R</div><b>{preview.get('rr',0)}x</b></div>"
            f"</div>"
            f"<div style='font-family:DM Mono,monospace;font-size:0.6rem;color:#7da048;"
            f"border-top:1px solid #2e3d1a;padding-top:0.4rem;'>"
            f"⚠️ Clicking CONFIRM places a real order on your Upstox account. "
            f"SL + T1 GTT set automatically. Not investment advice. You are responsible."
            f"</div></div>",
            unsafe_allow_html=True,
        )
        cf1, cf2 = st.columns(2)
        with cf1:
            if st.button("✅ CONFIRM — Place Real Order", key=f"confirm_{sym}",
                         use_container_width=True):
                if avail < cost:
                    st.error(f"Insufficient margin. Need ₹{cost:,.0f}, have ₹{avail:,.0f}")
                else:
                    with st.spinner("Placing market order..."):
                        res = upstox_place_order(sym, preview["side"], qty, "MARKET")
                    if res["success"]:
                        st.success(f"✅ Order placed: {res['order_id']}")
                        with st.spinner("Setting SL + Target GTT..."):
                            gtt = upstox_place_gtt(sym, preview["side"], qty, sl, t1, t2)
                        if gtt["success"]:
                            st.success(f"✅ GTT set: {gtt['message']}")
                        else:
                            st.warning(f"⚠️ GTT partial: {gtt['message']}")
                        # Also log in Forward Testing for P&L tracking
                        ft_add_signal({
                            "symbol": sym, "side": preview["side"],
                            "entry": ltp, "sl": sl, "t1": t1, "t2": t2,
                            "rr1": preview.get("rr",2.0), "tf": preview.get("tf","—"),
                            "rationale": preview.get("strategy","Upstox Live Order"),
                            "strategy": preview.get("strategy","Upstox Live Order"),
                            "strength": preview.get("strength",0),
                        }, source=f"Upstox Live · {preview.get('tf','—')}")
                        # Track live order
                        lo = st.session_state.get("upstox_live_orders", [])
                        lo.append({"order_id": res["order_id"],
                                   "gtt_ids": gtt.get("gtt_ids",[]),
                                   "symbol": sym, "side": preview["side"],
                                   "qty": qty, "entry": ltp, "sl": sl, "t1": t1, "t2": t2,
                                   "placed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   "status": "OPEN"})
                        st.session_state["upstox_live_orders"] = lo
                        st.session_state.pop("upstox_order_preview", None)
                        st.rerun()
                    else:
                        st.error(f"❌ Order failed: {res['message']}")
        with cf2:
            if st.button("❌ Cancel", key=f"cancel_{sym}", use_container_width=True):
                st.session_state.pop("upstox_order_preview", None)
                st.rerun()


    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  UPSTOX ORDER EXECUTION ENGINE
#  SEBI-Compliant Design:
#  • All orders are USER-INITIATED (you click Place Order)
#  • No fully automated unattended execution
#  • Every order logged with timestamp, order_id, status
#  • SL and Target placed as GTT (Good Till Trigger) orders after entry
#  • 2FA token (access token) required — rotated daily by user
#  • Intended for PERSONAL account trading only
# ══════════════════════════════════════════════════════════════════════════════

UPSTOX_HFT_BASE = "https://api-hft.upstox.com/v2"   # Order placement endpoint
UPSTOX_GTT_BASE = "https://api.upstox.com/v2"        # GTT orders endpoint



def upstox_place_gtt_sl_target(
    symbol:  str,
    side:    str,    # original trade side (BUY/SELL) — GTT is reverse
    qty:     int,
    sl:      float,
    target:  float,
) -> dict:
    """
    Place GTT (Good Till Trigger) bracket for SL + Target after entry fill.
    GTT order auto-triggers when price hits SL or Target.
    SEBI-compliant: GTT orders are exchange-resident, not algo-generated.
    Returns {"success": bool, "gtt_id": str, "message": str}
    """
    if not _upstox_connected():
        return {"success": False, "gtt_id": "", "message": "Upstox not connected."}

    instrument_key = _upstox_instrument_key(symbol)
    exit_side      = "SELL" if side.upper() == "BUY" else "BUY"

    # GTT OCO (One-Cancels-Other): SL leg + Target leg
    payload = {
        "type": "MULTI",           # OCO — one cancels other
        "quantity": qty,
        "product":  "I",           # Intraday
        "instrument_token": instrument_key,
        "gt_legs": [
            {
                "trigger_type":    "rising" if exit_side == "BUY" else "falling",
                "transaction_type": exit_side,
                "quantity":        qty,
                "order_type":      "LIMIT",
                "price":           round(target, 2),
                "trigger_price":   round(target * 0.9995, 2),
            },
            {
                "trigger_type":    "falling" if exit_side == "SELL" else "rising",
                "transaction_type": exit_side,
                "quantity":        qty,
                "order_type":      "SL-M",
                "price":           round(sl * (0.995 if exit_side == "SELL" else 1.005), 2),
                "trigger_price":   round(sl, 2),
            },
        ],
    }
    try:
        r = requests.post(
            f"{UPSTOX_GTT_BASE}/gtt/place",
            headers=_upstox_headers(),
            json=payload,
            timeout=8,
        )
        data = r.json()
        if r.status_code == 200 and data.get("status") == "success":
            gtt_id = data.get("data", {}).get("id", "")
            return {"success": True, "gtt_id": gtt_id,
                    "message": f"GTT SL+Target set. ID: {gtt_id}"}
        else:
            err = data.get("errors", [{}])
            msg = err[0].get("message", str(data)) if err else str(data)
            return {"success": False, "gtt_id": "", "message": f"GTT Error: {msg}"}
    except Exception as e:
        return {"success": False, "gtt_id": "", "message": f"GTT request failed: {e}"}


def upstox_get_orders_today() -> list:
    """Fetch today's order list from Upstox."""
    try:
        r = requests.get(
            f"{UPSTOX_BASE}/order/retrieve-all",
            headers=_upstox_headers(),
            timeout=6,
        )
        if r.status_code == 200:
            return r.json().get("data", [])
    except Exception:
        pass
    return []


def upstox_cancel_order(order_id: str) -> dict:
    """Cancel a pending order."""
    try:
        r = requests.delete(
            f"{UPSTOX_HFT_BASE}/order/cancel",
            headers=_upstox_headers(),
            params={"order_id": order_id},
            timeout=6,
        )
        data = r.json()
        if r.status_code == 200 and data.get("status") == "success":
            return {"success": True, "message": f"Order {order_id} cancelled."}
        return {"success": False, "message": str(data.get("errors","Cancel failed"))}
    except Exception as e:
        return {"success": False, "message": str(e)}



def upstox_exit_all_positions() -> dict:
    """Exit all open positions (EOD cleanup)."""
    try:
        r = requests.post(
            f"{UPSTOX_HFT_BASE}/order/positions/exit",
            headers=_upstox_headers(),
            timeout=8,
        )
        data = r.json()
        if r.status_code == 200:
            return {"success": True, "message": "All positions exit triggered."}
        return {"success": False, "message": str(data)}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── Order log in session state ─────────────────────────────────────────────

def _order_log_add(entry: dict):
    """Add an order event to session-based order log."""
    if "upstox_order_log" not in st.session_state:
        st.session_state["upstox_order_log"] = []
    entry["logged_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["upstox_order_log"].insert(0, entry)
    # Keep last 100 orders in memory
    st.session_state["upstox_order_log"] = st.session_state["upstox_order_log"][:100]


def page_order_execution():
    """
    Upstox Live Order Execution — SEBI-compliant, user-initiated.
    You review the signal, set params, click Place Order.
    SL + Target auto-placed as GTT after fill confirmation.
    """
    st.markdown("""
    <div class="title-bar">
        <span style="font-size:1.4rem;">⚡</span>
        <h1>Live Order Execution</h1>
        <span style="margin-left:auto;background:#eeedfe;border:1px solid #afa9ec;
                     color:#3c3489;padding:3px 12px;border-radius:20px;
                     font-family:DM Mono,monospace;font-size:0.7rem;font-weight:700;">
            UPSTOX · SEBI COMPLIANT · USER-INITIATED
        </span>
    </div>""", unsafe_allow_html=True)

    # SEBI disclaimer — mandatory display
    st.markdown("""
    <div style="background:#fdf3d4;border:2px solid #e0c060;border-radius:10px;
                padding:0.85rem 1.1rem;margin-bottom:1rem;
                font-family:DM Mono,monospace;font-size:0.75rem;color:#5a3e00;">
    <b>⚖️ SEBI Compliance Notice</b><br>
    This tool places orders on your <b>personal Upstox account only</b> via their official API.<br>
    • All orders are <b>user-initiated</b> — you review and click Place Order manually.<br>
    • This is a <b>white-box strategy tool</b> for your own account. Do not share access with others.<br>
    • Algo trading for others requires SEBI Research Analyst registration + exchange empanelment.<br>
    • Ensure your static IP is registered with Upstox per SEBI Feb 2025 circular.<br>
    • PivotVault AI is not a SEBI-registered entity. Use at your own discretion.
    </div>""", unsafe_allow_html=True)

    # Connection check
    if not _upstox_connected():
        st.error("⚠️ Upstox not connected. Go to ⚙️ Broker Settings and add your daily access token.")
        if st.button("→ Go to Broker Settings", key="oe_goto_broker"):
            st.session_state["current_page"] = "Broker Settings"
            st.rerun()
        return

    st.success("✅ Upstox connected — orders will execute on your live account.")

    mkt_open = is_market_open()
    from datetime import timezone as _tzoe
    IST_oe = _tzoe(timedelta(hours=5, minutes=30))
    now_oe = datetime.now(IST_oe)

    if not mkt_open:
        wday = now_oe.weekday()
        if now_oe.hour >= 15 and now_oe.minute >= 30:
            st.warning("🔴 Market closed for today. AMO (After Market Orders) can be placed for next session.")
        else:
            st.warning("🟡 Market not open yet. AMO orders can be placed — will execute at market open.")

    # ══════════════════════════════════════════════════════════════
    #  SECTION 1 — PLACE NEW ORDER
    # ══════════════════════════════════════════════════════════════
    st.markdown("### 📋 Place Order")

    # Pre-fill from pending signal if available
    pending = st.session_state.pop("oe_pending_signal", None)

    # Show available margin if connected
    if _upstox_connected():
        funds = upstox_get_funds()
        avail = funds.get("available", 0)
        if avail > 0:
            st.markdown(
                f"<div style='background:#e4f5e8;border:1px solid #8dcc9a;"
                f"border-radius:7px;padding:6px 14px;margin-bottom:0.75rem;"
                f"font-family:DM Mono,monospace;font-size:0.78rem;color:#1a6b2e;'>"
                f"💰 Available Margin: <b>₹{avail:,.2f}</b> · "
                f"Used: ₹{funds.get('used',0):,.2f} · "
                f"Total: ₹{funds.get('total',0):,.2f}</div>",
                unsafe_allow_html=True,
            )

    oc1, oc2, oc3 = st.columns(3)
    with oc1:
        sym  = st.text_input("Symbol (NSE)",
                              value=pending["symbol"] if pending else "RELIANCE",
                              key="oe_sym").upper().strip()
        side = st.radio("Direction", ["BUY","SELL"], horizontal=True,
                        index=0 if (not pending or pending.get("side")=="BUY") else 1,
                        key="oe_side")
        product = st.radio("Product", ["I — Intraday (MIS)","D — Delivery (CNC)"],
                           horizontal=True, key="oe_product")
        prod_code = "I" if product.startswith("I") else "D"

    with oc2:
        try:   live_px = _ft_get_ltp(sym)
        except: live_px = 0.0
        entry_px = st.number_input("Entry Price ₹",
                                    value=float(pending["entry"] if pending else live_px or 100.0),
                                    step=0.25, key="oe_entry")
        order_type = st.radio("Order Type", ["MARKET","LIMIT"], horizontal=True, key="oe_otype")
        qty = st.number_input("Quantity", value=100, min_value=1, step=1, key="oe_qty")

    with oc3:
        sl     = st.number_input("Stop Loss ₹",
                                  value=float(pending["sl"] if pending else
                                              round(entry_px*(0.98 if side=="BUY" else 1.02),2)),
                                  step=0.25, key="oe_sl")
        target = st.number_input("Target 1 ₹ (GTT)",
                                  value=float(pending["t1"] if pending else
                                              round(entry_px*(1.03 if side=="BUY" else 0.97),2)),
                                  step=0.25, key="oe_t1")
        t2     = st.number_input("Target 2 ₹ (GTT T2)",
                                  value=float(pending.get("t2",
                                              round(entry_px*(1.06 if side=="BUY" else 0.94),2))
                                              if pending else
                                              round(entry_px*(1.06 if side=="BUY" else 0.94),2)),
                                  step=0.25, key="oe_t2")

    # Risk metrics
    risk    = max(abs(entry_px - sl), 0.01)
    reward  = abs(target - entry_px)
    rr      = round(reward/risk, 2)
    max_loss= round(risk * qty, 2)
    max_gain= round(reward * qty, 2)
    rr_color= "#1a6b2e" if rr >= 2 else ("#b8860b" if rr >= 1.5 else "#9e2018")

    st.markdown(
        f"<div style='background:#f5f8ed;border:1.5px solid #b8c89a;border-radius:9px;"
        f"padding:0.65rem 1rem;font-family:DM Mono,monospace;font-size:0.8rem;"
        f"display:flex;flex-wrap:wrap;gap:1.5rem;align-items:center;'>"
        f"<span>Qty: <b>{qty}</b></span>"
        f"<span>Value: <b>₹{entry_px*qty:,.0f}</b></span>"
        f"<span>Max Loss: <b style='color:#9e2018;'>₹{max_loss:,.2f}</b></span>"
        f"<span>Max Gain T1: <b style='color:#1a6b2e;'>₹{max_gain:,.2f}</b></span>"
        f"<span>R:R: <b style='color:{rr_color};'>{rr}:1</b></span>"
        f"<span style='margin-left:auto;font-size:0.72rem;color:#4a5e32;'>"
        f"LTP: ₹{live_px:,.2f}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Send this signal to Live Order Execution
    if _upstox_connected():
        if st.button(f"⚡ Place Order — {sym}",
                     key=f"oe_place_{sym}_{side}",
                     use_container_width=True):
            pass  # handled by PLACE ORDER button below

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # GTT option
    place_gtt = st.checkbox(
        "🔒 Auto-place GTT (SL + Target) after order fill",
        value=True, key="oe_gtt",
        help="Recommended: Places SL and Target as exchange-resident GTT orders automatically after your entry fills."
    )

    # PLACE ORDER BUTTON — explicit user action
    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns([2,1,1])
    with col_btn1:
        place_clicked = st.button(
            f"⚡ PLACE {'MARKET' if order_type=='MARKET' else 'LIMIT'} ORDER — "
            f"{side} {qty}× {sym}",
            key="oe_place_btn",
            use_container_width=True,
            type="primary",
        )
    with col_btn2:
        if st.button("🔄 Refresh LTP", key="oe_refresh_ltp", use_container_width=True):
            st.rerun()
    with col_btn3:
        is_amo = not mkt_open

    if place_clicked:
        if not sym:
            st.error("Enter a symbol.")
        elif qty < 1:
            st.error("Quantity must be at least 1.")
        else:
            with st.spinner(f"Placing {order_type} {side} order for {qty}× {sym}..."):
                result = upstox_place_order(
                    symbol=sym, side=side, qty=qty,
                    order_type=order_type,
                    price=entry_px if order_type=="LIMIT" else 0.0,
                    product=prod_code,
                    tag="PivotVaultAI-Signal",
                )

            if result["success"]:
                order_id = result["order_id"]
                st.success(f"✅ Order placed! Order ID: {order_id}")

                # Log to order log
                _order_log_add({
                    "order_id":   order_id,
                    "symbol":     sym,
                    "side":       side,
                    "qty":        qty,
                    "order_type": order_type,
                    "price":      entry_px,
                    "sl":         sl,
                    "target":     target,
                    "t2":         t2,
                    "product":    prod_code,
                    "status":     "PLACED",
                    "gtt_id":     "",
                    "source":     pending.get("source","Manual") if pending else "Manual",
                    "strategy":   pending.get("strategy","") if pending else "",
                })

                # Place GTT if checked
                if place_gtt:
                    with st.spinner("Setting GTT SL + Target..."):
                        gtt_result = upstox_place_gtt_sl_target(
                            symbol=sym, side=side, qty=qty,
                            sl=sl, target=target,
                        )
                    if gtt_result["success"]:
                        # Update log with GTT ID
                        log = st.session_state.get("upstox_order_log", [])
                        if log:
                            log[0]["gtt_id"] = gtt_result["gtt_id"]
                            log[0]["status"] = "PLACED + GTT SET"
                        st.success(f"🔒 GTT SL+Target set. GTT ID: {gtt_result['gtt_id']}")
                    else:
                        st.warning(f"⚠️ Order placed but GTT failed: {gtt_result['message']}")
            else:
                st.error(f"❌ Order failed: {result['message']}")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  SECTION 2 — TODAY'S ORDERS FROM UPSTOX
    # ══════════════════════════════════════════════════════════════
    st.markdown("### 📋 Today's Orders (from Upstox)")
    c_fetch, c_exit = st.columns([2,1])
    with c_fetch:
        if st.button("🔄 Fetch Live Orders", key="oe_fetch_orders", use_container_width=True):
            with st.spinner("Fetching orders..."):
                orders = upstox_get_orders_today()
            st.session_state["oe_live_orders"] = orders

    with c_exit:
        if st.button("🚨 Exit ALL Positions", key="oe_exit_all", use_container_width=True,
                     help="Emergency exit — closes all open intraday positions"):
            if st.session_state.get("oe_confirm_exit"):
                with st.spinner("Exiting all positions..."):
                    res = upstox_exit_all_positions()
                st.session_state["oe_confirm_exit"] = False
                if res["success"]:
                    st.success("✅ Exit all triggered successfully.")
                else:
                    st.error(f"❌ {res['message']}")
            else:
                st.session_state["oe_confirm_exit"] = True
                st.warning("⚠️ Click again to confirm EXIT ALL positions.")

    live_orders = st.session_state.get("oe_live_orders", [])
    if live_orders:
        rows = []
        for o in live_orders:
            rows.append({
                "Order ID":     o.get("order_id",""),
                "Symbol":       o.get("trading_symbol",""),
                "Side":         o.get("transaction_type",""),
                "Qty":          o.get("quantity",0),
                "Type":         o.get("order_type",""),
                "Price":        f"₹{o.get('price',0):,.2f}",
                "Avg Price":    f"₹{o.get('average_price',0):,.2f}",
                "Status":       o.get("status",""),
                "Time":         o.get("order_timestamp",""),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True, height=250)

        # Cancel individual order
        st.markdown("**Cancel a pending order:**")
        cancel_id = st.text_input("Order ID to cancel", key="oe_cancel_id",
                                   placeholder="Enter Order ID from table above")
        if st.button("❌ Cancel Order", key="oe_cancel_btn") and cancel_id:
            res = upstox_cancel_order(cancel_id.strip())
            if res["success"]:
                st.success(res["message"])
            else:
                st.error(res["message"])
    else:
        st.info("Click 'Fetch Live Orders' to see today's orders from Upstox.")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  SECTION 3 — ORDER LOG (this session)
    # ══════════════════════════════════════════════════════════════
    order_log = st.session_state.get("upstox_order_log", [])
    st.markdown(f"### 📝 Session Order Log ({len(order_log)})")

    if not order_log:
        st.info("Orders placed this session will appear here with Order ID, GTT ID, and status.")
    else:
        for o in order_log:
            s_color = "#1a6b2e" if o["side"]=="BUY" else "#9e2018"
            st.markdown(
                f"<div style='background:#fff;border:1.5px solid #b8c89a;"
                f"border-left:4px solid {s_color};border-radius:9px;"
                f"padding:0.65rem 1rem;margin-bottom:0.4rem;"
                f"font-family:DM Mono,monospace;font-size:0.76rem;'>"
                f"<div style='display:flex;flex-wrap:wrap;gap:10px;align-items:center;'>"
                f"<span style='background:{s_color};color:#fff;border-radius:4px;"
                f"padding:1px 8px;font-weight:700;font-size:0.7rem;'>{o['side']}</span>"
                f"<b style='color:#0e1308;'>{o['symbol']}</b>"
                f"<span>{o['qty']}× @ ₹{o['price']:,.2f} ({o['order_type']})</span>"
                f"<span style='color:#4a5e32;'>SL ₹{o['sl']:,.2f} · T1 ₹{o['target']:,.2f}</span>"
                f"<span style='background:#e4f0d0;color:#1e5c0a;border-radius:4px;"
                f"padding:1px 7px;font-size:0.68rem;'>{o['status']}</span>"
                f"<span style='margin-left:auto;color:#8a9a78;font-size:0.68rem;'>{o['logged_at']}</span>"
                f"</div>"
                f"<div style='color:#6a7a58;font-size:0.68rem;margin-top:3px;'>"
                f"Order ID: {o['order_id']} "
                f"{'· GTT: ' + o['gtt_id'] if o.get('gtt_id') else ''} "
                f"{'· ' + o['strategy'][:35] if o.get('strategy') else ''}"
                f"</div></div>",
                unsafe_allow_html=True,
            )

    st.divider()
    st.caption(
        "⚖️ SEBI Note: This tool is for personal account use only. "
        "Automated unattended trading requires exchange-registered algo ID. "
        "All orders are user-initiated via explicit button click. "
        "Static IP must be registered with Upstox. See SEBI Circular Feb 2025."
    )


def page_broker_settings():
    st.markdown("""
    <div class="title-bar">
        <span style="font-size:1.5rem;">⚙️</span>
        <h1>Broker & Data Feed Settings</h1>
    </div>
    """, unsafe_allow_html=True)

    # ── DATA FEED STATUS ──────────────────────────────────────────────────
    upstox_ok = _upstox_connected()
    st.markdown(
        f"<div style='background:{'#e4f5e8' if upstox_ok else '#fdf3d4'};"
        f"border:1.5px solid {'#8dcc9a' if upstox_ok else '#e0c060'};"
        f"border-radius:10px;padding:0.85rem 1.1rem;margin-bottom:1.25rem;"
        f"font-family:DM Mono,monospace;font-size:0.82rem;'>"
        f"<b>{'✅ Upstox Live Data Feed ACTIVE' if upstox_ok else '⚪ Live Data Feed: Not connected (using yfinance)'}</b><br>"
        f"<span style='color:#4a5e32;font-size:0.75rem;'>"
        f"{'All market data (indices, charts, scanner) now uses Upstox real-time feed' if upstox_ok else 'Connect Upstox below for free NSE real-time data'}"
        f"</span></div>",
        unsafe_allow_html=True,
    )

    tab_upstox, tab_zerodha, tab_groww, tab_telegram = st.tabs(["📡 Upstox (Data + Trading)", "⚡ Zerodha Kite", "🟢 Groww", "📨 Telegram"])

    # ══════════════════════════════
    #  UPSTOX — Data Feed + Trading
    # ══════════════════════════════
    with tab_upstox:
        st.markdown("### 📡 Upstox — Live Data + Order Execution")

        # ── Overall status ────────────────────────────────────────────────
        has_creds     = _upstox_has_credentials()
        token_ok      = _upstox_connected()
        token_expired = _upstox_token_expired()

        if token_ok and not token_expired:
            st.success("✅ Upstox ACTIVE — live data feed and order execution enabled.")
        elif has_creds:
            st.warning("⚠️ Credentials saved. Daily access token needs refresh — paste below.")
        else:
            st.info("📡 Set up Upstox once to enable live NSE data. Only the access token needs daily refresh.")

        st.divider()

        # ── STEP 1: API Key + Secret (permanent) ─────────────────────────
        st.markdown("#### Step 1 — API Credentials *(save once, permanent)*")
        st.caption("Get from upstox.com/developer → My Apps. These never expire.")

        if has_creds:
            st.markdown(
                "<div style='background:#e4f5e8;border:1px solid #8dcc9a;"
                "border-radius:7px;padding:6px 12px;margin-bottom:0.5rem;"
                "font-family:DM Mono,monospace;font-size:0.75rem;color:#1a6b2e;'>"
                "🔐 API Key & Secret are saved permanently</div>",
                unsafe_allow_html=True,
            )

        c1, c2 = st.columns(2)
        with c1:
            uak  = st.text_input("API Key",
                value=st.session_state.get("upstox_api_key",""),
                key="up_ak", type="password", placeholder="your-api-key")
        with c2:
            uaks = st.text_input("API Secret",
                value=st.session_state.get("upstox_api_secret",""),
                key="up_aks", type="password", placeholder="your-api-secret")

        if st.button("💾 Save API Key & Secret Permanently",
                     key="save_up_creds", use_container_width=True):
            k = uak.strip(); s = uaks.strip()
            if not k or not s:
                st.warning("Enter both API Key and API Secret.")
            else:
                st.session_state["upstox_api_key"]    = k
                st.session_state["upstox_api_secret"] = s
                st.session_state["broker"]            = "upstox"
                _save_credentials()
                st.success("✅ API Key & Secret saved permanently.")
                st.rerun()

        st.divider()

        # ── STEP 2: Daily Access Token ────────────────────────────────────
        st.markdown("#### Step 2 — Daily Access Token *(refresh every morning)*")
        st.caption("Upstox tokens expire daily. Paste fresh token here each morning.")

        uat = st.text_input(
            "Access Token",
            value=st.session_state.get("upstox_access_token",""),
            key="up_at", type="password",
            placeholder="eyJ0eXAiOiJKV1QiLCJhbGci...",
            label_visibility="collapsed",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚡ Activate Token", key="save_up_token",
                         use_container_width=True):
                t = uat.strip()
                if not t:
                    st.warning("Paste your access token first.")
                elif len(t) < 20:
                    st.error("❌ Invalid token — too short. Paste the full access token from Upstox.")
                else:
                    st.session_state.update({
                        "upstox_access_token":  t,
                        "upstox_api_key":       uak.strip() or st.session_state.get("upstox_api_key",""),
                        "upstox_api_secret":    uaks.strip() or st.session_state.get("upstox_api_secret",""),
                        "broker":               "upstox",
                        "broker_connected":     True,
                        "upstox_token_expired": False,
                    })
                    _save_session()
                    _save_credentials()
                    st.cache_data.clear()
                    st.success(f"✅ Token activated ({len(t)} chars) — Upstox live feed is ON.")
                    st.rerun()
        with col2:
            if token_ok:
                if st.button("🔌 Revoke Token", key="btn_disconnect_up",
                             use_container_width=True):
                    st.session_state.update({
                        "upstox_access_token": "",
                        "broker_connected":    False,
                    })
                    _save_credentials()
                    st.cache_data.clear()
                    st.info("Token revoked. API Key & Secret still saved.")
                    st.rerun()

        st.divider()

        # ── STEP 3: Generate Token via OAuth ─────────────────────────────
        st.markdown("#### Step 3 — Generate Token via OAuth *(each morning)*")
        st.caption("Use this each morning to get a fresh access token. Takes 30 seconds.")

        api_key_for_oauth = uak.strip() or st.session_state.get("upstox_api_key","")
        if not api_key_for_oauth:
            st.warning("Enter your API Key in Step 1 first.")
        else:
            redir_choice = st.radio(
                "Redirect URI", ["http://localhost:8501","http://127.0.0.1:8501",
                                  "https://127.0.0.1","Custom"],
                horizontal=True, key="redir_choice",
            )
            redir_uri = st.text_input("Custom URI", key="redir_custom") if redir_choice == "Custom" else redir_choice
            import urllib.parse as _up
            auth_url = (f"https://api.upstox.com/v2/login/authorization/dialog"
                        f"?response_type=code&client_id={_up.quote(api_key_for_oauth)}"
                        f"&redirect_uri={_up.quote(redir_uri)}")
            st.markdown(f"**Step A:** [Click to authorise on Upstox ↗]({auth_url})")
            st.caption("After authorizing, Upstox redirects to your URI with a `code=` parameter in the URL.")

            auth_code = st.text_input("Step B — Paste code from redirect URL",
                key="up_auth_code", placeholder="abc123xyz...")

            if st.button("🔑 Step C — Generate Access Token", key="gen_token_btn",
                         use_container_width=True):
                code = auth_code.strip()
                if not code:
                    st.warning("Paste the authorization code from Step B.")
                else:
                    try:
                        api_sec = uaks.strip() or st.session_state.get("upstox_api_secret","")
                        import requests as _rq
                        resp = _rq.post(
                            "https://api.upstox.com/v2/login/authorization/token",
                            data={"code": code, "client_id": api_key_for_oauth,
                                  "client_secret": api_sec, "redirect_uri": redir_uri,
                                  "grant_type": "authorization_code"},
                            headers={"accept":"application/json","Content-Type":"application/x-www-form-urlencoded"},
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            tok = resp.json().get("access_token","")
                            if tok:
                                st.session_state.update({
                                    "upstox_access_token": tok,
                                    "broker": "upstox",
                                    "broker_connected": True,
                                    "upstox_token_expired": False,
                                })
                                _save_session()
                                _save_credentials()
                                st.cache_data.clear()
                                st.success(f"✅ Access token generated! ({len(tok)} chars) — Live feed ACTIVE.")
                                st.rerun()
                            else:
                                st.error("Token generation succeeded but token was empty.")
                        else:
                            st.error(f"Token generation failed ({resp.status_code}): {resp.text[:200]}")
                    except Exception as e:
                        st.error(f"Error: {str(e)[:150]}")

    with tab_zerodha:
        st.markdown("### ⚡ Zerodha Kite")
        st.info("📋 Go to kite.zerodha.com/apps → Create app → Copy API Key & Secret. Access token regenerates daily after login.")
        c1, c2 = st.columns(2)
        with c1:
            zak  = st.text_input("API Key",    value=st.session_state.get("zerodha_api_key",""),    key="zk_ak",  type="password")
        with c2:
            zaks = st.text_input("API Secret", value=st.session_state.get("zerodha_api_secret",""), key="zk_aks", type="password")
        zat  = st.text_input("Access Token",   value=st.session_state.get("zerodha_access_token",""), key="zk_at", type="password")
        if st.button("💾 Save Zerodha Config", use_container_width=True, key="save_zk"):
            st.session_state.update({"zerodha_api_key":zak,"zerodha_api_secret":zaks,
                                     "zerodha_access_token":zat,"broker":"zerodha",
                                     "broker_connected": bool(zak and zat)})
            st.success("✅ Zerodha saved!" if zak and zat else "⚠️ Enter API key and access token.")
        st.markdown("""
        ```
        pip install kiteconnect
        ```
        """)

    # ══════════════════════════════
    #  GROWW
    # ══════════════════════════════
    with tab_groww:
        st.markdown("### 🟢 Groww")
        st.info("ℹ️ Groww does not have a public trading API. Signal cards open Groww web/app — you place the order manually (one tap).")
        if st.button("✅ Use Groww (web links)", use_container_width=True, key="set_groww"):
            st.session_state["broker"] = "groww"
            st.session_state["broker_connected"] = True
            st.success("Groww selected. Signal cards will link to Groww stock pages.")

    # ── Status summary ────────────────────────────────────────────────────

    with tab_telegram:
        st.markdown("### 📨 Telegram Notifications")
        st.markdown("<div style='background:#f0f4e8;border:1px solid #b8c89a;border-radius:8px;"
            "padding:0.8rem 1rem;font-family:DM Mono,monospace;font-size:0.78rem;color:#2e3d1a;margin-bottom:1rem;'>"
            "Instant alerts: ⚡ New signals &nbsp;·&nbsp; 🟢 Trade entry &nbsp;·&nbsp; 🎯 T1/T2 hit &nbsp;·&nbsp; 🛑 SL hit</div>",
            unsafe_allow_html=True)
        _tgs = st.session_state.get("telegram_cfg", {})
        with st.expander("📖 Setup Instructions", expanded=not _tgs.get("bot_token")):
            st.markdown("""
**Step 1** — Open Telegram → search **@BotFather** → `/newbot` → copy **Bot Token**
**Step 2** — Send any message to your bot → open `https://api.telegram.org/bot<TOKEN>/getUpdates` → find your **Chat ID**
**Step 3** — Paste below → Save → Test ✅""")
        st.divider()
        _c1,_c2 = st.columns(2)
        with _c1: _bt=st.text_input("🤖 Bot Token",value=_tgs.get("bot_token",""),type="password",placeholder="123456789:ABCdef...",key="tg_bt")
        with _c2: _ci=st.text_input("💬 Chat ID",value=_tgs.get("chat_id",""),placeholder="123456789",key="tg_ci")
        st.markdown("#### 🔔 Notification Toggles")
        _tc1,_tc2,_tc3,_tc4=st.columns(4)
        with _tc1: _ns=st.checkbox("📡 New Signals",value=_tgs.get("notify_signals",True),key="tg_ns")
        with _tc2: _ne=st.checkbox("⚡ Trade Entry",value=_tgs.get("notify_entry",True),key="tg_ne")
        with _tc3: _nt=st.checkbox("🎯 T1/T2 Hit",value=_tgs.get("notify_t1",True),key="tg_nt")
        with _tc4: _nl=st.checkbox("🛑 SL Hit",value=_tgs.get("notify_sl",True),key="tg_nl")
        st.markdown("")
        _b1,_b2,_b3=st.columns([2,2,1])
        with _b1:
            if st.button("💾 Save Settings",use_container_width=True,key="tg_save"):
                st.session_state["telegram_cfg"]={"bot_token":_bt.strip(),"chat_id":_ci.strip(),
                    "notify_signals":_ns,"notify_entry":_ne,"notify_t1":_nt,"notify_t2":_nt,"notify_sl":_nl}
                _save_credentials()  # persist to disk — survives refresh
                st.success("✅ Telegram settings saved & persisted! ✅")
        with _b2:
            if st.button("🧪 Send Test Message",use_container_width=True,key="tg_test"):
                # Use LIVE widget values (_bt/_ci) so test works without saving first
                import requests as _treq
                _test_ok = False
                if _bt.strip() and _ci.strip():
                    try:
                        _tr = _treq.post(
                            f"https://api.telegram.org/bot{_bt.strip()}/sendMessage",
                            json={"chat_id": _ci.strip(),
                                  "text": "🧪 <b>PivotVault AI — Test</b>\n━━━━━━━━━━━━━━━━━━━━\n🟢 <b>BUY RELIANCE</b> [15m]\n📌 Entry ₹2,850 · T1 ₹2,920 · SL ₹2,800\n✅ Telegram is working!",
                                  "parse_mode": "HTML"}, timeout=5)
                        _test_ok = _tr.status_code == 200
                    except Exception:
                        _test_ok = False
                if _test_ok:
                    st.success("✅ Sent! Check Telegram.")
                elif _bt.strip() and _ci.strip():
                    st.error("❌ Failed — check your Bot Token and Chat ID.")
                else:
                    st.error("❌ Enter Bot Token and Chat ID above first.")
        with _b3:
            if st.button("🗑 Clear",use_container_width=True,key="tg_clr"):
                st.session_state["telegram_cfg"]={};_save_credentials();st.rerun()
        st.divider()
        if _tgs.get("bot_token") and _tgs.get("chat_id"):
            st.markdown("<div style='background:#e4f5e8;border:1px solid #8dcc9a;border-radius:8px;padding:0.6rem 1rem;font-family:DM Mono,monospace;font-size:0.78rem;color:#1a6b2e;'>📨 <b>Telegram ACTIVE</b></div>",unsafe_allow_html=True)
        else:
            st.markdown("<div style='background:#fdf3d4;border:1px solid #e0c060;border-radius:8px;padding:0.6rem 1rem;font-family:DM Mono,monospace;font-size:0.78rem;color:#7a5800;'>⚪ <b>Telegram not configured</b> — add credentials above.</div>",unsafe_allow_html=True)

    st.divider()
    connected = st.session_state.get("broker_connected", False)
    bname     = st.session_state.get("broker","none").replace("upstox","Upstox").replace("zerodha","Zerodha").replace("groww","Groww").replace("none","None")
    up_active = _upstox_connected()
    st.markdown(
        f"<div style='padding:0.85rem 1.1rem;"
        f"background:{'#e4f5e8' if up_active else ('#fdf3d4' if connected else '#f5f8ed')};"
        f"border:1.5px solid {'#8dcc9a' if up_active else ('#e0c060' if connected else '#b8c89a')};"
        f"border-radius:10px;font-family:DM Mono,monospace;font-size:0.82rem;'>"
        f"{'📡 Data Feed: Upstox LIVE  ·  Trading: ' + bname if up_active else ('⚙️ Broker: ' + bname + ' (no live data feed)' if connected else '⚪ No broker connected')}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  FORWARD TESTING ENGINE
#  • Every CPR scanner signal auto-creates a FT position
#  • SL + Target checked live every 15s (Upstox) or on refresh (yfinance)
#  • All events logged: Entry, SL Hit, Target Hit, Manual Exit
#  • Full P&L statement strategy-wise at day end
# ══════════════════════════════════════════════════════════════════════════════

import json as _json, os as _os

# FT persistent storage — triple backup locations
_FT_FILE = _os.path.join(
    _os.path.dirname(_os.path.abspath(__file__)), "data", "pivotvault_ft.json"
)
_FT_FILE_HOME = _os.path.join(_os.path.expanduser("~"), ".pivotvault_ft.json")
_FT_FILE_TMP  = "/tmp/pivotvault_ft.json"

def _all_ft_paths():
    return [_FT_FILE, _FT_FILE_HOME, _FT_FILE_TMP]

# ── Persistence helpers ───────────────────────────────────────────────────

def _ft_load():
    """Load FT state — tries all 3 storage locations, returns freshest data."""
    best = None
    best_time = None
    for path in _all_ft_paths():
        try:
            if _os.path.exists(path):
                mtime = _os.path.getmtime(path)
                with open(path) as f:
                    d = _json.load(f)
                if d and isinstance(d, dict):
                    if best_time is None or mtime > best_time:
                        best = d
                        best_time = mtime
        except Exception:
            continue
    if best:
        if "positions" not in best: best["positions"] = []
        if "events"    not in best: best["events"]    = []
        if "balance"   not in best: best["balance"]   = 10000000.0
        if "starting"  not in best: best["starting"]  = 10000000.0
        return best
    _def_bal = st.session_state.get("_ft_default_balance", 10000000.0)
    return {"positions": [], "events": [], "balance": _def_bal, "starting": _def_bal}

def _ft_save(state: dict):
    """Save FT state to ALL 3 storage locations simultaneously."""
    payload = _json.dumps(state, indent=2, default=str)
    for path in _all_ft_paths():
        try:
            _os.makedirs(_os.path.dirname(_os.path.abspath(path)), exist_ok=True)
            with open(path, "w") as f:
                f.write(payload)
        except Exception:
            pass

def _ft_state():
    """Get FT state — reloads from disk if session was lost (e.g. server restart)."""
    if (not st.session_state.get("_ft_loaded") or
            not st.session_state.get("_ft") or
            not isinstance(st.session_state.get("_ft"), dict)):
        d = _ft_load()
        st.session_state["_ft"]        = d
        st.session_state["_ft_loaded"] = True
    return st.session_state["_ft"]

def _ft_flush():
    """Persist current FT state to disk — safe even if session key missing."""
    try:
        state = st.session_state.get("_ft")
        if state and isinstance(state, dict):
            _ft_save(state)
    except Exception:
        pass

# ── LTP fetch ────────────────────────────────────────────────────────────

def _ft_get_ltp(symbol: str) -> float:
    """
    Get LTP for forward testing.
    - Indian stocks : Upstox → yfinance (.NS suffix)
    - US stocks     : yfinance directly (no .NS suffix)
    """
    if is_us_symbol(symbol):
        try:
            fi = yf.Ticker(symbol).fast_info
            p  = float(getattr(fi, "last_price", 0) or 0)
            if p > 0: return round(p, 4)
            hist = yf.Ticker(symbol).history(period="1d", interval="1m")
            if not hist.empty:
                return round(float(hist["Close"].iloc[-1]), 4)
        except Exception:
            pass
        return 0.0
    # Try Upstox first
    ltp = upstox_get_ltp(symbol)
    if ltp > 0:
        return ltp

    # yfinance fallback for Indian stocks (.NS suffix)
    try:
        fi = yf.Ticker(symbol + ".NS").fast_info
        p  = float(getattr(fi, "last_price", 0) or 0)
        if p > 0: return round(p, 2)
        hist = yf.Ticker(symbol + ".NS").history(period="1d", interval="1m")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 0.0

# ── Signal auto-entry (called from scanner + signal tab) ─────────────────

def ft_add_signal(s: dict, source: str = "Scanner", manual: bool = False):
    """
    Add a signal as a Forward Test position.

    Rules:
    - manual=False (auto): only enters during 9:45–14:45 IST auto-trade window
    - manual=True:         enters during any market hours (9:15–15:30 IST)
    - Entry price = FIRST live tick from data feed at moment of signal
    - Never re-enters same symbol+side already OPEN or traded today
    - India EOD auto-close at 15:30 IST | US EOD at 16:00 EST/EDT
    """
    from datetime import timezone as _tz, time as _time

    # ── Detect market from signal symbol ─────────────────────────────────
    sym     = s.get("symbol", "")
    _us     = is_us_symbol(sym)
    _mkt    = "us" if _us else "india"

    # ── Market hours gate ─────────────────────────────────────────────────
    if manual:
        # Manual entries allowed any time market is open (9:15–15:30 IST)
        if not is_market_open(_mkt):
            return   # Market fully closed — skip
    else:
        # Auto entries: respect strict auto-trade window (9:45–14:45 IST)
        if not is_auto_trade_open(_mkt):
            return   # Outside auto-trade window — skip

    if _us:
        now_ref = _est_now()
    else:
        from datetime import timezone as _tz2
        now_ref = datetime.now(_tz2(timedelta(hours=5, minutes=30)))

    ft    = _ft_state()
    side  = s.get("side","BUY")
    today = now_ref.strftime("%Y-%m-%d")

    # ── Skip if already OPEN for this symbol+side ────────────────────────
    for p in ft["positions"]:
        if p["status"] in ("OPEN","T1 HIT — TRAILING") and            p["symbol"] == sym and p["side"] == side:
            return

    # ── Skip if already TRADED today for this symbol+side ────────────────
    # Prevents re-entering after SL hit or exit in same session
    traded_today = ft.get("traded_today", {})
    traded_key   = f"{today}:{sym}:{side}"
    if traded_key in traded_today:
        return

    # ── Get LIVE first tick from data feed ───────────────────────────────
    ltp = _ft_get_ltp(sym)
    if not ltp or ltp <= 0:
        return  # No live price — skip

    bal  = ft["balance"]
    # Dynamic position sizing: 5% of balance per trade (max 2% if 5% too large)
    qty  = max(1, int(bal * 0.05 / max(ltp, 1)))
    cost = round(ltp * qty, 2)
    if cost > bal:
        qty  = max(1, int(bal * 0.02 / max(ltp, 1)))
        cost = round(ltp * qty, 2)
    if cost > bal:
        st.session_state["ft_low_bal_alert"] = True
        return

    pos_id = len(ft["positions"]) + 1
    pos = {
        "id":         pos_id,
        "symbol":     sym,
        "side":       side,
        "entry":      ltp,              # FIRST live tick = entry price
        "qty":        qty,
        "sl":         s.get("sl",  round(ltp*(0.98 if side=="BUY" else 1.02), 2)),
        "target":     s.get("t1", round(ltp*(1.03 if side=="BUY" else 0.97), 2)),
        "t2":         s.get("t2", round(ltp*(1.06 if side=="BUY" else 0.94), 2)),
        "rr":         round(s.get("rr1", 2.0), 2),
        "cost":       cost,
        "status":     "OPEN",
        "ltp":        ltp,
        "upnl":       0.0,
        "pnl":        0.0,
        "pnl_pct":    0.0,
        "exit_px":    None,
        "exit_type":  None,
        "source":     source,
        "tf":         s.get("tf","—"),
        "strategy":   s.get("rationale", s.get("strategy","CPR"))[:60],
        "candle":     s.get("candle","—"),
        "strength":   s.get("strength", 0),
        "opened_at":  now_ref.strftime("%Y-%m-%d %H:%M:%S"),
        "closed_at":  None,
        "date":       today,
        "market":     _mkt,
        "currency":   "$" if _us else "₹",
    }
    ft["positions"].append(pos)
    ft["balance"] = round(bal - cost, 2)

    # Mark this symbol+side as traded today
    if "traded_today" not in ft:
        ft["traded_today"] = {}
    ft["traded_today"][traded_key] = now_ref.strftime("%H:%M:%S")

    # Log ENTRY event
    ft["events"].append({
        "time":     pos["opened_at"],
        "type":     "ENTRY",
        "id":       pos_id,
        "symbol":   sym,
        "side":     side,
        "price":    ltp,
        "qty":      qty,
        "sl":       pos["sl"],
        "target":   pos["target"],
        "rr":       pos["rr"],
        "source":   source,
        "strategy": pos["strategy"],
        "tf":       pos.get("tf","—"),
        "pnl":      0.0,
        "note":     f"First live tick entry @ {'$' if _us else '₹'}{ltp}",
    })
    _ft_flush()
    if st.session_state.get("telegram_cfg",{}).get("notify_entry",True):
        _send_telegram(_tg_trade_msg(pos,"ENTRY"))

# ── Trigger checker ───────────────────────────────────────────────────────

def _ft_auto_close_eod() -> list:
    """
    Auto-close ALL open positions at EOD:
    - India (NSE) : 15:30 IST
    - US (NYSE)   : 16:00 EST/EDT
    Called every trigger cycle — fires only once per day per market.
    Returns list of fired close events.
    """
    fired_all = []

    # ── India EOD @ 15:30 IST ────────────────────────────────────────────
    from datetime import timezone as _tz
    IST      = _tz(timedelta(hours=5, minutes=30))
    now_ist  = datetime.now(IST)
    today_in = now_ist.strftime("%Y-%m-%d")
    _ist_eod_due = (now_ist.weekday() < 5 and
                    (now_ist.hour > 15 or (now_ist.hour == 15 and now_ist.minute >= 30)))

    # ── US EOD @ 16:00 EST/EDT ───────────────────────────────────────────
    now_est   = _est_now()
    today_us  = now_est.strftime("%Y-%m-%d")
    _us_eod_due = (now_est.weekday() < 5 and
                   (now_est.hour >= 16))

    if not _ist_eod_due and not _us_eod_due:
        return []

    ft = _ft_state()

    # ── Helper: close one position ────────────────────────────────────────
    def _close_pos(pos, close_time, label, today_key):
        eod_key = f"eod_closed_{today_key}_{pos['id']}"
        if ft.get(eod_key): return None
        ltp = _ft_get_ltp(pos["symbol"])
        if not ltp or ltp <= 0: ltp = pos.get("ltp", pos["entry"])
        bull      = pos["side"] == "BUY"
        rem_qty   = pos.get("qty_remaining", pos["qty"])
        pnl       = round((ltp-pos["entry"])*rem_qty if bull else (pos["entry"]-ltp)*rem_qty, 2)
        total_pnl = round(pnl + pos.get("t1_pnl",0.0), 2)
        pnl_pct   = round(total_pnl / max(pos["cost"],1)*100, 2)
        rem_cost  = round(pos["cost"]*rem_qty / max(pos["qty"],1), 2)
        cur = pos.get("currency","₹")
        pos.update({"status":"EOD CLOSE","exit_px":ltp,"pnl":total_pnl,
                    "pnl_pct":pnl_pct,"upnl":0.0,"closed_at":close_time,
                    "exit_type":f"EOD {label} Auto-Close","qty_remaining":0})
        ft["balance"] = round(ft["balance"] + rem_cost + pnl, 2)
        ft["events"].append({"time":close_time,"type":"EOD AUTO-CLOSE",
            "id":pos["id"],"symbol":pos["symbol"],"side":pos["side"],
            "price":ltp,"entry":pos["entry"],"qty":rem_qty,"pnl":total_pnl,
            "pnl_pct":pnl_pct,"source":pos["source"],"strategy":pos["strategy"],
            "tf":pos.get("tf","—"),
            "note":f"Auto-closed at {label} @ {cur}{ltp}. T1 booked: {cur}{pos.get('t1_pnl',0)}"})
        ft[eod_key] = True
        return {"symbol":pos["symbol"],"hit":f"EOD AUTO-CLOSE @ {label}",
                "pnl":total_pnl,"strategy":pos["strategy"],"note":f"Closed @ {cur}{ltp}"}

    open_pos = [p for p in ft["positions"] if p["status"] in ("OPEN","T1 HIT — TRAILING")]

    if _ist_eod_due:
        close_time = now_ist.strftime("%Y-%m-%d %H:%M:%S")
        for pos in open_pos:
            if not is_us_symbol(pos["symbol"]):
                r = _close_pos(pos, close_time, "15:30 IST", today_in)
                if r: fired_all.append(r)

    if _us_eod_due:
        close_time = now_est.strftime("%Y-%m-%d %H:%M:%S")
        for pos in open_pos:
            if is_us_symbol(pos["symbol"]):
                r = _close_pos(pos, close_time, "16:00 EST", today_us)
                if r: fired_all.append(r)

    if fired_all:
        ft["traded_today"] = {}
        _ft_flush()

    # Legacy support — keep old today variable for callers
    today    = today_in
    now_ist  = now_ist  # keep in scope for callers

    if False:  # pragma: no cover — old pattern kept for reference
        return []

    ft       = _ft_state()
    fired    = []
    eod_key  = f"eod_closed_{today}"

    # Already closed today
    if ft.get(eod_key):
        return []

    open_positions = [p for p in ft["positions"]
                      if p["status"] in ("OPEN","T1 HIT — TRAILING")]
    if not open_positions:
        ft[eod_key] = True
        # Reset traded_today for tomorrow
        ft["traded_today"] = {}
        _ft_flush()
        return []

    close_time = now_ist.strftime("%Y-%m-%d %H:%M:%S")
    for pos in open_positions:
        ltp = _ft_get_ltp(pos["symbol"])
        if not ltp or ltp <= 0:
            ltp = pos.get("ltp", pos["entry"])  # fallback to last known

        bull    = pos["side"] == "BUY"
        rem_qty = pos.get("qty_remaining", pos["qty"])

        # Full position P&L (including any T1 partial already booked)
        pnl     = round((ltp - pos["entry"]) * rem_qty if bull
                        else (pos["entry"] - ltp) * rem_qty, 2)
        total_pnl = round(pnl + pos.get("t1_pnl", 0.0), 2)
        pnl_pct   = round(total_pnl / max(pos["cost"], 1) * 100, 2)
        rem_cost  = round(pos["cost"] * rem_qty / max(pos["qty"], 1), 2)

        pos.update({
            "status":    "EOD CLOSE",
            "exit_px":   ltp,
            "pnl":       total_pnl,
            "pnl_pct":   pnl_pct,
            "upnl":      0.0,
            "closed_at": close_time,
            "exit_type": "EOD 15:30 Auto-Close",
            "qty_remaining": 0,
        })
        ft["balance"] = round(ft["balance"] + rem_cost + pnl, 2)

        ft["events"].append({
            "time":     close_time,
            "type":     "EOD AUTO-CLOSE",
            "id":       pos["id"],
            "symbol":   pos["symbol"],
            "side":     pos["side"],
            "price":    ltp,
            "entry":    pos["entry"],
            "qty":      rem_qty,
            "pnl":      total_pnl,
            "pnl_pct":  pnl_pct,
            "source":   pos["source"],
            "strategy": pos["strategy"],
            "tf":       pos.get("tf","—"),
            "note":     f"Auto-closed at 15:30 IST @ ₹{ltp}. "
                        f"T1 booked: ₹{pos.get('t1_pnl',0)}",
        })
        fired.append({
            "symbol":   pos["symbol"],
            "hit":      "EOD AUTO-CLOSE @ 15:30",
            "pnl":      total_pnl,
            "strategy": pos["strategy"],
            "note":     f"Closed @ ₹{ltp}",
        })

    # Mark EOD done + reset daily tracking for tomorrow
    ft[eod_key]         = True
    ft["traded_today"]  = {}
    _ft_flush()
    return fired


def _ft_run_triggers() -> list:
    """
    Live trigger engine — checks every OPEN position against LTP.

    Flow each 15s cycle:
    1. Check 15:30 EOD auto-close first
    2. Stage 1 — T1 hit → partial exit + SL moves to entry (trailing breakeven)
    3. Stage 2 — T2 hit → remaining qty exits (full close)
    4. SL hit → full position closes

    Entry only from FIRST live tick during market hours (handled in ft_add_signal).
    """
    # ── EOD auto-close at 15:30 ──────────────────────────────────────────
    eod_fired = _ft_auto_close_eod()

    ft    = _ft_state()
    fired = list(eod_fired)

    for pos in ft["positions"]:
        if pos["status"] not in ("OPEN", "T1 HIT — TRAILING"): continue
        ltp = _ft_get_ltp(pos["symbol"])
        if not ltp: continue

        pos["ltp"] = ltp
        bull = pos["side"] == "BUY"
        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Update unrealised P&L ─────────────────────────────────────────
        if bull:
            pos["upnl"] = round((ltp - pos["entry"]) * pos.get("qty_remaining", pos["qty"]), 2)
        else:
            pos["upnl"] = round((pos["entry"] - ltp) * pos.get("qty_remaining", pos["qty"]), 2)

        # ── Stage 1: T1 hit (only if not already trailing) ────────────────
        if pos["status"] == "OPEN":
            t1_hit = (bull and ltp >= pos["target"]) or (not bull and ltp <= pos["target"])
            sl_hit = (bull and ltp <= pos["sl"])     or (not bull and ltp >= pos["sl"])

            if t1_hit:
                # Half qty exits at T1
                full_qty      = pos["qty"]
                exit_qty      = max(1, full_qty // 2)
                remaining_qty = full_qty - exit_qty
                t1_pnl        = round((pos["target"]-pos["entry"])*exit_qty if bull
                                      else (pos["entry"]-pos["target"])*exit_qty, 2)
                t1_pnl_pct    = round(t1_pnl / max(pos["cost"],1) * 100, 2)

                # Move SL to entry (trailing = breakeven)
                pos["sl_original"]   = pos["sl"]
                pos["sl"]            = pos["entry"]          # trailing SL = entry
                pos["status"]        = "T1 HIT — TRAILING"
                pos["qty_remaining"] = remaining_qty
                pos["t1_exit_qty"]   = exit_qty
                pos["t1_pnl"]        = t1_pnl
                pos["t1_pnl_pct"]    = t1_pnl_pct
                pos["t1_hit_at"]     = now
                # Balance: credit T1 partial exit
                t1_cost_freed = round(pos["cost"] * exit_qty / full_qty, 2)
                ft["balance"]  = round(ft["balance"] + t1_cost_freed + t1_pnl, 2)

                # Log T1 event
                ft["events"].append({
                    "time":     now,
                    "type":     "T1 HIT — PARTIAL EXIT",
                    "id":       pos["id"],
                    "symbol":   pos["symbol"],
                    "side":     pos["side"],
                    "price":    pos["target"],
                    "entry":    pos["entry"],
                    "qty":      exit_qty,
                    "pnl":      t1_pnl,
                    "pnl_pct":  t1_pnl_pct,
                    "source":   pos["source"],
                    "strategy": pos["strategy"],
                    "tf":       pos.get("tf","—"),
                    "note":     f"T1 partial. SL moved to entry ₹{pos['entry']}. Trailing to T2 ₹{pos.get('t2',0)}"
                })
                fired.append({
                    "symbol": pos["symbol"],
                    "hit":    "T1 HIT — Trailing to T2",
                    "pnl":    t1_pnl,
                    "strategy": pos["strategy"],
                    "note":   f"SL → ₹{pos['entry']} (entry). T2 target: ₹{pos.get('t2',0)}"
                })
                _ft_flush()
                continue  # Don't check SL this cycle

            elif sl_hit:
                # Full SL hit — close entire position
                exit_px = pos["sl"]
                pnl     = round((exit_px-pos["entry"])*pos["qty"] if bull
                                else (pos["entry"]-exit_px)*pos["qty"], 2)
                pnl_pct = round(pnl / max(pos["cost"],1) * 100, 2)
                pos.update({"status":"SL HIT","exit_px":exit_px,"pnl":pnl,
                            "pnl_pct":pnl_pct,"upnl":0.0,
                            "closed_at":now,"exit_type":"SL HIT",
                            "qty_remaining":0})
                ft["balance"] = round(ft["balance"] + pos["cost"] + pnl, 2)
                ft["events"].append({
                    "time":pos["closed_at"],"type":"SL HIT","id":pos["id"],
                    "symbol":pos["symbol"],"side":pos["side"],"price":exit_px,
                    "entry":pos["entry"],"qty":pos["qty"],"pnl":pnl,"pnl_pct":pnl_pct,
                    "source":pos["source"],"strategy":pos["strategy"],"tf":pos.get("tf","—"),
                    "note":"Full position SL hit"
                })
                fired.append({"symbol":pos["symbol"],"hit":"SL HIT","pnl":pnl,
                              "strategy":pos["strategy"],"note":f"Closed @ ₹{exit_px}"})

        # ── Stage 2: Trailing to T2 ───────────────────────────────────────
        elif pos["status"] == "T1 HIT — TRAILING":
            t2     = pos.get("t2", pos.get("target", 0))
            rem_qty= pos.get("qty_remaining", 1)
            t2_hit = (bull and ltp >= t2)      or (not bull and ltp <= t2)
            sl_hit = (bull and ltp <= pos["sl"]) or (not bull and ltp >= pos["sl"])

            if t2_hit:
                # Remaining qty exits at T2
                pnl     = round((t2-pos["entry"])*rem_qty if bull
                                else (pos["entry"]-t2)*rem_qty, 2)
                pnl_pct = round(pnl / max(pos["cost"],1) * 100, 2)
                total_pnl = round(pnl + pos.get("t1_pnl",0), 2)
                rem_cost  = round(pos["cost"] * rem_qty / pos["qty"], 2)
                pos.update({"status":"T2 HIT — FULL EXIT","exit_px":t2,
                            "pnl":total_pnl,"pnl_pct":round(total_pnl/max(pos["cost"],1)*100,2),
                            "upnl":0.0,"closed_at":now,"exit_type":"T2 HIT",
                            "qty_remaining":0})
                ft["balance"] = round(ft["balance"] + rem_cost + pnl, 2)
                ft["events"].append({
                    "time":now,"type":"T2 HIT — FULL EXIT","id":pos["id"],
                    "symbol":pos["symbol"],"side":pos["side"],"price":t2,
                    "entry":pos["entry"],"qty":rem_qty,"pnl":pnl,"pnl_pct":pnl_pct,
                    "source":pos["source"],"strategy":pos["strategy"],"tf":pos.get("tf","—"),
                    "note":f"T2 exit. Total trade P&L ₹{total_pnl} (T1 ₹{pos.get('t1_pnl',0)} + T2 ₹{pnl})"
                })
                fired.append({"symbol":pos["symbol"],"hit":"T2 HIT 🎯🎯",
                              "pnl":total_pnl,"strategy":pos["strategy"],
                              "note":f"Full exit @ ₹{t2}. Total P&L ₹{total_pnl}"})

            elif sl_hit:
                # Trailing SL hit (at entry = breakeven or better)
                exit_px = pos["sl"]
                pnl     = round((exit_px-pos["entry"])*rem_qty if bull
                                else (pos["entry"]-exit_px)*rem_qty, 2)
                total_pnl= round(pnl + pos.get("t1_pnl",0), 2)
                rem_cost = round(pos["cost"] * rem_qty / pos["qty"], 2)
                pos.update({"status":"TRAILING SL HIT","exit_px":exit_px,
                            "pnl":total_pnl,"pnl_pct":round(total_pnl/max(pos["cost"],1)*100,2),
                            "upnl":0.0,"closed_at":now,"exit_type":"Trailing SL",
                            "qty_remaining":0})
                ft["balance"] = round(ft["balance"] + rem_cost + pnl, 2)
                ft["events"].append({
                    "time":now,"type":"TRAILING SL HIT","id":pos["id"],
                    "symbol":pos["symbol"],"side":pos["side"],"price":exit_px,
                    "entry":pos["entry"],"qty":rem_qty,"pnl":pnl,"pnl_pct":pnl_pct,
                    "source":pos["source"],"strategy":pos["strategy"],"tf":pos.get("tf","—"),
                    "note":f"Trailing SL at entry. Total P&L ₹{total_pnl} (T1 ₹{pos.get('t1_pnl',0)} locked in)"
                })
                fired.append({"symbol":pos["symbol"],"hit":"TRAILING SL (breakeven)",
                              "pnl":total_pnl,"strategy":pos["strategy"],
                              "note":f"T1 profit ₹{pos.get('t1_pnl',0)} locked. Remaining at breakeven."})

    if fired:
        _ft_flush()
        _tg=st.session_state.get("telegram_cfg",{})
        for _ev in fired:
            _h=_ev.get("hit","");_s=_ev.get("symbol","");_p=_ev.get("pnl",0)
            _pe="✅" if _p>=0 else "❌";_st=_ev.get("strategy","");_nt=_ev.get("note","")
            if "T2 HIT" in _h and _tg.get("notify_t2",True): _send_telegram(f"🎯🎯 <b>T2 HIT — {_s}</b>\nP&L: {_pe} ₹{_p:,.2f}\n<i>{_st}</i>")
            elif "T1 HIT" in _h and _tg.get("notify_t1",True): _send_telegram(f"🎯 <b>T1 HIT — {_s}</b>\nP&L: {_pe} ₹{_p:,.2f}\n<i>{_st}</i>")
            elif "TRAILING" in _h and _tg.get("notify_sl",True): _send_telegram(f"🔒 <b>TRAILING SL — {_s}</b>\nP&L: {_pe} ₹{_p:,.2f}\n<i>{_st}</i>")
            elif "SL HIT" in _h and _tg.get("notify_sl",True): _send_telegram(f"🛑 <b>SL HIT — {_s}</b>\nP&L: {_pe} ₹{_p:,.2f}\n<i>{_st}</i>")
    return fired



# ══════════════════════════════════════════════════════════════════════════════
#  FORWARD TESTING PAGE
# ══════════════════════════════════════════════════════════════════════════════

def page_forward_test():
    """Forward Testing — auto-signal entry, live SL/Target, full P&L by strategy."""

    # Auto-refresh 15s during market hours
    if _HAS_AUTOREFRESH and is_market_open():
        st_autorefresh(interval=15_000, limit=None, key="ft_ar")

    # ── BUG FIX: Consume manual Fwd Test signal from Trade Signals / Scanner ──
    _pending = st.session_state.pop("ft_pending_signal", None)
    if _pending and _pending.get("symbol"):
        _sym = _pending.get("symbol","")
        # Try to get fresh live price
        try:
            _live = _ft_get_ltp(_sym)
            if _live and _live > 0:
                _pending["entry"] = _live
        except Exception:
            pass
        if _pending.get("entry", 0) > 0:
            ft_add_signal(
                _pending,
                source=f"🖐 Manual · {_pending.get('tf', _pending.get('source','—'))}",
                manual=True,   # bypass auto-trade window — user clicked manually
            )
            st.toast(f"🖐 Manual trade added: {_sym} {_pending.get('side','BUY')} "
                     f"@ ₹{_pending.get('entry',0):,.2f}", icon="✅")
        else:
            st.warning(f"⚠️ Could not get live price for {_sym}. "
                       f"Check Upstox connection or market hours.", icon="⚠️")

    # Run triggers on every render
    fired = _ft_run_triggers()
    for f in fired:
        icon = "🎯" if "T2" in f["hit"] else ("🎯" if "T1" in f["hit"] else "🛑")
        st.toast(f"{icon} {f['symbol']} — {f['hit']} | P&L ₹{f['pnl']:+,.2f}", icon=icon)

    ft       = _ft_state()
    positions= ft["positions"]
    events   = ft["events"]
    bal      = ft["balance"]
    starting = ft["starting"]
    IST      = __import__("datetime").timezone(__import__("datetime").timedelta(hours=5,minutes=30))
    today    = datetime.now(IST).strftime("%Y-%m-%d")

    open_pos  = [p for p in positions if p["status"] == "OPEN"]
    closed_pos= [p for p in positions if p["status"] != "OPEN"]
    today_cl  = [p for p in closed_pos if str(p.get("closed_at","")).startswith(today)]
    wins      = [p for p in closed_pos if p.get("pnl",0) > 0]
    losses    = [p for p in closed_pos if p.get("pnl",0) <= 0]
    total_pnl = round(sum(p.get("pnl",0) for p in closed_pos), 2)
    today_pnl = round(sum(p.get("pnl",0) for p in today_cl), 2)
    live_upnl = round(sum(p.get("upnl",0) for p in open_pos), 2)
    win_rate  = round(len(wins)/max(len(closed_pos),1)*100,1)

    # Low balance alert from auto-signal skip
    if st.session_state.pop("ft_low_bal_alert", False):
        st.warning("⚠️ Insufficient virtual balance — new signals were skipped. "
                   "Add virtual funds below to continue forward testing.",
                   icon="💰")

    mkt_open = is_market_open()
    data_src = "📡 Upstox Live" if _upstox_connected() else "📊 yfinance (delayed)"

    # ── PAGE HEADER ───────────────────────────────────────────────────────
    st.markdown("""
    <div class="title-bar">
        <span style="font-size:1.4rem;">🧪</span>
        <h1>Forward Testing Simulator</h1>
    </div>""", unsafe_allow_html=True)

    from datetime import timezone as _tz2
    _IST2    = _tz2(timedelta(hours=5, minutes=30))
    _now_ist = datetime.now(_IST2)
    _today   = _now_ist.strftime("%Y-%m-%d")
    _ft_data = _ft_state()
    _eod_done= _ft_data.get(f"eod_closed_{_today}", False)
    _traded  = len(_ft_data.get("traded_today", {}))

    if _eod_done:
        _status_msg = "🔴 EOD CLOSE executed — India 15:30 IST / US 16:00 EST · all positions closed"
        _status_bg  = "#fbe8e6"; _status_bdr = "#dc9090"; _status_col = "#9e2018"
    elif mkt_open:
        _status_msg = f"🟢 Market OPEN · {data_src} · Triggers every 15s · {_traded} symbol(s) traded today"
        _status_bg  = "#e4f5e8"; _status_bdr = "#8dcc9a"; _status_col = "#1a6b2e"
    else:
        _nxt = "Opens Monday 9:15 AM" if _now_ist.weekday()>=4 else "Opens tomorrow 9:15 AM"
        _status_msg = f"🟡 Market Closed · {_nxt} · Entry only on live market tick"
        _status_bg  = "#fdf3d4"; _status_bdr = "#e0c060"; _status_col = "#7a5800"

    st.markdown(
        f"<div style='font-family:DM Mono,monospace;font-size:0.75rem;"
        f"padding:7px 14px;border-radius:7px;margin-bottom:0.75rem;"
        f"background:{_status_bg};border:1px solid {_status_bdr};color:{_status_col};'>"
        f"{_status_msg}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════
    #  SECTION 1 — P&L REPORT (always at top)
    # ══════════════════════════════════════════════════════════════
    pnl_color = "#1a6b2e" if total_pnl >= 0 else "#9e2018"
    st.markdown(
        f"<div style='background:#1a1f0e;border-radius:12px;"
        f"padding:1rem 1.25rem;margin-bottom:1rem;'>"
        f"<div style='font-family:DM Mono,monospace;font-size:0.65rem;"
        f"color:#7da048;letter-spacing:0.1em;text-transform:uppercase;"
        f"margin-bottom:0.5rem;'>📊 Live P&L Statement</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("💰 Balance",      f"₹{bal:,.0f}",
              f"{'+'if(bal-starting)>=0 else ''}₹{(bal-starting):,.0f}")
    c2.metric("📈 Total P&L",    f"₹{total_pnl:+,.0f}",
              f"{round(total_pnl/max(starting,1)*100,1):+.1f}%")
    c3.metric("📅 Today P&L",    f"₹{today_pnl:+,.0f}",
              f"{len(today_cl)} trades today")
    c4.metric("✅ Win Rate",      f"{win_rate}%",
              f"{len(wins)}W / {len(losses)}L")
    c5.metric("🔄 Open",         len(open_pos),
              f"uPnL ₹{live_upnl:+,.0f}")
    c6.metric("📊 Total Trades", len(positions),
              f"{len(closed_pos)} closed")

    # Strategy P&L statement
    if closed_pos:
        st.markdown("#### 📋 P&L by Strategy")
        strat_map: dict = {}
        for p in closed_pos:
            key = f"{p.get('strategy','Unknown')[:35]} [{p.get('tf','—')}]"
            if key not in strat_map:
                strat_map[key] = {"trades":0,"wins":0,"pnl":0.0,
                                   "sl_hits":0,"tgt_hits":0,"max_win":0.0,"max_loss":0.0}
            sm = strat_map[key]
            sm["trades"] += 1
            sm["pnl"]    += p.get("pnl",0)
            if p.get("pnl",0) > 0:
                sm["wins"]    += 1
                sm["tgt_hits"]+= 1
                sm["max_win"]  = max(sm["max_win"], p.get("pnl",0))
            else:
                sm["sl_hits"] += 1
                sm["max_loss"] = min(sm["max_loss"], p.get("pnl",0))

        rows = []
        for strat, sm in sorted(strat_map.items(), key=lambda x: -x[1]["pnl"]):
            wr  = round(sm["wins"]/sm["trades"]*100)
            pf  = round(abs(sm["pnl"])/max(abs(sm["max_loss"]*sm["sl_hits"]),0.01),2)
            rows.append({
                "Strategy":      strat,
                "Trades":        sm["trades"],
                "Win %":         f"{wr}%",
                "🎯 Tgt Hits":   sm["tgt_hits"],
                "🛑 SL Hits":    sm["sl_hits"],
                "Net P&L":       f"₹{sm['pnl']:+,.2f}",
                "Best Trade":    f"₹{sm['max_win']:+,.2f}",
                "Worst Trade":   f"₹{sm['max_loss']:+,.2f}",
                "Profit Factor": f"{pf}x",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True, height=min(250, 60+len(rows)*40))

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  SECTION 2 — OPEN POSITIONS (live SL/Target monitor)
    # ══════════════════════════════════════════════════════════════
    st.markdown(f"#### ⚡ Open Positions ({len(open_pos)})")

    if not open_pos:
        st.info("No open positions. Signals from the CPR Scanner auto-appear here. "
                "Or add manually below.")
    else:
        for pos in open_pos:
            bull   = pos["side"] == "BUY"
            ltp    = pos.get("ltp", pos["entry"])
            upnl   = pos.get("upnl", 0.0)
            ac     = "#1a6b2e" if bull else "#9e2018"
            pnl_c  = "#1a6b2e" if upnl >= 0 else "#9e2018"
            # Progress: 0=at SL, 50=at entry, 100=at target
            risk   = max(abs(pos["entry"]-pos["sl"]), 0.01)
            move   = (ltp-pos["entry"]) if bull else (pos["entry"]-ltp)
            prog   = max(0, min(100, int(50 + move/risk*50)))
            prog_c = "#1a6b2e" if prog>60 else ("#b8860b" if prog>40 else "#9e2018")

            st.markdown(
                f"<div style='background:#fff;border:1.5px solid #b8c89a;"
                f"border-left:5px solid {ac};border-radius:10px;"
                f"padding:0.75rem 1rem;margin-bottom:0.5rem;'>"
                f"<div style='display:flex;flex-wrap:wrap;gap:8px;"
                f"align-items:center;margin-bottom:6px;'>"
                f"<b style='font-size:1rem;color:#0e1308;'>{pos['symbol']}</b>"
                f"<span style='background:{ac};color:#fff;border-radius:4px;"
                f"padding:1px 8px;font-size:0.72rem;font-weight:700;'>{pos['side']}</span>"
                f"<span style='font-family:DM Mono,monospace;font-size:0.73rem;color:#4a5e32;'>"
                f"{pos['qty']}× · Entry ₹{pos['entry']:,.2f} · LTP ₹{ltp:,.2f}</span>"
                f"<span style='font-family:DM Mono,monospace;font-size:0.82rem;"
                f"font-weight:700;color:{pnl_c};margin-left:auto;'>"
                f"uPnL ₹{upnl:+,.2f}</span></div>"
                f"<div style='display:grid;grid-template-columns:repeat(4,1fr);"
                f"gap:6px;margin-bottom:7px;font-family:DM Mono,monospace;"
                f"font-size:0.7rem;text-align:center;'>"
                f"<div style='background:#fbe8e6;border-radius:5px;padding:3px;'>"
                f"<div style='color:#9e2018;'>🛑 SL</div>"
                f"<b style='color:#9e2018;'>₹{pos['sl']:,.2f}</b></div>"
                f"<div style='background:#e4f5e8;border-radius:5px;padding:3px;'>"
                f"<div style='color:#1a6b2e;'>🎯 T1</div>"
                f"<b style='color:#1a6b2e;'>₹{pos['target']:,.2f}</b></div>"
                f"<div style='background:#f0f4e8;border-radius:5px;padding:3px;'>"
                f"<div style='color:#4a5e32;'>📈 T2</div>"
                f"<b>₹{pos.get('t2',pos['target']):,.2f}</b></div>"
                f"<div style='background:#f0f4e8;border-radius:5px;padding:3px;'>"
                f"<div style='color:#4a5e32;'>R:R</div>"
                f"<b>{pos.get('rr',0)}x</b></div></div>"
                f"<div style='background:#e8eddf;border-radius:4px;height:6px;"
                f"overflow:hidden;margin-bottom:3px;'>"
                f"<div style='background:{prog_c};width:{prog}%;height:100%;"
                f"border-radius:4px;'></div></div>"
                f"<div style='font-family:DM Mono,monospace;font-size:0.63rem;"
                f"color:#8a9a78;'>"
                f"📌 {pos.get('source','—')} · {pos.get('tf','—')} · "
                f"Opened {pos.get('opened_at','—')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            # Manual exit
            mc1, mc2, mc3 = st.columns([2,1,1])
            with mc1:
                ex_px = st.number_input("Manual exit ₹", value=float(ltp),
                                        step=0.25,
                                        key=f"ft_ex_{pos['id']}",
                                        label_visibility="collapsed")
            with mc2:
                if st.button("Exit @ T1 🎯", key=f"ft_t1_{pos['id']}",
                             use_container_width=True):
                    ex_px = pos["target"]
                    pnl   = round((ex_px-pos["entry"])*pos["qty"] if bull
                                  else (pos["entry"]-ex_px)*pos["qty"], 2)
                    pos.update({"status":"MANUAL EXIT","exit_px":ex_px,"pnl":pnl,
                                "pnl_pct":round(pnl/max(pos["cost"],1)*100,2),
                                "closed_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "exit_type":"Manual T1"})
                    ft["balance"] = round(ft["balance"]+pos["cost"]+pnl, 2)
                    ft["events"].append({"time":pos["closed_at"],"type":"MANUAL EXIT",
                        "id":pos["id"],"symbol":pos["symbol"],"side":pos["side"],
                        "price":ex_px,"entry":pos["entry"],"qty":pos["qty"],
                        "pnl":pnl,"pnl_pct":pos["pnl_pct"],
                        "source":pos["source"],"strategy":pos["strategy"],"tf":pos["tf"]})
                    _ft_flush(); st.rerun()
            with mc3:
                if st.button("Exit ₹ ↗", key=f"ft_mex_{pos['id']}",
                             use_container_width=True):
                    pnl = round((ex_px-pos["entry"])*pos["qty"] if bull
                                else (pos["entry"]-ex_px)*pos["qty"], 2)
                    pos.update({"status":"MANUAL EXIT","exit_px":ex_px,"pnl":pnl,
                                "pnl_pct":round(pnl/max(pos["cost"],1)*100,2),
                                "closed_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "exit_type":"Manual"})
                    ft["balance"] = round(ft["balance"]+pos["cost"]+pnl, 2)
                    ft["events"].append({"time":pos["closed_at"],"type":"MANUAL EXIT",
                        "id":pos["id"],"symbol":pos["symbol"],"side":pos["side"],
                        "price":ex_px,"entry":pos["entry"],"qty":pos["qty"],
                        "pnl":pnl,"pnl_pct":pos["pnl_pct"],
                        "source":pos["source"],"strategy":pos["strategy"],"tf":pos["tf"]})
                    _ft_flush(); st.rerun()

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  SECTION 3 — EVENT LOG (every entry/exit/trigger)
    # ══════════════════════════════════════════════════════════════
    st.markdown(f"#### ⚡ Event Log — All Triggers ({len(events)})")

    if not events:
        st.info("Events appear here automatically: ENTRY → SL HIT / TARGET HIT / MANUAL EXIT")
    else:
        # Quick stats
        ev_ent  = [e for e in events if e["type"] == "ENTRY"]
        ev_t1   = [e for e in events if e["type"] == "T1 HIT — PARTIAL EXIT"]
        ev_t2   = [e for e in events if e["type"] == "T2 HIT — FULL EXIT"]
        ev_sl   = [e for e in events if e["type"] in ("SL HIT","TRAILING SL HIT")]
        ev_eod  = [e for e in events if e["type"] == "EOD AUTO-CLOSE"]
        ev_men  = [e for e in events if e["type"] == "MANUAL EXIT"]
        s1,s2,s3,s4,s5,s6 = st.columns(6)
        s1.metric("📥 Entries",       len(ev_ent))
        s2.metric("🎯 T1 Hits",       len(ev_t1),
                  f"₹{sum(e.get('pnl',0) for e in ev_t1):+,.0f}")
        s3.metric("🎯🎯 T2 Hits",      len(ev_t2),
                  f"₹{sum(e.get('pnl',0) for e in ev_t2):+,.0f}")
        s4.metric("🛑 SL Hits",       len(ev_sl),
                  f"₹{sum(e.get('pnl',0) for e in ev_sl):+,.0f}")
        s5.metric("🕞 EOD Closes",    len(ev_eod),
                  f"₹{sum(e.get('pnl',0) for e in ev_eod):+,.0f}")
        s6.metric("✋ Manual Exits",  len(ev_men),
                  f"₹{sum(e.get('pnl',0) for e in ev_men):+,.0f}")

        for e in reversed(events[-50:]):  # show last 50
            etype  = e["type"]
            pnl    = e.get("pnl", 0)
            icon   = {"ENTRY":"📥","TARGET HIT":"🎯","SL HIT":"🛑",
                      "T1 HIT — PARTIAL EXIT":"🎯½","T2 HIT — FULL EXIT":"🎯🎯",
                      "TRAILING SL HIT":"🔒","MANUAL EXIT":"✋",
                      "EOD AUTO-CLOSE":"🕞","FUND TOP-UP":"💰"}.get(etype,"●")
            bg     = {"ENTRY":"#f0f4e8","TARGET HIT":"#e4f5e8",
                      "T1 HIT — PARTIAL EXIT":"#e4f5e8","T2 HIT — FULL EXIT":"#d4f0dc",
                      "SL HIT":"#fbe8e6","TRAILING SL HIT":"#fff7e6",
                      "MANUAL EXIT":"#f5f0e8","EOD AUTO-CLOSE":"#e8f0ff",
                      "FUND TOP-UP":"#eeedfe"}.get(etype,"#fff")
            bdr    = {"ENTRY":"#b8c89a","TARGET HIT":"#8dcc9a",
                      "T1 HIT — PARTIAL EXIT":"#8dcc9a","T2 HIT — FULL EXIT":"#4dbb6a",
                      "SL HIT":"#dc9090","TRAILING SL HIT":"#e0c060",
                      "MANUAL EXIT":"#e0b870","EOD AUTO-CLOSE":"#90a8dc",
                      "FUND TOP-UP":"#afa9ec"}.get(etype,"#b8c89a")
            pnl_c  = "#1a6b2e" if pnl>0 else ("#9e2018" if pnl<0 else "#4a5e32")
            side_c = "#1a6b2e" if e.get("side","")=="BUY" else "#9e2018"
            pnl_str= f" · P&L <b style='color:{pnl_c};'>₹{pnl:+,.2f}</b>" if etype!="ENTRY" else ""
            st.markdown(
                f"<div style='background:{bg};border:1px solid {bdr};"
                f"border-left:4px solid {bdr};border-radius:8px;"
                f"padding:0.5rem 0.85rem;margin-bottom:0.3rem;"
                f"font-family:DM Mono,monospace;font-size:0.76rem;'>"
                f"<span style='font-size:0.9rem;'>{icon}</span> "
                f"<b style='color:#0e1308;'>{e.get('symbol','')}</b> "
                f"<span style='background:{side_c};color:#fff;border-radius:3px;"
                f"padding:0px 6px;font-size:0.68rem;font-weight:700;'>"
                f"{e.get('side','')}</span> "
                f"<b style='color:#2e3d1a;'>{etype}</b> "
                f"@ ₹{e.get('price',e.get('entry',0)):,.2f}"
                f"{pnl_str} "
                f"<span style='color:#8a9a78;float:right;'>{e.get('time','')}</span>"
                f"<br><span style='color:#6a7a58;font-size:0.68rem;'>"
                f"📌 {e.get('source','—')} · {e.get('tf','—')} · "
                f"{e.get('strategy','—')[:45]}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

        ecol1, ecol2 = st.columns(2)
        with ecol1:
            if st.button("📥 Export Events JSON", key="ft_ev_export"):
                st.download_button("⬇️ Download",
                    data=json.dumps(events, indent=2, default=str),
                    file_name=f"ft_events_{datetime.now().strftime('%Y%m%d')}.json",
                    mime="application/json", key="ft_ev_dl")
        with ecol2:
            if st.button("📋 Export CSV", key="ft_csv_exp"):
                rows = [{k:v for k,v in e.items()} for e in events]
                csv  = pd.DataFrame(rows).to_csv(index=False)
                st.download_button("⬇️ CSV", data=csv,
                    file_name=f"ft_events_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", key="ft_ev_csv_dl")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  SECTION 4 — CLOSED TRADE HISTORY + P&L FILTERS
    # ══════════════════════════════════════════════════════════════
    if closed_pos:
        st.markdown(f"#### 📋 Closed Trades ({len(closed_pos)})")

        # ── P&L Filter controls ───────────────────────────────────
        pnl_values = [p.get("pnl",0) for p in closed_pos]
        min_pnl_all = min(pnl_values) if pnl_values else -10000
        max_pnl_all = max(pnl_values) if pnl_values else 10000

        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            pnl_filter = st.selectbox("Show trades", ["All","Wins only","Losses only","Break-even"],
                                       key="ft_pnl_filter", label_visibility="collapsed")
        with fc2:
            tf_filter_cl = st.multiselect("Timeframe", ["15m","30m","1h","1d","Manual"],
                                           default=[], key="ft_tf_filter",
                                           placeholder="All TFs",
                                           label_visibility="collapsed")
        with fc3:
            side_filter = st.selectbox("Side",["All","BUY only","SELL only"],
                                        key="ft_side_filter", label_visibility="collapsed")
        with fc4:
            strat_list = sorted(set(p.get("strategy","—")[:25] for p in closed_pos))
            strat_filter = st.selectbox("Strategy",["All"]+strat_list,
                                         key="ft_strat_filter", label_visibility="collapsed")

        # Apply filters
        filtered_pos = closed_pos
        if pnl_filter == "Wins only":     filtered_pos = [p for p in filtered_pos if p.get("pnl",0) > 0]
        elif pnl_filter == "Losses only": filtered_pos = [p for p in filtered_pos if p.get("pnl",0) < 0]
        elif pnl_filter == "Break-even":  filtered_pos = [p for p in filtered_pos if p.get("pnl",0) == 0]
        if tf_filter_cl:  filtered_pos = [p for p in filtered_pos if p.get("tf","—") in tf_filter_cl]
        if side_filter == "BUY only":     filtered_pos = [p for p in filtered_pos if p.get("side") == "BUY"]
        elif side_filter == "SELL only":  filtered_pos = [p for p in filtered_pos if p.get("side") == "SELL"]
        if strat_filter != "All":
            filtered_pos = [p for p in filtered_pos if strat_filter in p.get("strategy","")]

        # Filtered summary
        if filtered_pos != closed_pos:
            f_wins = [p for p in filtered_pos if p.get("pnl",0) > 0]
            f_pnl  = round(sum(p.get("pnl",0) for p in filtered_pos), 2)
            st.markdown(
                f"<div style='font-family:DM Mono,monospace;font-size:0.75rem;"
                f"background:#f5f8ed;border:1px solid #b8c89a;border-radius:7px;"
                f"padding:5px 12px;margin-bottom:0.5rem;'>"
                f"Filtered: <b>{len(filtered_pos)}</b> trades · "
                f"Wins: <b>{len(f_wins)}</b> ({round(len(f_wins)/max(len(filtered_pos),1)*100)}%) · "
                f"P&L: <b style='color:{'#1a6b2e' if f_pnl>=0 else '#9e2018'};"
                f"'>₹{f_pnl:+,.2f}</b></div>",
                unsafe_allow_html=True,
            )

        rows = []
        for p in reversed(filtered_pos):
            pnl   = p.get("pnl",0)
            pnl_c = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")
            rows.append({
                "":           pnl_c,
                "Symbol":     p["symbol"],
                "Side":       p["side"],
                "Entry ₹":   f"₹{float(p.get('entry') or 0):,.2f}",
                "Exit ₹":    f"₹{float(p.get('exit_px') or 0):,.2f}",
                "Qty":        p.get("qty", 0),
                "P&L":        f"₹{float(pnl or 0):+,.2f}",
                "P&L %":      f"{float(p.get('pnl_pct') or 0):+.2f}%",
                "Exit Type":  p.get("exit_type","—"),
                "Strategy":   p.get("strategy","—")[:28],
                "TF":         p.get("tf","—"),
                "Closed":     p.get("closed_at","—"),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                         hide_index=True, height=min(400, 60+len(rows)*38))
        else:
            st.info("No trades match the current filter.")

        if rows:
            if st.button("📥 Export Filtered CSV", key="ft_trades_csv"):
                st.download_button("⬇️ Download",
                    data=pd.DataFrame(rows).to_csv(index=False),
                    file_name=f"ft_trades_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", key="ft_tr_dl")

    st.divider()

    st.divider()

    # ══════════════════════════════════════════════════════════════
    #  SECTION 6 — VIRTUAL FUND MANAGEMENT
    # ══════════════════════════════════════════════════════════════
    st.markdown("#### 💰 Virtual Fund Management")

    # Low balance warning (< ₹10,000)
    LOW_BAL_THRESHOLD = 500000.0
    if bal < LOW_BAL_THRESHOLD:
        st.markdown(
            f"<div style='background:#fdf3d4;border:2px solid #e0c060;"
            f"border-radius:10px;padding:0.85rem 1.1rem;margin-bottom:0.75rem;"
            f"font-family:DM Mono,monospace;'>"
            f"<div style='font-weight:700;color:#7a5800;font-size:0.9rem;'>"
            f"⚠️ Low Virtual Balance Alert</div>"
            f"<div style='color:#5a4000;font-size:0.8rem;margin-top:4px;'>"
            f"Balance ₹{bal:,.0f} is below ₹{LOW_BAL_THRESHOLD:,.0f} (5% of starting capital). "
            f"New signals may not enter. Add virtual funds below to continue testing."
            f"</div></div>",
            unsafe_allow_html=True,
        )

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        topup_amt = st.selectbox("Add funds", ["₹50,000","₹1,00,000","₹5,00,000","₹10,00,000"],
                                  key="ft_topup_sel", label_visibility="collapsed")
    with fc2:
        if st.button("➕ Add Virtual Funds", key="ft_topup", use_container_width=True):
            amt_map = {"₹50,000":50000,"₹1,00,000":100000,"₹5,00,000":500000,"₹10,00,000":1000000}
            add_amt = amt_map.get(topup_amt, 500000)
            ft["balance"]  = round(ft["balance"] + add_amt, 2)
            ft["starting"] = round(ft.get("starting",10000000) + add_amt, 2)
            ft["events"].append({
                "time":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type":     "FUND TOP-UP",
                "id":       0,
                "symbol":   "—",
                "side":     "—",
                "price":    0,
                "entry":    0,
                "qty":      0,
                "pnl":      add_amt,
                "pnl_pct":  0,
                "source":   "Manual",
                "strategy": "—",
                "tf":       "—",
                "note":     f"Virtual funds added: ₹{add_amt:,.0f}"
            })
            _ft_flush()
            st.success(f"✅ Added ₹{add_amt:,.0f} virtual funds. New balance ₹{ft['balance']:,.0f}")
            st.rerun()
    with fc3:
        if st.button("🔄 Refresh Prices", key="ft_refresh", use_container_width=True):
            st.rerun()
    with fc4:
        if st.button("🗑️ Reset Account", key="ft_reset_all", use_container_width=True):
            if st.session_state.get("ft_confirm_reset"):
                st.session_state["_ft"] = {"positions":[],"events":[],
                                            "balance":10000000.0,"starting":10000000.0}
                st.session_state["ft_confirm_reset"] = False
                st.session_state["_ft_loaded"] = False
                _ft_flush()
                st.success("✅ Reset to ₹1,00,00,000 (1 Crore)"); st.rerun()
            else:
                st.session_state["ft_confirm_reset"] = True
                st.warning("⚠️ Click Reset again to confirm — all trades & events will be deleted.")

    st.caption("⚠️ Forward Testing uses virtual capital only. Not connected to real broker orders.")


# ══════════════════════════════════════════════════════════════════════
#  STRATEGY LIBRARY
#  Shows all strategies used by the CPR scanner with their live
#  forward-test performance pulled directly from the event log.
# ══════════════════════════════════════════════════════════════════════

STRATEGY_DEFINITIONS = [
    {
        "name":     "CPR Narrow Breakout",
        "icon":     "⚡",
        "tf":       "15 Min / 30 Min",
        "type":     "Intraday Scalp",
        "author":   "Frank Ochoa — Pivot Boss",
        "color":    "#1a6b2e",
        "bg":       "#e4f5e8",
        "border":   "#8dcc9a",
        "entry":    "Price closes above TC (Bull) or below BC (Bear) with volume surge",
        "sl":       "Below BC for Bull / Above TC for Bear",
        "t1":       "R1 (Bull) / S1 (Bear)",
        "t2":       "R2 (Bull) / S2 (Bear) — trailing after T1",
        "filters":  ["CPR Width < 0.5%", "RSI 50–75 (Bull) or 25–50 (Bear)",
                     "HMA trending in signal direction", "Volume ≥ 1.2× avg"],
        "strength_min": 70,
        "rr_min":   1.5,
        "best_for": ["RELIANCE","HDFCBANK","INFY","TCS","ICICIBANK"],
    },
    {
        "name":     "Virgin CPR Breakout",
        "icon":     "⭐",
        "tf":       "1 Hour / 1 Day",
        "type":     "Swing",
        "author":   "Frank Ochoa — Pivot Boss",
        "color":    "#7c3aed",
        "bg":       "#f3effe",
        "border":   "#c8a0f0",
        "entry":    "First touch of untested CPR zone — high probability reversal",
        "sl":       "Beyond CPR range by ATR×0.5",
        "t1":       "Previous session high/low or next pivot",
        "t2":       "R2/S2 (Bull/Bear) — trailing after T1",
        "filters":  ["CPR never touched in last 10 bars", "RSI oversold/overbought near CPR",
                     "Reversal candle at CPR (Hammer, Engulfing, Doji)"],
        "strength_min": 65,
        "rr_min":   2.0,
        "best_for": ["SBIN","BHARTIARTL","LT","BAJFINANCE","KOTAKBANK"],
    },
    {
        "name":     "HMA Trend Follower",
        "icon":     "📈",
        "tf":       "1 Hour / 1 Day",
        "type":     "Trend Follow",
        "author":   "PivotVault AI",
        "color":    "#0369a1",
        "bg":       "#e0f2fe",
        "border":   "#7dd3fc",
        "entry":    "Price pulls back to HMA-20, bounce candle closes back above/below",
        "sl":       "Below HMA by ATR×0.5",
        "t1":       "Previous swing high/low or R1/S1",
        "t2":       "R2/S2 — trailing after T1",
        "filters":  ["HMA clearly trending (3 consecutive H/L values)",
                     "CPR above price (Bull) or below (Bear)", "RSI recovering from extreme"],
        "strength_min": 65,
        "rr_min":   2.0,
        "best_for": ["TCS","WIPRO","HCLTECH","INFY","SUNPHARMA"],
    },
    {
        "name":     "RSI + CPR Confluence",
        "icon":     "🔄",
        "tf":       "15 Min / 1 Hour",
        "type":     "Intraday",
        "author":   "PivotVault AI",
        "color":    "#dc2626",
        "bg":       "#fbe8e6",
        "border":   "#f0a0a0",
        "entry":    "RSI crosses 50 AND price on correct side of CPR",
        "sl":       "CPR midpoint (Pivot P)",
        "t1":       "R1 (Bull) / S1 (Bear)",
        "t2":       "R2/S2 — trailing after T1",
        "filters":  ["RSI cross above/below 50", "Price above TC (Bull) or below BC (Bear)",
                     "CPR width < 1%", "Volume at or above 20-bar avg"],
        "strength_min": 55,
        "rr_min":   1.5,
        "best_for": ["RELIANCE","SBIN","HDFCBANK","ASIANPAINT","NTPC"],
    },
    {
        "name":     "Candlestick + CPR",
        "icon":     "🕯️",
        "tf":       "15 Min / 1 Hour / 1 Day",
        "type":     "Intraday / Swing",
        "author":   "PivotVault AI",
        "color":    "#059669",
        "bg":       "#d1fae5",
        "border":   "#6ee7b7",
        "entry":    "Reversal pattern exactly at CPR or pivot level",
        "sl":       "Below pattern low (Bull) / Above pattern high (Bear)",
        "t1":       "Next pivot/CPR level",
        "t2":       "Second pivot level — trailing after T1",
        "filters":  ["Hammer/Engulfing/Morning Star/Shooting Star/Evening Star at CPR",
                     "Volume surge on pattern candle > 1.5× avg",
                     "RSI not at extreme", "HMA confirms direction"],
        "strength_min": 60,
        "rr_min":   1.5,
        "best_for": ["BAJFINANCE","KOTAKBANK","TITAN","MARUTI","LT"],
    },
    {
        "name":     "Two-Day CPR Non-Overlap",
        "icon":     "📅",
        "author":   "Frank Ochoa — Pivot Boss",
        "tf":       "15 Min / 30 Min / 1 Hour",
        "type":     "Trending Day Breakout",
        "color":    "#1a6b2e",
        "bg":       "#edf7ee",
        "border":   "#b8dfc0",
        "filters":  [
            "Today's CPR entirely above OR below yesterday's CPR (Non-overlapping)",
            "CPR Width < 0.5% (Narrow — confirms trending day)",
            "Price on correct side of CPR at open",
            "Strength ≥ 70%",
        ],
        "entry":    "TC breakout (Bull) or BC breakdown (Bear) with volume",
        "sl":       "Below BC (Bull) or above TC (Bear) + 0.1×ATR buffer",
        "t1":       "R1 (Bull) or S1 (Bear)",
        "t2":       "R2 (Bull) or S2 (Bear)",
        "strength_min": 70,
        "rr_min":   2.0,
        "best_for": ["RELIANCE", "NIFTY", "BANKNIFTY", "TCS", "HDFCBANK"],
    },
    {
        "name":     "Wick Reversal at CPR",
        "icon":     "🕯️",
        "author":   "Frank Ochoa — Pivot Boss SPB",
        "tf":       "15 Min / 30 Min / 1 Hour",
        "type":     "Reversal",
        "color":    "#7c3aed",
        "bg":       "#f5f0ff",
        "border":   "#c4b5fd",
        "filters":  [
            "Hammer / Pin Bar / Engulfing forming within 0.5×ATR of BC (Bull) or TC (Bear)",
            "Lower wick ≥ 2× body (Hammer) or upper wick ≥ 2× body (Shooting Star)",
            "RSI oversold (<40) for Bull or overbought (>60) for Bear",
            "Volume surge on reversal candle",
        ],
        "entry":    "Close of reversal candle + 0.05×ATR",
        "sl":       "Low of wick candle − 0.1×ATR",
        "t1":       "TC (Bull) or BC (Bear) — CPR midpoint",
        "t2":       "R1/S1 pivot extension",
        "strength_min": 65,
        "rr_min":   1.5,
        "best_for": ["INFY", "WIPRO", "AXISBANK", "MARUTI", "TITAN"],
    },
    {
        "name":     "Extreme Reversal (Rubber Band)",
        "icon":     "🔁",
        "author":   "Frank Ochoa — Pivot Boss SPB",
        "tf":       "15 Min / 30 Min",
        "type":     "Mean Reversion",
        "color":    "#dc2626",
        "bg":       "#fff0f0",
        "border":   "#fca5a5",
        "filters":  [
            "Current bar range ≥ 2× average bar size (over-extended move)",
            "Price at extreme — 3+ consecutive bars in one direction",
            "Reversal candle forming at S2/R2 or CPR extreme",
            "3/10 Oscillator showing exhaustion (histogram flattening)",
        ],
        "entry":    "Close of reversal bar after extreme move",
        "sl":       "Extreme of the over-extended bar",
        "t1":       "50% retracement back toward CPR value",
        "t2":       "CPR Pivot (P) — full mean reversion",
        "strength_min": 65,
        "rr_min":   2.0,
        "best_for": ["BAJFINANCE", "KOTAKBANK", "ADANIENT", "TATAMOTORS"],
    },
    {
        "name":     "Outside Reversal (False Breakout Fade)",
        "icon":     "🔄",
        "author":   "Frank Ochoa — Pivot Boss SPB",
        "tf":       "30 Min / 1 Hour",
        "type":     "False Breakout Fade",
        "color":    "#ea580c",
        "bg":       "#fff7ed",
        "border":   "#fdba74",
        "filters":  [
            "Bar sweeps beyond prior High/Low then closes back inside range",
            "Bar range ≥ 1.25× average bar size",
            "Previous bar was near key pivot level (R1/S1/TC/BC)",
            "RSI shows divergence at the sweep extreme",
        ],
        "entry":    "Close of outside reversal bar",
        "sl":       "Beyond the sweep extreme + 0.1×ATR",
        "t1":       "Prior consolidation midpoint / CPR value",
        "t2":       "Opposite pivot level (S1 for bull fade, R1 for bear fade)",
        "strength_min": 60,
        "rr_min":   1.5,
        "best_for": ["SBIN", "ICICIBANK", "LT", "HINDUNILVR", "NTPC"],
    },
    {
        "name":     "Virgin CPR Weekly Magnet",
        "icon":     "🧲",
        "author":   "Frank Ochoa — Pivot Boss",
        "tf":       "1 Hour / 1 Day",
        "type":     "Swing / Magnet Trade",
        "color":    "#0369a1",
        "bg":       "#f0f9ff",
        "border":   "#7dd3fc",
        "filters":  [
            "Weekly CPR untouched for 5+ sessions (Virgin Weekly CPR)",
            "Price approaching weekly CPR from below (Bull) or above (Bear)",
            "Daily CPR aligned with weekly CPR direction",
            "HMA trending toward CPR magnet",
        ],
        "entry":    "Price enters weekly CPR zone (BC to TC)",
        "sl":       "Weekly BC − ATR (Bull) or weekly TC + ATR (Bear)",
        "t1":       "Weekly CPR midpoint / Pivot P",
        "t2":       "Opposite weekly CPR boundary",
        "strength_min": 60,
        "rr_min":   2.0,
        "best_for": ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "HDFCBANK"],
    },
    {
        "name":     "3/10 Oscillator Cross",
        "icon":     "〰️",
        "tf":       "30 Min / 1 Hour",
        "type":     "Momentum",
        "author":   "Frank Ochoa — Pivot Boss",
        "color":    "#d97706",
        "bg":       "#fdf3d4",
        "border":   "#f0c060",
        "entry":    "Fresh 3MA/10MA bullish or bearish crossover with CPR confirmation",
        "sl":       "Below BC (Bull) / Above TC (Bear)",
        "t1":       "R1/S1",
        "t2":       "R2/S2 — trailing after T1",
        "filters":  ["Fresh crossover (not continuation)", "Price on correct CPR side",
                     "RSI in momentum zone (>50 Bull, <50 Bear)"],
        "strength_min": 60,
        "rr_min":   1.5,
        "best_for": ["MARUTI","TITAN","AXISBANK","BAJAJHFL","POWERGRID"],
    },
]


def page_strategy_library():
    """Strategy Library — all CPR strategies with live forward-test performance."""

    st.markdown("""
    <div class="title-bar">
        <span style="font-size:1.4rem;">📚</span>
        <h1>Strategy Library</h1>
        <span style="margin-left:auto;background:#eeedfe;border:1px solid #afa9ec;
                     color:#3c3489;padding:3px 12px;border-radius:20px;
                     font-family:DM Mono,monospace;font-size:0.7rem;font-weight:700;">
            FRANK OCHOA · CPR · PIVOT BOSS
        </span>
    </div>""", unsafe_allow_html=True)

    # ── Pull live P&L from Forward Testing events ─────────────────────────
    try:
        ft_events = _ft_state().get("events", [])
    except Exception:
        ft_events = []

    # Build strategy performance map from FT events
    strat_perf: dict = {}
    for e in ft_events:
        if e["type"] in ("ENTRY", "FUND TOP-UP"): continue
        strat_key = e.get("strategy","Unknown")[:40]
        if strat_key not in strat_perf:
            strat_perf[strat_key] = {
                "trades":0,"wins":0,"pnl":0.0,
                "tgt":0,"sl_hits":0,"trailing_sl":0,
                "t1":0,"t2":0,
            }
        sm = strat_perf[strat_key]
        sm["trades"] += 1
        sm["pnl"]    += e.get("pnl",0)
        if e.get("pnl",0) > 0:  sm["wins"] += 1
        if "T1 HIT"       in e["type"]: sm["t1"] += 1
        if "T2 HIT"       in e["type"]: sm["t2"] += 1
        if "SL HIT"       in e["type"]: sm["sl_hits"] += 1
        if "TRAILING SL"  in e["type"]: sm["trailing_sl"] += 1

    # ── Filters ───────────────────────────────────────────────────────────
    fc1, fc2 = st.columns([2,1])
    with fc1:
        tf_filter = st.multiselect("Filter by timeframe",
            ["15 Min","30 Min","1 Hour","1 Day"],
            default=[], placeholder="All timeframes", key="sl_tf",
            label_visibility="collapsed")
    with fc2:
        sort_by = st.selectbox("Sort by",
            ["Strategy Name","Win Rate","Net P&L","Trades"],
            key="sl_sort", label_visibility="collapsed")

    filtered = STRATEGY_DEFINITIONS
    if tf_filter:
        filtered = [s for s in filtered if any(t in s["tf"] for t in tf_filter)]

    st.markdown(
        f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
        f"color:#4a5e32;margin-bottom:0.75rem;'>"
        f"Showing <b>{len(filtered)}</b> of {len(STRATEGY_DEFINITIONS)} strategies · "
        f"<b>{len(strat_perf)}</b> have live forward-test data</div>",
        unsafe_allow_html=True,
    )

    # ── Overall Forward Test Summary ──────────────────────────────────────
    if strat_perf:
        st.markdown("#### 📊 Live Forward-Test Performance — All Strategies")
        rows = []
        for sk, sm in sorted(strat_perf.items(),
                              key=lambda x: (-x[1]["pnl"] if sort_by=="Net P&L"
                                            else -x[1]["wins"]/max(x[1]["trades"],1) if sort_by=="Win Rate"
                                            else -x[1]["trades"] if sort_by=="Trades"
                                            else x[0])):
            wr  = round(sm["wins"]/max(sm["trades"],1)*100)
            rows.append({
                "Strategy":   sk,
                "Trades":     sm["trades"],
                "Win %":      f"{wr}%",
                "🎯 T1 Hits": sm["t1"],
                "🎯🎯 T2 Hits": sm["t2"],
                "🛑 SL Hits": sm["sl_hits"],
                "🔒 Trail SL":sm["trailing_sl"],
                "Net P&L":    f"₹{sm['pnl']:+,.2f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True, height=min(300,60+len(rows)*40))
        st.divider()

    # ── Strategy Cards ────────────────────────────────────────────────────
    for strat in filtered:
        col     = strat["color"]
        bg      = strat["bg"]
        bdr     = strat["border"]

        # Look up live perf — match by partial strategy name
        live = None
        for sk, sm in strat_perf.items():
            if strat["name"][:20].lower() in sk.lower():
                live = sm; break

        with st.expander(
            f"{strat['icon']} {strat['name']} · {strat['tf']} · {strat['type']}",
            expanded=False,
        ):
            cc1, cc2 = st.columns([3,2])

            with cc1:
                st.markdown(
                    f"<div style='font-family:DM Mono,monospace;font-size:0.72rem;"
                    f"color:#4a5e32;margin-bottom:0.5rem;'>"
                    f"<b>Author:</b> {strat['author']}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("**Entry conditions:**")
                for f in strat["filters"]:
                    st.markdown(
                        f"<div style='font-family:DM Sans,sans-serif;font-size:0.82rem;"
                        f"color:#2e3d1a;margin-bottom:2px;'>"
                        f"<span style='color:{col};font-weight:700;'>✓</span> {f}</div>",
                        unsafe_allow_html=True,
                    )

                # Entry / SL / T1 / T2
                for label, val in [("🎯 Entry",  strat["entry"]),
                                   ("🛑 SL",     strat["sl"]),
                                   ("📍 T1",     strat["t1"]),
                                   ("🚀 T2",     strat["t2"])]:
                    st.markdown(
                        f"<div style='font-family:DM Mono,monospace;font-size:0.75rem;"
                        f"margin-bottom:3px;'><b style='color:#0e1308;'>{label}:</b> "
                        f"<span style='color:#2e3d1a;'>{val}</span></div>",
                        unsafe_allow_html=True,
                    )

            with cc2:
                st.markdown(
                    f"<div style='background:{bg};border:1.5px solid {bdr};"
                    f"border-radius:10px;padding:0.85rem;'>"
                    f"<div style='font-family:DM Mono,monospace;font-size:0.65rem;"
                    f"text-transform:uppercase;letter-spacing:0.08em;color:#4a5e32;"
                    f"margin-bottom:0.5rem;'>Strategy Specs</div>"
                    f"<div style='font-family:DM Mono,monospace;font-size:0.78rem;"
                    f"line-height:1.8;color:#1e2c0d;'>"
                    f"Min Strength: <b>{strat['strength_min']}%</b><br>"
                    f"Min R:R: <b>{strat['rr_min']}:1</b><br>"
                    f"Best stocks:<br>"
                    + "".join(f"<span style='background:{bdr};border-radius:4px;"
                              f"padding:1px 6px;margin:1px;font-size:0.68rem;"
                              f"display:inline-block;'>{s}</span>"
                              for s in strat["best_for"])
                    + "</div></div>",
                    unsafe_allow_html=True,
                )

                if live:
                    wr = round(live["wins"]/max(live["trades"],1)*100)
                    pnl_c = "#1a6b2e" if live["pnl"] >= 0 else "#9e2018"
                    st.markdown(
                        f"<div style='background:#1a1f0e;border-radius:8px;"
                        f"padding:0.65rem;margin-top:0.5rem;"
                        f"font-family:DM Mono,monospace;font-size:0.72rem;"
                        f"color:#7da048;'>"
                        f"🧪 LIVE FT RESULTS<br>"
                        f"<span style='color:#f8faf0;'>"
                        f"Trades: {live['trades']} · Win: {wr}%<br>"
                        f"P&L: <b style='color:{pnl_c};'>₹{live['pnl']:+,.2f}</b><br>"
                        f"T1: {live['t1']} · T2: {live['t2']} · SL: {live['sl_hits']}"
                        f"</span></div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div style='background:#f5f8ed;border:1px dashed #b8c89a;"
                        f"border-radius:8px;padding:0.65rem;margin-top:0.5rem;"
                        f"font-family:DM Mono,monospace;font-size:0.72rem;color:#4a5e32;"
                        f"text-align:center;'>No forward test data yet.<br>"
                        f"Run the scanner to start.</div>",
                        unsafe_allow_html=True,
                    )

            # Launch FT button
            if st.button(f"🧪 Forward Test this strategy",
                         key=f"ft_strat_{strat['name'][:20]}",
                         use_container_width=True):
                st.session_state["current_page"] = "Forward Testing"
                st.rerun()


def render_sidebar():
    """
    Navigation — uses st.radio (guaranteed to work in all Streamlit environments).
    Styled as pills via CSS override on radio buttons.
    Zero hidden buttons. Zero JS tricks. Pure Streamlit.
    """
    # ── All pages (key, label, always-on) ───────────────────────────────
    ALL_PAGES = [
        ("Market Snapshot",     "📊 Market",     True),   # always visible — home
        ("Pivot Boss Analysis", "📈 Pivot Boss",  False),
        ("Scanner & Signals",   "📡 Scanner",     False),
        ("Forward Testing",     "🧪 Fwd Test",    False),
        ("Trade Analysis",      "📊 Analysis",    False),
        ("Order Execution",     "⚡ Orders",      False),
        ("Strategy Library",    "📚 Strategy",    False),
        ("Broker Settings",     "⚙️ Broker",      True),  # always visible — required
        ("Watchlist",           "⭐ Watchlist",   False),
    ]

    # ── Load saved tab visibility from session (persisted in creds file) ─
    _TAB_VIS_KEY = "tab_visibility"
    if _TAB_VIS_KEY not in st.session_state:
        # First run: restore from saved creds or use defaults
        _saved_vis = {}
        try:
            import json, os
            _cf = os.path.join(os.path.expanduser("~"), ".pivotvault", "pivotvault_creds.json")
            if os.path.exists(_cf):
                _saved_vis = json.load(open(_cf)).get("tab_visibility", {})
        except Exception:
            pass
        st.session_state[_TAB_VIS_KEY] = _saved_vis

    _tab_vis = st.session_state[_TAB_VIS_KEY]

    # Build active page list — always-on pages + user-enabled pages
    PAGES = [
        (k, lbl) for k, lbl, always in ALL_PAGES
        if always or _tab_vis.get(k, False)
    ]
    PAGE_KEYS   = [p[0] for p in PAGES]
    PAGE_LABELS = [p[1] for p in PAGES]

    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Market Snapshot"
    if st.session_state["current_page"] not in PAGE_KEYS:
        st.session_state["current_page"] = "Market Snapshot"

    current = st.session_state["current_page"]
    cur_idx = PAGE_KEYS.index(current)
    wl      = len(st.session_state.get("watchlist", []))
    uname   = st.session_state.get("username", "")[:14]

    # ── Override radio to look like horizontal pills ──────────────────────
    st.markdown("""
<style>
/* Hide sidebar + collapse button */
section[data-testid="stSidebar"]        { display:none !important; }
[data-testid="collapsedControl"]         { display:none !important; }
button[data-testid="baseButton-header"]  { display:none !important; }

/* Radio nav — hide the label */
div[data-testid="stRadio"] > label { display:none !important; }

/* Radio container — wrap like pills */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    display       : flex !important;
    flex-wrap     : wrap !important;
    gap           : 4px !important;
    align-items   : center !important;
    padding       : 0.25rem 0 0.45rem !important;
    border-bottom : 2px solid #b8c89a !important;
    margin-bottom : 0.55rem !important;
}

/* Each radio option wrapper */
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    display       : inline-flex !important;
    align-items   : center !important;
    padding       : 5px 11px !important;
    border-radius : 18px !important;
    border        : 1.5px solid #b8c89a !important;
    background    : #ffffff !important;
    cursor        : pointer !important;
    margin        : 1px !important;
    transition    : background 0.12s, border-color 0.12s !important;
    white-space   : nowrap !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
    background    : #dce8c4 !important;
    border-color  : #638534 !important;
}

/* Radio label text */
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div > p,
div[data-testid="stRadio"] > div[role="radiogroup"] > label p {
    font-family : DM Sans, sans-serif !important;
    font-size   : 0.78rem !important;
    font-weight : 600 !important;
    color       : #2e3d1a !important;
    margin      : 0 !important;
    line-height : 1.3 !important;
}

/* Hide the actual radio circle */
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
    display : none !important;
}

/* SELECTED pill — dark green */
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-selected="true"],
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
    background   : #3d5a1c !important;
    border-color : #3d5a1c !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label[data-selected="true"] p,
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
    color       : #f8faf0 !important;
    font-weight : 700 !important;
}
</style>
""", unsafe_allow_html=True)

    # ── Logo + user ───────────────────────────────────────────────────────
    lc, rc = st.columns([5, 1])
    with lc:
        st.markdown(
            "<div style='font-family:DM Sans,sans-serif;font-weight:900;font-size:1rem;"
            "color:#0e1308;padding:0.15rem 0 0.05rem;'>"
            "🏦 PivotVault <span style=\"color:#3d5a1c;\">AI</span></div>",
            unsafe_allow_html=True,
        )
    with rc:
        st.markdown(
            "<div style='font-family:DM Mono,monospace;font-size:0.63rem;"
            "color:#4a5e32;text-align:right;padding-top:0.25rem;'>"
            "👤 " + uname + " ⭐" + str(wl) + "</div>",
            unsafe_allow_html=True,
        )

    # ── Radio nav (renders as pills via CSS above) ────────────────────────
    nc, btn1, btn2 = st.columns([10, 1, 1])
    with nc:
        selected = st.radio(
            "nav",
            PAGE_LABELS,
            index=cur_idx,
            horizontal=True,
            key="main_nav_radio",
            label_visibility="hidden",
        )
    with btn1:
        _show_tab_mgr = st.button(
            "🗂️", key="tab_mgr_btn",
            help="Manage Tabs — turn pages on/off",
            use_container_width=True,
        )
    with btn2:
        if st.button("🚪", key="logout_btn", help="Logout", use_container_width=True):
            _clear_session()
            st.session_state["logged_in"]    = False
            st.session_state["username"]     = ""
            st.session_state["user_email"]   = ""
            st.session_state["user_id"]      = None
            st.session_state["current_page"] = "Market Snapshot"
            st.session_state["tg_otp_code"]  = ""
            # Broker token intentionally NOT cleared — pasted once at 9 AM
            st.rerun()

    # ── Tab Manager toggle ─────────────────────────────────────────────────
    if _show_tab_mgr:
        st.session_state["show_tab_manager"] = not st.session_state.get("show_tab_manager", False)

    if st.session_state.get("show_tab_manager", False):
        _header_html = (
            "<div style='background:#f7f9f2;border:1.5px solid #b8c89a;border-radius:10px;"
            "padding:0.8rem 1rem;margin-bottom:0.6rem;font-family:IBM Plex Mono,monospace;'>"
            "<div style='font-size:0.85rem;font-weight:700;color:#1a1f0e;margin-bottom:0.4rem;'>"
            "🗂️ Manage Tabs"
            "<span style='font-size:0.65rem;font-weight:400;color:#5a6a48;margin-left:8px;'>"
            "Toggle pages on / off &nbsp;·&nbsp; Market &amp; Broker are always visible"
            "</span></div></div>"
        )
        st.markdown(_header_html, unsafe_allow_html=True)

        _toggleable = [(k, lbl) for k, lbl, always in ALL_PAGES if not always]
        _cols   = st.columns(3)
        _changed = False
        for _ti, (tk, tlbl) in enumerate(_toggleable):
            with _cols[_ti % 3]:
                _cur  = _tab_vis.get(tk, False)
                _new  = st.toggle(tlbl, value=_cur,
                                  key="tab_tog_" + tk.replace(" ", "_").replace("&",""))
                if _new != _cur:
                    st.session_state[_TAB_VIS_KEY][tk] = _new
                    _changed = True

        if _changed:
            # Persist tab visibility to creds file
            try:
                import json as _json, os as _os
                _cf = _os.path.join(_os.path.expanduser("~"), ".pivotvault", "pivotvault_creds.json")
                _cdata = {}
                if _os.path.exists(_cf):
                    with open(_cf) as _fh:
                        _cdata = _json.load(_fh)
                _cdata["tab_visibility"] = st.session_state[_TAB_VIS_KEY]
                _os.makedirs(_os.path.dirname(_cf), exist_ok=True)
                with open(_cf, "w") as _fh:
                    _json.dump(_cdata, _fh)
            except Exception:
                pass
            # If active page was just disabled, redirect home
            _active_keys = [
                k for k, lbl, always in ALL_PAGES
                if always or st.session_state[_TAB_VIS_KEY].get(k, False)
            ]
            if current not in _active_keys:
                st.session_state["current_page"] = "Market Snapshot"
            st.rerun()

        _, _done_col = st.columns([4, 1])
        with _done_col:
            if st.button("✅ Done", key="tab_mgr_close", use_container_width=True):
                st.session_state["show_tab_manager"] = False
                st.rerun()
        st.divider()

    # Update page on selection change
    sel_page = PAGE_KEYS[PAGE_LABELS.index(selected)]
    if sel_page != current:
        st.session_state["current_page"] = sel_page
        st.rerun()

    return sel_page



# ════════════════════════════════════════════════════════════════════════════════
# TRADE ANALYSIS TAB — PivotVault AI v2
# Records all trades, provides insights, generates CSV reports
# ════════════════════════════════════════════════════════════════════════════════

def format_rupee(val: float) -> str:
    """Format as ₹X,XXX.XX"""
    return f"₹{val:,.2f}"

def analyze_trade(pos: dict) -> dict:
    """Compute trade analytics for a single closed position"""
    entry = pos.get("entry", 0)
    sl = pos.get("sl", 0)
    t1_pnl = pos.get("t1_pnl", 0)
    t2_pnl = pos.get("pnl", 0)
    exit_px = pos.get("exit_px", 0)
    qty = pos.get("qty", 0)
    cost = pos.get("cost", 0)

    sl_dist_pct = abs(entry - sl) / entry * 100 if entry > 0 else 0
    max_risk = abs(entry - sl) * qty
    final_pnl = pos.get("pnl", 0)
    rr_achieved = abs(final_pnl) / max(max_risk, 1) if max_risk > 0 else 0

    return {
        "entry": entry,
        "sl": sl,
        "exit": exit_px,
        "sl_dist_pct": sl_dist_pct,
        "max_risk": max_risk,
        "t1_pnl": t1_pnl,
        "final_pnl": final_pnl,
        "rr_achieved": rr_achieved,
        "t1_locked": 1 if t1_pnl != 0 else 0,
    }

def page_trade_analysis():
    """Trade Analysis Tab — Records, Insights, CSV Export"""

    st.markdown("""
    <div class="title-bar">
        <span class="live-dots"></span>
        <h1 style="color:#1a1f0e">📊 Trade Analysis & Reports</h1>
    </div>
    """, unsafe_allow_html=True)

    ft = st.session_state.get("ft_state", {})
    trades = ft.get("trades", [])
    events = ft.get("events", [])
    balance = ft.get("balance", 0)
    starting = ft.get("starting", 10000000)

    # Filter closed trades
    closed_trades = [t for t in trades if t.get("status") != "OPEN"]

    if not closed_trades:
        st.info("📊 No closed trades yet. Start forward testing to see trade analysis.")
        return

    # ── SUMMARY METRICS ──
    st.divider()
    st.markdown("""
    <div style="font-family:IBM Plex Mono,monospace;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;color:#5a6a48;margin-bottom:0.6rem;">
    📈 SESSION SUMMARY
    </div>
    """, unsafe_allow_html=True)

    total_trades = len(closed_trades)
    wins = [t for t in closed_trades if t.get("pnl", 0) > 0]
    losses = [t for t in closed_trades if t.get("pnl", 0) < 0]
    breakeven = [t for t in closed_trades if t.get("pnl", 0) == 0]

    total_pnl = sum(t.get("pnl", 0) for t in closed_trades)
    total_risk = sum(abs(t.get("entry", 0) - t.get("sl", 0)) * t.get("qty", 1) for t in closed_trades)
    win_rate = round(len(wins) / max(total_trades, 1) * 100, 1)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Trades", total_trades)
    with col2:
        col_w = "#2d7a3a" if win_rate > 60 else "#d97706" if win_rate > 50 else "#c0392b"
        st.markdown(f"<div style='text-align:center'><div style='font-size:0.75rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.08em;'>Win Rate</div>"
                   f"<div style='font-size:1.4rem;font-weight:700;color:{col_w};'>{win_rate}%</div></div>", unsafe_allow_html=True)
    with col3:
        st.metric("Wins", len(wins))
    with col4:
        st.metric("Losses", len(losses))
    with col5:
        col_pnl = "#2d7a3a" if total_pnl > 0 else "#c0392b"
        st.markdown(f"<div style='text-align:center'><div style='font-size:0.75rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.08em;'>Total P&L</div>"
                   f"<div style='font-size:1.4rem;font-weight:700;color:{col_pnl};'>{format_rupee(total_pnl)}</div></div>", unsafe_allow_html=True)

    # ── TRADE-WISE BREAKDOWN ──
    st.divider()
    st.markdown("""
    <div style="font-family:IBM Plex Mono,monospace;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;color:#5a6a48;margin-bottom:0.6rem;">
    📋 TRADE-WISE DETAILS
    </div>
    """, unsafe_allow_html=True)

    # Build trade details table
    trade_rows = []
    for i, t in enumerate(closed_trades, 1):
        analysis = analyze_trade(t)
        side = t.get("side", "BUY")

        trade_rows.append({
            "#": i,
            "Symbol": t.get("symbol", ""),
            "Side": side,
            "Entry": format_rupee(t.get("entry", 0)),
            "Exit": format_rupee(t.get("exit_px", 0)),
            "SL": format_rupee(t.get("sl", 0)),
            "SL%": f"{analysis['sl_dist_pct']:.2f}%",
            "Qty": t.get("qty", 0),
            "Max Risk": format_rupee(analysis["max_risk"]),
            "P&L": format_rupee(t.get("pnl", 0)),
            "Exit Type": t.get("exit_type", ""),
            "Strategy": t.get("strategy", ""),
            "TF": t.get("tf", ""),
        })

    trade_df = pd.DataFrame(trade_rows)

    st.dataframe(
        trade_df,
        use_container_width=True,
        hide_index=True,
        height=min(500, 38 * len(trade_df) + 60)
    )

    # ── INSIGHTS SECTION ──
    st.divider()
    st.markdown("""
    <div style="font-family:IBM Plex Mono,monospace;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;color:#5a6a48;margin-bottom:0.6rem;">
    💡 KEY INSIGHTS
    </div>
    """, unsafe_allow_html=True)

    ins1, ins2, ins3, ins4 = st.columns(4)

    with ins1:
        best = max(closed_trades, key=lambda x: x.get("pnl", 0))
        st.markdown(f"""
        <div style='background:#edf7ee;border:1px solid #b8dfc0;border-radius:8px;padding:0.8rem;'>
        <div style='font-size:0.65rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.08em;'>Best Trade</div>
        <div style='font-size:0.9rem;font-weight:700;color:#2d7a3a;margin-top:0.3rem;'>{best.get("symbol")}</div>
        <div style='font-size:1rem;font-weight:700;color:#2d7a3a;margin-top:0.2rem;'>{format_rupee(best.get("pnl", 0))}</div>
        </div>
        """, unsafe_allow_html=True)

    with ins2:
        worst = min(closed_trades, key=lambda x: x.get("pnl", 0))
        st.markdown(f"""
        <div style='background:#fdf0ee;border:1px solid #f0c0b8;border-radius:8px;padding:0.8rem;'>
        <div style='font-size:0.65rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.08em;'>Worst Trade</div>
        <div style='font-size:0.9rem;font-weight:700;color:#c0392b;margin-top:0.3rem;'>{worst.get("symbol")}</div>
        <div style='font-size:1rem;font-weight:700;color:#c0392b;margin-top:0.2rem;'>{format_rupee(worst.get("pnl", 0))}</div>
        </div>
        """, unsafe_allow_html=True)

    with ins3:
        avg_win = sum(t.get("pnl", 0) for t in wins) / max(len(wins), 1) if wins else 0
        avg_loss = sum(t.get("pnl", 0) for t in losses) / max(len(losses), 1) if losses else 0
        profit_factor = abs(sum(t.get("pnl", 0) for t in wins)) / abs(sum(t.get("pnl", 0) for t in losses)) if losses and sum(t.get("pnl", 0) for t in losses) != 0 else 0

        st.markdown(f"""
        <div style='background:#f0f4e8;border:1px solid #d4e4c1;border-radius:8px;padding:0.8rem;'>
        <div style='font-size:0.65rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.08em;'>Profit Factor</div>
        <div style='font-size:1rem;font-weight:700;color:#2e3d1a;margin-top:0.3rem;'>{profit_factor:.2f}x</div>
        <div style='font-size:0.7rem;color:#5a6a48;margin-top:0.2rem;'>Wins ÷ Losses</div>
        </div>
        """, unsafe_allow_html=True)

    with ins4:
        ror = round(total_pnl / max(total_risk, 1) * 100, 1) if total_risk > 0 else 0
        st.markdown(f"""
        <div style='background:#f9f6eb;border:1px solid #e8dcc1;border-radius:8px;padding:0.8rem;'>
        <div style='font-size:0.65rem;color:#5a6a48;text-transform:uppercase;letter-spacing:0.08em;'>Return on Risk</div>
        <div style='font-size:1rem;font-weight:700;color:#c97e1f;margin-top:0.3rem;'>{ror}%</div>
        <div style='font-size:0.7rem;color:#5a6a48;margin-top:0.2rem;'>Total P&L ÷ Total Risk</div>
        </div>
        """, unsafe_allow_html=True)

    # ── EXIT TYPE ANALYSIS ──
    st.divider()
    exit_types = {}
    for t in closed_trades:
        et = t.get("exit_type", "Unknown")
        if et not in exit_types:
            exit_types[et] = {"count": 0, "pnl": 0, "wins": 0}
        exit_types[et]["count"] += 1
        exit_types[et]["pnl"] += t.get("pnl", 0)
        if t.get("pnl", 0) > 0:
            exit_types[et]["wins"] += 1

    st.markdown("""
    <div style="font-family:IBM Plex Mono,monospace;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;color:#5a6a48;margin-bottom:0.6rem;">
    📊 EXIT TYPE BREAKDOWN
    </div>
    """, unsafe_allow_html=True)

    exit_rows = []
    for et, stats in exit_types.items():
        wr = round(stats["wins"] / max(stats["count"], 1) * 100, 1)
        exit_rows.append({
            "Exit Type": et,
            "Count": stats["count"],
            "Win Rate": f"{wr}%",
            "Total P&L": format_rupee(stats["pnl"]),
            "Avg P&L": format_rupee(stats["pnl"] / stats["count"]),
        })

    exit_df = pd.DataFrame(exit_rows)
    st.dataframe(exit_df, use_container_width=True, hide_index=True)

    # ── EXPORT SECTION ──
    st.divider()
    st.markdown("""
    <div style="font-family:IBM Plex Mono,monospace;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase;color:#5a6a48;margin-bottom:0.6rem;">
    📄 EXPORT OPTIONS
    </div>
    """, unsafe_allow_html=True)

    exp_cols = st.columns(3)

    with exp_cols[0]:
        csv_data = trade_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"pvai_trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with exp_cols[1]:
        st.info("✅ CSV ready — Open in Excel or Google Sheets")

    with exp_cols[2]:
        if st.button("📋 Copy Table", use_container_width=True, key="copy_trades_tab"):
            st.toast("Trade table copied!", icon="✅")



def main():
    # Load persisted session + credentials on every run (survives refresh)
    _load_session()      # loads auth + calls _load_credentials inside

    # Validate restored session — if logged_in but name missing, re-ask login
    if st.session_state.get("logged_in") and not st.session_state.get("username"):
        # Partial restore — try to recover name from USERS dict
        _uid = st.session_state.get("user_email", "")
        if _uid and _uid in USERS:
            st.session_state["username"] = USERS[_uid]["name"]

    if not st.session_state["logged_in"]:
        page_login()
        return

    page = render_sidebar()
    render_market_header()
    st.divider()
    nse500 = fetch_nse500_list()

    # Daily 9 AM Telegram token reminder (weekdays only, once per day)
    _check_daily_token_reminder()

    # NOTE: _show_token_refresh_popup() is called inside render_market_header() above.
    # Do NOT call it again here — duplicate widget keys crash Streamlit.

    # ── Run FT triggers on EVERY page (not just FT page) ───────────────────
    # This ensures SL/T1/T2 are checked even when user is on Scanner/Snapshot
    if is_market_open():
        try:
            _bg_fired = _ft_run_triggers()
            for _bf in _bg_fired:
                _icon = "🎯" if "T2" in _bf.get("hit","") else (
                        "🎯" if "T1" in _bf.get("hit","") else "🛑")
                st.toast(f"{_icon} {_bf['symbol']} — {_bf['hit']} | "
                         f"₹{_bf.get('pnl',0):+,.2f}", icon=_icon)
        except Exception:
            pass

    if   page == "Market Snapshot":      page_market_snapshot(nse500)
    elif page == "Pivot Boss Analysis":  page_pivot_boss(nse500)
    elif page == "Scanner & Signals":    page_scanner_signals(nse500)
    elif page == "Forward Testing":      page_forward_test()
    elif page == "Trade Analysis":       page_trade_analysis()
    elif page == "Order Execution":      page_order_execution()
    elif page == "Strategy Library":     page_strategy_library()
    elif page == "Broker Settings":      page_broker_settings()
    elif page == "Watchlist":            page_watchlist()
    else:                                page_market_snapshot(nse500)

if __name__ == "__main__":
    main()