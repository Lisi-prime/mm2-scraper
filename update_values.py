import os
import sys
import re
import json
import time
import base64
import urllib.request
import urllib.error

# Headers to emulate browser request
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CATEGORIES = [
    "godlies",
    "ancients",
    "vintages",
    "chromas",
    "uniques",
    "legendaries",
    "rares",
    "uncommons",
    "commons",
    "pets"
]

FALLBACK_CORE_VALUES = {
    "Harvester": 3300,
    "Corrupt": 2750,
    "Icepiercer": 2900,
    "Bat": 2400,
    "Gingerscythe": 1600,
    "Darksword": 1500,
    "Darkshot": 1500,
    "Ocean": 900,
    "Waves": 850,
    "Candleflame": 240,
    "ElderwoodBlade": 280,
    "Elderwood Blade": 280,
    "Elderwood Revolver": 85,
    "Elderwood Scythe": 90,
    "Chroma Candleflame": 550,
    "CandleflameChroma": 550,
    "Chroma Swirly Gun": 1100,
    "Chroma Elderwood Blade": 1250,
    "Chroma Cookiecane": 750,
    "Chroma Lightbringer": 75,
    "Chroma Darkbringer": 75,
    "Chroma Luger": 65,
    "Chroma Gemstone": 45,
    "Chroma Fang": 32,
    "Chroma Heat": 40,
    "Chroma Tides": 35,
    "Chroma Saw": 25,
    "Chroma Seer": 25,
    "Chroma Deathshard": 30,
    "Chroma Laser": 40,
    "Chroma Slasher": 35,
    "Chroma Shark": 40,
    "Nikilis Scythe": 150000,
    "Chroma Gingerblade": 45,
    "Chroma Boneblade": 30,
    "Sugar": 135,
    "Candy": 145,
    "Red Luger": 60,
    "Green Luger": 55,
    "Luger": 70,
    "Nightblade": 35,
    "Hallowgun": 55,
    "Hallowscythe": 75,
    "BattleAxe": 25,
    "BattleAxe2": 45,
    "BattleAxe II": 45,
    "Boneblade": 15,
    "Ghostblade": 12,
    "Pumpking": 30,
    "Vampires Edge": 15,
    "Xmas": 35,
    "Icebreaker": 125,
    "Iceblaster": 115,
    "Ginger Luger": 40,
    "Gingerblade": 25,
    "Jinglegun": 35,
    "Minty": 35,
    "Frostbite": 15,
    "Frostsaber": 15,
    "Ice Dragon": 15,
    "Ice Shard": 15,
    "Snowflake": 12,
    "Winters Edge": 12,
    "Chill": 25,
    "Eternal": 10,
    "Eternal II": 10,
    "Eternal III": 12,
    "Eternal IV": 15,
    "Fang": 20,
    "Flames": 12,
    "Heat": 25,
    "Laser": 10,
    "Phoenix": 10,
    "Pixel": 40,
    "Saw": 8,
    "Shark": 25,
    "Slasher": 25,
    "Spider": 20,
    "Tides": 25,
    "Amerilaser": 35,
    "Old Glory": 35,
    "Clockwork": 30,
    "Deathshard": 20,
    "Gemstone": 20,
    "Lightbringer": 50,
    "Darkbringer": 50,
    "Nebula": 45,
    "Plasma": 40,
    "Heartblade": 60,
    "Swirly Gun": 450,
    "Swirly Blade": 350,
    "Swirly Axe": 220,
    "Cookiecane": 175,
    "Gingermint": 85,
    "Flora": 80,
    "Watergun": 240,
    "Pearl": 140,
    "Pearlshine": 135,
    "America": 20,
    "Blood": 15,
    "Cowboy": 10,
    "Ghost": 10,
    "Golden": 10,
    "LaserVintage": 10,
    "Phaser": 10,
    "Prince": 10,
    "Shadow": 10,
    "Splitter": 10
}

def clean_item_name(name):
    clean = re.sub(r"[^\w\s-]", "", name).strip()
    return clean

def scrape_category(category):
    url = f"https://supremevaluelist.com/mm2/{category}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
            # Parse item name and value from Supreme Values HTML structure:
            # data-name='ItemName' ... Value - <b class="itemvalue ...">1,234</b>
            pattern = re.compile(
                r"data-name=['\"]([^'\"]+)['\"].*?Value\s*-\s*<b class=['\"]itemvalue[^'\"]*['\"]>([0-9,]+)</b>",
                re.DOTALL
            )
            matches = pattern.findall(html)
            results = {}
            for name, val_str in matches:
                name_clean = clean_item_name(name)
                val = int(val_str.replace(",", ""))
                if name_clean and val > 0:
                    results[name_clean] = val
                    # Add alternative naming variants
                    if "Chroma " in name_clean:
                        suffix = name_clean.replace("Chroma ", "") + "Chroma"
                        results[suffix] = val
                    if name_clean == "Battle Axe II":
                        results["BattleAxe2"] = val
                        results["BattleAxe II"] = val
                    if name_clean == "Elderwood Blade":
                        results["ElderwoodBlade"] = val
                    if name_clean == "Elderwood Revolver":
                        results["ElderwoodRevolver"] = val
                    if name_clean == "Elderwood Scythe":
                        results["ElderwoodScythe"] = val
            return results
    except Exception as e:
        print(f"[Scraper] Failed to fetch {category}: {e}")
        return {}

