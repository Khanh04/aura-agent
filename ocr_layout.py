"""Re-OCR all pages with tesseract TSV and rebuild spatially-aligned text.

Words are placed on a character grid using their pixel x/y coordinates,
so table columns stay vertically aligned in the output text.
"""
import pymupdf, subprocess, os, csv, io

PX_PER_CHAR = 22.0   # ~char width at 300dpi for this font size
LINE_TOL = 18        # px tolerance to merge words into the same visual row

doc = pymupdf.open("Ngoc Hap Thong Thu.pdf")
os.makedirs("ocr_layout", exist_ok=True)

for i in range(doc.page_count):
    out = f"ocr_layout/page_{i+1:03d}.txt"
    if os.path.exists(out) and os.path.getsize(out) > 0:
        continue
    png = f"/tmp/_lay_{i}.png"
    doc[i].get_pixmap(dpi=300).save(png)
    tsv = subprocess.run(["tesseract", png, "stdout", "-l", "vie", "tsv"],
                         capture_output=True, text=True).stdout
    os.remove(png)
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row.get("text") and row["text"].strip() and int(row["conf"]) >= 0:
            words.append((int(row["top"]), int(row["left"]), row["text"].strip()))
    words.sort()
    # cluster into visual rows
    rows = []
    for top, left, text in words:
        if rows and abs(top - rows[-1][0]) <= LINE_TOL:
            rows[-1][1].append((left, text))
        else:
            rows.append((top, [(left, text)]))
    lines = []
    for _, items in rows:
        items.sort()
        line = ""
        for left, text in items:
            col = int(left / PX_PER_CHAR)
            if col > len(line):
                line += " " * (col - len(line))
            elif line:
                line += " "
            line += text
        lines.append(line.rstrip())
    with open(out, "w") as f:
        f.write("\n".join(lines))
    if (i + 1) % 20 == 0:
        print(f"done {i+1}/164", flush=True)
print("LAYOUT OCR COMPLETE")
