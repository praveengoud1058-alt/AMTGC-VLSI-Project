#!/usr/bin/env python3
"""Task-2 waveform figures: generic_timer (05) and junction_controller (06), drawn from
sim/logs/wave_units_trace.csv (written by sim/tools/wave_units_tb.v). Every claim on a figure is computed from the
trace and asserted; results go to sim/logs/waveform_units_checks.txt.
Run from the repository root:  python3 sim/tools/plot_waveforms_units.py
"""
import csv, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

T, J = [], []
for r in csv.reader(open("sim/logs/wave_units_trace.csv")):
    (T if r[0] == "T" else J).append([int(x) for x in r[1:]])
# T rows: cycle rst start target count done.   J rows: cycle rst state ns ew walk preq pending serve
OUT = "docs/waveforms"
checks = []
def ok(name, cond, info=""):
    checks.append((name, bool(cond), info))
    if not cond: print("CHECK FAILED:", name, info)

LIGHT = {0: "#d9534f", 1: "#f0ad4e", 2: "#5cb85c"}
WALK = {0: "#e8e8e8", 1: "#337ab7"}
STATE_COL = {1: "#5cb85c", 2: "#f0ad4e", 3: "#d9534f", 4: "#5cb85c", 5: "#f0ad4e", 6: "#d9534f", 7: "#337ab7", 0: "#bbbbbb"}
STATE_NAME = {1: "NS green", 2: "NS yellow", 3: "all-red 1", 4: "EW green", 5: "EW yellow", 6: "all-red 2", 7: "PED"}
SHORT = {2: "NS-Y", 3: "AR1", 5: "EW-Y", 6: "AR2"}

def runs(vals, lo, hi):
    out = []; s = lo
    for i in range(lo + 1, hi + 1):
        if i == hi or vals[i] != vals[s]:
            out.append((s, i - s, vals[s])); s = i
    return out

def digital(ax, y, vals, lo, hi, label, color="#444444"):
    xs = list(range(lo, hi)); ys = [y + 0.8 * vals[i] for i in xs]
    ax.step(xs, ys, where="post", color=color, linewidth=1.3)
    ax.hlines(y, lo, hi, color="#cccccc", linewidth=0.5)
    ax.text(lo - 0.01 * (hi - lo), y + 0.4, label, ha="right", va="center", fontsize=8)

def colored(ax, y, vals, lo, hi, cmap, label, names=None):
    for s, n, v in runs(vals, lo, hi):
        ax.broken_barh([(s, n)], (y, 0.8), facecolors=cmap[v], edgecolors="white", linewidth=0.3)
        if names and n >= 5:
            ax.text(s + n / 2, y + 0.4, f"{names.get(v, v)}\n{n}", ha="center", va="center", fontsize=6.5)
        elif names and n >= 2:
            ax.text(s + n / 2, y + 0.4, f"{SHORT.get(v, v)} {n}", ha="center", va="center", fontsize=6, rotation=90)
    ax.text(lo - 0.01 * (hi - lo), y + 0.4, label, ha="right", va="center", fontsize=8)

def setup(title, lo, hi, h, nl):
    fig, ax = plt.subplots(figsize=(14, h))
    ax.set_xlim(lo, hi); ax.set_ylim(-0.3, nl * 1.2 + 0.4); ax.set_yticks([])
    ax.set_xlabel("clock cycle"); ax.set_title(title, fontsize=11, loc="left")
    fig.subplots_adjust(left=0.1, right=0.99, top=0.88, bottom=0.12)
    return fig, ax

