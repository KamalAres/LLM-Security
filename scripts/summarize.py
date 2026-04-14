#!/usr/bin/env python3
"""
YouTube Video Summarizer — powered by Groq (free)
Get your free API key at: https://console.groq.com
"""

import os, re, sys, json, datetime, requests
from youtube_transcript_api import YouTubeTranscriptApi

# ── Groq config ───────────────────────────────────────────────────────────────
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"   # free, high quality
# alternatives: "llama-3.1-8b-instant" (fastest), "mixtral-8x7b-32768" (big context)

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract video ID from: {url}")

def fetch_transcript(video_id):
    # ── Method 1: youtube-transcript-api ──
    try:
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        segs = [{"text": t.text, "start": t.start} for t in transcript]
        return " ".join(s["text"] for s in segs), segs
    except Exception as e:
        print(f"⚠️ Primary transcript fetch failed: {e}")

    # ── Method 2: yt-dlp ──
    try:
        import subprocess, json

        print("🔄 Falling back to yt-dlp...")

        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--skip-download",
            "--print-json",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android",
            "--js-runtimes", "node",
            f"https://www.youtube.com/watch?v={video_id}"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            subs = data.get("automatic_captions", {}).get("en", [])

            if subs:
                import requests, re
                xml = requests.get(subs[0]["url"]).text
                texts = re.findall(r'>([^<]+)<', xml)
                segs = [{"text": t, "start": 0} for t in texts]
                return " ".join(texts), segs

    except Exception as e:
        print(f"⚠️ yt-dlp failed: {e}")

    # ── Method 3: External API (🔥 RELIABLE FIX) ──
    try:
        print("🌐 Falling back to external transcript API...")

        import requests
        url = f"https://youtubetranscript.com/?server_vid2={video_id}"
        res = requests.get(url, timeout=15)

        if res.status_code == 200:
            data = res.json()
            segs = [{"text": x["text"], "start": x.get("start", 0)} for x in data]
            return " ".join(s["text"] for s in segs), segs

    except Exception as e:
        print(f"⚠️ External API failed: {e}")

    # ── Final fail ──
    raise RuntimeError("❌ All transcript methods failed (YouTube blocked + no fallback worked)")
    
def fetch_metadata(video_id):
    try:
        r = requests.get(
            f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
            timeout=10)
        if r.status_code == 200:
            d = r.json()
            return d.get("title","Unknown"), d.get("author_name","Unknown"), d.get("thumbnail_url","")
    except Exception:
        pass
    return "Unknown Title", "Unknown Channel", ""

def ts(seconds):
    s = int(seconds)
    h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[\s_-]+", "-", text)[:80]

# ── Summarizer ────────────────────────────────────────────────────────────────

PROMPT = """You are an expert research assistant and note-taker.
Summarize this YouTube video transcript into a thorough Markdown study note.

VIDEO: "{title}" by {author}
URL: {url}  |  DURATION: ~{duration}

TRANSCRIPT:
{transcript}

---

Produce ONLY Markdown with these sections (no preamble):

## 🎯 TL;DR
3-5 sentences on the core message and why it matters.

## 📌 Key Takeaways
5-10 specific bullet points — concrete facts, insights, or lessons. No vague platitudes.

## 🗂 Detailed Notes
Section-by-section breakdown. Use ### subheadings per major topic. Include specific details, examples, data, quotes, frameworks.

## 💡 Concepts & Definitions
Define technical terms, frameworks, or named concepts introduced.

## ❓ Questions & Gaps
2-5 follow-up questions or unexplored topics this video raises.

## 🔗 Related Topics
3-5 topics worth exploring next.
"""

def summarize(transcript, title, author, url, duration, api_key):
    # Groq context ~32k tokens; ~120k chars is safe
    if len(transcript) > 120_000:
        transcript = transcript[:120_000] + "\n\n[Transcript truncated]"

    resp = requests.post(
        GROQ_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": PROMPT.format(
                title=title, author=author, url=url, duration=duration, transcript=transcript)}],
            "max_tokens": 4096,
            "temperature": 0.3,
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Groq API {resp.status_code}: {resp.text}")
    return resp.json()["choices"][0]["message"]["content"]

# ── Note builder ──────────────────────────────────────────────────────────────

def build_note(summary, title, author, url, video_id, tags, thumbnail, segs):
    today    = datetime.date.today().isoformat()
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    duration = ts(segs[-1]["start"]) if segs else "?"
    return (
        f'---\ntitle: "{title}"\nauthor: "{author}"\nsource: "{url}"\n'
        f'video_id: "{video_id}"\nthumbnail: "{thumbnail}"\ndate: "{today}"\n'
        f'duration: "{duration}"\ntags: {json.dumps(tag_list)}\n---\n\n'
        f'# 📺 {title}\n\n'
        f'> **Channel:** {author}  \n> **URL:** [{url}]({url})  \n'
        f'> **Date noted:** {today}  \n> **Duration:** ~{duration}  \n\n---\n\n'
        + summary
    )

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    url     = os.environ.get("YOUTUBE_URL","").strip()
    tags    = os.environ.get("TAGS","").strip()
    api_key = os.environ.get("GROQ_API_KEY","").strip()

    if not url:
        print("❌ Set YOUTUBE_URL"); sys.exit(1)
    if not api_key:
        print("❌ Set GROQ_API_KEY — free key at https://console.groq.com"); sys.exit(1)

    print(f"🔗 {url}")
    vid = extract_video_id(url)
    title, author, thumb = fetch_metadata(vid)
    print(f"✅ {title} — {author}")

    print("📄 Fetching transcript...")
    text, segs = fetch_transcript(vid)
    print(f"✅ {len(text):,} chars (~{ts(segs[-1]['start']) if segs else '?'})")

    print(f"🤖 Summarizing with {GROQ_MODEL}...")
    summary = summarize(text, title, author, url, ts(segs[-1]["start"]) if segs else "?", api_key)
    print("✅ Done")

    note     = build_note(summary, title, author, url, vid, tags, thumb, segs)
    today    = datetime.date.today().isoformat()
    filename = f"notes/{today}-{slugify(title)}.md"
    os.makedirs("notes", exist_ok=True)
    with open(filename, "w") as f: f.write(note)
    print(f"💾 {filename}")

    open("/tmp/output_file.txt","w").write(filename)
    open("/tmp/video_title.txt","w").write(title)
    print("🎉 Done!")

if __name__ == "__main__":
    main()
