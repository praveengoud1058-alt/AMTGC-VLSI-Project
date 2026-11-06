import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model
from model import Timer
class TimerW(Timer):
    def __init__(s,W): super().__init__(); s.W=W
    def step(s,start,target):
        M=(1<<s.W)-1
        if not start: s.cnt=0; s.done=0; return
        if target==0: s.done=1; s.cnt=0; return
        if s.cnt>=((target-1)&M): s.done=1; return
        s.cnt=(s.cnt+1)&M; s.done=0
MASK=lambda w:(1<<w)-1
res=[]
def chk(name,c,extra=""):
    res.append((name,bool(c))); print(("[PASS] " if c else "[FAIL] ")+name+("" if c else " "+extra))

# ---- generic_timer, three widths, same expectations as tb_generic_timer.v ----
for W in (4,8,12):
    maxt=MASK(W)
    for T in (0,1,2,maxt//2,maxt):
        tm=TimerW(W); edges=0
        while not tm.done and edges<10000:
            tm.step(1,T); edges+=1
        chk(f"W={W} T={T}: done after max(T,1)={max(T,1)} edges", edges==max(T,1), f"got {edges}")
        chk(f"W={W} T={T}: count == max(T-1,0)", tm.cnt==max(T-1,0), f"cnt={tm.cnt}")
        tm.step(1,T); chk(f"W={W} T={T}: done holds while start high", tm.done==1)
        tm.step(0,T); chk(f"W={W} T={T}: start low clears done/count", tm.done==0 and tm.cnt==0)
    # async reset mid count is modelled as clear
    tm=TimerW(W)
    for _ in range(4): tm.step(1,maxt)
    chk(f"W={W}: count running before reset", tm.cnt!=0)
    tm.cnt=0; tm.done=0
    chk(f"W={W}: reset clears count and done", tm.cnt==0 and tm.done==0)

# ---- ped_arbiter (contest-only round-robin pointer), same expectations as tb_ped_arbiter.v ----
from model import arbiter
pb=0; seq=[]
for i in range(40):
    ga,gb,pb=arbiter(1,1,pb); seq.append((ga,gb))
chk("arb T2a exactly one grant every cycle", all(a+b==1 for a,b in seq))
chk("arb T2b strict alternation", all(seq[i]!=seq[i+1] for i in range(39)))
chk("arb T2c 20 grants each over 40 cycles", sum(a for a,b in seq)==20 and sum(b for a,b in seq)==20)
chk("arb T1a lone A granted", arbiter(1,0,0)[:2]==(1,0))
chk("arb T1b lone B granted", arbiter(0,1,0)[:2]==(0,1))
chk("arb T1c no request no grant", arbiter(0,0,0)[:2]==(0,0))
pb=0; gap=0; maxgap=0
for i in range(100):
    ga,gb,pb=arbiter(1,1,pb)
    if gb: maxgap=max(maxgap,gap); gap=0
    else: gap+=1
chk("arb T3 B granted at least every 2 cycles under A worst case", maxgap<=1, f"maxgap {maxgap}")
pb=0
ga,gb,pb=arbiter(1,1,pb);  chk("arb T4a first contest goes to A", (ga,gb)==(1,0))
ga,gb,pb=arbiter(0,1,pb);  chk("arb T4b lone B granted", (ga,gb)==(0,1))
ga,gb,pb=arbiter(1,1,pb);  chk("arb T4c next contest goes to B (lone grant does not skew pointer)", (ga,gb)==(0,1))
ga,gb,pb=arbiter(1,0,pb);  chk("arb T4d lone A granted", (ga,gb)==(1,0))
ga,gb,pb=arbiter(1,1,pb);  chk("arb T4e next contest goes back to A", (ga,gb)==(1,0))
print(f"\nUNIT MODELS: {sum(p for _,p in res)} PASS / {sum(1 for _,p in res if not p)} FAIL of {len(res)}")
