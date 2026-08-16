from email import policy
from email.parser import BytesParser
from pathlib import Path
import hashlib
import html as html_lib
import re


folder = Path(r"D:\本体\汽轮机安调项目\项目初期demo")
source_html_path = folder / "汽轮机本体安装及维护说明书.html"
source_mhtml_path = folder / "汽轮机本体安装及维护说明书 _ PDF.mhtml"

source_html = source_html_path.read_text(encoding="utf-8", errors="replace")
with source_mhtml_path.open("rb") as stream:
    message = BytesParser(policy=policy.default).parse(stream)

html_parts = [part for part in message.walk() if part.get_content_type() == "text/html"]
main_html = html_parts[0].get_content()
debug_index = main_html.find('id="page1"')
if debug_index < 0:
    debug_index = main_html.find("id=page1")
print("page1_context", repr(main_html[max(0, debug_index - 160):debug_index + 240]))

source_doc_ids = set(re.findall(r"document/(\d+)", source_html))
mhtml_doc_ids = set(re.findall(r"document/(\d+)", main_html))

source_pages = {}
for match in re.finditer(
    r"docManager\.addPage\(\{(?P<body>.*?)\}\);", source_html, re.DOTALL
):
    body = match.group("body")
    number = re.search(r"pageNum:\s*(\d+)", body)
    width = re.search(r"origWidth:\s*(\d+)", body)
    height = re.search(r"origHeight:\s*(\d+)", body)
    url = re.search(r'contentUrl:\s*"([^"]+)"', body)
    if all((number, width, height, url)):
        source_pages[int(number.group(1))] = {
            "width": int(width.group(1)),
            "height": int(height.group(1)),
            "url": url.group(1),
        }

mhtml_pages = {}
page_starts = list(
    re.finditer(
        r'<div\s+class="newpage"\s+id="page(\d+)"\s+'
        r'style="[^"]*width:\s*(\d+)px;\s*height:\s*(\d+)px;[^"]*"',
        main_html,
    )
)
for index, match in enumerate(page_starts):
    number = int(match.group(1))
    end = page_starts[index + 1].start() if index + 1 < len(page_starts) else len(main_html)
    fragment = main_html[match.start():end]
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html_lib.unescape(re.sub(r"\s+", " ", text)).strip()
    mhtml_pages[number] = {
        "width": int(match.group(2)),
        "height": int(match.group(3)),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_chars": len(text),
    }

matching_dimensions = []
dimension_mismatches = []
for number in sorted(set(source_pages) & set(mhtml_pages)):
    source_size = (source_pages[number]["width"], source_pages[number]["height"])
    captured_size = (mhtml_pages[number]["width"], mhtml_pages[number]["height"])
    if source_size == captured_size:
        matching_dimensions.append(number)
    else:
        dimension_mismatches.append((number, source_size, captured_size))

locations = [part.get("Content-Location", "") for part in message.walk()]
document_asset_locations = [item for item in locations if "b7li9jzk0dud3wm" in item]

print("source_sha256", hashlib.sha256(source_html_path.read_bytes()).hexdigest())
print("mhtml_sha256", hashlib.sha256(source_mhtml_path.read_bytes()).hexdigest())
print("source_doc_ids", sorted(source_doc_ids))
print("mhtml_doc_ids", sorted(mhtml_doc_ids))
print("source_pages", len(source_pages), min(source_pages), max(source_pages))
print(
    "mhtml_pages",
    len(mhtml_pages),
    min(mhtml_pages) if mhtml_pages else None,
    max(mhtml_pages) if mhtml_pages else None,
)
print("matching_dimensions", len(matching_dimensions))
print("dimension_mismatches", dimension_mismatches)
print("nonempty_text_pages", sum(1 for page in mhtml_pages.values() if page["text_chars"] > 0))
print("document_asset_parts", len(document_asset_locations))
print(
    "same_document",
    source_doc_ids.issubset(mhtml_doc_ids)
    and len(source_pages) == len(mhtml_pages) == 94
    and not dimension_mismatches,
)

for part in message.walk():
    if part.get_content_type() != "text/css":
        continue
    try:
        css = part.get_content()
    except Exception:
        continue
    if re.search(r"\.ff[0-6](?:\{|,)", css):
        print("page_font_css_location", part.get("Content-Location", ""))
        print("page_font_css", css[:5000])
