import html as html_lib
import argparse
import base64
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import markdown
import yaml

# --------------------------------------------------
# WordPress-Konfiguration
# --------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTENT_ROOT = REPO_ROOT / "content/de"
BASE_URL = ""
API_URL = ""
auth = ""


def configure():
    global BASE_URL, API_URL, auth
    BASE_URL = os.environ["WP_URL"].rstrip("/")
    parsed = urllib.parse.urlsplit(BASE_URL)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise RuntimeError("WP_URL muss eine HTTPS-Basisadresse sein.")
    API_URL = f"{BASE_URL}/wp-json/wp/v2/wissen"
    auth = base64.b64encode(
        f"{os.environ['WP_USER']}:{os.environ['WP_APP_PASSWORD']}".encode("utf-8")
    ).decode("ascii")

# --------------------------------------------------
# WordPress REST API
# --------------------------------------------------

def api(method, path="", data=None, params=None):
    url = API_URL + path

    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }

    body = None

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    # Nur Leseabfragen mit temporärer Serverantwort wiederholen.
    # POST niemals automatisch wiederholen: Die Speicherung könnte erfolgt sein.
    delays = (2, 5, 10)
    attempts = len(delays) + 1 if method == "GET" else 1
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                status = response.status
                content_type = response.headers.get("Content-Type", "unbekannt")
                server = response.headers.get("Server", "unbekannt")
            if status == 202:
                if method == "GET" and attempt < len(delays):
                    delay = delays[attempt]
                    print(f"Leseabfrage: HTTP 202; erneuter Versuch in {delay} Sekunden.", flush=True)
                    time.sleep(delay)
                    continue
                raise RuntimeError(
                    f"REST-Abfrage abgewiesen oder zurückgestellt: {method} {url}; "
                    f"HTTP {status}; Content-Type: {content_type}; Server: {server}; "
                    f"Antwortlänge: {len(raw)} Bytes. "
                    "Bitte Hosting-/Sicherheitsprotokoll für diese Anfrage prüfen. "
                    "Authentifizierte REST-Zugriffe aus GitHub Actions müssen "
                    "ohne Browser-Challenge möglich sein. "
                    "Schreibabfragen werden nicht automatisch wiederholt."
                )
            if status not in (200, 201):
                raise RuntimeError(f"Unerwarteter REST-Status: {method} {url}; HTTP {status}.")
            try:
                return json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                raise RuntimeError(
                    f"WordPress liefert kein gültiges JSON: {method} {url}; "
                    f"HTTP {status}; Content-Type: {content_type}; Server: {server}; "
                    f"Antwortlänge: {len(raw)} Bytes. "
                    "Bitte Hosting-/Sicherheitsprotokoll prüfen."
                ) from error
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            if method == "GET" and error.code in (429, 502, 503, 504) and attempt < len(delays):
                delay = delays[attempt]
                print(f"Leseabfrage: HTTP {error.code}; erneuter Versuch in {delay} Sekunden.", flush=True)
                time.sleep(delay)
                continue
            raise RuntimeError(f"WordPress API HTTP {error.code}: {details}") from error

# --------------------------------------------------
# Vorhandene Artikel suchen
# --------------------------------------------------

def find_article(slug, parent=0):
    results = api(
        "GET",
        params={
            "slug": slug,
            "status": "draft,publish,future,private,pending",
            "per_page": 100,
            "context": "edit",
        },
    )

    if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
        raise RuntimeError(f"Unerwartete WordPress-Suchantwort für '{slug}'.")

    matches = [
        item
        for item in results
        if item.get("parent", 0) == parent
    ]

    if len(matches) > 1:
        raise RuntimeError(
            f"Mehrere Artikel gefunden: {slug}"
        )

    return matches[0] if matches else None

# --------------------------------------------------
# Artikel aktualisieren; neue Artikel ausschließlich als Entwurf erstellen
# --------------------------------------------------

def upsert_article(slug, parent, title, content):
    existing = find_article(slug, parent)

    if existing:
        existing = api("GET", f"/{existing['id']}", params={"context": "edit"})
        if existing.get("parent", 0) != parent or existing.get("slug") != slug:
            raise RuntimeError(f"Artikelzuordnung geändert: {slug}")
        verify_identity(existing, slug, parent)
        original_status = existing["status"]

        result = api(
            "POST",
            f"/{existing['id']}",
            {
                "title": title,
                "content": content,
            },
        )

        verify_identity(result, slug, parent, original_status)
        print(f"Artikel aktualisiert ({original_status}): {slug}")
        return result

    result = api(
        "POST",
        data={
            "slug": slug,
            "parent": parent,
            "title": title,
            "content": content,
            "status": "draft",
        },
    )

    verify_identity(result, slug, parent, "draft")
    print(f"Entwurf erstellt: {slug}")
    return result

