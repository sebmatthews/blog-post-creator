#!/usr/bin/env python3

# sync-post-dates.py
#
# Queries the WordPress API for all published and scheduled posts and
# checks that each local markdown file has the correct date prefix in
# its filename and front matter.  Any file whose prefix does not match
# the WordPress publish date is renamed and its front matter date field
# is updated to match.
#
# Matching order (most to least reliable):
#   1. wp_post_id field in front matter  (written by wp-draft.py on upload)
#   2. post_url field in front matter    (written by wp-draft.py on upload)
#   3. Slug derived from filename        (fallback for older files)
#
# Files with an XXXXXX prefix that have now been scheduled in WordPress
# will be picked up automatically and renamed to the correct YYMMDD prefix.
#
# Usage:
#   python3 sync-post-dates.py           # apply all changes
#   python3 sync-post-dates.py --dry-run # preview changes, nothing written

import os
import re
import sys
import json
import urllib.request
import urllib.error
import base64

# ---------------------------------------------------------------------------
# Config - credentials come from wp_config.py in the same folder
# ---------------------------------------------------------------------------

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    from wp_config import WP_URL, WP_USER, WP_APP_PASSWORD
except ImportError:
    print("Error: wp_config.py not found in the scripts folder.")
    sys.exit(1)

# Blog posts folder.
# When run via the Obsidian plugin, BLOG_POSTS_DIR is set by the plugin settings.
# When run standalone, falls back to one level up from the scripts folder.
POSTS_DIR = os.environ.get('BLOG_POSTS_DIR', os.path.dirname(script_dir))

DRY_RUN = '--dry-run' in sys.argv

# ---------------------------------------------------------------------------
# WordPress API
# ---------------------------------------------------------------------------

def get_wp_posts():
    """Fetch all published and scheduled posts from WordPress."""
    password = WP_APP_PASSWORD.replace(' ', '')
    credentials = base64.b64encode(f"{WP_USER}:{password}".encode()).decode()
    url = (
        f"{WP_URL}/wp-json/wp/v2/posts"
        f"?status=publish,future&per_page=100&orderby=date&order=asc"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {credentials}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            posts = json.loads(resp.read())
            print(f"WordPress: {len(posts)} published/scheduled post(s) found.")
            return posts
    except urllib.error.HTTPError as e:
        print(f"WordPress API error: {e.code} {e.reason}")
        print(e.read().decode())
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}")
        sys.exit(1)


def build_indexes(wp_posts):
    """
    Build three lookup dicts from the WordPress post list:
      by_id   : str(post_id) -> post dict
      by_url  : normalised link URL -> post dict
      by_slug : slug string -> post dict
    """
    by_id   = {}
    by_url  = {}
    by_slug = {}
    for post in wp_posts:
        post_id = str(post.get('id', ''))
        slug    = post.get('slug', '')
        link    = post.get('link', '').rstrip('/')
        if post_id:
            by_id[post_id] = post
        if slug:
            by_slug[slug] = post
        if link:
            by_url[link]         = post
            by_url[link + '/']   = post
    return by_id, by_url, by_slug


# ---------------------------------------------------------------------------
# Front matter helpers
# ---------------------------------------------------------------------------

def read_front_matter_fields(filepath):
    """
    Parse the YAML front matter of a markdown file.
    Returns a dict of simple key:value pairs (skips list items and indented lines).
    """
    fields = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except OSError:
        return fields

    if not content.startswith('---'):
        return fields

    end = content.find('\n---', 3)
    if end == -1:
        return fields

    for line in content[3:end].splitlines():
        if line and not line.startswith(' ') and not line.startswith('-') and ':' in line:
            key, _, val = line.partition(':')
            fields[key.strip()] = val.strip()

    return fields


