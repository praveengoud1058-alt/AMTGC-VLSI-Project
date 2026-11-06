#!/usr/bin/env python3
"""Draw waveform figures from sim/logs/wave_trace.csv (produced by sim/tools/wave_tb.v).
Every number written on a figure is computed from the trace and asserted here; results go to
sim/logs/waveform_checks.txt. Run from the repository root:  python3 sim/tools/plot_waveforms.py
"""
import csv, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLS = "c emg nsA ewA wA nsB ewB wB slot reqA reqB grA grB pra prb da db stA stB gwA".split()
rows = []
with open("sim/logs/wave_trace.csv") as f:
    for r in csv.reader(f):
        rows.append(dict(zip(COLS, map(int, r))))
N = len(rows)
col = lambda k: [r[k] for r in rows]
LIGHT = {0: "#d9534f", 1: "#f0ad4e", 2: "#5cb85c"}
WALK = {0: "#e8e8e8", 1: "#337ab7"}
OUT = "docs/waveforms"
checks = []

def ok(name, cond, info=""):
    checks.append((name, bool(cond), info))
    if not cond: print("CHECK FAILED:", name, info)

def runs(vals, lo, hi):
    out = []; s = lo
    for i in range(lo + 1, hi + 1):
        if i == hi or vals[i] != vals[s]:
            out.append((s, i - s, vals[s])); s = i
    return out

def lane(ax, y, vals, lo, hi, cmap, label):
    for s, n, v in runs(vals, lo, hi):
        ax.broken_barh([(s, n)], (y, 0.8), facecolors=cmap[v], edgecolors="white", linewidth=0.3)
    ax.text(lo - 0.01 * (hi - lo), y + 0.4, label, ha="right", va="center", fontsize=8)

def digital(ax, y, vals, lo, hi, label, color="#444444"):
    xs = list(range(lo, hi)); ys = [y + 0.8 * vals[i] for i in xs]
    ax.step(xs, ys, where="post", color=color, linewidth=1.2)
    ax.hlines(y, lo, hi, color="#cccccc", linewidth=0.5)
    ax.text(lo - 0.01 * (hi - lo), y + 0.4, label, ha="right", va="center", fontsize=8)

def setup(title, lo, hi, nlanes):
    fig, ax = plt.subplots(figsize=(14, 0.5 * nlanes + 1.8))
    ax.set_xlim(lo, hi); ax.set_ylim(0, nlanes * 1.2)
    ax.set_yticks([]); ax.set_xlabel("clock cycle (after reset release)")
    ax.set_title(title, fontsize=11, loc="left")
    fig.subplots_adjust(left=0.1, right=0.99, top=0.88, bottom=0.14)
    return fig, ax

def entries(state_col, code=1):
    return [i for i in range(1, N) if rows[i][state_col] == code and rows[i - 1][state_col] != code]

stA, stB = col("stA"), col("stB")
nsA, nsB, ewA, ewB = col("nsA"), col("nsB"), col("ewA"), col("ewB")
wA, wB = col("wA"), col("wB")
legend = "light: red / yellow / green     walk: blue"

# ---------------------------------------------------------------- 1. normal operation
lo, hi = 0, 100
# A's NS-green entry is the cycle in which its gw_sync pulse is high (this includes cycle 0 after reset)
aE = [i for i in range(N) if rows[i]["gwA"] and lo <= i < hi]; bE = [e for e in entries("stB") if lo <= e < hi]
fig, ax = setup("Normal operation: Junction A leads, Junction B follows (green wave)", lo, hi, 7)
ax.set_ylim(0, 9.8)
lane(ax, 7.2, nsA, lo, hi, LIGHT, "A  NS"); lane(ax, 6.0, ewA, lo, hi, LIGHT, "A  EW"); lane(ax, 4.8, wA, lo, hi, WALK, "A  walk")
lane(ax, 3.6, nsB, lo, hi, LIGHT, "B  NS"); lane(ax, 2.4, ewB, lo, hi, LIGHT, "B  EW"); lane(ax, 1.2, wB, lo, hi, WALK, "B  walk")
digital(ax, 0.0, col("pra"), lo, hi, "ped_req_a")
if len(aE) >= 2 and len(bE) >= 2:
    offs = [b - a for a, b in zip(aE, bE)]
    ok("fig1 green-wave offset is 4 cycles on every entry in window", all(o == 4 for o in offs), str(offs))
    for a, b in zip(aE[:2], bE[:2]):
        ax.annotate("", xy=(b, 7.0), xytext=(a, 7.0), arrowprops=dict(arrowstyle="<->", color="k"))
        ax.text((a + b) / 2, 8.6, "+%d cycles" % (b - a), ha="center", fontsize=9)
