# Cycle-accurate Python model of the AMTGC RTL (mirrors the Verilog equations 1:1).
S_GW, S_NS, S_NSY, S_AR1, S_EW, S_EWY, S_AR2, S_PED, S_EMG = range(9)
NAMES = ["GW_WAIT","NS_GREEN","NS_YELLOW","ALL_RED_1","EW_GREEN","EW_YELLOW","ALL_RED_2","PED","EMERGENCY"]
TIMER_OVERHEAD = 2
MASK8 = 0xFF

class Timer:
    def __init__(s): s.cnt=0; s.done=0
    def step(s, start, target):
        if not start: s.cnt=0; s.done=0; return
        if target == 0: s.done=1; s.cnt=0; return
        if s.cnt >= ((target-1) & MASK8): s.done=1; return   # cnt holds
        s.cnt = (s.cnt+1) & MASK8; s.done=0

class Junction:
    def __init__(s, p, is_b):
        s.p=p; s.is_b=is_b
        s.reset()
    def reset(s):
        s.state = S_GW if s.is_b else S_NS
        s.pe=1; s.latched=0; s.pending=0; s.req_prev=0; s.serve=0
        s.timer=Timer(); s.ped_req_out=0
    def ns_dur(s, d):
        t = s.p['base'] + d*s.p['step']
        return min(max(t, s.p['mn']), s.p['mx'])
    def ew_dur(s, d):
        return s.p['mn']+s.p['mx']-s.ns_dur(d)
    def to_target(s, dur):
        return dur-TIMER_OVERHEAD if dur > TIMER_OVERHEAD else 1
    def comb(s, emg):
        st=s.state; p=s.p
        if st==S_NS: dur=s.ns_dur(s.latched); run=1
        elif st==S_NSY: dur=p['y']; run=1
        elif st==S_AR1: dur=p['r']; run=1
        elif st==S_EW: dur=s.ew_dur(s.latched); run=1
        elif st==S_EWY: dur=p['y']; run=1
        elif st==S_AR2: dur=p['r']; run=1
        elif st==S_PED: dur=p['ped']; run=1
        else: dur=0; run=0
        s.timer_start = int(run and not s.pe)
        s.timer_target = s.to_target(dur) if run else 0
        s.tdone = int(s.timer.done and not s.pe)
        s.decision = int(st==S_AR2 and s.tdone and not emg)          # ped_slot_out
        s.armed = int(st in (S_EW, S_EWY, S_AR2))
        s.gw_out = int(st==S_NS and s.pe)
        ns=ew=0; walk=0
        if st==S_NS: ns=2
        elif st==S_NSY: ns=1
        elif st==S_EW: ew=2
        elif st==S_EWY: ew=1
        elif st==S_PED: walk=s.serve
        s.ns, s.ew, s.walk = ns, ew, walk
    def set_req(s, slot, emg):
        s.ped_req_out = int(bool(slot) and bool(s.armed) and bool(s.pending)
                            and not s.serve and not emg)
    def next_state(s, emg, gw_in):
        st=s.state
        if emg: return S_EMG
        if st==S_GW: return S_NS if gw_in else S_GW
        if st==S_EMG: return S_GW if s.is_b else S_AR1
        table = {S_NS:S_NSY, S_NSY:S_AR1, S_AR1:S_EW, S_EW:S_EWY, S_EWY:S_AR2, S_AR2:S_PED, S_PED:S_NS}
        if st in table: return table[st] if s.tdone else st
        return S_GW if s.is_b else S_NS
    def clock(s, emg, dens, req_in, grant, gw_in):
        ns = s.next_state(emg, gw_in)
        latched = dens if (s.pe and s.state==S_NS) else s.latched
        pend = s.pending
        if req_in and not s.req_prev: pend = 1
        elif s.ped_req_out and grant: pend = 0
        if s.ped_req_out and grant: serve = 1
        elif s.state==S_PED and ns != S_PED: serve = 0
        else: serve = s.serve
        s.timer.step(s.timer_start, s.timer_target)
        s.latched=latched; s.pending=pend; s.req_prev=req_in; s.serve=serve
        s.pe=int(ns != s.state); s.state=ns

def arbiter(ra, rb, prefer_b):
    ga = int(bool(ra) and (not rb or not prefer_b))
    gb = int(bool(rb) and not ga)
    if ra and rb: prefer_b ^= 1
    return ga, gb, prefer_b

def run_system(p_a, p_b, D=4, cycles=0, script=None):
    """script(cyc, A, B) -> dict(rst, emg, dens_a, dens_b, req_a, req_b)."""
    A=Junction(p_a,False); B=Junction(p_b,True)
    W=D-1; gw_sr=0; prefer_b=0
    trace=[]
    for cyc in range(cycles):
        inp = script(cyc, A, B)
        if inp.get('rst'):
            A.reset(); B.reset(); gw_sr=0; prefer_b=0
            trace.append(dict(cyc=cyc, rst=1)); continue
        emg=inp['emg']
        A.comb(emg); B.comb(emg)
        slot = A.decision
        A.set_req(slot, emg); B.set_req(slot, emg)
        ga, gb, prefer_next = arbiter(A.ped_req_out, B.ped_req_out, prefer_b)
        gw_a = A.gw_out
        gw_in_b = (gw_sr >> (D-2)) & 1
        trace.append(dict(cyc=cyc, emg=emg, rst=0, slot=slot,
            a=dict(state=A.state,ns=A.ns,ew=A.ew,walk=A.walk,pe=A.pe,latched=A.latched,pending=A.pending,req=A.ped_req_out,grant=ga,dec=A.decision,serve=A.serve),
            b=dict(state=B.state,ns=B.ns,ew=B.ew,walk=B.walk,pe=B.pe,latched=B.latched,pending=B.pending,req=B.ped_req_out,grant=gb,dec=B.decision,serve=B.serve),
            gw_a=gw_a, gw_in_b=gw_in_b))
        A.clock(emg, inp['dens_a'], inp['req_a'], ga, 0)
        B.clock(emg, inp['dens_b'], inp['req_b'], gb, gw_in_b)
        prefer_b = prefer_next
        gw_sr = 0 if emg else (((gw_sr<<1) | gw_a) & ((1<<W)-1))
    return trace
