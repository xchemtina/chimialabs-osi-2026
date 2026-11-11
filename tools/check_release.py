#!/usr/bin/env python3
"""Check frozen sources, generated site identity and local navigation."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_fixture():
    directory = ROOT / "companion/fixtures/pbso4"
    manifest = json.loads((directory / "manifest.json").read_text())
    expected = manifest["files_sha256"]
    assert {p.name for p in directory.iterdir()} == set(expected) | {"manifest.json"}
    for name, value in expected.items():
        assert digest(directory / name) == value, name


def check_vendor():
    directory = ROOT / "companion/adapter/vendor"
    upstream = json.loads((directory / "UPSTREAM.json").read_text())
    for name, value in upstream["crates_unmodified_sha256"].items():
        assert digest(directory / name) == value, name


def check_site():
    source = ROOT / "companion"
    target = ROOT / "docs/companion"
    for name in ("public", "fixtures/pbso4", "run"):
        files = [p for p in (source / name).rglob("*") if p.is_file()]
        for path in files:
            assert path.read_bytes() == (target / path.relative_to(source)).read_bytes(), str(path)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.urls.append(value)


def check_links():
    checked = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".git", "target"} for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix == ".html":
            parser = Links()
            parser.feed(path.read_text())
            urls = parser.urls
        elif path.suffix == ".md":
            urls = re.findall(r"\]\(([^)]+)\)", path.read_text())
        else:
            continue
        for url in urls:
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            assert target.is_relative_to(ROOT) and target.exists(), (str(path), url)
            checked += 1
    return checked


if __name__ == "__main__":
    check_fixture()
    check_vendor()
    check_site()
    print(json.dumps({"fixture": "PASS", "vendor": "PASS", "site_identity": "PASS", "local_links": check_links()}))
