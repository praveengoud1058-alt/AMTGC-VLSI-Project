import sys; import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'python_model'))
from model import *
PA=dict(base=6,mn=6,mx=24,step=3,y=3,r=3,ped=5)
PB=dict(base=9,mn=6,mx=24,step=2,y=3,r=3,ped=5)
def script(c,A,B):
    return dict(rst=0, emg=1 if 80<=c<=82 else 0,
                dens_a=3 if c<50 else 7, dens_b=5,
                req_a=1 if c in (10,60) else 0, req_b=1 if c in (12,60) else 0)
tr=run_system(PA,PB,4,cycles=200,script=script)
for t in tr:
    if t.get('rst'): continue
    print(t['cyc'], t['a']['ns'], t['a']['ew'], t['a']['walk'], t['b']['ns'], t['b']['ew'], t['b']['walk'])
