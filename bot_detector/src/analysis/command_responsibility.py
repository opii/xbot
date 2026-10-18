#!/usr/bin/env python3
"""
Komandna odgovornost & Voter — SAMO ono što podaci dokazuju (fer play).

Spaja tri činjenice iz baze:
  1) ko ima EKSPLICITNE VOTER privilegije (korisnici_privilegije: IZVEŠTAJI_VOTER,
     VOTER_DODATAK, VOTER_KOMENTARI) — 61 različit korisnik (109 dodela),
  2) ko je koordinator (opstina/okrug/region) i u kojoj opštini,
  3) da li u toj opštini postoje terminali kladionica (voter infrastruktura),
  + koliko je glasova kreditirano na tog korisnika (knv_voter_korisnik_id),
  + da li je jak operater/centroid u grafu.

NE tvrdi da je konkretan čovek pokrenuo afričke mašine (to veze u bazi NEMA).
Daje najjaču atribuciju KOJU PODACI NOSE: dodeljena prava + uloga + ko-lokacija.

Pokretanje:  ./venv/bin/python src/analysis/command_responsibility.py
"""
import json
import os

import psycopg2
from neo4j import GraphDatabase

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO = ("bolt://localhost:7687", ("neo4j", "bot_password"))
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "command_voter.json")
BETTING = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "betting_geo.json")


def main():
    with open(BETTING, encoding="utf-8") as f:
        shops = json.load(f).get("by_opstina", {})

    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    # 1) nosioci VOTER privilegija (agregiraj privilegije po korisniku)
    cur.execute("""
        SELECT p.kp_korisnik_id,
               array_agg(DISTINCT p.kp_privilegija_id) AS privs,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') AS ime,
               k.k_pozicija, o.o_naziv AS okrug, op.op_naziv AS opstina,
               kk.okrug_koordinator, kk.opstina_koordinator, kk.region_koordinator
        FROM korisnici_privilegije p
        LEFT JOIN korisnici k ON k.k_id = p.kp_korisnik_id
        LEFT JOIN okrug  o  ON o.o_id  = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
        LEFT JOIN koordinatori_korisnici kk ON kk.korisnik_id = p.kp_korisnik_id
        WHERE p.kp_privilegija_id ILIKE '%voter%'
        GROUP BY p.kp_korisnik_id, k.k_ime, k.k_prezime, k.k_pozicija,
                 o.o_naziv, op.op_naziv, kk.okrug_koordinator,
                 kk.opstina_koordinator, kk.region_koordinator
    """)
    cols = ("id", "privs", "ime", "pozicija", "okrug", "opstina",
            "ok_koord", "op_koord", "reg_koord")
    people = [dict(zip(cols, r)) for r in cur.fetchall()]

    # glasovi kreditirani na korisnika
    cur.execute("""
        SELECT knv_voter_korisnik_id, count(*)
        FROM arhiva_komentari_na_vestima
        WHERE knv_voter_aktiviran = 1 AND knv_voter_korisnik_id IS NOT NULL
        GROUP BY 1
    """)
    votes = dict(cur.fetchall())

    # zadaci sa voter_prioritet flagom po kreatoru
    cur.execute("""
        SELECT vu_korisnik_id, count(*)
        FROM arhiva_vesti_unos WHERE vu_voter_prioritet = 1 GROUP BY 1
    """)
    vprio = dict(cur.fetchall())

    drv = GraphDatabase.driver(*NEO[:1], auth=NEO[1])
    with drv.session() as s:
        for m in people:
            m["votes_credited"] = votes.get(m["id"], 0)
            m["voter_priority_tasks"] = vprio.get(m["id"], 0)
            m["shops_in_opstina"] = shops.get(m["opstina"] or "", 0)
            r = s.run("MATCH (o:Operator {id:$id}) RETURN o.tw_org AS tw, o.cc_org AS cc, "
                      "o.tw_organizer AS two, o.cc_organizer AS cco", id=m["id"]).single()
            m["max_org"] = round(max((r["tw"] or 0), (r["cc"] or 0)), 3) if r else 0
            m["centroid"] = bool(r and (r["two"] or r["cco"]))
            m["coordinator"] = bool(m["ok_koord"] or m["op_koord"] or m["reg_koord"])
    drv.close()

    people.sort(key=lambda m: -(m["votes_credited"] + m["max_org"] * 1e6
                                + (1e9 if m["coordinator"] else 0)))
    coord = sum(1 for m in people if m["coordinator"])
    with_shops = sum(1 for m in people if m["shops_in_opstina"] > 0)
    print(f"nosilaca VOTER privilegija: {len(people)} (koordinatori: {coord}, "
          f"u opštini sa terminalima: {with_shops})", flush=True)
    print("\nKOMANDNA ODGOVORNOST (ime · privilegije · uloga · opština/🎰 · glasovi · org):")
    for m in people[:18]:
        pv = ",".join(p.replace("IZVEŠTAJI_VOTER", "IZV").replace("VOTER_", "")
                      for p in (m["privs"] or []))
        flags = []
        if m["coordinator"]:
            flags.append("KOORD")
        if m["centroid"]:
            flags.append("CENTROID")
        print(f"  {(m['ime'] or m['id']):<22} [{pv:<14}] {','.join(flags) or '—':<14} "
              f"{(m['opstina'] or '?'):<16} 🎰{m['shops_in_opstina']:<3} "
              f"glas={m['votes_credited']:<8} org={m['max_org']}")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"count": len(people), "coordinators": coord,
                   "with_terminals": with_shops, "people": people},
                  fh, ensure_ascii=False, indent=2, default=str)
    print(f"\n[OK] {OUT}")


if __name__ == "__main__":
    main()
