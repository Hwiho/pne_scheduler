"""Find reference step number in capacity-cutoff CCDi step."""
import struct

with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760
SZ  = 612

# Dump ALL non-zero bytes of Step 20 (s=19) to find any small integer that might be the ref step
s = 19
base = HDR + s * SZ
blk = data[base:base+SZ]

print("=== FULL dump Step 20 (SOC to 80% = DOD 20%, capacity cutoff) ===")
print("Looking for small int values that could be a step reference (1..80):")
for off in range(0, SZ, 2):
    # try short int and byte
    v_s = struct.unpack_from('<h', blk, off)[0]
    v_i = struct.unpack_from('<i', blk, off)[0] if off <= SZ-4 else None
    if v_s != 0 and abs(v_s) < 200:
        tag = ""
        if v_i is not None and v_i == v_s:
            tag = " (also int)"
        print("  off " + str(off).rjust(3) + ": short=" + str(v_s).rjust(6) + tag)

print()
print("=== Byte-level non-zero regions in Step 20 ===")
i = 0
while i < SZ:
    if blk[i] != 0:
        # find run of non-zero bytes
        j = i
        while j < SZ and not (blk[j] == 0 and (j+1 >= SZ or blk[j+1] == 0) and (j+2 >= SZ or blk[j+2] == 0)):
            j += 1
        hx = ' '.join('%02x' % b for b in blk[i:j])
        if len(hx) > 80:
            hx = hx[:80] + '...'
        print("  off " + str(i).rjust(3) + "-" + str(j).rjust(3) + ": " + hx)
        i = j + 1
    else:
        i += 1

# Check specifically: bytes 490-510 since off 496 has the flag 1793 (=0x0701)
print()
print("=== Bytes 485-515 hex around flag offset (Step 20) ===")
print(' '.join('%02x' % b for b in blk[485:515]))
print("=== Bytes 485-515 hex around flag offset (Step 24, time-cutoff) ===")
blk24 = data[HDR + 23*SZ : HDR + 24*SZ]
print(' '.join('%02x' % b for b in blk24[485:515]))
print("=== Bytes 485-515 hex around flag offset (Step 26, return charge 100%) ===")
blk26 = data[HDR + 25*SZ : HDR + 26*SZ]
print(' '.join('%02x' % b for b in blk26[485:515]))

# Check if step 30 has different ref step than step 20
print()
print("=== Step 20 vs Step 40 (both SOC steps, different reference) ===")
s1, s2 = 19, 39
b1 = data[HDR + s1*SZ : HDR + (s1+1)*SZ]
b2 = data[HDR + s2*SZ : HDR + (s2+1)*SZ]
for off in range(0, SZ, 2):
    v1 = struct.unpack_from('<h', b1, off)[0]
    v2 = struct.unpack_from('<h', b2, off)[0]
    if v1 != v2 and (abs(v1) < 200 or abs(v2) < 200):
        print("  off " + str(off).rjust(3) + ": s20 short=" + str(v1).rjust(6) + "  s40 short=" + str(v2).rjust(6))
