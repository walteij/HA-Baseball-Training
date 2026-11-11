# Honkbal Trainer catalogus

Deze set bevat 135 gededupliceerde drills voor volwassen beginners in een sporthal.

Verdeling: {"batting": 22, "pitching": 16, "catching": 15, "infield": 16, "outfield": 14, "throwing": 10, "baserunning": 16, "situational": 14, "conditioning": 12}

YouTube: elke drill bevat een werkende, op 2026-11-11 gecontroleerde URL. Niet iedere drill heeft een unieke video; een goede fundamentals-video wordt bewust hergebruikt wanneer deze meerdere drills uitlegt. Het veld `match_quality` maakt dat expliciet.

Bronpagina's zijn bewust leeg gelaten wanneer de tekstextractie geen betrouwbare paginakoppeling toeliet. Geen paginanummers verzinnen, want dat is administratieve fantasy met JSON-syntax.

## Home Assistant-integratie

De custom integration staat in `custom_components/honkbal_trainer`. Kopieer deze map naar
`<config>/custom_components/honkbal_trainer`, herstart Home Assistant en voeg **Honkbal
Trainer** toe via **Instellingen → Apparaten en diensten → Integratie toevoegen**.

De config flow vraagt het team, twee trainingsdagen en de sessie-instellingen. Stel
vervolgens in de opties het beschikbare materiaal, de zaal en de veiligheidslimieten in.
Als harde ballen niet zijn toegestaan, moeten safety-/wiffleballen beschikbaar zijn voor
drills die ballen vereisen.
De integratie bouwt de planning lokaal op uit de meegeleverde, schema-gevalideerde
catalogus en bewaart de voortgang in Home Assistant storage.
De integratie gebruikt de ingestelde Home Assistant-taal voor drill- en warming-upteksten.
De Nederlandse vertalingen zijn meegeleverd; na het wijzigen van de HA-taal moet de
integratie opnieuw worden geladen om de teksten bij te werken.

De iCalendar-feed is alleen beschikbaar voor ingelogde Home Assistant-gebruikers op
`/api/honkbal_trainer/<config-entry-id>/calendar.ics`. De service `exporteer_ical` geeft
dezelfde agenda als service-response terug; `exporteer_sessie` geeft platte WhatsApp-tekst.

De tests zijn uit te voeren met `python -m pytest -q`; lint en opmaak met
`python -m ruff check custom_components tests` en `python -m ruff format --check custom_components tests`.
