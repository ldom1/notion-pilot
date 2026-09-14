# Notion Pilot

**Deploy the CRM into your Notion workspace in minutes. Run it from Claude Code with our skills and an optional local MCP, on your own machine. Your CRM records are stored in your Notion workspace; what your assistant reads is processed by your assistant's provider.**

Human-in-the-loop by default. Optional capture channels (Telegram, email, Discord) if you want them — not required.

## Customer path

1. **Deploy** at [notion-pilot.com](https://notion-pilot.com/)
2. **Run from Claude Code** — install [notion-pilot-powers](https://github.com/ldom1/notion-pilot-powers)
3. **Data & EU** — see below

Repo README: [ldom1/notion-pilot](https://github.com/ldom1/notion-pilot#readme)

## Data & EU

**Where your data goes.** Your CRM records are stored in your Notion workspace. On the **Notion Enterprise plan**, Notion can host that workspace in the EU (Frankfurt); on other plans, Notion stores it in its default region (US). Region and terms are set by your agreement with Notion ([details](https://www.notion.com/help/data-residency)). EU hosting covers CRM data stored in Notion, not AI processing. When your assistant reads CRM records, that content is processed by your assistant's provider (e.g. Anthropic for Claude), under the provider's data processing terms; Notion's residency does not cover it. Notion states that some of its own AI processing can also happen outside the residency region. notion-pilot.com deploys the CRM structure and keeps no CRM records and no Notion access token.

## Developers

- [[Self-host]] — Docker Compose web + bot, env / Infisical, Coolify, submodule
- [[Capture-channels]] — Telegram, email, Discord
- [[CLI-scripts]] — `scripts/crm/*`, `scripts/inbox/*`
- [[FAQ]]

## Links

- Site: [notion-pilot.com](https://notion-pilot.com/)
- Repo: [ldom1/notion-pilot](https://github.com/ldom1/notion-pilot)
- Plugin: [notion-pilot-powers](https://github.com/ldom1/notion-pilot-powers)
