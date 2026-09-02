import struct
with open('form_RPT.sch', 'rb') as f:
    data = f.read()

HDR = 1760
SZ = 612

# Compare step 20 (capacity cutoff) vs step 24 (time cutoff)
# byte-by-byte diff
s1, s2 = 19, 23
b1 = data[HDR + s1*SZ : HDR + (s1+1)*SZ]
b2 = data[HDR + s2*SZ : HDR + (s2+1)*SZ]

print("Step 20 vs Step 24 byte differences:")
for off in range(0, SZ, 4):
    v1_i = struct.unpack_from('<i', b1, off)[0]
    v2_i = struct.unpack_from('<i', b2, off)[0]
    v1_f = struct.unpack_from('<f', b1, off)[0]
    v2_f = struct.unpack_from('<f', b2, off)[0]
    if v1_i != v2_i:
        s = "  off " + str(off).rjust(3)
        s += ": s20 int=" + str(v1_i).rjust(12)
        s += "  s24 int=" + str(v2_i).rjust(12)
        if abs(v1_f) > 1e-6 and abs(v1_f) < 1e10:
            s += "   (s20 f=" + ("%.3f" % v1_f) + ")"
        if abs(v2_f) > 1e-6 and abs(v2_f) < 1e10:
            s += "   (s24 f=" + ("%.3f" % v2_f) + ")"
        print(s)

print()
print("=" * 60)
print("Step 20 vs Step 30 (both SOC steps, different DOD):")
s1, s2 = 19, 29
b1 = data[HDR + s1*SZ : HDR + (s1+1)*SZ]
b2 = data[HDR + s2*SZ : HDR + (s2+1)*SZ]
for off in range(0, SZ, 4):
    v1_i = struct.unpack_from('<i', b1, off)[0]
    v2_i = struct.unpack_from('<i', b2, off)[0]
    v1_f = struct.unpack_from('<f', b1, off)[0]
    v2_f = struct.unpack_from('<f', b2, off)[0]
    if v1_i != v2_i:
        s = "  off " + str(off).rjust(3)
        s += ": s20 int=" + str(v1_i).rjust(12)
        s += "  s30 int=" + str(v2_i).rjust(12)
        if abs(v1_f) > 1e-6 and abs(v1_f) < 1e10:
            s += "   (s20 f=" + ("%.3f" % v1_f) + ")"
        if abs(v2_f) > 1e-6 and abs(v2_f) < 1e10:
            s += "   (s30 f=" + ("%.3f" % v2_f) + ")"
        print(s)

print()
print("=" * 60)
print("Step 24 vs Step 26 (pulse discharge vs return charge):")
s1, s2 = 23, 25
b1 = data[HDR + s1*SZ : HDR + (s1+1)*SZ]
b2 = data[HDR + s2*SZ : HDR + (s2+1)*SZ]
for off in range(0, SZ, 4):
    v1_i = struct.unpack_from('<i', b1, off)[0]
    v2_i = struct.unpack_from('<i', b2, off)[0]
    v1_f = struct.unpack_from('<f', b1, off)[0]
    v2_f = struct.unpack_from('<f', b2, off)[0]
    if v1_i != v2_i:
        s = "  off " + str(off).rjust(3)
        s += ": s24 int=" + str(v1_i).rjust(12)
        s += "  s26 int=" + str(v2_i).rjust(12)
        if abs(v1_f) > 1e-6 and abs(v1_f) < 1e10:
            s += "   (s24 f=" + ("%.3f" % v1_f) + ")"
        if abs(v2_f) > 1e-6 and abs(v2_f) < 1e10:
            s += "   (s26 f=" + ("%.3f" % v2_f) + ")"
        print(s)

print()
print("=" * 60)
print("Header - step reference bytes (safety region and beyond):")
# Check if header has step reference numbers
for off in range(1400, 1760, 4):
    v_i = struct.unpack_from('<i', data, off)[0]
    v_f = struct.unpack_from('<f', data, off)[0]
    if v_i != 0 and abs(v_i) < 10000:
        fstr = ""
        if abs(v_f) > 1e-6 and abs(v_f) < 1e10:
            fstr = "  f=" + ("%.3f" % v_f)
        print("  off " + str(off).rjust(4) + ": int=" + str(v_i) + fstr)
