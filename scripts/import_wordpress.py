import argparse
import base64
import json
import os
import pathlib
import re
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

    try:
        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            raw = response.read()
            try:
                return json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                content_type = response.headers.get("Content-Type", "unbekannt")
                raise RuntimeError(
                    f"WordPress liefert kein gültiges JSON: {method} {url}; "
                    f"HTTP {response.status}; Content-Type: {content_type}; "
                    f"Antwortlänge: {len(raw)} Bytes. "
                    "Mögliche Ursachen sind eine leere Antwort, eine HTML-Seite "
                    "oder eine vorgeschaltete Sicherheitsprüfung. "
                    "Die Antwort wird nicht als erfolgreicher Import behandelt."
                ) from error

    except urllib.error.HTTPError as error:
        details = error.read().decode(
            "utf-8", errors="replace"
        )
        raise RuntimeError(
            f"WordPress API HTTP {error.code}: {details}"
        ) from error

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
# Entwurf erstellen oder aktualisieren
# --------------------------------------------------

def upsert_draft(slug, parent, title, content):
    existing = find_article(slug, parent)

    if existing:
        existing = api("GET", f"/{existing['id']}", params={"context": "edit"})
        if existing.get("parent", 0) != parent or existing.get("slug") != slug:
            raise RuntimeError(f"Artikelzuordnung geändert: {slug}")
        if existing["status"] != "draft":
            raise RuntimeError(
                f"Artikel '{slug}' ist kein Entwurf. "
                "Automatische Änderung abgebrochen."
            )

        result = api(
            "POST",
            f"/{existing['id']}",
            {
                "title": title,
                "content": content,
            },
        )

        verify_identity(result, slug, parent)
        print(f"Entwurf aktualisiert: {slug}")
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

    verify_identity(result, slug, parent)
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


def update_yoast_fields(article_id, expected_values):
    print("\nÜbernehme Yoast-Metadaten aus YAML ...")

    # Entwurfsstatus unmittelbar vor dem Schreiben erneut prüfen.
    current = api("GET", f"/{article_id}", params={"context": "edit"})
    if current.get("status") != "draft":
        raise RuntimeError(
            "Yoast-Import abgebrochen: Artikel ist kein Entwurf."
        )

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

    if saved.get("status") != "draft":
        raise RuntimeError(
            "Sicherheitsprüfung fehlgeschlagen: "
            "Artikel ist kein Entwurf."
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
    "hardware": "Hardware",
    "ratgeber": "Ratgeber",
    "begriffe": "Begriffe",
}


def verify_identity(article, slug, parent):
    if (article.get("status") != "draft"
            or article.get("slug") != slug
            or article.get("parent", 0) != parent):
        raise RuntimeError(f"Entwurfsstatus oder Artikelzuordnung unerwartet: {slug}")


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
            if section is None and relative.name in PARENT_TITLES:
                raise RuntimeError("Artikel kollidiert mit einem Bereichs-Slug.")
            metadata, content = read_markdown(source)
            seo = yoast_values(metadata)
            if metadata.get("lang") != "de":
                raise RuntimeError("Erwartet lang: de.")
            html = markdown.markdown(convert_links(content, source),
                                     extensions=["extra", "sane_lists"])
            articles.append({"path": relative.as_posix(), "slug": relative.name,
                             "section": section, "title": metadata["title"],
                             "content": html, "meta": seo})
        except (RuntimeError, ValueError, yaml.YAMLError) as error:
            errors.append(f"{source.relative_to(REPO_ROOT)}: {error}")
    if errors:
        raise RuntimeError("Vorprüfung fehlgeschlagen:\n" + "\n".join(errors))
    return articles


def preflight(articles):
    """Alle betroffenen vorhandenen Artikel vor dem ersten POST prüfen."""
    parents = {}
    for section in sorted({a["section"] for a in articles if a["section"]}):
        existing = find_article(section, 0)
        if existing and existing.get("status") != "draft":
            raise RuntimeError(f"Bereich '{section}' ist kein Entwurf.")
        parents[section] = existing
        print(f"Bereich {section}: " + ("Entwurf vorhanden" if existing else "neu"))
    for article in articles:
        section = article["section"]
        parent = parents.get(section) if section else None
        existing = (find_article(article["slug"], parent["id"] if parent else 0)
                    if not section or parent else None)
        if existing and existing.get("status") != "draft":
            raise RuntimeError(f"Artikel '{article['path']}' ist kein Entwurf.")
        print(("AKTUALISIEREN " if existing else "NEU ") + article["path"])
    return parents


def main():
    parser = argparse.ArgumentParser(description="Deutsche Wissensartikel als Entwürfe importieren.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Entwürfe schreiben und SEO prüfen")
    mode.add_argument("--dry-run", action="store_true", help="Nur prüfen (Standard)")
    args = parser.parse_args()
    configure()
    articles = prepare_articles()
    print(f"Lokal geprüft: {len(articles)} deutsche Artikel; keine englischen Inhalte.")
    parents = preflight(articles)
    if not args.apply:
        print("Prüfmodus abgeschlossen. Keine Änderungen an WordPress.")
        return
    parent_ids = {}
    for section in parents:
        # Bestehende Bereichsinhalte bewahren; neue Bereiche bleiben zunächst leer.
        existing = find_article(section, 0)
        if existing:
            verify_identity(existing, section, 0)
            parent_ids[section] = existing["id"]
        else:
            parent_ids[section] = upsert_draft(section, 0, PARENT_TITLES[section], "")["id"]
    for article in articles:
        parent_id = parent_ids.get(article["section"], 0)
        if parent_id:
            parent = api("GET", f"/{parent_id}", params={"context": "edit"})
            verify_identity(parent, article["section"], 0)
        saved = upsert_draft(article["slug"], parent_id,
                             article["title"], article["content"])
        update_yoast_fields(saved["id"], article["meta"])
        persisted = api("GET", f"/{saved['id']}", params={"context": "edit"})
        verify_identity(persisted, article["slug"], parent_id)
        print(f"Geprüft: {BASE_URL}/wissen/{article['path']}/ (ID {saved['id']})")
    print(f"Import erfolgreich: {len(articles)} Artikel als Entwürfe geprüft.")


if __name__ == "__main__":
    main()
