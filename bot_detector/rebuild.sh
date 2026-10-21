#!/usr/bin/env bash
#
# rebuild.sh — izgradnja podataka Cacix sistema jednim pozivom.
#
# Radi redom: (0) preuzimanje SQLite baze sa ocisti.net / Mega.nz (ako nedostaje) →
#             (3) uvoz SQLite→Postgres → (4) Neo4j graf + skorovi →
#             (5) GeoIP dataset + svi analitički JSON-ovi.
# Pretpostavke: Docker baze su podignute (`docker compose up -d`).
#               Ako `data/progress_baza_podataka.sqlite3` ne postoji, skripta je
#               automatski preuzima i dešifruje sa https://ocisti.net/ (Mega.nz).
#
# Upotreba:
#   ./rebuild.sh                 # pun rebuild (download ako treba, uvoz, graf, geoip, analize)
#   ./rebuild.sh --download-only # samo preuzmi i dešifruje SQLite bazu
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
OCISTI_URL="https://ocisti.net/"
MEGA_FALLBACK_URL="https://mega.nz/file/KDJ1FTDC#SOEiEWxUH19WRJhyxu_QrrsRgl-EubHq31p7r1Xwjq8"
GEOIP="data/geo/ip2asn-v4.tsv.gz"
GEOIP_URL="https://iptoasn.com/data/ip2asn-v4.tsv.gz"
ANALYSIS=(voter_geoip betting_geo task_masters voter_timing command_responsibility
          directives coordinators cascade betting_corporate shift_chat gamification_points
          regional_operations voter_kurir_links voter_custom_actions tactical_groups
          system_surveillance multiplatform)

FORCE=""; DO_IMPORT=1; DO_GRAPH=1; DO_ANALYSIS=1; DOWNLOAD_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --download-only) DOWNLOAD_ONLY=1; DO_IMPORT=0; DO_GRAPH=0; DO_ANALYSIS=0 ;;
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

download_sqlite() {
  say "Preuzimanje SQLite baze ($SQLITE nije pronađena lokalno)"
  command -v curl >/dev/null && command -v openssl >/dev/null || {
    err "Za automatsko preuzimanje sa Mega.nz potrebni su 'curl' i 'openssl'."
    exit 1
  }
  mkdir -p "$(dirname "$SQLITE")"

  # 1) Pokušaj da izvučeš aktuelni Mega.nz link sa https://ocisti.net/ (#baza-podataka),
  #    a ako sajt nije dostupan koristi fallback link (ili $SQLITE_MEGA_URL).
  local mega_meta
  if ! mega_meta=$("$PY" - "$OCISTI_URL" "${SQLITE_MEGA_URL:-$MEGA_FALLBACK_URL}" <<'PYMEGA'
import base64, json, re, struct, sys, urllib.request

ocisti_url, fallback_url = sys.argv[1], sys.argv[2]
mega_url = fallback_url
try:
    req = urllib.request.Request(ocisti_url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", "ignore")
    sec = re.search(r'id="baza-podataka".*?</section>', html, re.S)
    m = re.search(r'https://mega\.nz/file/[A-Za-z0-9_-]+#[A-Za-z0-9_-]+', sec.group(0) if sec else html)
    if m:
        mega_url = m.group(0)
except Exception:
    pass

m = re.match(r'^https://mega\.nz/file/([A-Za-z0-9_-]+)#([A-Za-z0-9_-]+)$', mega_url.strip())
if not m:
    sys.exit(f"Neispravan Mega URL: {mega_url}")
fid, b64key = m.group(1), m.group(2)
b64key += "=" * ((4 - len(b64key) % 4) % 4)
k = struct.unpack(">8I", base64.urlsafe_b64decode(b64key))
aes_key = struct.pack(">4I", k[0]^k[4], k[1]^k[5], k[2]^k[6], k[3]^k[7]).hex()
aes_iv  = struct.pack(">4I", k[4], k[5], 0, 0).hex()

api_req = urllib.request.Request(
    "https://g.api.mega.co.nz/cs",
    data=json.dumps([{"a": "g", "g": 1, "p": fid}]).encode(),
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
)
resp = json.loads(urllib.request.urlopen(api_req, timeout=15).read().decode())
if not isinstance(resp, list) or not isinstance(resp[0], dict) or "g" not in resp[0]:
    sys.exit(f"Mega API greška ({resp}) za {mega_url} (moguće prekoračenje kvote; preuzmi ručno u browseru)")

print(f"{mega_url}\n{resp[0]['g']}\n{aes_key}\n{aes_iv}\n{resp[0].get('s', 0)}")
PYMEGA
  ); then
    err "Nije uspelo dobijanje download sesije sa Mega.nz."
    err "Preuzmi bazu ručno sa: $OCISTI_URL ($MEGA_FALLBACK_URL) i sačuvaj u $SQLITE"
    exit 1
  fi

  local resolved_mega g_url hex_key hex_iv fsize
  {
    read -r resolved_mega
    read -r g_url
    read -r hex_key
    read -r hex_iv
    read -r fsize
  } <<< "$mega_meta"

  echo "  • Izvor : $resolved_mega (~$(( fsize / 1024 / 1024 )) MB)"
  echo "  • Cilj  : $SQLITE (streaming AES-128-CTR dešifrovanje u letu)"

  rm -f "$SQLITE.part"
  if ! curl -fL "$g_url" | openssl enc -d -aes-128-ctr -K "$hex_key" -iv "$hex_iv" > "$SQLITE.part"; then
    rm -f "$SQLITE.part"
    err "Preuzimanje prekinuto. Pokušaj ponovo ili preuzmi ručno sa $resolved_mega"
    exit 1
  fi

  local hdr
  hdr=$(head -c 15 "$SQLITE.part" 2>/dev/null || true)
  if [ "$hdr" != "SQLite format 3" ]; then
    rm -f "$SQLITE.part"
    err "Dešifrovani fajl nema ispravan SQLite zaglavlje! Proveri link na $OCISTI_URL"
    exit 1
  fi

  mv "$SQLITE.part" "$SQLITE"
  say "SQLite baza uspešno preuzeta i verifikovana ($SQLITE)"
}

# --- preflight ----------------------------------------------------------------
[ -x "$PY" ] || { err "venv ne postoji ($PY). Pokreni: python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"; exit 1; }
if [ "$DOWNLOAD_ONLY" = 1 ]; then
  if [ -f "$SQLITE" ]; then
    say "SQLite baza već postoji: $SQLITE ($(stat -c %s "$SQLITE") bajtova)"
  else
    download_sqlite
  fi
  exit 0
fi
if [ "$DO_IMPORT" = 1 ] && [ ! -f "$SQLITE" ]; then
  download_sqlite
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
