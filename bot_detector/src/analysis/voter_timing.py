#!/usr/bin/env python3
"""
Faza C: vremenska sinhronija voter udara (sekundni nivo).

Koristi arhiva_komentari_na_vestima: `knv_vreme_kreiranja` (kad je komentar
objavljen na portalu) i `knv_voter_vreme` (kad ga je voter sistem automatski
izglasao), uz `knv_voter_korisnik_id`. 4,5M glasova sa sekundnim vremenom.

Meri:
  1) latenciju komentar→voter udar (koliko brzo voter pogodi novi komentar),
  2) dnevni ritam glasanja (24/7 = automatizacija) vs ritam komentarisanja,
  3) udeo noćnih glasova (00–05h).

Pokretanje:  ./venv/bin/python src/analysis/voter_timing.py
"""
import json
import os

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "voter_timing.json")


def main():
    cur = psycopg2.connect(PG).cursor()
    cur.execute("SET search_path TO progress")

    print("Latencija komentar→voter udar ...", flush=True)
    cur.execute("""
        SELECT
          percentile_cont(0.5) WITHIN GROUP (ORDER BY d) AS med,
          count(*) n,
          count(*) FILTER (WHERE d < 10)            AS b1,
          count(*) FILTER (WHERE d >= 10 AND d < 60)    AS b2,
          count(*) FILTER (WHERE d >= 60 AND d < 300)   AS b3,
          count(*) FILTER (WHERE d >= 300 AND d < 1800) AS b4,
          count(*) FILTER (WHERE d >= 1800)         AS b5
        FROM (
          SELECT extract(epoch FROM (knv_voter_vreme::timestamp
                                     - knv_vreme_kreiranja::timestamp)) AS d
          FROM arhiva_komentari_na_vestima
          WHERE knv_voter_aktiviran = 1 AND knv_voter_vreme <> ''
            AND knv_voter_vreme > knv_vreme_kreiranja
        ) z
    """)
    r = cur.fetchone()
    lat = {"median_s": round(r[0], 1) if r[0] is not None else None, "n": r[1],
           "buckets": {"<10s": r[2], "10-60s": r[3], "1-5min": r[4],
                       "5-30min": r[5], ">30min": r[6]}}
    print(f"  medijana: {lat['median_s']}s · <10s: {r[2]:,} · <60s: {r[2]+r[3]:,}", flush=True)

    print("Dnevni ritam glasanja vs komentarisanja ...", flush=True)
    vhours = [0] * 24
    for hh, c in cur.execute("""
        SELECT substr(knv_voter_vreme, 12, 2) hh, count(*)
        FROM arhiva_komentari_na_vestima
        WHERE knv_voter_aktiviran = 1 AND knv_voter_vreme <> ''
        GROUP BY 1
    """) or cur.fetchall():
        if hh and hh.isdigit():
            vhours[int(hh)] = c
    chours = [0] * 24
    for hh, c in cur.execute("""
        SELECT substr(knv_vreme_kreiranja, 12, 2) hh, count(*)
        FROM arhiva_komentari_na_vestima WHERE knv_vreme_kreiranja <> ''
        GROUP BY 1
    """) or cur.fetchall():
        if hh and hh.isdigit():
            chours[int(hh)] = c
    vt, ct = sum(vhours) or 1, sum(chours) or 1
    vnight = sum(vhours[0:6]) / vt
    cnight = sum(chours[0:6]) / ct
    print(f"  noćni udeo: glasanje {100*vnight:.1f}% vs komentari {100*cnight:.1f}%", flush=True)

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"latency": lat, "vote_hours": vhours, "comment_hours": chours,
                   "vote_night_ratio": round(vnight, 4),
                   "comment_night_ratio": round(cnight, 4)}, fh, ensure_ascii=False, indent=2)
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()
