# Slojevi koordinacije — šta znači prekidač „Sloj: Tviter / Komentari"

Prekidač u levom meniju ne menja filter nad istim podacima — on bira **koji dokaz
koordinacije se gleda**. To su dve nezavisno izgrađene mreže nad istim ljudima.

Zajedničko im je jedno: čvor je uvek **operater** (osoba), nikad pojedinačni nalog,
a veza uvek znači „ovo dvoje su radili na istoj stvari". Razlikuje se *šta* je ta
zajednička stvar.

## Dva sloja ukratko

| | **Tviter** | **Komentari** |
| --- | --- | --- |
| Veza u Neo4j | `CO_ACTED` | `CO_COMMENTED` |
| Šta znači veza | dvoje su dirali **iste tvitove-mete** (lajk / retvit / odgovor / citat) | dvoje su komentarisali **iste vesti** na portalima |
| Težina veze (`shared`) | broj zajedničkih meta | broj zajedničkih vesti |
| Stepen na čvoru | `co_degree` | `cc_degree` |
| Izvor podataka | `arhiva_twitter_unos_korisnici_akcije` | `arhiva_vesti_korisnici_komentari` (`vkk_simulacija=0`) |

## Zašto postoje pragovi (i koji su)

Masovne mete su šum: tvit koji je dirnulo 3.608 operatera ne govori ništa o tome ko
s kim radi — svi su ga dirali. Prava koordinacija se vidi na **retkim, deljenim**
metama. Zato se pri gradnji grafa odsecaju oba kraja raspodele:

| Sloj | Meta/vest ulazi u račun ako je dira | Veza se pravi ako dvoje dele |
| --- | --- | --- |
| `CO_ACTED` | 2–30 operatera (`--coact-ceil 30`) | ≥ 4 mete (`--coact-min 4`) |
| `CO_COMMENTED` | 2–20 operatera (`--cocom-ceil 20`) | ≥ 5 vesti (`--cocom-min 5`) |

Pragovi su **izbor, ne prirodna konstanta** — menjaju gustinu mreže i osetljivost.
Rezultate treba čitati uz njih. Menjaju se argumentima `load_graph.py`.

## Kako slojevi izgledaju na ovom datasetu

| | Tviter | Komentari |
| --- | --- | --- |
| Operatera sa bar jednom vezom | 402 | 1.592 |
| Veza | 12.154 | 130.744 |
| Prosečan stepen | 60,5 | 164,3 |
| Zajednica (Louvain) | 12 | 4 |
| Centroida (organizatora) | 12 | 4 |
| Posle backbone filtera | 946 veza | 11.940 veza |

Sloj Komentari je **red veličine gušći**. To nije „više koordinacije" nego posledica
toga što jedan operater ostavi hiljade komentara na malom broju portala, pa se
preklapanja lako gomilaju. Praktično: u tom sloju su klizač **„min jačina veze"** i
**„samo backbone (disparity)"** gotovo obavezni, inače se dobije klupko.

## Šta se konkretno menja u aplikaciji

1. **Ko je „najpovezaniji"** — pogled *Pregled* rangira po `co_degree` odnosno
   `cc_degree`, pa na vrhu dobijaš drugu ekipu ljudi.
2. **Šta se razlistava na klik** — na Tviteru: **nalozi** pod kontrolom (`CONTROLS`),
   ko-akteri i **mete** (`@handle`). Na Komentarima: ko-komentatori i **portali**
   (N1, Danas, Informer…). Potpuno drugi tipovi čvorova i druga legenda boja.
3. **Organizatori i zajednice** — Louvain, PageRank i betweenness računaju se po
   sloju odvojeno: `tw_community`/`tw_org`/`tw_organizer` nasuprot
   `cc_community`/`cc_org`/`cc_organizer`.
4. **Putanja** između dvoje ljudi traži se kroz izabrani sloj; „spone" su konkretne
   zajedničke mete odnosno zajedničke vesti po skoku.
5. **Rang-liste bihevioralnih metrika** koriste veze izabranog sloja za prikaz grafa
   oko rangiranih operatera.

## Zašto oba, a ne jedan

Slojevi su **nezavisni dokazi**. Neko može biti jak na Tviteru a nevidljiv u
komentarima (i obrnuto) — to su različite uloge u operaciji.

Zato postoji pogled **⚑ Master**, koji množi oba:

```
master = √(tw_org · cc_org)
```

Visok `master` znači da se koordinacija oko te osobe vidi **i na Tviteru i u
komentarima**. To je jači nalaz od jačine u jednom sloju, jer ga potvrđuju dva
nezavisno izgrađena grafa iz dve različite tabele.

## Treći sloj (nije u prekidaču)

Postoji i **`CO_TEMPLATE`** — veza „dvoje koriste isti tekst". Gradi se nad
normalizovanim komentarom (mala slova, sažet razmak, dužina ≥ 15 znakova) koji
koristi 3–60 operatera; veza se pravi na ≥ 3 deljena šablona. Na ovom datasetu:
2.305 operatera i 17.238 veza.

Nije u prekidaču zato što nije sloj *aktivnosti* nego *teksta* — koristi se u
bihevioralnoj metrici „Deljeni šabloni" (`template_frac`) i vidi se kao zasebna boja
veze u grafu.

## Granica tumačenja (fer play)

Veza u bilo kom sloju znači **poklapanje u radu**, ne dokaz da se dvoje poznaju ili
da je jedno drugom naredilo. Komandni odnos se čita iz direktiva i koordinatorskih
tabela, ne iz ko-aktivnosti — i upravo je nalaz ovog projekta da se ta dva sloja
**razilaze** (nijedan od 156 koordinatora nije grafni centroid).

Vidi i: [`analiza_koordinatora.md`](analiza_koordinatora.md),
[`analiza_direktiva.md`](analiza_direktiva.md),
[`CACIX_MASTER_OSINT_WHITEPAPER.md`](CACIX_MASTER_OSINT_WHITEPAPER.md).
