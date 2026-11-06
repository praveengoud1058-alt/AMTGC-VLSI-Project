#!/bin/bash
# Regenerate every waveform trace and figure (needs python3 + matplotlib). Run from the repository root.
# Engine: iverilog if installed, otherwise the bundled sim/tools/vsim.py.
set -e
if command -v iverilog >/dev/null 2>&1; then
    run_sim() { iverilog -g2005 -o sim/build/wave.vvp "$@" && vvp -n sim/build/wave.vvp; }
else
    run_sim() { python3 sim/tools/vsim.py -T5000000 "$@"; }
fi
mkdir -p sim/build sim/logs
# system-level scenario (figures 01 to 04)
run_sim rtl/generic_timer.v rtl/junction_controller.v rtl/ped_arbiter.v rtl/amtgc_top.v sim/tools/wave_tb.v \
    | grep "^W," | sed 's/^W,//' > sim/logs/wave_trace.csv
python3 sim/tools/plot_waveforms.py
# standalone timer and junction controller (figures 05 and 06)
run_sim rtl/generic_timer.v rtl/junction_controller.v sim/tools/wave_units_tb.v \
    | grep -E "^[TJ]," > sim/logs/wave_units_trace.csv
python3 sim/tools/plot_waveforms_units.py