# ============================================================ 05: generic_timer
rst = [r[1] for r in T]; st = [r[2] for r in T]; tg = [r[3] for r in T]
cnt = [r[4] for r in T]; dn = [r[5] for r in T]
n = max(i for i in range(len(T)) if st[i] or dn[i]) + 5
starts = [i for i in range(1, n) if st[i] and not st[i - 1]]
fig, ax = setup("generic_timer (COUNTER_WIDTH = 8): start, count to target, done, clear, reset while counting", 0, n, 5.4, 5)
digital(ax, 4.8, rst, 0, n, "rst_n")
digital(ax, 3.6, st, 0, n, "start")
for idx, (s_, k, v) in enumerate([r_ for r_ in runs(tg, 0, n) if any(st[r_[0]:r_[0] + r_[1]])]):
    ax.text(s_ + min(k, 6) / 2, 3.0 + 0.32 * (idx % 2), f"target={v}", ha="center", fontsize=7)
ax.step(range(n), [1.3 + 1.5 * cnt[i] / 8.0 for i in range(n)], where="post", color="#7b3294", linewidth=1.4)
ax.text(-0.01 * n, 2.0, "current_count", ha="right", va="center", fontsize=8)
for i in range(n):
    if i == 0 or cnt[i] != cnt[i - 1]:
        ax.text(i + 0.5, 1.3 + 1.5 * cnt[i] / 8.0 + 0.12, str(cnt[i]), fontsize=6.5, ha="center", color="#7b3294")
digital(ax, 0.0, dn, 0, n, "done", "#c9302c")

runs_info = []
for s0 in starts:
    t = tg[s0]
    end = next((i for i in range(s0 + 1, n) if not st[i]), n)
    rsts = [i for i in range(s0, end) if not rst[i]]
    first_done = next((i for i in range(s0 + 1, end + 1) if i < n and dn[i]), None)
    runs_info.append((s0, t, end, rsts, first_done))
checked = 0
for s0, t, end, rsts, fd in runs_info:
    if rsts:
        r0 = rsts[0]
        ok(f"timer run at {s0} (target {t}): asynchronous reset clears count and done in the same cycle", cnt[r0] == 0 and dn[r0] == 0, f"count {cnt[r0]} done {dn[r0]}")
        ok(f"timer run at {s0}: counter was running before the reset", cnt[r0 - 1] > 0)
        rel = next(i for i in range(r0, n) if rst[i])
        fd2 = next((i for i in range(rel, n) if dn[i]), None)
        ok(f"timer run at {s0}: after the reset the timer restarts and completes (target {t})", fd2 is not None and fd2 - rel <= t + 1, f"release {rel} done {fd2}")
        ax.annotate("reset while counting", xy=(r0, 3.8), xytext=(r0 + 2, 4.45), fontsize=7, arrowprops=dict(arrowstyle="->"))
        continue
    expect = s0 + max(t, 1)
    ok(f"timer start at {s0}, target {t}: done rises exactly max(target,1) = {max(t,1)} edges after start", fd == expect, f"done at {fd}, expected {expect}")
    ok(f"timer start at {s0}, target {t}: count equals max(target-1,0) when done", cnt[fd] == max(t - 1, 0), f"count {cnt[fd]}")
    ok(f"timer start at {s0}, target {t}: done stays high while start stays high", all(dn[i] for i in range(fd, end)))
    ok(f"timer start at {s0}, target {t}: start low clears done and count on the next edge", dn[end + 1] == 0 and cnt[end + 1] == 0, f"{dn[end+1]} {cnt[end+1]}")
    ax.annotate(f"done after {fd - s0} edge" + ("s" if fd - s0 != 1 else ""), xy=(fd, 0.9),
                xytext=(fd + 1.5, 1.95 + 0.6 * (checked % 3)), fontsize=7, arrowprops=dict(arrowstyle="->"))
    checked += 1
ok("timer figure covers normal runs with targets 0, 1, 3 and 5, plus one run interrupted by a reset",
   sorted(t for _, t, _, r, _ in runs_info if not r) == [0, 1, 3, 5] and sum(1 for x in runs_info if x[3]) == 1,
   str([(t, bool(r)) for _, t, _, r, _ in runs_info]))
fig.savefig(f"{OUT}/05_generic_timer.png", dpi=110); plt.close(fig)

