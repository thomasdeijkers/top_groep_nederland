MODULES = [
    {"name": "Klanten", "count": 18, "status": "Actief"},
    {"name": "Opdrachtgevers", "count": 7, "status": "Nieuw"},
    {"name": "Loon berekenen", "count": 3, "status": "Concept"},
    {"name": "Gewerkte uren", "count": 42, "status": "Open"},
    {"name": "Sollicitanten", "count": 5, "status": "Review"},
]

REVIEW_ITEMS = [
    {"title": "Urenstaat week 22", "meta": "Gewerkte uren", "priority": "Vandaag"},
    {"title": "Nieuwe medewerker", "meta": "Sollicitanten", "priority": "Deze week"},
    {"title": "Opdrachtgever gegevens", "meta": "Opdrachtgevers", "priority": "Open"},
]

ACTIVITY_ITEMS = [
    {"title": "Document toegevoegd", "meta": "Nieuwe documenten"},
    {"title": "Urenstaat klaargezet", "meta": "Gewerkte uren"},
    {"title": "Klantprofiel bijgewerkt", "meta": "Klanten"},
]

SERVER_METRICS = [
    {"label": "API status", "value": "OK", "meta": "FastAPI actief", "level": 100},
    {"label": "Database", "value": "Later", "meta": "Koppeling via /api/stats", "level": 35},
    {"label": "Dashboard", "value": "8010", "meta": "lokale ontwikkelpoort", "level": 80},
    {"label": "Mail sync", "value": "Uit", "meta": "tickets later", "level": 8},
]

SCHEDULED_JOBS = [
    {"job": "Mail ophalen", "category": "Tickets", "schedule": "handmatig", "status": "Gepland"},
    {"job": "Urenstaten controleren", "category": "Uren", "schedule": "dagelijks", "status": "Placeholder"},
    {"job": "Documenten indexeren", "category": "Documenten", "schedule": "elk uur", "status": "Placeholder"},
]

TICKET_QUEUES = [
    {"name": "Nieuw", "count": 0, "meta": "Binnengekomen mails"},
    {"name": "In behandeling", "count": 0, "meta": "Toegewezen tickets"},
    {"name": "Wacht op klant", "count": 0, "meta": "Open opvolging"},
    {"name": "Afgerond", "count": 0, "meta": "Deze week"},
]

DIRECTORY_RESULTS = [
    {"type": "Klant", "name": "Bouwbedrijf Van Dijk", "contact": "info@vandijkbouw.nl", "city": "Utrecht", "status": "Concept"},
    {"type": "Opdrachtgever", "name": "Projectgroep Rijnkade", "contact": "planning@rijnkade.nl", "city": "Arnhem", "status": "Nieuw"},
    {"type": "Klant", "name": "Aannemersbedrijf Noord", "contact": "administratie@abnoord.nl", "city": "Zwolle", "status": "Actief"},
]

IMPORT_STEPS = [
    {"label": "OTYS export ontvangen", "status": "Wacht op bestand"},
    {"label": "Kolommen controleren", "status": "Nog niet gestart"},
    {"label": "Klanten importeren", "status": "Nog niet gestart"},
    {"label": "Opdrachtgevers importeren", "status": "Nog niet gestart"},
]

WHATSAPP_INBOX = []

CANDIDATES = [
    {
        "initials": "BB",
        "name": "Berry Bottinga",
        "email": "bgbottinga@gmail.com",
        "phone": "0610534464",
        "city": "Leidschendam",
        "status": "Via website",
        "date": "23-04-2026",
        "criteria": ["Zuid-Holland", "Timmerwerk Renovatie", "0-1 jaar", "Geen VCA"],
    },
    {
        "initials": "AM",
        "name": "Arnold Meijer",
        "email": "arnold-1969@outlook.com",
        "phone": "0628167972",
        "city": "Den Haag",
        "status": "Nog beoordelen",
        "date": "19-04-2026",
        "criteria": ["Zuid-Holland", "Timmerman", "VCA verlopen"],
    },
    {
        "initials": "SV",
        "name": "Sjaak Vermeer",
        "email": "jm.metselwerken@kpnmail.nl",
        "phone": "+31651453900",
        "city": "Utrecht",
        "status": "Nog binnenhalen",
        "date": "14-04-2026",
        "criteria": ["Metselwerk", "ZZP", "Uurtarief te bespreken"],
    },
]

CANDIDATE_PROFILE = {
    "name": "Berry Bottinga",
    "source": "Via website",
    "owner": "Top Groep Nederland",
    "birth_date": "1 augustus 1963",
    "age": "62",
    "motivation": "Wil graag timmerman werkzaamheden verrichten en is beschikbaar voor renovatieklussen.",
    "skills": ["Timmerwerk Renovatie", "Interieur", "EHBO"],
}

VACANCIES = [
    {
        "title": "Timmerlieden voor verduurzaming en renovatie",
        "reference_number": "ACT00344",
        "status": "Lopend",
        "owner": "Top Groep Nederland",
        "relation_name": "Top Groep Nederland",
        "location": "Nieuwegein",
        "publication_status": "concept",
        "applicant_count": 1,
        "website_enabled": False,
        "indeed_enabled": False,
    },
    {
        "title": "Restauratietimmerman Monumentaal Werk - Amsterdam",
        "reference_number": "ACT00343",
        "status": "Lopend",
        "owner": "Top Groep Nederland",
        "relation_name": "Restauratieproject",
        "location": "Amsterdam",
        "publication_status": "concept",
        "applicant_count": 1,
        "website_enabled": False,
        "indeed_enabled": False,
    },
    {
        "title": "Ervaren renovatie timmerman",
        "reference_number": "AC000118",
        "status": "Lopend",
        "owner": "Top Groep Nederland",
        "relation_name": "Bouw opdrachtgever",
        "location": "Rotterdam",
        "publication_status": "website klaar",
        "applicant_count": 1,
        "website_enabled": True,
        "indeed_enabled": False,
    },
]
