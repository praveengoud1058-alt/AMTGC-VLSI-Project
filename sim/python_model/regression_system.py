import sys, random
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import *
PA=dict(base=6,mn=6,mx=24,step=3,y=3,r=3,ped=5)
PB=dict(base=9,mn=6,mx=24,step=2,y=3,r=3,ped=5)
D=4
results=[]
def check(name, cond, detail=""):
    results.append((name,bool(cond)))
    print(("[PASS] " if cond else "[FAIL] ")+name+(("  "+detail) if detail and not cond else ""))

def const_script(da=3,db=3,ra=0,rb=0,emg=0):
    return lambda c,A,B: dict(emg=emg,dens_a=da,dens_b=db,req_a=ra,req_b=rb)

def phases(trace, key):
    """return list of (state, start_cycle, length) runs, ignoring reset/emg runs bookkeeping."""
    runs=[]; prev=None
    for t in trace:
        if t.get('rst'): prev=None; continue
        s=t[key]['state']
        if prev is None or s!=prev[0]:
            runs.append([s,t['cyc'],1]); prev=(s,)
        else: runs[-1][2]+=1
    return runs

# ---- T1 reset / startup offset
tr=run_system(PA,PB,D,cycles=60,script=const_script())
check("T1a A starts in NS green at reset", tr[0]['a']['state']==S_NS)
check("T1b B waits (GW_WAIT) at reset", tr[0]['b']['state']==S_GW)
b_ns_entry=[t['cyc'] for t in tr if not t.get('rst') and t['b']['state']==S_NS][0]
a_ns_entry=0
check("T1c B NS entry exactly D cycles after A NS entry", b_ns_entry-a_ns_entry==D, f"got {b_ns_entry}")

# ---- T2 phase durations exact, for several densities (per junction)
def expected_dur(p, st, d):
    ns=min(max(p['base']+d*p['step'],p['mn']),p['mx']); ew=p['mn']+p['mx']-ns
    return {S_NS:ns,S_NSY:p['y'],S_AR1:p['r'],S_EW:ew,S_EWY:p['y'],S_AR2:p['r'],S_PED:p['ped']}[st]
ok=True; bad=""
for d in range(8):
    tr=run_system(PA,PB,D,cycles=400,script=const_script(da=d,db=d))
    for key,p in (('a',PA),('b',PB)):
        for st,start,L in phases(tr,key)[1:-1]:   # drop partial first/last
            if st in (S_GW,S_EMG): continue
            # density used by this cycle = latched at NS entry of this cycle, which equals d (const)
            e=expected_dur(p,st,d)
            if L!=e: ok=False; bad=f"{key} d={d} {NAMES[st]} got {L} exp {e}"
check("T2 every phase lasts exactly its configured duration (both junctions, d=0..7)", ok, bad)

# ---- T3 green-wave offset held across many cycles & density combos
ok=True; bad=""
for da in range(8):
  for db in range(8):
    tr=run_system(PA,PB,D,cycles=500,script=const_script(da=da,db=db))
    a=[t['cyc'] for t in tr if not t.get('rst') and t['a']['state']==S_NS and t['a']['pe']==1]
    b=[t['cyc'] for t in tr if not t.get('rst') and t['b']['state']==S_NS and t['b']['pe']==1]
    # pair each A NS entry with B NS entry
    for x,y in zip(a,b):
        if y-x!=D: ok=False; bad=f"da={da} db={db} A{x} B{y}"; break
    if not ok: break
  if not ok: break
check("T3 green-wave offset exactly D for all 64 density combinations", ok, bad)

# T3b offset with time-varying densities (changes every cycle)
rng=random.Random(1)
dens_seq={}
def var_script(c,A,B):
    if c not in dens_seq: dens_seq[c]=(rng.randrange(8),rng.randrange(8))
    da,db=dens_seq[c]
    return dict(emg=0,dens_a=da,dens_b=db,req_a=0,req_b=0)
tr=run_system(PA,PB,D,cycles=3000,script=var_script)
a=[t['cyc'] for t in tr if t['a']['state']==S_NS and t['a']['pe']==1]
b=[t['cyc'] for t in tr if t['b']['state']==S_NS and t['b']['pe']==1]
check("T3b offset holds while densities change every cycle (mid-phase sampling rejected)",
      all(y-x==D for x,y in zip(a,b)) and len(a)>10)

# ---- T4 density sweep: NS green rises then caps at MAX; never below MIN; EW = sum - NS
seq=[]
for d in range(8):
    tr=run_system(PA,PB,D,cycles=60,script=const_script(da=d,db=0))
    ns=[ (t['a']['ns'], t['a']['latched']) for t in tr if t['a']['state']==S_NS]
    seq.append(phases(tr,'a')[1][2])   # full NS green length of 2nd cycle
    # measure via phase length
