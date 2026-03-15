#!/bin/bash

# strip_body.sh
# Extracts the <body>...</body> content from HTML files and saves each
# result as a new file with _BODY_ONLY appended to the filename.
#
# Usage:
#   Process all .html files in current directory:   ./strip_body.sh
#   Process specific files:                         ./strip_body.sh file1.html file2.html
#   Force overwrite of existing output files:       ./strip_body.sh -overwrite
#   Force overwrite of specific files:              ./strip_body.sh -overwrite file1.html file2.html

# Check for the -overwrite flag
overwrite=false
args=()
for arg in "$@"; do
    if [ "$arg" = "-overwrite" ]; then
        overwrite=true
    else
        args+=("$arg")
    fi
done

# If no file arguments given, find all .html files in the current directory
if [ ${#args[@]} -eq 0 ]; then
    files=(*.html)
else
    files=("${args[@]}")
fi

# Check that at least one file was found
if [ ${#files[@]} -eq 0 ] || [ ! -f "${files[0]}" ]; then
    echo "No HTML files found."
    exit 1
fi

for file in "${files[@]}"; do

    # Skip if source file does not exist
    if [ ! -f "$file" ]; then
        echo "Skipping: $file (not found)"
        continue
    fi

    # Build the output filename, inserting _BODY_ONLY before the extension
    # e.g. report.html becomes report_BODY_ONLY.html
    base="${file%.html}"
    output="${base}_BODY_ONLY.html"

    # Skip if the output file already exists and -overwrite was not set
    if [ -f "$output" ] && [ "$overwrite" = false ]; then
        echo "Skipping: $output (already exists, use -overwrite to replace)"
        continue
    fi

    # Extract everything from the opening <body tag to the closing </body> tag.
    # The /<body/i pattern is case-insensitive and handles attributes on the body tag.
    # The output is then stripped of carriage returns and newlines are collapsed into
    # single spaces, preventing the narrow-paste issue caused by pandoc's line wrapping.
    awk 'BEGIN{IGNORECASE=1} /<body/{found=1} found{print} /<\/body>/{found=0}' "$file" \
        | tr -d '\r' \
        | tr '\n' ' ' \
        | sed 's/  */ /g' \
        > "$output"

    if [ "$overwrite" = true ]; then
        echo "Overwritten: $output"
    else
        echo "Created: $output"
    fi

done
