# Kimi: Lever application form

Fill a Lever-hosted application form (`jobs.lever.co/<company>/<id>/apply`)
using pre-drafted answers.

Lever is the SIMPLEST major ATS: a single classic HTML form (not React-heavy
like Greenhouse), one page, POST on submit. Most fields are plain
`<input>`/`<textarea>`/native `<select>`.

## Inputs

- Answers (from career-ops's Section G + KB):

{ANSWERS_JSON}

- Resume file to upload: `{RESUME_PATH}`
- Snapshot output: `{SNAPSHOT_PATH}`

## Known Lever mechanics

1. **URL shape matters.** The posting page is `jobs.lever.co/<co>/<id>`; the
   form lives at `.../apply` â€” click "Apply for this job" if you're on the
   posting page.
2. **Standard field names** (stable across companies): `name` (FULL name, one
   field â€” use the candidate's full name), `email`, `phone`, `org` (current company),
   `urls[LinkedIn]`, `urls[GitHub]`, `urls[Portfolio]`, `comments`
   (cover letter / additional info), `resume` (file input).
3. **Text inputs are plain HTML** â€” the React native-setter is unnecessary but
   harmless; setting `.value` + dispatching `input` and `change` events works.
4. **Resume upload:** `DOM.setFileInputFiles` is blocked via chrome.debugger.
   Inject: base64 â†’ `atob` â†’ `Uint8Array` â†’ `new File` â†’ `DataTransfer` â†’
   `input[name=resume].files = dt.files` + `change` event. Lever parses the
   resume ("Your file is being processed" spinner) â€” WAIT for the parse to
   finish before filling other fields, it may overwrite name/email/phone.
   Re-verify email is <your-application-email> after parse.
5. **Custom questions** live under `cards[...]` field names â€” checkboxes,
   radios, dropdowns, and textareas. Radios/checkboxes are native inputs:
   `el.click()` works. Native `<select>`: set `.value` to the option value +
   `change` event.
6. **Location field** (when present, `location` input) is a typeahead backed by
   a suggestion list â€” same procedure as Greenhouse Places: real focus click,
   real char keystrokes ("<city prefix>"), click the suggestion.
7. **EEO / demographic** ("U.S. Equal Employment Opportunity", pronouns,
   gender, race, veteran) is voluntary â†’ leave blank or "Decline to
   self-identify".
8. **hCaptcha** may appear at the bottom. If a visible challenge blocks
   submission, STOP and report â€” do not attempt evasion.
9. **Stale coordinates:** always scrollIntoView + fresh getBoundingClientRect
   + click in ONE atomic invocation.

## Standard answers (work even with empty KB)

- US work authorization / sponsorship â†’ answer from the answer bank (`us_work_authorized` / `us_needs_sponsorship`)
- Authorized to work in India â†’ from the answer bank (`work_authorized_india`)
- Expected compensation â†’ **<expected_ctc>** (full rupees)
- Current location / city â†’ **<your city, country>**
- GitHub â†’ **github.com/<your-handle>**

## Procedure

1. Confirm you're on the `/apply` form (name/email/resume fields visible).
   If a login wall or non-Lever redirect: write
   `{"error": "not_lever_form", "url": "<url>"}` to `{SNAPSHOT_PATH}`, STOP.
2. Upload resume FIRST (mechanic 4), wait for parse, then verify/fix
   name/email/phone.
3. Walk remaining fields top-to-bottom; match labels to answers (exact â†’
   semantic â‰¥0.7 â†’ else leave blank + record in `unfilled_fields`).
4. Snapshot the form (same JSON shape as `kimi_snapshot.md`, `"ats": "lever"`)
   to `{SNAPSHOT_PATH}`.
5. STOP and show the user what was filled. Only click **Submit application**
   (scrollIntoView + fresh rect) after the user confirms, or if auto-submit
   is explicitly enabled (`behavior.auto_submit: true` in answer-bank.yaml
   AND `auto_submit: true` in config.yaml).
6. Verify the confirmation ("Application submitted"/thank-you page) and report.

## Hard rules

- Never submit without user confirmation unless auto-submit is explicitly
  enabled in both answer-bank.yaml and config.yaml.
- Never invent legal/EEO/sponsorship/salary answers.
- If a required field has no matching answer, STOP before submitting and
  report the label.
- Captcha challenge / login wall â†’ STOP and report.
- Validation failure on submit â†’ report flagged fields, do not retry blindly.
