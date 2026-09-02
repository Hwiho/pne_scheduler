#!=/usr/bin/env python3
import struct, json, sys
from datetime import datetime

MAGIC=b"\x71\x4d\x0b\x00\x02\x00\x01\x00"
HEADER_SIZE=1632; STEP_SIZE=612
FILE_SIG=b"PNE CTSPro Schedule File."
TYPE_REST=3; TYPE_CCCV=0x0101; TYPE_CCCh=0x0201; TYPE_CCDi=0x0202
TYPE_LOOP=8; TYPE_END=6; TYPE_CYCLE=7
OFF_IDX=0; OFF_TYPE=8; OFF_RDUR=20; OFF_CCI=16; OFF_CCVV=12
OFF_CCTL=20; OFF_CVCO=32; OFF_VLIM=12; OFF_VC=28
OFF_RVOLT=332; OFF_RTIME=340; OFF_F496=496; OFF_CNT=52; OFF_GOTO=564
HOFF_SIG=0x48; HOFF_AUTH=0x150; HOFF_TS2=0x250
HOFF_NAME=0x298; HOFF_TS3=0x398; HOFF_SAFE=0x3D8

AUTO_REST={
    "ratetest":"30min","ratetest_cyclelife":"30min",
    "cyclelife":None,"dcir":"30s","formation":"30min","impedance":"30s"
}

def pf(b,o,v): struct.pack_into("<f",b,o,float(v))
def pi(b,o,v): struct.pack_into("<i",b,o,int(v))

def pdur(s,cap=None):
    if s is None: return 0.0
    s=str(s).strip()
    if s.upper().endswith("C"):
        if cap is None: raise ValueError("C-rate needs capacity")
        return float(s[:-1])*cap
    sl=s.lower()
    if sl.endswith("d"): return float(s[:-1])*86400
    if sl.endswith("h"): return float(s[:-1])*3600
    if sl.endswith("min"): return float(s[:-3])*60
    if sl.endswith("s"): return float(s[:-1])
    return float(s)

def auto_rest(steps,tt):
    dur=AUTO_REST.get(tt)
    if dur is None or not steps: return steps
    rec="30s"
    for s in steps:
        if s.get("type") in ("cccv_charge","cc_charge","cc_discharge"):
            rec=s.get("record_time","30s"); break
    res=[]
    for i,step in enumerate(steps):
        res.append(step)
        t=step.get("type","")
        is_c=t in("cccv_charge","cc_charge"); is_d=(t=="cc_discharge")
        if is_c or is_d:
            last=(i==len(steps)-1)
            if last or steps[i+1].get("type")!="rest":
                res.append({"type":"rest","duration":dur,"record_time":rec,"auto_inserted":True})
    return res

def blk_rest(idx,dur_s,rec_s=60.0,in_loop=True):
    b=bytearray(STEP_SIZE); pi(b,OFF_IDX,idx); pi(b,OFF_TYPE,TYPE_REST)
    pf(b,OFF_RDUR,dur_s); pf(b,OFF_RTIME,rec_s)
    if in_loop: pi(b,OFF_F496,1)
    return bytes(b)

def blk_cccv(idx,v,i,tl,cv,rv=10.0,rt=30.0):
    b=bytearray(STEP_SIZE); pi(b,OFF_IDX,idx); pi(b,OFF_TYPE,TYPE_CCCV)
    pf(b,OFF_CCVV,v); pf(b,OFF_CCI,i); pf(b,OFF_CCTL,tl); pf(b,OFF_CVCO,cv)
    pf(b,OFF_RVOLT,rv); pf(b,OFF_RTIME,rt); pi(b,OFF_F496,1)
    return bytes(b)

def blk_ccdi(idx,i,vc,vl=2000.0,tl=0.0,rv=10.0,rt=30.0):
    b=bytearray(STEP_SIZE); pi(b,OFF_IDX,idx); pi(b,OFF_TYPE,TYPE_CCDi)
    pf(b,OFF_VLIM,vl); pf(b,OFF_CCI,i)
    if tl>0: pf(b,OFF_CCTL,tl)
    pf(b,OFF_VC,vc); pf(b,OFF_RVOLT,rv); pf(b,OFF_RTIME,rt); pi(b,OFF_F496,1)
    return bytes(b)

