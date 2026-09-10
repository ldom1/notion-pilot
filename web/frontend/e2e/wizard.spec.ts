import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Deploy-wizard UI, with Notion and the API fully intercepted.
 *
 * The real flow is: Deploy → Notion OAuth → callback with ?connected=1 → the
 * wizard → POST /api/setup/stream (SSE) → databases created. OAuth cannot be
 * automated, so these tests enter at the ?connected=1 step and stub the stream.
 * That still covers what actually breaks: whether the wizard renders, whether
 * each SSE event reaches the log, and whether the terminal states are right.
 *
 * The real deployment is covered separately by wizard-live.spec.ts.
 */

const STATUS_OK = {
  databases: [],
  workspace_name: "Playwright Workspace",
  user_name: "Playwright",
  workspace_url: "",
};

/** Build an SSE response body the way web/server.py writes it. */
function sse(events: object[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}

async function stubStatus(page: Page) {
  await page.route("**/api/cockpit/status", (route: Route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(STATUS_OK) }),
  );
}

/** The log lines web/server.py emits for a `crm` deploy, in order. */
const CRM_LOG = [
  { type: "log", message: "Creating root page…" },
  { type: "log", message: "✓ Root page created" },
  { type: "log", message: "Creating CRM page…" },
  { type: "log", message: "  → Companies database" },
  { type: "log", message: "  → People database" },
  { type: "log", message: "  → Leads database" },
  { type: "log", message: "  → Meetings database" },
  { type: "log", message: "  → Activities database" },
  { type: "log", message: "  → Rollups and pipeline formulas" },
  { type: "log", message: "✓ CRM ready (with demo data)" },
  { type: "log", message: "✓ Cockpit configured" },
];

test.describe("deploy wizard", () => {
  test.beforeEach(async ({ page }) => {
    await stubStatus(page);
  });

  test("renders after the OAuth callback and defaults to both scopes", async ({ page }) => {
    await page.goto("/?connected=1");

    await expect(page.getByRole("heading", { name: "Set up your workspace" })).toBeVisible();
    await expect(page.locator("input.modal-param-input")).toHaveValue("My Notion Workspace");
    // "Both" is the default and is the selected chip
    await expect(page.getByRole("button", { name: "Both" })).toHaveClass(/selected/);
    await expect(page.getByText("CRM + Knowledge inbox")).toBeVisible();
  });

  test("choosing the CRM scope names the five databases it will create", async ({ page }) => {
    await page.goto("/?connected=1");
    await page.getByRole("button", { name: "CRM", exact: true }).click();

    await expect(page.getByRole("button", { name: "CRM", exact: true })).toHaveClass(/selected/);
    // This description is the promise the wizard makes before deploying — it has
    // to match what create_crm_workspace actually creates.
    const desc = page.getByText(/Companies/).first();
    await expect(desc).toContainText("People");
    await expect(desc).toContainText("Leads");
    await expect(desc).toContainText("Activities");
    await expect(desc).toContainText("Meetings");
  });

  test("streams every log line and reaches the ready state", async ({ page }) => {
    await page.route("**/api/setup/stream", (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([
          ...CRM_LOG,
          { type: "done", url: "https://www.notion.so/deadbeefdeadbeefdeadbeefdeadbeef" },
        ]),
      }),
    );

    await page.goto("/?connected=1");
    await page.getByRole("button", { name: "CRM", exact: true }).click();
    await page.getByRole("button", { name: /Deploy|Create/i }).click();

    // every database the wizard claims to create must appear in the log
    for (const name of ["Companies", "People", "Leads", "Meetings", "Activities"]) {
      await expect(page.getByText(new RegExp(`→\\s*${name} database`))).toBeVisible();
    }
    await expect(page.getByText(/→\s*Rollups and pipeline formulas/)).toBeVisible();

    await expect(page.getByRole("heading", { name: "Workspace ready!" })).toBeVisible();
    const open = page.getByRole("link", { name: /Open in Notion/ });
    await expect(open).toHaveAttribute(
      "href",
      "https://www.notion.so/deadbeefdeadbeefdeadbeefdeadbeef",
    );
    await expect(page.getByRole("button", { name: /Go to Cockpit/ })).toBeVisible();
  });

  test("surfaces a Notion error instead of claiming success", async ({ page }) => {
    await page.route("**/api/setup/stream", (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([
          { type: "log", message: "Creating root page…" },
          { type: "error", message: "Notion API error: unauthorized" },
        ]),
      }),
    );

    await page.goto("/?connected=1");
    await page.getByRole("button", { name: /Deploy|Create/i }).click();

    await expect(page.getByText(/✗ Notion API error: unauthorized/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Workspace ready!" })).toHaveCount(0);
  });

  test("will not deploy without a workspace name", async ({ page }) => {
    await page.goto("/?connected=1");
    const deploy = page.getByRole("button", { name: /Deploy|Create/i });
    await expect(deploy).toBeEnabled();

    await page.locator("input.modal-param-input").fill("");
    // guarded at the control, not just in the handler
    await expect(deploy).toBeDisabled();
  });
});

test.describe("landing page", () => {
  test("an unauthenticated visitor gets a Deploy entry point", async ({ page }) => {
    // fetchStatus failing is what puts the landing page in its marketing state.
    // Kept copy-agnostic on purpose: the page's wording is owned by a different
    // branch, and this assertion should not break when marketing rewrites it.
    await page.route("**/api/cockpit/status", (route: Route) => route.fulfill({ status: 401 }));
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const deploy = page.locator('a[href="/auth/notion"], button:has-text("Deploy")').first();
    await expect(deploy).toBeVisible();
  });
});
