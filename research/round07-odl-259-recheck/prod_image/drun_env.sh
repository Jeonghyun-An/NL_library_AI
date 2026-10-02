#!/bin/bash
# same as drun.sh but passes extra env: first arg is a comma-separated K=V list
IFS=',' read -ra KV <<< "$1"; shift
EA=(); for kv in "${KV[@]}"; do EA+=(-e "$kv"); done
MSYS_NO_PATHCONV=1 exec docker run --rm --pull never --network none --init -w /app "${EA[@]}"   -v "C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/odl259/code/app:/app:ro" -v "D:/SKOVIX/KCI/pdf:/pdf:ro" -v "C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/odl259/verify_adv:/w" -v "C:/Users/LANDSOFT/AppData/Local/Temp/claude/C--Users-LANDSOFT-mygit-NL-library-AI/ac2847f8-32b7-46ce-8254-e87152398b72/scratchpad/odl259/compare_runs:/ref:ro"   -e PYTHONPATH=/app --entrypoint python landsoftdocker/nl-lib-fastapi:latest /w/prod_check.py "$@"
