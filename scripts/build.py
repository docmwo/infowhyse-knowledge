#!/usr/bin/env python3
"""Prüft die Inhalte und erzeugt llms.txt und llms-full.txt.

Aufruf:
    python scripts/build.py            # prüfen und Dateien erzeugen
    python scripts/build.py --check    # nur prüfen (für CI)
    python scripts/build.py --urls     # zusätzlich prüfen, ob website_url erreichbar ist

Geprüft wird pro Artikel:
  - Frontmatter mit title, description, lang, type, website_url, updated
  - Abschnitt "Mehr Informationen" bzw. "More information" mit mindestens einem https-Link
  - relative Markdown-Links zeigen auf existierende Dateien
"""
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
RAW_BASE = "https://raw.githubusercontent.com/docmwo/infowhyse-knowledge/main/"
REQUIRED = ["title", "description", "lang", "type", "website_url", "updated"]

# Reihenfolge und Titel der Abschnitte in llms.txt (nach Ordner bzw. Dateiname)
SECTIONS = {
    "de": [
        ("Unternehmen", lambda p: p.name == "ueber-infowhyse.md"),
        ("Branchen", lambda p: p.parent.name == "branchen"),
        ("Lösungen und Software", lambda p: p.parent.name == "loesungen"),
        ("Abstimmgeräte (Hardware)", lambda p: p.parent.name == "hardware"),
        ("Ratgeber", lambda p: p.parent.name == "ratgeber"),
        ("Begriffe und FAQ", lambda p: p.name in ("glossar.md", "faq.md")),
    ],
    "en": [
        ("Company", lambda p: p.name == "about-reply-systems.md"),
        ("Solutions", lambda p: p.parent.name == "solutions"),
        ("Keypads", lambda p: p.parent.name == "products"),
        ("Guides", lambda p: p.parent.name == "guides"),
        ("Glossary and FAQ", lambda p: p.name in ("glossary.md", "faq.md")),
    ],
}


def parse(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return None, text
    meta, key, lst = {}, None, None
    for line in m.group(1).splitlines():
        if re.match(r"^\s+- ", line) and key:
            meta.setdefault(key, []).append(line.strip()[2:].strip())
            continue
        kv = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if kv:
            key, val = kv.group(1), kv.group(2).strip()
            meta[key] = val.strip('"') if val else []
    return meta, m.group(2)


def check(path, meta, body):
    errors = []
    rel = path.relative_to(ROOT)
    if meta is None:
        return [f"{rel}: kein Frontmatter"]
    for k in REQUIRED:
        if not meta.get(k):
            errors.append(f"{rel}: Frontmatter '{k}' fehlt")
    if meta.get("website_url") and not str(meta["website_url"]).startswith("https://"):
        errors.append(f"{rel}: website_url muss mit https:// beginnen")
    m = re.search(r"^## (Mehr Informationen|More information)\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    if not m or "https://" not in m.group(2):
        errors.append(f"{rel}: Abschnitt 'Mehr Informationen' mit Link fehlt")
    for target in re.findall(r"\]\(((?!https?://|#|mailto:)[^)]+)\)", body):
        t = (path.parent / target.split("#")[0]).resolve()
        if not t.exists():
            errors.append(f"{rel}: toter Link {target}")
    return errors


def url_ok(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ikp-check"})
        return urllib.request.urlopen(req, timeout=15).status < 400
    except Exception:
        return False


def main():
    only_check = "--check" in sys.argv
    check_urls = "--urls" in sys.argv
    files = sorted(CONTENT.rglob("*.md"))
    articles, errors = [], []
    for f in files:
        meta, body = parse(f)
        errors += check(f, meta, body)
        if meta:
            articles.append((f, meta, body))
    if check_urls:
        seen = set()
        for f, meta, _ in articles:
            urls = [meta.get("website_url", "")] + list(meta.get("website_urls", []) or [])
            for u in urls:
                if u and u not in seen:
                    seen.add(u)
                    if not url_ok(u):
                        errors.append(f"{f.relative_to(ROOT)}: URL nicht erreichbar {u}")
    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} Problem(e) in {len(files)} Dateien.")
        sys.exit(1)
    print(f"OK: {len(files)} Artikel geprüft.")
    if only_check:
        return

    # llms.txt
    out = [
        "# Infowhyse GmbH / Reply Systems",
        "",
        "> Infowhyse GmbH (Friedberg, Hessen) und die zugehörige Marke Reply Systems liefern elektronische Abstimmungslösungen: "
        "Funk-Abstimmgeräte (Keypads, Clicker, TED-Systeme) und Software für Hauptversammlungen, Mitgliederversammlungen, "
        "Kommunalgremien (Gemeinderat, Stadtrat, Kreistag), Kongresse, Schulungen und Events, offline, online (Browser) oder hybrid. "
        "Jeder Eintrag verweist auf einen Artikel und nennt die maßgebliche Seite auf infowhyse.com oder replysystems.com.",
        "",
        "Infowhyse GmbH and its brand Reply Systems supply electronic voting solutions: wireless voting keypads (clickers, audience response systems) "
        "and software for AGMs, member meetings, councils, conferences, training and events, offline, online or hybrid.",
        "",
        "Websites: https://www.infowhyse.com (Deutsch) · https://www.replysystems.com (Deutsch/English)",
        "",
    ]
    for lang, sections in SECTIONS.items():
        heading = "Deutsch" if lang == "de" else "English"
        langs = [(f, m, b) for f, m, b in articles if m.get("lang") == lang]
        for name, pred in sections:
            items = [(f, m) for f, m, _ in langs if pred(f)]
            if not items:
                continue
            out.append(f"## {heading}: {name}")
            out.append("")
            for f, m in items:
                raw = RAW_BASE + f.relative_to(ROOT).as_posix()
                out.append(f"- [{m['title']}]({raw}): {m['description']} Website: {m['website_url']}")
            out.append("")
    out += [
        "## Optional",
        "",
        f"- [Vollständige Wissensbasis als ein Dokument]({RAW_BASE}llms-full.txt): alle Artikel im Volltext",
        "- [Quellrepository](https://github.com/docmwo/infowhyse-knowledge): Markdown-Artikel mit Frontmatter",
        "",
    ]
    (ROOT / "llms.txt").write_text("\n".join(out), encoding="utf-8")

    # llms-full.txt
    full = ["# Infowhyse / Reply Systems: Wissensbasis (Volltext)", ""]
    for f, m, body in articles:
        full.append(f"\n---\n\n# {m['title']}\n")
        full.append(f"Quelle / Source: {m['website_url']}\n")
        body = re.sub(r"^# .*\n", "", body.strip() + "\n", count=1)
        full.append(body.strip())
    (ROOT / "llms-full.txt").write_text("\n".join(full) + "\n", encoding="utf-8")
    print("llms.txt und llms-full.txt erzeugt.")


if __name__ == "__main__":
    main()
