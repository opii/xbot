# Predlog: profilisanje posta pre objave + specijalizovana detekcija

**Status:** predlog arhitekture, nije implementirano.
**Pitanje na koje odgovara:** može li se, pre nego što post ode u javnost, automatski
napraviti detektor skrojen baš za taj post i taj portal — koji zna da je očekivano da
Srbi iz Beča i Čikaga čitaju srpsku politiku, ali da nije očekivano da se Kamerun
masovno interesuje za nju?

Kratak odgovor: **može, ali ne onako kako se prvo pomisli.** Razlika između naivne i
upotrebljive verzije je suštinska i opisana je odmah ispod.

---

## 1. Šta ovo jeste, a šta nije

**Jeste:** sistem koji za svaku kombinaciju *(post × portal)* unapred postavi
očekivanja — ko bi ovo trebalo da čita, odakle, kojim tempom — a zatim meri odstupanje
stvarnog saobraćaja od tih očekivanja.

**Nije:** detektor botova na nivou pojedinačnog posetioca. To je zaseban, komplementaran
sloj (fingerprint/headless detekcija tipa BotD). Ovaj sistem gleda **kohortu**, ne
pojedinca — jer koordinaciju i ne vidiš na pojedincu.

**Nije ni:** zamena za ljudsku procenu. Izlaz su *signali za pregled*, ne presude.

Ključno ograničenje koje treba razumeti pre svega ostalog: ovaj sistem vidi **samo
saobraćaj na tvom sajtu**. Ako se kampanja odvija na Tviteru, ovde je nevidljiva.
Hvata ono što dolazi do tebe — glasove, komentare, reakcije, čitanja.

---

## 2. Ključna odluka: model generiše *profil*, ne *kod*

Prvobitna ideja je bila da LLM generiše kod specijalizovan za post. To ne treba raditi,
iz četiri razloga:

1. **Bezbednost.** Izvršavanje koda koji je generisao model, u produkciji, na svaki
   post — to je udaljeno izvršavanje koda kao arhitektonska odluka, a ne kao propust.
2. **Nedeterminizam.** Dva poziva daju dva različita detektora za isti post. Nemoguće je
   reprodukovati zašto je nešto prijavljeno pre tri meseca — a upravo to ćeš morati da
   objasniš kad neko ospori nalaz.
3. **Nemogućnost pregleda.** Niko neće pregledati 200 generisanih skripti dnevno. A
   nepregledan kod u detekcionoj putanji je kod kojem ne veruješ.
4. **Nema evaluacije.** Ne možeš meriti da li detektor postaje bolji ako se menja na
   svaki poziv.

**Umesto toga:** model vraća **deklarativni profil** (strukturiran JSON), a *fiksni,
pregledani, testirani engine* taj profil izvršava. Model bira *šta* da se meri i *sa
kojom osetljivošću*; engine zna *kako* se meri.

Time ne gubiš ništa od specijalizacije koju si hteo — profil je i dalje jedinstven za
svaku kombinaciju posta i portala. Gubiš samo proizvoljan kod.

**Za retke slučajeve** kad katalog detektora stvarno ne pokriva nešto, kompromis je
**ograničen izrazni jezik** (CEL ili JSONLogic): model piše izraz nad već izračunatim
metrikama, bez I/O, bez petlji, sa tajmautom i obaveznim pregledom pre aktiviranja.
To je „generisana logika" bez „generisanog koda".

---

## 3. Arhitektura

```
  objava / edit
       │
       ▼  (asinhrono — NIKAD ne blokira objavu)
  ┌─────────────┐    post + kontekst portala      ┌──────────────┐
  │  Profiler   │ ───────────────────────────────▶│  Vertex AI   │
  │             │ ◀─────────────────────────────── │  (Claude)    │
  └─────┬───────┘      profil (strukturiran JSON)  └──────────────┘
        │
        ▼
  ┌─────────────────┐         ┌──────────────────────────────┐
  │ Profil posta    │◀────────│ Baseline (istorija portala)  │
  │ v1, v2, v3…     │         │ geo/ASN/tempo po klasi teme  │
  └─────┬───────────┘         └──────────────────────────────┘
        │
        ▼
  ┌──────────────────────┐     ┌────────────────────────────┐
  │  Detekcioni engine   │◀────│ Telemetrija saobraćaja     │
  │  (FIKSNI KOD)        │     │ glasovi/komentari/čitanja  │
  └─────┬────────────────┘     └────────────────────────────┘
        │
        ▼
   signali → red za pregled → (opciono) automatska mera
```