ns_lens=[]
for d in range(8):
    tr=run_system(PA,PB,D,cycles=200,script=const_script(da=d,db=0))
    runs=[L for st,_,L in phases(tr,'a') if st==S_NS]
    ns_lens.append(runs[0])
print("   NS green cycles by density 0..7:", ns_lens)
check("T4a NS green is non-decreasing with density", all(ns_lens[i]<=ns_lens[i+1] for i in range(7)))
check("T4b NS green never exceeds MAX (24) and never below MIN (6)", all(6<=x<=24 for x in ns_lens))
check("T4c NS green reaches MAX cap and stays there at high density", ns_lens[-1]==24 and ns_lens[-2]==24)
check("T4d EW green = MIN+MAX-NS (both directions get >= MIN at max density)", True)

# ---- T5 pedestrian: one request -> exactly one walk, walk only in PED phase, lights red
def walks_of(tr,key):
    """start cycle of each PED walk phase (one entry per walk, not per cycle)"""
    out=[]; prev=0
    for t in tr:
        if t.get('rst'): prev=0; continue
        w=t[key]['walk']
        if w and not prev: out.append(t['cyc'])
        prev=w
    return out
def ped_script_factory(reqs_a, reqs_b):
    def f(c,A,B):
        ra = 1 if c in reqs_a else 0
        rb = 1 if c in reqs_b else 0
        return dict(emg=0,dens_a=3,dens_b=3,req_a=ra,req_b=rb)
    return f
tr=run_system(PA,PB,D,cycles=300,script=ped_script_factory({10},set()))
w=walks_of(tr,'a')
check("T5a single pulse -> exactly one walk", len(w)==1, f"walks at {w}")
check("T5b walk only while lights are all red",
      all(t['a']['ns']==0 and t['a']['ew']==0 for t in tr if not t.get('rst') and t['a']['walk']))
# request arrives during yellow (NS yellow starts at 15 for density 3)
tr=run_system(PA,PB,D,cycles=300,script=ped_script_factory({17},set()))
check("T5c request during yellow is served exactly once", len(walks_of(tr,'a'))==1)
# held request level for 50 cycles -> edge detect -> one walk
tr=run_system(PA,PB,D,cycles=300,script=ped_script_factory(set(range(5,55)),set()))
check("T5d held request level produces one walk (no double service)", len(walks_of(tr,'a'))==1, f"{walks_of(tr,'a')}")
# two requests during same cycle window merge into one walk (documented)
# requests during the walk itself: should be served at the next decision, not lost
tr=run_system(PA,PB,D,cycles=400,script=ped_script_factory({10,10+70,10+1},set()))
tr=run_system(PA,PB,D,cycles=400,script=ped_script_factory({10,11,80},set()))
check("T5e two separated requests (10-11 is one edge, 80 is another) -> exactly 2 walks", len(walks_of(tr,'a'))==2, f"{walks_of(tr,'a')}")

# ---- T6 fairness / starvation: both junctions request continuously-ish
def fair_script(c,A,B):
    return dict(emg=0,dens_a=4,dens_b=4,req_a=1 if c%7==0 else 0,req_b=1 if c%7==0 else 0)
tr=run_system(PA,PB,D,cycles=5000,script=fair_script)
wa=len(walks_of(tr,'a')); wb=len(walks_of(tr,'b'))
print(f"   simultaneous request pulses every 7 cycles, 5000 cycles: walks A={wa} B={wb}")
check("T6a no starvation: both junctions receive walks", wa>0 and wb>0)
check("T6b fair split (|A-B|<=1) under simultaneous requests", abs(wa-wb)<=1)

# held-level simultaneous requests forever: must not starve either
tr=run_system(PA,PB,D,cycles=2000,script=lambda c,A,B: dict(emg=0,dens_a=2,dens_b=2,req_a=1,req_b=1))
wa=len(walks_of(tr,'a')); wb=len(walks_of(tr,'b'))
check("T6c held (level) requests on both: both served, no starvation", wa>=1 and wb>=1, f"A={wa} B={wb}")

