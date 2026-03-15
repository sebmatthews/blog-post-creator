# Blog Post Creator

An Obsidian plugin that connects your markdown writing to a full blog publishing pipeline. From a single note you can generate a header image, push the post to WordPress as a draft, and share to LinkedIn and Twitter/X — all from the Obsidian command palette.

> **Desktop only.** The plugin runs Python scripts and requires a local Python installation. It has only been tested on Mac and will likely not work on PC.

---

## Contents

- [How it works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Option A — Install from release](#option-a--install-from-release)
  - [Option B — Build from source](#option-b--build-from-source)
- [Configuration](#configuration)
  - [General settings](#general-settings)
  - [WordPress](#wordpress)
  - [LinkedIn](#linkedin)
  - [Twitter / X](#twitter--x)
  - [OpenAI](#openai)
- [Front matter reference](#front-matter-reference)
- [Commands and workflow](#commands-and-workflow)
- [Syncing post dates](#syncing-post-dates)
- [Running scripts standalone](#running-scripts-standalone)
- [Updating the plugin](#updating-the-plugin)
- [Licence](#licence)

---

## How it works

The plugin bundles a set of Python scripts inside `main.js`. When Obsidian loads the plugin, those scripts are extracted to `.obsidian/plugins/blog-post-creator/scripts/` inside your vault. Each command in the palette runs the relevant script, passing in the path to your open note and your saved credentials.

Credentials are stored in the plugin's settings (`data.json`) and written to temporary config files immediately before each script run. The config files are deleted afterwards and are gitignored so they are never committed.

```
Obsidian note (Markdown)
        │
        ├─ Generate header image   →  OpenAI DALL-E → local image folder
        │
        ├─ Convert to HTML         →  _BODY_ONLY.html alongside the note
        │
        ├─ Push to WordPress       →  WordPress REST API (draft) → writes wp_post_id + post_url to front matter
        │
        ├─ Post to LinkedIn        →  LinkedIn API (article post with image)
        │
        ├─ Post to Twitter / X     →  Twitter API v2 (tweet with image)
        │
        └─ Sync post dates         →  Queries WP API → renames YYMMDD_ prefixed local files to match publish date
```

---

## Prerequisites

| Tool | Required by | How to install |
|---|---|---|
| Python 3 | All scripts | [python.org](https://www.python.org/downloads/) or `brew install python` |
| `markdown` (pip) | Convert to HTML | `pip install markdown` |
| `Pillow` (pip) | LinkedIn + Twitter image resizing | `pip install Pillow` |
| Node.js + npm | Building from source only | [nodejs.org](https://nodejs.org) |

To confirm your Python installation is working:

```bash
python3 --version
```

---

## Installation

### Option A — Install from release

This is the easiest approach. No Node.js or build step required.

1. Go to the [Releases page](https://github.com/sebmatthews/blog-post-creator/releases) and download `main.js` and `manifest.json` from the latest release.

2. Create the plugin folder inside your vault (replace the path with your own):

   ```bash
   mkdir -p "/path/to/your/vault/.obsidian/plugins/blog-post-creator"
   ```

3. Copy both downloaded files into that folder.

4. In Obsidian: **Settings → Community Plugins → enable Blog Post Creator**.

   > If you see a warning about community plugins being disabled, click **Turn on community plugins** first.

The plugin extracts its bundled scripts to the `scripts/` subfolder on load. They are refreshed every time Obsidian starts, so you never need to manage them manually.

---

### Option B — Build from source

Use this approach if you want to modify the plugin or scripts.

```bash
git clone https://github.com/sebmatthews/blog-post-creator.git
cd blog-post-creator/obsidian-plugin
npm install
npm run build
```

This produces `obsidian-plugin/main.js`. Copy it plus `obsidian-plugin/manifest.json` into your vault's plugin folder as described in Option A above.

---

## Configuration

After enabling the plugin, go to **Settings → Blog Post Creator** and fill in the sections below.

### General settings

| Field | Description |
|---|---|
| Python executable | The command or full path used to run Python 3. Try `python3` first; if that fails use the full path such as `/opt/homebrew/bin/python3` |
| Image folder path | Absolute path to the folder where generated blog header images are stored |
| Blog posts folder path | Absolute path to the folder containing your markdown blog post files (used by Sync post dates) |

---

### WordPress

The plugin communicates with your WordPress site using the REST API and an Application Password. Standard account passwords do not work here.

| Field | Description |
|---|---|
| Site URL | Your WordPress site, e.g. `https://yoursite.com` |
| Username | Your WordPress login username |
| Application password | A per-app password generated from your profile |

**How to create a WordPress Application Password:**

1. Log in to WordPress Admin.
2. Go to **Users → Your Profile**.
3. Scroll to **Application Passwords**.
4. Enter a name (e.g. `Blog Post Creator`) and click **Add New Application Password**.
5. Copy the generated password (it is shown only once). Spaces in the password are fine — the plugin strips them before use.

---

### LinkedIn

The plugin uses the LinkedIn Share API to post articles with an image.

| Field | Description |
|---|---|
| Access token | An OAuth 2.0 access token with posting permissions |
| Person ID | Your LinkedIn member ID, used to post on your behalf |

**How to get a LinkedIn access token:**

1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps) and create an app (or use an existing one).
2. Under **Products**, request access to **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. Once approved, go to the [OAuth Token Generator](https://www.linkedin.com/developers/tools/oauth/token-generator).
4. Select your app, tick all available scopes, and click **Request access token**.
5. Copy the **Access Token** and **Member ID (Person ID)** shown on the results page.

> **Tokens expire after 60 days.** Return to the token generator to renew — the process is the same.

---

### Twitter / X

The plugin posts tweets using Twitter API v2 with OAuth 1.0a (user context), which allows posting on your behalf.

| Field | Description |
|---|---|
| API key | Consumer key for your Twitter app |
| API secret | Consumer secret for your Twitter app |
| Access token | Token granting access to your specific account |
| Access token secret | Secret paired with the access token |

**How to get Twitter API credentials:**

1. Go to [developer.x.com](https://developer.x.com) and sign in with your Twitter account.
2. Create a Project and an App inside it.
3. Under **App Settings → User Authentication Settings**, set **App permissions** to **Read and Write**. This is required to post tweets.
4. Go to **Keys and Tokens** for your app.
5. Copy the **API Key** and **API Key Secret** from the Consumer Keys section.
6. Under **Authentication Tokens**, generate an **Access Token and Secret** (make sure it shows "Read and Write" permissions). Copy both values.

> The Access Token and Secret are tied to the specific account that generates them. If you need to post to a different account, generate new tokens while logged in as that account.

---

### OpenAI

The plugin uses DALL-E to generate header images.

| Field | Description |
|---|---|
| API key | Your OpenAI API key |

**How to get an OpenAI API key:**

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys) and sign in.
2. Click **Create new secret key**.
3. Copy the key — it is shown only once.

> Image generation uses the `dall-e-3` model and incurs API costs per image. Check [openai.com/pricing](https://openai.com/pricing) for current rates.

---

## Front matter reference

Each post is a standard Obsidian markdown note with a YAML front matter block at the top. A complete example:

```yaml
---
title: Your Post Title
date: 2026-03-15
status: draft
excerpt: A short summary shown in WordPress and used as a fallback caption.
focus_keyphrase: your seo keyphrase
meta_description: The meta description for search engines.
image: your-post-image.png
image_prompt: A photorealistic editorial scene showing a developer at a glowing monitor...
category:
  - Technology
  - AI
tags:
  - tech
  - AI
linkedin_caption: The text of your LinkedIn post.
linkedin_publish_date:
twitter_caption: Your tweet text — keep under ~220 chars to leave room for URL and hashtags.
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
| `status` | `sync-post-dates.py` | Updated to `publish` automatically when post goes live in WordPress |
| `excerpt` | `wp-draft.py`, `linkedin-post.py` | Written to WordPress excerpt field; used as fallback LinkedIn caption if `linkedin_caption` is empty |
| `focus_keyphrase` | `wp-draft.py` | Written to the Yoast SEO focus keyphrase field |
| `meta_description` | `wp-draft.py` | Written to the Yoast SEO meta description field |
| `image` | `wp-draft.py`, `linkedin-post.py`, `twitter-post.py` | Filename only — e.g. `my-image.png`. The plugin looks for it in the configured image folder |
| `image_prompt` | `generate-image.py` | The post-specific part of the image generation prompt. A standard style prefix is prepended automatically |
| `category` | `wp-draft.py` | List of category names matching WordPress exactly (case-sensitive) |
| `tags` | `linkedin-post.py` | Turned into `#hashtags` appended to the LinkedIn post |
| `linkedin_caption` | `wp-draft.py`, `linkedin-post.py` | Written to the LinkedIn plugin field in WordPress and used as the LinkedIn post text |
| `linkedin_publish_date` | `linkedin-post.py` | Written back automatically on publish — acts as a guard to prevent re-posting |
| `twitter_caption` | `twitter-post.py` | The tweet body, not including the URL or hashtags (those are appended automatically) |
| `twitter_hashtags` | `twitter-post.py` | List of hashtags without the `#` character |
| `post_url` | `wp-draft.py`, `linkedin-post.py`, `twitter-post.py` | Written back automatically by `wp-draft.py` after the draft is created |
| `wp_post_id` | `wp-draft.py`, `sync-post-dates.py` | Written back automatically by `wp-draft.py` after the draft is created |

---

## Commands and workflow

Open the command palette with `Cmd+P` and type **Blog Post Creator** to see all available commands. Run them in the order below.

---

### 1. Generate header image

**Command:** `Blog Post Creator: Generate header image`

Reads `image_prompt` from front matter, prepends a standard style prefix, sends the combined prompt to the OpenAI DALL-E API, and saves the resulting image to the configured image folder. The `image` and `image_prompt` fields must be set before running.

---

### 2. Convert to HTML

**Command:** `Blog Post Creator: Convert to HTML`

Converts the current note to an HTML fragment using the Python `markdown` library. Collapses soft line wrapping for clean pasting into Divi. Writes a `_BODY_ONLY.html` file alongside the markdown note.

> This must be run before Push to WordPress.

---

### 3. Push to WordPress as draft

**Command:** `Blog Post Creator: Push to WordPress as draft`

Requires the `_BODY_ONLY.html` file from the previous step. Wraps the HTML in Divi shortcodes, uploads the featured image to the WordPress media library, creates a draft post, and writes `wp_post_id` and `post_url` back into the front matter of your note.

If you run this command again on the same note, it updates the existing WordPress draft rather than creating a new one.

---

### 4. Review and schedule in WordPress

Open your WordPress dashboard, review the draft, and set a publish date. The post does not need to be live before proceeding to social.

---

### 5. Post to LinkedIn

**Command:** `Blog Post Creator: Post to LinkedIn`

Requires `post_url` to be set in front matter (written by step 3). Resizes the header image to LinkedIn's recommended dimensions (1200×627 px), uploads it to LinkedIn, and creates a public article post using `linkedin_caption`. Writes `linkedin_publish_date` back to front matter on success to prevent accidental re-posting.

---

### 6. Post to Twitter / X

**Command:** `Blog Post Creator: Post to Twitter/X`

Requires `post_url` to be set. Assembles the tweet from `twitter_caption`, `post_url`, and `twitter_hashtags`. Validates the total length against Twitter's 280-character limit (URLs are counted as 23 characters per t.co rules) and aborts with a clear error if the tweet is too long. Resizes and uploads the header image at 1200×675 px before posting.

---

## Syncing post dates

**Command:** `Blog Post Creator: Sync post dates from WordPress`

This command does not require a note to be open. It queries the WordPress REST API for all published and scheduled posts, then checks your local markdown files against the results.

For each file whose `YYMMDD_` filename prefix does not match the WordPress publish date, it:

- Renames the file to use the correct date prefix
- Updates the `date` field in front matter to match
- Promotes `status` from `draft` to `publish` if WordPress confirms the post is live

Run this after WordPress publishes a scheduled post to keep your local filenames in sync. Add `--dry-run` when running standalone to preview changes without writing anything.

Files with an `XXXXXX_` prefix (unscheduled drafts) are picked up and renamed automatically once a publish date is set in WordPress.

---

## Running scripts standalone

All scripts can be run directly from the terminal without the plugin. You will need to create credential config files manually from the provided examples:

```bash
cd scripts
cp wp_config.py.example wp_config.py
cp linkedin_config.py.example linkedin_config.py
cp twitter_config.py.example twitter_config.py
cp openai_config.py.example openai_config.py
```

Open each file and fill in your credentials. The config files are gitignored and will never be committed.

```bash
# Convert a post to HTML
python3 scripts/publish.py path/to/post.md

# Push a draft to WordPress
python3 scripts/wp-draft.py path/to/post.md

# Generate a header image
python3 scripts/generate-image.py path/to/post.md

# Post to LinkedIn
python3 scripts/linkedin-post.py path/to/post.md

# Post to Twitter / X
python3 scripts/twitter-post.py path/to/post.md

# Sync post dates (dry run)
python3 scripts/sync-post-dates.py --dry-run

# Sync post dates (apply)
python3 scripts/sync-post-dates.py
```

**Environment variable overrides**

| Variable | Used by | Purpose |
|---|---|---|
| `BLOG_IMAGE_FOLDER` | `generate-image.py`, `linkedin-post.py`, `twitter-post.py` | Override the image folder path |
| `BLOG_POSTS_DIR` | `sync-post-dates.py` | Override the blog posts folder path |

```bash
BLOG_IMAGE_FOLDER="/path/to/imagery" python3 scripts/generate-image.py post.md
```

---

## Updating the plugin

When a new release is available:

1. Download `main.js` from the [Releases page](https://github.com/sebmatthews/blog-post-creator/releases).
2. Copy it to your vault's plugin folder, replacing the existing file.
3. In Obsidian: disable and re-enable the plugin, or restart Obsidian.

The updated scripts are extracted automatically on next load.

If building from source, rebuild after any change to `main.ts` or the scripts:

```bash
cd obsidian-plugin
npm run build
cp main.js "/path/to/your/vault/.obsidian/plugins/blog-post-creator/"
```

---

## Licence

MIT Licence

Copyright © 2026 Seb Matthews ([sebmatthews.net](https://sebmatthews.net))

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
