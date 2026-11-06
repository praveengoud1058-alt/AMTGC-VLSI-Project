# Verification report

This report lists what was run, with what tool, and what each result means.

## 1. Tools used

| Tool | Status | Used for |
|---|---|---|
| Icarus Verilog | **Run once, on v6, by the repository owner** (screen recording, `docs/evidence/`): the six testbench runs PASS. Not run on the files in this archive. `sim/run_all_sims.sh` uses it automatically if installed. | Real-simulator check of the testbenches (v6 only) |
| ModelSim | **Not run.** No ModelSim log or screenshots exist. | Required by the VLSI rules; still to produce |
| `sim/tools/vsim.py` | **Run.** Event-driven Verilog-2005 subset simulator written for this project (Python 3, standard library only). Covers the constructs used in `rtl/` and `tb/`. | All testbench runs below |
| `sim/python_model/` | **Run.** Independent Python cycle model of the same design equations. | Cross-check of the RTL (section 4) |

Limits of `vsim.py`: two-state logic (registers start at 0, no X propagation), no
timescale handling (delays are in plain time units), and a subset of the language
(no generate blocks, no `signed` declarations beyond those used here). It has not been
validated against a commercial simulator. Running the testbenches under iverilog or
ModelSim is the recommended confirmation.

## 2. Testbench results (RTL as delivered)

Command: `bash sim/run_all_sims.sh` (engine: vsim).

| Testbench | Named checks | Result | Notes |
|---|---|---|---|
| `tb_generic_timer` COUNTER_WIDTH = 4 | 22 | PASS | Same file, parameter set on the command line |
| `tb_generic_timer` COUNTER_WIDTH = 8 | 22 | PASS | |
| `tb_generic_timer` COUNTER_WIDTH = 12 | 22 | PASS | |
| `tb_junction_controller` | 5 named, 64 total | PASS | Also checks every phase length and order (59 phases observed) |
| `tb_ped_arbiter` | 12 | PASS | Lone requests, alternation, starvation bound, contest-only pointer |
| `tb_amtgc_top` | 37 named, 11 450 total | PASS | 42 978 cycles monitored; 855 green-wave entries verified; 450 A and 290 B walks; 20 000-cycle random section; 120 contested pedestrian pairs (S8); override during an active walk for A and B |

"Total" counts include per-cycle invariant checks, which print only on failure.

## 3. Mutation testing (does the testbench catch real bugs?)

Command: `python3 sim/tools/mutation_test.py`. Log: `sim/logs/mutation_test.log`.
Each mutant is a copy of `rtl/` with one injected defect.

| Mutant | Injected defect | First failing check |
|---|---|---|
| M1 | Timer not restarted between phases (BUG-01) | phase length |
| M2 | Density sampled every green cycle (BUG-02) | phase length |
| M3 | Fixed-priority pedestrian arbiter (BUG-03) | S4: first-served junction does not alternate |
| M4 | Pending pedestrian flag never cleared | S3a |
| M5 | Emergency ignored by the FSM | emergency latency |
| M6 | Green-wave offset one cycle short | green wave |
| M7 | Outputs not forced red during reset (BUG-12) | S6 |
| M8 | No all-red gap after EW yellow | phase order |
| M9 | Junction B does not wait for green wave after override | green wave |
| M10 | Override takes two clock cycles to reach all-red | emergency latency |
| M11 | Reset not synchronised | S6 release timing |
| M12 | Walk started without a grant | S3b |
| M13 | Arbiter pointer moves on every grant (last-served, not contest-based) | S4: first-served junction does not alternate |
| M14 | Pedestrian slot not delivered to Junction B | S3b |

**Result: 14 of 14 mutants are caught by the system testbench.** The earlier version of this design
missed M3 at system level because the two junctions' requests never met at the arbiter. The pedestrian
slot (CHG-01) fixes that, and the alternation checks in S4 and S8 are what catch M3 and M13. The arbiter's
own testbench also catches M3.

## 4. Cross-check against the independent Python model

`sim/tools/xcheck_tb.v` drives the RTL with a fixed stimulus (pedestrian requests at cycles
10, 12, 60, including a contested press at 60 and one at 10/12; density change at cycle 50; emergency at cycles 80–82). `sim/tools/xcheck_model.py`
runs the Python cycle model with the same stimulus. The per-cycle light and walk outputs
of both are in `sim/logs/xcheck_*`.