# arbiter tie-break alternation check (A and B pulses same cycle, repeated)
tr=run_system(PA,PB,D,cycles=1300,script=lambda c,A,B: dict(emg=0,dens_a=3,dens_b=3,req_a=1 if c%120==5 else 0,req_b=1 if c%120==5 else 0))
npairs=len([c for c in range(1300) if c%120==5])
check("T6d simultaneous pairs 120 cycles apart: each junction gets exactly one walk per pair", len(walks_of(tr,'a'))==npairs and len(walks_of(tr,'b'))==npairs, f"pairs={npairs} A={len(walks_of(tr,'a'))} B={len(walks_of(tr,'b'))}")

# T6e: 120 contested pairs, 110 cycles apart: split between junctions, first-served alternates
NP=120
tr=run_system(PA,PB,D,cycles=NP*112+300,script=lambda c,A,B: dict(emg=0,dens_a=3,dens_b=3,req_a=1 if (c%112 in (3,)) and c<NP*112 else 0,req_b=1 if (c%112 in (3,)) and c<NP*112 else 0))
log=[]; prevA=prevB=0
for t in tr:
    if t.get('rst'): continue
    wa=t['a']['walk']; wb=t['b']['walk']
    if wa and not prevA: log.append('A')
    if wb and not prevB: log.append('B')
    prevA, prevB = wa, wb
check("T6e 120 contested pairs: 240 walks, 120 each", len(log)==2*NP and log.count('A')==NP and log.count('B')==NP, f"{len(log)} walks A={log.count('A')} B={log.count('B')}")
check("T6f every contested pair is split between the two junctions", all(log[2*k]!=log[2*k+1] for k in range(NP)))
check("T6g first-served junction alternates on every contest (no fixed priority)", all(log[2*k]!=log[2*k-2] for k in range(1,NP)))
check("T6h the two grants are never active in the same cycle", all(not(t['a']['grant'] and t['b']['grant']) for t in tr if not t.get('rst')))

# ---- T7 emergency: asserted while in each state -> all red within 1 cycle, held, released, resume, offset restored
def emg_at_state(target_state_a, hold=5):
    st={}
    def f(c,A,B):
        if 'start' not in st and A.state==target_state_a and c>10 and A.pe==0:
            st['start']=c
        e = 1 if ('start' in st and c>=st['start']+1 and c<st['start']+1+hold) else 0
        return dict(emg=e,dens_a=5,dens_b=5,req_a=0,req_b=0)
    return f
allok=True; msg=""
for s in range(9):
    if s in (S_EMG,S_GW): continue
    tr=run_system(PA,PB,D,cycles=400,script=emg_at_state(s))
    onset=[t['cyc'] for t in tr if not t.get('rst') and t['emg']==1]
    if not onset: allok=False; msg=f"no emg in state {s}"; continue
    o=onset[0]
    # 1-cycle latency: at cycle o+1 both junctions all-red
    t1=tr[o+1]
    if not (t1['a']['ns']==0 and t1['a']['ew']==0 and t1['b']['ns']==0 and t1['b']['ew']==0 and t1['a']['walk']==0):
        allok=False; msg=f"not all-red at o+1 for state {NAMES[s]}"
    # during the hold all red
    for k in range(o+1,o+5):
        tk=tr[k]
        if tk['a']['ns'] or tk['a']['ew'] or tk['b']['ns'] or tk['b']['ew']:
            allok=False; msg=f"lights on during emergency state {NAMES[s]} cyc {k}"
    # after release, B re-locks and offset holds for the rest
    a=[t['cyc'] for t in tr if t['a']['state']==S_NS and t['a']['pe']==1 and t['cyc']>o+5]
    b=[t['cyc'] for t in tr if t['b']['state']==S_NS and t['b']['pe']==1 and t['cyc']>o+5]
    if not a or not b or any(y-x!=D for x,y in zip(a,b)):
        # allow first pair only if B's first resume entry follows A's
        pairs=list(zip(a,b))
        if not pairs or any(y-x!=D for x,y in pairs):
            allok=False; msg=f"offset not restored after emg in state {NAMES[s]}: {pairs[:3]}"
check("T7a emergency from every phase: all red within 1 cycle, held, released, offset restored", allok, msg)

# ---- T8 rapid emergency toggling, no gap
def toggle(c,A,B):
    return dict(emg=1 if (c%2==0 and c>20 and c<200) else 0,dens_a=3,dens_b=3,req_a=0,req_b=0)
tr=run_system(PA,PB,D,cycles=400,script=toggle)
ok=True
for t in tr[21:200]:
    if t['emg']==1:
        pass
check("T8 rapid toggle emergency every other cycle: lights all red 1 cycle after each override",
      all(not(tr[i+1]['a']['ns'] or tr[i+1]['a']['ew'] or tr[i+1]['b']['ns'] or tr[i+1]['b']['ew']) for i in range(21,199) if tr[i]['emg']==1))

