"""Dump all steps' key fields to understand the full schedule structure."""
import struct

with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760
SZ  = 612
num_steps = (len(data) - HDR) // SZ

print(f"{'IDX':>3} {'StepN':>5} {'Type':>8} {'Cur(A)':>8} {'Time(s)':>10} {'VCut(V)':>8} {'ICut':>8} {'DOD%':>7} {'Flag':>8} {'off88':>6}")
print("-" * 85)

TYPE_NAMES = {
    0x0003: "REST",
    0x0006: "END",
    0x0007: "CYCMRK",
    0x0008: "LOOP",
    0x0101: "CCCV",
    0x0201: "CCCh",
    0x0202: "CCDi",
}

for idx in range(num_steps):
    b = data[HDR + idx*SZ : HDR + idx*SZ + SZ]
    step_n = struct.unpack_from('<I', b, 0)[0]
    step_t = struct.unpack_from('<H', b, 8)[0]
    cur    = struct.unpack_from('<f', b, 16)[0]
    tcut   = struct.unpack_from('<f', b, 20)[0]
    vcut   = struct.unpack_from('<f', b, 332)[0]
    icut   = struct.unpack_from('<f', b, 340)[0]
    dod    = struct.unpack_from('<f', b, 384)[0]
    flag   = struct.unpack_from('<H', b, 496)[0]
    off88  = struct.unpack_from('<I', b, 88)[0]

    tname = TYPE_NAMES.get(step_t, f"0x{step_t:04x}")
    print(f"{idx:3d} {step_n:5d} {tname:>8} {cur:8.3f} {tcut:10.1f} {vcut:8.2f} {icut:8.3f} {dod:7.1f} 0x{flag:04x}   {off88:5d}")