Result: **identical over 200 cycles**. The two implementations were written separately, so
agreement is evidence that the RTL implements the intended equations and that vsim
simulates the RTL faithfully on this stimulus.

## 5. Python model regression (independent of the RTL text)

| Regression | Checks | Result |
|---|---|---|
| `sim/python_model/regression_units.py` | 78 | 78 PASS |
| `sim/python_model/regression_system.py` | 31 | 31 PASS |

## 6. Bugs found during verification

Listed in `docs/bug_log.md`. Found by simulation and mutation testing: BUG-12 (lights not red
during reset), CHG-01 (arbiter not exercised in the integrated system), BUG-13 and BUG-14 (testbench and
simulator defects, corrected).

## 7. Coverage against the Task 1 plan

See `docs/verification_plan.md`. All behavioural scenarios (1 to 34) have a checking test.
Scenario 35 is partial: `docs/waveforms/` has six figures (01 to 06) drawn from real RTL traces (not ModelSim screenshots;
see `docs/waveforms/README.md`), and there is no ModelSim log.

## 7a. Randomised test: size and justification

The system testbench's constrained-random section (S7) runs **20 000 clock cycles**: about 1 % chance of an override
per cycle, about 8 % chance of a pedestrian press per junction per cycle, and a new random density for both junctions
every cycle. A signal cycle is 47 cycles, so 20 000 cycles is about 425 signal cycles.

Why that length: the section is meant to hit every (phase, event) combination many times, not just once. Measured on the
Python model with the same distribution (the Verilog run uses `$random`, so the exact sequence differs):

| Quantity | Measured over 20 000 cycles |
|---|---|
| Override assertions | 194 |
| Overrides hitting each phase of Junction A (min over phases) | 8 (NS yellow); NS green 57, EW green 68 |
| Overrides hitting each phase of Junction B (min over phases) | 5 (EW yellow); GW_WAIT 46 |
| Pedestrian press edges, Junction A | about 1 475 |
| Contested slots (both junctions requesting together) | about 248 |
| Densities seen at NS-green entry | all 8 (0 to 7) |

Fewer cycles would leave some (phase, override) pairs hit only once or twice. More cycles add runtime (the Python
simulator runs about 1 500 cycles per second) and, past this point, repeat the same combinations. The random section checks
the same invariants as the directed tests on every cycle: no conflicting greens, walk only with all lights red, all-red one
cycle after an override, the green-wave offset on every entry, and one walk per accepted request.

## 8. Integrated arbitration fairness (S4 and S8)

S8 applies 120 simultaneous pedestrian presses from A and B, 110 cycles apart (two signal cycles plus margin,
because one walk is served per slot). Results: 120 walks for each junction; in every pair the two walks go to
different junctions; the junction served first alternates on every one of the 120 contests. S4 does the same
for 40 pairs. These checks are what a fixed-priority arbiter cannot pass.

## 8a. Waveform figures

`docs/waveforms/` holds six figures drawn from per-cycle traces of the RTL. Every number on them is computed from the
trace and asserted by `sim/tools/plot_waveforms.py` (32 checks, all PASS, `sim/logs/waveform_checks.txt`). Drawing the first
version of the emergency figure showed that an override had hit a pedestrian *slot* with no walk in it. The testbench had
only asserted an override in the PED state, not during a walk. Directed tests for an override during an active walk
(Junction A and Junction B) were added to `tb_amtgc_top`, and they pass.

## 8c. v7 changes

- Watchdog in every testbench (BUG-15); deliberate-hang self-test ends with RESULT: FAIL by design.
- Standalone Task-2 waveforms for generic_timer and junction_controller (05, 06; 29 checks).
- Mutation runner uses iverilog when installed, with a timeout per mutant. The 14 results in `sim/logs/mutation_test.log`
  are from the bundled simulator; the iverilog mutation run is still to be done.
- Demonstration video `docs/demo/AMTGC_demo_captioned.mp4` (138 s, silent: no audio track, captioned slides; not a live demonstration).

## 9. Still to do before submission

- Run `bash sim/run_all_sims.sh` under iverilog or ModelSim and confirm every log shows PASS.
- Produce waveform screenshots and a ModelSim log (Task 5 deliverables).
