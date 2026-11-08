# §5 Generation-Requirement Deltas (sibling-spec note, 2026-11-08)

Evidence from battery m0b-baseline-frozen182 + clean p0 probe (0/400 kit fails):

1. **Naturals tagged stratum (owner vote):** twin must emit a per-episode natural-breakdown tag
   (§5 stratification keys extension) so the battery can stratify natural vs injected DOWN.
2. **Incipient-rung coverage:** delay/loss/quality incipient episodes (3/5, 3/4, 3/4) were ALL missed.
   If the trained pool also misses incipient, the H2-A2 branch fires: rebalance the ladder toward
   incipient representation or concede the rung explicitly.
3. **Kit-outcome taxonomy sufficient:** 0/400 clean kit fails; CUSUM p0 locked at 1/402 (Laplace).
   No new kit event types required for the quality expert.
4. **Score persistence is now a runner contract:** `--dump-dir` persists max-machine quantile scores +
   root-window labels per episode (VUS-PR primary needs scores, not just hits).
5. **Lower-fence follow-up:** unfenced low-obs alarms need machine-state corroboration at generation
   time (state_hist_delta already exported — sufficient; no new twin keys).
