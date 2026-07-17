"""Training video production engine.

For each video: synthesize per-scene narration (OpenAI TTS via Emergent key),
drive the real app in a recorded Chromium session (fake cursor overlay for a
human-trainer feel), pace each scene to its narration length, then mux
narration + screen recording into a web-ready MP4 with poster + chapters.
Outputs land in /app/backend/static/training/ and metadata in manifest.json.
"""
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import os
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from emergentintegrations.llm.openai import OpenAITextToSpeech  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

BASE = "https://salonepaycms.preview.emergentagent.com"
OUT = Path("/app/backend/static/training")
WORK = Path("/app/training_production/work")
AUDIO = Path("/app/training_production/audio")
for d in (OUT, WORK, AUDIO):
    d.mkdir(parents=True, exist_ok=True)
MANIFEST = OUT / "manifest.json"

CURSOR_JS = """
(() => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div');
    c.id = '__cur';
    Object.assign(c.style, {position:'fixed', width:'22px', height:'22px', borderRadius:'50%',
      background:'rgba(19,51,38,0.82)', border:'2.5px solid #fff',
      boxShadow:'0 1px 8px rgba(0,0,0,0.5)', zIndex:2147483647,
      pointerEvents:'none', left:'-60px', top:'-60px',
      transition:'transform 0.09s ease'});
    (document.body || document.documentElement).appendChild(c);
  };
  window.addEventListener('mousemove', e => {
    mk();
    const c = document.getElementById('__cur');
    if (c) { c.style.left = (e.clientX-11)+'px'; c.style.top = (e.clientY-11)+'px'; }
  }, true);
  window.addEventListener('mousedown', () => {
    const c = document.getElementById('__cur');
    if (c) c.style.transform = 'scale(0.55)';
  }, true);
  window.addEventListener('mouseup', () => {
    const c = document.getElementById('__cur');
    if (c) c.style.transform = 'scale(1)';
  }, true);
  if (document.readyState !== 'loading') mk();
  else document.addEventListener('DOMContentLoaded', mk);
})();
"""

SLIDE = """<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{{margin:0;height:100%;background:#0A4A1E;color:#fff;
    font-family:Georgia,'Times New Roman',serif;overflow:hidden}}
  .wrap{{height:100%;display:flex;flex-direction:column;justify-content:center;padding:0 110px}}
  .brand{{font-size:20px;letter-spacing:.28em;text-transform:uppercase;color:#D9C58A;font-family:Arial,sans-serif;font-weight:700}}
  .tag{{margin-top:38px;font-size:14px;letter-spacing:.32em;text-transform:uppercase;color:#83CF95;font-family:Arial,sans-serif}}
  h1{{font-size:58px;margin:16px 0 0;font-weight:700;line-height:1.12;max-width:900px}}
  .sub{{margin-top:20px;font-size:21px;color:#C9D4CE;font-family:Arial,sans-serif;max-width:760px;line-height:1.5}}
  .rule{{width:84px;height:3px;background:#D9C58A;margin-top:34px}}
  .foot{{position:absolute;bottom:44px;left:110px;font-size:13px;color:#6B9E77;font-family:Arial,sans-serif;letter-spacing:.14em;text-transform:uppercase}}
</style></head><body><div class="wrap">
  <div class="brand">SaloneHCM</div>
  <div class="tag">{tag}</div>
  <h1>{title}</h1>
  <div class="sub">{subtitle}</div>
  <div class="rule"></div>
  <div class="foot">Official training series &nbsp;·&nbsp; Sierra Leone HCM &amp; Payroll</div>
</div></body></html>"""

_tts = OpenAITextToSpeech(api_key=os.getenv("EMERGENT_LLM_KEY"))


async def tts_for(text: str) -> Path:
    key = hashlib.sha1(text.encode()).hexdigest()[:16]
    path = AUDIO / f"{key}.mp3"
    if not path.exists():
        audio = await _tts.generate_speech(text=text, model="tts-1-hd", voice="coral", speed=1.0)
        path.write_bytes(audio)
    return path


def dur_of(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return float(out.stdout.strip())


async def smooth_move_click(page, selector, click=True):
    loc = page.locator(selector).first
    await loc.wait_for(state="visible", timeout=8000)
    await loc.scroll_into_view_if_needed()
    box = await loc.bounding_box()
    if not box:
        raise RuntimeError(f"no box for {selector}")
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y, steps=28)
    await page.wait_for_timeout(320)
    if click:
        await page.mouse.click(x, y)


