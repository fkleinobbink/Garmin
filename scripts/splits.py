"""Per-km splits en laps uit een Garmin FIT-bestand (zip of .fit)."""
import io, zipfile

import fitdecode


def _fit_bytes(blob: bytes) -> bytes:
    if blob[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".fit"))
            return z.read(name)
    return blob


def _pace(sec, meters):
    if not meters:
        return None
    s = sec / (meters / 1000)
    return f"{int(s // 60)}:{int(round(s % 60)):02d}"


def parse(blob: bytes) -> dict:
    records, laps = [], []
    with fitdecode.FitReader(io.BytesIO(_fit_bytes(blob))) as fr:
        for fr_ in fr:
            if not isinstance(fr_, fitdecode.FitDataMessage):
                continue
            g = lambda f: fr_.get_value(f, fallback=None)
            if fr_.name == "record":
                ts, dist = g("timestamp"), g("distance")
                if ts is None or dist is None:
                    continue
                alt = g("enhanced_altitude")
                records.append((ts.timestamp(), dist, g("heart_rate"),
                                alt if alt is not None else g("altitude"), g("cadence")))
            elif fr_.name == "lap":
                t, d = g("total_timer_time"), g("total_distance")
                cad = g("avg_running_cadence") or g("avg_cadence")
                laps.append({"km": round((d or 0) / 1000, 2), "tijd_s": round(t or 0),
                             "tempo": _pace(t or 0, d), "hs": g("avg_heart_rate"),
                             "hs_max": g("max_heart_rate"),
                             "stijging": g("total_ascent"), "daling": g("total_descent"),
                             "cadans": cad * 2 if cad and cad < 120 else cad})

    # per-km uit records, op afstand; pauzes (gaten > 10 s) tellen niet mee
    splits = []
    if records:
        moving, prev = 0.0, records[0]
        seg_start_t, seg_start_alt, hrs = 0.0, prev[3], []
        next_km = 1000.0
        for rec in records[1:]:
            dt = rec[0] - prev[0]
            if 0 < dt <= 10:
                moving += dt
            if rec[2]:
                hrs.append(rec[2])
            while rec[1] >= next_km:
                frac = (next_km - prev[1]) / (rec[1] - prev[1]) if rec[1] > prev[1] else 1
                t_at = moving - (dt if 0 < dt <= 10 else 0) * (1 - frac)
                alt = rec[3]
                splits.append({"km": len(splits) + 1, "tijd_s": round(t_at - seg_start_t),
                               "tempo": _pace(t_at - seg_start_t, 1000),
                               "hs": round(sum(hrs) / len(hrs)) if hrs else None,
                               "hoogte": round(alt - seg_start_alt) if alt is not None and seg_start_alt is not None else None})
                seg_start_t, seg_start_alt, hrs = t_at, alt, []
                next_km += 1000
            prev = rec
        rest = records[-1][1] - (next_km - 1000)
        if rest > 50:
            splits.append({"km": round(rest / 1000, 2), "tijd_s": round(moving - seg_start_t),
                           "tempo": _pace(moving - seg_start_t, rest),
                           "hs": round(sum(hrs) / len(hrs)) if hrs else None,
                           "hoogte": round(records[-1][3] - seg_start_alt) if records[-1][3] is not None and seg_start_alt is not None else None})
    return {"km_splits": splits, "laps": laps}
