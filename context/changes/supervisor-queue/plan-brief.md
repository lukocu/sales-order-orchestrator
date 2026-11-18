# Kolejka przełożonego — skrót planu

> Pełny plan: [plan.md](plan.md)

## What & Why

S-15: przełożony rozstrzyga przekazane wyjątki w kolejce „Do akceptacji” z licznikiem w nawigacji. Po otwarciu sprawy widzi najpierw reguły wymagające uwagi, ocenianą ofertę i decyzje z komentarzem. Oczekująca sprawa pozostaje niezmieniona do decyzji.

## Starting Point

Istnieją decyzje przełożonego, historia, obowiązkowy komentarz, kontrola własnego zgłoszenia i filtr oczekujących w skrzynce. Brakuje osobnej kolejki, licznika w nawigacji i układu nastawionego na decyzję; zwykłe endpointy nadal pozwalają ponawiać analizę oczekującej sprawy.

## Desired End State

Przełożony otwiera `/approvals`, wybiera najdłużej oczekującą sprawę i podejmuje decyzję bez przechodzenia przez kroki handlowca. Po decyzji widzi jej wynik, a licznik maleje. Handlowiec może poprawić sprawę po odrzuceniu; nieaktualne zgłoszenie można odrzucić, ale nie zatwierdzić.

## Key Decisions Made

| Obszar | Wybór | Dlaczego |
| --- | --- | --- |
| Członkostwo | Tylko surowe `awaiting_supervisor`, także nieaktualne | Nie gubi przekazanych spraw. |
| Kolejność | Najstarsze przekazanie pierwsze | Zapobiega zaleganiu starszych zgłoszeń. |
| Lista | Klient / nadawca, temat, czas i reguły wymagające decyzji | Ułatwia wybór sprawy. |
| Odświeżanie | Wejście, powrót do karty, decyzja i ręcznie | Aktualizuje pracę bez pollingu. |
| Poprawki | Zablokowane dla obu ról do odrzucenia | Stabilny przedmiot oceny. |
| Nieaktualność | Dopuszczalne odrzucenie z historycznym snapshotem | Sprawa może wrócić do poprawek. |
| Kontekst | Rozwijany pod regułami, ofertą i decyzją | Główna akcja pozostaje blisko początku. |
| Oceniana oferta | Rzeczywisty szkic i jego polityka | Uwzględnia poprawki handlowca względem rekomendacji. |
| Po decyzji | Pozostaje wynik, bez automatycznego przejścia | Użytkownik widzi skutek i komentarz. |
| Ekran startowy | Skrzynka; kolejka w nawigacji przełożonego | Zachowuje jego pozostałe zadania. |

## Scope

**W zakresie:**

- Blokady wszystkich mutacji i spóźnionych zapisów, bezpieczne odrzucenie nieaktualnej sprawy.
- API listy i oceny, trasy kolejki, wspólny licznik, ekran decyzji i kontekst tylko do odczytu.
- Blokady również pod zwykłym adresem zapytania, PL/EN, dostępność i kitchen sink.

**Poza zakresem:** polling, powiadomienia, masowe decyzje, przydzielanie spraw, nowe statusy, zamrożona polityka, wycofanie przez handlowca, pełne URL kroków z S-17 i tłumaczenia backendu z S-16.

## Architecture / Approach

Stan kolejki wynika z istniejącego szkicu i historii decyzji. Lekki odczyt API zasila wspólny provider listy i nawigacji; szczegół oceny korzysta z istniejącego endpointu decyzji. Kontrola pod blokadą analizy oraz wersja historii przenoszona przez etapy chronią przed nadpisaniem zgłoszenia lub decyzji przez wcześniejsze przetwarzanie. Blokady nie obejmują czasu wywołań modelu.

## Phases at a Glance

| Faza | Rezultat | Główne ryzyko |
| --- | --- | --- |
| 1. Blokada zmian i bezpieczne decyzje | Obie role nie zmieniają oczekujących danych; stare wyniki nie nadpisują decyzji | Pominięty zapis lub usunięcie wyniku w łańcuchu etapów. |
| 2. API kolejki i danych oceny | Kolejność przekazania, przyczyny, licznik i odporny odczyt szczegółu | Nieaktualne dane lub polityka inna dla edytowanej oferty. |
| 3. Kolejka, licznik i ekran decyzji | Pełny przepływ, odświeżanie, wynik, blokady UI i weryfikacja | Rozjazd licznika, wyścigi odczytów i utrata fokusu. |

**Warunki wejścia:** S-11 i S-14 są zakończone; do testów backendu potrzebny PostgreSQL.
**Rozmiar orientacyjny:** średnia zmiana w trzech fazach; najwięcej pracy wymaga ochrona zapisów wszystkich etapów.

## Open Risks & Assumptions

- Odrzucenie musi działać także przy niedostępnych danych starego zgłoszenia, z jawnym brakiem szczegółów w historii.
- Konfiguracja polityki nadal obowiązuje z chwili decyzji; nie zmieniamy tej reguły.
- Bezczynna widoczna karta może mieć stary licznik do odświeżenia; brak pollingu jest uzgodniony.

## Success Criteria (Summary)

- Przełożony podejmuje decyzję z kolejki, widząc reguły i faktyczną ofertę; wynik pozostaje na ekranie.
- Nikt nie zmienia oczekującej sprawy zwykłymi endpointami; odrzucenie przywraca poprawki, także dla nieaktualnego zgłoszenia.
- Licznik i lista są spójne; przepływ działa klawiaturą, w PL/EN i obu motywach, na desktopie i 375 px.