# --------------------------------------------------
# Markdown mit YAML-Frontmatter lesen
# --------------------------------------------------

def read_markdown(source):
    text = source.read_text(encoding="utf-8")
    metadata = {}

    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)

        if len(parts) != 2:
            raise RuntimeError(
                "YAML-Frontmatter ist nicht abgeschlossen."
            )

        metadata = yaml.safe_load(parts[0][4:]) or {}
        text = parts[1]

    return metadata, text

# --------------------------------------------------
# Interne Markdown-Links umwandeln
# --------------------------------------------------

def convert_links(text, source):
    def replace(match):
        label, target = match.groups()
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc or parsed.path.startswith("/"):
            return match.group(0)
        if not parsed.path.endswith(".md"):
            return match.group(0)
        resolved = (source.parent / urllib.parse.unquote(parsed.path)).resolve()
        try:
            relative = resolved.relative_to(CONTENT_ROOT.resolve())
        except ValueError:
            raise RuntimeError(f"Interner Link außerhalb content/de: {source}: {target}")
        if not resolved.is_file():
            raise RuntimeError(f"Internes Linkziel fehlt: {source}: {target}")
        slug = relative.with_suffix("").as_posix()
        url = f"{BASE_URL}/wissen/{slug}/"
        if parsed.query:
            url += "?" + parsed.query
        if parsed.fragment:
            url += "#" + parsed.fragment
        return f"[{label}]({url})"

    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", replace, text)


# --------------------------------------------------
# Yoast SEO aus YAML-Metadaten übernehmen
# --------------------------------------------------

def yoast_values(metadata):
    if not isinstance(metadata, dict):
        raise RuntimeError("YAML-Frontmatter muss eine Zuordnung sein.")

    for field in ("title", "description"):
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeError(f"YAML-Feld '{field}' muss ein nicht leerer Text sein.")

    keywords = metadata.get("keywords")
    if (
        not isinstance(keywords, list)
        or not keywords
        or not isinstance(keywords[0], str)
        or not keywords[0].strip()
    ):
        raise RuntimeError(
            "YAML-Feld 'keywords' muss eine Liste mit einem nicht leeren "
            "ersten Text-Element sein."
        )

    return {
        "_yoast_wpseo_title": metadata["title"],
        "_yoast_wpseo_metadesc": metadata["description"],
        "_yoast_wpseo_focuskw": keywords[0],
    }


def update_yoast_fields(article_id, expected_values, expected_status):
    print("\nÜbernehme Yoast-Metadaten aus YAML ...")

    # Den beim Inhaltsimport bestätigten Status vor dem SEO-Schreiben prüfen.
    current = api("GET", f"/{article_id}", params={"context": "edit"})
    if current.get("status") != expected_status or expected_status not in ("draft", "publish"):
        raise RuntimeError("Yoast-Import abgebrochen: Artikelstatus geändert oder nicht freigegeben.")

    # Nur SEO-Metadaten aktualisieren.
    # Der Artikelstatus bleibt unverändert.
    api(
        "POST",
        f"/{article_id}",
        {
            "meta": expected_values,
        },
    )

    # Gespeicherte Werte erneut aus WordPress lesen.
    saved = api(
        "GET",
        f"/{article_id}",
        params={
            "context": "edit",
        },
    )

    if saved.get("status") != expected_status:
        raise RuntimeError(
            "Sicherheitsprüfung fehlgeschlagen: "
            "Artikelstatus wurde unerwartet geändert."
        )

    meta = saved.get("meta", {})

    for field, expected in expected_values.items():
        actual = meta.get(field)

        if actual != expected:
            raise RuntimeError(
                f"Yoast-Feld wurde nicht korrekt "
                f"gespeichert: {field}. "
                f"Erwartet: {expected!r}, "
                f"erhalten: {actual!r}"
            )

        print(f"Erfolgreich gespeichert: {field}")

    print(
        "\nAlle drei Yoast-Felder erfolgreich "
        "gespeichert und überprüft!"
    )

# --------------------------------------------------
# Hauptprogramm
# --------------------------------------------------

PARENT_TITLES = {
    "branchen": "Branchen",
    "loesungen": "Lösungen",
    "hardware": "Abstimmgeräte",
    "ratgeber": "Ratgeber",
    "begriffe": "Begriffe",
}


def verify_identity(article, slug, parent, expected_status=None):
    if (article.get("status") not in ("draft", "publish")
            or (expected_status is not None and article.get("status") != expected_status)
            or article.get("slug") != slug
            or article.get("parent", 0) != parent):
        raise RuntimeError(f"Artikelstatus oder Artikelzuordnung unerwartet: {slug}")


