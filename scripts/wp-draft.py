#!/usr/bin/env python3

# wp-draft.py
# Pushes a blog post to WordPress as a draft using the REST API.
# Reads the post title, categories, excerpt, focus keyphrase and featured image
# from the markdown front matter, wraps the generated HTML in Divi shortcodes,
# and creates a draft post. On success, writes the post_url back into the
# markdown front matter using the slug returned by WordPress and the date year.
#
# Usage:
#   python3 wp-draft.py file.md
#
# Requires publish.sh to have been run first to generate the _BODY_ONLY.html file.

import sys
import os
import json
import base64
import mimetypes
import urllib.request
import urllib.error

# Folder where featured images are stored.
# When run via the Obsidian plugin, BLOG_IMAGE_FOLDER is set by the plugin settings.
# When run standalone, falls back to the path below.
IMAGE_FOLDER = os.environ.get('BLOG_IMAGE_FOLDER', '/users/sebmatthews/onedrive/holder/content/writing/2026/blog posts/imagery')

# Load credentials from wp_config.py in the same folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wp_config import WP_URL, WP_USER, WP_APP_PASSWORD

# Divi shortcode wrapper - matches the structure and styling of existing posts
DIVI_OPEN = (
    '[et_pb_section fb_built="1" admin_label="section" _builder_version="4.27.5" '
    'background_color="#000000" global_colors_info="{}"]'
    '[et_pb_row admin_label="row" _builder_version="4.16" background_size="initial" '
    'background_position="top_left" background_repeat="repeat" global_colors_info="{}"]'
    '[et_pb_column type="4_4" _builder_version="4.16" custom_padding="|||" '
    'global_colors_info="{}" custom_padding__hover="|||"]'
    '[et_pb_text _builder_version="4.27.6" _module_preset="default" '
    'text_text_color="#FFFFFF" text_font_size="20px" header_font_size="30px" '
    'header_2_text_color="#FFFFFF" header_2_font_size="30px" global_colors_info="{}"]'
)

DIVI_CLOSE = '[/et_pb_text][/et_pb_column][/et_pb_row][/et_pb_section]'

# Browser-like headers to pass Cloudflare bot detection
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9"
}


def make_auth_headers(credentials, extra=None):
    """Build headers with authorisation and optional extras."""
    headers = dict(HEADERS)
    headers["Authorization"] = f"Basic {credentials}"
    if extra:
        headers.update(extra)
    return headers


def parse_front_matter(md_content):
    """Extract title, date, excerpt, focus_keyphrase, meta_description, image, linkedin_caption and categories from YAML front matter."""
    title = None
    date = None
    excerpt = None
    focus_keyphrase = None
    meta_description = None
    image = None
    linkedin_caption = None
    categories = []
    lines = md_content.split('\n')
    in_front_matter = False
    in_category = False

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
            in_category = False
        elif line.startswith('date:'):
            date = line[5:].strip()
            in_category = False
        elif line.startswith('excerpt:'):
            excerpt = line[8:].strip()
            in_category = False
        elif line.startswith('focus_keyphrase:'):
            focus_keyphrase = line[16:].strip()
            in_category = False
        elif line.startswith('meta_description:'):
            meta_description = line[17:].strip()
            in_category = False
        elif line.startswith('image:'):
            image = line[6:].strip()
            in_category = False
        elif line.startswith('linkedin_caption:'):
            linkedin_caption = line[17:].strip()
            in_category = False
        elif line.startswith('category:'):
            in_category = True
        elif in_category and line.strip().startswith('- '):
            value = line.strip()[2:].strip()
            if value:
                categories.append(value)
        elif not line.startswith(' ') and not line.startswith('\t'):
            in_category = False

    return title, date, excerpt, focus_keyphrase, meta_description, image, linkedin_caption, categories


