#!/usr/bin/env python3
"""
Vremenska kaskada: centralna direktiva (SS/ČET) → teren (okruzi/operateri).

Rekonstruiše kako se zadatak širi kroz vreme: od kreiranja (izdavač) do izvršenja
(operateri), sa geografskim lead-lag obrascem. Pošteno: redosled i latencija su
KORELACIJA (ko obično reaguje ubrzo posle kreiranja), INFERIRANA propagacija — NE
dokaz da je neko lično prosledio poruku konkretnom operateru.

Meri:
  1) ss_priority   : medijana prve reakcije — SS zadaci vs baseline (ne-SS).
  2) first_mover   : po okrugu, koliko puta je PRVI reagent + učešće → stopa
                     „vrha koplja" (ko konzistentno otvara kampanju). Svi + SS.
  3) hour_of_day   : ritam — SS kreiranje vs SS izvršenje po satu (0–23).
  4) timeline      : mesečno — SS kreiranje vs SS izvršenje.
  5) issuer_okrug  : za top SS izdavače, koji okruzi izvršavaju (bipartitne veze).

Izlaz: data/geo/cascade.json → /api/cascade → UI „⏱ Kaskada (SS → teren)".
Pokretanje:  ./venv/bin/python src/analysis/cascade.py
"""
import json
import os
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "cascade.json")