def prepare_articles():
    sources = sorted(CONTENT_ROOT.rglob("*.md"))
    if not sources:
        raise RuntimeError(f"Keine Artikel gefunden: {CONTENT_ROOT}")
    articles = []
    errors = []
    for source in sources:
        try:
            relative = source.relative_to(CONTENT_ROOT).with_suffix("")
            if len(relative.parts) > 2:
                raise RuntimeError("Mehr als eine Ordnerebene wird nicht unterstützt.")
            section = relative.parts[0] if len(relative.parts) == 2 else None
            if section is not None and section not in PARENT_TITLES:
                raise RuntimeError(f"Unbekannter Ordner: {section}")
            if section is None and relative.name in {*PARENT_TITLES, "start"}:
                raise RuntimeError("Artikel kollidiert mit einem Bereichs-Slug.")
            metadata, content = read_markdown(source)
            seo = yoast_values(metadata)
            if metadata.get("lang") != "de":
                raise RuntimeError("Erwartet lang: de.")
            html = markdown.markdown(convert_links(content, source),
                                     extensions=["extra", "sane_lists"])
            articles.append({"path": relative.as_posix(), "slug": relative.name,
                             "section": section, "title": metadata["title"],
                             "content": html, "meta": seo,
                             "description": metadata["description"]})
        except (RuntimeError, ValueError, yaml.YAMLError) as error:
            errors.append(f"{source.relative_to(REPO_ROOT)}: {error}")
    if errors:
        raise RuntimeError("Vorprüfung fehlgeschlagen:\n" + "\n".join(errors))
    return articles


GENERATED_MARKER = "<!-- infowhyse:generated-navigation:v1 -->"
SECTION_INTROS = {
    "branchen": "Finden Sie passende Abstimmungslösungen für Ihre Branche und Ihre Versammlung.",
    "loesungen": "Vergleichen Sie Software und Verfahren für Wahlen, Abstimmungen und Live-Umfragen.",
    "hardware": "Lernen Sie Reply-Abstimmgeräte kennen und vergleichen Sie die Modelle.",
    "ratgeber": "Planen Sie Ihre Abstimmung mit Checklisten, Entscheidungshilfen und Praxiswissen.",
    "begriffe": "Schlagen Sie Begriffe rund um elektronische Abstimmungen nach.",
}


def knowledge_url(path):
    return f"{BASE_URL}/wissen/{path}/"


def link(path, label):
    return (f'<a href="{html_lib.escape(knowledge_url(path), quote=True)}">'
            f'{html_lib.escape(label)}</a>')


def navigation_content(articles):
    """Übersichten aus denselben Quelldaten wie die Artikel erzeugen."""
    by_path = {article["path"]: article for article in articles}
    for required in ("faq", "begriffe/glossar"):
        if required not in by_path:
            raise RuntimeError(f"Navigation benötigt den Artikel: {required}")
    sections = {}
    for section in PARENT_TITLES:
        children = sorted((a for a in articles if a["section"] == section),
                          key=lambda a: a["title"].casefold())
        if not children:
            raise RuntimeError(f"Bereich ohne Artikel: {section}")
        items = "\n".join(
            f'<li><h2>{link(a["path"], a["title"])}</h2>'
            f'<p>{html_lib.escape(a["description"])}</p></li>' for a in children
        )
        sections[section] = (
            GENERATED_MARKER + '<nav aria-label="Brotkrümelnavigation">'
            + link("start", "Wissen") + ' / '
            + html_lib.escape(PARENT_TITLES[section]) + '</nav>'
            + f'<p>{html_lib.escape(SECTION_INTROS[section])}</p><ul>{items}</ul>'
        )
    entries = [
        ("branchen", "Branchen", SECTION_INTROS["branchen"]),
        ("loesungen", "Lösungen", SECTION_INTROS["loesungen"]),
        ("hardware", "Abstimmgeräte", SECTION_INTROS["hardware"]),
        ("ratgeber", "Ratgeber", SECTION_INTROS["ratgeber"]),
        ("begriffe/glossar", "Glossar", "Begriffe verständlich erklärt."),
        ("faq", "Häufige Fragen", "Antworten auf häufige Fragen zu Abstimmungssystemen."),
    ]
    cards = "".join(
        '<li style="border:1px solid #ddd;border-radius:8px;padding:1.25rem;">'
        f'<h2>{link(path, title)}</h2><p>{html_lib.escape(description)}</p></li>'
        for path, title, description in entries
    )
    home = (GENERATED_MARKER
            + '<p>Wie stimmen Sie sicher und passend zu Ihrer Veranstaltung ab? '
            'Hier finden Sie Lösungen, Geräte und praktische Hilfen für Ihre Planung.</p>'
            + '<ul style="list-style:none;padding:0;display:grid;'
            'grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:1rem;">'
            + cards + '</ul><p>' + link("ueber-infowhyse", "Über Infowhyse") + '</p>')
    if "ueber-infowhyse" not in by_path:
        raise RuntimeError("Navigation benötigt ueber-infowhyse.md.")
    for article in articles:
        section = article["section"]
        crumbs = link("start", "Wissen")
        if section:
            crumbs += " / " + link(section, PARENT_TITLES[section])
        article["content"] = (
            '<nav aria-label="Brotkrümelnavigation">' + crumbs + ' / '
            + html_lib.escape(article["title"]) + '</nav>' + article["content"]
            + '<p>' + (link(section, "Zur Bereichsübersicht") if section
                       else link("start", "Zur Wissensübersicht")) + '</p>'
        )
    return home, sections


