import pymupdf, subprocess, os, sys

doc = pymupdf.open("Ngoc Hap Thong Thu.pdf")
os.makedirs("ocr_pages", exist_ok=True)
for i in range(doc.page_count):
    out = f"ocr_pages/page_{i+1:03d}.txt"
    if os.path.exists(out) and os.path.getsize(out) > 0:
        continue
    pix = doc[i].get_pixmap(dpi=300)
    png = f"/tmp/_ocr_{i}.png"
    pix.save(png)
    txt = subprocess.run(["tesseract", png, "stdout", "-l", "vie"],
                         capture_output=True, text=True).stdout
    with open(out, "w") as f:
        f.write(txt)
    os.remove(png)
    if (i + 1) % 10 == 0:
        print(f"done {i+1}/164", flush=True)
print("OCR COMPLETE")
