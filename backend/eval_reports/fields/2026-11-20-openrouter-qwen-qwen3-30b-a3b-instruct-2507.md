# Parser field evaluation

- Date: 2026-11-20 22:29:05 UTC (finished 2026-11-20 22:38:48 UTC)
- Provider: `openrouter`
- Model: `qwen/qwen3-30b-a3b-instruct-2507`
- Extractor: `openrouter`
- Repeats: 3
- Case set sha256: `5c3afa1f769d86c3187ba74f11a21dd32bca3a7b894070eb3837326433065de0`
- Cases: 42
- Extractor calls: 126 (0 failed)
- Tokens (in / out): 73950 / 12008
- Mean call time: 3920 ms

## Accuracy per field

Counts over (case, repeat, field); failed calls are not counted here.

| Field | Hit | Flagged miss | Silent wrong | Total |
|---|---|---|---|---|
| customer | 126 (100%) | 0 (0%) | 0 (0%) | 126 |
| product_code | 126 (100%) | 0 (0%) | 0 (0%) | 126 |
| quantity | 126 (100%) | 0 (0%) | 0 (0%) | 126 |
| deadline | 117 (93%) | 9 (7%) | 0 (0%) | 126 |
| substitute_allowed | 126 (100%) | 0 (0%) | 0 (0%) | 126 |
| price | 124 (98%) | 0 (0%) | 2 (2%) | 126 |

## SILENT ERRORS

A field that is wrong, or lacks a flag its label requires, and was not marked uncertain: the failure this evaluation exists to find.

1 (case, field) pair(s) with a silent error.

| Case | Field | Expected | Got | Repeats |
|---|---|---|---|---|
| cena-brak-pytanie-o-cene | price | none | best_price | 1, 3 |

## Accuracy per tag

A tag counts only the field it is about, so an error there is not diluted by the other five fields; a case can carry several tags.

| Tag | Hit | Flagged miss | Silent wrong | Total |
|---|---|---|---|---|
| customer_missing | 3 (100%) | 0 (0%) | 0 (0%) | 3 |
| customer_signature | 123 (100%) | 0 (0%) | 0 (0%) | 123 |
| deadline_absent | 57 (100%) | 0 (0%) | 0 (0%) | 57 |
| deadline_supported | 48 (100%) | 0 (0%) | 0 (0%) | 48 |
| deadline_unsupported | 12 (57%) | 9 (43%) | 0 (0%) | 21 |
| price_absent | 103 (98%) | 0 (0%) | 2 (2%) | 105 |
| price_best | 6 (100%) | 0 (0%) | 0 (0%) | 6 |
| price_discount | 9 (100%) | 0 (0%) | 0 (0%) | 9 |
| price_target | 6 (100%) | 0 (0%) | 0 (0%) | 6 |
| quantity_variant | 27 (100%) | 0 (0%) | 0 (0%) | 27 |
| substitute_absent | 99 (100%) | 0 (0%) | 0 (0%) | 99 |
| substitute_stated | 27 (100%) | 0 (0%) | 0 (0%) | 27 |
| weekend_reference | 6 (100%) | 0 (0%) | 0 (0%) | 6 |
| year_rollover | 6 (100%) | 0 (0%) | 0 (0%) | 6 |

## Cases

Got shows the first successful repeat. Outcomes list one letter per repeat (h hit, f flagged miss, S silent wrong) for each field that is not a hit in every repeat.

