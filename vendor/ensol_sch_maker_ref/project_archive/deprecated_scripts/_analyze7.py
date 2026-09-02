"""Dump LOOP step key fields: count at off52, goto at off564, off88."""
import struct

with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760; SZ = 612
TYPE_LOOP = 8

print(f"{'IDX':>3} {'StepN':>5} {'cnt@52':>7} {'goto@564':>9} {'f@88':>6} {'f@496-499 hex':>15}")
for idx in range((len(data) - HDR) // SZ):
    b = data[HDR+idx*SZ : HDR+idx*SZ+SZ]
    stype = struct.unpack_from('<H', b, 8)[0]
    if stype != TYPE_LOOP:
        continue
    step_n = struct.unpack_from('<I', b, 0)[0]
    cnt    = struct.unpack_from('<I', b, 52)[0]
    goto   = struct.unpack_from('<I', b, 564)[0]
    f88    = struct.unpack_from('<I', b, 88)[0]
    f496   = ' '.join(f'{x:02x}' for x in b[496:500])
    print(f"{idx:3d} {step_n:5d} {cnt:7d} {goto:9d} {f88:6d}   {f496}")
