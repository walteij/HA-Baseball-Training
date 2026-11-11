# VS Code Copilot Agent prompt: Home Assistant `honkbal_trainer`

Bouw een volledig werkende Home Assistant custom integration met domain `honkbal_trainer` voor een recreatief volwassen honkbalteam (beginners, 30-55 jaar) dat tweemaal per week 90 minuten in een kleine tot middelgrote sporthal traint.

## Niet onderhandelbare uitgangspunten
- Gebruik de bestaande `calisthenics_tracker` integratie in deze workspace uitsluitend als structurele referentie.
- Lever productieklare code, geen skeletons, TODO's, placeholders of gefingeerde YouTube-URL's.
- Gebruik `__init__.py`, niet `init.py`.
- Gebruik config entries, config flow, options flow, coordinator, storage, calendar, sensors, selects, buttons en services volgens actuele Home Assistant patronen.
- Alle gebruikersgerichte teksten zijn Nederlands via `translations/nl.json`; houd `strings.json` als canonieke brontekst consistent.
- Voeg typing, dataclasses/TypedDict en pytest unit tests toe.
- Laad de meegeleverde JSON-bestanden uit `data/`; valideer ze bij startup tegen `schema.json`.
- De catalogus bevat 135 gededupliceerde drills. Verander bestaande drill-ID's nooit.

## Bestandsstructuur
```text
custom_components/honkbal_trainer/
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── coordinator.py
├── models.py
├── storage.py
├── calendar.py
├── ical.py
├── sensor.py
├── select.py
├── button.py
├── services.yaml
├── strings.json
├── translations/nl.json
└── data/
    ├── warmup.json
    ├── categories.json
    ├── schema.json
    ├── catalog_summary.json
    ├── drills_batting.json
    ├── drills_pitching.json
    ├── drills_catching.json
    ├── drills_infield.json
    ├── drills_outfield.json
    ├── drills_throwing.json
    ├── drills_baserunning.json
    ├── drills_situational.json
    ├── drills_conditioning.json
    ├── blocks_foundation.json
    ├── blocks_closing.json
    └── programs.json
```

## Sessie-indeling
- warming-up: 20 minuten, vast uit `warmup.json`
- foundation block: 15 minuten gooien plus fielden
- theme_1: 20 minuten
- theme_2: 20 minuten
- closing: 15 minuten situational game of mini-scrimmage

## Achtweeks programma
1. batting + infield
2. pitching + catching
3. batting + baserunning
4. infield/outfield + throwing
5. pitching + catching
6. batting + situational
7. infield + catching
8. batting + pitching
Training 1 en 2 van dezelfde week gebruiken verschillende drills.

## Harde selectiefilters, vóór scoring
Sluit een drill uit wanneer vereist materiaal ontbreekt, de zaal te klein is, netten ontbreken bij batting, hard balls niet zijn toegestaan, de maximale werpafstand wordt overschreden, de vloer ongeschikt is voor sliding, de minimum-repeat-gap nog actief is, catcheruitrusting ontbreekt voor blocking, of de combinatie te hoge throwing load veroorzaakt.

## Scoring
- +30 indoor_friendly
- +25 primary theme
- +15 secondary theme
- +20 passende ruimte en materialen
- +10 beginner
- +10 suitable_for_beginner_adults
- -3 per eerder gebruik in het seizoen
- random tie-breaker 0..5 met injecteerbare RNG voor tests
Voorkom twee high-intensity throwing drills in één sessie en voorkom batting zonder veilige lane/net.

## Entiteiten
Sensoren: volgende_training, huidig_thema, huidige_week, programma_voortgang, sessie_status, warming_up, basis_drill, drill_1, drill_2, afsluiting, totaal_trainingen, drill_catalogus_count.
Selects: thema_override en focus.
Buttons: start_training, voltooi_training, volgende_drill, genereer_planning.
Calendar: `calendar.honkbal_training` met volledige sessie in description.

## Services
- `honkbal_trainer.genereer_seizoen`
- `honkbal_trainer.voeg_drill_toe`
- `honkbal_trainer.verwijder_drill`
- `honkbal_trainer.wissel_drill`
- `honkbal_trainer.exporteer_sessie`
- `honkbal_trainer.exporteer_ical`
Valideer service-input. Persisteer wijzigingen en gebruik een storage-versie met migratiepad.

## Config flow
Teamnaam, trainingsdagen, trainingstijd, sessieduur, warming-upduur, startdatum en aantal weken. Options: beschikbare materialen, zaalgrootte, vloer, hard balls toegestaan, maximale werpafstand, aantal hitting lanes/netten, focusoverride en voorkeur YouTube-taal.

## iCal
Implementeer naast de HA calendar entity een RFC 5545 `.ics` export via service en een geauthenticeerde HTTP view. Geen publieke agenda-token zonder revocation. Escape tekst correct en gebruik stabiele UID's.

## WhatsApp-export
Genereer platte Unicode-tekst met datum, thema, blokduur, drillnaam, korte beschrijving, eerste twee coach-cues en de YouTube-URL. Geen HTML-ankers.

## Tests
Test minimaal: deduplicatie van ID's, JSON-schema-validatie, materiaalfilters, ruimtefilters, repeat gap 14 dagen, verschillende drills binnen één week, reproducible RNG, throwing-load guard, opslag/migratie, calendar event generation, iCal escaping en WhatsApp-export.

## Uitvoering
1. Inspecteer eerst `calisthenics_tracker`.
2. Maak alle bestanden.
3. Kopieer de meegeleverde catalogus-JSON naar `data/` zonder ID's te wijzigen.
4. Draai tests, ruff/formatting en Home Assistant-validatie die lokaal beschikbaar is.
5. Herstel alle fouten.
6. Rapporteer exact welke bestanden zijn gemaakt, welke tests zijn uitgevoerd en welke beperkingen nog bestaan.
