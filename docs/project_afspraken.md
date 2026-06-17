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
