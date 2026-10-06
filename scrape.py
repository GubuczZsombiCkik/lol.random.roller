"""Letölti az op.gg-ről lane-enként a 10 legalacsonyabb winrate-ű championt -> data.json"""
import json, re, datetime
from playwright.sync_api import sync_playwright

LANES = {"Top": "top", "Jungle": "jungle", "Mid": "mid", "Bot": "adc", "Support": "support"}
PCT = re.compile(r"^(\d{2}(?:\.\d+)?)%$")

def scrape(page, pos):
    page.goto(f"https://op.gg/lol/champions?position={pos}", wait_until="networkidle")
    page.wait_for_selector("table tbody tr", timeout=30000)
    rows = page.eval_on_selector_all(
        "table tbody tr",
        "rs => rs.map(r => [...r.querySelectorAll('td')].map(td => td.innerText.trim()))")
    out = []
    for cells in rows:
        name = next((c for c in cells if len(re.findall(r"[A-Za-z]", c)) >= 2), None)
        wr = next((PCT.match(c).group(1) for c in cells if PCT.match(c)), None)  # első % = win rate
        if name and wr:
            out.append({"n": name.split("\n")[0].strip(), "w": wr})
    out.sort(key=lambda x: float(x["w"]))
    return out[:10]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
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