# ============================================================ 06: junction_controller
js = [r[2] for r in J]; jn = [r[3] for r in J]; je = [r[4] for r in J]
jw = [r[5] for r in J]; jq = [r[6] for r in J]; jp = [r[7] for r in J]; jv = [r[8] for r in J]; m = len(J)
fig, ax = setup("junction_controller: NS green > NS yellow > all-red > EW green > EW yellow > all-red > pedestrian phase", 0, m, 6.2, 6.8)
colored(ax, 7.2, js, 0, m, STATE_COL, "FSM state", STATE_NAME)
colored(ax, 6.0, jn, 0, m, LIGHT, "NS lights"); colored(ax, 4.8, je, 0, m, LIGHT, "EW lights")
colored(ax, 3.6, jw, 0, m, WALK, "ped_walk")
digital(ax, 2.4, jq, 0, m, "button", "#444444"); digital(ax, 1.2, jp, 0, m, "pending", "#7b3294"); digital(ax, 0.0, jv, 0, m, "serve", "#337ab7")

sr = [(s_, k, v) for s_, k, v in runs(js, 0, m) if v != 0]
seq = [v for _, _, v in sr]
ok("FSM visits the phases in the required order for the whole trace", all(seq[i + 1] == (seq[i] % 7) + 1 for i in range(len(seq) - 1)), str(seq))
EXP = {1: 15, 2: 3, 3: 3, 4: 15, 5: 3, 6: 3, 7: 5}
bad = [(STATE_NAME[v], k, EXP[v]) for _, k, v in sr[1:-1] if k != EXP[v]]
ok("every complete phase lasts exactly its configured length (15, 3, 3, 15, 3, 3, 5 cycles)", not bad, str(bad))
ok("NS and EW are never green together", all(not (jn[i] == 2 and je[i] == 2) for i in range(m)))
gaps = []
for (s1, k1, v1), (s2, k2, v2) in zip(sr, sr[1:]):
    if (v1 == 2 and v2 == 3) or (v1 == 5 and v2 == 6):
        gaps.append(k2)
ok("every change of right-of-way has a non-zero all-red gap (3 cycles)", gaps and all(g == 3 for g in gaps), str(gaps))
ok("walk is only ever shown while both vehicle directions are red", all(not jw[i] or (jn[i] == 0 and je[i] == 0) for i in range(m)))
press = [i for i in range(1, m) if jq[i] and not jq[i - 1]]
wst = [i for i in range(1, m) if jw[i] and not jw[i - 1]]
p1, p2 = press[0], press[1]
ok("request arrives during NS yellow", js[p1] == 2, f"state {js[p1]}")
w_after_1 = [w for w in wst if p1 < w < p1 + 47]
ok("request during yellow is served exactly once, in the next pedestrian phase", len(w_after_1) == 1 and js[w_after_1[0]] == 7, str(w_after_1))
ok("request during yellow is not served a second time", not [w for w in wst if p1 + 47 <= w < p2])
w_after_2 = [w for w in wst if p2 < w <= p2 + 94]
ok("request held high for 20 cycles is served exactly once", len(w_after_2) == 1, str(w_after_2))
ax.annotate("request in yellow", xy=(p1, 2.6), xytext=(p1 + 2, 3.0), fontsize=7, arrowprops=dict(arrowstyle="->"))
fig.savefig(f"{OUT}/06_junction_controller.png", dpi=110); plt.close(fig)

with open("sim/logs/waveform_units_checks.txt", "w") as f:
    for nme, p, i in checks: f.write(("PASS  " if p else "FAIL  ") + nme + (("  " + i) if (i and not p) else "") + "\n")
    f.write(f"\n{sum(1 for _, p, _ in checks if p)} PASS / {sum(1 for _, p, _ in checks if not p)} FAIL\n")
print(open("sim/logs/waveform_units_checks.txt").read())
sys.exit(0 if all(p for _, p, _ in checks) else 1)
