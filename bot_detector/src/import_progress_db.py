#!/usr/bin/env python3
"""
Uvoz kompletne SQLite baze (progress_baza_podataka.sqlite3) u PostgreSQL.

Verno prebacuje SVE tabele i SVE kolone 1:1 (bez izbacivanja kolona).
Koristi COPY u serijama radi brzine, a indekse pravi tek na kraju.

Pokretanje:
    cd bot_detector
    ./venv/bin/python src/import_progress_db.py
    # opcije:
    #   --sqlite PUTANJA   (podrazumevano data/progress_baza_podataka.sqlite3)
    #   --only t1,t2       (uvezi samo navedene tabele)
    #   --schema progress  (ciljna PG šema, podrazumevano 'progress')
    #   --batch 50000      (broj redova po COPY seriji)
"""
import argparse
import csv
import io
import os
import re
import sqlite3
import sys
import time

import psycopg2

# Neki šifarnici u izvoru imaju literalne JSON \uXXXX sekvence
# (npr. 'Južna Srbija'). Pretvaramo ih u prave znakove, a pravi
# UTF-8 tekst (komentari i sl.) ostaje netaknut. Guard '\\u' in s znači
# da regex radi samo nad retkim pogođenim vrednostima.
_U_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def normalize(v):
    if type(v) is str and "\\u" in v:
        return _U_ESC.sub(lambda m: chr(int(m.group(1), 16)), v)
    return v


# SQLite je dinamički tipiziran: INTEGER/REAL kolona može da sadrži i tekst
# (npr. literalni "NULL"). Za numeričke PG kolone takve ne-brojeve svodimo na
# pravi NULL i brojimo koliko puta, da ništa ne nestane neprimetno.
def coerce(v, pgtype, counter, key):
    if v is None:
        return ""
    if pgtype == "BIGINT":
        if type(v) is int:
            return v
        try:
            return int(v)
        except (ValueError, TypeError):
            counter[key] = counter.get(key, 0) + 1
            return ""
    if pgtype == "DOUBLE PRECISION":
        if type(v) in (int, float):
            return v
        try:
            return float(v)
        except (ValueError, TypeError):
            counter[key] = counter.get(key, 0) + 1
            return ""
    return normalize(v)

POSTGRES_DSN = os.environ.get(
    "PROGRESS_PG_DSN",
    "host=localhost dbname=bot_detector_db user=bot_user password=bot_password",
)

# Mapiranje SQLite deklarisanih tipova na PostgreSQL tipove.
# Sve je permisivno: ako ne prepoznamo tip, ide TEXT.
def pg_type(sqlite_decl: str) -> str:
    t = (sqlite_decl or "").upper()
    if "INT" in t:
        return "BIGINT"
    if any(k in t for k in ("REAL", "FLOA", "DOUB")):
        return "DOUBLE PRECISION"
    # TEXT, CHAR, CLOB, NUMERIC, prazno -> TEXT (čuva sadržaj bez gubitka)
    return "TEXT"


# Kolone koje vredi indeksirati (po imenu). Pravimo indekse samo tamo gde
# imaju smisla za analizu/spajanje, da izgradnja ne bi trajala beskonačno.
INDEX_HINTS = (
    "_id", "_korisnik", "nalog", "twitter_id", "_datum", "_vreme",
    "korisnik_id", "vest_id", "portal", "_autor", "racunar",
)


def should_index(col: str) -> bool:
    c = col.lower()
    # izbegavamo indekse na slobodnom tekstu / velikim poljima
    if c in ("tu_embed_code", "tu_smernica"):
        return False
    return any(h in c for h in INDEX_HINTS)


