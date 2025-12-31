#!/bin/bash
cd /mnt/d/sanskrit/sanskritsahitya-com/data

for chapter in 2 3 4 5 6 7 8 10 12 13 14 15 16 17 20
do
    echo "=== Processing Chapter $chapter ==="
    python3 code/populate_mallinatha_commentary.py shishupalavadham/chapter${chapter}_wikisource.txt $chapter 2>&1 | tail -5
    echo ""
done
