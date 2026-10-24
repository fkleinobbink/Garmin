"""Haalt Garmin-data op via garmin-personal-mcp en schrijft JSON naar de repo.

1. Sync: laatste DAYS dagen -> data/daily/<datum>.json, data/activities/<datum>_<id>.json
   (inclusief splits), data/latest.json (compact overzicht).
2. Requests: elk bestand requests/<naam>.json = {"tool": "garmin_get_...", "args": {...}}
   of een lijst daarvan -> responses/<naam>.json, request wordt daarna verwijderd.
"""
import asyncio, datetime as dt, json, os, pathlib, traceback

from garmin_personal_mcp import server

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, REQ, RESP = ROOT / "data", ROOT / "requests", ROOT / "responses"
DAYS = int(os.environ.get("DAYS", "14"))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


async def call(tool, **args):
    fn = getattr(server, tool)
    try:
        return await fn(**args)
    except Exception as exc:  # één fout mag de rest niet slopen
        return {"error": f"{type(exc).__name__}: {exc}"}


async def sync():
    today = dt.date.today()
    start = (today - dt.timedelta(days=DAYS - 1)).isoformat()
    end = today.isoformat()

    for d in range(DAYS):
        day = (today - dt.timedelta(days=d)).isoformat()
        dump(DATA / "daily" / f"{day}.json", await call("garmin_get_day", date=day))

    acts = await call("garmin_search_activities", start=start, end=end, limit=100)
    overview = []
    for a in acts.get("results", []):
        aid = a.get("activityId")
        date = str(a.get("startTimeLocal", ""))[:10]
        path = DATA / "activities" / f"{date}_{aid}.json"
        if not path.exists() or date >= (today - dt.timedelta(days=2)).isoformat():
            detail = await call("garmin_get_activity", activity_id=aid)
            dump(path, {"summary": a, "detail": detail})
        overview.append({k: a.get(k) for k in (
            "activityId", "activityName", "startTimeLocal", "distance", "duration",
            "averageHR", "maxHR", "averageSpeed", "elevationGain", "calories",
            "aerobicTrainingEffect", "anaerobicTrainingEffect", "trainingEffectLabel",
            "activityType") if k in a})

    dump(DATA / "latest.json", {
        "synced_utc": dt.datetime.utcnow().isoformat(timespec="seconds"),
        "range": [start, end],
        "activities": overview,
        "sleep": await call("garmin_get_sleep_summaries", start=start, end=end),
        "hrv": await call("garmin_get_hrv_summaries", start=start, end=end),
    })


async def requests():
    for f in sorted(REQ.glob("*.json")):
        try:
            spec = json.loads(f.read_text())
            specs = spec if isinstance(spec, list) else [spec]
            out = [{"tool": s["tool"], "args": s.get("args", {}),
                    "result": await call(s["tool"], **s.get("args", {}))} for s in specs]
            dump(RESP / f.name, out if isinstance(spec, list) else out[0])
        except Exception:
            dump(RESP / f.name, {"error": traceback.format_exc()})
        f.unlink()


async def main():
    await requests()
    await sync()

asyncio.run(main())
