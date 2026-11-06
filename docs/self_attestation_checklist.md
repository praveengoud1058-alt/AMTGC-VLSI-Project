# Self-attestation checklist

Legend: [x] done and checked, [~] done, checked only with the bundled simulator, [ ] not done.

- [x] Task 1: architecture, interfaces, shared-arbiter rationale, clocking and reset decision, verification plan with 34 behavioural scenarios (`docs/architecture_final.md`, `docs/verification_plan.md`).
- [x] Task 2: generic_timer unmodified and independent. junction_controller parameterised; no timing constants in the FSM; default cases; non-blocking sequential logic. Timer testbench runs at three widths.
- [x] Task 3: amtgc_top with two junctions, one shared ped_arbiter, emergency override, green-wave link. Named port connections throughout. The arbiter resolves contested requests in the integrated system (pedestrian slot).
- [x] Task 4: adaptive timing with min/max clamps; timer unchanged; density sampled once per cycle (documented); both-directions-at-maximum case tested. East-west green is the complement of north-south green (documented trade-off).
- [~] Task 5: self-checking unified testbench (`tb/tb_amtgc_top.v`) passes under vsim; 14/14 injected bugs caught at system level. Confirm under iverilog/ModelSim.
- [~] Task 5: 20 000-cycle constrained-random run in the testbench.
- [~] Task 5: integrated arbitration fairness over more than 100 requests: 120 contested pairs, 120 walks each, first-served alternates on every contest.
- [~] Task 5: waveform figures (normal operation, emergency, arbitration, adaptive timing) in `docs/waveforms/`, drawn from real RTL traces.
- [ ] Task 5: ModelSim simulation log and ModelSim screenshots. Not produced (no GUI tool).
- [x] Task 2: standalone waveform images for the timer and the junction controller: `docs/waveforms/05_generic_timer.png`, `06_junction_controller.png` (drawn from simulator traces).
- [ ] Task 6: spoken demonstration video showing a live run. Not produced. `docs/demo/AMTGC_demo_captioned.mp4` is silent and does not meet the requirement.
- [ ] Task 6: public GitHub repository. Not produced; this folder is the repository content.
- [x] Task 6: README, architecture and state diagrams, technical report, bug log, assumptions, verification plan and report, mutation and cross-check logs.
- [x] Requirements traceability table (`docs/requirements_traceability.md`).
- [x] Bug log updated, including CHG-01 and the new open issues OI-05 to OI-07.
- [~] RTL in `rtl/` is the version that passes the bundled testbenches. Re-run under iverilog/ModelSim before final submission.
