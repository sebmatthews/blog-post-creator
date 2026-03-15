#!/usr/bin/env python3

# twitter-post.py
# Posts a completed blog post to Twitter/X with a resized header image.
# Reads twitter_caption, twitter_hashtags, post_url, and image from the
# markdown front matter. Assembles the tweet as caption + URL + hashtags,
# validates the length before posting (URLs count as 23 chars after t.co
# wrapping regardless of actual length), then uploads the image and posts.
#
# Usage:
#   python3 scripts/twitter-post.py file.md
#
# Prerequisites:
#   - The post must be published on WordPress with post_url populated.
#   - scripts/twitter_config.py must contain valid API credentials.
#   - Pillow must be installed: pip install Pillow

import sys
import os
import json
import hmac
import hashlib
import base64
import time
import uuid
import io
import urllib.request
import urllib.parse
import urllib.error

# Target dimensions for Twitter feed images (16:9)
TWITTER_IMAGE_WIDTH = 1200
TWITTER_IMAGE_HEIGHT = 675

# Twitter counts all URLs as this many characters after t.co wrapping
TWITTER_URL_LENGTH = 23

# Maximum tweet length
TWITTER_MAX_LENGTH = 280

# Folder where blog header images are stored.
# When run via the Obsidian plugin, BLOG_IMAGE_FOLDER is set by the plugin settings.
# When run standalone, falls back to the path below.
IMAGE_FOLDER = os.environ.get('BLOG_IMAGE_FOLDER', '/users/sebmatthews/onedrive/holder/content/writing/2026/blog posts/imagery')

# Twitter/X API endpoints
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
TWEETS_URL = "https://api.x.com/2/tweets"

# Load credentials from twitter_config.py in the same folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twitter_config import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_TOKEN_SECRET,
)


def parse_front_matter(content):
    """Extract title, twitter_caption, twitter_hashtags, post_url, and image
    from YAML front matter."""
    title = None
    twitter_caption = None
    twitter_hashtags = []
    post_url = None
    image = None

    lines = content.split('\n')
    in_front_matter = False
    in_hashtags = False

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
            in_hashtags = False
        elif line.startswith('twitter_caption:'):
            twitter_caption = line[16:].strip()
            in_hashtags = False
        elif line.startswith('twitter_hashtags:'):
            in_hashtags = True
        elif in_hashtags and line.strip().startswith('- '):
            value = line.strip()[2:].strip()
            if value and value != '-':
                twitter_hashtags.append(value)
        elif line.startswith('post_url:'):
            post_url = line[9:].strip()
            in_hashtags = False
        elif line.startswith('image:'):
            image = line[6:].strip()
            in_hashtags = False
        elif not line.startswith(' ') and not line.startswith('\t'):
            in_hashtags = False

    return title, twitter_caption, twitter_hashtags, post_url, image


def build_tweet_text(twitter_caption, post_url, twitter_hashtags):
    """Assemble the full tweet text from its parts.

    Returns (tweet_text, display_length) where display_length applies
    Twitter's URL counting rule: all URLs count as TWITTER_URL_LENGTH
    characters regardless of actual length.
    """
    hashtags_str = ' '.join(f'#{tag}' for tag in twitter_hashtags if tag)

    parts = [twitter_caption]
    if post_url:
        parts.append(post_url)
    if hashtags_str:
        parts.append(hashtags_str)

    tweet_text = ' '.join(parts)

    # Calculate display length using Twitter's URL rule
    display_len = len(twitter_caption)
    if post_url:
        display_len += 1 + TWITTER_URL_LENGTH       # space + 23-char t.co URL
    if hashtags_str:
        display_len += 1 + len(hashtags_str)         # space + hashtags

    return tweet_text, display_len


def resize_image(image_path):
    """Resize the header image to Twitter optimal dimensions and return PNG bytes."""
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow is not installed. Run: pip install Pillow")
        sys.exit(1)

    with Image.open(image_path) as img:
        img = img.convert('RGB')
        img = img.resize((TWITTER_IMAGE_WIDTH, TWITTER_IMAGE_HEIGHT), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()


def make_oauth_header(method, url, extra_params=None):
    """Generate an OAuth 1.0a Authorization header for the given request.

    extra_params should contain any URL query parameters or form fields that
    need to be included in the signature base string. For JSON body requests
    and multipart uploads, pass None as these are not signed.
    """
    oauth_params = {
        'oauth_consumer_key': TWITTER_API_KEY,
        'oauth_nonce': uuid.uuid4().hex,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str(int(time.time())),
        'oauth_token': TWITTER_ACCESS_TOKEN,
        'oauth_version': '1.0',
    }

    # Combine OAuth params with any additional params for the signature
    all_params = dict(oauth_params)
    if extra_params:
        all_params.update(extra_params)

    # Percent-encode, sort, and build the parameter string
    encoded_params = sorted(
        (urllib.parse.quote(str(k), safe=''), urllib.parse.quote(str(v), safe=''))
        for k, v in all_params.items()
    )
    param_string = '&'.join(f'{k}={v}' for k, v in encoded_params)

    # Build the signature base string
    base_string = '&'.join([
        method.upper(),
        urllib.parse.quote(url, safe=''),
        urllib.parse.quote(param_string, safe=''),
    ])

    # Build the signing key from consumer secret and token secret
    signing_key = (
        urllib.parse.quote(TWITTER_API_SECRET, safe='') + '&' +
        urllib.parse.quote(TWITTER_ACCESS_TOKEN_SECRET, safe='')
    )

    # Sign with HMAC-SHA1
    signature = base64.b64encode(
        hmac.new(
            signing_key.encode('ascii'),
            base_string.encode('ascii'),
            hashlib.sha1,
        ).digest()
    ).decode('ascii')

    oauth_params['oauth_signature'] = signature

    # Format as Authorization header value
    header_parts = ', '.join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f'OAuth {header_parts}'


def upload_image(image_bytes):
    """Upload image bytes to the Twitter/X media API.

    Uses simple multipart upload (suitable for images). Returns the media_id
    string to include in the tweet payload.
    """
    boundary = uuid.uuid4().hex

    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="media"; filename="image.png"\r\n'
        f'Content-Type: image/png\r\n\r\n'
    ).encode('utf-8') + image_bytes + f'\r\n--{boundary}--\r\n'.encode('utf-8')

    # Multipart body fields are not included in the OAuth signature
    auth_header = make_oauth_header('POST', MEDIA_UPLOAD_URL)

    req = urllib.request.Request(
        MEDIA_UPLOAD_URL,
        data=body,
        headers={
            'Authorization': auth_header,
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        },
        method='POST',
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())
        media_id = result['data']['id']
        print(f"Image uploaded. Media ID: {media_id}")
        return media_id


