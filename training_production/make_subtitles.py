"""Generate WebVTT subtitle files for all training videos (English + Krio).
Cue timings reconstructed from manifest chapter offsets + cached narration
audio durations. Writes subs into /app/backend/static/training/subs/ and adds
a `captions` field to each manifest entry."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, "/app/training_production")
from scenes import VIDEOS  # noqa: E402

AUDIO = Path("/app/training_production/audio")
OUT = Path("/app/backend/static/training/subs")
OUT.mkdir(parents=True, exist_ok=True)
MANIFEST = Path("/app/backend/static/training/manifest.json")


def dur_of(p) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True)
    return float(out.stdout.strip())


def cues_for(text: str, start: float, dur: float):
    parts = re.split(r"(?<=[.!?…]) +", text.strip())
    chunks = []
    for p in parts:
        if chunks and (len(chunks[-1]) < 30 or len(p) < 20):
            chunks[-1] += " " + p
        else:
            chunks.append(p)
    total = sum(len(c) for c in chunks) or 1
    t = start
    for c in chunks:
        d = dur * len(c) / total
        yield t, t + d, c
        t += d


def ts(x: float) -> str:
    h, m, s = int(x // 3600), int(x % 3600 // 60), x % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


manifest = json.loads(MANIFEST.read_text())

for v in VIDEOS:
    for lang in ("en", "krio", "mende"):
        slug = v["slug"] + ("" if lang == "en" else f"-{lang}")
        entry = manifest.get(slug)
        if not entry:
            continue
        offsets = [c["t"] for c in entry["chapters"]]
        lines = ["WEBVTT", ""]
        n = 1
        for sc, off in zip(v["scenes"], offsets):
            text = sc["narration"] if lang == "en" else sc[f"narration_{lang}"]
            key = hashlib.sha1(text.encode()).hexdigest()[:16]
            ap = AUDIO / f"{key}.mp3"
            adur = dur_of(ap) if ap.exists() else max(4.0, len(text) / 16)
            for a, b, c in cues_for(text, off + 0.25, adur):
                lines += [str(n), f"{ts(a)} --> {ts(b)}", c, ""]
                n += 1
        (OUT / f"{slug}.vtt").write_text("\n".join(lines), encoding="utf-8")
        entry["captions"] = [{
            "src": f"/api/static/training/subs/{slug}.vtt",
            "srclang": {"en": "en", "krio": "kri", "mende": "men"}[lang],
            "label": {"en": "English", "krio": "Krio", "mende": "Mɛnde"}[lang],
        }]
        print(f"wrote {slug}.vtt ({n - 1} cues)")

MANIFEST.write_text(json.dumps(manifest, indent=2))
print("manifest updated with captions")
