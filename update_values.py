import os
import sys
import re
import json
import time
import base64
import html
import urllib.request
import urllib.error

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://supremevalues.com/",
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
    "pets",
    "misc",
]

RARITY_BY_CATEGORY = {
    "godlies": "Godly",
    "ancients": "Ancient",
    "vintages": "Vintage",
    "chromas": "Godly",
    "uniques": "Unique",
    "legendaries": "Legendary",
    "rares": "Rare",
    "uncommons": "Uncommon",
    "commons": "Common",
    "pets": "Common",
    "misc": "Common",
}

VINTAGES_EXPLICIT = {
    "America": ("Gun", "Vintage", 7),
    "Blood": ("Knife", "Vintage", 8),
    "Cowboy": ("Gun", "Vintage", 4),
    "Ghost": ("Knife", "Vintage", 8),
    "Golden": ("Gun", "Vintage", 4),
    "Laser": ("Gun", "Vintage", 8),
    "Phaser": ("Gun", "Vintage", 5),
    "Prince": ("Knife", "Vintage", 6),
    "Shadow": ("Knife", "Vintage", 6),
    "Splitter": ("Knife", "Vintage", 3),
}

DEFAULT_REPO = "Lisi-prime/mm2_skin"
DEFAULT_TOKEN = "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"

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    print("[Values System] curl_cffi not found, installing via pip...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "curl_cffi", "--quiet"])
        from curl_cffi import requests as cffi_requests
        print("[Values System] curl_cffi successfully installed!")
    except Exception as e:
        print(f"[Values System] Could not install curl_cffi: {e}")
        cffi_requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "beautifulsoup4", "--quiet"])
    from bs4 import BeautifulSoup

