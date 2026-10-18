#!/usr/bin/env python3
"""
KORAK 2: Kurir/relay nalozi ↔ afričke mašine (voter_kurir_nalozi → voter_racunari).

Tabela voter_kurir_nalozi (1.514 naloga): racunar_id (FK → voter_racunari.vr_id,
DOKAZANA veza), email (temp-mail domeni), aktivan, problem, vreme_uzimanja,
password (NIKAD se ne izlaže — samo status/dužina/heš).

FER PLAY:
- racunar_id → vr_id je eksplicitan FK (dokaz da je nalog dodeljen baš toj mašini).
- „kurir" = kurir/relay nalog; NE tvrdimo da su to nalozi na portalu Kurir.rs
  (nema kolone koja to veže — to bi bila hipoteza).
- password se NE čita ni ne izlaže (samo da postoji / dužina).

Izlaz: data/geo/voter_kurir_accounts.json
"""
import json
import os
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "voter_kurir_accounts.json")


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    total = q("SELECT count(*) FROM voter_kurir_nalozi")[0][0]
    active = q("SELECT count(*) FROM voter_kurir_nalozi WHERE aktivan=1")[0][0]
    with_pw = q("SELECT count(*) FROM voter_kurir_nalozi WHERE password IS NOT NULL AND password<>''")[0][0]

    # temp-mail domeni (bez lokalnog dela adrese)
    domains = [{"domain": d or "?", "accounts": n} for d, n in q(
        r"SELECT substring(email from '@(.*)$'), count(*) FROM voter_kurir_nalozi "
        r"GROUP BY 1 ORDER BY 2 DESC LIMIT 20")]

    # raspodela po mašini → država/lokacija (FK join)
    machines = q("""
        SELECT n.racunar_id,
               CASE WHEN r.vr_srbija=1 THEN 'Srbija' ELSE 'strano' END drz,
               r.vr_naziv_ss, count(*) nalog
        FROM voter_kurir_nalozi n
        LEFT JOIN voter_racunari r ON r.vr_id = n.racunar_id
        GROUP BY n.racunar_id, r.vr_srbija, r.vr_naziv_ss
        ORDER BY nalog DESC""")
    distinct_machines = len({m[0] for m in machines})
    matched = [m for m in machines if m[1] is not None]
    srb = len({m[0] for m in matched if m[1] == "Srbija"})
    strano = len({m[0] for m in matched if m[1] == "strano"})
    top_machines = [{"racunar_id": m[0], "drzava": m[1], "lokacija": m[2], "naloga": m[3]}
                    for m in matched[:20]]

    # vremenski raspon uzimanja naloga
    span = q("SELECT min(vreme_uzimanja), max(vreme_uzimanja) FROM voter_kurir_nalozi "
             "WHERE vreme_uzimanja IS NOT NULL AND vreme_uzimanja<>''")[0]

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "accounts_total": total, "accounts_active": active,
        "accounts_with_password": with_pw,  # SAMO broj, ne i lozinke
        "distinct_machines_referenced": distinct_machines,
        "machines_matched": srb + strano, "machines_serbia": srb, "machines_foreign": strano,
        "temp_mail_domains": domains,
        "top_machines": top_machines,
        "vreme_uzimanja_od": span[0], "vreme_uzimanja_do": span[1],
        "mechanism": ("Mašine (uglavnom afričke lokacije) imaju DODELJENE registrovane "
                      "naloge (email+lozinka) — infrastruktura za autorizaciju/upis, ne "
                      "samo anonimno glasanje. Portal nije eksplicitno vezan u tabeli."),
        "fair_play": ("racunar_id→vr_id je dokazan FK. „kurir“ = relay nalog; NE tvrdi se "
                      "da su nalozi na Kurir.rs (nema veze u bazi). password se ne izlaže."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Naloga: {total} (aktivnih {active}, sa lozinkom {with_pw})")
    print(f"Mašina referisano: {distinct_machines} · uparено {srb+strano} "
          f"(Srbija {srb} / strano {strano})")
    print(f"Top temp-mail domeni: {[d['domain'] for d in domains[:5]]}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
