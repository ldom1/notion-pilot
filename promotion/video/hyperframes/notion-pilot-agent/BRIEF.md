# BRIEF — Notion Pilot · the AI agent

- **workflow:** product-launch-video
- **flow:** autonomous
- **destination:** embedded on the notion-pilot landing page, below the Claudeforce section — 16:9, muted autoplay loop, no audio track
- **length:** 16s

## Intent

Answer the objection an autonomous CRM agent raises before anybody asks it: what stops
it writing nonsense into the system of record? The answer is mechanical, not reassuring
prose — `confirm=false` is the default, so the film shows the tool call and what it
returns.

## Angle

Trust through the actual contract. Show the request, show the refusal, show the
human's one-word answer, show the write. Then the four rules that hold every time.

## Beats

| Time       | Beat                                                                  |
| ---------- | --------------------------------------------------------------------- |
| 0–3.6s     | The agent has one rule: nothing is written until you say so           |
| 3.6–9.4s   | `confirm: false` → preview, nothing saved. `confirm: true` → written  |
| 9.6–14s    | The four rules: look first · dry run · you approve · calls too        |
| 14–16s     | Lockup — "You keep the judgement"                                     |

## Customizations

- Same shared design system as the other two films (`_shared/np.css`).
- The rules copy is lifted verbatim from `AGENT_STEPS` in `Landing.tsx`.
- A write that landed is green; a held write is amber. Colour carries state, never mood.
