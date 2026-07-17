# Manual Notion UI Steps — CRM Migration

These steps **cannot be performed via the Notion API** and must be done by hand in the Notion web or desktop app.
Complete them after all migration scripts have run successfully.

**Quick links (open in Notion):**

| Database | Notion URL |
|----------|------------|
| Deals (Commercial) | `https://www.notion.so/4890e1d6178d4a42af067bbe0cef09fe` |
| People | `https://www.notion.so/11b5f43ca19a4bec94897c6897ed30fb` |
| Companies | `https://www.notion.so/cfc2119896844ef798aefc5657511998` |
| Meetings | `https://www.notion.so/e94cc98f2f664c53acd662b9d8f7d5aa` |
| Activities | `https://www.notion.so/38f6c45194658166a862e531d15f467f` |
| CRM parent page | `https://www.notion.so/36d6c451946580b7af00d80250f0974c` |

---

## Step 1 — Rename "Commercial" → "Deals"

- [ ] Open the CRM parent page in the left sidebar or via the link above
- [ ] Find the "Commercial" database inline on that page
- [ ] Hover over the database title → click `···` (three-dot menu) → **Rename**
- [ ] Type `Deals` → press Enter

---

## Step 2 — Create default views for the Deals database

Open the Deals database (full-page view). For each view below, click **+** next to the last existing tab, choose the view type, name it exactly as shown, then configure filters and sorts.

### 2.1 — 📊 Pipeline (Board view)

- [ ] Click **+** → select **Board**
- [ ] Name the view: `📊 Pipeline`
- [ ] Set **Group by** → `Stage`
- [ ] Open **Filter** → **+ Add a filter**:
  - `Stage` **is not** `Closed Won`
  - `Stage` **is not** `Closed Lost`
  - `Stage` **is not** `No Answer`
  *(use "Add a filter" three times, or use an OR group as needed)*
- [ ] Click **Done** / close the filter panel

### 2.2 — 📅 Closing This Month (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `📅 Closing This Month`
- [ ] Open **Filter** → **+ Add a filter**:
  - `Expected Close Date` **is within** `Current month`
- [ ] Open **Sort** → **+ Add a sort**:
  - `Expected Close Date` → **Ascending**
- [ ] Click **Done**

### 2.3 — ⚠️ No Next Step (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `⚠️ No Next Step`
- [ ] Open **Filter** → **+ Add a filter** (two rules):
  - `Next Step Scheduled` **is unchecked** *(checkbox = false)*
  - `Stage` **is not** `Closed Won`
  - `Stage` **is not** `Closed Lost`
  - `Stage` **is not** `No Answer`
- [ ] Open **Sort** → **+ Add a sort**:
  - `Stage` → **Ascending**
- [ ] Click **Done**

### 2.4 — ❄️ Cold Deals (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `❄️ Cold Deals`
- [ ] Open **Filter** → **+ Add a filter**:
  - `Deal Temperature` **is** `❄️ Cold`
- [ ] Open **Sort** → **+ Add a sort**:
  - `Deal Age (days)` → **Descending**
- [ ] Click **Done**

### 2.5 — 🌡 All Active (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `🌡 All Active`
- [ ] Open **Filter** → **+ Add a filter**:
  - `Stage` **is not** `Closed Won`
  - `Stage` **is not** `Closed Lost`
  - `Stage` **is not** `No Answer`
- [ ] Open **Sort** → **+ Add a sort**:
  - `Days Since Last Activity` → **Descending**
- [ ] Click **Done**

---

## Step 3 — Create default views for the Activities database

Open the Activities database (full-page view). For each view, click **+** next to the last tab.

### 3.1 — Today (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `Today`
- [ ] Open **Filter** → **+ Add a filter**:
  - `Date` **is** `Today`
- [ ] Open **Sort** → **+ Add a sort**:
  - `Date` → **Ascending**
- [ ] Click **Done**

### 3.2 — Overdue Follow-ups (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `Overdue Follow-ups`
- [ ] Open **Filter** → **+ Add a filter** (two rules, both must match):
  - `Next Step Date` **is before** `Today`
  - `Outcome` **is** `➡️ Follow-up Needed`
- [ ] Open **Sort** → **+ Add a sort**:
  - `Next Step Date` → **Ascending**
- [ ] Click **Done**

### 3.3 — This Week (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `This Week`
- [ ] Open **Filter** → **+ Add a filter**:
  - `Date` **is within** `Current week`
- [ ] Click **Done**

### 3.4 — By Deal (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `By Deal`
- [ ] Open **Group** → set **Group by** → `Deal` *(the relation property)*
- [ ] Open **Sort** → **+ Add a sort**:
  - `Date` → **Descending**
- [ ] Click **Done**
  *(No filter — shows all activities, grouped per deal for a full history scroll)*

---

## Step 4 — Create default views for the People database

Open the People database (full-page view).

### 4.1 — 🔥 Needs Follow-up (Gallery view)

- [ ] Click **+** → select **Gallery**
- [ ] Name the view: `🔥 Needs Follow-up`
- [ ] Open **Filter** → **+ Add a filter** → switch filter group to **OR**:
  - `Priority` **is** `🔥 Hot`
  - `Priority` **is** `🌡 Warm`
  *(ensure the two rules are connected with OR, not AND)*
