# F5 follow-up for PRISSUE-64 (path layer lever) — PR-time comment draft

> F5 (delay STARVED-mass probe) supporting PRISSUE-64. Gate
> `assert_delay_starved_mass(injected_steps, starved_steps, n_downstream,
> buffer_shield_steps=0.0)` asserts conservation
> (`starved <= injected * n_downstream`) plus visibility
> (`starved + shield >= injected`), with `vacuous`/`shielded`/`visible`
> sides. Pinned cases in `tests/test_possibility.py:71-117`: (4,6,2)→ok
> visible; (2,9,2)→CONSERVATION; (6,1,2,shield=0)→VISIBILITY; (6,1,2,
> shield=6)→ok shielded; (6,0,0)→ok vacuous. Probe lineage:
> `probe_delay.py` on C2 delay episodes (eps 41218/41220/41221/41242/41281/
> 41291; S=3–9 STARVED steps at bufq≈0; ep 41242 the decoupled specimen)
> per `.superpowers/sdd/dx-followups/FINAL-probeassist.md` — steps-to-steps
> with fan-out, shield stays a parameter.
