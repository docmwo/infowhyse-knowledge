# Strategie: KI-Sichtbarkeit für Abstimmungslösungen

## Ziel

Wer für eine Veranstaltung nach einer Abstimmungslösung sucht (nicht nur nach „Clicker“), soll bei ChatGPT, Perplexity, Google AI Overviews & Co. auf infowhyse.com und replysystems.com stoßen oder dort mindestens genannt werden.

## Was KI-Systeme aus dem Repo nutzen

KI-Systeme beantworten Fragen aus (a) Trainingsdaten, (b) Websuche in Echtzeit. Ein GitHub-Repo wirkt vor allem indirekt. Deshalb gelten drei Prinzipien:

1. **Die Antworten müssen auf den Websites selbst stehen.** Die Artikel im Repo sind die Vorlage; die wichtigsten (Branchen, Ratgeber, Hardwarevergleich, FAQ) sollten als Seiten auf infowhyse.com bzw. replysystems.com erscheinen. Das Repo verweist dann auf diese Seiten.
2. **Suchabsichten statt Begriffe.** Artikel beantworten Fragen wie „Abstimmungssystem für Kreistag“, „Keypad oder Smartphone“, „Abstimmgeräte mieten“.
3. **Konsistente Fakten überall.** Gleiche Produktnamen, Zahlen, Kontaktdaten auf beiden Websites, im Repo und in Profilen (Google Business, LinkedIn, Verzeichnisse).

## Empfohlene Maßnahmen außerhalb des Repos

| Maßnahme | Nutzen |
|---|---|
| `llms.txt` (aus diesem Repo erzeugt) auf beiden Websites unter `/llms.txt` bereitstellen | direkter Index für KI-Crawler; Wirkung bei einzelnen Systemen noch nicht belegt, Aufwand gering |
| Neue Seiten auf infowhyse.com für die Branchen (Kommunen, Vereine, Hauptversammlungen, Kongresse, Bildung) mit Kurzantwort, Tabelle, FAQ | wichtigste Grundlage, weil KI-Systeme Websites zitieren |
| Strukturierte Daten (schema.org: Organization, Product, FAQPage) auf den Seiten | erleichtert maschinelles Verstehen |
| Vergleichs- und Entscheidungsseiten („Keypad oder Smartphone“, „mieten oder kaufen“) | werden in KI-Antworten gern übernommen |
| Referenzen und Fallbeispiele (auch als Zitat/Nummern) veröffentlichen | Glaubwürdigkeit |
| Nennung in Fachverzeichnissen, Verbandsseiten, Vergleichsportalen | KI-Systeme gewichten Erwähnungen Dritter |
| Auf beiden Websites konsistente Kontaktdaten | Vermeidung von Widersprüchen |

## Themenlandkarte (Branchen × Technik)

| Branche | Offline (Keypads) | Online (Browser) | Hybrid |
|---|---|---|---|
| Kommunen | CouncilARS + Interact Mini | BYOPAD | ja |
| Vereine, Verbände | BoardARS/4elections + Interact / Pro | BYOPAD | ja |
| Hauptversammlung, Genossenschaft | 4elections + Interact Pro | eingeschränkt | ja |
| Eigentümerversammlung | OwnARS/Interact | BYOPAD | ja |
| Kongress, Pharma | EdiVote + Interact | BYOPAD | ja |
| Schulung, Coaching | EdiVote + Interact Mini / Interact | BYOPAD | ja |
| Bildung | EdiVote + Interact Mini | BYOPAD | ja |
| TV, Events | Mini+ / Interact + EdiVote | BYOPAD | ja |

## Nächste Inhalte (Backlog)

- Weitere Branchen mit belegbarer Nachfrage: Gewerkschaften und Parteien (Delegiertenversammlungen), Kirchengemeinden und Stiftungen, Betriebsräte und Mitarbeiterversammlungen, Aufsichtsräte und Beiräte
- Kundenfälle mit Zitat und Zahlen (Kommune, Verband, Kongress)
- Anleitungen: Testlauf, Geräteausgabe, Raumplanung und Reichweite
- Englische Inhalte für Länder außerhalb DACH (Councils, HOAs)
- Regionale Seiten für Kommunalrecht je Bundesland (nur mit juristisch geprüften Aussagen)
