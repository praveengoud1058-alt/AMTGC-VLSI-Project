#!/bin/bash
# Runs every self-checking testbench. Uses Icarus Verilog if installed (iverilog/vvp),
# otherwise falls back to sim/tools/vsim.py (a Python Verilog-subset simulator in this repo).
# Usage (repository root):  bash sim/run_all_sims.sh
set -u
mkdir -p sim/logs sim/build
status=0
if command -v iverilog >/dev/null 2>&1; then ENGINE=iverilog; else ENGINE=vsim; fi
echo "engine: $ENGINE"

run() {  # run <name> <top-or-plusargs> <files...>
    local name=$1; shift
    local log="sim/logs/$name.log"
    if [ "$ENGINE" = iverilog ]; then
        iverilog -g2005 -o "sim/build/$name.vvp" "$@" || { echo "COMPILE ERROR: $name"; status=1; return; }
        vvp -n "sim/build/$name.vvp" > "$log"
    else
        python3 sim/tools/vsim.py -T100000000 "$@" > "$log" 2>&1
    fi
    if grep -q "RESULT: FAIL" "$log" || grep -q "\[FAIL\]" "$log" || grep -q "ERROR" "$log"; then
        echo "FAIL: $name  (see $log)"; status=1
    else
        echo "PASS: $name  ($(grep -c '\[PASS\]' "$log") named checks passed; see the RESULT line in the log for totals)"
    fi
}

# generic_timer: same testbench file at three parameter values (no testbench edits)
for w in 4 8 12; do
    if [ "$ENGINE" = iverilog ]; then P="-Ptb_generic_timer.COUNTER_WIDTH=$w"; else P="-Ptb_generic_timer.COUNTER_WIDTH=$w"; fi
    run tb_generic_timer_w$w $P rtl/generic_timer.v tb/tb_generic_timer.v
done
run tb_junction_controller rtl/generic_timer.v rtl/junction_controller.v tb/tb_junction_controller.v
run tb_ped_arbiter         rtl/ped_arbiter.v tb/tb_ped_arbiter.v
run tb_amtgc_top           rtl/generic_timer.v rtl/junction_controller.v rtl/ped_arbiter.v rtl/amtgc_top.v tb/tb_amtgc_top.v

if [ $status -eq 0 ]; then echo "ALL TESTBENCHES PASSED"; else echo "SOME TESTBENCHES FAILED"; fi
exit $status
