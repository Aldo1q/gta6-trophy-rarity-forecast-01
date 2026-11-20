# Methodology — GTA VI week-one trophy rarity forecast

## What is being forecast

For every PlayStation 5 trophy of Grand Theft Auto VI, the percent of
Exophase-tracked players who will have earned it at the case's target. The
final case is cut at the deadline (2026-11-21 11:30 UTC) from every recorded
read since launch night, and its target is 2026-11-26 00:00 UTC — 6,510
minutes (4.52 days) later. Scoring is mean pinball loss on the logit scale
over five quantiles per trophy, so rare and common trophies weigh alike and
an honest spread scores as well as an honest median.

## Why logit against log-time

An earn rate is a ratio, earners over tracked players, and both sides move.
Two forces dominate week one of a big open-world launch, and both are
multiplicative rather than additive:

- **Progression.** The tracked cohort pushes into the game. Story and
  activity trophies accumulate roughly with the logarithm of time played:
  the first day produces the prologue and chapter-one trophies for most of
  the cohort, then each further chapter converts a shrinking share of the
  players who reached the previous one — a funnel with heavy decay.
- **Dilution.** The tracked pool keeps growing after launch, and late
  arrivals start at zero progress. For trophies the early cohort earned
  quickly, pool growth drags the rate down even while earners rise.

On the logit scale against `ln(1 + hours since release)`, the net of those
two forces is close to a straight line over the first week for most
trophies, which is what the model fits. This is the same skeleton as
observed week-one curves for comparable launches: in GTA V and Red Dead
Redemption 2, PSN trophy rarity for early story trophies was already near
its long-run level within days, mid-story trophies climbed steadily through
the first week as the hardcore cohort (heavily over-represented among
Exophase-tracked players) pushed through a 30-plus-hour story, and
completion/platinum rates stayed in the low single digits — the platinum
here sat at 0.63% on launch night, and week-one platinum for a game of this
size is a 1–3% event, not a 10% one. Any model that extrapolates an early
steep slope undamped will promise rates the funnel cannot deliver; that is
the failure this design is built to avoid.

## The model, step by step

For each trophy, from the case's own recorded reads (the sandbox has no
network; all structure must come from the case):

1. **Points.** Every read with a non-null rate for the trophy becomes a
   point `(x, y)`: `x = ln(1 + hours since release)`, `y = logit(rate)`
   with the rate clamped to [0.01, 99.99] as the scorer clamps.
2. **Recency-weighted fit.** Least squares of `y` on `x` over the last 72
   hours of reads, weights halving every 20 hours, so the recent curve
   speaks louder than launch-night chaos (the launch-night page was stale
   for hours, then jumped — the practice cases show exactly that).
3. **Slope shrinkage.** A single trophy's slope is noisy. Each slope is
   shrunk toward the SXX-weighted mean slope of trophies in the same
   last-rate logit band (trophies at similar rarity move alike), and toward
   the global mean slope, with weights 5 and 2 against the trophy's own
   SXX.
4. **Damped, blended median.** The forecast level blends the fitted level
   at the last read (60%) with the raw last rate (40%). The move to the
   target is the shrunk slope times the log-time gap, damped by
   `sqrt(x_last / x_target)` — growth decelerates, so the extrapolated leg
   is shortened — and capped at ±2.3 logit, which already spans moves like
   5% → 36% or 0.6% → 5.7%.
5. **Honest spread.** The standard deviation combines a horizon term
   (0.40·√days, raised to 0.6× the pooled step volatility when the page's
   own read-to-read logit steps — measured per √day across every trophy —
   say the rates are moving faster than that floor), the trophy's fit
   residual — shrunk toward the pooled residual across all trophies —
   inflated by the extrapolation leverage
   `sqrt(1 + 1/W + (x* − x̄)²/SXX)` (capped at 3), and a 0.30 floor for
   everything the line cannot see (pool composition shifts, refresh
   timing). Total spread is clamped to [0.22, 2.20] logit.
6. **Quantiles.** `q_τ = inv_logit(median + z_τ · σ)` at the contest's five
   levels, rounded half-up to 4 decimals, forced non-decreasing.

Trophies with too few usable reads fall back to persistence at the last
rate with the horizon spread; a trophy with no reads at all falls back to
the pooled median last level.

## What this does differently from the house baselines

- Against **persistence**: the median actually follows the measured curve
  instead of freezing launch state for 4.5 days, while the damping and the
  move cap keep it from believing its own extrapolation.
- Against the **curve baseline**: it shrinks slopes across trophies,
  damps by the log-time stretch, blends the fitted level with the last
  observed rate, weights recent reads more, and prices the extrapolation
  leverage into the spread instead of bolting a fixed random-walk band onto
  the line.

## Determinism and limits

Pure float arithmetic over the case file, fixed iteration order, no
randomness, no clock, no network: two runs of a case are byte-identical,
and a case runs in well under a second.
