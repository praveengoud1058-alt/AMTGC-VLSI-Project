# AMTGC Technical Report

## 1. Project Overview

The Adaptive Multi-Junction Traffic Grid Controller (AMTGC) controls two four-way junctions on one clock.
Junction A leads and Junction B follows with a fixed four-cycle offset (the green wave), so a platoon released on
A's green reaches B on green. Each junction's north-south green length responds to a 3-bit traffic-density input.
One shared pedestrian arbiter grants walks, an emergency override sends both junctions to all-red within one clock
cycle, and the reset is synchronised.

This report covers the decisions that shaped the design, what they cost, how the design was verified, what went
wrong along the way, and what remains open.

## 2. Architecture

Four modules, each in its own file, communicating only through named ports:

| Module | Role |
|---|---|
| `generic_timer` | Reusable down-counter. Unmodified since the original submission (byte-identical, checked). |
| `junction_controller` | One junction's phase sequencing, density split, pedestrian request latch. Instantiated twice with different parameters. |
| `ped_arbiter` | Shared pedestrian arbiter. Sees only request and grant signals. |
| `amtgc_top` | Reset synchroniser, green-wave delay line, pedestrian-slot strobe, the two junctions and the arbiter. |

Full interfaces, block diagram and the reasoning for each module are in `docs/architecture_final.md`.

**Why the pedestrian controller is shared.** Duplicating it would mean no fairness decision exists: each junction
would serve itself independently, with nothing to verify. A shared arbiter is one resource with one policy.
Its cost is a throughput bottleneck under simultaneous demand (OI-05).

## 3. RTL Design

**Fixed signal cycle.** North-south green is `clamp(BASE + density*STEP, MIN, MAX)` and east-west green is the
remainder of a fixed `MIN + MAX` budget. Every cycle also contains a pedestrian slot, whether or not a walk is
requested. The green wave is exact only if the two junctions have equal cycle lengths, so the cycle length must not
depend on density or on pedestrian service. The constant cycle keeps the offset at exactly four cycles for all 64
density pairs (verified). The cost: `PED_TIME` (5) cycles of pedestrian slot every cycle, and the two directions share
one green budget.

**East-west is the complement of north-south.** The design has one density input per junction. Both directions always
receive between `MIN` and `MAX` cycles, so at maximum density on both directions north-south gets 24 cycles and
east-west gets 6. The limitation is that east-west cannot demand extra green by itself. An independent east-west
input would need a cycle that is re-derived each time, which reintroduces the variable-cycle problem above.

**Density is sampled once per signal cycle**, at the north-south green entry edge, and held for the whole cycle.
Sampling every cycle would make the green length wander while the input changes. The cost is a delay of up to one
signal cycle before a change in traffic reaches the signal.

**Exact phase lengths.** The timer clears only when `start` is low. Each phase therefore begins with one entry cycle in
which `start` is low and the stale `done` is masked. The timer is loaded with `duration - 2`. The timer itself is
unchanged, and each phase lasts exactly its configured length (three cycles minimum).

**Pedestrian requests.** The button is edge-detected and held in a pending flag until granted. A press during yellow
waits for the next slot, so it is neither lost nor served twice. A press that arrives while one is pending merges into
it. Requests pending at reset are discarded; requests pending during an override are kept.

**Shared pedestrian slot and contest-based arbiter.** Junction A emits a strobe in the last cycle of its ALL_RED_2,
and the top level distributes it to both junctions. In that cycle every armed junction with a pending request raises
its request, so both reach the arbiter together. The arbiter grants at most one; the granted junction walks in its next
slot, and the other keeps its request.

The pointer moves only on contested cycles. A last-served rule would fail here: the loser is always served last, so
the pointer would hand the next contest back to the same junction, which is fixed priority in disguise. With the
contest-only pointer the first-served junction alternates A, B, A, B over 120 contested pairs.

**Reset.** Asynchronous assertion, synchronous release through two flip-flops. Outputs are forced to all-red while
reset is asserted, so the lights are safe before the first clock edge.

**Emergency override.** Sampled on every clock; all-red one cycle later. Junction A resumes at all-red 1 with a full red
interval. Junction B resumes in a waiting state and stays all-red until A's next north-south green, which restores the
offset exactly. The cost is up to one signal cycle of extra red on B after an override.

## 4. FSM Design

Each junction is a Moore FSM with nine states:

| State | Lights shown | Duration (default parameters) |
|---|---|---|
| GW_WAIT (Junction B only) | all red | until green-wave pulse |
| NS_GREEN | NS green | 6 to 24, from density |
| NS_YELLOW | NS yellow | 3 |
| ALL_RED_1 | all red | 3 |
| EW_GREEN | EW green | 30 minus NS green |
| EW_YELLOW | EW yellow | 3 |
| ALL_RED_2 | all red | 3 (pedestrian decision point at its end) |
| PED | all red, walk if granted | 5 |
| EMERGENCY | all red | while override is high |

Transitions: the normal cycle is NS_GREEN, NS_YELLOW, ALL_RED_1, EW_GREEN, EW_YELLOW, ALL_RED_2, PED, then NS_GREEN.
Every state can enter EMERGENCY. EMERGENCY leaves to ALL_RED_1 (Junction A) or GW_WAIT (Junction B) on release.
Every change of right-of-way passes through an all-red state, so no direct green-to-green transition exists.
The state diagram is in `docs/architecture_final.md` section 3.

## 5. Verification Methodology

