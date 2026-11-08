
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
        item for item in results
        if item.get("parent", 0) == parent
    ]

    if len(matches) > 1:
        raise RuntimeError(
            f"Mehrere Artikel gefunden: {slug}"
        )

    return matches[0] if matches else None


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


def read_markdown(source):
    text = source.read_text(encoding="utf-8")
    metadata = {}

    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)

        if len(parts) != 2:
            raise RuntimeError(
                "YAML-Frontmatter ist nicht abgeschlossen."
            )

        metadata = yaml.safe_load(
            parts[0][4:]
        ) or {}

        text = parts[1]

    return metadata, text


def convert_links(text):
    # Relative Markdown-Links innerhalb von content/de/
    # auf die zukünftigen Wissensartikel-URLs abbilden.
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

        root = pathlib.Path("content/de").resolve()

        try:
            relative = resolved.relative_to(root)
        except ValueError:
            return match.group(0)

        slug = relative.with_suffix("").as_posix()
        return f"[{label}]({BASE_URL}/wissen/{slug}/)"

    return re.sub(
        r"\[([^\]]+)\]\(([^)\s]+\.md)\)",
        replace,
        text,
    )


def main():
    metadata, content = read_markdown(SOURCE)

    title = metadata.get("title") or next(
        (
            line[2:].strip()
            for line in content.splitlines()
            if line.startswith("# ")
        ),
        SOURCE.stem,
    )

    content = convert_links(content)

    html = markdown.markdown(
        content,
        extensions=["extra", "sane_lists"],
    )

    parent = upsert_draft(
        slug="loesungen",
        parent=0,
        title="Lösungen",
        content="",
    )

    article = upsert_draft(
        slug="edivote-powerpoint-abstimmung",
        parent=parent["id"],
        title=title,
        content=html,
    )

    print("Import erfolgreich!")
    print("Artikel-ID:", article["id"])
    print(
        "Erwartete URL:",
        f"{BASE_URL}/wissen/loesungen/"
        "edivote-powerpoint-abstimmung/",
    )


if __name__ == "__main__":
    main()
