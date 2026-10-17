---
title: "I sell AI to small hotels. This week I built the tool they actually ask for — 100% local, €0 per reply"
published: true
tags: devchallenge, hf26challenge, opensource, ai
cover_image: https://raw.githubusercontent.com/jeffreyturov-dev/review-reply-studio/main/media/cover.png
---

*Hacktoberfest Open-Source AI Challenge — Week 2: Side Hustle*

I run a one-person company that sells AI phone receptionists to independent hotels in Luxembourg. It's a real business with real invoices, and it teaches you things no benchmark does. Like the two objections I hear in almost every sales conversation:

1. *"I can't send my guests' data to some API. GDPR. No."*
2. *"Another €50/month subscription? For my 12 rooms? No."*

Small hoteliers are not anti-technology. They're anti-*rentier*. They've been sold booking engines, channel managers, review platforms, upsell platforms — each one a monthly fee, each one holding their data on someone else's server, priced for chains with revenue managers, not for Claire and Marc who also do the breakfast shift.

So for this week's Side Hustle challenge I built the tool they actually ask for, the way they'd actually buy it:

**[Review Reply Studio](https://github.com/jeffreyturov-dev/review-reply-studio)** — paste a guest review, get a warm, factual, on-brand reply draft. It runs entirely on an **open-weight model** (Gemma 3, via Ollama) on the hotel's own machine. No cloud. No account. No telemetry. No per-seat pricing. A reply costs exactly €0.00, and a German guest's complaint about the hair in the shower never leaves the building.

**🟢 Live demo:** https://aug-balance-specialty-flu.trycloudflare.com
**📦 Code (MIT):** https://github.com/jeffreyturov-dev/review-reply-studio

![Review Reply Studio — home](https://raw.githubusercontent.com/jeffreyturov-dev/review-reply-studio/main/media/shot1_home.png)

## The part that actually matters: the model proposes, the code disposes

Here's the thing nobody puts in their demo: a 4B open model *will* occasionally misbehave. I know, because I tested mine with a trap.

I told the app my fictional hotel's profile: *"We do NOT have a spa, pool or restaurant."* Then I fed it this review:

> "The breakfast was amazing and the spa was wonderful, best in Luxembourg!"

A naive AI reply would gush *"We're so glad you loved our spa!"* — and the hotel would have publicly confirmed an amenity that doesn't exist. That's not a hallucination bug, that's a reputational incident with a screenshot. My first prompt-only version did exactly that. It also answered an English review in French, because the hotel profile was written in French and the model got confused.

So instead of trusting prompts, I wrapped generation in **deterministic guardrails** — boring, auditable Python:

- **Language guard.** The review's language and the draft's language are detected with stopword scoring. Mismatch → one automatic regeneration with the violation spelled out. Still wrong → the draft is delivered *flagged* `⚠ verify before posting` instead of pretending everything is fine.
- **Invented-facts guard.** The hotel profile declares what the hotel *doesn't* have. Any draft that echoes a forbidden amenity is regenerated once, then flagged.
- **Human-in-the-loop for the serious stuff.** Any review ≤ 2★, or containing safety/hygiene/theft keywords, is routed to a human with the draft attached — never auto-published.

The trap review now produces this (real output, unedited):

> "We are absolutely delighted to hear you enjoyed your stay with us at Auberge du Moulin! It warms our hearts to know you appreciated our homemade breakfast and found it truly wonderful. We're so pleased you also discovered a lovely riverside experience."

No spa. The guardrail caught it.

And my favorite failure, because it's honest: a 2★ review in German. Gemma 3 4B tried twice and both times drafted in French. The language guard caught it both times and shipped the draft with a visible `[⚠ auto-check: language:fr!=de — verify before posting]` banner. A closed SaaS would have posted confident nonsense. My little local tool *knows what it doesn't know* — because the code, not the model, has the final word.

![Full flow: flagged draft for a serious review](https://raw.githubusercontent.com/jeffreyturov-dev/review-reply-studio/main/media/demo.gif)

## How it works

```
guest review ──► ┌─────────────────────────────┐
hotel profile ─► │  Flask app (1 file)         │
                 │                             │
                 │  1. Ollama / Gemma 3 draft  │  ← open-weight, local
                 │  2. language guard          │  ← stdlib regex
                 │  3. invented-facts guard    │  ← stdlib regex
                 │  4. ≤2★ → human flag        │  ← policy in code
                 └─────────────────────────────┘
                              │
                              ▼
                    reply draft + trust badge
                 (✓ safe to post / ⚠ human check)
```

One Python file. One HTML page. No database, no build step, no Docker required. `pip install flask`, point `OLLAMA_HOST` at any Ollama server, done. A replying draft takes ~5–10 seconds on CPU.

## Why open-source was a requirement, not a preference

This is the part of the prompt I care about most, because for this product it's not philosophy — it's the entire business case:

**GDPR is a wall, not a checkbox.** My clients are Luxembourgish family hotels. Reviews contain guest names, stay dates, sometimes health details ("my husband's wheelchair…"). Sending that to a third-party inference API means a data-processing agreement, a sub-processor list, and a conversation no 12-room hotel wants to have. With an open-weight model on their own hardware, the answer is one sentence: *"Nothing leaves your office."* I cannot make that promise with a closed API. Nobody can.

**The unit economics only work open.** The SaaS competition charges €30–50/month per property for review management. For a hotel doing 40 reviews a month, that's €1+ per AI-assisted reply, forever, plus price hikes they can't refuse. My side hustle math: a €250 one-time setup on a €300 mini-PC the hotel already has, plus an optional €15/month support retainer. The model costs nothing per token. Open weights are what makes the €250 price point *possible* — closed API margins would eat it alive.

**Ownability is the sales pitch.** "You own it" is three words long and closes better than any feature list. MIT license, one file they can read, a model file on their disk. If I get hit by a bus, their tool keeps working. Try saying that about a venture-funded startup.

## Did I land a user?

Honest answer, since the challenge asks: not yet — I built this in challenge week, between client calls. But it's not a demo in search of a problem: it plugs directly into my existing sales conversations with independent hotels, and the first pilot installs are the next conversations on my list. The reason I believe someone will pay isn't market research. It's that I've had this exact objection-handling conversation twenty times, and this tool is the answer to it, finally priced the way a 12-room hotel thinks.

If you run a small hotel, B&B or guesthouse: the repo is MIT, the setup is one command, and your guests' words never leave your building. That's the whole pitch.

## Built with

- **Gemma 3** (open-weight, via [Ollama](https://ollama.com)) — drafting, multilingual
- **Flask + stdlib Python** — backend, guardrails, zero other dependencies
- **A single HTML page** — the entire frontend
- ☁️ **cloudflared** — temporary demo tunnel for the judging period
- Deterministic regex guardrails — because the code should have the final word

**Live demo:** https://aug-balance-specialty-flu.trycloudflare.com
**Repo:** https://github.com/jeffreyturov-dev/review-reply-studio
