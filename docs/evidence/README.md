# Evidence from the repository owner's recorded session (18 Oct 2026)

The repository owner ran the v6 package in an Emergent session and recorded the screen. These are frames from that
recording. They are screenshots of a chat transcript, not simulator log files.

| File | What it shows | What it supports |
|---|---|---|
| `rec_iverilog_run_all_sims.png` | `bash sim/run_all_sims.sh` on v6: `engine: iverilog`, PASS for generic_timer at widths 4, 8, 12, junction_controller, ped_arbiter, amtgc_top; `ALL TESTBENCHES PASSED`; `Exit code: 0`. | The six testbench runs compile and pass under Icarus Verilog. |
| `rec_iverilog_mutation_timeout.png` | The mutation run in that session printed `mutation exit: 124` (timeout) after 4 mutants, then "Moving it to background". | The mutation run under iverilog did **not** finish in that session. |

Not shown by the recording: a 14-of-14 mutation result under iverilog, and any ModelSim run. The 14-of-14 result in
`sim/logs/mutation_test.log` comes from the bundled simulator (`engine: vsim`).
