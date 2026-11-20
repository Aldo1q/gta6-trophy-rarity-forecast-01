"""GTA VI trophy rarity forecaster (make.fun: gta6-trophy-rarity-forecast-01).

Reads one case file from the input directory: the house's recorded reads of
Exophase's GTA VI (PS5) trophy page up to a checkpoint, and writes, for every
trophy in the case, five quantiles (5/25/50/75/95) of its earn rate at the
case's target time, in percent.

Model, in one paragraph: work on the logit scale against ln(1 + hours since
release). For each trophy, fit a recency-weighted least-squares line to its
logit rate over the recorded reads, shrink the slope toward the mean slope of
trophies sitting in the same rate band (and toward the global mean slope),
damp the extrapolation by the square root of the log-time stretch, blend the
fitted level with the last observed rate, and cap the total move. The spread
combines a horizon term, the pooled fit residuals inflated by the
extrapolation leverage, and a floor, so the band is honest about how far the
target sits beyond the data. See METHODOLOGY.md for the full reasoning.

Standard library only, no network, fully deterministic: the same case always
produces the same bytes.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

RATE_LO = 0.01
RATE_HI = 99.99
HALF_LIFE_H = 20.0        # recency weighting of reads, hours
WINDOW_H = 72.0           # fit only reads this close to the last one
BAND_W = 5.0              # slope-shrinkage weight toward the rate-band mean
GLOBAL_W = 2.0            # slope-shrinkage weight toward the global mean
LEVEL_BLEND = 0.4         # weight of the raw last rate in the fitted level
MOVE_CAP = 2.3            # largest |logit move| the median may make
RW_COEF = 0.40            # horizon spread floor, logit per sqrt(day)
STEP_W = 0.6              # weight of the measured step volatility in the spread
SIGMA_FLOOR = 0.30        # irreducible spread, logit
SIGMA_MIN = 0.22
SIGMA_MAX = 2.20
LEV_CAP = 3.0


def clamp_rate(x: float) -> float:
    return min(RATE_HI, max(RATE_LO, x))


def logit(pct: float) -> float:
    p = clamp_rate(pct) / 100.0
    return math.log(p / (1.0 - p))


def inv_logit(y: float) -> float:
    if y >= 0:
        return 100.0 / (1.0 + math.exp(-y))
    e = math.exp(y)
    return 100.0 * e / (1.0 + e)


def round4(x: float):
    """Round to 4 decimals, half up; whole numbers come back as int."""
    v = math.floor(x * 10000.0 + 0.5) / 10000.0
    return int(v) if v == int(v) else v


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def anchor_time(case: dict, first_read: datetime) -> datetime:
    """Release midnight UTC from the case's game block, else the first read."""
    rel = (case.get("game") or {}).get("release_date")
    if rel:
        try:
            d = datetime.fromisoformat(str(rel))
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            pass
    return first_read


def hours_since(anchor: datetime, when: datetime) -> float:
    return max(0.0, (when - anchor).total_seconds() / 3600.0)


class Fit:
    """One trophy's weighted logit-vs-log-time fit and its forecast pieces."""

    __slots__ = ("n", "last_y", "last_x", "level", "slope", "sxx",
                 "resid", "xbar", "sw", "band")

    def __init__(self) -> None:
        self.n = 0
        self.last_y = None
        self.last_x = 0.0
        self.level = None
        self.slope = 0.0
        self.sxx = 0.0
        self.resid = 0.0
        self.xbar = 0.0
        self.sw = 0.0
        self.band = 0


def fit_trophy(points):
    """points: list of (x, y, w) with x = ln(1 + hours), y = logit rate."""
    f = Fit()
    f.n = len(points)
    if not points:
        return f
    f.last_x, f.last_y, _ = points[-1]
    f.band = int(math.floor(f.last_y / 1.5))
    sw = sum(w for _, _, w in points)
    xbar = sum(w * x for x, _, w in points) / sw
    ybar = sum(w * y for _, y, w in points) / sw
    sxx = sum(w * (x - xbar) ** 2 for x, _, w in points)
    sxy = sum(w * (x - xbar) * (y - ybar) for x, y, w in points)
    f.sxx = sxx
    if sxx > 1e-9:
        f.slope = sxy / sxx
    f.level = ybar + f.slope * (f.last_x - xbar)
    f.xbar = xbar
    f.sw = sw
    if f.n >= 3 and sw > 0:
        var = sum(w * (y - (ybar + f.slope * (x - xbar))) ** 2
                  for x, y, w in points) / sw
        f.resid = math.sqrt(max(var, 0.0))
    return f


