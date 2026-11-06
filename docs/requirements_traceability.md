# Requirements traceability

Each requirement from the six task descriptions, where it is satisfied, and its honest status.

Status: **Done** = implemented and checked by a self-checking test or a mechanical check.
**Partial** = done, with the stated limit. **Not done** = not produced.

Every "checked" below was run with the bundled simulator `sim/tools/vsim.py`, not with a commercial simulator (see
`docs/verification_report.md`, section 1).

## Task 1: architecture planning

| Requirement | Evidence | Status |
|---|---|---|
| Two junctions with NS/EW sequencing and a green wave (B's NS green a defined delay after A's) | `architecture_final.md` §4; green-wave offset measured on 855 entries in `tb_amtgc_top` | Done |
| Shared pedestrian arbiter, fair choice of who is served first | `architecture_final.md` §1a, §7; `tb_ped_arbiter`; S4/S8 in `tb_amtgc_top` | Done |
| One emergency input, both junctions all-red within a stated number of cycles | 1 clock cycle, `architecture_final.md` §8; checked every cycle by monitor M4 and in S5 | Done |
| Block diagram of every module and connection | `architecture_final.md` §1 | Done (ASCII diagram) |
| Interface of every module: inputs, outputs, purpose | `architecture_final.md` §2 | Done |
| Why each module is separate | `architecture_final.md` §1a | Done |
| Why the pedestrian controller is shared | `architecture_final.md` §1a | Done |
| Simultaneous requests without starvation | `architecture_final.md` §1a, §7 | Done |
| Clocking strategy (single domain) | `architecture_final.md` §10 | Done |
| Sync or async reset, justified | `architecture_final.md` §9; async assert, sync release | Done |
| Verification plan with at least 15 scenarios | `verification_plan.md`: 36 rows | Done |

## Task 2: parameterised RTL

| Requirement | Evidence | Status |
|---|---|---|
| Moore FSM junction_controller with NS green/yellow, all-red, EW green/yellow, optional pedestrian phase | `rtl/junction_controller.v`; state diagram in `architecture_final.md` §3 | Done |
| generic_timer independent, parameter COUNTER_WIDTH, inputs start/count_target, output done | `rtl/generic_timer.v` | Done |
| Controller parameters GREEN_TIME, YELLOW_TIME, RED_TIME, PED_TIME | `YELLOW_TIME`, `RED_TIME`, `PED_TIME` as specified. `GREEN_TIME` is expressed as `BASE_GREEN` + `MIN_GREEN` + `MAX_GREEN` + `DENSITY_STEP` (needed for Task 4) | Done (name differs for green) |
| Both junctions from the same module with different values | `amtgc_top.v` instantiates A and B with different `BASE_GREEN`/`DENSITY_STEP` | Done |
| No hard-coded numbers in the FSM logic | All timing from parameters or localparams; state and light codes are localparams; the last numeric literal (`32'd1`) was replaced by `MIN_TIMER_TARGET`. Remaining literals are 1-bit flags and reset values | Done |
| Non-blocking assignments in sequential logic | Mechanically checked: no blocking `=` in any clocked block | Done |
| Default in every case statement | Mechanically checked: 3 case statements, 3 defaults | Done |
| Defined reset value for every register | Reset branches in all clocked blocks | Done |
| No timer logic duplicated in the FSM | The FSM only drives `start` and `count_target` | Done |
| Timer testbench with at least three parameter values, testbench unmodified | `tb_generic_timer` at COUNTER_WIDTH 4, 8, 12, via the command line | Done |
| Junction testbench: full sequence and pedestrian requests | `tb_junction_controller` (64 checks, 59 phases) | Done |
| Corner cases: count_target = 0, reset during counting, request during yellow | `tb_generic_timer` (T=0, async reset), `tb_junction_controller`, S3c | Done |
| Non-zero all-red gap between conflicting directions | `RED_TIME` = 3; mutant M8 (gap removed) is caught | Done |
| Waveforms of the timer and of the junction controller on their own | `docs/waveforms/05_generic_timer.png`, `06_junction_controller.png`: drawn from simulator traces, 29 asserted checks; not ModelSim screenshots | Partial |

## Task 3: integration

