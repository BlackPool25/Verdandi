# Registers (companion to Charter)
## Stakeholder Register
| ID | Name/Role | Power (H/M/L) | Interest (H/M/L) | Engagement | Source |
|---|---|---|---|---|---|
| STK-001 | 2–4 person BTech team (builders/operators) | H | H | leading | V1-§1 |
| STK-002 | Operators (fix root in <3 steps) | M | H | supportive | V1-§1 |
| STK-003 | Professor — economic buyer, marks | H | H | supportive | V1-§1 |
| STK-004 | Lab infra / ROCm drivers — blocker | M | M | neutral | V1-§1 |
| STK-005 | Seniors IoT/ICS + Grafana-rule hackers — channel | L | M | neutral | V1-§1 |
## Risk Register
| ID | cause | event | consequence | owner | trigger | status |
|---|---|---|---|---|---|---|
| RSK-001 | friction+distribution (Predix $4–7B burn) | prod twin upkeep demanded | semester sink | Lead | upkeep linear in services | mitigating |
| RSK-002 | inverted economics (Uptake $2.3B→160) | $/incident exceeds $0.50 | uneconomic demo | Lead | $/incident >$0.50 | mitigating |
| RSK-003 | friction (Twitter-AD archived) | integration exceeds budget | missed milestones | Team | integration > calibration budget | open |
| RSK-004 | premature (EGADS stale) | fixed thresholds collapse | F1 drop >30pts | Team | F1 drop>30pts fixed→adaptive | mitigating |
| RSK-005 | distribution (TensorZero archived) | topology/layout egress | trust burn | Lead | egress/topology leak | mitigating |
| RSK-006 | no caps ($47K agent loop) | uncapped LLM calls | cost blowout | Team | uncapped calls observed | mitigating |
| RSK-007 | scale OOM (GAD-in-wild 500k–1M) | full-graph replay OOM | demo crash | Team | RSS growth >5% | mitigating |
| RSK-008 | threshold/collapse fragility (TCN-GAT SWaT 0.886→0.281) | causal instability AC@1<30%/flip>40% | wrong rank | Team | AC@1<30% or flip>40% | mitigating |
| RSK-009 | partial-plant sim gap | unmodeled machine/buffer hides root | unattributable alarm | Team | plant coverage <32/32 machines or any partition × channel × class cell empty | open |