ax.text(hi, 9.4, legend, ha="right", fontsize=8)
fig.savefig(f"{OUT}/01_normal_operation_green_wave.png", dpi=110); plt.close(fig)

# ---------------------------------------------------------------- 2. adaptive timing
def clamp(v, mn, mx): return max(mn, min(mx, v))
sweep_lo = next(i for i in range(N) if rows[i]["da"] == 0 and rows[i - 1]["da"] != 0)
sweep_hi = min(N, sweep_lo + 8 * 47 + 200 + 60)
lo, hi = sweep_lo - 20, sweep_hi
fig, ax = setup("Adaptive timing: density 0..7, then 7 on both junctions (NS green grows, then caps at MAX = 24)", lo, hi, 4)
lane(ax, 3.6, nsA, lo, hi, LIGHT, "A  NS"); lane(ax, 2.4, ewA, lo, hi, LIGHT, "A  EW")
digital(ax, 1.2, [d / 7.0 for d in col("da")], lo, hi, "density_a", "#7b3294")
digital(ax, 0.0, [d / 7.0 for d in col("db")], lo, hi, "density_b", "#7b3294")
lens = []
for e in entries("stA"):
    if lo <= e < hi - 30:
        n = 0
        while e + n < N and nsA[e + n] == 2: n += 1
        d = rows[e]["da"]; exp = clamp(6 + 3 * d, 6, 24)
        ok(f"fig2 A NS green at entry cycle {e}: density {d} -> {exp} cycles", n == exp, f"measured {n}")
        lens.append((e, d, n))
        ax.text(e + n / 2, 4.55, f"d={d}\n{n}", ha="center", fontsize=7)
ns_seq = [n for _, _, n in lens]
ok("fig2 A NS green never exceeds 24 and never below 6", all(6 <= n <= 24 for n in ns_seq), str(ns_seq))
ok("fig2 A NS green reaches the cap of 24 and stays there at density 7", ns_seq.count(24) >= 2, str(ns_seq))
ew_last = None
for e in entries("stA", 4):
    pass
ax.text(hi, 5.6, "labels: latched density d, NS green length in cycles", ha="right", fontsize=8)
fig.savefig(f"{OUT}/02_adaptive_timing_density_sweep.png", dpi=110); plt.close(fig)

# max density both directions: NS 24, EW 6 on A
late = [e for e in entries("stA") if e > sweep_lo + 8 * 47 + 40][0]
nsn = 0
while nsA[late + nsn] == 2: nsn += 1
ewE = next(i for i in range(late, N) if ewA[i] == 2); ewn = 0
while ewA[ewE + ewn] == 2: ewn += 1
ok("max density: NS green 24 cycles", nsn == 24, str(nsn))
ok("max density: EW green keeps its guaranteed minimum of 6 cycles (not starved)", ewn == 6, str(ewn))

# ---------------------------------------------------------------- 3. pedestrian arbitration
presses = [i for i in range(1, N) if rows[i]["pra"] and rows[i]["prb"] and not (rows[i - 1]["pra"] and rows[i - 1]["prb"])]
lo, hi = presses[0] - 10, min(N, presses[3] + 112 + 10)
fig, ax = setup("Pedestrian arbitration: 4 simultaneous presses from A and B, one walk per slot, first-served alternates", lo, hi, 10)
ax.set_ylim(-1.4, 12.0)
names = [("pra", "press A"), ("prb", "press B"), ("slot", "ped_slot"), ("reqA", "req_a"), ("reqB", "req_b"),
         ("grA", "grant_a"), ("grB", "grant_b")]
