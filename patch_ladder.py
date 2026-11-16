#!/usr/bin/env python3
"""One stop that only moves forward, one bot process, and a $0.25 loss cut."""
import os
import shutil
import py_compile

TARGET = "main.py"
BACKUP = "main.py.bak_ladder"

REPLACEMENTS = [
(
"""    R1_LOCK_PEAK_R = 1.00
    R1_LOCK_STOP_R = 0.40
""",
"""    R1_LOCK_PEAK_R = 1.00
    R1_LOCK_STOP_R = 0.50
    LOSS_CUT_USD = 0.25
    LOSS_CUT_USD_SEC = 15.0
"""
),
(
"""async def replace_close_position_stop(symbol: str, side: str, stop_price: float) -> Optional[dict]:
    \"\"\"
    Binance allows ONE closePosition stop/tp per direction.
    Never place a second until the first is confirmed gone.
    \"\"\"
    if not await wait_close_position_clear(symbol, timeout=7.0):
        return None
    await asyncio.sleep(0.30)
    return await safe_place_order(
        symbol,
        "SELL" if side == "BUY" else "BUY",
        "STOP_MARKET",
        stopPrice=stop_price,
        closePosition=True,
    )
""",
"""_best_stop_px: Dict[str, float] = {}
_instance_lock_fh = None

def _stop_moves_forward(side: str, symbol: str, new_px: float) -> bool:
    old = _best_stop_px.get(symbol)
    if old is None or old <= 0:
        return True
    if side == "BUY":
        return new_px > old
    if side == "SELL":
        return new_px < old
    return False

def hold_single_instance() -> bool:
    global _instance_lock_fh
    import fcntl
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".phoenix.lock")
    fh = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return False
    _instance_lock_fh = fh
    return True

async def replace_close_position_stop(symbol: str, side: str, stop_price: float) -> Optional[dict]:
    \"\"\"
    Binance allows ONE closePosition stop/tp per direction.
    A new stop may only improve the previous one. A worse price is refused
    before the live order is cancelled.
    \"\"\"
    px = float(stop_price)
    if not _stop_moves_forward(side, symbol, px):
        logger.info(f"⛔ stop kept {symbol} | new={px:.8g} held={_best_stop_px.get(symbol)} side={side}")
        return None
    if not await wait_close_position_clear(symbol, timeout=7.0):
        return None
    await asyncio.sleep(0.30)
    order = await safe_place_order(
        symbol,
        "SELL" if side == "BUY" else "BUY",
        "STOP_MARKET",
        stopPrice=stop_price,
        closePosition=True,
    )
    if order:
        _best_stop_px[symbol] = px
    return order
"""
),
(
"""    lock_r = float(getattr(config, "R1_LOCK_STOP_R", 0.40))
""",
"""    lock_r = float(getattr(config, "R1_LOCK_STOP_R", 0.50))
"""
),
(
"""    if trade.get("profit_locked") or trade.get("trailing_activated") or trade.get("ld_early_lock") or trade.get("r1_locked"):
        return
    if float(trade.get("ratchet_r") or 0) >= float(getattr(config, "PROFIT_LOCK_R", 0.20)):
        trade["profit_locked"] = True
        return
""",
"""    if trade.get("profit_locked") or trade.get("trailing_activated") or trade.get("ld_early_lock") or trade.get("r1_locked"):
        return
    if peak_now >= float(getattr(config, "R1_LOCK_PEAK_R", 1.0)):
        return
    if float(trade.get("ratchet_r") or 0) >= float(getattr(config, "PROFIT_LOCK_R", 0.20)):
        trade["profit_locked"] = True
        return
"""
),
(
"""        # 2) Any strategy already tracking a REAL (not reserved) position on this symbol?
        for sn, trades in list(active_trades.items()):
            tr = trades.get(symbol)
            if tr and not tr.get("reserved") and tr.get("entry_price"):
                logger.info(f"🚫 STRICT REJECT {symbol} | already tracked by strategy={sn}")
                occupied_symbols[symbol] = {"strategy": sn, "side": tr.get("side"), "ts": now}
                return False
""",
"""        # 2) Any record, including a reservation, blocks a second order on this symbol.
        for sn, trades in list(active_trades.items()):
            tr = trades.get(symbol)
            if tr:
                logger.info(f"🚫 STRICT REJECT {symbol} | already tracked by strategy={sn}")
                occupied_symbols[symbol] = {"strategy": sn, "side": tr.get("side"), "ts": now}
                return False
"""
),
(
"""                        await lock_open_profit(symbol, trade, peak_now, current_r, entry_price, stop_dist, side)
                        lock_at = float(getattr(config, "LD_EARLY_LOCK_R", 0.55))
""",
"""                        await lock_open_profit(symbol, trade, peak_now, current_r, entry_price, stop_dist, side)
                        await arm_one_r_lock(symbol, trade, entry_price, stop_dist, side)
                        lock_at = float(getattr(config, "LD_EARLY_LOCK_R", 0.55))
"""
),
(
"""                        hard_hit = impulse_hard_confirmed(symbol, trade, current_r)
                        if hard_hit or hit_max_hold or ld_reason or hour_reason or flip_reason:
""",
"""                        usd_loss_hit = False
                        qty_now = float(trade.get("qty") or 0)
                        if qty_now > 0 and entry_price > 0:
                            if side == "BUY":
                                open_usd = (current_price - entry_price) * qty_now
                            else:
                                open_usd = (entry_price - current_price) * qty_now
                            cut_usd = float(getattr(config, "LOSS_CUT_USD", 0.25))
                            if open_usd <= -cut_usd:
                                now_ts = datetime.now(timezone.utc).timestamp()
                                since_usd = trade.get("_usd_loss_since")
                                if not since_usd:
                                    trade["_usd_loss_since"] = now_ts
                                elif now_ts - float(since_usd) >= float(getattr(config, "LOSS_CUT_USD_SEC", 15.0)):
                                    usd_loss_hit = True
                            else:
                                trade["_usd_loss_since"] = None
                        hard_hit = impulse_hard_confirmed(symbol, trade, current_r)
                        if usd_loss_hit or hard_hit or hit_max_hold or ld_reason or hour_reason or flip_reason:
"""
),
(
"""                                    if hard_hit:
                                        reason = "FAST_HARD_SL"
""",
"""                                    if usd_loss_hit:
                                        reason = "LOSS_$0.25"
                                    elif hard_hit:
                                        reason = "FAST_HARD_SL"
"""
),
(
"""    client = await create_binance_client()
    await force_one_way_mode()
""",
"""    client = await create_binance_client()
    if not hold_single_instance():
        logger.error("Another Phoenix process is already running — this copy will exit")
        await send_telegram("⛔ نسخة ثانية لم تعمل. البوت يعمل بالفعل")
        return
    await force_one_way_mode()
"""
),
]


def main():
    if not os.path.exists(TARGET):
        print(f"STOPPED missing {TARGET}")
        return
    shutil.copy2(TARGET, BACKUP)
    text = open(TARGET, encoding="utf-8").read()
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        n = text.count(old)
        if n != 1:
            shutil.copy2(BACKUP, TARGET)
            print(f"STOPPED piece {i} count={n}")
            print(f"restored from {BACKUP} — bot file was not changed")
            return
        text = text.replace(old, new, 1)
    open(TARGET, "w", encoding="utf-8").write(text)
    try:
        py_compile.compile(TARGET, doraise=True)
    except Exception as e:
        shutil.copy2(BACKUP, TARGET)
        print(f"STOPPED compile: {e}")
        print(f"restored from {BACKUP} — bot file was not changed")
        return
    print(f"DONE pieces={len(REPLACEMENTS)}")
    print(f"backup={BACKUP}")


if __name__ == "__main__":
    main()
