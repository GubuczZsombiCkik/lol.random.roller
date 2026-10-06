"""op.gg -> profile.json (rang, winrate, utolsó 10 meccs) + data.json (a SAJÁT rangodnak megfelelő napi legrosszabb champek)"""
import json, re, datetime, os
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# ---- A TE PROFILOD ----
REGION = "eune"        # eune / euw
NAME = "HIPLETSLAYER"
TAG = "OOOO"           # ha nullák (0000), írd át
TIER_OVERRIDE = ""     # kézi rang-szűrő, pl. "emerald_plus"; üresen = a rangodból számolja
# -----------------------
MODE = os.environ.get("MODE", "all")   # "profile" = csak a profil (gyakori futás)
LANES = {"Top": "top", "Jungle": "jungle", "Mid": "mid", "Bot": "adc", "Support": "support"}
TIERMAP = {"iron": "ibsg", "bronze": "ibsg", "silver": "ibsg", "gold": "gold_plus", "platinum": "platinum_plus",
           "emerald": "emerald_plus", "diamond": "diamond_plus", "master": "master_plus",
           "grandmaster": "grandmaster_plus", "challenger": "challenger"}
TIERS = "Iron|Bronze|Silver|Gold|Platinum|Emerald|Diamond|Master|Grandmaster|Challenger"
PCT = re.compile(r"^(\d{2}(?:\.\d+)?)\s*%$")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
JS_BLOCK = r"""()=>{
 const els=[...document.querySelectorAll('*')].filter(e=>e.children.length===0&&/Ranked Solo/i.test(e.textContent));
 for(const e of els){let n=e;for(let i=0;i<7&&n;i++){n=n.parentElement;
  if(n&&/\bLP\b|Unranked/i.test(n.innerText)&&n.innerText.length<700)return n.innerText}}
 return ''}"""

def from_next(page):
    """op.gg beágyazott (__NEXT_DATA__) adata: ez a legmegbízhatóbb forrás a rangra"""
    try:
        raw = page.evaluate("()=>{const e=document.getElementById('__NEXT_DATA__');return e?e.textContent:''}")
        data = json.loads(raw) if raw else None
    except Exception:
        data = None
    if not data:
        print("    __NEXT_DATA__ nem található")
        return None
    found = []
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("tier_info"), dict):
                found.append(o)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(data)
    print(f"    __NEXT_DATA__: {len(found)} rang-bejegyzés")
    for o in found:
        if "SOLO" in json.dumps(o.get("queue_info", ""), ensure_ascii=False).upper():
            print("    Solo bejegyzés:", json.dumps(o, ensure_ascii=False)[:400])
            return o
    return None

