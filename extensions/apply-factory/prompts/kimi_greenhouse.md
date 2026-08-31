# Kimi: Greenhouse application form

Fill a Greenhouse-hosted company application form (`job-boards.greenhouse.io/<slug>`
or an embedded Greenhouse form) using pre-drafted answers.

Unlike LinkedIn Easy Apply, this is the **company's own ATS form** in the top
frame (no iframe / `isTrusted` quirk), but you MUST **upload the resume file**
(Greenhouse does not store it server-side) and the form is **US-templated** even
for non-US roles.

## Inputs

- Answers (from career-ops's Section G + KB):

{ANSWERS_JSON}

- Resume file to upload: `{RESUME_PATH}`
- Snapshot output: `{SNAPSHOT_PATH}`

## Known Greenhouse mechanics (do not relearn these the hard way)

1. **Plain text inputs are React-controlled.** The reliable fill is the React
   native value setter, not keystrokes:
   ```js
   Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el, v);
   el.dispatchEvent(new Event('input',{bubbles:true}));
   ```
   (use `HTMLTextAreaElement.prototype` for textareas). `Input.insertText`
   works only after a real focus click + select-all.
2. **Location (City) is a Google Places autocomplete** (`#candidate-location`).
   Native-setter values get wiped by React re-render, and typed text clears on
   blur unless a suggestion is clicked. Procedure: scrollIntoView + fresh rect +
   **real trusted click** to focus (verify activeElement), then **real
   char-by-char keystrokes** (e.g. "<city prefix>"), wait for the suggestion, then a
   real click on the suggestion. After selection the input `.value` reads ""
   by design â€” verify via the wrapper's textContent.
3. **File upload:** `DOM.setFileInputFiles` is blocked ("Not allowed") when
   driving via the extension's chrome.debugger. Inject instead:
   base64 â†’ `atob` â†’ `Uint8Array` â†’ `new File` â†’ `DataTransfer` â†’
   `input.files = dt.files` + `change` event on `#resume`. This triggers
   Greenhouse's resume parse/autofill (verify the filename appears in the page
   text afterward; the parse may overwrite email â€” re-check it).
   The visible "Autofill my application" button opens an OS file picker that
   CDP cannot drive â€” do not click it; Escape if opened.
3b. **Custom dropdowns are react-select** (`select__input`, aria-haspopup).
   They IGNORE all synthetic mouse events. Open with a real trusted click on
   `.select__input-container` (aria-expanded flips true), then real click on
   the `.select__option`. Beware: a hidden phone-country listbox permanently
   pollutes `[role=option]` queries â€” scope selectors to the open menu.
3c. **Stale coordinates kill clicks.** Any scroll invalidates cached rects.
   Always scrollIntoView + fresh getBoundingClientRect + click in ONE atomic
   evaluate/invocation. A stray click can set an EEO react-select â€” if that
   happens, click its clear-X icon-button to reset to "Select...".
4. **US-templated legal questions** appear even on a <your-country> role. Answer
   from the loaded answers only â€” never invent. Typical set and the intent_key
   that answers them:
   - "Are you legally authorized to work in the United States?" â†’ answer
     honestly from `us_work_authorized`
   - "Will you now or in the future require sponsorship?" â†’ from
     `us_needs_sponsorship`
   - "Are you authorized to work in India?" â†’ from `india_work_authorized`
   - Desired salary / expected compensation â†’ `expected_ctc` (full rupees, e.g.
     `1200000`, never an "LPA" string)
   - Current city / country of residence â†’ `location` (<your city, country>)
5. **EEO / demographic section** (race, ethnicity, gender, veteran status,
   disability) is **voluntary** â€” the fields carry no `*`. Leave them blank or
   pick "I don't wish to answer" / "Prefer not to answer". Never guess these.
6. **Portfolio / GitHub / website** field â†’ `github` (github.com/<your-handle>).

## Procedure

### 1. Verify it's a real application form

Confirm the page shows the job title + an application form with a first-name /
last-name / email field. If instead it shows only a "Apply" button that opens
an external site, or a login wall, write
`{"error": "not_greenhouse_form", "url": "<current_url>"}` to `{SNAPSHOT_PATH}`
and STOP.

### 2. Walk the form top to bottom

Greenhouse is usually a single long page (sometimes 2 steps: application â†’
demographic). For every visible field:

**a.** Read the label (`<label for=>`, wrapping `<label>`, `aria-label`, or
nearest visible text). Note whether it is required (`*` / `aria-required`).

**b.** Match the label to a key in the answers above:
- Exact question match â†’ use that answer
- Semantic match, confidence â‰¥ 0.7 â†’ use
- No match â†’ leave blank, add the label to `unfilled_fields`

**c.** Free-text â†’ type char-by-char (mechanic 1). Location â†’ typeahead
(mechanic 2). Resume â†’ upload (mechanic 3). Native `<select>` â†’ click to focus,
type the option's first character(s) to typeahead-select, then Enter.

**d.** EEO/demographic fields â†’ mechanic 5 (blank / "prefer not to answer").

### 3. Snapshot, then submit

When the form is fully filled (all required non-EEO fields have values):

1. Walk the DOM once (procedure in `prompts/kimi_snapshot.md`) and build the
   field array. Each field:
   ```
   {"label": "...", "field_type": "...", "value": "...",
    "options": [...], "was_prefilled": true/false, "prefilled_value": "..."}
   ```

2. Write the JSON to `{SNAPSHOT_PATH}`:
   ```json
   {
     "url": "https://job-boards.greenhouse.io/...",
     "captured_at": "2026-...",
     "ats": "greenhouse",
     "fields": [ ... ]
   }
   ```

3. Click **Submit Application** (scrollIntoView + fresh rect first â€” the
   button is usually below the fold).

4. **Email OTP gate:** Greenhouse may respond with "A verification code was
   sent to <email>" and 8 Security-code boxes (anti-bot, plus invisible
   reCAPTCHA). The code goes to the application email. STOP and ask the user
   for the 8-character code, enter it, then submit again.

5. Report: "Submitted. Snapshot saved at {SNAPSHOT_PATH}."

## Hard rules

- **Never** invent answers for legal, EEO, sponsorship, salary, disability,
  veteran, or citizenship fields â€” they come from the answers above or stay
  blank for the user.
- **Never** click "Save" as a draft.
- **If a required field has no matching answer**, STOP before submitting and
  report the field label. Do not guess to get past validation.
- **If the site shows a captcha, login wall, or logs you out**, STOP and report.
  Do not attempt evasion.
- **If validation fails on Submit**, stop and report which fields Greenhouse
  flagged. Do not retry blindly.
