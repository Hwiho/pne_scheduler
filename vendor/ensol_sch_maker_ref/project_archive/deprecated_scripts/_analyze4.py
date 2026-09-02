"""Find reference step field by comparing Steps 27, 37, 47 (ref 25, 35, 45)."""
import struct

with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760
SZ  = 612

def blk(step_num):
    idx = step_num - 1
    return data[HDR + idx*SZ : HDR + idx*SZ + SZ]

print("=" * 70)
print("Step 27 vs Step 37 vs Step 47 (return 100% referencing 25/35/45)")
print("=" * 70)
b27 = blk(27); b37 = blk(37); b47 = blk(47)

# Find all offsets where bytes differ across the three
for off in range(SZ):
    if b27[off] != b37[off] or b27[off] != b47[off] or b37[off] != b47[off]:
        print(f"  off {off:3d}: s27=0x{b27[off]:02x}  s37=0x{b37[off]:02x}  s47=0x{b47[off]:02x}")

print()
print("=" * 70)
print("Interpret as integers at differing 2/4-byte aligned offsets")
print("=" * 70)
# Print bytes grouped as uint16 and uint32 at points of interest
for off in range(0, SZ-4, 2):
    u16_27 = struct.unpack_from('<H', b27, off)[0]
    u16_37 = struct.unpack_from('<H', b37, off)[0]
    u16_47 = struct.unpack_from('<H', b47, off)[0]
    if u16_27 != u16_37 or u16_27 != u16_47:
        # Only show "small" values (1..100) that could be step refs
        if any(1 <= v <= 80 for v in (u16_27, u16_37, u16_47)):
            print(f"  off {off:3d} u16: s27={u16_27:5d}  s37={u16_37:5d}  s47={u16_47:5d}")

print()
print("=" * 70)
print("Step 21 vs Step 31 vs Step 41 (SOC cutoff, all referencing Step 7)")
print("=" * 70)
b21 = blk(21); b31 = blk(31); b41 = blk(41)

# These should only differ in step_num field (off 0) and DOD% (off 384) if ref is same
for off in range(SZ):
    if b21[off] != b31[off] or b21[off] != b41[off] or b31[off] != b41[off]:
        print(f"  off {off:3d}: s21=0x{b21[off]:02x}  s31=0x{b31[off]:02x}  s41=0x{b41[off]:02x}")

print()
print("=" * 70)
print("Find 'step 7' value (0x07 0x00) in Step 21 block")
print("=" * 70)
for off in range(SZ-1):
    if b21[off] == 0x07 and b21[off+1] == 0x00:
        # Could be uint16=7 or part of something else
        # Check context
        ctx = b21[max(0,off-2):min(SZ,off+4)]
        print(f"  off {off:3d}: 0x07 0x00 found  ctx={' '.join(f'{x:02x}' for x in ctx)}")

print()
print("=" * 70)
print("Find step-number uint16 patterns in Step 27 that match 25 (0x19 0x00)")
print("=" * 70)
for off in range(SZ-1):
    if b27[off] == 0x19 and b27[off+1] == 0x00:
        # check if s37 has 0x23 (35) and s47 has 0x2d (45) at same offset
        if b37[off] == 0x23 and b47[off] == 0x2d:
            ctx27 = ' '.join(f'{x:02x}' for x in b27[max(0,off-2):min(SZ,off+4)])
            ctx37 = ' '.join(f'{x:02x}' for x in b37[max(0,off-2):min(SZ,off+4)])
            ctx47 = ' '.join(f'{x:02x}' for x in b47[max(0,off-2):min(SZ,off+4)])
            print(f"  off {off:3d}: MATCH! (25/35/45)")
            print(f"    s27: {ctx27}")
            print(f"    s37: {ctx37}")
            print(f"    s47: {ctx47}")
        else:
            print(f"  off {off:3d}: s27=0x19 0x00 but s37=0x{b37[off]:02x} 0x{b37[off+1]:02x}, s47=0x{b47[off]:02x} 0x{b47[off+1]:02x}")
