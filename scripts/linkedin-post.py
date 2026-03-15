#!/usr/bin/env python3

# linkedin-post.py
# Publishes a completed blog post to LinkedIn as a teaser with a link back to WordPress.
# Reads post metadata from the markdown front matter, resizes the header image to
# LinkedIn's optimal dimensions, uploads it, and creates a public article post.
#
# Usage:
#   python3 scripts/linkedin-post.py file.md
#
# Prerequisites:
#   - The post must be published on WordPress with a post_url field in the front matter.
#   - scripts/linkedin_config.py must contain LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_ID.
#   - Pillow must be installed: pip install Pillow

import sys
import os
import json
import io
import urllib.request
import urllib.error
from datetime import date

# Target dimensions for LinkedIn article thumbnail (optimal display size)
LINKEDIN_IMAGE_WIDTH = 1200
LINKEDIN_IMAGE_HEIGHT = 627

# Folder where blog header images are stored.
# When run via the Obsidian plugin, BLOG_IMAGE_FOLDER is set by the plugin settings.
# When run standalone, falls back to the path below.
IMAGE_FOLDER = os.environ.get('BLOG_IMAGE_FOLDER', '/users/sebmatthews/onedrive/holder/content/writing/2026/blog posts/imagery')

# LinkedIn API version
LI_VERSION = "202601"

# Load credentials from linkedin_config.py in the same folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linkedin_config import LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_ID


def auth_headers(extra=None):
    """Build standard LinkedIn API headers with optional extras."""
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "LinkedIn-Version": LI_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if extra:
        headers.update(extra)
    return headers


def parse_front_matter(md_content):
    """Extract title, excerpt, linkedin_caption, linkedin_publish_date, tags, image, and post_url from YAML front matter."""
    title = None
    excerpt = None
    linkedin_caption = None
    linkedin_publish_date = None
    tags = []
    image = None
    post_url = None

    lines = md_content.split('\n')
    in_front_matter = False
    in_tags = False

    for i, line in enumerate(lines):
        if i == 0 and line.strip() == '---':
            in_front_matter = True
            continue
        if not in_front_matter:
            break
        if line.strip() == '---':
            break
        if line.startswith('title:'):
            title = line[6:].strip()
            in_tags = False
        elif line.startswith('excerpt:'):
            excerpt = line[8:].strip()
            in_tags = False
        elif line.startswith('linkedin_caption:'):
            linkedin_caption = line[17:].strip()
            in_tags = False
        elif line.startswith('linkedin_publish_date:'):
            linkedin_publish_date = line[22:].strip()
            in_tags = False
        elif line.startswith('image:'):
            image = line[6:].strip()
            in_tags = False
        elif line.startswith('post_url:'):
            post_url = line[9:].strip()
            in_tags = False
        elif line.startswith('tags:'):
            in_tags = True
        elif in_tags and line.strip().startswith('- '):
            value = line.strip()[2:].strip()
            if value:
                tags.append(value)
        elif not line.startswith(' ') and not line.startswith('\t'):
            in_tags = False

    return title, excerpt, linkedin_caption, linkedin_publish_date, tags, image, post_url