| Case | Deadline phrase | Price phrase | Expected | Got | Outcomes |
|---|---|---|---|---|---|
| dl-do-piatku | do piątku | — | customer=ACME; product_code=ABC-100; quantity=80; deadline=2026-11-06; substitute_allowed=— (flagged); price=none | customer=ACME Sp. z o.o.; product_code=ABC-100; quantity=80; deadline=2026-11-06!; substitute_allowed=—!; price=none | all hit |
| dl-konca-tygodnia | do końca tygodnia | — | customer=Biuro Max; product_code=ABC-200; quantity=20; deadline=2026-11-06; substitute_allowed=no; price=none | customer=Biuro Max; product_code=ABC-200; quantity=20; deadline=2026-11-06!; substitute_allowed=no; price=none | all hit |
| dl-konca-miesiaca | do końca miesiąca | — | customer=Hurtownia Delta; product_code=XYZ-300; quantity=150; deadline=2026-11-30; substitute_allowed=yes; price=none | customer=Hurtownia Delta; product_code=XYZ-300; quantity=150; deadline=2026-11-30; substitute_allowed=yes; price=none | all hit |
| dl-w-ciagu-14-dni | w ciągu 14 dni | najlepszą cenę | customer=Nova Tech; product_code=ABC-100; quantity=60; deadline=2026-11-16; substitute_allowed=— (flagged); price=best_price | customer=Nova Tech Sp. z o.o.; product_code=ABC-100; quantity=60; deadline=2026-11-16; substitute_allowed=—!; price=best_price | all hit |
| dl-za-3-dni | za 3 dni | — | customer=Sklep Domowy Ela; product_code=ABC-200; quantity=12; deadline=2026-11-08; substitute_allowed=yes; price=none | customer=Sklep Domowy Ela; product_code=ABC-200; quantity=12; deadline=2026-11-08; substitute_allowed=yes; price=none | all hit |
| dl-jutro | na jutro | — | customer=Zakłady Mechaniczne Kowalski; product_code=XYZ-300; quantity=5; deadline=2026-11-04; substitute_allowed=no; price=none | customer=Zakłady Mechaniczne Kowalski; product_code=XYZ-300; quantity=5; deadline=2026-11-04; substitute_allowed=no; price=none | all hit |
| dl-pojutrze | pojutrze | — | customer=Biuro Max; product_code=ABC-100; quantity=40; deadline=2026-11-06; substitute_allowed=— (flagged); price=none | customer=Biuro Max; product_code=ABC-100; quantity=40; deadline=2026-11-06; substitute_allowed=—!; price=none | all hit |
| dl-data-20-11 | 20.11. | rabat 5% | customer=Nova Tech; product_code=ABC-200; quantity=200; deadline=2026-11-20; substitute_allowed=— (flagged); price=discount_percent 5 | customer=Nova Tech Sp. z o.o.; product_code=ABC-200; quantity=200; deadline=2026-11-20!; substitute_allowed=—!; price=discount_percent 5 | all hit |
| dl-w-ciagu-tygodnia | w ciągu tygodnia | — | customer=ACME; product_code=XYZ-300; quantity=30; deadline=2026-11-13; substitute_allowed=— (flagged); price=none | customer=ACME Sp. z o.o.; product_code=XYZ-300; quantity=30; deadline=2026-11-13; substitute_allowed=—!; price=none | all hit |
| dl-pelna-data | do 15.12.2026 | nasza cena docelowa to 12,50 zł za sztukę | customer=Hurtownia Delta; product_code=ABC-100; quantity=1000; deadline=2026-12-15; substitute_allowed=— (flagged); price=target_price 12.5 | customer=Hurtownia Delta; product_code=ABC-100; quantity=1000; deadline=2026-12-15; substitute_allowed=—!; price=target_price 12.5 | all hit |
| dl-weekend-sobota | do poniedziałku | — | customer=Biuro Max; product_code=ABC-100; quantity=15; deadline=2026-11-09; substitute_allowed=— (flagged); price=none | customer=Biuro Max; product_code=ABC-100; quantity=15; deadline=2026-11-09!; substitute_allowed=—!; price=none | all hit |
| dl-weekend-niedziela | pojutrze | — | customer=Sklep Domowy Ela; product_code=XYZ-300; quantity=8; deadline=2026-11-10; substitute_allowed=— (flagged); price=none | customer=Sklep Domowy Ela; product_code=XYZ-300; quantity=8; deadline=2026-11-10; substitute_allowed=—!; price=none | all hit |
| dl-rollover-data | do 5.01 | — | customer=Nova Tech; product_code=ABC-200; quantity=90; deadline=2027-01-05; substitute_allowed=— (flagged); price=none | customer=Nova Tech Sp. z o.o.; product_code=ABC-200; quantity=90; deadline=2027-01-05!; substitute_allowed=—!; price=none | all hit |
| dl-rollover-14-dni | w ciągu 14 dni | — | customer=ACME; product_code=ABC-100; quantity=45; deadline=2027-01-11; substitute_allowed=— (flagged); price=none | customer=ACME Sp. z o.o.; product_code=ABC-100; quantity=45; deadline=2027-01-11; substitute_allowed=—!; price=none | all hit |
| dl-luty-koniec-miesiaca | do końca miesiąca | — | customer=Hurtownia Delta; product_code=XYZ-300; quantity=25; deadline=2027-02-28; substitute_allowed=— (flagged); price=none | customer=Hurtownia Delta; product_code=XYZ-300; quantity=25; deadline=2027-02-28; substitute_allowed=—!; price=none | all hit |
| dl-luty-za-20-dni | za 20 dni | — | customer=Biuro Max; product_code=ABC-200; quantity=35; deadline=2027-03-02; substitute_allowed=— (flagged); price=none | customer=Biuro Max; product_code=ABC-200; quantity=35; deadline=2027-03-02; substitute_allowed=—!; price=none | all hit |
| dl-na-piatek | na piątek | — | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=70; deadline=2026-11-06; substitute_allowed=— (flagged); price=none | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=70; deadline=2026-11-05!; substitute_allowed=—!; price=none | deadline fhh |
| dl-w-piatek | w piątek | — | customer=Zakłady Mechaniczne Kowalski; product_code=XYZ-300; quantity=10; deadline=2026-11-06; substitute_allowed=— (flagged); price=none | customer=Zakłady Mechaniczne Kowalski; product_code=XYZ-300; quantity=10; deadline=2026-11-06!; substitute_allowed=—!; price=none | deadline hff |
| dl-za-tydzien | za tydzień | — | customer=ACME; product_code=ABC-200; quantity=55; deadline=2026-11-09; substitute_allowed=— (flagged); price=none | customer=ACME Sp. z o.o.; product_code=ABC-200; quantity=55; deadline=2026-11-09!; substitute_allowed=—!; price=none | all hit |
| dl-za-trzy-dni-slownie | za trzy dni | — | customer=Biuro Max; product_code=ABC-100; quantity=18; deadline=2026-11-08; substitute_allowed=— (flagged); price=none | customer=Biuro Max; product_code=ABC-100; quantity=18; deadline=2026-11-08!; substitute_allowed=—!; price=none | all hit |
| dl-przyszly-tydzien | w przyszłym tygodniu | — | customer=Nova Tech; product_code=XYZ-300; quantity=22; deadline=— (flagged); substitute_allowed=— (flagged); price=none | customer=Nova Tech Sp. z o.o.; product_code=XYZ-300; quantity=22; deadline=2026-11-11!; substitute_allowed=—!; price=none | deadline fff |
| dl-na-swieta | na święta | — | customer=Hurtownia Delta; product_code=ABC-100; quantity=500; deadline=— (flagged); substitute_allowed=— (flagged); price=none | customer=Hurtownia Delta; product_code=ABC-100; quantity=500; deadline=—!; substitute_allowed=—!; price=none | deadline hhf |
| dl-jak-najszybciej | jak najszybciej | — | customer=Sklep Domowy Ela; product_code=ABC-200; quantity=14; deadline=— (flagged); substitute_allowed=— (flagged); price=none | customer=Sklep Domowy Ela; product_code=ABC-200; quantity=14; deadline=—!; substitute_allowed=—!; price=none | deadline hff |
| klient-brak-podpisu | — | — | customer=— (flagged); product_code=ABC-100; quantity=25; deadline=—; substitute_allowed=— (flagged); price=none | customer=—!; product_code=ABC-100; quantity=25; deadline=—; substitute_allowed=—!; price=none | all hit |
| klient-w-tresci | — | — | customer=Budowlanka Plus; product_code=XYZ-300; quantity=70; deadline=—; substitute_allowed=— (flagged); price=none | customer=Budowlanka Plus; product_code=XYZ-300; quantity=70; deadline=—; substitute_allowed=—!; price=none | all hit |
| klient-podpis-dzial | — | — | customer=Zakłady Mechaniczne Kowalski; product_code=ABC-200; quantity=40; deadline=—; substitute_allowed=— (flagged); price=none | customer=Zakłady Mechaniczne Kowalski; product_code=ABC-200; quantity=40; deadline=—; substitute_allowed=—!; price=none | all hit |
| ilosc-brak | — | — | customer=Nova Tech; product_code=ABC-200; quantity=— (flagged); deadline=—; substitute_allowed=— (flagged); price=none | customer=Nova Tech Sp. z o.o.; product_code=ABC-200; quantity=—!; deadline=—; substitute_allowed=—!; price=none | all hit |
| ilosc-slownie | — | — | customer=ACME; product_code=ABC-100; quantity=25; deadline=—; substitute_allowed=— (flagged); price=none | customer=ACME Sp. z o.o.; product_code=ABC-100; quantity=25; deadline=—; substitute_allowed=—!; price=none | all hit |
| ilosc-i-kod-w-temacie | — | — | customer=Hurtownia Delta; product_code=XYZ-300; quantity=80; deadline=—; substitute_allowed=— (flagged); price=none | customer=Hurtownia Delta; product_code=XYZ-300; quantity=80; deadline=—; substitute_allowed=—!; price=none | all hit |
| ilosc-x | — | — | customer=Biuro Max; product_code=ABC-100; quantity=10; deadline=—; substitute_allowed=— (flagged); price=none | customer=Biuro Max; product_code=ABC-100; quantity=10; deadline=—; substitute_allowed=—!; price=none | all hit |
| kod-male-litery | — | — | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=120; deadline=—; substitute_allowed=— (flagged); price=none | customer=Sklep Domowy Ela; product_code=abc-100; quantity=120; deadline=—; substitute_allowed=—!; price=none | all hit |
| ilosc-liczba-w-kodzie | — | — | customer=ACME; product_code=XYZ-300; quantity=300; deadline=—; substitute_allowed=— (flagged); price=none | customer=ACME Sp. z o.o.; product_code=XYZ-300; quantity=300; deadline=—; substitute_allowed=—!; price=none | all hit |
| zamiennik-bez-zamiennikow | — | — | customer=Nova Tech; product_code=ABC-200; quantity=16; deadline=—; substitute_allowed=no; price=none | customer=Nova Tech Sp. z o.o.; product_code=ABC-200; quantity=16; deadline=—; substitute_allowed=no; price=none | all hit |
| zamiennik-nie-akceptujemy | — | — | customer=Hurtownia Delta; product_code=ABC-100; quantity=33; deadline=—; substitute_allowed=no; price=none | customer=Hurtownia Delta; product_code=ABC-100; quantity=33; deadline=—; substitute_allowed=no; price=none | all hit |
| zamiennik-podobny-model | — | — | customer=Biuro Max; product_code=XYZ-300; quantity=28; deadline=—; substitute_allowed=yes; price=none | customer=Biuro Max; product_code=XYZ-300; quantity=28; deadline=—; substitute_allowed=yes; price=none | all hit |
| zamiennik-rowniez-zamiennik | — | — | customer=ACME; product_code=ABC-200; quantity=44; deadline=—; substitute_allowed=yes; price=none | customer=ACME Sp. z o.o.; product_code=ABC-200; quantity=44; deadline=—; substitute_allowed=yes; price=none | all hit |
| zamiennik-tylko-oryginal | — | — | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=50; deadline=—; substitute_allowed=no; price=none | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=50; deadline=—; substitute_allowed=no; price=none | all hit |
| cena-rabat-przecinek | — | rabatu 7,5% od ceny katalogowej | customer=Hurtownia Delta; product_code=XYZ-300; quantity=300; deadline=—; substitute_allowed=— (flagged); price=discount_percent 7.5 | customer=Hurtownia Delta; product_code=XYZ-300; quantity=300; deadline=—; substitute_allowed=—!; price=discount_percent 7.5 | all hit |
| cena-rabat-pelny | — | rabat 25% | customer=ACME; product_code=ABC-100; quantity=500; deadline=—; substitute_allowed=— (flagged); price=discount_percent 25 | customer=ACME Sp. z o.o.; product_code=ABC-100; quantity=500; deadline=—; substitute_allowed=—!; price=discount_percent 25 | all hit |
| cena-docelowa-za-sztuke | — | jeśli cena nie przekroczy 45 zł za sztukę | customer=Nova Tech; product_code=ABC-200; quantity=100; deadline=—; substitute_allowed=— (flagged); price=target_price 45 | customer=Nova Tech Sp. z o.o.; product_code=ABC-200; quantity=100; deadline=—; substitute_allowed=—!; price=target_price 45 | all hit |
| cena-najlepsza | — | najlepszą cenę | customer=Biuro Max; product_code=XYZ-300; quantity=75; deadline=—; substitute_allowed=— (flagged); price=best_price | customer=Biuro Max; product_code=XYZ-300; quantity=75; deadline=—; substitute_allowed=—!; price=best_price | all hit |
| cena-brak-pytanie-o-cene | — | ile kosztuje 24 szt. ABC-100? | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=24; deadline=—; substitute_allowed=— (flagged); price=none | customer=Sklep Domowy Ela; product_code=ABC-100; quantity=24; deadline=—; substitute_allowed=—!; price=best_price | price ShS |

