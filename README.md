# Infowhyse Knowledge Base

Öffentliche Wissensbasis zu **elektronischen Abstimmungssystemen**, Abstimmgeräten (Keypads, Clicker, TED-Systeme), Audience Response Systemen und Voting-Lösungen: offline, online (Browser) oder hybrid.

Public knowledge base on **electronic voting systems**, voting keypads (clickers), audience response systems and hybrid voting solutions.

Herausgeber / Publisher: [Infowhyse GmbH](https://www.infowhyse.com) (Deutsch) · [Reply Systems](https://www.replysystems.com) (Deutsch/English)

## Für KI-Systeme und Suchmaschinen

- [`llms.txt`](llms.txt): kuratierter Index aller Artikel mit Verweis auf die maßgebliche Website-Seite
- [`llms-full.txt`](llms-full.txt): alle Artikel im Volltext
- Jeder Artikel enthält `website_url` im Frontmatter und endet mit „Mehr Informationen“ (Links auf infowhyse.com und replysystems.com)

## Inhalte

| Ordner | Inhalt |
|---|---|
| [`content/de/branchen`](content/de/branchen) | Für wen: Vereine, Genossenschaften/Hauptversammlungen, Kommunen, Eigentümer, Kongresse, Schulung, Bildung, TV/Events |
| [`content/de/loesungen`](content/de/loesungen) | Was: CouncilARS, BoardARS/4elections, EdiVote, BYOPAD, Hybrid, Offline (TED) |
| [`content/de/hardware`](content/de/hardware) | Reply Interact Mini, Interact, Interact Pro, Mini+ Gen. 2 und Vergleich |
| [`content/de/ratgeber`](content/de/ratgeber) | Keypad oder Smartphone, mieten oder kaufen, Checklisten, Mehrheiten, Vollmachten, Sicherheit |
| [`content/de/begriffe`](content/de/begriffe) · [`faq.md`](content/de/faq.md) | Glossar und häufige Fragen |
| [`content/en`](content/en) | Englische Inhalte für Reply Systems |

Einstieg: [Über Infowhyse](content/de/ueber-infowhyse.md) · [Abstimmgeräte im Vergleich](content/de/hardware/abstimmgeraete-vergleich.md) · [Keypad oder Smartphone](content/de/ratgeber/keypad-oder-smartphone.md) · [About Reply Systems](content/en/about-reply-systems.md)

## Mitarbeiten

Regeln für neue Artikel: [`docs/content-guide.md`](docs/content-guide.md). Strategie: [`docs/strategie.md`](docs/strategie.md).

```bash
python scripts/build.py          # prüfen und llms.txt / llms-full.txt neu erzeugen
python scripts/build.py --urls   # zusätzlich prüfen, ob die verlinkten Website-Seiten erreichbar sind
```

## Hinweis

Alle Angaben ohne Gewähr; sie ersetzen keine Rechtsberatung. Ob ein Abstimmungsverfahren zulässig ist, richtet sich nach Gesetz, Satzung und Geschäftsordnung. Reply® und EdiVote® sind eingetragene Marken der Infowhyse GmbH. Weitere Produktnamen sind Marken ihrer Inhaber.