def update_front_matter_field(filepath, field, value):
    """
    Replace the value of a top-level front matter field in the file.
    Returns True if the file was changed.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = re.sub(
        rf'^{re.escape(field)}:[ ]*.*$',
        rf'{field}: {value}',
        content,
        count=1,
        flags=re.MULTILINE
    )

    if new_content == content:
        return False

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


# ---------------------------------------------------------------------------
# Filename / date helpers
# ---------------------------------------------------------------------------

def slug_from_filename(filename):
    """
    Derive a WordPress-style slug from the markdown filename.
    e.g. '260208_orbital_datacentres_real_or_fantasy_DRAFT.md'
      -> 'orbital-datacentres-real-or-fantasy'
    """
    name = re.sub(r'^[A-Za-z0-9X]{6}_', '', filename)
    name = re.sub(r'_DRAFT\.md$', '', name, flags=re.IGNORECASE)
    return name.replace('_', '-').lower()


def prefix_from_wp_date(date_str):
    """
    Convert a WordPress date string (e.g. '2026-04-09T09:00:00')
    to a YYMMDD filename prefix (e.g. '260409').
    Returns None if the date is not a real publish date (e.g. 1970-01-01
    which WordPress uses for unscheduled drafts).
    """
    if not date_str:
        return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        year, month, day = m.groups()
        if year == '1970':
            return None
        return year[2:] + month + day   # e.g. '260409'
    return None


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def sync():
    wp_posts = get_wp_posts()
    by_id, by_url, by_slug = build_indexes(wp_posts)

    # Find all markdown files whose names start with a 6-character prefix
    md_files = sorted(
        f for f in os.listdir(POSTS_DIR)
        if f.endswith('.md') and re.match(r'^[A-Za-z0-9X]{6}_', f)
    )
    print(f"Local posts: {len(md_files)} markdown file(s) found.\n")

    renamed         = []
    dates_updated   = []
    status_updated  = []
    no_match        = []
    already_correct = []
    no_wp_date      = []

    for filename in md_files:
        filepath       = os.path.join(POSTS_DIR, filename)
        fields         = read_front_matter_fields(filepath)
        current_prefix = filename[:6]

        # -----------------------------------------------------------------
        # Step 1 - find the matching WordPress post
        # -----------------------------------------------------------------
        wp_post      = None
        match_method = None

        # Primary: wp_post_id (most reliable - set by wp-draft.py on upload)
        wp_post_id = fields.get('wp_post_id', '').strip()
        if wp_post_id and wp_post_id in by_id:
            wp_post      = by_id[wp_post_id]
            match_method = 'wp_post_id'

        # Secondary: post_url in front matter
        if not wp_post:
            post_url = fields.get('post_url', '').strip().rstrip('/')
            if post_url and post_url in by_url:
                wp_post      = by_url[post_url]
                match_method = 'post_url'

        # Tertiary: slug derived from filename
        if not wp_post:
            slug = slug_from_filename(filename)
            if slug in by_slug:
                wp_post      = by_slug[slug]
                match_method = 'slug'

        if not wp_post:
            no_match.append(filename)
            continue

        # -----------------------------------------------------------------
        # Step 2 - sync status field
        # WordPress returns 'publish' or 'future'. We only promote to
        # 'publish' when WordPress confirms the post is live. Scheduled
        # posts (future) are left as 'draft' until they go live.
        # -----------------------------------------------------------------
        wp_status    = wp_post.get('status', '')
        local_status = fields.get('status', '').strip()

        if wp_status == 'publish' and local_status != 'publish':
            print(f"  STATUS  {filename}")
            print(f"          {local_status} -> publish  (matched via: {match_method})")
            if not DRY_RUN:
                # Use the current filepath which may change below if renamed
                update_front_matter_field(filepath, 'status', 'publish')
                status_updated.append(filename)
            print()

        # -----------------------------------------------------------------
        # Step 3 - work out what the prefix should be
        # -----------------------------------------------------------------
        wp_date         = wp_post.get('date', '')
        expected_prefix = prefix_from_wp_date(wp_date)

        if not expected_prefix:
            # Post exists in WordPress but has no real publish date yet
            no_wp_date.append(filename)
            continue

        # -----------------------------------------------------------------
        # Step 4 - rename and update date if prefix is wrong
        # -----------------------------------------------------------------
        if current_prefix == expected_prefix:
            already_correct.append(filename)
            continue

        new_filename = expected_prefix + filename[6:]
        old_path     = os.path.join(POSTS_DIR, filename)
        new_path     = os.path.join(POSTS_DIR, new_filename)
        new_date     = f"20{expected_prefix[:2]}-{expected_prefix[2:4]}-{expected_prefix[4:6]}"

        print(f"  RENAME  {filename}")
        print(f"       -> {new_filename}")
        print(f"          matched via: {match_method} | WP date: {wp_date[:10]}")

        if not DRY_RUN:
            os.rename(old_path, new_path)
            renamed.append((filename, new_filename))

            date_changed = update_front_matter_field(new_path, 'date', new_date)
            if date_changed:
                dates_updated.append(new_filename)
                print(f"          front matter date updated to {new_date}")
        else:
            renamed.append((filename, new_filename))
            print(f"          front matter date would be updated to {new_date}")

        print()

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    label = 'Would rename' if DRY_RUN else 'Renamed'
    print(f"\n{'=== DRY RUN - no files were changed ===' if DRY_RUN else '=== Complete ==='}")
    print(f"  {label:<22} {len(renamed)}")
    if not DRY_RUN:
        print(f"  {'Dates updated':<22} {len(dates_updated)}")
        print(f"  {'Status updated':<22} {len(status_updated)}")
    print(f"  {'Already correct':<22} {len(already_correct)}")
    print(f"  {'No WordPress match':<22} {len(no_match)}")
    if no_match:
        for f in no_match:
            print(f"    - {f}")
    print(f"  {'No WP date assigned':<22} {len(no_wp_date)}")
    if no_wp_date:
        for f in no_wp_date:
            print(f"    - {f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if DRY_RUN:
        print("=== DRY RUN - no files will be changed ===\n")
    sync()
