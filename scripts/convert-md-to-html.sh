#!/bin/bash
for f in *.md; do
  html="${f%.md}.html"
  if [ ! -f "$html" ]; then
    pandoc "$f" -f markdown -t html -s -o "$html"
    echo "Converted $f"
  else
    echo "Skipped $f (html already exists)"
  fi
done