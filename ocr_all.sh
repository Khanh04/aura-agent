#!/bin/bash
set -e
mkdir -p ocr_pages
> raw_text.txt
for i in $(seq -w 1 164); do
  png="ocr_pages/page-${i}.png"
  if [ ! -f "$png" ]; then
    pdftoppm -png -r 300 -f "$((10#$i))" -l "$((10#$i))" "Ngoc Hap Thong Thu.pdf" ocr_pages/page
  fi
  echo "===PAGE ${i}===" >> raw_text.txt
  tesseract "$png" stdout -l vie 2>/dev/null >> raw_text.txt
  echo "$i done"
done