Tri stvari koje ovaj dijagram tvrdi, a vredi ih izgovoriti naglas:

- **Objava se ne blokira.** Profilisanje traje sekunde do desetak sekundi; objava traje
  koliko traje. Dok profil ne stigne, važi podrazumevani profil za taj portal.
- **Baseline ne dolazi od modela.** Dolazi iz istorije samog portala.
- **Engine je fiksan.** Menja se kroz pull request, ne kroz prompt.

---

## 4. Podela rada: šta odlučuje model, a šta podaci

Ovo je drugi po važnosti deo dokumenta i najčešći izvor grešaka u ovakvim sistemima.

| | **Model (Vertex AI)** | **Tvoji podaci** |
| --- | --- | --- |
| Uloga | semantika | brojevi |
| Odgovara na | „o čemu je ovo, koga zanima, ko bi legitimno mogao da reaguje" | „kako zapravo izgleda saobraćaj na ovom portalu za ovakve teme" |
| Primer izlaza | tema = *unutrašnja politika / izborna*; relevantne dijaspore = AT, DE, CH, US, CA, SE | iz poslednjih 90 dana: AT 4,1%, DE 6,8%, CH 2,2%, US 1,9%… |
| Rizik ako se pobrka | **model halucinira procente** koji zvuče ubedljivo | — |

**Model nikada ne daje očekivane procente.** On zna, grubo, da ima dosta Srba u Beču i
Turaka u Nemačkoj — ali ne zna koliko njih čita *baš tvoj portal*, i izmisliće broj koji
izgleda razumno. Tačan broj imaš samo ti, u svojim logovima.

Model daje **skup zemalja koje su legitimno objašnjive** i obrazloženje za svaku.
Baseline daje **koliko ih se očekuje**.

Arhitektura primenjuje **dvo-kapijsku proveru (Two-gate check)**:
1. **Kapija 1 (Semantička dozvola — LLM):** Da li je zemlja uopšte u `plausible_*` skupu?
   Ako zemlja X (npr. Kamerun, Kongo ili Vijetnam za srpsku unutrašnju politiku) **nije** na
   spisku, svaka pojava iznad statističkog šuma (npr. >0,5% saobraćaja) **odmah pali alarm**.
   Engine tu uopšte ne pita baseline da li je ta zemlja „uobičajena u istoriji sajta“ —
   semantički neobjašnjiva lokacija se seče na prvoj kapiji.
2. **Kapija 2 (Statistička raspodela — Baseline):** Za zemlje koje **jesu** u objašnjivom
   skupu (npr. Austrija, Nemačka), engine meri KL-divergenciju u odnosu na istorijski baseline
   portala za tu klasu tema.

**„Pali alarm" znači signal, ne meru.** Kapija 1 proizvodi ulaz u kompozitni skor i red za
pregled; sama, bez bihevioralnog ili infrastrukturnog signala, ne pokreće nikakvu automatsku
meru. To je isto tvrdo pravilo iz §8 i ovde važi bez izuzetka.

**Kapija 1 mora imati povratnu spregu.** Cena zaobilaženja baseline-a je da sve zavisi od
toga da model nije *zaboravio* zemlju. Propusti li Švedsku (velika srpska zajednica) ili ne
shvati da tekst o srpskom sportisti u Japanu legitimno privlači japanske čitaoce, dobijaš
lažni pozitiv — a mreža koja bi ga uhvatila je upravo ta koju smo namerno zaobišli.

Zato: zemlja koju recenzent **dva puta** označi kao legitimnu promoviše se u trajni
`portal_allowlist`, koji se spaja sa `plausible_*` pri svakoj evaluaciji. Bez toga recenzenti
mesecima dobijaju isti lažni alarm, prestanu da ga gledaju, i red za pregled postane šum —
što je najčešći način na koji ovakvi sistemi tiho umru.

