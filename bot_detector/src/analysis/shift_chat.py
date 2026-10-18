#!/usr/bin/env python3
"""
Zadatak 1: operativni chat i dežurstva — ko vodi smene i kako kontroliše kvalitet.

Tabela `chat_twitter_brisanje` (20.232 poruke): ctb_vreme, ctb_poruka (HTML),
ctb_korisnik (k_id). Interni operativni chat — dnevnici smena, primopredaje,
kontrola („vratila sam što nije po pravilima"), krizni nalozi za brisanje tvitova.

FER PLAY: poruke su interni operativni logovi REALNIH ljudi (dežurni/supervizori);
imena se tretiraju odgovorno (isti principi kao u ostatku sistema). Iznosimo
operativni sadržaj (smene, kontrola, brisanja), ne privatne lične podatke.

Izlaz: data/geo/shift_chat.json → /api/shift_chat → UI „💬 Dnevnik dežurstava".
Pokretanje:  ./venv/bin/python src/analysis/shift_chat.py
"""
import html
import json
import os
import re
from datetime import datetime

import psycopg2

PG = "host=localhost dbname=bot_detector_db user=bot_user password=bot_password"
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "geo", "shift_chat.json")

# Taksonomija (regex, case-insensitive) — poklapa primer primopredaje iz zadatka.
TAX = {
    "primopredaja": r"prijava|odjava|smena|preuzima|predaj|koleg|laku noć|laku noc|zdravo svima",
    "kontrola": r"vratila|vratio|nije po pravil|ispravite|ponovite|analiz|proveri|kontrol",
    "brisanje": r"obriši|obrisi|brisanje|brisi|obrisan|pogrešan link|pogresan link|greška|greska|pogrešan tvit",
}


def clean(s):
    if not s:
        return ""
    s = s.replace("<\\/", "</").replace("<\\", "<")
    s = re.sub(r"<[^>]+>", " ", s)          # skini HTML tagove (div, br…)
    s = html.unescape(s)
    s = s.replace("\\n", " ").replace("\\t", " ").replace("\\/", "/")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    pg = psycopg2.connect(PG); cur = pg.cursor()
    cur.execute("SET search_path TO progress")

    def q(s, a=None):
        cur.execute(s, a); return cur.fetchall()

    total = q("SELECT count(*) FROM chat_twitter_brisanje")[0][0]

    # --- vodeći dežurni/supervizori (ko najviše piše) ------------------------
    sup = q("""
        SELECT ch.ctb_korisnik, count(*) n,
               NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') ime,
               k.k_pozicija, o.o_naziv okrug, op.op_naziv opstina
        FROM chat_twitter_brisanje ch
        LEFT JOIN korisnici k ON k.k_id = ch.ctb_korisnik
        LEFT JOIN okrug o ON o.o_id = k.k_okrug
        LEFT JOIN opstina op ON op.op_id = k.k_opstina
        GROUP BY 1,3,4,5,6 ORDER BY 2 DESC LIMIT 25
    """)
    supervisors = [{"id": r[0], "ime": r[2] or f"#{r[0]}", "msgs": r[1],
                    "pozicija": r[3], "okrug": r[4], "opstina": r[5]} for r in sup]

    # --- taksonomija poruka ---------------------------------------------------
    taxonomy = {}
    for lbl, rx in TAX.items():
        taxonomy[lbl] = q("SELECT count(*) FROM chat_twitter_brisanje WHERE ctb_poruka ~* %s", (rx,))[0][0]

    # --- vremenski profil (po satu) ------------------------------------------
    hours = [0] * 24
    for h, n in q(r"SELECT substr(ctb_vreme,12,2), count(*) FROM chat_twitter_brisanje "
                  r"WHERE ctb_vreme ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}' GROUP BY 1"):
        if h and h.isdigit():
            hours[int(h)] = n

    # --- reprezentativne verbatim poruke po kategoriji -----------------------
    def samples(rx, lo, hi, limit=10):
        rows = q("""SELECT ch.ctb_vreme, ch.ctb_poruka,
                       NULLIF(trim(coalesce(k.k_ime,'')||' '||coalesce(k.k_prezime,'')),'') ime
                    FROM chat_twitter_brisanje ch
                    LEFT JOIN korisnici k ON k.k_id = ch.ctb_korisnik
                    WHERE ch.ctb_poruka ~* %s AND length(ch.ctb_poruka) BETWEEN %s AND %s
                    ORDER BY length(ch.ctb_poruka) DESC LIMIT %s""", (rx, lo, hi, limit * 3))
        out, seen = [], set()
        for vreme, por, ime in rows:
            t = clean(por)
            key = t[:40].lower()
            if len(t) < 12 or key in seen:
                continue
            seen.add(key)
            out.append({"vreme": vreme, "ime": ime or "?", "tekst": t[:400]})
            if len(out) >= limit:
                break
        return out

    handover = samples(r"smena|primopredaj|odjava|preuzima|protekla", 60, 600, 10)
    control = samples(TAX["kontrola"], 50, 600, 8)
    deletion = samples(r"obriši|obrisi|brisi|obrisan|pogrešan|pogresan|greška|greska|izbriš", 12, 150, 10)

    out = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "total_messages": total,
        "supervisors": supervisors,
        "taxonomy": taxonomy,
        "hours": hours,
        "samples": {"handover": handover, "control": control, "deletion": deletion},
        "note": ("Interni operativni chat smene (dnevnik dežurstava). Vreme predaje "
                 "smene se vidi kao pikovi po satu (oko 12h, 15h, 19h + jutarnja 8h)."),
        "fair_play": ("Poruke su operativni logovi realnih ljudi; imena = operateri "
                      "(isti tretman kao drugde). Iznosi se operativni sadržaj smene/"
                      "kontrole/brisanja, ne privatni lični podaci."),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Poruka: {total} · taksonomija: {taxonomy}")
    print("Top supervizori:")
    for s in supervisors[:6]:
        print(f"  {s['msgs']:>5}  {s['ime']:<22} [{s['pozicija'] or '?'}] {s['okrug'] or ''}")
    print(f"Pikovi predaje smene (sat): {sorted(range(24), key=lambda h: -hours[h])[:4]}")
    print(f"\n[OK] {OUT}")
    pg.close()


if __name__ == "__main__":
    main()
