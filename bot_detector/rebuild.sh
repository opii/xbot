#!/usr/bin/env bash
#
# rebuild.sh — izgradnja podataka Cacix sistema jednim pozivom.
#
# Radi redom: (3) uvoz SQLite→Postgres → (4) Neo4j graf + skorovi →
#             (5) GeoIP dataset + svi analitički JSON-ovi.
# Pretpostavke: Docker baze su podignute (`docker compose up -d`) i
#               `data/progress_baza_podataka.sqlite3` je na mestu.
#
# Upotreba:
#   ./rebuild.sh                 # pun rebuild (uvoz ako treba, graf, geoip, analize)
#   ./rebuild.sh --force         # prisilan ponovni uvoz baze
#   ./rebuild.sh --skip-import   # preskoči uvoz (Postgres već pun)
#   ./rebuild.sh --skip-analysis # samo uvoz + graf
#   ./rebuild.sh --analysis-only # samo GeoIP + analitički JSON-ovi
#   ./rebuild.sh -h | --help
#
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # uvek radi iz bot_detector/

PY="./venv/bin/python"
SQLITE="data/progress_baza_podataka.sqlite3"
GEOIP="data/geo/ip2asn-v4.tsv.gz"
GEOIP_URL="https://iptoasn.com/data/ip2asn-v4.tsv.gz"
ANALYSIS=(voter_geoip betting_geo task_masters voter_timing command_responsibility
          directives coordinators cascade betting_corporate shift_chat gamification_points
          regional_operations voter_kurir_links voter_custom_actions tactical_groups
          system_surveillance multiplatform)

FORCE=""; DO_IMPORT=1; DO_GRAPH=1; DO_ANALYSIS=1
for arg in "$@"; do
  case "$arg" in
    --force) FORCE="--force" ;;
    --skip-import) DO_IMPORT=0 ;;
    --skip-analysis) DO_ANALYSIS=0 ;;
    --analysis-only) DO_IMPORT=0; DO_GRAPH=0 ;;
    -h|--help) grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Nepoznat argument: $arg (vidi --help)"; exit 2 ;;
  esac
done

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
err() { printf '\033[1;31m[GREŠKA] %s\033[0m\n' "$*" >&2; }
t0=$(date +%s)

# --- preflight ----------------------------------------------------------------
[ -x "$PY" ] || { err "venv ne postoji ($PY). Pokreni: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"; exit 1; }
if [ "$DO_IMPORT" = 1 ] && [ ! -f "$SQLITE" ]; then
  err "SQLite baza ne postoji: $SQLITE (postavi je ili koristi --skip-import)"; exit 1
fi
# provera da je Postgres dostupan
if ! "$PY" - <<'PYCHK' 2>/dev/null
import os, psycopg2
psycopg2.connect(os.environ.get("PROGRESS_PG_DSN",
    "host=localhost dbname=bot_detector_db user=bot_user password=bot_password")).close()
PYCHK
then
  err "Postgres nije dostupan na localhost:5432. Pokreni: docker compose up -d"; exit 1
fi

# --- 3) UVOZ ------------------------------------------------------------------
if [ "$DO_IMPORT" = 1 ]; then
  say "Korak 3/5 — uvoz SQLite → Postgres ${FORCE:+(force)}"
  "$PY" src/import_progress_db.py $FORCE
else
  say "Korak 3/5 — uvoz preskočen"
fi

# --- 4) GRAF ------------------------------------------------------------------
if [ "$DO_GRAPH" = 1 ]; then
  say "Korak 4/5 — Neo4j graf + organizatori + bihevioralni skorovi + burstovi"
  "$PY" src/graph/load_graph.py
else
  say "Korak 4/5 — graf preskočen"
fi

# --- 5) GEOIP + ANALIZE -------------------------------------------------------
if [ "$DO_ANALYSIS" = 1 ]; then
  if [ ! -f "$GEOIP" ]; then
    say "GeoIP dataset — preuzimanje (nije u repo-u)"
    curl -fL "$GEOIP_URL" -o "$GEOIP" || err "GeoIP download nije uspeo (voter_geoip će biti preskočen)"
  fi
  say "Korak 5/5 — analitički JSON-ovi (${#ANALYSIS[@]} modula)"
  failed=()
  for m in "${ANALYSIS[@]}"; do
    printf '  • %-24s ' "$m"
    if "$PY" "src/analysis/$m.py" >/dev/null 2>&1; then echo "ok"; else echo "PAO"; failed+=("$m"); fi
  done
  [ ${#failed[@]} -eq 0 ] || err "Nisu uspeli: ${failed[*]}"
else
  say "Korak 5/5 — analize preskočene"
fi

say "Gotovo za $(( $(date +%s) - t0 ))s. Pokreni backend: ./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --app-dir src"