SS = r'super ?spec|iz ss|\mss\M|iz cet|video iz cet|\mceta\M'
TS = r"~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}$'"


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    # 1) SS PRIORITET — medijana prve reakcije SS vs baseline -------------------
    print("[1/5] SS prioritet (latencija prve reakcije) ...", flush=True)
    priority = {}
    for key, where in (("ss", "t.tu_smernica ~* %s"), ("baseline", "t.tu_smernica !~* %s")):
        r = q(f"""
            WITH f AS (
              SELECT t.tu_id, min(EXTRACT(EPOCH FROM (a.tuka_vreme::timestamp
                     - t.tu_kreirano_vreme::timestamp))) lat
              FROM arhiva_twitter_unos t
              JOIN arhiva_twitter_unos_korisnici_akcije a ON a.tuka_twitter_id = t.tu_id
              WHERE {where} AND a.tuka_vreme {TS} AND t.tu_kreirano_vreme {TS}
              GROUP BY t.tu_id)
            SELECT count(*), percentile_cont(0.5) WITHIN GROUP (ORDER BY lat),
                   percentile_cont(0.25) WITHIN GROUP (ORDER BY lat)
            FROM f WHERE lat >= 0 AND lat <= 259200
        """, (SS,))
        priority[key] = {"tasks": r[0][0], "median_s": round(float(r[0][1] or 0), 1),
                         "p25_s": round(float(r[0][2] or 0), 1)}
    print(f"  SS medijana={priority['ss']['median_s']}s vs baseline={priority['baseline']['median_s']}s")

    # 2) FIRST-MOVER po okrugu --------------------------------------------------
    print("[2/5] Vrh koplja (prvi reagent po okrugu) ...", flush=True)

    def first_mover(ss_only):
        cond = "AND t.tu_smernica ~* %s" if ss_only else ""
        args = (SS,) if ss_only else None
        # prvi reagent po zadatku -> okrug
        cur.execute(f"""
            WITH first_act AS (
              SELECT DISTINCT ON (a.tuka_twitter_id) a.tuka_twitter_id tid, a.tuka_korisnik_id uid
              FROM arhiva_twitter_unos_korisnici_akcije a
              JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
              WHERE a.tuka_vreme {TS} {cond}
              ORDER BY a.tuka_twitter_id, a.tuka_vreme::timestamp
            )
            SELECT o.o_naziv, count(*) FROM first_act f
            JOIN korisnici k ON k.k_id = f.uid JOIN okrug o ON o.o_id = k.k_okrug
            GROUP BY o.o_naziv
        """, args)
        firsts = dict(cur.fetchall())
        # učešće: koliko distinct zadataka okrug uopšte dira
        cur.execute(f"""
            SELECT o.o_naziv, count(DISTINCT a.tuka_twitter_id)
            FROM arhiva_twitter_unos_korisnici_akcije a
            JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
            JOIN korisnici k ON k.k_id = a.tuka_korisnik_id
            JOIN okrug o ON o.o_id = k.k_okrug
            WHERE a.tuka_vreme {TS} {cond}
            GROUP BY o.o_naziv
        """, args)
        part = dict(cur.fetchall())
        rows = []
        for okr, fm in firsts.items():
            p = part.get(okr, 0)
            rows.append({"okrug": okr, "first_moves": fm, "participated": p,
                         "first_rate": round(fm / p, 3) if p else 0})
        rows.sort(key=lambda r: r["first_moves"], reverse=True)
        return rows

    fm_all = first_mover(False)
    fm_ss = first_mover(True)
    print("  TOP vrh koplja (svi):",
          ", ".join(f"{r['okrug'].replace(' okrug','')}({r['first_moves']})" for r in fm_all[:5]))

    # 3) HOUR-OF-DAY — SS kreiranje vs izvršenje --------------------------------
    print("[3/5] Ritam po satu ...", flush=True)
    create_h = [0] * 24
    for h, n in q(f"""SELECT substr(tu_kreirano_vreme,12,2)::int, count(*)
                     FROM arhiva_twitter_unos
                     WHERE tu_smernica ~* %s AND tu_kreirano_vreme {TS} GROUP BY 1""", (SS,)):
        create_h[h] = n
    exec_h = [0] * 24
    for h, n in q(f"""SELECT substr(a.tuka_vreme,12,2)::int, count(*)
                     FROM arhiva_twitter_unos_korisnici_akcije a
                     JOIN arhiva_twitter_unos t ON t.tu_id = a.tuka_twitter_id
                     WHERE t.tu_smernica ~* %s AND a.tuka_vreme {TS} GROUP BY 1""", (SS,)):
        exec_h[h] = n

    # 4) TIMELINE mesečno -------------------------------------------------------
    print("[4/5] Mesečni timeline ...", flush=True)
    cre_m = {r[0]: r[1] for r in q(f"""SELECT substr(tu_kreirano_vreme,1,7), count(*)
             FROM arhiva_twitter_unos WHERE tu_smernica ~* %s AND tu_kreirano_vreme {TS}
             GROUP BY 1""", (SS,))}
    exe_m = {r[0]: r[1] for r in q(f"""SELECT substr(a.tuka_vreme,1,7), count(*)
             FROM arhiva_twitter_unos_korisnici_akcije a JOIN arhiva_twitter_unos t ON t.tu_id=a.tuka_twitter_id
             WHERE t.tu_smernica ~* %s AND a.tuka_vreme {TS} GROUP BY 1""", (SS,))}
    months = sorted(set(cre_m) | set(exe_m))
    timeline = [{"ym": m, "created": cre_m.get(m, 0), "executed": exe_m.get(m, 0)} for m in months]

    # 5) IZDAVAČ → OKRUG (SS) ---------------------------------------------------
    print("[5/5] Izdavač → okrug (SS) ...", flush=True)
    edges = q(f"""
        SELECT NULLIF(trim(coalesce(ki.k_ime,'')||' '||coalesce(ki.k_prezime,'')),'') izdavac,
               o.o_naziv okrug, count(*) n
        FROM arhiva_twitter_unos t
        JOIN arhiva_twitter_unos_korisnici_akcije a ON a.tuka_twitter_id = t.tu_id
        JOIN korisnici ki ON ki.k_id = t.tu_kreirano_korisnik_id
        JOIN korisnici kr ON kr.k_id = a.tuka_korisnik_id
        JOIN okrug o ON o.o_id = kr.k_okrug
        WHERE t.tu_smernica ~* %s AND a.tuka_vreme {TS}
        GROUP BY 1,2 HAVING count(*) >= 5 ORDER BY 3 DESC LIMIT 40
    """, (SS,))
    issuer_okrug = [{"izdavac": r[0] or "?", "okrug": r[1], "n": r[2]} for r in edges]

    speedup = round((priority["baseline"]["median_s"] - priority["ss"]["median_s"])
                    / priority["baseline"]["median_s"] * 100, 1) if priority["baseline"]["median_s"] else 0

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "ss_priority": {**priority, "speedup_pct": speedup},
        "first_mover_all": fm_all,
        "first_mover_ss": fm_ss,
        "hour_of_day": {"created": create_h, "executed": exec_h},
        "timeline": timeline,
        "issuer_okrug": issuer_okrug,
        "disclaimer": ("Redosled i latencija su KORELACIJA (ko obično reaguje ubrzo "
                       "posle kreiranja zadatka), inferirana propagacija — NE dokaz "
                       "da je pojedinac lično prosledio poruku konkretnom operateru."),
        "note": ("SS/ČET = zadaci sa oznakom centralnog izvora (super specijal / iz "
                 "četa). „Vrh koplja“ = okrug koji je najčešće PRVI reagent na zadatke."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"\nSS prioritet: {priority['ss']['median_s']}s vs {priority['baseline']['median_s']}s "
          f"baseline ({speedup}% brže)")
    print("Vrh koplja (SS), top 5:")
    for r in fm_ss[:5]:
        print(f"  {r['okrug']:<22} prvi={r['first_moves']:>4} / učešće={r['participated']:>4} "
              f"= {r['first_rate']}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
