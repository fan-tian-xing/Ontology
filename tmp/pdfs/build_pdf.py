from pathlib import Path
import json

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


workspace = Path(r"D:\obsidian笔记库\本体论一些知识")
pages_dir = workspace / "output" / "playwright" / "document-pages"
output_dir = workspace / "output" / "pdf"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "汽轮机本体安装及维护说明书_重建版.pdf"

manifest = json.loads((pages_dir / "manifest.json").read_text(encoding="utf-8"))
if len(manifest) != 94:
    raise RuntimeError(f"Expected 94 pages, found {len(manifest)}")

page_width_points = 595.275590551
pdf = canvas.Canvas(str(output_path), pageCompression=1)
pdf.setTitle("Turbine Body Installation and Maintenance Manual - Reconstructed")
pdf.setAuthor("Reconstructed from saved Scribd page captures")
pdf.setSubject("D300N-000105ASM")

for item in manifest:
    image_path = pages_dir / item["filename"]
    if not image_path.exists():
        raise FileNotFoundError(image_path)
    page_height_points = page_width_points * item["height"] / item["width"]
    pdf.setPageSize((page_width_points, page_height_points))
    pdf.drawImage(
        ImageReader(str(image_path)),
        0,
        0,
        width=page_width_points,
        height=page_height_points,
        preserveAspectRatio=False,
        mask="auto",
    )
    pdf.showPage()

pdf.save()
print(output_path)
