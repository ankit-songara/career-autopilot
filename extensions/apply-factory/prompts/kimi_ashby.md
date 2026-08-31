# Kimi: Ashby application form

Fill an Ashby-hosted application form (`jobs.ashbyhq.com/<company>/<uuid>` â†’
"Application" tab) using pre-drafted answers.

Ashby is a **heavily React-controlled SPA** â€” expect the same class of quirks
as Greenhouse's new UI, but with Ashby's own component library (no
`select__`-prefixed classes; fields use `_input`/`ashby-application-form-*`
style hashed classes and `aria-*` attributes).

## Inputs

- Answers (from career-ops's Section G + KB):

{ANSWERS_JSON}

- Resume file to upload: `{RESUME_PATH}`
- Snapshot output: `{SNAPSHOT_PATH}`

## Known Ashby mechanics

1. **Two tabs: "Overview" and "Application".** Click the Application tab if
   the form isn't visible.
2. **All inputs are React-controlled â€” the native setter is NOT enough.**
   (Live-confirmed on Bjak 2026-08-31): the native value setter + `input`
   event fills the DOM `.value` but Ashby's React form state stays EMPTY â€”
   submit fails with "Missing entry for required field" for every field.
   The working fill per field:
   1. clear via native setter (`''` + input event), scrollIntoView, fresh rect
   2. REAL trusted CDP click to focus (verify `document.activeElement`)
   3. one `Input.insertText` CDP call with the whole value (works after real
      focus; generates trusted input events React accepts)
   Textareas: same procedure with `HTMLTextAreaElement.prototype` for the clear.
3. **Resume upload + autofill:** Ashby has an "Autofill from resume" /
   "Upload resume" control. The visible button opens an OS file picker CDP
   cannot drive â€” do NOT click it. Find the hidden `input[type=file]` and
   inject: base64 â†’ `atob` â†’ `Uint8Array` â†’ `new File` â†’ `DataTransfer` â†’
   `input.files = dt.files` + `change` event. Wait for parse; re-verify email
   is <your-application-email> afterward.
4. **Dropdowns/comboboxes** are custom React components (`role="combobox"` /
   listbox popups). Synthetic mouse events are ignored â€” use REAL trusted CDP
   clicks: click the combobox to open (verify `aria-expanded="true"`), then
   real click on the desired `[role=option]` INSIDE the open listbox (scope
   the query to the open popup only).
5. **Yes/No questions** are segmented button pairs â€” real click on the button
   whose text matches the answer; verify `aria-pressed="true"`. The page can
   SCROLL-JUMP between calls (wiping your scroll position) â€” do
   scrollIntoView + rect + click in one tight sequence and re-verify.
   Consent checkboxes are native inputs: synthetic `el.click()` works.
6. **Location field** is an autocomplete: real focus click + real char
   keystrokes + real click on the suggestion. Value may read "" after
   selection â€” verify via the wrapper's rendered text.
7. **Stale coordinates:** any scroll invalidates rects. scrollIntoView +
   fresh getBoundingClientRect + click in ONE atomic invocation, always.
8. **EEO / demographic / diversity survey** section is voluntary â†’ leave
   blank or "Prefer not to say".
9. Ashby may show an inline **"Submit application"** button per-tab; there is
   no multi-step wizard â€” one page, one submit.

## Standard answers (work even with empty KB)

- US work authorization / sponsorship â†’ answer from the answer bank (`us_work_authorized` / `us_needs_sponsorship`)
- Authorized to work in India â†’ from the answer bank (`work_authorized_india`)
- Expected compensation â†’ **<expected_ctc>** (full rupees)
- Current location / city â†’ **<your city, country>**
- GitHub â†’ **github.com/<your-handle>**

## Procedure

1. Confirm the Application form is visible (name/email/resume). If login wall
   or external redirect: write `{"error": "not_ashby_form", "url": "<url>"}`
   to `{SNAPSHOT_PATH}`, STOP.
2. Inject resume first (mechanic 3), wait for parse, verify/fix contact
   fields.
3. Walk fields top-to-bottom; match labels to answers (exact â†’ semantic â‰¥0.7
   â†’ else blank + `unfilled_fields`).
4. Snapshot (JSON shape from `kimi_snapshot.md`, `"ats": "ashby"`) to
   `{SNAPSHOT_PATH}`.
5. Click **Submit application** (scrollIntoView + fresh rect, atomic).
6. Ashby may gate with a captcha or email verification â€” if so, STOP and
   report (user supplies codes). Otherwise verify the success screen and
   report.

## Hard rules

- Never invent legal/EEO/sponsorship/salary answers.
- Required field with no matching answer â†’ STOP before submit, report label.
- Captcha / login wall â†’ STOP and report. No evasion.
- Validation failure on submit â†’ report flagged fields; no blind retries.