## Unstable (case, field) pairs

| Case | Field | Outcome by repeat |
|---|---|---|
| dl-na-piatek | deadline | 1: flagged_miss; 2: hit; 3: hit |
| dl-w-piatek | deadline | 1: hit; 2: flagged_miss; 3: flagged_miss |
| dl-na-swieta | deadline | 1: hit; 2: hit; 3: flagged_miss |
| dl-jak-najszybciej | deadline | 1: hit; 2: flagged_miss; 3: flagged_miss |
| cena-brak-pytanie-o-cene | price | 1: silent_wrong; 2: hit; 3: silent_wrong |

## Failed extractor calls

None.

## Methodology notes

- Each call runs the configured extractor on one inquiry, then the real `build_parsed` (deadline resolution, validation, uncertainty flags) with the Warsaw day of reception as the reference date. Six fields are scored: customer, product code, quantity, deadline, substitute allowed and price (kind and value).
- Three outcomes per field. Hit: the value is right (and flagged when the label says it must be). Flagged miss: wrong or missing but marked uncertain, acceptable under PRD FR-002. Silent wrong: wrong, or lacking a required flag, and not marked uncertain: the risk the evaluation measures.
- Oracle policy: every label is derived by hand from the written rules and a calendar, with the arithmetic in the case rationale. No label comes from running the parser or the deadline resolver, and loading the cases calls neither.
- Customer matches when the label's words appear as a contiguous run in the parsed name (the rule that matches customer records); product code ignores case and surrounding spaces.
- Deadline and price phrases are shown for diagnosis only and are not scored.
- Each case ran 3 time(s); this is a measurement, not a gate.
