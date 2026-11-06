# Waveform figures

These six figures are drawn from a per-cycle trace of the real RTL (`sim/logs/wave_trace.csv`), produced by
`sim/tools/wave_tb.v` under the bundled simulator `sim/tools/vsim.py`. **They are not ModelSim screenshots.**
Every number written on a figure is computed from the trace and asserted by `sim/tools/plot_waveforms.py`
(results in `sim/logs/waveform_checks.txt` for 01 to 04, 32 checks; `sim/logs/waveform_units_checks.txt` for 05 and 06, 29 checks).

| File | Shows |
|---|---|
| `01_normal_operation_green_wave.png` | Both junctions' lights over 100 cycles; Junction B's NS green starts exactly 4 cycles after A's |
| `02_adaptive_timing_density_sweep.png` | Density 0 to 7, then 7 held: NS green 6, 9, 12, 15, 18, 21, 24, then capped at 24 |
| `03_pedestrian_arbitration_fairness.png` | Four simultaneous presses: one grant per slot, the loser served at the next slot, first-served junction alternates A, B, A, B |
| `04_emergency_override.png` | An override during an active walk, one during NS green, and three with no gap: all lights and walks off one cycle later; B re-locks 4 cycles behind A |
| `05_generic_timer.png` | The timer on its own: done after exactly 5, 1, 1 and 3 edges for targets 5, 0, 1 and 3; start low clears it; an asynchronous reset while counting clears it at once and the run restarts |
| `06_junction_controller.png` | The junction controller on its own: NS green 15, yellow 3, all-red 3, EW green 15, yellow 3, all-red 3, pedestrian phase 5; a request during yellow is served once; a request held 20 cycles is served once |

Regenerate: `bash sim/tools/make_waveforms.sh` (needs Python 3 and matplotlib).
For real ModelSim screenshots, load `sim/tools/wave_tb.v` with the four RTL files and `add wave -r /wave_tb/*`.
