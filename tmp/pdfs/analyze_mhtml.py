from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path
import re


source = Path(r"C:\Users\尹仕程\Desktop\汽轮机本体安装及维护说明书 _ PDF.mhtml")
with source.open("rb") as stream:
    message = BytesParser(policy=policy.default).parse(stream)

parts = list(message.walk())
print("parts", len(parts))
print("content_types", Counter(part.get_content_type() for part in parts))

html_parts = [part for part in parts if part.get_content_type() == "text/html"]
print("html_parts", len(html_parts))
html = html_parts[0].get_content() if html_parts else ""
print("html_chars", len(html))
print("outer_pages", len(re.findall(r'id=[\"\']outer_page_\d+', html)))
print("newpages", len(re.findall(r'id=[\"\']page\d+[\"\']', html)))
print("addPage", html.count("docManager.addPage"))
print(
    "jsonp_urls",
    len(set(re.findall(r'https://html\.scribdassets\.com/[^\"\']+\.jsonp', html))),
)
print("absimg", html.count('class="absimg"'))

locations = [part.get("Content-Location", "") for part in parts]
print("font_parts", sum(1 for item in locations if re.search(r"\.(woff2?|ttf)(\?|$)", item)))
print("image_parts", sum(1 for part in parts if part.get_content_maintype() == "image"))
print("jsonp_parts", sum(1 for item in locations if ".jsonp" in item))

font_urls = set()
font_rules = []
for part in parts:
    if part.get_content_type() not in {"text/css", "text/html"}:
        continue
    try:
        content = part.get_content()
    except Exception:
        continue
    if "@font-face" in content or re.search(r"\.ff\d+", content):
        font_rules.append((part.get("Content-Location", ""), len(content)))
    font_urls.update(
        re.findall(r"https?://[^\"')\s]+\.(?:woff2?|ttf)(?:\?[^\"')\s]*)?", content)
    )

print("font_rule_parts", len(font_rules))
for location, size in font_rules[:20]:
    print("font_rule", size, location)
print("font_urls", len(font_urls))
for url in sorted(font_urls):
    print("font_url", url)