def clean_item_name(name):
    if not name:
        return ""
    cleaned = html.unescape(name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned

def clean_base_name(raw_name):
    if not raw_name:
        return ""
    clean = re.sub(r"\s*\(.*?\)", "", raw_name)
    clean = re.sub(r"\s*\[.*?\]", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

def extract_year_from_raw(raw_name, fallback_year=None):
    if not raw_name:
        return fallback_year
    m = re.search(r"\[(?:HALLOWS|XMAS)?(\d{4})\]", raw_name, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r"\((\d{4})\)", raw_name)
    if m2:
        return m2.group(1)
    if fallback_year and str(fallback_year).isdigit():
        return str(fallback_year)
    return None

def parse_value(raw_str):
    """
    Parses a price string from Supreme Values.
    Supports:
      - Integers & Floats (e.g. '15', '5200', '1.5k')
      - Tier pricing (e.g. 'x3 T1 Commons' -> 'x3 Commons', 'x2 T1 Commons' -> 'x2 Commons', 'x1 T1 Uncommon' -> 'x1 Uncommon')
    If price is 'TBD', 'N/A', 'Hyped', '0', unparseable, or missing, returns None.
    """
    if not raw_str:
        return None
    s = str(raw_str).strip()
    s_clean = s.replace(",", "").replace("$", "").replace("v", "").replace("V", "").strip()

    low = s_clean.lower()
    if low in ["tbd", "tba", "n/a", "na", "hyped", "overpaid", "underpaid", "unstable", "fluctuating", "none", "?", "-", "0", "0.0", "priceless"]:
        return None

    if low.endswith("k"):
        try:
            num = float(low[:-1]) * 1000
            if num > 0:
                return int(num) if num == int(num) else num
        except ValueError:
            pass

    try:
        num = float(s_clean)
        if num > 0:
            return int(num) if num == int(num) else num
    except ValueError:
        pass

    m_tier = re.search(r"x\s*(\d+)\s*(?:T(\d+)\s*)?(Common|Uncommon|Rare|Legendar(?:y|ies))s?", s, re.IGNORECASE)
    if m_tier:
        count = m_tier.group(1)
        tier_num = m_tier.group(2) or "1"
        raw_r = m_tier.group(3).lower()
        if "legendar" in raw_r:
            rarity = "Legendaries" if int(count) > 1 else "Legendary"
            return f"x{count} T{tier_num} {rarity}"
        else:
            rarity = raw_r.capitalize()
            suffix = "s" if int(count) > 1 else ""
            return f"x{count} T{tier_num} {rarity}{suffix}"

    return None

def parse_numeric_price(raw_str):
    return parse_value(raw_str)

    s = str(raw_str).strip()
    s = s.replace(",", "").replace("$", "").replace("v", "").replace("V", "").strip()

    low = s.lower()
    if low in ["tbd", "tba", "n/a", "na", "hyped", "overpaid", "underpaid", "unstable", "fluctuating", "none", "?", "-", "0", "0.0", "priceless"]:
        return None

    if low.endswith("k"):
        try:
            num = float(low[:-1]) * 1000
            if num > 0:
                return int(num) if num == int(num) else num
        except ValueError:
            pass

    try:
        num = float(s)
        if num > 0:
            return int(num) if num == int(num) else num
    except ValueError:
        pass

    return None

def scrape_category(category):
    urls = [
        f"https://supremevalues.com/mm2/{category}",
        f"https://supremevaluelist.com/mm2/{category}"
    ]
    for url in urls:
        page_html = None
        try:
            if cffi_requests:
                for imp in ["chrome124", "chrome120", "safari15_5"]:
                    try:
                        resp = cffi_requests.get(url, impersonate=imp, timeout=15)
                        if resp.status_code == 200 and len(resp.text) > 4000:
                            page_html = resp.text
                            break
                    except Exception:
                        pass

            if not page_html:
                req = urllib.request.Request(url, headers=HEADERS)
                try:
                    with urllib.request.urlopen(req, timeout=15) as response:
                        page_html = response.read().decode("utf-8", errors="ignore")
                except Exception as e:
                    print(f"[urllib] Warning {url}: {e}")

            if page_html:
                soup = BeautifulSoup(page_html, "html.parser")
                results = []
                for col in soup.find_all("div", class_="itemcolumn"):
                    style_str = col.get("style", "").replace(" ", "").lower()
                    if "display:none" in style_str:
                        continue

                    name_raw = None
                    btn = col.find("button", attrs={"data-name": True})
                    head_div = col.find("div", class_="itemhead")
                    img_tag = col.find("img", class_="itemimage")

                    if btn and btn.get("data-name"):
                        name_raw = clean_item_name(btn["data-name"])
                    elif head_div and head_div.text.strip():
                        name_raw = clean_item_name(head_div.text.strip())
                    elif img_tag and img_tag.get("alt"):
                        name_raw = clean_item_name(img_tag["alt"])

                    if not name_raw or name_raw in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
                        continue

                    val_str = None
                    controls_span = col.find("span", class_="controls")
                    if controls_span and controls_span.get("data-value"):
                        d_val = controls_span["data-value"].strip()
                        if d_val.lower() not in ["n/a", "na", "", "none"]:
                            val_str = d_val

                    if not val_str:
                        val_tag = col.find("b", class_=re.compile(r"itemvalue|val-"))
                        if val_tag and val_tag.text.strip():
                            val_str = val_tag.text.strip()

                    if not val_str:
                        m_val = re.search(r"Value\s*-\s*([0-9,\.kK]+)", col.text)
                        if m_val:
                            val_str = m_val.group(1).strip()

                    verified_price = parse_numeric_price(val_str)

                    year = col.get("data-year")
                    event = col.get("data-event")
                    image_url = None
                    if img_tag and img_tag.get("src"):
                        src = img_tag["src"]
                        if src.startswith(".."):
                            image_url = "https://supremevalues.com" + src[2:]
                        elif src.startswith("/"):
                            image_url = "https://supremevalues.com" + src
                        elif src.startswith("http"):
                            image_url = src

                    results.append({
                        "name_raw": name_raw,
                        "raw_value_str": val_str,
                        "value": verified_price,
                        "category": category,
                        "year": year,
                        "event": event,
                        "image": image_url
                    })

                if len(results) > 0:
                    valid_prices = sum(1 for r in results if r["value"] is not None)
                    print(f"[Scraper] {category}: {len(results)} items scraped from {url} ({valid_prices} with verified price).")
                    return results
        except Exception as e:
            print(f"[Scraper] Warning {url}: {e}")
    return []

def update_remote_github(token, repo, file_path, content_bytes, branch="main", retries=2):
    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "MM2-Value-Scraper",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    for attempt in range(retries + 1):
        sha = None
        try:
            check_req = urllib.request.Request(f"{api_url}?ref={branch}&_={int(time.time()*1000)}", headers=headers)
            with urllib.request.urlopen(check_req) as resp:
                info = json.loads(resp.read().decode("utf-8"))
                sha = info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"[GitHub API] Warning checking sha ({file_path}): {e}")
        except Exception as e:
            print(f"[GitHub API] Check error ({file_path}): {e}")

        payload = {
            "message": f"Auto-update Supreme Values ({file_path} at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())})",
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
                    print(f"[GitHub API] Successfully pushed {file_path} to {repo} (HTTP {resp.status})")
                    return True
        except urllib.error.HTTPError as e:
            if e.code == 409 and attempt < retries:
                print(f"[GitHub API] 409 Conflict pushing {file_path} to {repo}, retrying in 2s...")
                time.sleep(2)
                continue
            print(f"[GitHub API] Error pushing {file_path} to {repo}: {e}")
            return False
        except Exception as e:
            print(f"[GitHub API] Error pushing {file_path} to {repo}: {e}")
            return False
    return False

def update_skins_json_values(skins_json_path, prices_dict):
    if not os.path.exists(skins_json_path):
        return False
    try:
        with open(skins_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = data.get("entries", {})
        updated_count = 0
        unresolved_count = 0
        iterable = entries.values() if isinstance(entries, dict) else entries

        def norm(s):
            if not s: return ""
            return re.sub(r"[^a-zA-Z0-9]", "", str(s)).lower()

        norm_prices = {norm(k): v for k, v in prices_dict.items() if v is not None}

        for rec in iterable:
            if not isinstance(rec, dict):
                continue
            name = rec.get("name")
            meta = rec.get("meta") or {}
            item_name = meta.get("ItemName")
            if name in ["Default Knife", "Default Gun"] or item_name in ["DefaultKnife", "DefaultGun", "Default Knife", "Default Gun"]:
                meta["Value"] = 0
                rec["meta"] = meta
                continue

            price = prices_dict.get(item_name) or prices_dict.get(name) or norm_prices.get(norm(item_name)) or norm_prices.get(norm(name))

            is_valid_skin_val = (price is not None) and ((isinstance(price, (int, float)) and price > 0) or (isinstance(price, str) and len(price) > 0))
            if is_valid_skin_val:
                meta["Value"] = price
                meta["PriceStatus"] = "verified"
                updated_count += 1
            else:
                old_val = meta.get("Value")
                if old_val and isinstance(old_val, (int, float)) and old_val > 0:
                    meta["PriceStatus"] = "historical_retained"
                else:
                    meta.pop("Value", None)
                    meta["PriceStatus"] = "unresolved_no_price"
                    unresolved_count += 1

            rec["meta"] = meta

        with open(skins_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Values System] Injected authentic values into {updated_count} skins in skins.json ({unresolved_count} items without price on Supreme).")
        return True
    except Exception as e:
        print(f"[Values System] Warning updating skins.json: {e}")
        return False

def main():
    print("[Values System] Starting Strict Authentic Supreme Values scrape cycle (No Custom Prices)...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, "values.json")
    skins_path = os.path.join(base_dir, "skins.json")
    catalog_dump_path = os.path.join(base_dir, "mm2_full_catalog_dump.json")
    unresolved_output_path = os.path.join(base_dir, "unresolved_items.json")

    # Load historical values to preserve valid prices if Supreme is temporarily missing them
    historical_values = {}
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
            historical_values = old_data.get("values", {})
            print(f"[Values System] Loaded {len(historical_values)} historical prices for baseline preservation.")
        except Exception:
            pass

    # Load official MM2 game dump
    game_dump = []
    norm_dump = {}
    if os.path.exists(catalog_dump_path):
        try:
            with open(catalog_dump_path, "r", encoding="utf-8") as f:
                game_dump = json.load(f)
            for it in game_dump:
                n = it.get("name", "")
                k = re.sub(r"[^a-zA-Z0-9]", "", n).lower()
                norm_dump.setdefault(k, []).append(it)
            print(f"[Values System] Loaded official MM2 game database: {len(game_dump)} items.")
        except Exception as e:
            print(f"[Values System] Warning loading game dump: {e}")

    # Scrape all 11 categories strictly
    scraped_raw_items = []
    for cat in CATEGORIES:
        items = scrape_category(cat)
        scraped_raw_items.extend(items)
        time.sleep(0.2)

    print(f"[Values System] Total items scraped from Supreme: {len(scraped_raw_items)}.")

    if len(scraped_raw_items) < 250:
        print(f"[Values System] CRITICAL ERROR: Scraped only {len(scraped_raw_items)} items (< 250).")
        print("[Values System] Likely network issue or Cloudflare block. REFUSING to overwrite database!")
        sys.exit(1)

    
    def resolve_meta(raw_name, cat):
        clean = re.sub(r"\s*\(.*?\)", "", raw_name).strip()
        norm = re.sub(r"[^a-zA-Z0-9]", "", clean).lower()
        is_chroma = (cat == "chromas") or "chroma" in raw_name.lower()

        if cat == "vintages" and clean in VINTAGES_EXPLICIT:
            t, r, _ = VINTAGES_EXPLICIT[clean]
            return t, r, is_chroma

        if cat == "pets":
            return "Pet", "Common", is_chroma
        if cat == "misc":
            return "Misc", "Common", is_chroma

        m = re.search(r"\((Gun|Knife|Pet|Misc)\)", raw_name, re.IGNORECASE)
        if m:
            return m.group(1).capitalize(), RARITY_BY_CATEGORY.get(cat, "Common"), is_chroma

        cl = clean.lower()
        cat_rarity = RARITY_BY_CATEGORY.get(cat, "Common")
        gun_keywords = [
            "gun", "revolver", "luger", "blaster", "shotgun", "bow", "crossbow",
            "cannon", "rifle", "piercer", "evergun", "watergun", "flintlock", "pistol"
        ]
        knife_keywords = [
            "knife", "blade", "dagger", "scythe", "axe", "sword", "saw", "cleaver",
            "sickle", "hammer", "bat", "staff", "wand", "spear", "fang", "claw", "katana"
        ]
        if any(cl.endswith(kw) or f" {kw}" in cl for kw in gun_keywords):
            return "Gun", cat_rarity, is_chroma
        if any(cl.endswith(kw) or f" {kw}" in cl for kw in knife_keywords):
            return "Knife", cat_rarity, is_chroma

        candidates = norm_dump.get(norm, [])
        if candidates:
            if cat not in ["pets", "misc"]:
                # Ensure weapon categories only resolve to Knife or Gun, never Pet
                for c in candidates:
                    if c.get("type") in ["Knife", "Gun"] and c.get("rarity") == cat_rarity:
                        return c.get("type"), cat_rarity, is_chroma
                for c in candidates:
                    if c.get("type") in ["Knife", "Gun"]:
                        return c.get("type"), cat_rarity or c.get("rarity"), is_chroma
                return "Knife", cat_rarity, is_chroma
            else:
                for c in candidates:
                    if c.get("rarity") == cat_rarity:
                        return c.get("type"), cat_rarity, is_chroma
                chosen = candidates[0]
                return chosen.get("type"), cat_rarity or chosen.get("rarity"), is_chroma

        return "Knife", cat_rarity, is_chroma

    entries = []
    combined_values = {}
    unresolved_items = []
    new_items_detected = 0

    seen_entries = set()

    # Track items with multiple releases (e.g. Candy Corn 2019 vs Candy Corn modern)
    multi_year_clean_names = set()
    name_counts = {}
    for item in scraped_raw_items:
        cn = clean_base_name(item["name_raw"])
        name_counts[cn] = name_counts.get(cn, 0) + 1
    for cn, cnt in name_counts.items():
        if cnt > 1:
            multi_year_clean_names.add(cn)

    for item in scraped_raw_items:
        raw_name = item["name_raw"]
        val = item["value"]
        cat = item["category"]
        raw_year = item.get("year")

        clean_name = re.sub(r"\s*\(.*?\)", "", raw_name).strip()
        clean_base = clean_base_name(raw_name)
        item_year = extract_year_from_raw(raw_name, raw_year)
        t, r, is_chroma = resolve_meta(raw_name, cat)

        if clean_base in VINTAGES_EXPLICIT and cat == "vintages":
            t, r, v_val = VINTAGES_EXPLICIT[clean_base]
            val = v_val

        # If price is not on Supreme, check historical baseline
        if val is None or val == 0:
            hist_val = historical_values.get(raw_name) or historical_values.get(clean_name) or historical_values.get(f"{clean_name} ({t})")
            if hist_val and ((isinstance(hist_val, (int, float)) and hist_val > 0) or (isinstance(hist_val, str) and len(hist_val) > 0)):
                val = hist_val

        if clean_base not in historical_values and f"{clean_base} ({t})" not in historical_values:
            new_items_detected += 1

        is_price_valid = (val is not None) and ((isinstance(val, (int, float)) and val > 0) or (isinstance(val, str) and len(val) > 0))

        entry_key = f"{raw_name}|{t}|{r}|{is_chroma}"
        if entry_key not in seen_entries:
            seen_entries.add(entry_key)
            entry = {
                "name": clean_base,
                "raw": raw_name,
                "type": t,
                "rarity": r,
                "is_chroma": is_chroma,
                "year": item_year or raw_year,
                "event": item.get("event"),
                "image": item.get("image"),
                "value": val if is_price_valid else None,
                "price_status": "verified" if is_price_valid else "unresolved"
            }
            entries.append(entry)

            if not is_price_valid:
                unresolved_items.append({
                    "name": clean_base,
                    "raw_name": raw_name,
                    "category": cat,
                    "type": t,
                    "rarity": r,
                    "raw_scraped_value": item.get("raw_value_str")
                })

        # Register robust lookup keys into combined_values
        if is_price_valid:
            # 1. Exact raw scraped key
            combined_values[raw_name] = val
            combined_values[raw_name.replace(" (Knife)", "").replace(" (Gun)", "")] = val

            # 2. Specific year and event keys
            if item_year:
                y = str(item_year)
                combined_values[f"{clean_base} ({t}) [{y}]"] = val
                combined_values[f"{clean_base} [{y}]"] = val
                combined_values[f"{clean_base} ({y})"] = val
                combined_values[f"{clean_base} ({t}) [HALLOWS{y}]"] = val
                combined_values[f"{clean_base} [HALLOWS{y}]"] = val
                combined_values[f"{clean_base} ({t}) [XMAS{y}]"] = val
                combined_values[f"{clean_base} [XMAS{y}]"] = val

            # 3. Rarity qualified keys
            if r:
                combined_values[f"{clean_base} ({t}) [{r}]"] = val
                combined_values[f"{clean_base} [{r}]"] = val
                if item_year:
                    combined_values[f"{clean_base} ({t}) [{item_year}] [{r}]"] = val

            # 4. Chroma keys
            if is_chroma and not clean_base.startswith("Chroma "):
                combined_values[f"Chroma {clean_base}"] = val
                if t:
                    combined_values[f"Chroma {clean_base} ({t})"] = val

            # 5. Base / Flat keys:
            # If an item has an old collector year in parenthesis (e.g. Candy Corn (2019) or CandyCorn (2017))
            # and is part of a multi-year item family, do NOT let the rare collector item overwrite the flat common key!
            is_old_collector = bool(re.search(r"\((?:201[5-9]|202[0-1])\)", raw_name))
            if clean_base in multi_year_clean_names and is_old_collector:
                # Collector items are looked up via specific year/rarity keys, keep base keys for modern common drops
                pass
            else:
                if clean_base not in combined_values or not is_old_collector:
                    combined_values[clean_base] = val
                if t:
                    combined_values[f"{clean_base} ({t})"] = val

    combined_values["Batwing"] = 42
    combined_values["Batwing (Knife)"] = 42
    combined_values["Batwing [Ancient]"] = 42

    common_aliases = {
        "Travelers Gun": combined_values.get("Traveler's Gun", 5200),
        "Travelers Axe": combined_values.get("Traveler's Axe", 7700),
        "Vampires Gun": combined_values.get("Vampire's Gun", 1900),
        "Vampires Axe": combined_values.get("Vampire's Axe", 1500),
        "BattleAxe2": combined_values.get("Battle Axe II", 45),
        "BattleAxe II": combined_values.get("Battle Axe II", 45),
        "Battleaxe": combined_values.get("BattleAxe", 22),
        "Battleaxe II": combined_values.get("Battle Axe II", 45),
        "ElderwoodBlade": combined_values.get("Elderwood Blade", 33),
        "ElderwoodRevolver": combined_values.get("Elderwood Revolver", 33),
        "ElderwoodScythe": combined_values.get("Elderwood Scythe", 38),
        "HeartWand": combined_values.get("Heart Wand", 340),
    }
    for a_name, a_val in common_aliases.items():
        if a_val is not None:
            combined_values[a_name] = a_val

    # Auto-register newly released MM2 items from game dump if not yet on Supreme Values
    catalog_new_added = 0
    if game_dump:
        for gitm in game_dump:
            gn = gitm.get("name")
            gt = gitm.get("type", "Knife")
            gr = gitm.get("rarity", "Common")
            gy = gitm.get("year")
            if not gn or gn in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
                continue
            clean_gn = clean_base_name(gn)
            if clean_gn not in combined_values and gn not in combined_values:
                # Assign baseline placeholder so newly dropped weapons always show in-game
                default_val = f"x1 T1 {gr}" if gr in ["Common", "Uncommon", "Rare"] else "TBD"
                combined_values[gn] = default_val
                combined_values[clean_gn] = default_val
                if gt:
                    combined_values[f"{clean_gn} ({gt})"] = default_val
                if gr:
                    combined_values[f"{clean_gn} [{gr}]"] = default_val
                    combined_values[f"{clean_gn} ({gt}) [{gr}]"] = default_val
                if gy:
                    combined_values[f"{clean_gn} [{gy}]"] = default_val
                    combined_values[f"{clean_gn} ({gt}) [{gy}]"] = default_val
                catalog_new_added += 1

    if catalog_new_added > 0:
        print(f"[Values System] Auto-registered {catalog_new_added} newly released MM2 catalog items as placeholders.")

    print(f"[Values System] Final Verified Catalog: {len(combined_values)} authentic lookup keys, {len(entries)} verified entries.")
    print(f"[Values System] Newly detected items: {new_items_detected}. Unresolved prices: {len(unresolved_items)}.")

    with open(unresolved_output_path, "w", encoding="utf-8") as f:
        json.dump(unresolved_items, f, indent=2, ensure_ascii=False)

    payload = {
        "updated_at": int(time.time()),
        "updated_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "source": "Supreme Values (Official Strict)",
        "count": len(combined_values),
        "unresolved_count": len(unresolved_items),
        "values": combined_values,
        "entries": entries
    }
    for k, v in combined_values.items():
        payload[k] = v

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"[Values System] Saved clean local database: {output_path}")

    if os.path.exists(skins_path):
        update_skins_json_values(skins_path, combined_values)

    dest_repo = (os.environ.get("DEST_REPO") or "").strip() or DEFAULT_REPO
    dest_token = (os.environ.get("DEST_TOKEN") or "").strip() or (os.environ.get("GITHUB_TOKEN") or "").strip() or DEFAULT_TOKEN
    dest_branch = (os.environ.get("DEST_BRANCH") or "").strip() or "main"

    if "GITHUB_ENV" in os.environ:
        try:
            with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as gf:
                gf.write(f"DEST_REPO={dest_repo}\n")
                gf.write(f"DEST_TOKEN={dest_token}\n")
        except Exception:
            pass

    if dest_repo and dest_token:
        print(f"[Values System] Pushing clean values.json and skins.json to GitHub: {dest_repo} ...")
        update_remote_github(dest_token, dest_repo, "values.json", json_bytes, dest_branch)
        if os.path.exists(skins_path):
            with open(skins_path, "rb") as sf:
                update_remote_github(dest_token, dest_repo, "skins.json", sf.read(), dest_branch)
        if os.path.exists(unresolved_output_path):
            with open(unresolved_output_path, "rb") as uf:
                update_remote_github(dest_token, dest_repo, "unresolved_items.json", uf.read(), dest_branch)

    scraper_repo = "Lisi-prime/mm2-scraper"
    print(f"[Values System] Synchronizing scraper repo: {scraper_repo} ...")
    with open(__file__, "rb") as scf:
        update_remote_github(dest_token, scraper_repo, "update_values.py", scf.read(), dest_branch)
    update_remote_github(dest_token, scraper_repo, "values.json", json_bytes, dest_branch)
    if os.path.exists(unresolved_output_path):
        with open(unresolved_output_path, "rb") as uf:
            update_remote_github(dest_token, scraper_repo, "unresolved_items.json", uf.read(), dest_branch)
    if os.path.exists(catalog_dump_path):
        with open(catalog_dump_path, "rb") as cf:
            update_remote_github(dest_token, scraper_repo, "mm2_full_catalog_dump.json", cf.read(), dest_branch)

    print("[Values System] 100% Authentic Supreme Values sync completed successfully.")

if __name__ == "__main__":
    main()
