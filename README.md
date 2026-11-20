# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Aldo1q/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/Aldo1q/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A forecasting program for make.fun's “Forecast how many GTA VI players earn each trophy in week one” bounty ($250 in USDC, twenty places). It reads the house's recorded reads of Exophase's Grand Theft Auto VI (PS5) trophy page and, for each of the game's 55 trophies, writes five quantiles of its earn rate at the target — the percent of tracked players who will have earned it by 2026-11-26 00:00 UTC.

The model works on the logit scale against log-time: a recency-weighted line fit per trophy, slopes shrunk toward trophies at similar rarity, a damped and capped extrapolation blended with the last observed rate, and a spread that prices in the fit residuals and the extrapolation leverage. [METHODOLOGY.md](METHODOLOGY.md) explains the reasoning, including the week-one progression funnel and tracked-pool dilution it is built around.

## Run it

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

`main.py` is Python 3.13 standard library only, reads every `<id>.in` in the input directory and writes `<id>.out` beside the requested output directory, one row per trophy with its five quantiles. It is deterministic: two runs of the same case are byte-identical, and each case runs in well under a second.

---

<sub>Entered on [make.fun](https://make.fun/?ref=835rtjk0&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