Prag od 0,5% je ilustracija, ne vrednost za implementaciju: stvarni prag izvodi engine iz
`sensitivity` nivoa i veličine uzorka (mali post nema statističku masu za bilo kakav zaključak).

---

## 5. Profil posta — ugovor sa modelom

Strukturiran izlaz (`output_config.format` sa JSON šemom), ne slobodan tekst.

```jsonc
{
  "profile_version": 3,
  "post_id": "n1-2026-10-20-1874",
  "portal_id": "n1info.rs",
  "generated_at": "2026-10-20T11:04:22Z",
  "model": "claude-opus-5",

  "topic": {
    "primary": "unutrasnja_politika",
    "secondary": ["izbori", "korupcija"],
    "named_entities": ["SNS", "Novi Sad"],
    "political_valence": "kriticki_prema_vlasti",
    "controversy": 0.82                    // 0–1, očekivana sporost teme
  },

  "audience": {
    "primary_market": "RS",
    "plausible_diaspora": [                // SAMO skup, bez procenata
      {"cc": "AT", "rationale": "velika srpska zajednica u Beču"},
      {"cc": "DE", "rationale": "gastarbajterska dijaspora"},
      {"cc": "CH", "rationale": "velika srpska zajednica"},
      {"cc": "US", "rationale": "Čikago, srpska zajednica"},
      {"cc": "CA", "rationale": "Toronto"}
    ],
    "plausible_other": [
      {"cc": "BA", "rationale": "deljen jezik i politički prostor"},
      {"cc": "ME", "rationale": "deljen jezik i politički prostor"},
      {"cc": "HR", "rationale": "regionalni interes"}
    ],
    "language_scope": ["sr", "hr", "bs", "me"]
  },

  "expected_dynamics": {
    "tempo_class": "brz_pa_opadajuci",     // iz taksonomije, ne slobodan tekst
    "peak_window_min": 90,
    "expected_comment_ratio": "visok",
    "vote_brigading_risk": 0.74
  },

  "detectors": [                           // izbor iz FIKSNOG kataloga
    {"id": "geo_divergence",      "enabled": true, "sensitivity": "high"},
    {"id": "asn_composition",     "enabled": true, "sensitivity": "high"},
    {"id": "tempo_burst",         "enabled": true, "sensitivity": "medium"},
    {"id": "template_similarity", "enabled": true, "sensitivity": "high"},
    {"id": "pseudonym_diversity", "enabled": true, "sensitivity": "medium"},
    {"id": "cross_post_cohort",   "enabled": true, "sensitivity": "high"},
    {"id": "session_behavior",    "enabled": true, "sensitivity": "medium"}
  ],

  "rationale": "Kritički tekst o izborima pred lokalne izbore; visok rizik od
                organizovanog downvote-a i šablonskih komentara. Strani saobraćaj je
                očekivan samo iz dijaspore i regiona.",
  "confidence": 0.86
}
```

Dve stvari koje ovaj profil **namerno ne sadrži**: konkretne pragove i očekivane
procente. Pragovi se izvode iz baseline-a i `sensitivity` nivoa, u engine-u. Da model
upisuje pragove, dobio bi nereproducibilno ponašanje i izmišljene brojeve.

---

## 6. Poziv ka Vertex AI

Skica (Python; tačne potpise proveriti u SDK dokumentaciji pre implementacije):

```python
from anthropic import AnthropicVertex   # pip install "anthropic[vertex]"

client = AnthropicVertex(project_id=GCP_PROJECT, region="global")

resp = client.messages.create(
    model="claude-opus-5",
    max_tokens=4096,
    thinking={"type": "adaptive"},
    output_config={
        "effort": "medium",
        "format": {"type": "json_schema", "schema": POST_PROFILE_SCHEMA},
    },
    system=[
        # Stabilan prefiks — keširati. Menja se retko, pa je keš isplativ.
        {"type": "text", "text": TAXONOMY_AND_RULES,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": PORTAL_CONTEXT[portal_id],
         "cache_control": {"type": "ephemeral"}},
    ],
    messages=[{"role": "user", "content": post_payload}],
)
```

Napomene koje nisu kozmetičke:

