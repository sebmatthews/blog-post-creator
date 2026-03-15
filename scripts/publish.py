#!/usr/bin/env python3

# publish.py
# Converts an Obsidian markdown file to a Divi-ready HTML fragment.
# Replaces publish.sh — no pandoc dependency required.
#
# Strips YAML front matter, converts the markdown body to HTML using the
# Python markdown library, then collapses line wrapping so it pastes
# cleanly into Divi.
#
# Usage:
#   Convert a specific file:              python3 publish.py file.md
#   Force overwrite of existing output:   python3 publish.py -overwrite file.md
#
# Requires: pip install markdown

import sys
import os
import re

import markdown


def strip_front_matter(content):
    """Remove YAML front matter from the top of the file if present.
    The Python markdown library does not handle front matter — leaving it
    in would produce a stray <hr> and garbled YAML in the HTML output."""
    if not content.startswith('---'):
        return content
    end = content.find('\n---', 3)
    if end == -1:
        return content
    return content[end + 4:].lstrip('\n')


def main():
    overwrite = False
    args = []
    for arg in sys.argv[1:]:
        if arg == '-overwrite':
            overwrite = True
        else:
            args.append(arg)

    if not args:
        print("Usage: publish.py [-overwrite] file.md")
        sys.exit(1)

    file = args[0]

    if not os.path.exists(file):
        print(f"File not found: {file}")
        sys.exit(1)

    if not file.endswith('.md'):
        print("Error: expected a .md file")
        sys.exit(1)

    output = file[:-3] + '_BODY_ONLY.html'

    if os.path.exists(output) and not overwrite:
        print(f"Skipping: {output} (already exists, use -overwrite to replace)")
        sys.exit(0)

    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    content = strip_front_matter(content)

    # Convert markdown to HTML fragment.
    # tables: GFM-style pipe tables.
    # fenced_code: triple-backtick code blocks.
    html = markdown.markdown(
        content,
        extensions=['tables', 'fenced_code'],
        output_format='html'
    )

    # Post-process: strip carriage returns, collapse newlines to spaces,
    # then collapse any resulting runs of spaces down to one.
    # This matches the behaviour of the original publish.sh pipeline and
    # ensures the output pastes as a single clean line into Divi.
    html = html.replace('\r', '')
    html = html.replace('\n', ' ')
    html = re.sub(r'  +', ' ', html).strip()

    with open(output, 'w', encoding='utf-8') as f:
        f.write(html)

    if overwrite:
        print(f"Overwritten: {output}")
    else:
        print(f"Created: {output}")


if __name__ == '__main__':
    main()
