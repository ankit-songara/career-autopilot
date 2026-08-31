# LinkedIn Easy Apply — Automation Runbook

The fully-automated Easy Apply flow. Read this first before operating the flow;
it captures what works and the traps that don't.

> **Ethics & safety:** this flow NEVER submits without review unless you have
> explicitly enabled `behavior.auto_submit` in your `answer-bank.yaml`. All
> answers come from your own answer bank — never invent facts a form asks for.
> See `../../LEGAL_DISCLAIMER.md` before using any automation against LinkedIn
> or an ATS; automated interaction may violate their terms of service.

## The key discovery

LinkedIn's Easy Apply modal is rendered **inside an iframe**, and the Easy Apply
button + its native `<select>` dropdowns check `event.isTrusted`. Consequences:

- `document.querySelectorAll` from the top frame **cannot see** the modal's Next
  button, dropdowns, or most fields. DOM-based `click`/`fill` on them silently
  fail or hit the wrong element.
- Synthetic `click`/`fill` (isTrusted=false) are **ignored** by the Easy Apply
  launcher and native selects.

**What works: CDP trusted events at CSS-pixel coordinates.**
`Input.dispatchMouseEvent` / `dispatchKeyEvent` / `insertText` are trusted and
reach iframe content. So the loop is: **screenshot → read pixels → CDP-click**.

## Coordinate mapping (critical)

Check `devicePixelRatio` on your machine (commonly 1.25 on Windows scaling).
Screenshots come back in **device pixels**; CDP wants **CSS pixels**. Always
convert:

    css_x = screenshot_px_x / devicePixelRatio
    css_y = screenshot_px_y / devicePixelRatio

Recompute whenever DPR or the window size changes.

## Native dropdowns — use keyboard, not clicks

Clicking a native `<select>` opens an **OS-drawn** list that is NOT in the page's
coordinate space; a coordinate click on an option falls through and closes the
modal (→ "Save this application?" prompt). Instead:

1. CDP-click the select to focus/open it.
2. Send the option's **first letter** as a key event (`y` → Yes, `n` → No).
3. Send `Enter`.

If the "Save this application?" dialog appears, click its **X** (not Discard, not
Save) to return to the form — no data lost.

## Standard step sequence

| % | Step | Action |
|---|------|--------|
| 0 | Contact info | Pre-filled. Scroll down, click Next. |
| 25–33 | Resume | Your stored resume PDF is already in LinkedIn. Click Next. |
| 50–67 | Top choice (optional) | Leave unchecked. Click Next. |
| 67–75 | Additional Questions | Fill from answer-bank.yaml; dropdowns by typeahead. Click Review. |
| 100 | Review | Scroll down. **Uncheck the "Follow {company}" box** (pre-checked, green) BEFORE submitting if you don't want to auto-follow companies. Then click **Submit application** — only after the user has reviewed, unless auto-submit is explicitly enabled. |

Button coordinates shift with layout — always verify per screenshot before
clicking; never replay coordinates blindly across postings.

## Answer bank

`answer-bank.yaml` (copied from `answer-bank.example.yaml`) holds your confirmed
defaults: compensation, experience, notice period, work authorization,
relocation, and per-skill answers. Update it, not this file, when values change.
It is personal — keep it gitignored and out of any public fork.

## The local driver

`linkedin_auto_apply.py` wraps all the CDP plumbing:

    python linkedin_auto_apply.py check
    python linkedin_auto_apply.py open  <jobUrl>      # opens + clicks Easy Apply
    python linkedin_auto_apply.py shot                # screenshot for the agent to read
    python linkedin_auto_apply.py next  [x y]         # click Next/Review
    python linkedin_auto_apply.py dropdown <cssY> Yes # answer a native select
    python linkedin_auto_apply.py text  <x> <y> "..." # fill a text field
    python linkedin_auto_apply.py scroll [delta]
    python linkedin_auto_apply.py submit [x y]

The agent is the decision layer: it reads each screenshot, decides answers from
the profile + answer-bank, and calls these primitives. The script is the
reliable actuation layer so the CDP details never get re-derived.

## ATS-specific notes (learned across batches)

- **SmartRecruiters / Ceipal / Lever** forms are longer (5–7 steps): they add
  Work experience + Education steps (both prefill from the LinkedIn profile —
  just Next through) and richer Additional Questions.
- **Location fields** are often typeahead autocompletes: `text` the city, then a
  suggestion list appears — click the first suggestion (in-page, a normal click
  works) before Next, or validation blocks you.
- **Range dropdowns** ("1-3 years" vs "10-13 years"): typeahead is unreliable
  (first-letter collisions). Use `steps <y> up|down <n>` — focus, Escape, arrow
  while closed. Read a screenshot to confirm; adjust by ±1 if off.
- **Two salary fields close together** (Expected Salary + Total CTC) are easy to
  mis-map by a few pixels. After filling, screenshot and verify each; use
  `retext` (clear + type) to fix a field that already has the wrong value —
  plain `text` only appends.
- **Privacy consent** checkboxes ("I consent") are required on SmartRecruiters —
  click the box before Review.
- **Salary convention:** know both scales for your numbers — full annual rupees
  (e.g. ₹12L = `1200000`) and LPA (`12`). Fill variable pay `0` unless you have
  one, and your real notice period in days.