- **Keširanje prefiksa.** Taksonomija i opis portala su isti za svaki post tog portala.
  Stave se u `system` sa `cache_control`, a promenljivi deo (sam post) ide posle. Ovo
  obara cenu ulaza za red veličine. Proveri `usage.cache_read_input_tokens` — ako je
  nula kroz uzastopne pozive, nešto tiho ruši keš (najčešće timestamp u promptu).
- **Taksonomija mora biti zatvorena.** `topic.primary` i `tempo_class` su enumeracije u
  šemi, ne slobodan tekst. Inače ti se posle tri meseca u bazi nađe četrdeset varijanti
  iste teme i nijedna agregacija ne radi.
- **Model.** `claude-opus-5` je podrazumevani izbor. Ako obim postane ozbiljan, cena se
  prvo obara keširanjem i `effort` nivoom, pa tek onda razmatranjem jeftinijeg modela —
  i to merenjem na stvarnim postovima, ne pretpostavkom.
- **Vertex ima sopstveno partnersko tarifiranje**, različito od prvostrane API cene.
- **Otpornost na Prompt Injection u telu posta.** Tekst vesti se u `messages` šalje unutar
  strogo izolovanih XML/JSON blokova (`<article_content>`), uz eksplicitnu sistemsku
  instrukciju da se sadržaj tretira isključivo kao neprovereni podatak, a ne kao direktiva.
  Time se sprečava napad gde bi maliciozni autor teksta ili citat u članku pokušao da natera
  model da npr. Kamerun proglasi za „objašnjivu dijasporu“.

  Izolacija je ublažavanje, ne garancija. Dve dopune: (a) `plausible_diaspora` se unakrsno
  proverava sa **statičkom referentnom tabelom** stvarnih dijaspora — zemlja koju model doda
  van te tabele traži ljudsku potvrdu pre nego što uđe u profil; (b) **`rationale` stringovi
  su izlaz modela izveden iz neproverenog ulaza** i prikazuju se recenzentu, pa se pri
  renderovanju tretiraju kao neproveren sadržaj (eskejpovanje, bez HTML-a) — inače je red za
  pregled vektor i za XSS i za socijalni inženjering recenzenta.

---

## 7. Katalog detektora (fiksni engine)

Model bira iz ovog skupa; ne proširuje ga. Proširuje ga pull request.

| `id` | Šta meri | Signal |
| --- | --- | --- |
| `geo_divergence` | raspodela po državama naspram baseline-a (KL divergencija) | masa iz zemlje koja nije u `plausible_*` |
| `asn_composition` | udeo datacentar/VPN/hosting naspram rezidencijalnih i mobilnih ASN-ova | skok hosting ASN-ova = jeftina anonimizacija |
| `tempo_burst` | udeo reakcija u prvih N minuta, pravilnost razmaka | vojnička sinhronija |
| `template_similarity` | near-duplicate klasterovanje teksta (MinHash/LSH) | šablonski komentari |
| `pseudonym_diversity` | broj različitih imena po izvoru/sesiji | industrija lažnih identiteta |
| `cross_post_cohort` | ista kohorta pogađa više postova | **najjači signal** — ko-aktivnost |
| `session_behavior` | vreme na strani pre glasa, prisustvo interakcije, headless potpisi | automatizovano glasanje |
| `edit_delta` | promena profila između verzija posta | bait-and-switch |

`cross_post_cohort` je najvredniji i najčešće izostavljen. Pojedinačan post sa čudnim
saobraćajem je anegdota; **ista grupa koja se pojavljuje na deset kritičkih tekstova u
istoj nedelji je obrazac.** To je, konceptualno, `CO_ACTED` iz Cacix-a primenjen uživo.

*Napomena o mobilnom CGNAT-u:* Zbog zaštite privatnosti IP adrese se skraćuju na `/24`.
U mobilnim mrežama (npr. domaći Telekom ili afrički provajderi poput CAMNET-a), stotine hiljada
legitimnih korisnika dele iste CGNAT pool-ove. Zato `cross_post_cohort` nikada ne sme da se
osloni samo na puki mrežni prefiks — kohorta se uvek vezuje za **spregu mrežnog prefiksa i
bihevioralnog otiska** (isti uski vremenski prozor reakcije, dwell time < 2s, nula interakcije).