def check_generated_target(existing, slug):
    if not existing:
        return
    verify_identity(existing, slug, 0)
    content = existing.get("content", {}).get("raw")
    if not isinstance(content, str):
        raise RuntimeError(f"Bereichsinhalt nicht lesbar: {slug}")
    if content.strip() and GENERATED_MARKER not in content:
        raise RuntimeError(
            f"'{slug}' enthält manuell gepflegte Inhalte. "
            "Automatisches Überschreiben abgebrochen."
        )


def preflight(articles):
    """Alle betroffenen vorhandenen Artikel vor dem ersten POST prüfen."""
    start = find_article("start", 0)
    check_generated_target(start, "start")
    print("Wissen-Startseite: " + ("aktualisieren" if start else "neu"))
    parents = {}
    for section in sorted({a["section"] for a in articles if a["section"]}):
        existing = find_article(section, 0)
        check_generated_target(existing, section)
        parents[section] = existing
        print(f"Bereich {section}: " + (existing["status"] + " vorhanden" if existing else "neu"))
    for article in articles:
        section = article["section"]
        parent = parents.get(section) if section else None
        existing = (find_article(article["slug"], parent["id"] if parent else 0)
                    if not section or parent else None)
        if existing:
            verify_identity(existing, article["slug"], parent["id"] if parent else 0)
        print(("AKTUALISIEREN " if existing else "NEU ") + article["path"])
    return parents


def main():
    parser = argparse.ArgumentParser(description="Wissensartikel aktualisieren; Status bewahren, neue Inhalte als Entwurf.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Artikel schreiben und SEO prüfen; bestehende Veröffentlichung bewahren")
    mode.add_argument("--dry-run", action="store_true", help="Nur prüfen (Standard)")
    args = parser.parse_args()
    configure()
    articles = prepare_articles()
    print(f"Lokal geprüft: {len(articles)} deutsche Artikel; keine englischen Inhalte.")
    home_content, section_contents = navigation_content(articles)
    parents = preflight(articles)
    if not args.apply:
        print("Prüfmodus abgeschlossen. Keine Änderungen an WordPress.")
        return
    # Vorhandene URLs und Parent-Zuordnungen bleiben erhalten.
    check_generated_target(find_article("start", 0), "start")
    home = upsert_article("start", 0, "Wissen", home_content)
    update_yoast_fields(home["id"], {
        "_yoast_wpseo_title": "Wissen zu Abstimmungssystemen | Infowhyse",
        "_yoast_wpseo_metadesc": "Branchen, Abstimmungslösungen, Reply-Abstimmgeräte und Ratgeber: Finden Sie das passende Wissen für Ihre Veranstaltung.",
        "_yoast_wpseo_focuskw": "Abstimmungssysteme",
    }, home["status"])
    parent_ids = {}
    for section in parents:
        check_generated_target(find_article(section, 0), section)
        saved = upsert_article(section, 0, PARENT_TITLES[section], section_contents[section])
        parent_ids[section] = saved["id"]
        update_yoast_fields(saved["id"], {
            "_yoast_wpseo_title": PARENT_TITLES[section] + " | Infowhyse Wissen",
            "_yoast_wpseo_metadesc": SECTION_INTROS[section],
            "_yoast_wpseo_focuskw": PARENT_TITLES[section],
        }, saved["status"])
    for article in articles:
        parent_id = parent_ids.get(article["section"], 0)
        if parent_id:
            parent = api("GET", f"/{parent_id}", params={"context": "edit"})
            verify_identity(parent, article["section"], 0)
        saved = upsert_article(article["slug"], parent_id,
                             article["title"], article["content"])
        update_yoast_fields(saved["id"], article["meta"], saved["status"])
        persisted = api("GET", f"/{saved['id']}", params={"context": "edit"})
        verify_identity(persisted, article["slug"], parent_id, saved["status"])
        print(f"Geprüft: {BASE_URL}/wissen/{article['path']}/ (ID {saved['id']})")
    print(f"Import erfolgreich: {len(articles)} Artikel, 5 Bereiche und Wissen-Startseite geprüft; vorhandener Status bewahrt, neue Inhalte als Entwurf.")
    print("Menüziel Wissen:", knowledge_url("start"))


if __name__ == "__main__":
    main()
