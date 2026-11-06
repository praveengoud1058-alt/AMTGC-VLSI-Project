# Submission guide

## What this repository is

A parameterised RTL implementation of an Adaptive Multi-Junction Traffic Grid Controller (AMTGC): two coordinated
four-way junctions with a green wave, a shared pedestrian arbiter, an emergency override, and traffic-adaptive green timing.
Start with `README.md`. Design details are in `docs/architecture_final.md`.

## Check it in five minutes

From the repository root:

```bash
bash sim/run_all_sims.sh            # all testbenches; expect "ALL TESTBENCHES PASSED"
bash sim/tools/make_waveforms.sh    # regenerates docs/waveforms/*.png (needs matplotlib)
python3 sim/tools/mutation_test.py  # 14 injected bugs; each should print DETECTED
```

`run_all_sims.sh` uses Icarus Verilog (`iverilog`) if it is installed. Otherwise it uses `sim/tools/vsim.py`, a Python
simulator written for this project, which covers the Verilog subset used here.

## What is verified, and how

| Item | Evidence | Status |
|---|---|---|
| Testbenches pass | `sim/logs/tb_*.log` (generated with vsim for v11); the owner's recorded iverilog run (`docs/evidence/`) was on **v6** | Passed under vsim for v11; passed under iverilog for v6 only |
| Injected bugs caught | `sim/logs/mutation_test.log`, 14 of 14 | Passed under vsim. **Under iverilog not yet completed** (a timeout after 4 mutants was recorded) |
| Green wave, adaptive timing, arbitration, emergency, reset | System testbench S1–S8 and the random section S7 | Passed under vsim |
| RTL matches an independent Python model | `sim/logs/xcheck_result.txt` (200 cycles) | Identical |
| Standalone timer and junction controller | `docs/waveforms/05_*.png`, `06_*.png`, 29 asserted checks | Passed |
| Testbenches always terminate | Watchdog in every testbench; `sim/logs/watchdog_selftest.log` | Confirmed |
| `generic_timer.v` unmodified | Byte-identical to the original submission | Confirmed |

## Open items

1. Run `bash sim/run_all_sims.sh` and `python3 sim/tools/mutation_test.py` with `iverilog` installed, and keep the logs.
2. ModelSim log and screenshots: not produced.
3. Spoken live-demo video: not produced. `docs/demo/AMTGC_demo_captioned.mp4` is a silent slide video (no audio track) and does not show a live run.

## Trade-offs (documented in `docs/bug_log.md`, OI-02 to OI-07)

- East-west green is the complement of north-south green, not an independent adaptive value.
- Under simultaneous pedestrian demand, one walk is served per signal cycle (47 cycles apart).
- A walk cut off by an emergency override is not repeated.
