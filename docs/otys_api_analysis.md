# OTYS OWS API analyse

Laatste analyse: 2026-06-02.

## Bewezen leesbaar via getListEx

### RelationService

- `uid`
- `relation`
- `status`
- `email`
- `phoneNumberMain`
- `website`
- `city`
- `entryDateTime`

Niet leesbaar via deze list-call: `address`, `postalCode`, `country`, `updateDateTime`.

### CandidateService

- `uid`
- `status`
- `Person.firstName`
- `Person.lastName`
- `Person.emailPrimary`
- `entryDateTime`

Niet leesbaar via deze list-call: telefoon, adresvelden, geboortedatum, `updateDateTime`.

### RelationContactService

- `uid`
- `relation`
- `Person.firstName`
- `Person.lastName`
- `Person.emailPrimary`

Niet leesbaar via deze list-call: `relationUid`, `status`, telefoon en plaats.

### VacancyService

- `uid`
- `title`
- `referenceNr`
- `status`
- `relation`
- `location`
- `entryDateTime`

Niet leesbaar via deze list-call: `owner`, `relationUid`, `updateDateTime`.

## Datamodel

- Dashboardgebruik:
  - `relations` voor kandidaten en opdrachtgevers.
  - `vacancies` voor vacatures.
- OTYS-staging:
  - `otys_organizations`
  - `otys_candidates`
  - `otys_contacts`
  - `otys_vacancies`
  - `otys_raw_records`

Alle bekende OTYS-records bewaren hun `uid` als vaste externe sleutel en de volledige payload in `raw_data`.

## Vervolg

1. Contactpersonen syncen met de bewezen list-velden.
2. Detailcalls per entiteit testen om abstracte velden alsnog op te halen.
3. Een `otys_outbox` maken voor gecontroleerd terugschrijven.
4. Cronjobs pas toevoegen nadat pull-sync en detail-sync stabiel zijn.
