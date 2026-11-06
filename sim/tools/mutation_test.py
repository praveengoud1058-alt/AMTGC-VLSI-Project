#!/usr/bin/env python3
"""Mutation test: inject known bugs into copies of rtl/ and check that tb/tb_amtgc_top.v catches them.
Run from the repository root:  python3 sim/tools/mutation_test.py [names...]
Each mutant must be reported DETECTED. A MISSED result means the testbench cannot see that defect.
Every mutant, including the fixed-priority arbiter (M3), is expected to be DETECTED by the system testbench.
"""
import os, shutil, subprocess, sys
ROOT = os.getcwd()
RTL = ['generic_timer.v', 'junction_controller.v', 'ped_arbiter.v', 'amtgc_top.v']
TB = os.path.join(ROOT, 'tb', 'tb_amtgc_top.v')
VSIM = os.path.join(ROOT, 'sim', 'tools', 'vsim.py')
IVERILOG = shutil.which('iverilog')      # real Icarus Verilog when installed, else the bundled simulator
TIMEOUT = 300                            # seconds per mutant
MUTANTS = {
 'M1_no_timer_restart': [('junction_controller.v', "assign timer_start = timer_run & ~phase_entry;", "assign timer_start = timer_run;")],
 'M2_density_continuous': [('junction_controller.v', "if (phase_entry && (state == S_NS_GREEN))", "if (state == S_NS_GREEN)")],
 'M3_fixed_priority': [('ped_arbiter.v', "assign grant_a = req_a & (~req_b | ~prefer_b);", "assign grant_a = req_a;")],
 'M4_no_pending_clear': [('junction_controller.v', "else if (ped_req_out && ped_grant)", "else if (1'b0)")],
 'M5_no_emergency_mask': [('junction_controller.v', "if (emergency_override) begin\n            next_state = S_EMERGENCY;", "if (1'b0) begin\n            next_state = S_EMERGENCY;")],
 'M6_gw_one_early': [('amtgc_top.v', "gw_sr[GW_DELAY_CYCLES-2];", "gw_sr[GW_DELAY_CYCLES-3];")],
 'M7_no_reset_gate': [('junction_controller.v', "        if (rst_n) begin\n            case (state)", "        if (1'b1) begin\n            case (state)")],
 'M8_no_allred_gap': [('junction_controller.v', "S_EW_YELLOW: if (tdone)      next_state = S_ALL_RED_2;", "S_EW_YELLOW: if (tdone)      next_state = S_NS_GREEN;")],
 'M9_no_gw_wait_after_emg': [('junction_controller.v', "localparam [3:0]   RESUME_STATE    = IS_JUNCTION_B ? S_GW_WAIT : S_ALL_RED_1;", "localparam [3:0]   RESUME_STATE    = S_ALL_RED_1;")],
 'M10_emg_2cycle_latency': [('junction_controller.v', "            next_state = S_EMERGENCY;             // 1-cycle latency to all-red", "            next_state = (state == S_EMERGENCY) ? S_EMERGENCY : state;")],
 'M11_unsynced_reset': [('amtgc_top.v', "wire       rst_n_sync = rst_sync[1];", "wire       rst_n_sync = rst_n;")],
 'M12_walk_without_grant': [('junction_controller.v', "if (ped_req_out && ped_grant)\n                ped_serve <= 1'b1;", "if (ped_req_out)\n                ped_serve <= 1'b1;")],
 'M13_pointer_moves_every_grant': [('ped_arbiter.v', "else if (req_a & req_b)\n            prefer_b <= ~prefer_b;", "else if (grant_a)\n            prefer_b <= 1'b1;\n        else if (grant_b)\n            prefer_b <= 1'b0;")],
 'M14_slot_not_sent_to_B': [('amtgc_top.v', ".ped_slot_in        (ped_slot),\n        .ped_slot_out       (),", ".ped_slot_in        (1'b0),\n        .ped_slot_out       (),")],
}
names = sys.argv[1:] or list(MUTANTS)
for name in names:
    d = os.path.join('/tmp', 'mut_' + name)
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    for f in RTL: shutil.copy(os.path.join(ROOT, 'rtl', f), d)
    ok = True
    for fn, old, new in MUTANTS[name]:
        p = os.path.join(d, fn); s = open(p).read()
        if s.count(old) != 1:
            print(f'{name}: PATCH NOT APPLIED'); ok = False; break
        open(p, 'w').write(s.replace(old, new))
    if not ok: continue
    files = [os.path.join(d, f) for f in RTL]
    if IVERILOG:
        vvp = os.path.join(d, 'mut.vvp')
        c = subprocess.run([IVERILOG, '-g2005', '-o', vvp] + files + [TB], capture_output=True, text=True)
        if c.returncode != 0:
            print(f'{name:28s} COMPILE-ERROR (not counted as detected) {c.stderr.strip()[:80]}', flush=True)
            continue
        try:
            out = subprocess.run(['vvp', '-n', vvp], capture_output=True, text=True, timeout=TIMEOUT).stdout
        except subprocess.TimeoutExpired:
            out = '[FAIL] harness timeout after %d s\n' % TIMEOUT
        engine = 'iverilog'
    else:
        out = subprocess.run([sys.executable, VSIM, '-T2000000'] + files + [TB], capture_output=True, text=True).stdout
        engine = 'vsim'
    fails = [l for l in out.splitlines() if l.startswith('[FAIL]') or 'WATCHDOG' in l]
    verdict = 'DETECTED' if fails else 'MISSED'
    print(f'{name:28s} {verdict:9s} [{engine}] {fails[0][:90] if fails else ""}', flush=True)
