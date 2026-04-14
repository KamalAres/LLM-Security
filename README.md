# 📺 YouTube Notes — AI-Powered Video Summarizer

Automatically fetch, summarize, and store YouTube video notes using **GitHub Actions** + **Claude AI**.  
Every summary is saved as a structured Markdown file in the `notes/` folder of this repo.

---

## ✨ Features

- 🎬 **Auto-fetches transcripts** from any YouTube video (no API key needed for transcripts)
- 🤖 **Summarized by Claude** with TL;DR, key takeaways, detailed notes, concepts & definitions
- 📁 **Stored as Markdown** with YAML front matter (compatible with Obsidian, Notion import, Jekyll, etc.)
- 🏷 **Taggable** for easy organization
- ⚡ **Two trigger modes**: GitHub UI (workflow dispatch) or GitHub Issue

---

## 🚀 Setup

### 1. Fork or clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/youtube-notes.git
cd youtube-notes
```

### 2. Add your Anthropic API key as a secret

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `ANTHROPIC_API_KEY` | Your key from [console.anthropic.com](https://console.anthropic.com) |

### 3. Create the `notes/` folder (first time only)

```bash
mkdir notes
echo "# My YouTube Notes" > notes/README.md
git add notes/ && git commit -m "init notes folder" && git push
```

---

## ▶️ How to Use

### Option A — GitHub UI (Workflow Dispatch)

1. Go to your repo → **Actions** tab
2. Click **"📺 YouTube Video Summarizer"**
3. Click **"Run workflow"**
4. Paste the YouTube URL
5. (Optional) Add comma-separated tags
6. Click **Run** — done!

The summary will be committed to `notes/YYYY-MM-DD-video-title.md` automatically.

---

### Option B — GitHub Issue

1. Create a new issue in your repo
2. Paste the YouTube URL anywhere in the issue body
3. (Optional) Add a line like `tags: ai, research, tutorial`
4. Apply the label **`summarize`** to the issue
5. The workflow triggers, and posts the summary as a comment + commits the file

**Issue body example:**
```
Please summarize this video:
https://www.youtube.com/watch?v=dQw4w9WgXcQ

tags: music, nostalgia, classic
```

---

## 📄 Output Format

Each note is saved as `notes/YYYY-MM-DD-video-title.md` and looks like:

```markdown
---
title: "Video Title"
author: "Channel Name"
source: "https://youtube.com/watch?v=..."
video_id: "dQw4w9WgXcQ"
date: "2024-01-15"
duration: "12:34"
tags: ["ai", "research"]
---

# 📺 Video Title

> **Channel:** Channel Name
> **URL:** https://...
> **Date noted:** 2024-01-15

## 🎯 TL;DR
...

## 📌 Key Takeaways
...

## 🗂 Detailed Notes
...

## 💡 Concepts & Definitions
...

## ❓ Questions & Gaps
...

## 🔗 Related Topics
...
```

---

## 🗂 Folder Structure

```
youtube-notes/
├── .github/
│   └── workflows/
│       └── youtube-summary.yml   # The GitHub Actions workflow
├── scripts/
│   └── summarize.py              # Python summarizer script
├── notes/                        # 📁 All your saved summaries live here
│   ├── README.md
│   ├── 2024-01-15-some-video.md
│   └── ...
└── README.md
```

---

## 🔧 Customization

| What | Where |
|------|-------|
| Change AI model | `scripts/summarize.py` → `model=` parameter |
| Change summary structure | Edit the `SUMMARY_PROMPT_TEMPLATE` in `summarize.py` |
| Change output folder | `summarize.py` → `filename = f"notes/..."` |
| Add Obsidian vault path | Point your Obsidian vault at the `notes/` folder |

---

## ⚠️ Limitations

- Videos **must have captions** (auto-generated or manual) — videos without transcripts will fail
- Very long videos (3h+) may have transcripts truncated at ~400k characters
- Age-restricted or private videos cannot be accessed

---

## 📜 License

MIT — do whatever you want with this.
