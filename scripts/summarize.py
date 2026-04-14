#!/usr/bin/env python3
"""
YouTube Video Summarizer
Fetches transcript from a YouTube video and summarizes it using Claude API.
Saves the result as a structured Markdown note.
"""

import os
import re
import sys
import json
import datetime
import anthropic

from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def fetch_transcript(video_id: str) -> tuple[str, list]:
    """Fetch transcript for a given video ID. Returns (full_text, segments)."""
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id)
    except Exception:
        # Try auto-generated captions
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_generated_transcript(["en"])
            segments = transcript.fetch()
        except Exception as e:
            raise RuntimeError(f"Could not fetch transcript: {e}")

    full_text = " ".join(seg["text"] for seg in segments)
    return full_text, segments


def fetch_video_metadata(video_id: str) -> dict:
    """Fetch basic video metadata via oEmbed (no API key required)."""
    import requests
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "title": data.get("title", "Unknown Title"),
                "author": data.get("author_name", "Unknown Channel"),
                "thumbnail": data.get("thumbnail_url", ""),
            }
    except Exception:
        pass
    return {"title": "Unknown Title", "author": "Unknown Channel", "thumbnail": ""}


def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS."""
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def build_timestamped_chapters(segments: list, num_chapters: int = 8) -> list[dict]:
    """Divide transcript into rough chapters for timestamp anchoring."""
    if not segments:
        return []
    chunk_size = max(1, len(segments) // num_chapters)
    chapters = []
    for i in range(0, len(segments), chunk_size):
        chunk = segments[i : i + chunk_size]
        start_time = chunk[0]["start"]
        text = " ".join(seg["text"] for seg in chunk)
        chapters.append({"start": start_time, "text": text})
    return chapters


# ─── Summarizer ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert research assistant and note-taker. 
Your job is to create thorough, structured, and insightful summaries of YouTube video transcripts.
Produce your output strictly in Markdown format with no preamble.
"""

SUMMARY_PROMPT_TEMPLATE = """
Below is the full transcript of a YouTube video titled: "{title}" by {author}.

VIDEO URL: {url}
DURATION: approx. {duration}

TRANSCRIPT:
{transcript}

---

Please produce a comprehensive, well-structured Markdown summary with the following sections:

## 🎯 TL;DR
One paragraph (3–5 sentences) capturing the core message and why it matters.

## 📌 Key Takeaways
A bulleted list of 5–10 specific insights, lessons, or facts from the video. Be precise — no vague platitudes.

## 🗂 Detailed Notes
A thorough section-by-section breakdown of the video. Use subheadings (###) for each major topic or chapter. Include specific details, examples, data, quotes, or frameworks mentioned.

## 💡 Concepts & Definitions
If the video introduces technical terms, frameworks, or named concepts, define each one clearly.

## ❓ Questions & Gaps
List 2–5 follow-up questions this video raises, or topics it leaves unexplored.

## 🔗 Related Topics
3–5 topics worth exploring next based on this video's content.

---
Write in clear, concise language. Aim for depth over brevity — this is a study note, not a tweet.
"""


def summarize_with_claude(
    transcript: str,
    title: str,
    author: str,
    url: str,
    duration: str,
    api_key: str,
) -> str:
    """Send transcript to Claude and get a structured summary."""
    client = anthropic.Anthropic(api_key=api_key)

    # Truncate very long transcripts to fit context window (~150k tokens safe limit)
    max_chars = 400_000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n\n[Transcript truncated due to length]"

    prompt = SUMMARY_PROMPT_TEMPLATE.format(
        title=title,
        author=author,
        url=url,
        duration=duration,
        transcript=transcript,
    )

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


# ─── File builder ─────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Create a URL/filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:80]


def build_markdown_note(
    summary: str,
    title: str,
    author: str,
    url: str,
    video_id: str,
    tags: str,
    thumbnail: str,
    segments: list,
) -> str:
    """Wrap the Claude summary in a full front-matter Markdown note."""
    today = datetime.date.today().isoformat()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    tag_yaml = json.dumps(tag_list)

    total_seconds = segments[-1]["start"] if segments else 0
    duration_str = format_timestamp(total_seconds)

    frontmatter = f"""---
title: "{title}"
author: "{author}"
source: "{url}"
video_id: "{video_id}"
thumbnail: "{thumbnail}"
date: "{today}"
duration: "{duration_str}"
tags: {tag_yaml}
---

"""

    header = f"""# 📺 {title}

> **Channel:** {author}  
> **URL:** [{url}]({url})  
> **Date noted:** {today}  
> **Duration:** ~{duration_str}  

---

"""

    return frontmatter + header + summary


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    youtube_url = os.environ.get("YOUTUBE_URL", "").strip()
    tags = os.environ.get("TAGS", "").strip()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not youtube_url:
        print("❌ No YouTube URL provided. Set YOUTUBE_URL environment variable.")
        sys.exit(1)

    if not api_key:
        print("❌ No Anthropic API key. Set ANTHROPIC_API_KEY secret in your repo.")
        sys.exit(1)

    print(f"🔗 Processing: {youtube_url}")

    # 1. Extract video ID
    video_id = extract_video_id(youtube_url)
    print(f"✅ Video ID: {video_id}")

    # 2. Fetch metadata
    meta = fetch_video_metadata(video_id)
    title = meta["title"]
    author = meta["author"]
    thumbnail = meta["thumbnail"]
    print(f"✅ Title: {title}")
    print(f"✅ Channel: {author}")

    # 3. Fetch transcript
    print("📄 Fetching transcript...")
    transcript_text, segments = fetch_transcript(video_id)
    total_seconds = segments[-1]["start"] if segments else 0
    duration_str = format_timestamp(total_seconds)
    print(f"✅ Transcript fetched ({len(transcript_text):,} chars, ~{duration_str})")

    # 4. Summarize with Claude
    print("🤖 Summarizing with Claude...")
    summary = summarize_with_claude(
        transcript=transcript_text,
        title=title,
        author=author,
        url=youtube_url,
        duration=duration_str,
        api_key=api_key,
    )
    print("✅ Summary generated")

    # 5. Build final note
    note_content = build_markdown_note(
        summary=summary,
        title=title,
        author=author,
        url=youtube_url,
        video_id=video_id,
        tags=tags,
        thumbnail=thumbnail,
        segments=segments,
    )

    # 6. Save to notes/ folder
    today = datetime.date.today().isoformat()
    slug = slugify(title)
    filename = f"notes/{today}-{slug}.md"
    os.makedirs("notes", exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(note_content)

    print(f"💾 Saved: {filename}")

    # Signal to GitHub Actions
    with open("/tmp/output_file.txt", "w") as f:
        f.write(filename)
    with open("/tmp/video_title.txt", "w") as f:
        f.write(title)

    print("🎉 Done!")


if __name__ == "__main__":
    main()
