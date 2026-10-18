#!/usr/bin/env python3
"""
KORACI 5–7: Nadzor i telemetrija nad operaterima.

K5 otvoren_inspector (306): sistem beleži kad operater otvori DevTools/F12 konzolu
    (oi_korisnik_id, oi_vreme) — kontraobaveštajni nadzor.
K6 korisnici_uredjaji (29.682): digitalni otisak (OS, kolačić, LocalStorage GUID,
    uredjaj_parametar) — hardversko praćenje; multi-device i deljeni uređaji.
K7 arhiva_sms_poruke (11.627): zvanični SMS gateway „Internet Tim" (2FA kodovi,
    test poruke). TELEFONI I KODOVI SE MASKIRAJU.

FER PLAY:
- Vremensko poklapanje inspektora sa događajima (jul 2023) = KORELACIJA, ne uzrok.
- „Farma telefona preko deljenog uređaja" se proverava podatkom (ne pretpostavlja).
- sp_telefon se NIKAD ne izlaže (maska); 2FA kodovi se redaguju.

Izlaz: data/geo/system_surveillance.json → /api/system_surveillance.
Doc: docs/nadzor_operatera.md
"""
import json
import os
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "system_surveillance.json")


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    # --- K5: F12 inspector ----------------------------------------------------
    insp_total = q("SELECT count(*) FROM otvoren_inspector")[0][0]
    insp_distinct = q("SELECT count(DISTINCT oi_korisnik_id) FROM otvoren_inspector")[0][0]
    insp_span = q("SELECT min(oi_vreme), max(oi_vreme) FROM otvoren_inspector")[0]
    insp_top = [{"id": r[0], "ime": r[2] or f"#{r[0]}", "opened": r[1]} for r in q("""
        SELECT i.oi_korisnik_id, count(*),
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'')
        FROM otvoren_inspector i LEFT JOIN korisnici k ON k.k_id=i.oi_korisnik_id
        GROUP BY 1,3 ORDER BY 2 DESC LIMIT 15""")]
    inspector = {
        "records": insp_total, "distinct_operators": insp_distinct,
        "from": insp_span[0], "to": insp_span[1], "top_watched": insp_top,
        "note": ("Telemetrija otvaranja konzole koncentrisana u uskom prozoru "
                 f"({insp_span[0]} – {insp_span[1]}). Poklapanje sa internim događajima "
                 "(npr. curenje spiska u julu 2023) je KORELACIJA, ne dokaz uzroka."),
    }

    # --- K6: uređaji / digitalni otisak ---------------------------------------
    os_dist = [{"os": r[0] or "?", "devices": r[1], "operators": r[2]} for r in q("""
        SELECT ku_operativni_sistem, count(*), count(DISTINCT ku_korisnik_id)
        FROM korisnici_uredjaji GROUP BY 1 ORDER BY 2 DESC""")]
    multi5 = q("SELECT count(*) FROM (SELECT ku_korisnik_id FROM korisnici_uredjaji "
               "GROUP BY 1 HAVING count(*)>=5) z")[0][0]
    multi10 = q("SELECT count(*) FROM (SELECT ku_korisnik_id FROM korisnici_uredjaji "
                "GROUP BY 1 HAVING count(*)>=10) z")[0][0]
    shared = q("""SELECT count(*) FROM (
        SELECT ku_uredjaj_parametar FROM korisnici_uredjaji WHERE ku_uredjaj_parametar<>''
        GROUP BY 1 HAVING count(DISTINCT ku_korisnik_id)>=3) z""")[0][0]
    devices = {
        "records": q("SELECT count(*) FROM korisnici_uredjaji")[0][0],
        "os": os_dist, "operators_5plus_devices": multi5, "operators_10plus_devices": multi10,
        "shared_device_3plus_ops": shared,
        "note": ("Android dominira. Multi-device (5+ uređaja po operateru) je jak signal. "
                 f"Deljeni uređaj (isti parametar, 3+ operatera) = {shared} → hipoteza "
                 "o „farmi telefona“ preko deljenog parametra NIJE potkrepljena ovim poljem."),
    }

    # --- K7: SMS gateway (maskirano) ------------------------------------------
    sms_total = q("SELECT count(*) FROM arhiva_sms_poruke")[0][0]
    sms_status = {str(r[0]): r[1] for r in q("SELECT sp_status, count(*) FROM arhiva_sms_poruke GROUP BY 1 ORDER BY 2 DESC")}
    sms_span = q("SELECT min(sp_vreme_kreiranja), max(sp_vreme_kreiranja) FROM arhiva_sms_poruke")[0]
    # tip poruke (bez izlaganja koda/telefona)
    code2fa = q("SELECT count(*) FROM arhiva_sms_poruke WHERE sp_poruka ~* 'broj je|kod|code|verif'")[0][0]
    testmsg = q("SELECT count(*) FROM arhiva_sms_poruke WHERE sp_poruka ~* 'test'")[0][0]
    delivered = sms_status.get("2", 0)
    sms = {
        "messages": sms_total, "delivered": delivered,
        "delivered_pct": round(delivered / sms_total, 3) if sms_total else 0,
        "status_counts": sms_status, "from": sms_span[0], "to": sms_span[1],
        "type_2fa_codes": code2fa, "type_test": testmsg,
        "sender": "Internet Tim (alfanumerički SMS gateway)",
        "note": ("2FA kodovi i administrativne test poruke. Telefoni (sp_telefon) i "
                 "sami kodovi se NE izlažu — prikazuje se samo tip/status/obim."),
    }

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "inspector": inspector, "devices": devices, "sms": sms,
        "fair_play": ("Telefoni i 2FA kodovi maskirani. Vremenska poklapanja = korelacija. "
                      "Deljeni uređaj proveren podatkom (ne pretpostavljen)."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"K5 inspector: {insp_total} zapisa / {insp_distinct} operatera ({insp_span[0]}–{insp_span[1]})")
    print(f"   top praćeni: {[t['ime'] for t in insp_top[:4]]}")
    print(f"K6 uređaji: {devices['records']:,} · Android {os_dist[0]['devices']:,} · 5+ uređaja: {multi5} op · deljeni: {shared}")
    print(f"K7 SMS: {sms_total:,} ({round(sms['delivered_pct']*100)}% isporučeno) · 2FA {code2fa} · test {testmsg}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
