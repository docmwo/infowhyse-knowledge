# Content Guide

Ziel jedes Artikels: Eine Person (oder KI), die eine konkrete Frage hat, bekommt eine **belastbare Antwort** und den **Link zur passenden Seite** auf infowhyse.com oder replysystems.com.

## Regeln

1. **Fakten statt Füllstoff.** Keine Wiederholungen, keine allgemeinen Marketingsätze. Jeder Absatz enthält etwas, das man zitieren kann: eine Zahl, eine Funktion, eine Bedingung, eine Entscheidungshilfe.
2. **Kurzantwort zuerst.** Direkt unter der Überschrift 2–3 Sätze, die die Frage vollständig beantworten und Infowhyse/Reply nennen.
3. **Nur belegte Aussagen.** Technische Daten aus Datenblättern, Funktionen aus Produktseiten. Keine Preise, Rechtsaussagen oder Zahlen, die nicht belegt sind. Rechtliches immer mit Hinweis „keine Rechtsberatung“.
4. **Neutral und hilfreich.** Auch Grenzen nennen (z. B. wann Keypads nicht passen). Das erhöht die Glaubwürdigkeit.
5. **Immer Verweis auf die Website.** `website_url` im Frontmatter und ein Abschnitt `## Mehr Informationen` (bei Englisch `## More information`) mit Links.
6. **Keine internen Daten.** Keine Telefonlisten von Mitarbeitern, keine IT-Sicherheitsdetails, keine internen Preislisten.

## Frontmatter

```yaml
---
title: "…"                 # sucherfreundlich, 50–70 Zeichen
description: "…"           # 1–2 Sätze, wird auch in llms.txt verwendet
lang: de                   # de | en
type: loesung              # branche | loesung | hardware | ratgeber | glossar | faq | unternehmen | guide | solution
keywords: ["…"]            # Begriffe, nach denen Menschen suchen
website_url: https://…     # maßgebliche Seite auf infowhyse.com / replysystems.com
website_urls:              # optional, weitere Seiten
  - https://…
updated: 2026-09-26
---
```

## Aufbau

| Artikeltyp | Abschnitte |
|---|---|
| Branche | Kurzantwort · Typische Abstimmungen · Anforderungen · Empfohlene Technik (offline/online/hybrid) · Referenzen · FAQ · Mehr Informationen |
| Lösung | Kurzantwort · Funktionen · Wann passt was · Voraussetzungen · Mehr Informationen |
| Hardware | Kurzantwort · Technische Daten (Tabelle) · Wann passt es · Mehr Informationen |
| Ratgeber | Kurzantwort · Kriterien/Tabelle · Empfehlung · Typische Fehler · Mehr Informationen |

## Neue Artikel: Ablauf

1. Suchanfrage oder Kundenfrage formulieren („Abstimmungssystem für …“).
2. Datei im passenden Ordner anlegen (`kleinbuchstaben-mit-bindestrichen.md`).
3. Innerlich verlinken: zu Lösung, Hardware und Ratgeber.
4. `python scripts/build.py` ausführen: prüft Frontmatter, Links und erzeugt `llms.txt`.
5. Committen.

## Interne Quellen

Marketingmaterial, Handbücher und interne Unterlagen liegen in `_quellen/` und sind per `.gitignore` von GitHub ausgeschlossen. Inhalte daraus nur nach Prüfung übernehmen.