- [ ] Open **Sort** → **+ Add a sort**:
  - `Days Since Last Activity` → **Descending**
- [ ] Click **Done**

### 4.2 — 🌐 Network (Table view)

- [ ] Click **+** → select **Table**
- [ ] Name the view: `🌐 Network`
- [ ] Open **Group** → set **Group by** → `Relationship`
  *(groups: Close / Warm / Cold / None)*
- [ ] Open **Sort** → **+ Add a sort**:
  - `Days Since Last Activity` → **Descending**
- [ ] No filter — leave empty to show everyone
- [ ] Click **Done**

---

## Step 5 — Create the CRM Dashboard page

- [ ] In the left sidebar, click **+** next to the CRM parent page to add a child page
- [ ] Name the page: `📊 CRM Dashboard`
- [ ] Inside the page, use the `/linked` command (type `/linked view`) to insert a **Linked view of database** for each section below:

| Section title (type as heading) | Source database | View to show |
|----------------------------------|-----------------|--------------|
| `Pipeline` | Deals | 📊 Pipeline (Board) |
| `Closing This Month` | Deals | 📅 Closing This Month (Table) |
| `Cold Deals` | Deals | ❄️ Cold Deals (Table) |
| `Overdue Follow-ups` | Activities | Overdue Follow-ups (Table) |
| `Hot Contacts` | People | 🔥 Needs Follow-up (Gallery) |
| `Companies` | Companies | *(default table or any existing view)* |

**For each linked view:**
- [ ] Type `/linked view` → select **Create linked view of database**
- [ ] Pick the source database from the list
- [ ] In the view picker, select the matching view name from the list above
- [ ] Add an H2 heading above each linked view for readability

---

## Step 6 — Set up the Meetings → Activities automation

> **Requires a Notion paid plan** (Business or Enterprise). Skip if on Free.

Open the **Meetings** database (full-page view).

- [ ] Click `···` (three-dot menu at top-right) → **Automations** → **New automation**
- [ ] Name the automation: `Meetings → CRM Activity`

**Trigger:**
- [ ] Click **+ Add trigger** → choose **"When a property is edited"**
- [ ] Property: `Advanced Deal?` *(checkbox)*
- [ ] Condition: value changes to **Checked** ✓

**Action:**
- [ ] Click **+ Add action** → choose **"Add page to"**
- [ ] Target database: **Activities** (`38f6c451-9465-8166-a862-e531d15f467f`)
- [ ] Set the following property mappings:

| Activities property | Value / source |
|---------------------|----------------|
| `Type` | `🤝 Meeting` *(static select value)* |
| `Date` | `Meeting.Date` *(use "Insert property from trigger page")* |
| `Person` | `Meeting.People` *(first relation — use "Insert property from trigger page")* |
| `Deal` | `Meeting.Deal` *(use "Insert property from trigger page")* |
| `Company` | `Meeting.Company` *(use "Insert property from trigger page")* |

- [ ] Click **Save** to activate the automation

**How to use:** When you finish a meeting and want it logged as a CRM activity, open the meeting page and check the `Advanced Deal?` checkbox. Notion will automatically create the corresponding record in Activities.

---

## Post-migration data fixes — People option remapping

After the migration scripts run, existing People records will have old option values in `Priority` and `Relationship`. These must be reassigned manually because Notion does not allow bulk-editing select values via the API.

### Priority field — remap existing values

Open the People database → **All** view (or the default table view). Filter by each old value and manually update:

| Old value (before migration) | New value (after migration) |
|------------------------------|-----------------------------|
| `Non` | `🧊 Cold` |
| `Normal` | `🧊 Cold` |
| `Yes` | `🌡 Warm` |
| `🔥 Key` | `🔥 Hot` |

**How to remap efficiently:**
- [ ] Open People DB → click **Filter** → `Priority` **is** `Non` → select all visible rows → edit `Priority` inline → set to `🧊 Cold` → remove filter
- [ ] Repeat: filter `Priority` **is** `Normal` → set to `🧊 Cold`
- [ ] Repeat: filter `Priority` **is** `Yes` → set to `🌡 Warm`
- [ ] Repeat: filter `Priority` **is** `🔥 Key` → set to `🔥 Hot`

### Relationship field — remap existing values

Apply the same approach for the `Relationship` property:

| Old value | New value |
|-----------|-----------|
| `Non` | `Cold` |
| `Normal` | `Cold` |
| `Yes` | `Warm` |
| `🔥 Key` | `Close` |

- [ ] Open People DB → filter `Relationship` **is** `Non` → bulk-set to `Cold` → remove filter
- [ ] Repeat: filter `Relationship` **is** `Normal` → set to `Cold`
- [ ] Repeat: filter `Relationship` **is** `Yes` → set to `Warm`
- [ ] Repeat: filter `Relationship` **is** `🔥 Key` → set to `Close`

> **Tip:** After remapping, verify by filtering `Priority` **is not empty** and checking that no old option names appear in the dropdown. If they do, they have no records and can be deleted from the property options via `···` → **Edit property** → remove unused options.

---

*Generated for notion-pilot CRM migration — Task 7*
