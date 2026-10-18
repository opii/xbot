#!/usr/bin/env python3
"""
Dublja analiza koordinatora — hijerarhija komande i raspon kontrole.

Komandna struktura je GEOGRAFSKA: Region (7) → Okrug (26) → Opština (162).
Koordinatorske pozicije (namenske tabele, autoritativne):
  - region_koordinator   (rk_region_id, rk_korisnik_id)    — 5
  - okrug_koordinator    (ok_okrug_id,  ok_korisnik_id)     — 15
  - opstina_koordinator  (ok_opstina_id, ok_korisnik_id)    — 136
  + zamenici (region/okrug/opstina_zamenici).

Za svaki čvor hijerarhije računamo RASPON KONTROLE:
  - operators : broj registrovanih operatera (korisnici) u toj geografiji
  - centroids : koliko ih je jakih u grafu (tw_organizer/cc_organizer) — izvršna moć
  - command   : koliko ih zadaje zadatke (tu/vu kreatori) — komandni sloj
  - ss_issuers: koliko izdaje centralne direktive (SS/ČET)
  - shops     : uplatna mesta kladionica (🎰) u opštini (voter infrastruktura)

Ključno pitanje: da li se KOMANDA (koordinatorske pozicije) i IZVRŠENJE (grafni
centroidi) poklapaju ili su razdvojeni? (Prethodno: izdavači SS-a često org≈0.)

Izlaz: data/geo/coordinators.json → /api/coordinators → UI „🏛 Koordinatori".
Pokretanje:  ./venv/bin/python src/analysis/coordinators.py
"""
import json
import os
import re
import unicodedata
from datetime import datetime

import psycopg2
from neo4j import GraphDatabase

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
NEO = ("bolt://localhost:7687", ("neo4j", "bot_password"))
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "coordinators.json")
BETTING = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "betting_geo.json")


