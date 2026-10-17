#!/usr/bin/env python3
"""Review Reply Studio — local-first review reply drafter for small hotels.

All AI runs on open-weight models via Ollama (default: local or in-cluster).
No guest data ever leaves the machine. Zero cost per reply.
"""
import json
import os
import re
import urllib.request

from flask import Flask, jsonify, render_template, request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama.ollamaserver-shared:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:latest")

app = Flask(__name__)

SYSTEM_PROMPT = """You are the reply-writing assistant of a small independent hotel.

ABSOLUTE RULES — breaking them is a critical failure:
1. LANGUAGE: reply ONLY in the exact language the review is written in
   (English review -> English reply, German review -> German reply,
   French review -> French reply). Ignore the language of the hotel profile.
2. NEVER invent or confirm facts. You may ONLY mention amenities, services or
   details that are explicitly listed in the hotel profile below. If the
   review praises or mentions something NOT in the profile (e.g. a spa, a
   restaurant, a pool), thank the guest warmly but do NOT repeat, echo or
   confirm that specific detail. Do not claim the guest did anything that is
   not explicitly stated in the review.
3. NEVER invent names, dates, prices, or promises (no discounts, no refunds,
   no "we will fix it by Friday") unless the hotel profile explicitly allows it.
4. NEVER argue with the guest or blame them. Acknowledge, thank, stay factual.
5. If the review contains a serious complaint (safety, hygiene, theft,
   discrimination), do NOT draft a public reply. Instead output exactly:
   "HUMAN_NEEDED: <one sentence why>".
6. Length: 60-110 words. Warm, personal, no corporate filler. Do not start
   with "Dear guest". Sign at the very END, with the hotel's signature from
   the profile — never at the beginning.

Hotel profile (the ONLY facts you may use):
{profile}
"""

USER_TEMPLATE = """Review ({stars}/5 stars):
\"\"\"{review}\"\"\"

Write the public reply draft. Output ONLY the reply text (or HUMAN_NEEDED)."""


def ollama_generate(prompt: str, system: str) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.4, "num_predict": 400},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/generate", data=payload,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r).get("response", "").strip()


SERIOUS = re.compile(
    r"\b(bed ?bugs?|cafard|cockroach|vol[ée]|stolen|theft|moisissure|mold|"
    r"insalubre|dangereux|unsafe|harass|discriminat|injur|assault)\b", re.I)

# ---------------------------------------------------------------------------
# Deterministic guardrails — the model proposes, the code disposes.
# ---------------------------------------------------------------------------

STOPWORDS = {
    "en": {"the", "and", "was", "with", "our", "we", "you", "your", "thank",
           "stay", "room", "very", "for", "that", "this"},
    "fr": {"le", "la", "les", "et", "nous", "vous", "votre", "notre", "merci",
           "séjour", "chambre", "très", "pour", "que", "une", "des", "avec"},
    "de": {"der", "die", "das", "und", "wir", "sie", "ihr", "ihre", "danke",
           "zimmer", "sehr", "für", "dass", "mit", "nicht", "aufenthalt"},
    "pt": {"obrigado", "obrigada", "estadia", "quarto", "muito", "para",
           "que", "uma", "nós", "você", "seu", "sua", "com", "foi"},
    "es": {"gracias", "estancia", "habitación", "muy", "para", "que", "una",
           "nosotros", "usted", "con", "fue", "los", "las"},
}
LANG_NAMES = {"en": "English", "fr": "French", "de": "German",
              "pt": "Portuguese", "es": "Spanish"}


def detect_lang(text: str) -> str:
    words = re.findall(r"[a-zàâäéèêëîïôöùûüçß]+", text.lower())
    scores = {lang: sum(1 for w in words if w in sw) for lang, sw in STOPWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 2 else "en"


def forbidden_terms(profile: str) -> list:
    """Extract amenities the profile says the hotel does NOT have."""
    terms = []
    for m in re.finditer(
            r"(?:do NOT have|don't have|does not have|pas de|kein(?:e|en)?|sans)\s+([a-zà-ÿ ,]+?)(?:\.|;|$)",
            profile, re.I):
        for t in re.split(r",| or | and | et | und ", m.group(1)):
            t = t.strip().lower()
            if 2 < len(t) < 25:
                terms.append(t)
    return terms


def draft_with_guards(review: str, stars: int, profile: str) -> dict:
    """Generate a draft, then enforce language + no-invented-facts in code."""
    review_lang = detect_lang(review)
    banned = forbidden_terms(profile)
    system = SYSTEM_PROMPT.format(profile=profile)
    prompt = USER_TEMPLATE.format(stars=stars, review=review)

    out = ollama_generate(prompt, system)
    violations = []

    for attempt in range(2):
        violations = []
        if out.startswith("HUMAN_NEEDED"):
            return {"draft": out, "flagged": True, "violations": ["serious"]}
        draft_lang = detect_lang(out)
        if draft_lang != review_lang:
            violations.append(f"language:{draft_lang}!={review_lang}")
        low = out.lower()
        for t in banned:
            if re.search(rf"\b{re.escape(t)}\b", low):
                violations.append(f"invented:{t}")
        if not violations:
            break
        # Regenerate once with the violation spelled out
        note = (f"CRITICAL CORRECTION: your previous draft violated these rules: "
                f"{'; '.join(violations)}. The review is written in "
                f"{LANG_NAMES[review_lang]} — reply ONLY in {LANG_NAMES[review_lang]}. "
                f"Do NOT mention: {', '.join(banned) or 'anything not in the profile'}.")
        out = ollama_generate(prompt + "\n\n" + note, system)

    if out.startswith("HUMAN_NEEDED"):
        return {"draft": out, "flagged": True, "violations": ["serious"]}
    flagged = bool(violations)
    if flagged:
        out += "\n\n[⚠ auto-check: " + "; ".join(violations) + " — verify before posting]"
    return {"draft": out, "flagged": flagged, "violations": violations}


@app.get("/")
def index():
    return render_template("index.html", model=MODEL)


@app.get("/api/health")
def health():
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as r:
            ok = r.status == 200
    except Exception:
        ok = False
    return jsonify({"ok": ok, "model": MODEL, "ollama": OLLAMA_HOST})


@app.post("/api/reply")
def reply():
    data = request.get_json(force=True)
    review = (data.get("review") or "").strip()[:3000]
    stars = int(data.get("stars") or 5)
    stars = max(1, min(5, stars))
    profile = (data.get("profile") or "").strip()[:1500] or "A small family-run hotel."
    if not review:
        return jsonify({"error": "empty review"}), 400

    if stars <= 2 or SERIOUS.search(review):
        # Serious reviews always go to a human — still offer a local draft
        result = draft_with_guards(review, stars, profile)
        result["flagged"] = True
        return jsonify(result)

    return jsonify(draft_with_guards(review, stars, profile))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8787")))