def write_front_matter_field(md_file, field, value):
    """Write a value back into a top-level front matter field."""
    with open(md_file, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith(f'{field}:'):
            new_lines.append(f'{field}: {value}')
        else:
            new_lines.append(line)

    with open(md_file, 'w') as f:
        f.write('\n'.join(new_lines))


def write_post_url(md_file, post_url):
    """Write the post_url value back into the markdown front matter."""
    write_front_matter_field(md_file, 'post_url', post_url)


def upload_featured_image(credentials, image_filename):
    """Upload an image to the WordPress media library and return its ID."""
    image_path = os.path.join(IMAGE_FOLDER, image_filename)

    if not os.path.exists(image_path):
        print(f"Warning: image file not found at {image_path}. Featured image will not be set.")
        return None

    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/jpeg"

    with open(image_path, 'rb') as f:
        image_data = f.read()

    req = urllib.request.Request(
        f"{WP_URL}/wp-json/wp/v2/media",
        data=image_data,
        headers=make_auth_headers(credentials, {
            "Content-Type": mime_type,
            "Content-Disposition": f'attachment; filename="{image_filename}"'
        }),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            print(f"Image uploaded: {image_filename}")
            return result['id']
    except urllib.error.HTTPError as e:
        print(f"Warning: image upload failed ({e.code} {e.reason}). Featured image will not be set.")
        return None


def get_wp_category_ids(credentials, category_names):
    """Fetch all WordPress categories and return IDs matching the given names."""
    if not category_names:
        return []

    url = f"{WP_URL}/wp-json/wp/v2/categories?per_page=100"
    req = urllib.request.Request(url, headers=make_auth_headers(credentials))

    try:
        with urllib.request.urlopen(req) as response:
            all_categories = json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"Warning: could not fetch categories ({e.code} {e.reason}). Categories will not be set.")
        return []

    # Build a case-insensitive name-to-ID map
    category_map = {cat['name'].lower(): cat['id'] for cat in all_categories}

    ids = []
    for name in category_names:
        cat_id = category_map.get(name.lower())
        if cat_id:
            ids.append(cat_id)
        else:
            print(f"Warning: category '{name}' not found in WordPress and will be skipped.")

    return ids


def main():
    if len(sys.argv) < 2:
        print("Usage: wp-draft.py file.md")
        sys.exit(1)

    md_file = sys.argv[1]

    if not os.path.exists(md_file):
        print(f"File not found: {md_file}")
        sys.exit(1)

    # Read markdown file and extract front matter
    with open(md_file, 'r') as f:
        md_content = f.read()

    title, date, excerpt, focus_keyphrase, meta_description, image, linkedin_caption, category_names = parse_front_matter(md_content)

    if not title:
        print("No title found in front matter. Using filename instead.")
        title = os.path.basename(md_file).replace('.md', '')

    # Find the corresponding _BODY_ONLY.html file
    base = md_file.replace('.md', '')
    html_file = base + '_BODY_ONLY.html'

    if not os.path.exists(html_file):
        print(f"HTML file not found: {html_file}")
        print("Run publish.sh first to generate the HTML file.")
        sys.exit(1)

    # Read HTML content
    with open(html_file, 'r') as f:
        html_content = f.read().strip()

    # Wrap in Divi shortcodes
    content = DIVI_OPEN + html_content + DIVI_CLOSE

    # Encode credentials
    password = WP_APP_PASSWORD.replace(' ', '')
    credentials = base64.b64encode(f"{WP_USER}:{password}".encode()).decode()

    # Look up category IDs from WordPress
    category_ids = get_wp_category_ids(credentials, category_names)
    if category_names and category_ids:
        print(f"Categories matched: {category_names}")

    # Upload featured image if specified
    featured_media_id = None
    if image:
        featured_media_id = upload_featured_image(credentials, image)

    # Build the post payload
    payload = {
        "title": title,
        "content": content,
        "status": "draft"
    }
    if category_ids:
        payload["categories"] = category_ids
    if excerpt:
        payload["excerpt"] = excerpt
    payload["meta"] = {}
    if focus_keyphrase:
        payload["meta"]["_yoast_wpseo_focuskw"] = focus_keyphrase
    if meta_description:
        payload["meta"]["_yoast_wpseo_metadesc"] = meta_description
    # LinkedIn plugin fields - always sent so the caption is ready in WordPress.
    # _slp_auto_post is hardcoded to "0" to prevent automatic posting.
    payload["meta"]["_slp_intro_text"] = linkedin_caption if linkedin_caption else "Text needs to be added!"
    payload["meta"]["_slp_auto_post"] = "0"
    if not linkedin_caption:
        print("Warning: linkedin_caption is empty. Placeholder text written to WordPress.")
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    data = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        f"{WP_URL}/wp-json/wp/v2/posts",
        data=data,
        headers=make_auth_headers(credentials, {"Content-Type": "application/json"}),
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read())
            print(f"Draft created successfully!")
            print(f"Title: {result.get('title', {}).get('rendered', title)}")
            print(f"Edit URL: {WP_URL}/wp-admin/post.php?post={result['id']}&action=edit")

            # Write the WordPress post ID back into the front matter so sync-post-dates.py
            # can match this file reliably in future without relying on slugs or URLs.
            wp_post_id = str(result.get('id', ''))
            if wp_post_id:
                try:
                    write_front_matter_field(md_file, 'wp_post_id', wp_post_id)
                    print(f"WordPress post ID written: {wp_post_id}")
                except Exception as e:
                    print(f"Warning: could not write wp_post_id back to file: {e}")

            # Use the permalink WordPress returns directly - it is always correct.
            # Only fall back to constructing a URL if WordPress did not return one.
            post_url = result.get('link', '').rstrip('/')
            slug = result.get('slug', '') or result.get('generated_slug', '')
            print(f"Slug returned by WordPress: '{slug}'")

            if post_url:
                post_url = post_url + '/'
                try:
                    write_post_url(md_file, post_url)
                    print(f"Post URL written: {post_url}")
                except Exception as e:
                    print(f"Warning: could not write post_url back to file: {e}")
            elif slug:
                # Fallback: construct URL from slug and year extracted from the date field.
                # Date field should be YYYY-MM-DD. Extract the 4-digit year safely.
                import re
                year_match = re.match(r'(\d{4})-\d{2}-\d{2}', date or '')
                year = year_match.group(1) if year_match else '2026'
                post_url = f"{WP_URL}/{year}/{slug}/"
                try:
                    write_post_url(md_file, post_url)
                    print(f"Warning: WordPress returned no link. Constructed URL from slug: {post_url}")
                except Exception as e:
                    print(f"Warning: could not write post_url back to file: {e}")
            else:
                # Last resort: derive slug from filename.
                import re
                basename = os.path.basename(md_file)
                derived = re.sub(r'^[A-Za-z0-9]{6}_', '', basename)
                derived = re.sub(r'_DRAFT\.md$', '', derived)
                derived = re.sub(r'_', '-', derived).lower()
                year_match = re.match(r'(\d{4})-\d{2}-\d{2}', date or '')
                year = year_match.group(1) if year_match else '2026'
                if derived:
                    post_url = f"{WP_URL}/{year}/{derived}/"
                    try:
                        write_post_url(md_file, post_url)
                        print(f"Warning: WordPress returned no link or slug. Used filename-derived URL: {post_url}")
                    except Exception as e:
                        print(f"Warning: could not write post_url back to file: {e}")
                else:
                    print("Warning: could not determine post_url. Update it manually after the post is published.")

    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
