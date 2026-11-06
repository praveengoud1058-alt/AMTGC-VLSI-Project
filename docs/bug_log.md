# Bug log

Each entry gives the symptom, the root cause, the design decision that caused it, and the fix.
The first set (BUG-01 to BUG-08) was found in a review of the previous submission.
The earlier log said these were resolved. Some were not, and some were never
fixed at all; the earlier log is superseded.

| ID | Where | Symptom | Root cause | Traced to decision | Fix |
|---|---|---|---|---|---|
| BUG-01 | junction_controller + generic_timer | After the first green, every later phase lasted about one clock cycle. Yellow and all-red were effectively skipped. | `timer_start` was held high in every active state. The timer clears only when `start` is low, so `done` stayed high across phase boundaries. | Task 2 timer interface: `start` is the only clear, and the FSM never used it between phases. | Each phase starts with a one-cycle entry in which `start` is low. The stale `done` is masked during that cycle. Timer loaded with `duration - 2`. Phase lengths are now exact (verified for all densities in the Python model; Verilog run pending, see verification_report.md). |
| BUG-02 | junction_controller | Green time changed while green was active (the "mid-phase jitter" the log had marked resolved). | `latched_density` was written on every cycle with `next_state == NS_GREEN`, which is also true while staying in NS green. | Task 4 requirement: density must not be sampled continuously during green. | Density is written only on the entry cycle of NS green. Held for the whole signal cycle. Verified by sending random density every cycle (system test S2b). |
| BUG-03 | ped_arbiter + junction_controller | Junction A could hold the pedestrian grant indefinitely. Junction B was starved while A's request input stayed high. | Grant held while `req_a` was high. Junction request was a latch that is re-set by a held input, so it never dropped. | Task 3 requirement: round-robin or starvation-proof arbitration. The earlier arbiter used a priority rule and had no release condition. | Requests are edge-detected into `ped_pending`, which clears only when granted. Arbiter is round-robin with a pointer that moves only on contests, with combinational grants. Starvation bound: one slot behind the other junction. |
| BUG-04 | junction_controller + amtgc_top | Green wave held only for the first cycle after reset. After an emergency, B's link was lost and the junctions drifted. | Junction B left `S_STARTUP` on the first pulse and never waited again. Emergency cleared the delay line without resynchronising B. | Task 3 requirement: green wave must hold through the run. | B returns to `GW_WAIT` after reset and after every override. Cycle length is constant (BUG-05), so the offset then holds exactly. |
| BUG-05 | junction_controller | Offset between A and B depended on densities and on pedestrian phases. | Cycle length varied with density (NS+EW green not fixed) and with pedestrian service (PED slot skipped when no request). | Task 4 concern: adaptivity must not break coordination. | Fixed cycle: NS green = clamp(...), EW green = MIN+MAX-NS. Pedestrian slot always present; walk only if granted. Trade-off documented in the technical report. |
| BUG-06 | junction_controller | A single pedestrian button press could produce two walks, or none, depending on timing. | `ped_req_out` cleared only in PED, and was re-set by a level input in the same cycle. | Task 2 corner case: a request in yellow must be neither lost nor serviced twice. | Edge detection and pending flag (see BUG-03). Verified: held level gives one walk; request in yellow gives one walk. |
| BUG-07 | amtgc_top | Reset documentation said synchronous de-assertion, but the code had none. | Assumptions document and implementation disagreed. | Task 1 reset decision was recorded but not implemented. | 2-flop reset synchroniser added. Junctions and arbiter reset from `rst_n_sync`. |
| BUG-08 | testbenches | The old reports (1,240 checks, "100% PASS") could not detect BUG-01 to BUG-06. Several tests only checked a pure function (`calc_green_time`) or only the order of lights. Some printed PASS with no FAIL path. | Testbench design: ordering checks, bounds on a helper function, no phase-length checks, no starvation test. | Task 5 requirement: self-checking, measuring the real behaviour. | All testbenches rewritten to measure durations, offset, safety, pedestrian accounting, fairness, emergency latency and resets. Each prints PASS or FAIL. |
| BUG-09 | tb_generic_timer | Timer testbench gave up after 300 edges, so a 12-bit target could not complete. | Hard-coded timeout. | My own error found while adding the three-width run. | Timeout raised to 10000 edges. |
| BUG-10 | junction_controller | `RED_TIME` default of 2 gave a 2-cycle red that the timer could not realise. | Timer needs at least 3 cycles per phase with the entry-cycle scheme (see BUG-01). | Fix for BUG-01. | Default `RED_TIME` = 3, minimum phase length documented as 3 cycles. |
| BUG-11 | junction_controller | ped request was ignored during emergency, so it was lost after release. | `ped_req_out` was cleared while `emergency_override` was high. | Task 5 corner case: no request may be lost. | Pending flag is kept during emergency and cleared only by service or reset. Verified in system test S3e. |

