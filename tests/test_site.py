import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.images: list[str] = []
        self.has_main = False
        self.h1_count = 0
        self.lang: str | None = None
        self.description = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        if tag == "main":
            self.has_main = True
        if tag == "h1":
            self.h1_count += 1
        if identifier := values.get("id"):
            self.ids.add(identifier)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "img" and values.get("src"):
            self.images.append(values["src"] or "")
        if tag == "meta" and values.get("name") == "description" and values.get("content"):
            self.description = True


def parse_site() -> SiteParser:
    parser = SiteParser()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    return parser


def test_site_has_accessible_document_structure() -> None:
    parser = parse_site()
    assert parser.lang == "en"
    assert parser.has_main
    assert parser.h1_count == 1
    assert parser.description
    assert {"home", "journey", "projects", "evidence", "next"} <= parser.ids


def test_internal_links_and_images_exist() -> None:
    parser = parse_site()
    for target in parser.links:
        if target.startswith("#"):
            assert target[1:] in parser.ids, f"Missing anchor: {target}"
        elif not target.startswith(("http://", "https://", "mailto:")):
            path = ROOT / unquote(target.split("#", 1)[0])
            assert path.exists(), f"Missing linked file: {target}"
    for source in parser.images:
        assert (ROOT / unquote(source)).exists(), f"Missing image: {source}"


def test_vercel_configuration_is_valid_json() -> None:
    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert config["cleanUrls"] is True
    assert config["headers"]


def test_public_files_contain_no_embedded_weather_or_sql_credentials() -> None:
    candidates = [
        ROOT / "index.html",
        ROOT / "README.md",
        ROOT / "learning" / "advanced-python" / "weather_etl.ipynb",
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in candidates)
    assert "Depi123" not in content
    assert not re.search(r'"appid"\s*:\s*"[a-f0-9]{24,}"', content, re.IGNORECASE)
    assert "OPENWEATHER_API_KEY" in content


def test_weather_notebook_is_valid_and_output_free() -> None:
    notebook = json.loads(
        (ROOT / "learning" / "advanced-python" / "weather_etl.ipynb").read_text(encoding="utf-8")
    )
    assert notebook["nbformat"] == 4
    code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code_cells
    assert all(cell.get("execution_count") is None for cell in code_cells)
    assert all(cell.get("outputs") == [] for cell in code_cells)