- **Numeric-validation on comp/notice fields:** many ATS ask "current CTC in
  INR / LPA" and "notice period in days" as text fields that reject non-numeric
  input ("Enter a decimal number larger than 0.0"). Type PLAIN NUMBERS: CTC in
  LPA or full rupees depending on the example hint next to the label; notice as
  a bare day count. Never append "LPA"/"days".
- **PyjamaHR custom dropdowns:** styled selects (not native) whose option list
  renders IN-PAGE and often opens UPWARD, overlapping the label. Keyboard
  typeahead still works: click to focus, press the option's first char (e.g.
  `3` → "3 years", `6` → "6 months"), then Enter. Wheel-scroll with the cursor
  OUTSIDE the list closes it — reopen and typeahead instead.
- **Skill-years questions with prefilled defaults:** LinkedIn pre-fills some at
  0/low. Overwrite them (`retext`) with the honest values from your answer
  bank's per-skill entries; leave 0 only for skills you genuinely haven't
  touched. Never claim years in a stack you haven't worked in.
- **Low-fit skip discipline:** discard (don't submit) roles that are a clear
  mismatch — wrong stack, or an Easy Apply that funnels to a student/campus
  intake form (Year-of-Study fields, intern track). Log them as `Discarded` in
  the tracker with the reason.
- **Window-resize breaks coordinates:** if the user maximizes the browser, the
  viewport grows and ALL calibrated modal coords break. Detect it (screenshot
  much wider than expected; check `window.innerWidth`) and re-lock the layout
  with CDP `Emulation.setDeviceMetricsOverride` (your calibrated
  width/height/deviceScaleFactor). NOTE: the override is cleared on navigation,
  so re-assert it after each `open`/`navigate` if the window is maximized.
  Downside: screenshots get slow under the override and intermittently time
  out — wrap `shot` in a retry (`shot || shot || shot`); the underlying
  click/scroll still executes even when the bundled screenshot times out.
- **Duplicate reposts under different "Inc" names:** staffing shops repost the
  SAME underlying role (identical company description) under multiple LinkedIn
  employer names. Read the "Company Description" — if it matches a role already
  applied, DISCARD the duplicate instead of double-applying.
- **Short forms auto-advance past the follow-uncheck step:** on very short forms
  (Contact→Resume→one AQ), clicking the primary button can submit before a
  separate review/Follow page appears, so the "Follow" box can't be unchecked.
  If this happens, unfollow the company manually afterward and note it.
- **"Job search safety reminder" interstitial:** for some new/unverified
  employers, clicking Easy Apply first shows a "Job search safety reminder"
  dialog (Research the company / Report suspicious jobs) with **"Review job
  post"** and **"Continue applying"**. Click **Continue applying** to proceed
  into the normal modal.
- **Easy Apply button selector can miss (`found:false`):** `easy_apply_coords()`
  looks for `a[aria-label="Easy Apply to this job"]`; some postings render it
  differently so it returns `found:false` even though the button is visible.
  Fall back to a direct CDP click at the button's on-screen position.
- **Zoho-powered forms — location field is an autocomplete:** a "Location
  (city)" field that shows "Please enter a valid answer" even with a typed city
  needs an autocomplete SELECTION. `Input.insertText` alone doesn't fire the
  keystroke events the widget listens for — type the city character-by-character
  with `dispatchKeyEvent` (keyDown+keyUp per char), wait for the suggestion
  list, then CLICK the first suggestion. US-staffing Zoho forms also ask full
  address (City/State/Zip), Current Employer, Experience-in-Years, Work
  Authorization (pick your true status via keyboard typeahead, since the native
  select falls through on click), GitHub, LinkedIn URL, and optional document
  uploads.
- **Submit that loops back to step 1 = broken posting:** if clicking Submit
  repeatedly returns to the Contact step (not "Application sent"), the posting's
  form flow is broken on LinkedIn's end. Don't keep retrying — abandon after
  ~2-3 attempts and log it Discarded.
- **Email-gated applications need the user (permission boundary):** some AQs
  require confirming you've emailed a named recruiter or filled an external
  form. Sending outbound email to a real person is out of scope for autonomous
  apply. Do NOT answer "Yes" (it would be false). Instead fill everything else,
  click **Save** (not Discard) to preserve the draft, and surface it to the user
  as a manual to-do (send the email, then finish + submit).
- **Commitment/policy AQs:** some roles ask acceptance questions like "This job
  requires US hours. Is that acceptable?" or "Will you be working a 2nd job?" —
  answer these from the user's actual stated preferences (they are choices, not
  facts to optimize). Capability questions ("Do you have expertise in X?") are
  answered Yes only when backed by the answer bank or CV.
- **Off-stack forms — discard, don't misrepresent:** a posting whose AQs gate
  entirely on *professional* experience in a stack the profile has never worked
  in is a clear mismatch. Answering Yes anyway is fabrication. Close the modal →
  **Discard** → log `Discarded` with reason.

## After a batch

1. Write one TSV per application to `batch/tracker-additions/NNN-slug-DATE.tsv`
   (cols: num, date, company, role, `applied`, `—`, `❌`, ``, note, url).
2. `node ../../merge-tracker.mjs` from the career-ops root.
3. Score sentinel MUST be `—` (never a bare number — the column-swap guard
   rejects numeric scores in the score column and skips the row).
