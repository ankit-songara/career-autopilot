#!/usr/bin/env python3
"""
LinkedIn Easy Apply — local automation driver.

Drives LinkedIn's multi-step Easy Apply modal end-to-end through Kimi WebBridge
using CDP (trusted) mouse/keyboard events. This is the technique that actually
works: LinkedIn's Easy Apply button and its native <select> dropdowns live in an
iframe and check event.isTrusted, so synthetic DOM clicks are ignored. CDP
Input.dispatch{Mouse,Key}Event events are trusted and reach iframe content.

WHAT THIS SCRIPT DOES
  - Opens each LinkedIn job URL, clicks Easy Apply.
  - Walks Contact -> Resume -> (Top choice) -> Additional Questions -> Review.
  - Fills known answers; answers dropdowns by keyboard typeahead (focus the
    <select>, press first letter, Enter). The answer values come from the
    agent driving this script (which reads answer-bank.yaml) — this script
    itself does not parse the answer bank.
  - `submit` is a bare click primitive with NO built-in gate: it clicks
    whatever is at the Submit coordinates. The caller (you, or the agent
    following the kimi_*.md prompts) is the only submit gate — the prompts
    require user confirmation unless auto-submit is explicitly enabled in
    both answer-bank.yaml and config.yaml.

WHAT IT DELIBERATELY DOES NOT DO (yet)
  - It cannot *read* arbitrary new additional-question text on its own — the
    modal is in an iframe unreachable from top-frame JS. For unknown questions a
    human (or the Claude/Kimi agent driving this) reads the screenshot and calls
    answer_dropdown()/fill_text() with the right value. This script is the
    reliable *actuation* layer; the agent is the *decision* layer.

USAGE
  python linkedin_auto_apply.py check                 # daemon reachable?
  python linkedin_auto_apply.py open <jobUrl>         # open job + click Easy Apply
  python linkedin_auto_apply.py shot [path]           # screenshot current modal
  python linkedin_auto_apply.py next                  # click primary (Next/Review)
  python linkedin_auto_apply.py submit                # click Submit application
  python linkedin_auto_apply.py dropdown <y> <Yes|No> # answer a native select by row-y (CSS px)
  python linkedin_auto_apply.py text <x> <y> "value"  # focus a text field and type
  python linkedin_auto_apply.py scroll [deltaY]       # wheel-scroll the modal

Coordinates are CSS pixels (screenshot px / devicePixelRatio). The agent reads a
screenshot, maps pixels, and calls these primitives. All the fiddly CDP plumbing
lives here so the agent never re-derives it.
"""
import json, sys, time, urllib.request, pathlib

DAEMON = "http://127.0.0.1:10086/command"
SESSION = "linkedin-easy-apply"
HERE = pathlib.Path(__file__).parent


def cmd(action, args=None):
    body = json.dumps({"action": action, "args": args or {}, "session": SESSION}).encode()
    req = urllib.request.Request(DAEMON, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def cdp(method, params):
    return cmd("cdp", {"method": method, "params": params})


def click(x, y):
    cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    time.sleep(0.12)
    cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    time.sleep(0.4)


def key(k, text=None):
    p = {"type": "keyDown", "key": k}
    if text:
        p["text"] = text
    if k == "Enter":
        p.update({"code": "Enter", "windowsVirtualKeyCode": 13})
    cdp("Input.dispatchKeyEvent", p)
    up = {"type": "keyUp", "key": k}
    if k == "Enter":
        up.update({"code": "Enter", "windowsVirtualKeyCode": 13})
    cdp("Input.dispatchKeyEvent", up)


def scroll(delta=600):
    cdp("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": 530, "y": 400, "deltaX": 0, "deltaY": delta})
    time.sleep(0.8)


def shot(path=None):
    path = path or str(HERE / "snapshots" / "current.jpg")
    return cmd("screenshot", {"format": "jpeg", "quality": 55, "path": path})


def easy_apply_coords():
    # The Easy Apply <a aria-label="Easy Apply to this job"> sits at a stable
    # top-card position; grab its center in CSS px.
    code = ("(() => { const a=document.querySelector('a[aria-label=\"Easy Apply to this job\"]');"
            "if(!a) return JSON.stringify({found:false}); a.scrollIntoView({block:'center'});"
            "const r=a.getBoundingClientRect();"
            "return JSON.stringify({found:true,x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)});})()")
    res = cmd("evaluate", {"code": code})
    return json.loads(res["data"]["value"])