| BUG-12 | junction_controller | While reset was asserted during a green phase, Junction A's lights showed NS green (reset state is NS green and lights came straight from the state register). | Output logic had no reset term. Found by the junction testbench reset check, run in the simulator. | Safety: outputs must be all-red during reset. | Lights and walk are forced to all-red while `rst_n` is low (combinational, immediate). |
| BUG-13 | tb_amtgc_top (monitor) | Phase-length monitor reported false failures in the random run. | Monitor recorded NS-entry density only for valid cycles; an NS entry on the same cycle as an override was skipped. The design was correct (it latches density on the entry edge). | Harness error, not a design error. | Monitor now records every NS-green entry. |
| CHG-01 | junction_controller, ped_arbiter, amtgc_top, tb | The shared arbiter never resolved a contest in the integrated system. A fixed-priority arbiter passed the system testbench (mutant M3 missed). | Each junction raised its request at its own decision point. The green wave places those 4 cycles apart, so the two requests never met at the arbiter. Found by mutation testing. | Task 3: the arbiter must resolve simultaneous requests fairly. The earlier design satisfied this only inside the arbiter testbench. | Pedestrian slot: Junction A's decision strobe is distributed to both junctions (`ped_slot`), so both present requests in the same cycle. One walk per slot; the loser keeps its request for the next slot. Arbiter pointer moves only on contests. System testbench now checks that the first-served junction alternates over 120 contested pairs. All 14 mutants, including M3, are now detected at system level. |
| BUG-14 | (simulator + tb) | Early simulator runs used the wrong timer width and ignored the testbench's parameter overrides. | Simulator bugs (task `integer` inputs sized 1 bit; body-level parameters ignored `-P`). | Not a design defect; recorded for transparency. | Fixed in the simulator and rechecked. |
| BUG-15 | all testbenches; sim/tools/mutation_test.py | In the owner's iverilog session the mutation run hit its timeout (exit 124) after 4 of 14 mutants. A fault that stops a `wait()` from completing would make a testbench run forever. | The testbenches had no watchdog. The bundled simulator's `-T` limit hid this; iverilog has no such limit. | Task 5: a self-checking testbench must always finish and report. | Each testbench ends with `[FAIL] watchdog` and `RESULT: FAIL` at a fixed time. `sim/tools/watchdog_selftest_tb.v` (a deliberate hang) ends with RESULT: FAIL on its own (`sim/logs/watchdog_selftest.log`). The mutation harness uses iverilog when installed, with a per-mutant timeout, and reports compile errors separately. |

## Open issues (not fixed; documented)

- OI-01 (resolved by CHG-01): the arbiter's tie-break is now exercised in the integrated system.
  History: with each junction requesting at its own decision point, the two requests never coincided,
  and a fixed-priority arbiter passed the system testbench. The pedestrian slot (CHG-01) makes both
  junctions request in the same cycle.
- OI-02: A fixed pedestrian slot costs `PED_TIME` cycles of vehicle time per signal
  cycle, even when no pedestrian is waiting. This is the price of the constant cycle.
- OI-03: After a system-wide override, Junction B waits in all-red for up to one
  full signal cycle, until A's next NS green. The lights stay safe; the delay is bounded.
- OI-04: Pedestrian requests that arrive in the same cycle merge into one walk, and so
  do requests that arrive while one is pending. A pedestrian is never left without a walk,
  but two presses in a short window produce one walk.
- OI-05: Under simultaneous demand the shared pedestrian resource is a bottleneck. One walk is
  served per signal cycle in total, so when both junctions have a pending request each is served every
  second signal cycle (47 cycles apart at the default parameters). This follows from the arbiter
  serving one request per slot, which is what makes the arbitration observable. A deployment that wants
  both junctions served in one cycle would need a second slot, or a PED slot that serves both.
- OI-06: A walk that is in progress when the emergency override arrives is cut short and is not
  repeated. The request was already consumed when the walk was granted. A walk that was granted but had
  not started (Junction B, between the slot and its PED slot) is kept and walked after the override.
- OI-07: `GW_DELAY_CYCLES` is limited to `YELLOW_TIME + RED_TIME + MIN_GREEN` so that the slot strobe
  reaches Junction B while it is armed. This is a documented parameter constraint, not checked by an
  assertion in the RTL.