async def do_step(page, step):
    op = step[0]
    if op == "slide":
        await page.set_content(SLIDE.format(tag=step[1], title=step[2], subtitle=step[3]))
    elif op == "goto":
        await page.goto(BASE + step[1], wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(800)
    elif op == "login":
        await page.goto(BASE + "/login", wait_until="networkidle", timeout=30000)
        await smooth_move_click(page, 'input[type="email"]')
        await page.locator('input[type="email"]').first.fill("")
        await page.keyboard.type(step[1], delay=42)
        await smooth_move_click(page, 'input[type="password"]')
        await page.locator('input[type="password"]').first.fill("")
        await page.keyboard.type(step[2], delay=42)
        await smooth_move_click(page, 'button[type="submit"]')
        await page.wait_for_timeout(2600)
        print(f"  post-login url: {page.url}", flush=True)
    elif op == "click":
        await smooth_move_click(page, step[1])
        await page.wait_for_timeout(700)
    elif op == "hover":
        await smooth_move_click(page, step[1], click=False)
    elif op == "type":
        await smooth_move_click(page, step[1])
        await page.keyboard.type(step[2], delay=55)
    elif op == "scroll":
        for _ in range(6):
            await page.mouse.wheel(0, step[1] / 6)
            await page.wait_for_timeout(140)
    elif op == "press":
        await page.keyboard.press(step[1])
    elif op == "pause":
        await page.wait_for_timeout(int(step[1] * 1000))


async def produce(video: dict) -> dict:
    slug = video["slug"]
    print(f"=== producing {slug} ===", flush=True)
    for sc in video["scenes"]:
        sc["audio"] = await tts_for(sc["narration"])
        sc["adur"] = dur_of(sc["audio"])
    print(f"narration total {sum(s['adur'] for s in video['scenes']):.0f}s", flush=True)

    rec_dir = WORK / slug
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(rec_dir),
            record_video_size={"width": 1280, "height": 720},
        )
        await ctx.add_init_script(CURSOR_JS)
        page = await ctx.new_page()
        vid_ref = page.video
        rec_start = time.monotonic()
        offsets = []
        for sc in video["scenes"]:
            start = time.monotonic() - rec_start
            offsets.append(start)
            for step in sc["steps"]:
                try:
                    await do_step(page, step)
                except Exception as e:
                    print(f"  step {step[0]} {step[1] if len(step)>1 else ''} failed: {e}", flush=True)
                await page.wait_for_timeout(420)
            target = start + sc["adur"] + 1.3
            remaining = target - (time.monotonic() - rec_start)
            if remaining > 0:
                await page.wait_for_timeout(int(remaining * 1000))
        await page.wait_for_timeout(700)
        await ctx.close()
        webm = await vid_ref.path()
        await browser.close()

    # narration track: each scene's mp3 delayed to its scene offset
    n = len(video["scenes"])
    cmd = ["ffmpeg", "-y"]
    for sc in video["scenes"]:
        cmd += ["-i", str(sc["audio"])]
    parts, tags = [], []
    for i, off in enumerate(offsets):
        d = int((off + 0.25) * 1000)
        parts.append(f"[{i}]adelay={d}|{d}[a{i}]")
        tags.append(f"[a{i}]")
    fc = ";".join(parts) + ";" + "".join(tags) + f"amix=inputs={n}:normalize=0[out]"
    mix = WORK / f"{slug}_mix.m4a"
    cmd += ["-filter_complex", fc, "-map", "[out]", "-c:a", "aac", "-b:a", "128k", str(mix)]
    subprocess.run(cmd, check=True, capture_output=True)

    mp4 = OUT / f"{slug}.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(webm), "-i", str(mix),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p", "-r", "25",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(mp4),
    ], check=True, capture_output=True)
    subprocess.run([
        "ffmpeg", "-y", "-ss", "6", "-i", str(mp4), "-frames:v", "1", "-q:v", "4",
        str(OUT / f"{slug}.jpg"),
    ], check=True, capture_output=True)

    total = dur_of(mp4)
    chapters = [{"t": int(off), "label": sc["chapter"]}
                for sc, off in zip(video["scenes"], offsets) if sc.get("chapter")]
    entry = {
        "slug": slug, "title": video["title"], "summary": video["summary"],
        "persona": video["persona"], "sort": video["sort"],
        "duration_s": int(total), "chapters": chapters,
        "src": f"/api/static/training/{slug}.mp4",
        "poster": f"/api/static/training/{slug}.jpg",
        "category": "training",
    }
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    manifest[slug] = entry
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    print(f"=== {slug} DONE — {total:.0f}s, {mp4.stat().st_size/1e6:.1f} MB ===", flush=True)
    return entry


async def main():
    from scenes import VIDEOS
    only = sys.argv[1:] or None
    for v in VIDEOS:
        if only and v["slug"] not in only:
            continue
        await produce(v)


if __name__ == "__main__":
    asyncio.run(main())
