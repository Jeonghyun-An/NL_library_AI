import zipfile, struct, sys, collections
for v in ("250","259"):
    p = rf"{sys.argv[1]}/src{v}/opendataloader_pdf/jar/opendataloader-pdf-cli.jar"
    z = zipfile.ZipFile(p)
    hist = collections.Counter(); top = collections.defaultdict(collections.Counter)
    mr = collections.Counter()
    for n in z.namelist():
        if not n.endswith(".class"): continue
        b = z.open(n).read(8)
        if b[:4] != b"\xca\xfe\xba\xbe": continue
        major = struct.unpack(">H", b[6:8])[0]
        if n.startswith("META-INF/versions/"):
            mr[(n.split("/")[2], major)] += 1; continue
        hist[major] += 1
        pref = "/".join(n.split("/")[:3])
        top[major][pref] += 1
    print(v, "base:", dict(hist), "multirelease:", dict(mr))
    for m in sorted(top):
        if m > 55: print("  major", m, top[m].most_common(15))
    mf = z.read("META-INF/MANIFEST.MF").decode()
    print("  Multi-Release" in mf, [l for l in mf.splitlines() if "Multi" in l])
