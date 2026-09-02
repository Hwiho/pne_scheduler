import struct
with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760
SZ = 612

targets = [
    ("Step 20 (SOC to 80%) CCDi", 19),
    ("Step 22 (LOOP)", 21),
    ("Step 24 (Pulse) CCDi", 23),
    ("Step 26 (Return CCCh)", 25),
    ("Step 28 (LOOP)", 27),
    ("Step 30 (SOC to 50%) CCDi", 29),
    ("Step 34 (Pulse 50%) CCDi", 33),
    ("Step 40 (SOC to 20%) CCDi", 39),
    ("Step 44 (Pulse 20%) CCDi", 43),
    ("Step 48 (LOOP)", 47),
]

for label, s in targets:
    base = HDR + s * SZ
    blk = data[base:base + SZ]
    idx = struct.unpack_from('<i', blk, 0)[0]
    typ = struct.unpack_from('<i', blk, 8)[0]
    print("\n=== " + label + "  (idx=" + str(idx) + ", type=0x" + format(typ, '04x') + ") ===")
    for off in range(0, 580, 4):
        i = struct.unpack_from('<i', blk, off)[0]
        fv = struct.unpack_from('<f', blk, off)[0]
        if i == 0 and abs(fv) < 1e-10:
            continue
        fstr = ""
        if abs(fv) > 1e-5 and abs(fv) < 1e10:
            fstr = "  float=" + ("%14.4f" % fv)
        print("  off " + str(off).rjust(3) + ": int=" + str(i).rjust(12) + fstr)