def scrape_profile(page):
    page.goto(f"https://op.gg/lol/summoners/{REGION}/{quote(NAME)}-{TAG}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(6000)
    try:  # op.gg "Update" gomb: friss adat a Riot szerveréről
        page.get_by_role("button", name=re.compile(r"^\s*Update", re.I)).first.click(timeout=4000)
        page.wait_for_timeout(7000)
        print("    Update gomb megnyomva")
    except Exception:
        print("    Update gomb nem található / nem kattintható")
    body = page.inner_text("body")
    print(f"--- profil: cím = {page.title()!r}")
    res = re.findall(r"\b(Victory|Defeat|Remake)\b", body)[:10]
    if not res:
        print("    OLDAL SZÖVEGE:", body[:600].replace("\n", " | "))
        return None
    blk = page.evaluate(JS_BLOCK)
    if not blk:
        m = re.search(r"Ranked\s*Solo\s*/?\s*Duo(.{0,300})", body, re.S | re.I)
        blk = m.group(1) if m else ""
    print("    Solo/Duo blokk:", blk.replace("\n", " | ")[:700] or "(nem találtam)")
    lpm = re.search(r"(\d+)\s*LP", blk)
    rank = re.search(rf"\b({TIERS})\b\s*([1-4])?\s*{lpm.group(1)}\s*LP", blk, re.I | re.S) if lpm else None
    if not rank and lpm:  # utolsó rangnév az LP előtt
        pre = list(re.finditer(rf"\b({TIERS})\b\s*([1-4])?", blk[:lpm.start()], re.I))
        rank = pre[-1] if pre else None
    unr = re.search(r"Unranked", blk, re.I)
    lp = re.search(r"(\d+)\s*LP", blk)
    rec = re.search(r"(\d+)\s*W\s*(\d+)\s*L", blk)
    wr = re.search(r"Win rate\s*(\d{1,3})\s*%", blk, re.I)
    r = ""
    if rank and not unr:
        r = rank.group(1).capitalize() + (" " + rank.group(2) if rank.group(2) else "")
    elif unr:
        r = "Unranked"
    prof = {"name": f"{NAME}#{TAG}", "region": REGION.upper(),
            "last10": [{"Victory": "W", "Defeat": "L", "Remake": "R"}[x] for x in res],
            "record": f"{rec.group(1)}W {rec.group(2)}L" if rec else "",
            "winrate": wr.group(1) if wr else (str(round(100 * int(rec.group(1)) / (int(rec.group(1)) + int(rec.group(2))))) if rec else ""),
            "rank": r, "lp": lp.group(1) if lp else "", "date": datetime.date.today().isoformat(),
            "updated": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    nd = from_next(page)
    if nd:
        ti = nd["tier_info"]
        t = (ti.get("tier") or "").capitalize()
        dv = ti.get("division")
        prof["rank"] = (t + (f" {dv}" if dv and t not in ("Master", "Grandmaster", "Challenger") else "")) if t else "Unranked"
        prof["lp"] = str(ti.get("lp", "")) if t else ""
        w, l = nd.get("win"), nd.get("lose")
        if isinstance(w, int) and isinstance(l, int) and w + l:
            prof["record"] = f"{w}W {l}L"
            prof["winrate"] = str(round(100 * w / (w + l)))
    else:
        for m in list(re.finditer(r"Challenger", body))[:3]:
            print("    'Challenger' környezete:", body[max(0, m.start() - 80):m.end() + 80].replace("\n", " | "))
    print("    profil:", prof)
    return prof

def scrape(page, pos, tier):
    url = f"https://op.gg/lol/champions?position={pos}&region=global" + (f"&tier={tier}" if tier else "")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(8000)
    rows = [r for r in page.eval_on_selector_all(
        "tr", "rs => rs.map(r => [...r.querySelectorAll('td')].map(td => td.innerText.trim()))") if r]
    print(f"--- {pos} (tier={tier or 'alap'}): {len(rows)} sor")
    out = []
    for cells in rows:
        name = next((c for c in cells if len(re.findall(r"[A-Za-z]", c)) >= 2), None)
        wr = next((PCT.match(c).group(1) for c in cells if PCT.match(c)), None)
        if name and wr:
            out.append({"n": name.split("\n")[0].strip(), "w": wr})
    out.sort(key=lambda x: float(x["w"]))
    if not out and tier:
        print("    nincs adat ezzel a szűrővel, próbálom az alapértelmezettel")
        return scrape(page, pos, "")
    return out[:10], tier

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1400, "height": 900}).new_page()
    try:
        profile = scrape_profile(page)
    except Exception as e:
        print("Profil hiba:", e); profile = None
    if MODE == "profile":
        browser.close()
        if profile:
            json.dump(profile, open("profile.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            raise SystemExit(0)
        raise SystemExit("Profil hiba")
    tier = TIER_OVERRIDE or (TIERMAP.get(profile["rank"].split()[0].lower(), "") if profile and profile["rank"] else "")
    print("Használt rang-szűrő:", tier or "alapértelmezett")
    lanes, used = {}, ""
    for lane, pos in LANES.items():
        lanes[lane], used = scrape(page, pos, tier)
        print(lane, lanes[lane])
    browser.close()

if profile:
    json.dump(profile, open("profile.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if all(lanes.values()):
    json.dump({"date": datetime.date.today().isoformat(), "tier": used, "lanes": lanes},
              open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
else:
    raise SystemExit("Hiba: valamelyik lane üres, nem írom felül a data.json-t")
