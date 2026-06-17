# Projectafspraken TGN

## Deploy

Voor dit project deployen we altijd via de bekende methode vanuit de werkmap:

```bash
cd C:\Users\thoma\.codex\worktrees\bf3a\top_groep_nederland
git add <files>
git commit -m "<message>"
git push origin HEAD:main
```

Elke push naar `main` start de GitHub Actions deploy naar het TGN dashboard.

Gebruik geen alternatieve deploy-route tenzij Thomas dat expliciet vraagt.

## Bouwvolgorde

Werk stap voor stap op basis van de blauwdruk. Geen grote refactors zonder duidelijke reden; eerst kleine, testbare bouwstappen.

## Afgeronde fase: payroll-controlelaag

Status: afgerond op 17 juni 2026.

Deze fase bevat de basis die Excel als controle- en voorbereidingslaag vervangt, zonder Easyflex te vervangen:

- 13 loonperiodes per jaar met 4 weken per periode.
- Medewerkerinrichting op de relatiekaart.
- Week-invoer, weekresultaten en periode-afrekening per medewerker.
- Lopende saldi op medewerkerkaart en als controleoverzicht.
- Payroll-uitzonderingen per periode met blokkades en aandachtspunten.
- Accorderen wordt geblokkeerd zolang er blokkerende payroll-uitzonderingen zijn.
- Auditspoor legt akkoord of geblokkeerde akkoordpoging vast met controlesamenvatting.

Volgende fases mogen hierop voortbouwen met nieuwe prompts, maar horen deze controlelaag niet groot te refactoren zonder expliciete opdracht.