def name_of(row):
    return (row or {}).get("ime")


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    # --- geografski skelet -----------------------------------------------------
    regions = {r[0]: {"id": r[0], "naziv": r[1], "okruzi": {}} for r in q("SELECT r_id,r_naziv FROM region")}
    okr2reg, op2okr = {}, {}
    for oid, rid, naz in q("SELECT o_id,o_region_id,o_naziv FROM okrug"):
        okr2reg[oid] = rid
        if rid in regions:
            regions[rid]["okruzi"][oid] = {"id": oid, "naziv": naz, "opstine": {}}
    op_name = {}
    for opid, oid, naz in q("SELECT op_id,op_okrug_id,op_naziv FROM opstina"):
        op2okr[opid] = oid
        op_name[opid] = naz
        rid = okr2reg.get(oid)
        if rid in regions and oid in regions[rid]["okruzi"]:
            regions[rid]["okruzi"][oid]["opstine"][opid] = {
                "id": opid, "naziv": naz, "operators": 0, "centroids": 0,
                "command": 0, "ss_issuers": 0, "shops": 0, "coord": [], "deputy": 0}

    # --- imena korisnika (za koordinatore) ------------------------------------
    def names(ids):
        if not ids:
            return {}
        rows = q("""SELECT k_id, NULLIF(trim(coalesce(k_ime,'')||' '||coalesce(k_prezime,'')),''),
                           k_pozicija FROM korisnici WHERE k_id IN %s""", (tuple(ids),))
        return {r[0]: {"ime": r[1], "pozicija": r[2]} for r in rows}

    # --- koordinatorske pozicije (autoritativne) ------------------------------
    reg_coord = {rid: kid for _, rid, kid in q("SELECT rk_id,rk_region_id,rk_korisnik_id FROM region_koordinator")}
    okr_coord = {oid: kid for _, oid, kid in q("SELECT ok_id,ok_okrug_id,ok_korisnik_id FROM okrug_koordinator")}
    op_coord = {}
    for _, opid, kid in q("SELECT ok_id,ok_opstina_id,ok_korisnik_id FROM opstina_koordinator"):
        op_coord[opid] = kid
    # zamenici (brojimo po čvoru)
    reg_dep = {}; okr_dep = {}; op_dep = {}
    for _, rid, kid in q("SELECT rz_id,rz_region_id,rz_korisnik_id FROM region_zamenici"):
        reg_dep.setdefault(rid, []).append(kid)
    for _, oid, kid in q("SELECT oz_id,oz_okrug_id,oz_korisnik_id FROM okrug_zamenici"):
        okr_dep.setdefault(oid, []).append(kid)
    for _, opid, kid in q("SELECT oz_id,oz_opstina_id,oz_korisnik_id FROM opstina_zamenici"):
        op_dep.setdefault(opid, []).append(kid)

    all_coord_ids = set(reg_coord.values()) | set(okr_coord.values()) | set(op_coord.values())
    nm = names(all_coord_ids)

    # --- operateri po opštini --------------------------------------------------
    for opid, cnt in q("SELECT k_opstina, count(*) FROM korisnici GROUP BY 1"):
        oid = op2okr.get(opid); rid = okr2reg.get(oid)
        if rid in regions and oid in regions[rid]["okruzi"] and opid in regions[rid]["okruzi"][oid]["opstine"]:
            regions[rid]["okruzi"][oid]["opstine"][opid]["operators"] = cnt

    # --- komandni sloj: ko zadaje zadatke (tu+vu kreatori) po opštini ----------
    cur.execute("""
        SELECT k.k_opstina, count(DISTINCT c.id) FROM (
            SELECT DISTINCT tu_kreirano_korisnik_id id FROM arhiva_twitter_unos WHERE tu_kreirano_korisnik_id IS NOT NULL
            UNION SELECT DISTINCT vu_korisnik_id FROM arhiva_vesti_unos WHERE vu_korisnik_id IS NOT NULL
        ) c JOIN korisnici k ON k.k_id=c.id GROUP BY 1
    """)
    cmd_by_op = dict(cur.fetchall())

    # --- SS/ČET izdavači po opštini -------------------------------------------
    cur.execute("""
        SELECT k.k_opstina, count(DISTINCT c.id) FROM (
            SELECT DISTINCT tu_kreirano_korisnik_id id FROM arhiva_twitter_unos
              WHERE tu_smernica ~* 'super ?spec|iz ss|\\mss\\M|iz cet|video iz cet|\\mceta\\M'
            UNION SELECT DISTINCT vu_korisnik_id FROM arhiva_vesti_unos
              WHERE vu_smernica ~* 'super ?spec|iz ss|\\mss\\M|iz cet|video iz cet|\\mceta\\M'
        ) c JOIN korisnici k ON k.k_id=c.id WHERE k.k_opstina IS NOT NULL GROUP BY 1
    """)
    ss_by_op = dict(cur.fetchall())

    # --- centroidi + org po operateru iz grafa --------------------------------
    drv = GraphDatabase.driver(NEO[0], auth=NEO[1])
    op_centroid_by_op = {}   # opstina_name -> broj centroida
    op_info = {}             # korisnik_id -> {centroid, max_org, opstina}
    with drv.session() as s:
        rows = s.run("MATCH (o:Operator) RETURN o.id AS id, o.opstina AS opstina, "
                     "o.tw_organizer AS two, o.cc_organizer AS cco, "
                     "o.tw_org AS tw, o.cc_org AS cc")
        for r in rows:
            cent = bool(r["two"] or r["cco"])
            mo = max((r["tw"] or 0), (r["cc"] or 0))
            op_info[r["id"]] = {"centroid": cent, "max_org": mo, "opstina": r["opstina"]}
            if cent and r["opstina"]:
                op_centroid_by_op[r["opstina"]] = op_centroid_by_op.get(r["opstina"], 0) + 1
    drv.close()

    # --- betting 🎰 po opštini -------------------------------------------------
    shops_by_name = {}
    try:
        with open(BETTING, encoding="utf-8") as f:
            shops_by_name = json.load(f).get("by_opstina", {})
    except Exception:  # noqa: BLE001
        pass

    def shops_for(naz):
        return shops_by_name.get(naz) or shops_by_name.get(f"Beograd-{naz}") or 0

    # --- popuni listove (opštine) ---------------------------------------------
    for rid, R in regions.items():
        for oid, O in R["okruzi"].items():
            for opid, P in O["opstine"].items():
                naz = P["naziv"]
                P["command"] = cmd_by_op.get(opid, 0)
                P["ss_issuers"] = ss_by_op.get(opid, 0)
                P["centroids"] = op_centroid_by_op.get(naz, 0)
                P["shops"] = shops_for(naz)
                kid = op_coord.get(opid)
                if kid:
                    P["coord"] = [{"id": kid, "ime": name_of(nm.get(kid)) or f"#{kid}",
                                   "centroid": op_info.get(kid, {}).get("centroid", False),
                                   "max_org": round(op_info.get(kid, {}).get("max_org", 0), 3)}]
                P["deputy"] = len(op_dep.get(opid, []))

    # --- agregacija naviše (okrug, region) ------------------------------------
    def agg(children, keys):
        out = {k: 0 for k in keys}
        for ch in children:
            for k in keys:
                out[k] += ch.get(k, 0)
        return out

    SUM = ["operators", "centroids", "command", "ss_issuers", "shops"]
    tree = []
    for rid, R in sorted(regions.items(), key=lambda kv: kv[0]):
        okruzi = []
        for oid, O in sorted(R["okruzi"].items()):
            opstine = sorted(O["opstine"].values(), key=lambda p: p["operators"], reverse=True)
            a = agg(opstine, SUM)
            kid = okr_coord.get(oid)
            okruzi.append({"id": oid, "naziv": O["naziv"], **a,
                           "coord": ([{"id": kid, "ime": name_of(nm.get(kid)) or f"#{kid}",
                                       "centroid": op_info.get(kid, {}).get("centroid", False),
                                       "max_org": round(op_info.get(kid, {}).get("max_org", 0), 3)}]
                                     if kid else []),
                           "deputy": len(okr_dep.get(oid, [])),
                           "opstine": opstine})
        a = agg(okruzi, SUM)
        kid = reg_coord.get(rid)
        tree.append({"id": rid, "naziv": R["naziv"], **a,
                     "coord": ([{"id": kid, "ime": name_of(nm.get(kid)) or f"#{kid}",
                                 "centroid": op_info.get(kid, {}).get("centroid", False),
                                 "max_org": round(op_info.get(kid, {}).get("max_org", 0), 3)}]
                               if kid else []),
                     "deputy": len(reg_dep.get(rid, [])),
                     "okruzi": okruzi})
    tree.sort(key=lambda r: r["operators"], reverse=True)

    # --- komanda vs izvršenje (ključni nalaz) ---------------------------------
    # od svih koordinatora: koliko ih je samih grafnih centroida / jakih
    ss_issuer_ids = set()
    cur.execute("""
        SELECT DISTINCT c.id FROM (
            SELECT DISTINCT tu_kreirano_korisnik_id id FROM arhiva_twitter_unos
              WHERE tu_smernica ~* 'super ?spec|iz ss|\\mss\\M|iz cet|video iz cet|\\mceta\\M'
            UNION SELECT DISTINCT vu_korisnik_id FROM arhiva_vesti_unos
              WHERE vu_smernica ~* 'super ?spec|iz ss|\\mss\\M|iz cet|video iz cet|\\mceta\\M'
        ) c WHERE c.id IS NOT NULL
    """)
    ss_issuer_ids = {r[0] for r in cur.fetchall()}

    coord_rows = []
    for level, mapping in (("region", reg_coord), ("okrug", okr_coord), ("opstina", op_coord)):
        for area_id, kid in mapping.items():
            info = op_info.get(kid, {})
            coord_rows.append({
                "id": kid, "ime": name_of(nm.get(kid)) or f"#{kid}", "level": level,
                "centroid": info.get("centroid", False),
                "max_org": round(info.get("max_org", 0), 3),
                "in_graph": kid in op_info,
                "ss_issuer": kid in ss_issuer_ids,
            })
    n_coord = len(coord_rows)
    n_centroid = sum(1 for c in coord_rows if c["centroid"])
    n_ingraph = sum(1 for c in coord_rows if c["in_graph"])
    n_ss = sum(1 for c in coord_rows if c["ss_issuer"])

    cmd_vs_exec = {
        "coordinators_total": n_coord, "in_graph": n_ingraph,
        "are_centroids": n_centroid, "are_ss_issuers": n_ss,
        "note": ("Koordinatorska pozicija = formalna komanda. Grafni centroid = "
                 "izvršna moć (jak u mreži akcija). Preklapanje je mali deo — komanda "
                 "i izvršenje su uglavnom RAZDVOJENI slojevi."),
    }

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "levels": {"region": len(reg_coord), "okrug": len(okr_coord),
                   "opstina": len(op_coord),
                   "deputies": sum(len(v) for v in reg_dep.values())
                   + sum(len(v) for v in okr_dep.values())
                   + sum(len(v) for v in op_dep.values())},
        "command_vs_execution": cmd_vs_exec,
        "tree": tree,
        "disclaimer": ("Koordinatorske pozicije su iz namenskih tabela (autoritativne). "
                       "Raspon kontrole = geografska nadležnost (operateri registrovani "
                       "u toj opštini/okrugu/regionu), ne dokaz pojedinačnog naređenja."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Koordinatori: region {len(reg_coord)} · okrug {len(okr_coord)} · "
          f"opština {len(op_coord)} · zamenika {out['levels']['deputies']}")
    print(f"Komanda vs izvršenje: od {n_coord} koordinatora, u grafu {n_ingraph}, "
          f"centroida {n_centroid}, SS-izdavača {n_ss}")
    print("\nTOP regioni (operateri · centroidi · komanda · SS · 🎰):")
    for r in tree:
        cname = r["coord"][0]["ime"] if r["coord"] else "—"
        print(f"  {r['naziv']:<18} {r['operators']:>5} op · {r['centroids']:>3} cent · "
              f"{r['command']:>3} cmd · {r['ss_issuers']:>2} SS · 🎰{r['shops']:>3}  koord: {cname}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
