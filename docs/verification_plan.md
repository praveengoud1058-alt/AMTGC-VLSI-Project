# Verification plan (Task 1 contract) and coverage status

Status key:
- **Model + RTL tb**: checked by the Python cycle model (`sim/python_model/`) AND by a self-checking
  Verilog testbench in `tb/`, run under vsim. Re-run under iverilog/ModelSim for final confirmation.
- **RTL tb (vsim)**: run by the vsim simulator only.
- **Model**: checked only by the Python cycle model in this submission.
- **Not run**: planned but not executed.

Testbench names: `TB-T` = tb_generic_timer, `TB-J` = tb_junction_controller,
`TB-A` = tb_ped_arbiter, `TB-S` = tb_amtgc_top (system).

| # | Scenario | Expected behaviour | Where covered | Status |
|---|---|---|---|---|
| 1 | Reset: both junctions leave reset in a valid state | A in NS green; B waits in GW_WAIT | TB-S S1; model T1 | Model + RTL tb |
| 2 | Every phase lasts its configured length | NS/Y/R/EW/Y/R/PED durations exact at all densities 0..7 | TB-S M1; model T2 | Model + RTL tb |
| 3 | Phase order | GW/NS -> Y -> R -> EW -> Y -> R -> PED -> NS | TB-S M2; TB-J | Model + RTL tb |
| 4 | Green-wave offset | B NS entry exactly 4 cycles after A NS entry, every time | TB-S M5; model T1c, T3 | Model + RTL tb |
| 5 | Green-wave offset across all 64 density pairs | Offset unchanged | Model T3 (64 pairs) | Model |
| 6 | Green-wave offset with density changing every cycle | Offset unchanged; density sampled once per cycle | TB-S S2b; model T3b | Model + RTL tb |
| 7 | Density sweep, NS green non-decreasing and capped at MAX | 6,9,12,15,18,21,24,24 | TB-S S2 (M1); model T4 | Model + RTL tb |
| 8 | Both directions at maximum density | NS 24, EW 6; both ≥ MIN | TB-S S2 (7,7); model T4d | Model + RTL tb |
| 9 | Pedestrian: single request | Exactly one walk, only while lights red | TB-S S3a; model T5a/b | Model + RTL tb |
| 10 | Pedestrian request during yellow | Served once at the next decision point | TB-S S3c; TB-J; model T5c | Model + RTL tb |
| 11 | Held pedestrian level | One walk (edge detect) | TB-S S3d; TB-J; model T5d | Model + RTL tb |
| 12 | Simultaneous requests from A and B | Contested slot: one junction walks in the first slot, the other in the next | TB-S S3b; model T6d | Model + RTL tb |
| 13 | Pedestrian request during emergency | Kept, served after release | TB-S S3e | Model + RTL tb |
| 14 | Fairness, 40 contested request pairs, 110 cycles apart | 40 walks each; walks of a pair go to different junctions; first-served alternates | TB-S S4; model T6a/b | Model + RTL tb |
| 15 | Arbiter: simultaneous requests alternate | Strict A/B alternation, one grant per cycle | TB-A T2; unit model | Model + RTL tb |
| 15b | Arbiter pointer moves only on contests | A lone grant does not skew the next contest | TB-A T4; unit model | Model + RTL tb |
| 16 | Arbiter starvation, worst case (A always requesting) | B granted at least every 2 cycles | TB-A T3; unit model | Model + RTL tb |
| 17 | Arbiter lone requests and idle | Correct grant, no grant when idle | TB-A T1 | Model + RTL tb |
| 18 | Emergency during each phase of A | All red one cycle after override, offset restored after release | TB-S S5 (A states 1..7); model T7 | Model + RTL tb |
| 19 | Emergency during each phase of B | As above | TB-S S5 (B states 1..7) | Model + RTL tb |
| 19b | Emergency during an ACTIVE pedestrian walk (A, then B) | Walk and all lights off after 1 cycle; the cut walk is counted once and not repeated | TB-S S5 ("ACTIVE walk"); waveform figure 04 | RTL tb (vsim) |
| 20 | Emergency while B waits in GW_WAIT | Stays all red, waits for A's next NS | TB-S S5 (GW_WAIT case) | Model + RTL tb |
| 21 | Emergency asserted and released with no gap (toggle every cycle) | No lights on while override high; no lock-up | TB-S S5 (toggle); model T8 | Model + RTL tb |
| 22 | Reset asserted mid-count (asynchronous) | Immediate clear; valid restart; offset re-established | TB-S S6; TB-J; TB-T; model T9 | Model + RTL tb |
| 23 | generic_timer: target 0 | done after one edge; count 0 | TB-T (T=0) | Model + RTL tb |
| 24 | generic_timer: targets 1, 2, mid, max | done after exactly max(T,1) edges | TB-T | Model + RTL tb |
| 25 | generic_timer: start low clears | done and count cleared | TB-T | Model + RTL tb |
| 26 | generic_timer: parameter sweep (widths 4, 8, 12) with unchanged tb | All pass | TB-T run with -P | Model + RTL tb |
| 27 | Safety: NS and EW never green together, walk never with vehicle green | Holds in every cycle | TB-S M3; TB-J; model T10a/b | Model + RTL tb |
| 28 | Emergency latency: lights all red at t+1 after override at t | Holds in every cycle | TB-S M4; model T10c | Model + RTL tb |
| 29 | Constrained-random, 20 000 cycles (1% overrides, 8% pedestrian requests per junction, random densities) | All invariants hold; every request that finds nothing pending gets exactly one walk | TB-S S7; model T10, T11 | Model + RTL tb |
| 30 | Reset-release synchronisation | Junctions released two cycles after raw reset | TB-S S6 (release timing checks) | Model + RTL tb |
| 31 | Outputs all-red while reset asserted | Immediate, no clock needed | TB-S S6; TB-J (reset check) | RTL tb (vsim) |
| 32 | Integrated arbitration fairness, 120 contested pairs (more than 100 per junction) | 120 walks each; each pair split between the junctions; first-served junction alternates on every contest | TB-S S8; model T6e/f/g | Model + RTL tb |
| 33 | No fixed priority in the integrated system | A fixed-priority or last-served arbiter is detected | TB-S S4/S8; mutants M3, M13 | RTL tb (vsim) |
| 34 | One walk per slot | The two grants are never active together | TB-S monitor M7; model T6h | Model + RTL tb |
| 35 | Waveform screenshots and ModelSim GUI logs | Required deliverable for Task 5/6 | `docs/waveforms/*.png` (six figures, drawn from real RTL traces; 61 asserted checks) | Partial: no ModelSim screenshots or log |
| 36 | Testbench always terminates | A hang is reported as FAIL | Watchdog in every testbench; deliberate-hang self-test | RTL tb (vsim) |

Coverage summary: all behavioural scenarios (1 to 34) have a checking test. Scenario 35 is partly met: waveform
figures drawn from real RTL traces are in `docs/waveforms/`, but there are no ModelSim screenshots or ModelSim log
(no GUI tool was available).
