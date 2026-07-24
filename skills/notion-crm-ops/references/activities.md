# Activities

Append-only event log. Model: `ActivityInput`. Never “upsert” an activity — always CREATE a new row.

## Type enum

`📞 Call` | `📧 Email` | `💼 LinkedIn` | `🎤 Demo` | `🤝 Meeting` | `📄 Proposal` | `🎪 Conference` | `📋 Other`

## Outcome enum

`✅ Positive` | `➡️ Follow-up Needed` | `❌ Negative` | `🔇 No Response`

## Properties

| Field | Notion | Notes |
|-------|--------|-------|
| title | `Name` | French, specific (not just “Email”) |
| type | `Type` | required |
| date | `Date` | ISO date of the event; defaults to today |
| duration_min | `Duration (min)` | minutes; optional |
| outcome | `Outcome` | |
| deal | `Deal` | relation → Lead |
| person | `Person` | relation → People |
| company | `Company` | relation → Companies |
| next_step | `Next Step` | FR |
| next_step_date | `Next Step Date` | |
| notes | `Notes` | source language OK |

## From email threads

Create one activity per meaningful event (send, reply, meeting). Link Deal + Person + Company when known. Planned future meetings: still CREATE with the planned date and Outcome `➡️ Follow-up Needed`.
