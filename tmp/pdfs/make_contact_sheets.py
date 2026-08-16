from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


workspace = Path(r"D:\obsidian笔记库\本体论一些知识")
render_dir = workspace / "tmp" / "pdfs" / "final-render"
output_dir = workspace / "output" / "playwright" / "final-qa"
output_dir.mkdir(parents=True, exist_ok=True)

files = sorted(render_dir.glob("page-*.png"))
if len(files) != 94:
    raise RuntimeError(f"Expected 94 rendered pages, found {len(files)}")

columns = 6
rows = 4
thumb_width = 180
label_height = 24
cell_padding = 8
font = ImageFont.load_default()

for sheet_index in range((len(files) + columns * rows - 1) // (columns * rows)):
    subset = files[sheet_index * columns * rows : (sheet_index + 1) * columns * rows]
    prepared = []
    max_thumb_height = 0
    for path in subset:
        image = Image.open(path).convert("RGB")
        thumb_height = round(image.height * thumb_width / image.width)
        thumbnail = image.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        prepared.append((path, thumbnail))
        max_thumb_height = max(max_thumb_height, thumb_height)

    cell_width = thumb_width + cell_padding * 2
    cell_height = max_thumb_height + label_height + cell_padding * 2
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), "#d9d9d9")
    draw = ImageDraw.Draw(sheet)
    for index, (path, thumbnail) in enumerate(prepared):
        column = index % columns
        row = index // columns
        x = column * cell_width + cell_padding
        y = row * cell_height + label_height + cell_padding
        sheet.paste(thumbnail, (x, y))
        page_number = int(path.stem.split("-")[-1])
        draw.text((x, row * cell_height + 6), f"Page {page_number}", fill="black", font=font)
    output_path = output_dir / f"contact-sheet-{sheet_index + 1}.jpg"
    sheet.save(output_path, quality=92, optimize=True)
    print(output_path)
