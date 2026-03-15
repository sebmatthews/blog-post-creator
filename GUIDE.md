# Blog Post Creator — Setup & Usage Guide

A publishing pipeline for Obsidian that takes a markdown post through image generation, HTML conversion, WordPress draft creation, and social posting — all from the command palette.

Scripts are bundled inside the plugin — no separate scripts folder to manage or configure.

---

## Contents

- [Prerequisites](#prerequisites)
- [Building the plugin](#building-the-plugin)
- [Installing into Obsidian](#installing-into-obsidian)
- [Configuring the plugin](#configuring-the-plugin)
- [Front matter reference](#front-matter-reference)
- [Commands and workflow](#commands-and-workflow)
- [Updating after code changes](#updating-after-code-changes)
- [Running scripts standalone](#running-scripts-standalone)

---

## Prerequisites

| Tool | Required by | Install |
|---|---|---|
| Node.js + npm | Plugin build | [nodejs.org](https://nodejs.org) |
| Python 3 | All `.py` scripts | `brew install python` |
| pandoc | `publish.sh` | `brew install pandoc` |
| Pillow | `linkedin-post.py`, `twitter-post.py` | `pip install Pillow` |

---

## Building the plugin

```bash
cd obsidian-plugin
npm install
npm run build
```

This produces `obsidian-plugin/main.js` with all scripts bundled inside it.

---

## Installing into Obsidian

1. Create the plugin folder inside your vault:

```bash
mkdir -p /path/to/your/vault/.obsidian/plugins/blog-post-creator
```

2. Copy the two required files:

```bash
cp obsidian-plugin/main.js       /path/to/your/vault/.obsidian/plugins/blog-post-creator/
cp obsidian-plugin/manifest.json /path/to/your/vault/.obsidian/plugins/blog-post-creator/
```

3. In Obsidian: **Settings → Community Plugins → enable "Blog Post Creator"**

> If you see a warning about community plugins being disabled, click **Turn on community plugins** first.

When the plugin loads it automatically extracts the bundled scripts to `.obsidian/plugins/blog-post-creator/scripts/` inside your vault. These are refreshed every time Obsidian starts, so updating the plugin always brings the latest scripts with it.

---

## Configuring the plugin

Go to **Settings → Blog Post Creator** and fill in all sections.

### General

| Field | Value |
|---|---|
| Python executable | `python3` or full path e.g. `/opt/homebrew/bin/python3` |
| Image folder path | Absolute path to the folder where blog header images are stored and generated |

### WordPress

| Field | Where to get it |
|---|---|
| Site URL | e.g. `https://yoursite.com` |
| Username | Your WordPress username |
| Application password | WP Admin → Users → Your Profile → Application Passwords |

### LinkedIn

| Field | Where to get it |
|---|---|
| Access token | [linkedin.com/developers/tools/oauth/token-generator](https://www.linkedin.com/developers/tools/oauth/token-generator) — tick all scopes |
| Person ID | Shown on the same token generator page after generating |

> LinkedIn tokens expire after **60 days**. Return to the token generator to renew.

### Twitter / X

| Field | Where to get it |
|---|---|
| API key | [developer.x.com](https://developer.x.com) → your app → Keys and Tokens |
| API secret | As above |
| Access token | As above — requires **Read and Write** app permissions |
| Access token secret | As above |

### OpenAI

| Field | Where to get it |
|---|---|
| API key | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

---

## Front matter reference

Each script reads specific fields from the YAML front matter at the top of your markdown file. A full example:

```yaml
---
title: Your Post Title
date: 2026-03-15
status: draft
excerpt: A short summary of the post shown in WordPress and used as a fallback caption.
focus_keyphrase: your seo keyphrase
meta_description: The meta description for search engines.
image: your-post-image.png
image_prompt: A photorealistic editorial scene showing...
category:
  - Technology
  - AI
tags:
  - tech
  - AI
linkedin_caption: The text of your LinkedIn post.
linkedin_publish_date:
twitter_caption: Your tweet text (keep under ~220 chars to leave room for URL and hashtags).
twitter_hashtags:
  - tech
  - AI
post_url:
wp_post_id:
---
```

| Field | Used by | Notes |
|---|---|---|
| `title` | `wp-draft.py` | Falls back to filename if missing |
| `date` | `wp-draft.py`, `sync-post-dates.py` | Format: `YYYY-MM-DD` |
| `status` | `sync-post-dates.py` | Updated to `publish` automatically when post goes live |
| `excerpt` | `wp-draft.py`, `linkedin-post.py` | Shown in WP excerpt field; fallback LinkedIn caption |
| `focus_keyphrase` | `wp-draft.py` | Written to Yoast SEO field |
| `meta_description` | `wp-draft.py` | Written to Yoast SEO field |
| `image` | `wp-draft.py`, `linkedin-post.py`, `twitter-post.py` | Filename only, e.g. `my-image.png` |
| `image_prompt` | `generate-image.py` | Post-specific part of the image prompt — style prefix is prepended automatically |
| `category` | `wp-draft.py` | List of category names matching WordPress exactly |
| `tags` | `linkedin-post.py` | Turned into `#hashtags` on LinkedIn |
| `linkedin_caption` | `wp-draft.py`, `linkedin-post.py` | Written to WP LinkedIn plugin field and used as LinkedIn post text |
| `linkedin_publish_date` | `linkedin-post.py` | Written back automatically on publish; guards against re-posting |
| `twitter_caption` | `twitter-post.py` | Tweet text, not including URL or hashtags |
| `twitter_hashtags` | `twitter-post.py` | List of hashtags without the `#` |
| `post_url` | `wp-draft.py`, `linkedin-post.py`, `twitter-post.py` | Written back automatically by `wp-draft.py` |
| `wp_post_id` | `wp-draft.py`, `sync-post-dates.py` | Written back automatically by `wp-draft.py` |

---

## Commands and workflow

All commands are available via `Cmd+P` → type **Blog Post Creator**.

### Typical order

#### 1. Generate header image
**Command:** `Blog Post Creator: Generate header image`

Reads `image_prompt` from front matter, prepends a standard style prefix, calls the OpenAI image API, and saves the result to the image folder configured in settings. Requires `image` and `image_prompt` to be set in front matter.

---

#### 2. Convert to HTML
**Command:** `Blog Post Creator: Convert to HTML`

Uses pandoc to convert the current markdown file to an HTML fragment and collapses line wrapping for clean pasting into Divi. Produces a `_BODY_ONLY.html` file alongside the markdown file.

> Must be run before **Push to WordPress**.

---

#### 3. Push to WordPress as draft
**Command:** `Blog Post Creator: Push to WordPress as draft`

Requires the `_BODY_ONLY.html` file to exist. Wraps the HTML in Divi shortcodes, uploads the featured image to the WordPress media library, creates a draft post, and writes `wp_post_id` and `post_url` back into the front matter.

---

#### 4. Review and schedule in WordPress

Open the WordPress draft in your browser, review it, and set a publish date. The post does not need to be live before posting to social.

---

#### 5. Post to LinkedIn
**Command:** `Blog Post Creator: Post to LinkedIn`

Requires `post_url` to be set in front matter (written by step 3). Resizes the header image to LinkedIn dimensions (1200×627), uploads it, and creates a public article post using `linkedin_caption`. Writes `linkedin_publish_date` back to front matter to prevent re-posting.

---

#### 6. Post to Twitter / X
**Command:** `Blog Post Creator: Post to Twitter/X`

Requires `post_url` to be set. Assembles the tweet from `twitter_caption`, `post_url`, and `twitter_hashtags`. Validates the assembled length against Twitter's 280-character limit (URLs counted as 23 chars per t.co rules) before posting. Resizes and uploads the header image at 1200×675.

---

#### 7. Sync post dates
**Command:** `Blog Post Creator: Sync post dates from WordPress`

Does not require an open file. Queries the WordPress API for all published and scheduled posts, then renames any local markdown files whose `YYMMDD_` filename prefix does not match the WordPress publish date. Also updates the `date` field in front matter and promotes `status` to `publish` for live posts.

Run this after WordPress publishes a scheduled post to keep local filenames in sync.

---

## Updating after code changes

After editing `main.ts` or any script in `scripts/`:

```bash
cd obsidian-plugin
npm run build
cp main.js /path/to/your/vault/.obsidian/plugins/blog-post-creator/
```

Then in Obsidian: disable and re-enable the plugin, or restart Obsidian. The updated scripts are extracted automatically on next load.

---

## Running scripts standalone

All scripts can still be run directly from the terminal without the plugin. You will need to create the config files manually by copying the `.example` files:

```bash
cd scripts
cp wp_config.py.example wp_config.py
cp linkedin_config.py.example linkedin_config.py
cp twitter_config.py.example twitter_config.py
cp openai_config.py.example openai_config.py
# edit each file and fill in your credentials
```

Then run as normal:

```bash
python3 scripts/wp-draft.py path/to/post.md
bash scripts/publish.sh path/to/post.md
python3 scripts/sync-post-dates.py --dry-run
```

The `BLOG_IMAGE_FOLDER` environment variable can be set to override the default image folder path:

```bash
BLOG_IMAGE_FOLDER="/path/to/imagery" python3 scripts/generate-image.py post.md
```

> The config files are gitignored and will never be committed.
