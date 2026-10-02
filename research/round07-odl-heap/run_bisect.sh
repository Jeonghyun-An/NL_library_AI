#!/bin/bash
# odl_heap: minimum heap per heavy document — KCI_FI002990049 finely, the next heaviest coarsely (G1 log on)
cd "$(dirname "$0")"
for c in 1152m 1280m 1408m 1536m 1664m 1792m; do
  ./drun.sh -Xmx$c /w/driver.py bis_$c --gc --ids KCI_FI002990049 KCI_FI002990049 > out/bis_$c.out 2>&1
done
for c in 384m 512m 768m; do
  ./drun.sh -Xmx$c /w/driver.py bis_$c --gc --ids KCI_FI002990049 KCI_FI003315691 KCI_FI001372507 KCI_FI002298010 KCI_FI001160724 KCI_FI001401892 KCI_FI001428194 KCI_FI001930485 KCI_FI002252358 KCI_FI001827561 KCI_FI003214027 KCI_FI001667569 > out/bis_$c.out 2>&1
done
./drun.sh -Xmx1g /w/driver.py bis_1g --gc --ids KCI_FI002990049 KCI_FI003315691 KCI_FI001372507 KCI_FI002298010 KCI_FI001238691 > out/bis_1g.out 2>&1
./drun.sh -Xmx2g /w/driver.py bis_2g --gc --ids KCI_FI002990049 KCI_FI003315691 KCI_FI001372507 KCI_FI002298010 KCI_FI001238691 > out/bis_2g.out 2>&1
./drun.sh -Xmx3g /w/driver.py bis_3g --gc --ids KCI_FI002990049 KCI_FI003315691 KCI_FI001372507 KCI_FI002298010 KCI_FI001238691 > out/bis_3g.out 2>&1
echo done > out/bisect.done