def resize_image(source_path):
    """Resize the header image to LinkedIn dimensions and return PNG bytes."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is required for image resizing.")
        print("Install it with: pip install Pillow")
        sys.exit(1)

    img = Image.open(source_path)
    img_resized = img.resize((LINKEDIN_IMAGE_WIDTH, LINKEDIN_IMAGE_HEIGHT), Image.LANCZOS)

    buf = io.BytesIO()
    img_resized.save(buf, format='PNG')
    return buf.getvalue()


def initialize_image_upload():
    """Initialize a LinkedIn image upload and return the upload URL and image URN."""
    payload = {
        "initializeUploadRequest": {
            "owner": f"urn:li:person:{LINKEDIN_PERSON_ID}"
        }
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://api.linkedin.com/rest/images?action=initializeUpload",
        data=data,
        headers=auth_headers({"Content-Type": "application/json"}),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"Error initialising image upload: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)

    upload_url = result['value']['uploadUrl']
    image_urn = result['value']['image']
    return upload_url, image_urn


def upload_image(upload_url, image_bytes):
    """Upload image bytes to the LinkedIn-provided upload URL."""
    req = urllib.request.Request(
        upload_url,
        data=image_bytes,
        headers={"Content-Type": "application/octet-stream"},
        method="PUT"
    )

    try:
        with urllib.request.urlopen(req) as response:
            pass  # 201 No Content on success
    except urllib.error.HTTPError as e:
        print(f"Error uploading image: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)


def build_commentary(title, linkedin_caption, excerpt, tags, post_url):
    """Build the LinkedIn post text from front matter fields.
    Uses linkedin_caption if populated, falls back to excerpt."""
    caption = linkedin_caption if linkedin_caption else excerpt

    hashtags = ' '.join(
        f'#{tag.replace("-", "").replace(" ", "")}' for tag in tags
    ) if tags else ''

    parts = []
    if title:
        parts.append(title)
    if caption:
        parts.append(f"\n{caption}")
    if post_url:
        parts.append(f"\nRead the full post: {post_url}")
    if hashtags:
        parts.append(f"\n{hashtags}")

    return '\n'.join(parts)


def write_publish_date(md_file, date_str):
    """Write the linkedin_publish_date value back into the markdown file's front matter."""
    with open(md_file, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    updated = False

    for line in lines:
        if line.startswith('linkedin_publish_date:') and not updated:
            new_lines.append(f"linkedin_publish_date: {date_str}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        print("Warning: linkedin_publish_date field not found in front matter. Date not written back.")
    else:
        with open(md_file, 'w') as f:
            f.write('\n'.join(new_lines))
        print(f"linkedin_publish_date set to {date_str} in front matter.")


def create_post(commentary, image_urn, post_url, title, excerpt):
    """Create a LinkedIn article post with image thumbnail and link back to the blog."""
    payload = {
        "author": f"urn:li:person:{LINKEDIN_PERSON_ID}",
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "content": {
            "article": {
                "source": post_url,
                "thumbnail": image_urn,
                "title": title or "",
                "description": excerpt or ""
            }
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "https://api.linkedin.com/rest/posts",
        data=data,
        headers=auth_headers({"Content-Type": "application/json"}),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            post_id = response.headers.get('x-restli-id', 'unknown')
            return post_id
    except urllib.error.HTTPError as e:
        print(f"Error creating post: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: linkedin-post.py file.md")
        sys.exit(1)

    md_file = sys.argv[1]

    if not os.path.exists(md_file):
        print(f"File not found: {md_file}")
        sys.exit(1)

    with open(md_file, 'r') as f:
        md_content = f.read()

    title, excerpt, linkedin_caption, linkedin_publish_date, tags, image_filename, post_url = parse_front_matter(md_content)

    if linkedin_publish_date:
        print(f"This post has already been published to LinkedIn on {linkedin_publish_date}.")
        print("If you want to re-publish, clear the linkedin_publish_date field in the front matter first.")
        sys.exit(0)

    if not post_url:
        print("No post_url found in front matter.")
        print("Publish the post to WordPress first, then add the public URL to the post_url field and try again.")
        sys.exit(1)

    if not image_filename:
        print("No image field found in front matter. Cannot determine image to upload.")
        sys.exit(1)

    image_path = os.path.join(IMAGE_FOLDER, image_filename)
    if not os.path.exists(image_path):
        print(f"Image file not found: {image_path}")
        sys.exit(1)

    print(f"Resizing image to {LINKEDIN_IMAGE_WIDTH}x{LINKEDIN_IMAGE_HEIGHT}...")
    image_bytes = resize_image(image_path)

    print("Initialising LinkedIn image upload...")
    upload_url, image_urn = initialize_image_upload()

    print("Uploading image...")
    upload_image(upload_url, image_bytes)
    print(f"Image uploaded: {image_urn}")

    commentary = build_commentary(title, linkedin_caption, excerpt, tags, post_url)

    print("Creating LinkedIn post...")
    post_id = create_post(commentary, image_urn, post_url, title, excerpt)

    print(f"Post published successfully!")
    print(f"Post ID: {post_id}")
    print(f"View at: https://www.linkedin.com/feed/")

    write_publish_date(md_file, date.today().strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()