def load_previous_values(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "values" in data and isinstance(data["values"], dict):
                return data["values"]
            if isinstance(data, dict):
                return {k: v for k, v in data.items() if isinstance(v, (int, float))}
    except Exception:
        pass
    return {}

def update_remote_github(token, repo, file_path, content_bytes, branch="main"):
    """
    Updates or creates values.json in the destination repository (Link 2)
    using the official GitHub REST API without requiring git checkout.
    """
    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "MM2-Value-Scraper",
    }
    
    # Check if file exists to obtain current sha
    sha = None
    try:
        check_req = urllib.request.Request(f"{api_url}?ref={branch}", headers=headers)
        with urllib.request.urlopen(check_req) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            sha = info.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[GitHub API] Warning checking sha: {e}")
    except Exception as e:
        print(f"[GitHub API] Check error: {e}")

    payload = {
        "message": f"Auto-update Supreme Values ({time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())})",
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": branch
    }
    if sha:
        payload["sha"] = sha

    data_json = json.dumps(payload).encode("utf-8")
    put_req = urllib.request.Request(api_url, data=data_json, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(put_req) as resp:
            if resp.status in (200, 201):
                print(f"[GitHub API] Successfully pushed values.json to {repo} (HTTP {resp.status})")
                return True
    except Exception as e:
        print(f"[GitHub API] Error pushing to {repo}: {e}")
    return False

def update_skins_json_values(skins_json_path, prices_dict):
    """
    Safely injects or updates 'Value' inside rec.meta for each skin in skins.json,
    leaving 100% of display, meshes, textures, particles, sounds, and grips intact!
    """
    if not os.path.exists(skins_json_path):
        return False
    try:
        with open(skins_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        entries = data.get("entries", {})
        updated_count = 0
        is_dict = isinstance(entries, dict)
        iterable = entries.values() if is_dict else entries

        def norm(s):
            if not s: return ""
            return re.sub(r"[^a-zA-Z0-9]", "", str(s)).lower()

        norm_prices = {norm(k): v for k, v in prices_dict.items()}

        for rec in iterable:
            if not isinstance(rec, dict):
                continue
            name = rec.get("name")
            meta = rec.get("meta") or {}
            item_name = meta.get("ItemName")
            
            # Find price from prices_dict directly or normalized
            price = prices_dict.get(item_name) or prices_dict.get(name)
            if price is None:
                n1 = norm(item_name)
                n2 = norm(name)
                price = norm_prices.get(n1) or norm_prices.get(n2)
            
            if price is not None:
                meta["Value"] = int(price)
            elif "Value" not in meta:
                meta["Value"] = 1
                
            rec["meta"] = meta
            updated_count += 1
                
        with open(skins_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Values System] Injected updated values into {updated_count} skins in skins.json (all meshes/sounds preserved).")
        return True
    except Exception as e:
        print(f"[Values System] Warning updating skins.json: {e}")
        return False

def main():
    print("[Values System] Starting Supreme Values update cycle...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, "values.json")
    skins_path = os.path.join(base_dir, "skins.json")
    
    # 1. Base values from previous file and built-in fallbacks
    combined = dict(FALLBACK_CORE_VALUES)
    prev = load_previous_values(output_path)
    combined.update(prev)

    # 2. Live scrape from Supreme Values
    scraped_total = 0
    for cat in CATEGORIES:
        items = scrape_category(cat)
        scraped_total += len(items)
        combined.update(items)
        time.sleep(0.5)

    print(f"[Values System] Scraped {scraped_total} items from Supreme. Total catalog: {len(combined)} items.")

    # 3. Assemble JSON payload (both nested and flat formats for maximum compatibility)
    payload = {
        "updated_at": int(time.time()),
        "updated_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "source": "Supreme Values",
        "count": len(combined),
        "values": combined
    }
    # Add flat keys as well
    for k, v in combined.items():
        payload[k] = v

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    # 4. Save local values.json
    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"[Values System] Saved local file: {output_path}")

    # 5. Inject prices into skins.json (preserving meshes, textures, sounds, and effects)
    if os.path.exists(skins_path):
        update_skins_json_values(skins_path, combined)

    # 6. Remote push to Link 2 (if DEST_REPO and DEST_TOKEN are configured)
    dest_repo = os.environ.get("DEST_REPO")
    dest_token = os.environ.get("DEST_TOKEN") or os.environ.get("GITHUB_TOKEN")
    dest_branch = os.environ.get("DEST_BRANCH", "main")
    dest_file = os.environ.get("DEST_FILE", "values.json")

    if dest_repo and dest_token:
        print(f"[Values System] Pushing to remote storage repo: {dest_repo} ...")
        update_remote_github(dest_token, dest_repo, dest_file, json_bytes, dest_branch)
        if os.path.exists(skins_path):
            with open(skins_path, "rb") as sf:
                skins_bytes = sf.read()
            update_remote_github(dest_token, dest_repo, "skins.json", skins_bytes, dest_branch)
    else:
        print("[Values System] Notice: DEST_REPO or DEST_TOKEN not provided in env. Local values.json updated successfully.")

if __name__ == "__main__":
    main()