def get_tables(scur, only):
    rows = scur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    names = [r[0] for r in rows]
    if only:
        wanted = {x.strip() for x in only.split(",") if x.strip()}
        names = [n for n in names if n in wanted]
        missing = wanted - set(names)
        if missing:
            print(f"[UPOZORENJE] Nepostojeće tabele ignorisane: {sorted(missing)}")
    return names


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--sqlite", default=os.path.join(here, "..", "data",
                                                     "progress_baza_podataka.sqlite3"))
    ap.add_argument("--schema", default="progress")
    ap.add_argument("--only", default=None)
    ap.add_argument("--batch", type=int, default=50000)
    ap.add_argument("--force", action="store_true",
                    help="ponovo uvezi i tabele koje već postoje")
    args = ap.parse_args()

    sqlite_path = os.path.abspath(args.sqlite)
    if not os.path.exists(sqlite_path):
        sys.exit(f"[GREŠKA] SQLite fajl ne postoji: {sqlite_path}")

    print(f"Izvor (read-only): {sqlite_path}")
    scon = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    scon.text_factory = lambda b: b.decode("utf-8", "replace")
    scur = scon.cursor()

    pcon = psycopg2.connect(POSTGRES_DSN)
    pcon.autocommit = False
    pcur = pcon.cursor()
    pcur.execute(f'CREATE SCHEMA IF NOT EXISTS "{args.schema}";')
    pcon.commit()

    tables = get_tables(scur, args.only)
    print(f"Tabela za uvoz: {len(tables)}\n")

    index_jobs = []  # (table, column)
    coerced = {}     # (table, column) -> broj ne-brojeva svedenih na NULL
    t_start = time.time()

    for ti, tbl in enumerate(tables, 1):
        cols_info = scur.execute(f'PRAGMA table_info("{tbl}")').fetchall()
        cols = [c[1] for c in cols_info]
        pgtypes = [pg_type(c[2]) for c in cols_info]
        coldefs = ", ".join(f'"{c}" {t}' for c, t in zip(cols, pgtypes))
        total = scur.execute(f'SELECT COUNT(*) FROM "{tbl}"').fetchone()[0]

        fq = f'"{args.schema}"."{tbl}"'

        # Resume: preskoči tabelu koja već postoji sa tačnim brojem redova.
        if not args.force:
            pcur.execute(
                "SELECT to_regclass(%s)", (f"{args.schema}.{tbl}",)
            )
            if pcur.fetchone()[0] is not None:
                pcur.execute(f"SELECT count(*) FROM {fq}")
                if pcur.fetchone()[0] == total:
                    print(f"[{ti}/{len(tables)}] {tbl}: već uvezeno "
                          f"({total:,}) — preskačem.", flush=True)
                    for c in cols:
                        if should_index(c):
                            index_jobs.append((tbl, c))
                    continue

        pcur.execute(f"DROP TABLE IF EXISTS {fq} CASCADE;")
        pcur.execute(f"CREATE TABLE {fq} ({coldefs});")
        pcon.commit()

        collist = ", ".join(f'"{c}"' for c in cols)
        copy_sql = f"COPY {fq} ({collist}) FROM STDIN WITH (FORMAT csv)"

        print(f"[{ti}/{len(tables)}] {tbl}: {total:,} redova ...", flush=True)

        scur.execute(f'SELECT {collist} FROM "{tbl}"')
        done = 0
        while True:
            rows = scur.fetchmany(args.batch)
            if not rows:
                break
            buf = io.StringIO()
            w = csv.writer(buf)
            for row in rows:
                w.writerow([coerce(v, pgtypes[i], coerced, (tbl, cols[i]))
                            for i, v in enumerate(row)])
            buf.seek(0)
            pcur.copy_expert(copy_sql, buf)
            done += len(rows)
            if total > 200000:
                print(f"      {done:,}/{total:,}", flush=True)
        pcon.commit()

        for c in cols:
            if should_index(c):
                index_jobs.append((tbl, c))

    # Indeksi na kraju (brže nego inkrementalno tokom uvoza)
    print(f"\nPravljenje {len(index_jobs)} indeksa ...", flush=True)
    for tbl, col in index_jobs:
        idx = f"ix_{tbl}_{col}"[:63]
        try:
            pcur.execute(
                f'CREATE INDEX IF NOT EXISTS "{idx}" '
                f'ON "{args.schema}"."{tbl}" ("{col}");'
            )
            pcon.commit()
        except Exception as e:  # noqa: BLE001
            pcon.rollback()
            print(f"   [preskočen indeks {idx}: {e}]")

    pcur.execute(f'SET search_path TO "{args.schema}", public;')
    pcon.commit()

    if coerced:
        print("\nNebrojčane vrednosti u numeričkim kolonama svedene na NULL:")
        for (tbl, col), n in sorted(coerced.items(), key=lambda x: -x[1]):
            print(f"   {tbl}.{col}: {n:,}")

    dt = time.time() - t_start
    print(f"\n[OK] Uvoz završen za {dt/60:.1f} min. Šema: {args.schema}")
    print(f"     Postgres: {POSTGRES_DSN}")
    pcur.close(); pcon.close(); scon.close()


if __name__ == "__main__":
    main()
