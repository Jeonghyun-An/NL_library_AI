#!/bin/bash
# odl_heap: the four production-identical passes (no extra JVM flags) then a G1-log pass without a cap
cd "$(dirname "$0")"
./drun.sh - /w/driver.py nocap > out/nocap.out 2>&1
./drun.sh -Xmx3g /w/driver.py xmx3g > out/xmx3g.out 2>&1
./drun.sh -Xmx2g /w/driver.py xmx2g > out/xmx2g.out 2>&1
./drun.sh -Xmx1g /w/driver.py xmx1g > out/xmx1g.out 2>&1
./drun.sh - /w/driver.py nocap_gc --gc > out/nocap_gc.out 2>&1
echo ALLDONE >> out/run_all.done