y = 10.8
for k, lab in names:
    digital(ax, y, col(k), lo, hi, lab); y -= 1.2
lane(ax, y, wA, lo, hi, WALK, "A  walk"); y -= 1.2
lane(ax, y, wB, lo, hi, WALK, "B  walk")
firsts = []
for p in presses[:4]:
    walks = []
    for i in range(p, min(N, p + 112)):
        if wA[i] and not wA[i - 1]: walks.append(("A", i))
        if wB[i] and not wB[i - 1]: walks.append(("B", i))
    ok(f"fig3 pair pressed at {p}: exactly two walks, one per junction", len(walks) == 2 and {w for w, _ in walks} == {"A", "B"}, str(walks))
    firsts.append(walks[0][0])
    ax.text(walks[0][1], -0.9, f"1st: {walks[0][0]}", fontsize=8, ha="left", color="#333333")
ok("fig3 first-served junction alternates on every contest", all(firsts[i] != firsts[i + 1] for i in range(3)), str(firsts))
ok("fig3 the two grants are never high in the same cycle", all(not (r["grA"] and r["grB"]) for r in rows))
fig.savefig(f"{OUT}/03_pedestrian_arbitration_fairness.png", dpi=110); plt.close(fig)

# ---------------------------------------------------------------- 4. emergency override
on = [i for i in range(1, N) if rows[i]["emg"] and not rows[i - 1]["emg"]]
lo, hi = max(0, on[0] - 30), min(N, on[-1] + 140)
fig, ax = setup("Emergency override: both junctions all-red one cycle after the override; Junction B re-locks to A afterwards", lo, hi, 8)
digital(ax, 8.4, col("emg"), lo, hi, "emergency", "#c9302c")
lane(ax, 7.2, nsA, lo, hi, LIGHT, "A  NS"); lane(ax, 6.0, ewA, lo, hi, LIGHT, "A  EW"); lane(ax, 4.8, wA, lo, hi, WALK, "A  walk")
lane(ax, 3.6, nsB, lo, hi, LIGHT, "B  NS"); lane(ax, 2.4, ewB, lo, hi, LIGHT, "B  EW"); lane(ax, 1.2, wB, lo, hi, WALK, "B  walk")
for i in on:
    ax.axvline(i, color="#c9302c", linewidth=0.6, linestyle=":")
    allred = lambda j: not (nsA[j] or ewA[j] or wA[j] or nsB[j] or ewB[j] or wB[j])
    ok(f"fig4 override at cycle {i}: all lights and walks off one cycle later", allred(i + 1), "")
walk_hit = [i for i in on if rows[i]["wA"] or rows[i]["wB"]]
ok("fig4 at least one override was asserted while a pedestrian WALK was active", len(walk_hit) >= 1, str(on))
ok("fig4 the walk is off one cycle after that override", all(not rows[i + 1]["wA"] and not rows[i + 1]["wB"] for i in walk_hit), str(walk_hit))
# B re-lock: after the last override, B NS entries follow A NS entries by 4
last = on[-1]
aE = [e for e in entries("stA") if e > last]; bE = [e for e in entries("stB") if e > last]
ok("fig4 after the override Junction B resumes exactly 4 cycles behind A", len(aE) and len(bE) and bE[0] - aE[0] == 4, f"A {aE[:2]} B {bE[:2]}")
ax.text(hi, 9.6, legend, ha="right", fontsize=8)
fig.savefig(f"{OUT}/04_emergency_override.png", dpi=110); plt.close(fig)

with open("sim/logs/waveform_checks.txt", "w") as f:
    for n, p, i in checks: f.write(("PASS  " if p else "FAIL  ") + n + (("  " + i) if (i and not p) else "") + "\n")
    f.write(f"\n{sum(1 for _, p, _ in checks if p)} PASS / {sum(1 for _, p, _ in checks if not p)} FAIL\n")
print(open("sim/logs/waveform_checks.txt").read())
sys.exit(0 if all(p for _, p, _ in checks) else 1)
