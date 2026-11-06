# Adaptive Multi-Junction Traffic Grid Controller (AMTGC)

Start here: `SUBMISSION.md` (what to run and what is still open). Datasets: none, see `DATASETS.md`.

A parameterised RTL implementation of two coordinated four-way traffic junctions with a
green wave, a shared pedestrian arbiter, an emergency override and traffic-adaptive
green timing.

## Repository layout

| Path | Contents |
|---|---|
| `rtl/` | Synthesizable Verilog-2005 sources: `generic_timer.v`, `junction_controller.v`, `ped_arbiter.v`, `amtgc_top.v` |
| `tb/` | Self-checking testbenches. Each prints `[PASS]` / `[FAIL]` and a final `RESULT:` line |
| `sim/` | Run scripts (`run_all_sims.sh`, `run_all_sims.bat`), commands, logs, and the Python cycle model |
| `sim/python_model/` | Independent Python model of the RTL equations and its regression scripts |
| `sim/tools/` | `vsim.py` (Python Verilog-subset simulator), mutation tests, RTL-vs-model cross-check |
| `docs/` | Architecture and state diagrams, assumptions, bug log, verification plan and report, technical report, requirements traceability, checklist |
| `docs/waveforms/` | Waveform figures drawn from real RTL traces (not ModelSim screenshots) |

## Features

- Two junctions from one parameterised `junction_controller`, with different timing parameters.
- Exact phase lengths: NS green, yellow, all-red, EW green, yellow, all-red, pedestrian slot.
- Green wave: Junction B starts its north-south green exactly `GW_DELAY_CYCLES` (default 4) cycles after Junction A.
- Traffic-adaptive north-south green (3-bit density) with minimum and maximum clamps. East-west green is the complementary share of a fixed budget.
- Shared pedestrian arbiter: both junctions request in the same cycle (shared pedestrian slot), one walk per slot, round-robin on contests, no starvation.
- Emergency override: both junctions all-red one clock cycle after the override is sampled high.
- Asynchronous reset with synchronous release.

## Required tools

- Icarus Verilog 11 or later (`iverilog`, `vvp`) for the testbenches, or ModelSim/Questa.
- Python 3.8 or later for the optional cycle model (standard library only).

## How to reproduce the results

From the repository root:

```bash
# 1. Run every self-checking testbench (Icarus Verilog)
bash sim/run_all_sims.sh
# Uses iverilog if installed, otherwise the bundled vsim.py. Expect "ALL TESTBENCHES PASSED".
# Logs are written to sim/logs/.

# 2. Single system-level run
iverilog -g2005 -o sim/build/top.vvp rtl/generic_timer.v rtl/junction_controller.v rtl/ped_arbiter.v rtl/amtgc_top.v tb/tb_amtgc_top.v
vvp -n sim/build/top.vvp | tail -12

# 3. generic_timer with three parameter values, same testbench file
iverilog -g2005 -Ptb_generic_timer.COUNTER_WIDTH=4 -o sim/build/t4.vvp rtl/generic_timer.v tb/tb_generic_timer.v
vvp -n sim/build/t4.vvp

# 4. ModelSim / Questa
vlib work
vlog rtl/generic_timer.v rtl/junction_controller.v rtl/ped_arbiter.v rtl/amtgc_top.v tb/tb_amtgc_top.v
vsim -c tb_amtgc_top -do "run -all; quit -f"

# 5. Mutation tests (every mutant should report DETECTED)
python3 sim/tools/mutation_test.py

# 6. Waveform figures (needs matplotlib)
bash sim/tools/make_waveforms.sh

# 7. Independent Python cycle model and RTL cross-check (no HDL tool needed)
python3 sim/python_model/regression_units.py
python3 sim/python_model/regression_system.py
python3 sim/tools/xcheck_model.py
```

## Parameters

Top level (`amtgc_top`): `COUNTER_WIDTH` (8), `GW_DELAY_CYCLES` (4, must be ≥ 2).

Per junction (`junction_controller`): `BASE_GREEN`, `MIN_GREEN`, `MAX_GREEN`, `DENSITY_STEP`,
`YELLOW_TIME`, `RED_TIME`, `PED_TIME`, `IS_JUNCTION_B`.

Constraint: the two junctions must use the same `MIN_GREEN`, `MAX_GREEN`, `YELLOW_TIME`,
`RED_TIME` and `PED_TIME`, or the green wave will not hold. Minimum phase length is 3 cycles.

Default values: Junction A `BASE_GREEN=6, DENSITY_STEP=3`; Junction B `BASE_GREEN=9, DENSITY_STEP=2`;
both `MIN_GREEN=6, MAX_GREEN=24, YELLOW_TIME=3, RED_TIME=3, PED_TIME=5`.

## Status

- All testbenches pass on the delivered RTL, run with the bundled Python simulator (`sim/tools/vsim.py`). See `docs/verification_report.md`.
- 14 of 14 injected mutant bugs are caught by the system testbench (`sim/tools/mutation_test.py`), including a fixed-priority arbiter.
- Pedestrian arbitration is exercised in the integrated system: 120 contested pairs, 120 walks per junction, first-served junction alternating on every contest.
- Independent Python cycle model and RTL simulation agree cycle-for-cycle over a 200-cycle stimulus (`sim/logs/xcheck_result.txt`).
- Not yet confirmed under iverilog or ModelSim. Run `bash sim/run_all_sims.sh` with iverilog installed; it uses iverilog automatically if present.
- Waveform figures: six figures in `docs/waveforms/`, drawn from simulator traces (not ModelSim screenshots). Not included: ModelSim screenshots and log, and a spoken live-demo video. `docs/demo/AMTGC_demo_captioned.mp4` is a silent slide video with no audio track.
- `docs/requirements_traceability.md` lists every requirement with its evidence and status, including what is not done.
- Known trade-offs are in `docs/bug_log.md` (OI-02, OI-03, OI-05, OI-06, OI-07).

See `docs/architecture_final.md` for the design, `docs/bug_log.md` for the defects found
in the earlier version and how they were fixed, and `docs/verification_report.md` for
exactly what was run.