def blk_marker(idx,flag=64):
    b=bytearray(STEP_SIZE); pi(b,OFF_IDX,idx); pi(b,OFF_TYPE,TYPE_CYCLE); pi(b,flag,1)
    return bytes(b)

def blk_loop(idx,cnt,rst=False):
    b=bytearray(STEP_SIZE); pi(b,OFF_IDX,idx); pi(b,OFF_TYPE,TYPE_LOOP)
    pi(b,OFF_CNT,cnt)
    if rst: pi(b,OFF_F496,1)
    pi(b,OFF_GOTO,1)
    return bytes(b)

def blk_end(idx):
    b=bytearray(STEP_SIZE); pi(b,OFF_IDX,idx); pi(b,OFF_TYPE,TYPE_END); return bytes(b)

def s2b(step,idx,cap,in_loop):
    t=step["type"]; rv=step.get("record_voltage_V",0.01)*1000
    if t=="rest":
        return blk_rest(idx,pdur(step["duration"]),pdur(step.get("record_time","1min")),in_loop)
    if t=="cccv_charge":
        return blk_cccv(idx,step["voltage_V"]*1000,pdur(step["current"],cap),
                        pdur(step["time_limit"]),pdur(step["cv_cutoff"],cap),
                        rv,pdur(step.get("record_time","30s")))
    if t=="cc_discharge":
        return blk_ccdi(idx,pdur(step["current"],cap),step["voltage_cutoff_V"]*1000,
                        step.get("voltage_limit_V",2.0)*1000,
                        pdur(step.get("time_limit","0s")),rv,
                        pdur(step.get("record_time","30s")))
    raise ValueError("Unknown step type: "+t)

def make_header(name,safety,auth="user"):
    h=bytearray(HEADER_SIZE); h[0:8]=MAGIC
    ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S.000").encode("ascii")
    h[0x08:0x08+len(ts)]=ts
    h[HOFF_SIG:HOFF_SIG+len(FILE_SIG)]=FILE_SIG
    try: ab=auth.encode("cp949")[:60]
    except: ab=auth.encode("ascii",errors="replace")[:60]
    h[HOFF_AUTH:HOFF_AUTH+len(ab)]=ab; h[HOFF_TS2:HOFF_TS2+len(ts)]=ts
    fn=(name+".sch").encode("cp949",errors="replace")[:100]
    h[0x290]=1; h[0x294]=2; h[HOFF_NAME:HOFF_NAME+len(fn)]=fn
    h[HOFF_TS3:HOFF_TS3+len(ts)]=ts
    so=HOFF_SAFE
    struct.pack_into("<f",h,so+0,safety.get("max_voltage_V",4.3)*1000)
    struct.pack_into("<f",h,so+4,safety.get("min_voltage_V",1.5)*1000)
    struct.pack_into("<f",h,so+8,safety.get("max_current_mA",0.0))
    struct.pack_into("<f",h,so+12,safety.get("max_capacity_mAh",100.0))
    struct.pack_into("<f",h,so+16,0.0)
    struct.pack_into("<f",h,so+20,safety.get("max_temp_C",70.0))
    struct.pack_into("<i",h,0x404,7)
    return bytes(h)

def build_single_loop(cap,pre,loop_def):
    blks=[]; idx=1; has_loop=loop_def is not None
    if pre:
        for s in pre:
            blks.append(s2b(s,idx,cap,False)); idx+=1
        blks.append(blk_loop(idx,1,False)); idx+=1
        if has_loop: blks.append(blk_marker(idx,64)); idx+=1
    if has_loop:
        for s in loop_def.get("steps",[]): blks.append(s2b(s,idx,cap,True)); idx+=1
        blks.append(blk_loop(idx,loop_def.get("count",1),loop_def.get("reset_capacity",False))); idx+=1
    blks.append(blk_end(idx)); return blks

