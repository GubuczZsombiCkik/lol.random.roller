"""Letölti az op.gg-ről lane-enként a 10 legalacsonyabb winrate-ű championt -> data.json"""
import json, re, datetime
from playwright.sync_api import sync_playwright

LANES = {"Top": "top", "Jungle": "jungle", "Mid": "mid", "Bot": "adc", "Support": "support"}
PCT = re.compile(r"^(\d{2}(?:\.\d+)?)\s*%$")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def scrape(page, pos):
    url = f"https://op.gg/lol/champions?position={pos}&region=global"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)  # várunk, hogy a lista betöltsön
    print(f"--- {pos}: cím = {page.title()!r}, url = {page.url}")
    rows = page.eval_on_selector_all(
        "tr",
        "rs => rs.map(r => [...r.querySelectorAll('td')].map(td => td.innerText.trim()))")
    rows = [r for r in rows if r]
    print(f"    talált sorok: {len(rows)}")
    if not rows:
        body = page.inner_text("body")
        print("    OLDAL SZÖVEGE (eleje):", body[:600].replace("\n", " | "))
        return []
    print("    első sor:", rows[0])
    out = []
    for cells in rows:
        name = next((c for c in cells if len(re.findall(r"[A-Za-z]", c)) >= 2), None)
        wr = next((PCT.match(c).group(1) for c in cells if PCT.match(c)), None)
        if name and wr:
            out.append({"n": name.split("\n")[0].strip(), "w": wr})
    out.sort(key=lambda x: float(x["w"]))
    return out[:10]

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    lanes = {}
    for lane, pos in LANES.items():
        lanes[lane] = scrape(page, pos)
        print(lane, lanes[lane])
    browser.close()

if all(lanes.values()):
    json.dump({"date": datetime.date.today().isoformat(), "lanes": lanes},
              open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
else:
    raise SystemExit("Hiba: valamelyik lane üres, nem írom felül a data.json-t")
