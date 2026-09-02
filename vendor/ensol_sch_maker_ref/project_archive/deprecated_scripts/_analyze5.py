"""Check if reference step number is stored in header or footer region."""
import struct

with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760
SZ  = 612
num_steps = (len(data) - HDR) // SZ
print(f"File size: {len(data)}, header={HDR}, step size={SZ}, num steps={num_steps}")
print(f"Footer/remainder: {len(data) - HDR - num_steps*SZ} bytes")
print()

# Look in header for small ints that might be step refs (7, 25, 35, 45)
print("=== Search header (0..1760) for uint16 = 7 or 25 or 35 or 45 ===")
for off in range(0, HDR-2, 2):
    v = struct.unpack_from('<H', data, off)[0]
    if v in (7, 25, 35, 45):
        ctx = ' '.join(f'{x:02x}' for x in data[max(0,off-4):min(HDR,off+6)])
        print(f"  off {off:5d}: u16={v:3d}  ctx={ctx}")

print()
# Footer search
if len(data) > HDR + num_steps*SZ:
    footer = data[HDR + num_steps*SZ:]
    print(f"=== Footer ({len(footer)} bytes) hex dump ===")
    for i in range(0, min(len(footer), 256), 16):
        print(f"  {i:04x}: {' '.join(f'{x:02x}' for x in footer[i:i+16])}")

print()
# Let me also print the full FIRST 128 bytes of Step 21 and Step 27 to compare headers within the block
print("=== Step 21 bytes 0..128 ===")
b21 = data[HDR + 20*SZ : HDR + 20*SZ + 128]
for i in range(0, 128, 16):
    print(f"  {i:04x}: {' '.join(f'{x:02x}' for x in b21[i:i+16])}")
print("=== Step 27 bytes 0..128 ===")
b27 = data[HDR + 26*SZ : HDR + 26*SZ + 128]
for i in range(0, 128, 16):
    print(f"  {i:04x}: {' '.join(f'{x:02x}' for x in b27[i:i+16])}")

print()
# Check bytes 384-420 range in Step 21 and Step 27 (where DOD% is)
print("=== Step 21 bytes 380..420 ===")
b21r = data[HDR + 20*SZ + 380 : HDR + 20*SZ + 420]
print(f"  {' '.join(f'{x:02x}' for x in b21r)}")
print("=== Step 27 bytes 380..420 ===")
b27r = data[HDR + 26*SZ + 380 : HDR + 26*SZ + 420]
print(f"  {' '.join(f'{x:02x}' for x in b27r)}")

# Search Step 21 block broadly for byte 7 (step 7 reference)
print()
print("=== Positions of byte value 0x07 in Step 21 block ===")
b21_full = data[HDR + 20*SZ : HDR + 20*SZ + SZ]
for off in range(SZ):
    if b21_full[off] == 0x07:
        ctx = ' '.join(f'{x:02x}' for x in b21_full[max(0,off-3):min(SZ,off+5)])
        print(f"  off {off:3d}: ctx={ctx}")

print()
print("=== Positions of byte value 0x19 (=25) in Step 27 block ===")
b27_full = data[HDR + 26*SZ : HDR + 26*SZ + SZ]
for off in range(SZ):
    if b27_full[off] == 0x19:
        ctx = ' '.join(f'{x:02x}' for x in b27_full[max(0,off-3):min(SZ,off+5)])
        print(f"  off {off:3d}: ctx={ctx}")
