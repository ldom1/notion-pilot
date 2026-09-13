import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

// the package is ESM ("type": "module"), so __dirname is unavailable
const HERE = path.dirname(fileURLToPath(import.meta.url));

/**
 * The real deploy wizard, really creating databases in Notion.
 *
 * This is the test that proves the wizard works — not that its UI renders, which
 * wizard.spec.ts already covers, but that clicking Deploy produces five
 * databases with working rollups in an actual workspace.
 *
 * It needs three things, and skips cleanly without any of them:
 *
 *   1. `E2E_LIVE_BASE_URL` — a running FastAPI app (not the static preview).
 *   2. `e2e/.auth/state.json` — a session, since Notion OAuth cannot be scripted.
 *      **It must be a real OAuth session**, captured once by hand:
 *
 *          npx playwright open --save-storage=e2e/.auth/state.json \
 *            http://127.0.0.1:8099/auth/notion
 *
 *      Complete the Notion authorization, then close the browser. A session
 *      minted from the internal-integration NOTION_TOKEN
 *      (scripts/e2e/mint_session.py) authenticates fine but **cannot run the
 *      deploy**: create_workspace_root_page posts `parent: {workspace: true}`,
 *      and Notion rejects that for internal integrations —
 *      "Internal integrations aren't owned by a single user, so creating
 *      workspace-level private pages is not supported." Only a public-integration
 *      OAuth token has the insert_content capability the wizard needs.
 *   3. `E2E_ALLOW_REAL_DEPLOY=1` — an explicit acknowledgement, because this
 *      cannot be sandboxed. create_workspace_root_page posts
 *      `parent: {workspace: true}`, so the wizard always creates a **top-level**
 *      page; there is no parent to confine it to. Set `E2E_NOTION_TOKEN` as well
 *      and the test archives what it created; without it the page id is printed
 *      for you to archive by hand.
 *
 * Run:
 *   uv run uvicorn web.server:create_app --factory --port 8080     # terminal 1
 *   uv run python scripts/e2e/mint_session.py                       # terminal 2
 *   E2E_LIVE_BASE_URL=http://127.0.0.1:8080 \
 *   E2E_NOTION_PARENT_PAGE_ID=<page id> \
 *   npm run e2e:live
 */

const AUTH = path.join(HERE, ".auth", "state.json");
const LIVE = process.env.E2E_LIVE_BASE_URL;
const ALLOWED = process.env.E2E_ALLOW_REAL_DEPLOY === "1";
const CLEANUP_TOKEN = process.env.E2E_NOTION_TOKEN;

/** Archive a page so a real deploy does not litter the workspace. */
async function archive(pageId: string): Promise<string> {
  if (!CLEANUP_TOKEN) return "skipped (set E2E_NOTION_TOKEN to auto-archive)";
  const res = await fetch(`https://api.notion.com/v1/pages/${pageId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${CLEANUP_TOKEN}`,
      "Notion-Version": "2022-06-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ archived: true }),
  });
  return res.ok ? "archived" : `FAILED (${res.status})`;
}

test.describe("wizard against real Notion", () => {
  test.skip(!LIVE, "set E2E_LIVE_BASE_URL to a running FastAPI app");
  test.skip(!existsSync(AUTH), "run scripts/e2e/mint_session.py first — no e2e/.auth/state.json");
  test.skip(
    !ALLOWED,
    "set E2E_ALLOW_REAL_DEPLOY=1 — this creates a real top-level Notion page and cannot be sandboxed",
  );

  test.use({ storageState: AUTH });
  // a real deploy creates six databases and patches rollups onto three of them
  test.setTimeout(180_000);

  test("deploys a five-database CRM and reports the workspace", async ({ page }) => {
    // sanity-check the forged session before blaming the wizard for a 401
    const status = await page.request.get(`${LIVE}/api/cockpit/status`);
    expect(
      status.status(),
      "the minted session was rejected — re-run mint_session.py against the same " +
        "WEB_SESSION_SECRET the server is using",
    ).toBe(200);

    await page.goto("/?connected=1");
    await expect(page.getByRole("heading", { name: "Set up your workspace" })).toBeVisible();

    const name = `E2E CRM ${new Date().toISOString().slice(0, 19)}`;
    await page.locator("input.modal-param-input").fill(name);
    await page.getByRole("button", { name: "CRM", exact: true }).click();
    await page.getByRole("button", { name: /Deploy|Create/i }).click();

    // The deploy really calls Notion, so allow time — but race the success
    // state against the wizard's error line, otherwise a 400 on the very first
    // request burns the full timeout before reporting anything useful.
    const ready = page.getByRole("heading", { name: "Workspace ready!" });
    const failed = page.getByText(/^✗/);
    await expect
      .poll(
        async () => {
          if (await ready.isVisible()) return "ready";
          if (await failed.isVisible()) return await failed.first().innerText();
          return "pending";
        },
        { timeout: 150_000, intervals: [1000] },
      )
      .toBe("ready");

    // every database the wizard claims must have been logged
    for (const db of ["Companies", "People", "Leads", "Meetings", "Activities"]) {
      await expect(page.getByText(new RegExp(`→\\s*${db} database`))).toBeVisible();
    }
    await expect(page.getByText(/→\s*Rollups and pipeline formulas/)).toBeVisible();
    await expect(page.getByText(/✓ CRM ready/)).toBeVisible();

    // and the user must be handed a link to what was created — the affordance a
    // premature redirect used to eat
    const open = page.getByRole("link", { name: /Open in Notion/ });
    await expect(open).toBeVisible();
    const href = await open.getAttribute("href");
    expect(href, "the done event carried no workspace URL").toMatch(/notion\.so/);

    const pageId = (href ?? "").split("/").pop() ?? "";
    const outcome = await archive(pageId);
    console.log(`\ndeployed workspace: ${href}\ncleanup: ${outcome}`);
  });

  test("persists the Activities id so logging an activity works afterwards", async ({ page }) => {
    // The point of creating Activities is that log_activity stops hard-failing.
    // A deploy that creates the database but does not persist its id leaves the
    // product's headline flow just as broken, and nothing in the UI would show it.
    const cfg = await page.request.get(`${LIVE}/api/cockpit/config`);
    if (cfg.status() !== 200) {
      test.skip(true, `/api/cockpit/config returned ${cfg.status()}`);
    }
    const body = await cfg.json();
    const ids = body.databases ?? body;
    expect(
      ids.notion_activities_database_id,
      "Activities id was not persisted — POST /api/cockpit/log-activity will 400",
    ).toBeTruthy();
    expect(ids.notion_meetings_database_id, "Meetings id was not persisted").toBeTruthy();
  });
});

/** Guard: the auth file must never be committed — it holds a real Notion token. */
test("the minted session file is not tracked by git", async () => {
  test.skip(!existsSync(AUTH), "no auth file to check");
  const gitignore = readFileSync(path.join(HERE, "..", "..", "..", ".gitignore"), "utf8");
  expect(gitignore, ".gitignore must exclude e2e/.auth/").toMatch(/e2e\/\.auth/);
});