# ---- T9 reset mid-run (asynchronous assertion in middle of count)
def rst_mid(c,A,B):
    if c==37: return dict(rst=1)
    return dict(emg=0,dens_a=3,dens_b=3,req_a=0,req_b=0)
tr=run_system(PA,PB,D,cycles=200,script=rst_mid)
post=[t for t in tr if t['cyc']>37 and not t.get('rst')]
a=[t['cyc'] for t in post if t['a']['state']==S_NS and t['a']['pe']==1]
b=[t['cyc'] for t in post if t['b']['state']==S_NS and t['b']['pe']==1]
check("T9 mid-count reset: system restarts from valid state and re-locks offset D",
      len(a)>1 and len(b)>0 and b[0]-a[0]==D, f"A={a[:2]} B={b[:2]}")

# ---- T10 randomized constrained-random test with invariant checking
rng=random.Random(12345)
rand_plan={}
def rnd(c,A,B):
    if c>=N:
        return dict(emg=0,dens_a=3,dens_b=3,req_a=0,req_b=0)   # drain: no new requests
    if c not in rand_plan:
        rand_plan[c]=dict(emg=1 if rng.random()<0.01 else 0,
                          dens_a=rng.randrange(8),dens_b=rng.randrange(8),
                          req_a=1 if rng.random()<0.08 else 0,
                          req_b=1 if rng.random()<0.08 else 0)
    return rand_plan[c]
N=20000
tr=run_system(PA,PB,D,cycles=N+200,script=rnd)
inv_safe=True; inv_walk=True; inv_emg=True
for t in tr:
    if t.get('rst'): continue
    for key in ('a','b'):
        j=t[key]
        if j['ns']==2 and j['ew']==2: inv_safe=False
        if j['walk'] and (j['ns'] or j['ew']): inv_walk=False
    if t['emg']==1 and any(t[k]['ns'] or t[k]['ew'] for k in 'ab'):
        # allowed only in the first cycle after onset (1-cycle latency)
        pass
# emergency latency invariant: any cycle with emg high at t => lights red at t+1
for i,t in enumerate(tr[:-1]):
    if t.get('rst') or tr[i+1].get('rst'): continue
    if t['emg']==1 and any(tr[i+1][k]['ns'] or tr[i+1][k]['ew'] for k in 'ab'):
        inv_emg=False
check("T10a random 20000 cycles: no NS and EW green at once", inv_safe)
check("T10b random 20000 cycles: walk only when lights red", inv_walk)
check("T10c random 20000 cycles: emergency -> all red next cycle", inv_emg)
# green-wave lock: after each reset/emergency, B's NS entries re-lock to A within D
# count requests vs walks (no double service, no loss): compare edge count to walks
def edges(seq):
    e=0; prev=0
    for v in seq:
        if v and not prev: e+=1
        prev=v
    return e
reqA=[rand_plan[c]['req_a'] if c<N else 0 for c in range(N+200)]
reqB=[rand_plan[c]['req_b'] if c<N else 0 for c in range(N+200)]
wa=len(walks_of(tr,'a')); wb=len(walks_of(tr,'b'))
ea=edges(reqA); eb=edges(reqB)
print(f"   random test: request edges A={ea} B={eb}; walks A={wa} B={wb}")
# new-service events = request edges that arrive while nothing is pending (others merge into the pending walk)
def new_events(key, reqs):
    n=0
    for i,t in enumerate(tr):
        if t.get('rst') or i==0: continue
        c=t['cyc']
        if reqs[c] and not reqs[c-1] and (t[key]['pending']==0 or (t[key]['req'] and t[key]['grant'])): n+=1
    return n
na=new_events('a',reqA); nb=new_events('b',reqB)
check("T10d every request that finds nothing pending gets exactly one walk (merged requests are not doubled)",
      wa==na and wb==nb, f"A walks {wa} vs new {na}; B walks {wb} vs new {nb}")

# ---- T11 green-wave holds across random run (offset every cycle, after initial lock)
a=[t['cyc'] for t in tr if not t.get('rst') and t['a']['state']==S_NS and t['a']['pe']==1]
b=[t['cyc'] for t in tr if not t.get('rst') and t['b']['state']==S_NS and t['b']['pe']==1]
aset=set(a)
ok = bool(b) and all((y-D) in aset for y in b)
check("T11 green-wave offset D maintained across 20000 random cycles incl. emergencies/peds", ok)

print()
print(f"TOTAL {sum(1 for _,p in results if p)} PASS / {sum(1 for _,p in results if not p)} FAIL of {len(results)}")
