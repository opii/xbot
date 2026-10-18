#!/usr/bin/env python3
"""
KORAK 4: Specijalne taktičke grupe i komandni timovi (korisnici_grupe).

Tabele: korisnici_grupe (30 grupa: kg_naziv, kg_opis, kg_kreirao_korisnik_id),
korisnici_grupe_aktivisti (1.232 članstva: kga_grupa_id → kg_id, kga_aktivista_id
→ korisnici), korisnici.

Otkriva PARALELNU hijerarhiju: TikTok divizija (abecedna podela A–I/J–M/N–Z),
Voter administracija, Hit Tvit tim, Kontrolori/Sekretari/Protokol.

Izlaz: data/geo/tactical_groups.json → /api/tactical_groups.
Doc: docs/takticke_grupe_i_divizije.md
"""
import json
import os
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "tactical_groups.json")


def categorize(naziv):
    n = (naziv or "").lower()
    if "tik tok" in n or "tiktok" in n:
        return "TikTok divizija"
    if "voter" in n or "glasanje" in n or "glas" in n:
        return "Voter administracija"
    if "koordinator" in n or "koo " in n or "regionalni" in n:
        return "Koordinacija"
    if "kontrolor" in n or "monitoring" in n or "nadzor" in n or "sekretar" in n or "protokol" in n:
        return "Nadzor i kontrola"
    if "instagram" in n:
        return "Instagram"
    if "hit tvit" in n or "javljanje" in n:
        return "Hit Tvit (rapid)"
    if "analiza" in n:
        return "Analiza komentara"
    if "vesti" in n or "deljenje" in n:
        return "Vesti/Deljenje"
    if "specijal" in n or "sastanak" in n:
        return "Specijal / sastanak"
    return "Ostalo"


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    rows = q("""
        SELECT g.kg_id, g.kg_naziv, g.kg_opis, count(a.kga_id) n,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') kreirao
        FROM korisnici_grupe g
        LEFT JOIN korisnici_grupe_aktivisti a ON a.kga_grupa_id = g.kg_id
        LEFT JOIN korisnici k ON k.k_id = g.kg_kreirao_korisnik_id
        GROUP BY g.kg_id, g.kg_naziv, g.kg_opis, k.k_ime, k.k_prezime
        ORDER BY n DESC""")
    groups = [{"id": r[0], "naziv": r[1], "opis": r[2], "members": r[3],
               "kreirao": r[4], "category": categorize(r[1])} for r in rows]

    # agregat po kategoriji
    by_cat = {}
    for g in groups:
        d = by_cat.setdefault(g["category"], {"category": g["category"], "groups": 0, "members": 0})
        d["groups"] += 1; d["members"] += g["members"]
    categories = sorted(by_cat.values(), key=lambda d: d["members"], reverse=True)

    # članovi malih komandnih grupa (Voter admini, Hit tvit, Kontrolori) — imena
    def members(gid, limit=20):
        return [{"id": r[0], "ime": r[1] or f"#{r[0]}", "opstina": r[2]} for r in q("""
            SELECT a.kga_aktivista_id,
                   NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),''),
                   op.op_naziv
            FROM korisnici_grupe_aktivisti a
            LEFT JOIN korisnici k ON k.k_id = a.kga_aktivista_id
            LEFT JOIN opstina op ON op.op_id = k.k_opstina
            WHERE a.kga_grupa_id=%s ORDER BY 2 LIMIT %s""", (gid, limit))]

    key_groups = {}
    for g in groups:
        if g["category"] in ("Voter administracija", "Nadzor i kontrola", "Hit Tvit (rapid)") and g["members"] <= 40:
            key_groups[g["id"]] = {"naziv": g["naziv"], "members": members(g["id"])}

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "groups_total": len(groups),
        "memberships_total": sum(g["members"] for g in groups),
        "categories": categories,
        "groups": groups,
        "key_group_members": key_groups,
        "note": ("Paralelna hijerarhija po funkciji/platformi: TikTok divizija "
                 "(abecedna podela), Voter administracija, Hit Tvit (rapid koordinacija), "
                 "Nadzor/Kontrola. Članstvo = korisnici_grupe_aktivisti (eksplicitno)."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Grupa: {len(groups)} · članstava: {out['memberships_total']}")
    for c in categories:
        print(f"  {c['category']:<22} {c['groups']} grupa · {c['members']} članstava")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
