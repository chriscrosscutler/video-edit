# Compliance

Read before delivering anything sponsored, affiliate, AI-assisted or scored with library music or
sound effects. US rules unless noted; checked October 2026. Rules change: re-check a source before
relying on it for a new kind of deal. This is a checklist, not legal advice.

## Sponsorship disclosure (FTC, 16 CFR 255, revised 2023)

Applies when a brand paid, gifted, discounted, reimbursed or otherwise rewarded the creator, or
the creator earns from a link.

- **In the medium of the endorsement.** A video endorsement discloses in the video: on screen, said
  aloud, or both (both is best). A caption, a profile bio or a "more" fold alone is not enough.
- **Unavoidable.** On screen long enough to read, big enough, in contrast, not lost among hashtags;
  at the start, and again before a mid-video endorsement. The FTC sets no seconds rule.
- **Words that work:** "Brand paid me to try this", "Sponsored by Brand", "Paid post", "Brand sent me
  this for free", "#ad" at the start. Plain words in the creator's own voice are fine.
- **Words that fail alone:** "gifted" without who gave it, "#ambassador", "#partner", "#collab",
  "#comped", "#hosted", "sp", "spon", a thank-you to the brand.
- **Affiliate links:** disclose in the video and next to the link. "Paid link" or "I earn from
  this link" works; "affiliate link" alone may not be understood.
- Platform branded-content tools (Instagram's paid-partnership label, TikTok's content disclosure
  toggle) are each platform's own rule and add to, not replace, the FTC disclosure. Whether to use
  them is the creator's call.

## Amazon Associates

- The account's statement "As an Amazon Associate I earn from qualifying purchases" must appear
  where links appear (a bio or link page counts for the account).
- No prices burned into video: Amazon prices change and must carry a timestamp disclaimer, which a
  video cannot keep current. Say "under $20" only if the project allows it.
- No link shorteners that hide amazon.com, no paid boosting of posts with Associates links, no
  Amazon product images taken from listings (policies updated 2026-04-14).

## AI content labels

- **TikTok:** realistic AI-generated or heavily AI-edited people, places or events must be labelled
  (Community Guidelines effective 2026-09-24); files carrying C2PA credentials are labelled
  automatically.
- **Meta (Instagram, Facebook):** an "AI info" label from C2PA indicators or self-disclosure.
- **YouTube:** the "altered or synthetic" setting for realistic altered content. Exempt: beauty
  filters, background blur, colour and upscaling, audio repair. A synthetic voice reading a script
  over real footage is borderline; disclose.
- Editing a real person's footage (cuts, grade, captions, noise reduction) needs no label.

## Music and sound effects

| Source | Allowed | Not allowed |
|---|---|---|
| Epidemic Sound Creator | The creator's own channels, monetized | Brand promotion, paid ads, client work (needs Pro or Business) |
| Epidemic Sound Pro | Client work, ads | Check seat and channel limits |
| Artlist Social | One channel per platform; 100 SFX downloads a day | Promotion and paid media |
| Instagram Sound Collection, TikTok Commercial Music Library | Business accounts, in-app | Meta's music guidelines bar commercial use of the general library |
| Pixabay sounds and music | Commercial, no credit (terms of 2026-10-20) | Selling the sounds as they are |
| Freesound CC0 | Anything | |
| Freesound CC-BY | With a credit in the caption | CC-BY-NC: never in a sponsored or monetized video |
| Mixkit (Free License) | Social posts and ads | Redistribution |
| Zapsplat free tier | With a "ZapSplat" credit (unconfirmed) | |
| YouTube Audio Library | YouTube only | Other platforms |
| BBC Sound Effects (RemArc) | Personal, educational | Commercial |
| Sonniss GDC bundles | Licence v2.0, royalty-free | Social use not named; ask |

Keep each file's source page, licence and SHA-256 in `music/SOURCES.txt` or `sfx/SOURCES.txt`.
Downloaded trend audio (yt-dlp) is a timing reference only, never in a render; trending sounds are
added by the person in the app after export.

## Originality

Instagram recommends reposts and videos with "noticeable watermarks" less; TikTok keeps unoriginal
content out of For You. Never deliver a render carrying another app's watermark (`edl.py qa` errors
on TikTok, CapCut and similar marks found on screen). Re-using the creator's own footage is fine.

## Privacy on screen

Before delivery, nothing readable that identifies a private person: shipping labels, addresses,
phone numbers, emails, tracking numbers, another person's face who did not agree, a screen with
notifications. `edl.py qa` reads on-screen text and errors on these; blur them in the edit
(render.md).