def build_multi_cycle(cap,pre,cycles):
    blks=[]; idx=1; has_pre=len(pre)>0
    if has_pre:
        for s in pre: blks.append(s2b(s,idx,cap,False)); idx+=1
        blks.append(blk_loop(idx,1,False)); idx+=1
        blks.append(blk_marker(idx,496)); idx+=1
    for ci,cyc in enumerate(cycles):
        steps=cyc.get("steps",[]); cnt=cyc.get("count",1); rst=cyc.get("reset_capacity",True)
        if not has_pre and ci==0: blks.append(blk_marker(idx,496)); idx+=1
        for s in steps: blks.append(s2b(s,idx,cap,True)); idx+=1
        blks.append(blk_loop(idx,cnt,rst)); idx+=1
        if ci<len(cycles)-1: blks.append(blk_marker(idx,64)); idx+=1
    blks.append(blk_end(idx)); return blks

def build_rt_cl(cap,cycles,followup):
    """Rate Test + CycleLife: first RT cycle has NO leading marker."""
    blks=[]; idx=1
    for ci,cyc in enumerate(cycles):
        steps=cyc.get("steps",[]); cnt=cyc.get("count",1); rst=cyc.get("reset_capacity",True)
        for s in steps: blks.append(s2b(s,idx,cap,True)); idx+=1
        blks.append(blk_loop(idx,cnt,rst)); idx+=1
        if ci<len(cycles)-1: blks.append(blk_marker(idx,64)); idx+=1
    if followup:
        pre=followup.get("pre_loop",[])
        ldef=followup.get("loop",{})
        if pre:
            for s in pre: blks.append(s2b(s,idx,cap,False)); idx+=1
            blks.append(blk_loop(idx,1,False)); idx+=1
        blks.append(blk_marker(idx,64)); idx+=1
        for s in ldef.get("steps",[]): blks.append(s2b(s,idx,cap,True)); idx+=1
        blks.append(blk_loop(idx,ldef.get("count",1),ldef.get("reset_capacity",True))); idx+=1
    blks.append(blk_end(idx)); return blks

def build_blocks(sched):
    meta=sched.get("metadata",{}); cap=meta.get("cell_capacity_mAh",1000.0)
    tt=meta.get("test_type",None)
    pre=sched.get("pre_loop",[]); ldef=sched.get("loop",None)
    cycs=sched.get("cycles",None); fup=sched.get("followup",None)
    if tt:
        pre=auto_rest(pre,tt)
        if ldef and "steps" in ldef:
            ldef=dict(ldef); ldef["steps"]=auto_rest(ldef["steps"],tt)
        if cycs: cycs=[{**c,"steps":auto_rest(c.get("steps",[]),tt)} for c in cycs]
        if fup:
            fl=dict(fup.get("loop",{}))
            if "steps" in fl: fl["steps"]=auto_rest(fl["steps"],tt)
            fup={**fup,"loop":fl}
    if tt=="ratetest_cyclelife" and cycs: return build_rt_cl(cap,cycs,fup)
    if cycs: return build_multi_cycle(cap,pre,cycs)
    return build_single_loop(cap,pre,ldef)

def json_to_sch(jin,out):
    if isinstance(jin,str):
        with open(jin,"r",encoding="utf-8") as f: data=json.load(f)
    else: data=jin
    meta=data.get("metadata",{}); safety=meta.get("safety",{})
    sname=meta.get("schedule_name","schedule"); author=meta.get("author","user")
    tt=meta.get("test_type","?")
    print("[Generate] %s (type=%s)"%(sname,tt))
    hdr=make_header(sname,safety,author); blks=build_blocks(data)
    total=len(hdr)+len(blks)*STEP_SIZE
    print("  Steps: %d  Total: %d bytes"%(len(blks),total))
    with open(out,"wb") as f:
        f.write(hdr)
        for b in blks: f.write(b)
    print("  [Done] -> "+out)
    return out