| Requirement | Evidence | Status |
|---|---|---|
| amtgc_top with two junctions, their timers, and ped_arbiter | `rtl/amtgc_top.v` | Done |
| Fair arbitration, not fixed priority | Contest-only round-robin; mutants M3 and M13 caught at system level | Done |
| Emergency override: bounded, held until released | 1 cycle; S5; monitor M4 | Done |
| Strict hierarchy, no flattening | Four separate files | Done |
| Named port connections only | Mechanically checked: no positional connections | Done |
| ped_arbiter sees only requests and grants | Ports: `req_a`, `req_b`, `grant_a`, `grant_b` | Done |
| Green-wave measured in simulation | Monitor M5 on every B entry (855) | Done |
| Integration testbench: both junctions, simultaneous requests, no starvation | `tb_amtgc_top` S3b, S4, S8 | Done |
| Waveforms: green-wave offset, fair arbitration | `docs/waveforms/01_*.png`, `03_*.png` | Partial (see Task 5) |
| Corner case: repeated simultaneous requests | S4 (40 pairs), S8 (120 pairs) | Done |
| Corner case: override during an active pedestrian phase | S5 "ACTIVE walk" tests, both junctions | Done |
| Corner case: safe resume after the override | S5; B re-locks 4 cycles behind A | Done |
| Follows the declared reset strategy | 2-flop synchroniser; S6 checks assertion and release | Done |

## Task 4: traffic-adaptive timing

| Requirement | Evidence | Status |
|---|---|---|
| 3-bit traffic_density per junction | `density_a`, `density_b` | Done |
| Green grows with density, within min and max | `ns_green_dur()`; sweep S2; figure 02 | Done |
| generic_timer not modified | `cmp` against the original upload: byte-identical | Done |
| Target computed in the controller | `architecture_final.md` §6a | Done |
| Limits as parameters | `MIN_GREEN`, `MAX_GREEN`, `DENSITY_STEP`, `BASE_GREEN` | Done |
| Diagram of where the calculation sits, and why not in the timer | `architecture_final.md` §6a | Done |
| Density sweep of every value, cap never exceeded | S2 (A: 0 to 7, B: 7 to 0), figure 02 | Done |
| Green wave valid across different density combinations | Monitor M5 over the sweep and the random run; model: all 64 pairs | Done |
| Written statement on whether generic_timer changed | `architecture_final.md` §6a: No | Done |
| Density change during green documented | Sampled once at NS-green entry | Done |
| Both directions at maximum density, neither starved | NS 24 and EW 6 (the minimum guaranteed) | Done |

East-west green is the complement of north-south green, not an independent adaptive value (documented trade-off).

## Task 5: verification

| Requirement | Evidence | Status |
|---|---|---|
| One unified self-checking testbench | `tb/tb_amtgc_top.v` | Done |
| Every planned scenario covered | `verification_plan.md` | Done (see the waveform row) |
| Bugs documented, fixed, traced to the earlier decision | `bug_log.md` | Done |
| Directed tests and a random test; size justified | 20 000 random cycles; justification in `verification_report.md` §7a | Done |
| ModelSim simulation log with pass/fail | Not produced. `sim/logs/*.log` come from the bundled simulator | Not done |
| Waveform screenshots: normal, emergency, arbitration, adaptive timing | `docs/waveforms/*.png`: real traces of the RTL, plotted with annotations asserted by script. They are not ModelSim screenshots | Partial |
| Coverage statement: plan against what was run | `verification_plan.md` | Done |
| Override during every traffic phase | S5: every phase of A and of B, plus GW_WAIT, plus an active walk | Done |
| Arbitration fairness over more than 100 requests | S8: 120 contested pairs | Done |
| Green wave across at least five density combinations | Sweep (8 combinations) and the random run | Done |
| Reset asserted during a running simulation | S6 | Done |
| Override toggled with no gap | S5 toggle loop | Done |

## Task 6: documentation and delivery

| Requirement | Evidence | Status |
|---|---|---|
| Repository with /rtl, /tb, /docs, /sim | This folder | Done |
| README with features, tools, exact commands | `README.md` | Done (commands not yet run under iverilog) |
| Final architecture, block and state diagrams | `architecture_final.md` | Done (one state diagram covers both junctions: B differs only in its start state) |
| Technical report: decisions, trade-offs, verification, bugs, improvements | `TECHNICAL_REPORT.md` | Done |
| Demonstration video | `docs/demo/AMTGC_demo_captioned.mp4`: **silent** (no audio track), captioned slides with figures. It does not show a live run, the RTL source, or a terminal | Partial: spoken live-demo video not produced |
| RTL in the repository identical to the verified version | The suite, the cross-check and all mutants were rerun on the final files | Done |
| Waveforms, screenshots and logs archived with meaningful names | `docs/waveforms/`, `sim/logs/` | Partial (no ModelSim output) |
| Public GitHub repository | Not produced | Not done |

## Not confirmed

Nothing has been run in iverilog or ModelSim. The bundled simulator is two-state (no X propagation) and covers a subset
of Verilog-2005, and it has not been validated against a commercial tool.
