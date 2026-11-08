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

BASE_URL = os.environ["WP_URL"].rstrip("/")
API_URL = f"{BASE_URL}/wp-json/wp/v2/wissen"

SOURCE = pathlib.Path(
    "content/de/loesungen/edivote-powerpoint-abstimmung.md"
)

USERNAME = os.environ["WP_USER"]
PASSWORD = os.environ["WP_APP_PASSWORD"]

auth = base64.b64encode(
    f"{USERNAME}:{PASSWORD}".encode("utf-8")
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
            return json.load(response)

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

def convert_links(text):
    def replace(match):
        label, target = match.groups()

        if (
            not target.endswith(".md")
            or "://" in target
            or target.startswith("/")
        ):
            return match.group(0)

        resolved = (
            SOURCE.parent / target
        ).resolve()

        root = pathlib.Path(
            "content/de"
        ).resolve()

        try:
            relative = resolved.relative_to(root)
        except ValueError:
            return match.group(0)

        slug = relative.with_suffix("").as_posix()

        return (
            f"[{label}]"
            f"({BASE_URL}/wissen/{slug}/)"
        )

    return re.sub(
        r"\[([^\]]+)\]\(([^)\s]+\.md)\)",
        replace,
        text,
    )

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

def main():
    metadata, content = read_markdown(SOURCE)

    # Vor jeder WordPress-Änderung alle benötigten SEO-Werte validieren.
    seo_meta = yoast_values(metadata)
    title = metadata["title"]

    # Markdown-Links in WordPress-Links umwandeln
    content = convert_links(content)

    # Markdown in HTML umwandeln
    html = markdown.markdown(
        content,
        extensions=[
            "extra",
            "sane_lists",
        ],
    )

    # Übergeordneten Artikel erstellen/aktualisieren
    parent = upsert_draft(
        slug="loesungen",
        parent=0,
        title="Lösungen",
        content="",
    )

    # EdiVote-Testartikel erstellen/aktualisieren
    article = upsert_draft(
        slug="edivote-powerpoint-abstimmung",
        parent=parent["id"],
        title=title,
        content=html,
    )

    print("Artikel-ID:", article["id"])

    print(
        "Erwartete URL:",
        f"{BASE_URL}/wissen/loesungen/"
        "edivote-powerpoint-abstimmung/",
    )

    # Sicherheit: Nur vorhandenen Entwurf testen
    if article.get("status") != "draft":
        raise RuntimeError(
            "Yoast-Test abgebrochen: "
            "Artikel ist kein Entwurf."
        )

    # Yoast-Felder schreiben und per separatem GET überprüfen.
    update_yoast_fields(article["id"], seo_meta)
    print("\nImport erfolgreich; Entwurf und Yoast-Metadaten überprüft!")

if __name__ == "__main__":
    main()
