# Faza 1 — silnik dostępności Warszawy

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