def create_tweet(tweet_text, media_id=None):
    """Post a tweet. Returns the tweet ID on success."""
    payload = {'text': tweet_text}
    if media_id:
        payload['media'] = {'media_ids': [media_id]}

    data = json.dumps(payload).encode('utf-8')

    # JSON body is not included in the OAuth signature
    auth_header = make_oauth_header('POST', TWEETS_URL)

    req = urllib.request.Request(
        TWEETS_URL,
        data=data,
        headers={
            'Authorization': auth_header,
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())
        return result['data']['id']


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/twitter-post.py file.md")
        sys.exit(1)

    md_file = sys.argv[1]

    if not os.path.exists(md_file):
        print(f"File not found: {md_file}")
        sys.exit(1)

    with open(md_file, 'r') as f:
        md_content = f.read()

    title, twitter_caption, twitter_hashtags, post_url, image = parse_front_matter(md_content)

    # Pre-flight checks
    if not twitter_caption:
        print("Error: twitter_caption is empty. Populate it in the front matter before posting.")
        sys.exit(1)

    if not post_url:
        print("Error: post_url is empty. Run wp-draft.py and ensure the post is live before posting to Twitter/X.")
        sys.exit(1)

    # Assemble tweet and validate length
    tweet_text, display_len = build_tweet_text(twitter_caption, post_url, twitter_hashtags)

    print(f"Assembled tweet ({display_len}/{TWITTER_MAX_LENGTH} chars):")
    print(f"  {tweet_text}")
    print()

    if display_len > TWITTER_MAX_LENGTH:
        print(f"Error: tweet is {display_len} characters, which exceeds the {TWITTER_MAX_LENGTH} character limit.")
        print(f"  Caption:  {len(twitter_caption)} chars")
        print(f"  URL:      {TWITTER_URL_LENGTH} chars (t.co wrapped)")
        if twitter_hashtags:
            hashtags_str = ' '.join(f'#{tag}' for tag in twitter_hashtags)
            print(f"  Hashtags: {len(hashtags_str)} chars  ({hashtags_str})")
        overage = display_len - TWITTER_MAX_LENGTH
        print(f"Shorten twitter_caption by at least {overage} character(s) and try again.")
        sys.exit(1)

    # Upload image if specified
    media_id = None
    if image:
        image_path = os.path.join(IMAGE_FOLDER, image)
        if os.path.exists(image_path):
            print(f"Resizing and uploading image: {image}")
            try:
                image_bytes = resize_image(image_path)
                media_id = upload_image(image_bytes)
            except urllib.error.HTTPError as e:
                print(f"Warning: image upload failed ({e.code} {e.reason}). Posting without image.")
                print(e.read().decode())
        else:
            print(f"Warning: image not found at {image_path}. Posting without image.")

    # Post the tweet
    try:
        tweet_id = create_tweet(tweet_text, media_id)
        print(f"Tweet posted successfully!")
        print(f"Tweet ID: {tweet_id}")
        print(f"View at: https://x.com/i/web/status/{tweet_id}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        if e.code == 503:
            print(f"X returned 503. Waiting 10 seconds then checking whether the tweet posted...")
            time.sleep(10)
            try:
                tweet_id = create_tweet(tweet_text, media_id)
                print(f"Tweet posted successfully on retry!")
                print(f"Tweet ID: {tweet_id}")
                print(f"View at: https://x.com/i/web/status/{tweet_id}")
            except urllib.error.HTTPError as e2:
                error_body2 = e2.read().decode()
                if e2.code == 403 and 'duplicate' in error_body2.lower():
                    print(f"Confirmed: the original tweet posted successfully.")
                    print(f"The retry was rejected as a duplicate, which means the first request went through.")
                    print(f"Check your X profile to find it: https://x.com")
                else:
                    print(f"Uncertain: original returned 503, retry returned {e2.code}.")
                    print(f"Check your X profile before retrying to avoid posting a duplicate.")
                    print(f"Retry response: {error_body2}")
            except urllib.error.URLError as e2:
                print(f"Uncertain: original returned 503, retry failed with a network error ({e2.reason}).")
                print(f"Check your X profile before retrying to avoid posting a duplicate.")
        else:
            print(f"Error posting tweet: {e.code} {e.reason}")
            print(error_body)
            sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error: {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