---

## 8. Dijaspora — najteži deo

Ovde sistem najlakše pravi štetu, pa zaslužuje poseban odeljak.

**Problem:** „strana država = sumnjivo" je pravilo koje kažnjava dijasporu. Čitalac iz
Beča ili Čikaga je legitiman kao i onaj iz Beograda, i tretirati ga drugačije je i
pogrešno i uvredljivo.

**Zato se geografija ne koristi samostalno.** Tri sloja razlikovanja:

1. **Da li postoji objašnjenje?** Austrija ima objašnjenje za srpski politički tekst.
   Kamerun nema. Model daje taj skup — to je zadatak za koji je dobar.

2. **Kakva je infrastruktura?** Ovo je često informativnije od same zemlje. Datacentar
   ili VPN izlaz ne dokazuje ništa — svako može zakupiti server za pet evra. Ali
   **rezidencijalni ili mobilni ASN** znači da saobraćaj prolazi kroz mrežu krajnjih
   korisnika na toj lokaciji. U Cacix podacima je najveći strani otisak upravo niz
   afričkih *mobilnih* operatera (Kamerun 472 distinct IP: CAMNET 195, MTN 172,
   Orange 124; pa Congo Telecom) — što je mnogo teže objasniti kao jeftinu anonimizaciju
   nego hosting ASN.
   **Ali oprez u oba smera:** mobilne mreže koriste CGNAT i rotiraju adrese, pa broj IP-ova
   nije broj uređaja — ni gore ni dole. Mobilni ASN je *jači* signal od datacentra, ali
   nije dokaz o broju mašina.

3. **Da li se ponašanje razlikuje od ostatka te iste kohorte?** Beč koji čita kao i
   ostatak dijaspore je normalan. Beč koji glasa za 1,2 sekunde po članku, bez
   skrolovanja, u 300 sesija iz istog /24 — nije. **Ponašanje unutar grupe nadjačava
   geografiju.**

Pravilo koje bi trebalo da bude tvrdo kodirano: **nijedan signal zasnovan isključivo na
geografiji ne sme sam da pokrene automatsku meru.** Mora ga pratiti bihevioralni ili
infrastrukturni signal.

---

## 9. Edit kao signal

Tvoja ideja da se profiliše i pri svakom editu nije samo higijena — ona hvata konkretan
napad.

**Bait-and-switch:** objaviš bezazlen tekst, sakupi se organski saobraćaj i rangiranje,
pa se tekst izmeni u politički. Profil v1 i profil v2 se tada drastično razlikuju.

Zato `edit_delta` meri **rastojanje između verzija profila**, a ne samo novi profil:

- promena `topic.primary` posle objave → visok signal
- skok `political_valence` iz neutralnog u polarizovan → visok signal
- promena naslova uz nepromenjeno telo → srednji signal (SEO ili bait)
- tipografske ispravke → nema signala

Čuvati **sve verzije profila**, ne samo poslednju. Kad se nešto ospori, treba ti ono što
je sistem mislio *u tom trenutku*, ne ono što misli danas.

---

## 10. Skorovanje i posledice

Engine ne izriče presudu. Proizvodi **signale sa dokazima**:

```jsonc
{
  "post_id": "n1-2026-10-20-1874",
  "window": "2026-10-20T12:00Z/13:00Z",
  "signals": [
    {"detector": "geo_divergence", "score": 0.91,
     "evidence": {"cc": "CM", "observed": 0.31, "baseline": 0.002,
                  "in_plausible_set": false}},
    {"detector": "asn_composition", "score": 0.77,
     "evidence": {"asn": "AS30992 CAMNET", "sessions": 472, "type": "mobile"}},
    {"detector": "session_behavior", "score": 0.84,
     "evidence": {"median_dwell_s": 1.2, "no_interaction_pct": 0.96}}
  ],
  "composite": 0.86,
  "recommendation": "review"
}
```

Stepenovanje posledica — nikad odmah blokada:

| Kompozitni skor | Mera |
| --- | --- |
| < 0,4 | ništa, samo se loguje |
| 0,4–0,7 | red za pregled, bez vidljivog efekta |
| 0,7–0,85 | glasovi iz označene kohorte se izdvajaju iz javnog brojača (čuvaju se) |
| > 0,85 | pregled uz prioritet + proof-of-work izazov za novi saobraćaj |

**Automatsko brisanje komentara ne postoji ni na jednom nivou.** Lažni pozitiv tu košta
mnogo više nego lažni negativ — pogrešno obrisan legitiman komentar je cenzura, a
propušten bot je šum.

---

## 11. Kako ovo ne radi

Pošteno nabrojano, jer svaka od ovih stavki može da potopi projekat:

- **Hladan start.** Nov portal ili nova tema nemaju baseline. Rešenje: predefinisani
  regionalni arhetipovi (npr. *srpski informativni portal*, *lokalni vojvođanski medij*) +
  globalni podrazumevani profil uz eksplicitno nisku pouzdanost prvih 30 dana; dotad samo logovati.
- **Zagađeni baseline (sindrom kuvane žabe / hronični napad).** Šta ako je portal mesecima
  ili godinama već pod intenzivnim voter napadom (upravo scenario koji je Cacix otkrio — 550M
  klikova godinama sa kladioničarskih terminala u Srbiji i Africi)? Ako se baseline naivno
  izračuna kao prosek istorijskih logova, engine će 15% saobraćaja iz Kameruna proglasiti za
  „normalno stanje“. Rešenje je četvorostruko:
  1. *Semantički rez:* Neobjašnjive zemlje nikad ne ulaze u `plausible_*` (Kapija 1 ih seče
     makar činile 50% istorijskog saobraćaja).
  2. *Sanitizacija pre baseline-a (Clean Baseline):* Pre računanja istorijskih raspodela,
     iz logova se filtriraju sesije sa očiglednim botovskim parametrima (dwell time < 3s, 0%
     skrolovanja, hosting/serverski ASN-ovi).
  3. *Unakrsno poređenje tema (Cross-topic baseline):* Voter mašine i operateri napadaju
     politiku, izbore i afere. Niko ne botuje recepte, kulturu ili vremensku prognozu. Mirne
     rubrike daju čist baseline stvarne publike portala.
     **Ograda:** mirne rubrike daju *drugačiju* publiku, ne samo čistiju — čitaoci recepata se
     geografski i demografski razlikuju od čitalaca politike. Zato se ovaj baseline koristi kao
     **gornja granica i provera razumnosti** („može li politička rubrika imati 15% Kameruna kad
     ga ceo portal nema 0,3%?"), a ne kao direktna očekivana raspodela. U suprotnom se jedna
     pristrasnost zamenjuje drugom.
  4. *Bihevioralni sloj nadjačava procente:* Čak i ako napad dolazi iz legitimne zemlje
     (npr. Nemačka ili domaći Telekom), nedostatak interakcije (`session_behavior`) ruši skor.
- **Legitiman viralni proboj.** Tekst stvarno može da eksplodira u inostranstvu. Zato
  „neobično" ≠ „neautentično" — i zato red za pregled, a ne blokada.
- **Adaptacija protivnika.** Ako su pragovi predvidivi, zaobići će ih. Ne izlagati
  pragove, uvoditi nasumičnost u `sensitivity`, rotirati ih.
- **Ljudi, ne botovi.** Najvažnija pouka iz Cacix-a: operateri su bili **ljudi u
  smenama, na pravim uređajima**. Njihov fingerprint je savršeno normalan. Hvata ih samo
  `cross_post_cohort` i `template_similarity` — ne fingerprint.
- **Model greši u klasifikaciji.** Pogrešna tema → pogrešan baseline → pogrešan signal.
  Zato `confidence` u profilu, i zato uzorak profila ide na ljudsku proveru.
- **Troškovna zamka.** Jedan poziv po postu je jeftino. Jedan poziv po zahtevu bi bio
  katastrofa. Profil se računa po postu, detekcija radi na agregiranoj telemetriji.

---

## 12. Privatnost i pravni okvir

Sistem obrađuje IP adrese i bihevioralnu telemetriju čitalaca — **to su lični podaci**.

- Pravni osnov: legitimni interes (zaštita integriteta servisa), dokumentovano.
- IP se ne čuva sirov duže nego što traje detekcioni prozor; posle toga ostaje
  `/24` prefiks, ASN i država.
- Retencija telemetrije: dani, ne godine. Signali i agregati mogu duže.
- Bez profilisanja pojedinca kroz vreme i kroz portale — jedinica analize je **kohorta
  na postu**, a ne čitalac.
- Fingerprinting ima zasebne implikacije (ePrivacy); ako se uvede BotD ili slično,
  tretirati ga odvojeno i pravno proveriti.

---

## 13. Cena

Red veličine, po postu: ulaz 2–4k tokena (post + kontekst + taksonomija), izlaz ~1k.
Uz keširan prefiks, efektivni ulaz padne znatno. Za portal sa 200 postova dnevno to je
svega nekoliko dolara dnevno — zanemarljivo u odnosu na trošak jednog pregleda od strane
čoveka.

Dve poluge pre razmišljanja o jeftinijem modelu: **keširanje prefiksa** i **`effort`
nivo**. Za masovno re-profilisanje arhive koristiti Batch API (upola jeftinije, nije
osetljivo na latenciju).

Konkretne cifre za Vertex uzeti sa Google-ove stranice za partnersko tarifiranje —
razlikuju se od prvostranih.

---

## 14. Redosled gradnje

| Faza | Šta | Zašto prvo |
| --- | --- | --- |
| 0 | Telemetrija + **sanitizovani** baseline iz istorije | **Bez čistog baseline-a ništa drugo nema smisla.** Čišćenje logova od očiglednih bot-sesija (<3s) i unakrsno poređenje sa mirnim rubrikama pre računanja normala. Nema profila, nema modela — samo merenje. |
| 1 | Tri detektora bez LLM-a: `geo_divergence`, `tempo_burst`, `asn_composition`, sa ručnim profilima po portalu | Dokazuje da signal uopšte postoji u podacima |
| 2 | Profiler na Vertex AI, ali **samo u shadow režimu** — profili se čuvaju i porede sa ručnim | Meri da li model dodaje vrednost pre nego što išta zavisi od njega |
| 3 | Ostatak kataloga detektora + kompozitni skor + red za pregled | Tek sad sistem nekom koristi |
| 4 | `cross_post_cohort` i `edit_delta` | Najjači signali, ali traže istoriju iz faza 0–3 |
| 5 | Stepenovane mere | Poslednje, kad su lažni pozitivi izmereni |

Faza 1 je presudna. Ako tri jednostavna detektora nad realnim podacima ne proizvedu
nijedan upotrebljiv signal, LLM sloj neće to popraviti — samo će skupo zamagliti.

---

## 15. Veza sa Cacix-om

Cacix je ovome **retrospektivni blizanac**: isti detektori, nad podacima posle događaja,
sa unutrašnjim ground-truth-om. To je ozbiljna prednost pri gradnji, jer imaš nešto što
gotovo niko nema — **označen skup u kom se zna ko je zaista bio koordinisan.**

Preslikavanje je gotovo jedan na jedan:

| Cacix | Ovde |
| --- | --- |
| `CO_ACTED` / `CO_COMMENTED` | `cross_post_cohort` |
| `template_frac`, `CO_TEMPLATE` | `template_similarity` |
| `burst10` iz `target_bursts` | `tempo_burst` |
| `pseudonyms` (`vkk_autor`) | `pseudonym_diversity` |
| `auto_score` komponente | `session_behavior` |
| `voter_geoip` (ASN, država) | `geo_divergence`, `asn_composition` |

Praktična posledica: **Cacix dataset je eval set.** Pragovi i težine se mogu kalibrisati
nad podacima gde se tačno zna šta je bila koordinacija — umesto da se pogađaju. To je
najvredniji deo celog predloga i razlog zašto bi ovo moglo da radi bolje od generičkih
rešenja.

Vidi i: [`slojevi_koordinacije.md`](slojevi_koordinacije.md),
[`voter_kladionice_infrastruktura.md`](voter_kladionice_infrastruktura.md),
[`CACIX_MASTER_OSINT_WHITEPAPER.md`](CACIX_MASTER_OSINT_WHITEPAPER.md).