def open_job(url):
    cmd("navigate", {"url": url})
    time.sleep(3)
    c = easy_apply_coords()
    if not c.get("found"):
        print(json.dumps({"error": "no_easy_apply_button", "note": "external Apply or already applied"}))
        return
    click(c["x"], c["y"])          # trusted click opens the iframe modal
    time.sleep(2)
    shot()
    print(json.dumps({"ok": True, "opened": url, "clicked_easy_apply_at": c}))


def answer_dropdown(row_y, value):
    """Answer a native <select> by clicking its row (CSS y) then keyboard typeahead.

    Good for UNAMBIGUOUS first letters (Yes/No, Male). For range options where
    several share a first letter (e.g. '1-3 years' vs '10-13 years') typeahead is
    unreliable — use dropdown_steps() instead.
    """
    click(419, row_y)              # focus + open native dropdown (x=419 is modal center-ish)
    time.sleep(0.4)
    first = value.strip()[0].lower()
    key(first, first)              # typeahead jumps to Yes/No/etc
    time.sleep(0.25)
    key("Enter")
    time.sleep(0.4)
    shot()


def dropdown_steps(row_y, direction, n):
    """Deterministic native-<select> selection: focus, Escape to close (keeping
    focus + value), then arrow the value by n steps. Arrowing a *closed* focused
    select changes the value directly with no OS list to intercept clicks — this
    is the reliable path for range dropdowns. `direction` is 'up' or 'down'.
    Count steps from the current (or reset) value; caller reads a screenshot to
    verify. Value does not need Enter when the list stays closed.
    """
    click(419, row_y)
    time.sleep(0.4)
    key("Escape")                  # close the OS list, keep focus + current value
    time.sleep(0.3)
    arrow = "ArrowUp" if direction == "up" else "ArrowDown"
    for _ in range(n):
        key(arrow)
        time.sleep(0.18)
    time.sleep(0.3)
    shot()


def clear_and_type(x, y, value):
    """Focus a text field, select-all + delete, then type — for overwriting a
    field that already has content (insertText alone only appends)."""
    click(x, y)
    time.sleep(0.2)
    cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA",
                                   "windowsVirtualKeyCode": 65, "modifiers": 2})
    cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA",
                                   "windowsVirtualKeyCode": 65, "modifiers": 2})
    time.sleep(0.15)
    cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Delete", "code": "Delete",
                                   "windowsVirtualKeyCode": 46})
    cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Delete", "code": "Delete",
                                   "windowsVirtualKeyCode": 46})
    time.sleep(0.15)
    cdp("Input.insertText", {"text": value})
    time.sleep(0.3)
    shot()


def fill_text(x, y, value):
    click(x, y)
    time.sleep(0.3)
    cdp("Input.insertText", {"text": value})
    time.sleep(0.4)
    shot()


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    op = sys.argv[1]
    if op == "check":
        try:
            cmd("evaluate", {"code": "1"}); print(json.dumps({"daemon": "up"}))
        except Exception as e:
            print(json.dumps({"daemon": "down", "error": str(e)}))
    elif op == "open":
        open_job(sys.argv[2])
    elif op == "shot":
        print(json.dumps(shot(sys.argv[2] if len(sys.argv) > 2 else None)))
    elif op == "next":
        # primary button (Next/Review) sits bottom-right; CSS ~ (724,446) at first
        # step, agent overrides with exact coords per screenshot when needed.
        x = int(sys.argv[2]) if len(sys.argv) > 2 else 724
        y = int(sys.argv[3]) if len(sys.argv) > 3 else 446
        click(x, y); time.sleep(1.5); shot(); print(json.dumps({"clicked_primary": [x, y]}))
    elif op == "submit":
        x = int(sys.argv[2]) if len(sys.argv) > 2 else 674
        y = int(sys.argv[3]) if len(sys.argv) > 3 else 447
        click(x, y); time.sleep(3); shot(); print(json.dumps({"clicked_submit": [x, y]}))
    elif op == "dropdown":
        answer_dropdown(int(sys.argv[2]), sys.argv[3])
        print(json.dumps({"dropdown_set": {"y": int(sys.argv[2]), "value": sys.argv[3]}}))
    elif op == "steps":                       # steps <y> <up|down> <n>
        dropdown_steps(int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
        print(json.dumps({"stepped": {"y": int(sys.argv[2]), "dir": sys.argv[3], "n": int(sys.argv[4])}}))
    elif op == "text":
        fill_text(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
        print(json.dumps({"text_set": sys.argv[4]}))
    elif op == "retext":                      # retext <x> <y> "value"  (clear + type)
        clear_and_type(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
        print(json.dumps({"retext_set": sys.argv[4]}))
    elif op == "scroll":
        scroll(int(sys.argv[2]) if len(sys.argv) > 2 else 600); print(json.dumps({"scrolled": True}))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