def forecast_case(case: dict) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"levels {case['levels']} != {LEVELS}")
    history = case["history"]
    if not history:
        raise ValueError("case has no history")
    trophies = case["trophies"]

    read_times = [parse_time(r.get("slot") or r["at"]) for r in history]
    anchor = anchor_time(case, read_times[0])
    target_x = math.log1p(hours_since(anchor, parse_time(case["target"])))
    last_t = read_times[-1]
    horizon_days = case["horizon_minutes"] / 1440.0

    # Build each trophy's weighted point cloud once, collecting the pooled
    # step volatility (per-sqrt-day logit moves between consecutive reads)
    # on the way: the page moves in refresh steps, and their size is the
    # honest scale of what a horizon of the same length can do.
    fits = []
    step_terms = []
    for i in range(len(trophies)):
        pts = []
        prev = None
        for j, read in enumerate(history):
            rate = read["rates"][i] if i < len(read["rates"]) else None
            if rate is None:
                continue
            age_h = (last_t - read_times[j]).total_seconds() / 3600.0
            if age_h > WINDOW_H:
                continue
            w = 0.5 ** (age_h / HALF_LIFE_H)
            hrs = hours_since(anchor, read_times[j])
            x = math.log1p(hrs)
            y = logit(rate)
            if prev is not None:
                gap_days = max((hrs - prev[0]) / 24.0, 1.0 / 24.0)
                step_terms.append((y - prev[1]) ** 2 / gap_days)
            prev = (hrs, y)
            pts.append((x, y, w))
        fits.append(fit_trophy(pts))
    step_vol = (math.sqrt(sum(step_terms) / len(step_terms))
                if step_terms else 0.0)
    step_vol = min(step_vol, 1.2)
    rw_coef = max(RW_COEF, STEP_W * step_vol)

    # Fallback level for a trophy with no usable reads: the pooled last level.
    known = [f.last_y for f in fits if f.last_y is not None]
    pooled_last = sorted(known)[len(known) // 2] if known else logit(1.0)

    # Slope shrinkage targets: per-band and global SXX-weighted mean slopes.
    band_num, band_den = {}, {}
    g_num = g_den = 0.0
    for f in fits:
        if f.n >= 3 and f.sxx > 1e-9:
            band_num[f.band] = band_num.get(f.band, 0.0) + f.sxx * f.slope
            band_den[f.band] = band_den.get(f.band, 0.0) + f.sxx
            g_num += f.sxx * f.slope
            g_den += f.sxx
    global_slope = g_num / g_den if g_den > 0 else 0.0

    # Pooled residual scale, shrunk per trophy below.
    r_num = r_den = 0.0
    for f in fits:
        if f.n >= 3:
            r_num += f.n * f.resid ** 2
            r_den += f.n
    pooled_resid = math.sqrt(r_num / r_den) if r_den > 0 else 0.35

    rows = []
    for f in fits:
        if f.last_y is None:
            med = pooled_last
            sigma = max(SIGMA_MIN, rw_coef * math.sqrt(horizon_days))
        else:
            slope = f.slope
            if f.n >= 3 and f.sxx > 1e-9:
                bmean = (band_num[f.band] / band_den[f.band]
                         if band_den.get(f.band) else global_slope)
                slope = ((f.sxx * f.slope + BAND_W * bmean
                          + GLOBAL_W * global_slope)
                         / (f.sxx + BAND_W + GLOBAL_W))
            base = (1.0 - LEVEL_BLEND) * (f.level if f.level is not None
                                          else f.last_y) + LEVEL_BLEND * f.last_y
            dx = max(0.0, target_x - f.last_x)
            damp = math.sqrt(f.last_x / target_x) if target_x > 0 else 1.0
            move = slope * dx * damp
            move = max(-MOVE_CAP, min(MOVE_CAP, move))
            med = base + move
            resid_i = ((f.n * f.resid + 8.0 * pooled_resid) / (f.n + 8.0)
                       if f.n >= 3 else pooled_resid)
            if f.n >= 3 and f.sxx > 1e-9:
                lev = math.sqrt(min(LEV_CAP ** 2,
                                    1.0 + 1.0 / max(f.sw, 1e-6)
                                    + (target_x - f.xbar) ** 2 / f.sxx))
            else:
                lev = 1.0
            sigma = math.sqrt((rw_coef * math.sqrt(horizon_days)) ** 2
                              + (resid_i * lev) ** 2 + SIGMA_FLOOR ** 2)
            sigma = min(SIGMA_MAX, max(SIGMA_MIN, sigma))
        qs = []
        prev = 0.0
        for z in Z:
            q = round4(inv_logit(med + z * sigma))
            q = max(prev, min(100.0, float(q)))
            qs.append(int(q) if float(q) == int(q) else q)
            prev = float(q)
        rows.append({"id": trophies[len(rows)]["id"], "q": qs})
    return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        out = forecast_case(case)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
