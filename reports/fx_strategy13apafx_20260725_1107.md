# Advanced Price Action wedge-breakout on FX MAJORS (strategy #13-fx) - 2026-07-25 10:18 UTC

RESEARCH ONLY - nothing deploys. Same wedge-breakout engine as gold, pooled across a 7-pair basket; M1=scalping, M5=intraday, each judged on an UNTOUCHED holdout.
pairs ['EUR_USD', 'GBP_USD', 'AUD_USD', 'NZD_USD', 'USD_JPY', 'USD_CHF', 'USD_CAD'] - select 2024-07-01..2025-12-31 - holdout <= 2024-06-30

### M1

Selection grid (spent window):
- atr_mult=1.5, target_r=2.0, trend_filter=False: 5448t, -0.251R, PF 0.729
- atr_mult=1.5, target_r=2.0, trend_filter=True: 5435t, -0.239R, PF 0.741
- atr_mult=1.5, target_r=3.0, trend_filter=False: 5414t, -0.23R, PF 0.783
- atr_mult=1.5, target_r=3.0, trend_filter=True: 5395t, -0.229R, PF 0.781
- atr_mult=2.5, target_r=2.0, trend_filter=False: 4382t, -0.246R, PF 0.701
- atr_mult=2.5, target_r=2.0, trend_filter=True: 3644t, -0.217R, PF 0.732
- atr_mult=2.5, target_r=3.0, trend_filter=False: 4290t, -0.249R, PF 0.709
- atr_mult=2.5, target_r=3.0, trend_filter=True: 3577t, -0.225R, PF 0.73

Verdict: FAIL
- winner: atr_mult=2.5, target_r=2.0, trend_filter=True
- selection: 3644t, -0.217R, PF 0.732
- HOLDOUT (untouched judge): 18458t, win 30.7%, -0.24R, PF 0.729, 0/26q+, maxDD $75,865.93
- holdout GROSS (0 spread): 18933t, -0.022R (spread eats +0.218R)
- bootstrap 90% CI: [-0.255, -0.224]R, P(>0)=0% -> CI includes 0
- walk-forward: 0/6 folds+ (-0.266, -0.264, -0.201, -0.265, -0.193, -0.239)
- slippage: 1.0x -> -0.24R | 2.0x -> -0.332R
- 2026 reference (CONTAMINATED): 1577t, -0.356R

### M5

Selection grid (spent window):
- atr_mult=1.5, target_r=2.0, trend_filter=False: 4926t, -0.158R, PF 0.801
- atr_mult=1.5, target_r=2.0, trend_filter=True: 4322t, -0.13R, PF 0.83
- atr_mult=1.5, target_r=3.0, trend_filter=False: 4730t, -0.143R, PF 0.814
- atr_mult=1.5, target_r=3.0, trend_filter=True: 4182t, -0.113R, PF 0.844
- atr_mult=2.5, target_r=2.0, trend_filter=False: 1450t, -0.129R, PF 0.84
- atr_mult=2.5, target_r=2.0, trend_filter=True: 1078t, -0.114R, PF 0.867
- atr_mult=2.5, target_r=3.0, trend_filter=False: 1433t, -0.109R, PF 0.869
- atr_mult=2.5, target_r=3.0, trend_filter=True: 1072t, -0.09R, PF 0.899

Verdict: FAIL
- winner: atr_mult=2.5, target_r=3.0, trend_filter=True
- selection: 1072t, -0.09R, PF 0.899
- HOLDOUT (untouched judge): 5595t, win 35.5%, -0.147R, PF 0.764, 1/26q+, maxDD $33,302.5
- holdout GROSS (0 spread): 5620t, -0.044R (spread eats +0.103R)
- bootstrap 90% CI: [-0.173, -0.122]R, P(>0)=0% -> CI includes 0
- walk-forward: 0/6 folds+ (-0.168, -0.156, -0.109, -0.152, -0.162, -0.126)
- slippage: 1.0x -> -0.147R | 2.0x -> -0.219R
- 2026 reference (CONTAMINATED): 520t, -0.12R
