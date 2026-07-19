"""Translate all training narrations to Mende via Emergent LLM (Claude), writing mende.py."""
import asyncio
import json
import os
import sys

sys.path.insert(0, "/app/training_production")
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from scenes import VIDEOS  # noqa: E402
from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402

PROMPT = """You are a professional Sierra Leonean translator, a native Mende speaker from Bo.
Translate each numbered English narration below into natural spoken Mende (Sierra Leone).

Rules:
- Keep product names and technical terms in English: SaloneHCM, dashboard, payroll, payslip, NASSIT, PAYE, NRA, voucher, branch, supervisor, finance officer, MoF, Training Center, Feature Directory, quiz, certificate, email, password, SMS, PDF, bank, budget, audit log, self-service, two-factor authentication, administrator.
- Write for text-to-speech: prefer standard Mende orthography but keep it readable; commas for natural pauses.
- Keep roughly the same length and the same meaning; warm instructional tone.
- Output STRICT JSON only: an array of strings, one translation per numbered item, same order. No markdown, no commentary.

Narrations:
{items}"""


async def main():
    out = {}
    for v in VIDEOS:
        items = "\n".join(f"{i+1}. {sc['narration']}" for i, sc in enumerate(v["scenes"]))
        chat = LlmChat(
            api_key=os.environ["EMERGENT_LLM_KEY"],
            session_id=f"mende-{v['slug']}",
            system_message="You translate English to Mende (Sierra Leone). Respond with strict JSON arrays only.",
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        resp = await chat.send_message(UserMessage(text=PROMPT.format(items=items)))
        text = resp.strip()
        if text.startswith("```"):
            text = text.split("```")[1].lstrip("json").strip()
        arr = json.loads(text)
        assert len(arr) == len(v["scenes"]), f"{v['slug']}: {len(arr)} != {len(v['scenes'])}"
        out[v["slug"]] = arr
        print(f"{v['slug']}: {len(arr)} scenes translated")

    with open("/app/training_production/mende.py", "w", encoding="utf-8") as f:
        f.write('"""Mende narrations for the 7 training videos — LLM-translated (Claude), same scene order as scenes.py."""\n\n')
        f.write("MENDE = ")
        f.write(json.dumps(out, ensure_ascii=False, indent=2))
        f.write("\n")
    print("wrote mende.py")


asyncio.run(main())
