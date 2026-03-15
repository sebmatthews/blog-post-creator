#!/usr/bin/env python3

# generate-image.py
# Generates a header image for a blog post using the OpenAI Images API (gpt-image-1.5).
# Reads the image_prompt and image filename from the markdown front matter,
# prepends standard style constraints, and saves the result to the imagery folder.
#
# Usage:
#   python3 generate-image.py file.md
#
# Requires openai_config.py in the same folder with OPENAI_API_KEY defined.

import sys
import os
import json
import base64
import urllib.request
import urllib.error

# Folder where generated images are saved.
# When run via the Obsidian plugin, BLOG_IMAGE_FOLDER is set by the plugin settings.
# When run standalone, falls back to the path below.
IMAGE_FOLDER = os.environ.get('BLOG_IMAGE_FOLDER', '/users/sebmatthews/onedrive/holder/content/writing/2026/blog posts/imagery')

# Style prefix applied to every prompt - derived from Writing/Templates/image-creation-workflow.md.
# Keeps individual image_prompt fields short and post-specific.
STYLE_PREFIX = (
    "Photorealistic editorial photography, wide 16:9 landscape header format. "
    "Cold neutral palette, subtle steel blue bias, occasional restrained amber accents only. "
    "Well-lit but soft, diffused natural or ambient light, slightly elevated exposure. "
    "Overcast daylight or softly lit interior, enough light to read detail clearly. "
    "Shadows used sparingly for depth only, never to darken the overall scene. "
    "Wide composition with generous negative space suitable for a text headline. "
    "Clear subject, uncluttered read, strong leading lines where relevant. "
    "No text overlays, no logos, no flags, no UI labels, no readable markings. "
    "No explosions, no weapons, no overt conflict imagery. "
    "If people are present they are background context only, calm posture, never the hero. "
    "Any on-screen interfaces should look plausible but not be real or identifiable systems. "
)

# Load API key from openai_config.py in the same folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from openai_config import OPENAI_API_KEY


def parse_front_matter(md_content):
    """Extract image_prompt and image filename from YAML front matter."""
    image_prompt = None
    image = None
    lines = md_content.split('\n')
    in_front_matter = False

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == '---':
            in_front_matter = True
            continue
        if not in_front_matter:
            break
        if line.strip() == '---':
            break
        if line.startswith('image_prompt:'):
            image_prompt = line[13:].strip()
        elif line.startswith('image:'):
            image = line[6:].strip()

    return image_prompt, image


def generate_image(prompt):
    """Call the OpenAI Images API and return raw PNG bytes."""
    payload = {
        "model": "gpt-image-1.5",
        "prompt": prompt,
        "n": 1,
        "size": "1536x1024",
        "quality": "high"
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=data,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())

    b64_data = result['data'][0]['b64_json']
    return base64.b64decode(b64_data)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-image.py file.md")
        sys.exit(1)

    md_file = sys.argv[1]

    if not os.path.exists(md_file):
        print(f"File not found: {md_file}")
        sys.exit(1)

    with open(md_file, 'r') as f:
        md_content = f.read()

    image_prompt, image_filename = parse_front_matter(md_content)

    if not image_prompt:
        print("No image_prompt found in front matter. Add an image_prompt field and try again.")
        sys.exit(1)

    if not image_filename:
        print("No image field found in front matter. Cannot determine output filename.")
        sys.exit(1)

    # Ensure output filename uses .png
    if not image_filename.lower().endswith('.png'):
        image_filename = os.path.splitext(image_filename)[0] + '.png'

    full_prompt = STYLE_PREFIX + image_prompt

    print(f"Generating image: {image_filename}")
    print(f"Prompt: {full_prompt[:140]}...")

    try:
        image_bytes = generate_image(full_prompt)
    except urllib.error.HTTPError as e:
        print(f"API error: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)

    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    output_path = os.path.join(IMAGE_FOLDER, image_filename)

    with open(output_path, 'wb') as f:
        f.write(image_bytes)

    print(f"Image saved: {output_path}")


if __name__ == "__main__":
    main()
