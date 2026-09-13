# BRIEF — Notion Pilot · the pipeline

- **workflow:** product-launch-video
- **flow:** autonomous
- **destination:** embedded on the notion-pilot landing page, below the Claudeforce section — 16:9, muted autoplay loop, no audio track
- **length:** 21s

## Intent

Show the one thing the landing page asserts but cannot demonstrate in prose: a real
sales email becomes four correct CRM records and a set of current KPIs, without anybody
opening the CRM. Featured film of the three — the widest slot on the page.

## Angle

The pipeline *is* the product. So the film is the pipeline, beat by beat, on the page's
own example deal (Voltaris Énergie / Camille Dubois), using the same figures the page
already shows so the two cannot drift.

## Beats

| Time        | Beat                                                                     |
| ----------- | ------------------------------------------------------------------------ |
| 0–3.8s      | 17:42 Friday. An email lands. Nobody opens the CRM.                      |
| 3.8–9.4s    | The email, its facts lifted out, and the agent's search-before-write log |
| 9.4–13.8s   | The proposed writes, per database — then the approval mark               |
| 13.8–17.6s  | Leads and Activities actually move, in place                             |
| 17.6–19.6s  | The formulas recompute: weighted pipeline, stale deals, next step set    |
| 19.6–21s    | Lockup — "Your CRM, kept current"                                        |

## Customizations

- Design system is `web/frontend/src/styles/tokens.css`, mirrored into `_shared/np.css`:
  white stock, achromatic grey ramp, near-black as the only brand colour. Colour only
  ever lands on CRM data (won / stale / lost). Archivo + IBM Plex Mono, localised.
- No voiceover, no music: the film plays muted on a marketing page.
- Every number, stage name, and record in the film also appears in `Landing.tsx`.
