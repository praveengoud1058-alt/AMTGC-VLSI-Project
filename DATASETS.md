# Datasets

This project uses **no external datasets**.

- All stimulus is generated inside the testbenches: directed sequences, plus a constrained-random
  section (`tb/tb_amtgc_top.v`, section S7) driven by `$random` with a fixed seed in each simulator.
- The Python model (`sim/python_model/`) and the cross-check (`sim/tools/xcheck_*`) use fixed, written-out stimulus.
- Waveform figures (`docs/waveforms/`) are drawn from traces produced by the simulator. They contain no external data.

If a Google Drive folder is required for submission, it should contain this repository as a zip archive
(`AMTGC_submission_FINAL_v11.zip`) and this statement. No dataset files exist.
