# Faza 2 — gotowość MVP do regularnego użycia

## Cel

Domknąć MVP zoniq po zbudowaniu silnika: wynik symulacji ma dać się
ponownie otworzyć i udostępnić, mapa ma oferować czytelne tryby prezentacji
oraz eksport PNG, a projekt ma mieć automatyczną weryfikację obu aplikacji
i powtarzalne uruchomienie lokalne.

## Wymagania i kryteria akceptacji

| Wymaganie | Status | Dowód / uwaga |
| --- | --- | --- |
| Trwałe wyniki symulacji, odporne na restart API | DONE | Atomowy artefakt JSON zawiera parametry, odpowiedź i GeoJSON; test handlerów odtwarza wynik po wyczyszczeniu pamięci. |
| Udostępnialny scenariusz | DONE | URL przechowuje identyfikator wyniku i parametry; klient odtwarza je i pobiera trwały artefakt. |
| Eksport mapy PNG | DONE | Canvas MapLibre z podpisem scenariusza pobierany przez przycisk „Eksport PNG”; kontrola typów przechodzi. |
| Czytelne tryby mapy | DONE | Przełączniki Zasięg/Czas/Środki zmieniają warstwy i legendę; dominujący środek jest opisany zgodnie z metryką. |
| Gotowość uruchomieniowa | BLOCKED | Compose i Dockerfile są zwalidowane; Docker Desktop działa, lecz pełny build jest trzykrotnie przerywany przez limit 30 s podczas pobierania warstw naukowych. |
| CI dla obu aplikacji | DONE | Workflow uruchamia `pytest apps/api/tests -q`, kontrolę typów i build webu. |
| Testy jednostkowe, integracyjne i scenariusz użytkownika | BLOCKED | 12 testów API przechodzi (w tym restart przez handler); TypeScript przechodzi. Pełny build webu i start Compose wymagają środowiska bez 30-sekundowego limitu polecenia. |

## Znane problemy / blokady

- Brak wybranego hostingu nie blokuje przygotowania kontenerów ani lokalnej
  weryfikacji; faktyczne wdrożenie pozostaje świadomą decyzją użytkownika.
- Twardy limit 30 s pojedynczego polecenia terminala przerywa pełny build
  Compose w czasie pobierania SciPy/OSMnx. Docker Desktop 27.5.1 działa,
  a YAML i podstawowa warstwa obrazu API są zweryfikowane.

## Dokładny następny krok

Minimalne działanie odblokowujące: uruchomić w zwykłym lokalnym terminalu
bez 30-sekundowego limitu `docker compose up --build`, poczekać na zdrowy
serwis API i otworzyć `http://localhost:3000`. Następnie wrócić do tego
wątku; dokończę kontrolę `/health`, strony głównej i oznaczę fazę jako
COMPLETE.

---

# Archiwum — Faza 1 — silnik dostępności Warszawy

## Cel

Zbudować zweryfikowany pionowy wycinek: od punktu startowego, przez
dane GTFS i sieć pieszą OSM, do mapy końcowego zasięgu dla Warszawy.

## Wymagania i kryteria akceptacji

| Wymaganie | Status | Dowód / uwaga |
| --- | --- | --- |
| Lokalne, wersjonowane dane GTFS z kalendarzami i wyjątkami | DONE | `data/processed/ztm.sqlite`; testy `test_gtfs_store.py`. |
| Graf pieszy OSM dla całej Warszawy | DONE | 16/16 GraphML w `data/processed/walking/tiles`; testy Kabatów i Białołęki ręcznie wykonane. |
| Dojście piesze do przystanku i od przystanku do celu | DONE | `walking_access.py`, `walking_surface_from_stops`; test na rzeczywistym kaflu Kabatów. |
| Routing rozkładowy do dwóch przesiadek wraz z pieszą zmianą platformy | DONE | `find_reachable_stops` i `/api/journeys` mają 2 rundy; test trzech kursów i dwóch zmian peronu przechodzi. |
| Uśrednianie startów co minutę | DONE | `_aggregate_departure_window`; `test_simulation.py`. |
| Mapa zawiera powierzchnię końcowego dojścia, nie tylko przystanki | DONE | commit `56d1b57`, próbki Dijkstry jako `point_kind=surface`. |
| Ciężka symulacja nie blokuje żądania HTTP | DONE | kolejka `ThreadPoolExecutor`, polling UI, test `test_simulation_api.py`. |
| Testy jednostkowe i integracyjne | DONE | `apps/api`: 12 testów przechodzi; `apps/web`: kontrola typów i produkcyjny build przechodzą. |
| Rzeczywisty scenariusz Kabaty, sobota 17:00 | DONE | Pełny worker na GTFS+OSM: limit 15 min — 35 przystanków, 2 788 punktów; limit 60 min — pasma 15/30/45/60: 35/374/1091/1878, 6 118 punktów. |

## Znane problemy / blokady

- Lokalny sandbox nie pozwala nasłuchiwać na porcie, więc test HTTP wykonujemy przez handlery FastAPI w jednym procesie. Nie blokuje to działania aplikacji poza sandboxem.
- Nie ma znanych krytycznych błędów ani blokad fazy 1.

## Dokładny następny krok

Faza 1 jest COMPLETE po końcowej kontroli regresji: testach API, testach
jednostkowych, kontroli typów i produkcyjnym buildzie frontendu. Następna
faza może obejmować wdrożenie, obserwowalność i walidację wizualną na
docelowym hostingu.