Verification uses self-checking testbenches. Each one measures real behaviour and prints PASS or FAIL: phase lengths and
order, the green-wave offset, safety invariants (no conflicting greens; walk only when all red), pedestrian accounting,
fairness, emergency latency and reset behaviour. Each testbench has a watchdog, so a hang ends as a FAIL.

Test layers:

1. **Standalone:** `tb_generic_timer` run at three counter widths (4, 8, 12) with the same file, `tb_junction_controller`,
   `tb_ped_arbiter`.
2. **System:** `tb_amtgc_top` with directed scenarios S1 to S8 (reset, density sweep, pedestrian cases, contested
   fairness over 40 and 120 pairs, emergency from every phase of each junction and during an active walk, mid-count reset)
   and a 20 000-cycle constrained-random section.
3. **Mutation testing:** 14 known defects injected into copies of the RTL. A mutant counts as detected only if a
   testbench fails.
4. **Cross-check:** the RTL and an independent Python cycle model, compared cycle by cycle.

The testbenches were run under the bundled simulator (`sim/tools/vsim.py`) and, in the repository owner's recorded
session (on v6, not on this archive), under Icarus Verilog. Plan coverage is in `docs/verification_plan.md`.

## 6. Simulation Results

| Result | Value | Source |
|---|---|---|
| Testbench checks (system) | 11 450 checks over 42 978 monitored cycles, 0 errors | `sim/logs/tb_amtgc_top.log` |
| Green-wave entries verified | 855, all offset exactly 4 cycles | system testbench, monitor M5 |
| Pedestrian walks (system) | A 450, B 290; contested pairs: 40 and 120, split evenly | system testbench S4, S8 |
| Standalone checks | timer 22 per width; junction 64; arbiter 12 | per-testbench logs |
| Mutation testing | 14 of 14 detected | `sim/logs/mutation_test.log` (bundled simulator) |
| Cross-check vs Python model | identical for 200 cycles | `sim/logs/xcheck_result.txt` |
| Standalone waveform checks | 29 timer and junction checks; 32 system checks | `sim/logs/waveform_*_checks.txt` |
| Real iverilog run | six testbench runs PASS (repository owner's recorded session on v6) | `docs/evidence/` |

Figures in `docs/waveforms/` show: the green wave (01), the density sweep to the 24-cycle cap (02), contested pedestrian
arbitration (03), emergency override (04), the standalone timer (05) and the standalone junction controller (06).
The figures are drawn from simulator traces, and each annotated number is asserted by script.

The mutation test under iverilog did not finish in the recorded session (timed out after 4 of 14 mutants). Its
14-of-14 result is from the bundled simulator only.

## 7. Challenges Faced

- **Phase lengths collapsed.** The timer was never restarted, so every phase after the first green lasted one cycle.
  A test that checked only the order of the lights could not catch it. The lesson: a timing interface has to be read
  end to end.
- **The arbiter was never contested.** The two junctions' requests were four cycles apart, so a fixed-priority arbiter
  passed every system test. Mutation testing exposed it. The fix was the shared pedestrian slot (section 3).
- **Density sampled continuously.** An earlier log marked this as fixed when it was not. A test that changes density
  every cycle showed it.
- **Pedestrian starvation and double service.** A level input re-set the request latch. Replaced by an edge-detected
  pending flag that clears only on service.
- **The green wave held only once.** Junction B never waited again after its first pulse, so the offset was lost after
  an override. Fixed by making B wait after every reset and override, with a constant cycle so the offset then holds.
- **Reset documented but not implemented.** The documents claimed a synchronised release that the RTL did not have.
  The design and the documents now agree.
- **Lights not red during reset.** Found by the junction testbench. Fixed by forcing outputs to red during reset.
- **Testbenches that could not fail.** Earlier testbenches checked a helper function rather than behaviour, and some
  printed PASS with no FAIL path. Rewritten to measure real behaviour, with watchdogs added later.
- **Tooling defects.** Two bugs in my own simulator and one monitor bug in a testbench produced false failures. Each was
  traced to the harness, not the design, and fixed there.
- **Evidence.** An earlier mutation summary was labelled "under iverilog" when the command had not run iverilog. The
  label was corrected, and the evidence note now states exactly what each recorded frame shows.

The most damaging defects sat between blocks (the timer's clear path, the reset path) and in the testbenches, which
were confirming the wrong things. Each time, a behavioural check found the problem where re-reading the code had not.

## 8. Conclusions

The design meets its specification in simulation. Two junctions run a fixed-cycle signal with a verified four-cycle
green wave, density-adaptive north-south green between configurable limits, a shared pedestrian arbiter that is fair
under contest, an emergency override that reaches all-red in one cycle, and a synchronised reset. The timer is reused
unchanged.

The result is verified by self-checking testbenches, 14 injected defects, and an independent model, but with limits.
Results are from the bundled simulator except the recorded iverilog run of the testbenches. ModelSim has not been run.
No synthesis or timing analysis was done.

Known trade-offs: east-west green is the complement of north-south green; one walk is served per signal cycle under
simultaneous demand; a walk cut by an override is not repeated; `GW_DELAY_CYCLES` is limited by the slot position and is
not checked by an assertion in the RTL.

Next steps, in order of value:
1. Run the full suite and mutation test under iverilog and ModelSim, and keep the logs and screenshots.
2. Serve both junctions in one signal cycle under simultaneous demand, and measure the pedestrian waiting time cost.
3. Use an independent east-west density input, which needs a resynchronisation rule for the green wave.
4. Add formal property checks for the safety invariants.
