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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://supremevalues.com/",
}

CATEGORY_INFO = {
    "godlies": {"rarity": "Godly", "is_chroma": False},
    "ancients": {"rarity": "Ancient", "is_chroma": False},
    "vintages": {"rarity": "Vintage", "is_chroma": False},
    "chromas": {"rarity": "Godly", "is_chroma": True},
    "uniques": {"rarity": "Unique", "is_chroma": False},
    "legendaries": {"rarity": "Legendary", "is_chroma": False},
    "rares": {"rarity": "Rare", "is_chroma": False},
    "uncommons": {"rarity": "Uncommon", "is_chroma": False},
    "commons": {"rarity": "Common", "is_chroma": False},
    "pets": {"rarity": "Common", "type": "Pet", "is_chroma": False}
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

class PreservingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req:
            for k, v in HEADERS.items():
                new_req.headers[k] = v
        return new_req

opener = urllib.request.build_opener(PreservingRedirectHandler)

def clean_item_name(name):
    return html.unescape(name).strip()

def scrape_category(category):
    urls = [
        f"https://supremevalues.com/mm2/{category}",
        f"https://supremevaluelist.com/mm2/{category}"
    ]
    cat_meta = CATEGORY_INFO.get(category, {})
    for url in urls:
        page_html = None
        try:
            if cffi_requests:
                for imp in ["chrome120", "chrome124", "safari15_5"]:
                    try:
                        resp = cffi_requests.get(url, impersonate=imp, timeout=12)
                        if resp.status_code == 200 and len(resp.text) > 5000:
                            page_html = resp.text
                            break
                    except Exception:
                        pass

            if not page_html:
                req = urllib.request.Request(url, headers=HEADERS)
                try:
                    with opener.open(req, timeout=14) as response:
                        page_html = response.read().decode("utf-8", errors="ignore")
                except Exception as e:
                    print(f"[urllib] Warning {url}: {e}")

            if page_html:
                pattern = re.compile(
                    r"data-name=['\"]([^'\"]+)['\"].*?Value\s*-\s*<b class=['\"]itemvalue[^'\"]*['\"]>([^<]+)</b>",
                    re.DOTALL
                )
                matches = pattern.findall(page_html)
                if matches:
                    results = {}
                    for name, val_str in matches:
                        name_clean = clean_item_name(name)
                        if name_clean in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
                            continue
                        
                        raw_val = html.unescape(val_str).strip()
                        val_num_str = raw_val.replace(",", "")
                        try:
                            num_val = float(val_num_str)
                            if num_val == int(num_val):
                                num_val = int(num_val)
                            final_val = num_val
                        except ValueError:
                            final_val = raw_val
                        
                        results[name_clean] = {
                            "value": final_val,
                            "category": category,
                            "rarity": cat_meta.get("rarity"),
                            "type": cat_meta.get("type"),
                            "is_chroma": cat_meta.get("is_chroma", False)
                        }

                    if "Batwing" in results:
                        results["Batwing"]["value"] = 42

                    if len(results) > 0:
                        print(f"[Scraper] {category}: {len(results)} items scraped from {url}.")
                        return results
        except Exception as e:
            print(f"[Scraper] Warning {url}: {e}")
    return {}

def update_remote_github(token, repo, file_path, content_bytes, branch="main"):
    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "MM2-Value-Scraper",
    }
    
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
    except Exception as e:
        print(f"[GitHub API] Error pushing {file_path} to {repo}: {e}")
    return False

def update_skins_json_values(skins_json_path, prices_dict):
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
            
            if name in ["Default Knife", "Default Gun"] or item_name in ["DefaultKnife", "DefaultGun", "Default Knife", "Default Gun"]:
                meta["Value"] = 0
                rec["meta"] = meta
                continue

            price = prices_dict.get(item_name) or prices_dict.get(name)
            if price is None:
                n1 = norm(item_name)
                n2 = norm(name)
                price = norm_prices.get(n1) or norm_prices.get(n2)
            
            if price is not None:
                meta["Value"] = price
            else:
                meta["Value"] = 0
                
            rec["meta"] = meta
            updated_count += 1
                
        with open(skins_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Values System] Injected authentic values into {updated_count} skins in skins.json.")
        return True
    except Exception as e:
        print(f"[Values System] Warning updating skins.json: {e}")
        return False

def main():
    print("[Values System] Starting Supreme Values update cycle...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, "values.json")
    skins_path = os.path.join(base_dir, "skins.json")
    accurate_json = os.path.join(base_dir, "accurate_supreme_values.json")
    catalog_path = os.path.join(base_dir, "mm2_items_catalog.json")
    
    # Load official MM2 catalog
    catalog = {}
    norm_catalog = {}
    if os.path.exists(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            for k, v in catalog.items():
                norm_key = re.sub(r"[^a-zA-Z0-9]", "", k).lower()
                norm_catalog[norm_key] = v
            print(f"[Values System] Loaded official MM2 catalog: {len(catalog)} items.")
        except Exception as e:
            print(f"[Values System] Warning loading catalog: {e}")

    # 1. Base values from accurate_supreme_values.json or existing values.json
    combined_values = {}
    item_metadata = {}

    if os.path.exists(accurate_json):
        try:
            with open(accurate_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                combined_values.update(d)
        except Exception:
            pass

    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                prev_vals = d.get("values", d)
                if isinstance(prev_vals, dict) and len(prev_vals) > 50:
                    for k, v in prev_vals.items():
                        if k not in combined_values:
                            combined_values[k] = v
                if "entries" in d and isinstance(d["entries"], list):
                    for e in d["entries"]:
                        n = e.get("name") or e.get("raw")
                        if n:
                            item_metadata[n] = e
        except Exception:
            pass

    # 2. Live scrape all categories
    scraped_total = 0
    for cat in CATEGORY_INFO.keys():
        scraped_items = scrape_category(cat)
        scraped_total += len(scraped_items)
        for name, info in scraped_items.items():
            combined_values[name] = info["value"]
            item_metadata[name] = info
        time.sleep(0.3)

    if scraped_total > 50:
        print(f"[Values System] Scrape successful: {scraped_total} items updated.")
    else:
        print(f"[Values System] Warning: Live scrape returned {scraped_total} items. Retaining previous catalog of {len(combined_values)} items.")

    combined_values["Batwing"] = 42
    for bad in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
        if bad in combined_values:
            del combined_values[bad]

    # Verified authentic Supreme Values for Vintages & High tier items
    vintages_explicit = {
        "Cowboy": (4, "Gun", "Vintage"),
        "Golden": (4, "Gun", "Vintage"),
        "Splitter": (3, "Knife", "Vintage"),
        "Phaser": (5, "Gun", "Vintage"),
        "Prince": (6, "Knife", "Vintage"),
        "Shadow": (6, "Knife", "Vintage"),
        "America": (7, "Gun", "Vintage"),
        "Blood": (8, "Knife", "Vintage"),
        "Ghost": (8, "Knife", "Vintage"),
        "Laser": (8, "Gun", "Vintage"),
    }
    for v_name, (v_val, v_type, v_rar) in vintages_explicit.items():
        combined_values[v_name] = v_val
        item_metadata[v_name] = {
            "value": v_val,
            "type": v_type,
            "rarity": v_rar,
            "category": "vintages",
            "is_chroma": False
        }

    # Add standard naming aliases
    aliases = {
        "Travelers Gun": combined_values.get("Traveler's Gun", 5200),
        "Travelers Axe": combined_values.get("Traveler's Axe", 7100),
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
        "GingerLuger": combined_values.get("Ginger Luger", 17),
        "RedLuger": combined_values.get("Red Luger", 35),
        "GreenLuger": combined_values.get("Green Luger", 55),
        "Black Luger": combined_values.get("Black Luger", 1000000),
    }
    for a_name, a_val in aliases.items():
        if a_val is not None:
            combined_values[a_name] = a_val

    # Normalize combined_values so stale bracketed keys never pollute fresh scrape
    clean_combined = {}
    for k, v in combined_values.items():
        c_k = re.sub(r"\s*\(.*?\)", "", k)
        c_k = re.sub(r"\s*\[.*?\]", "", c_k).strip()
        if c_k not in clean_combined or k == c_k:
            clean_combined[c_k] = v
    for v_name, (v_val, v_type, v_rar) in vintages_explicit.items():
        clean_combined[v_name] = v_val
    combined_values = clean_combined

    # Build 100% complete structured item entries
    entries = []
    for raw_name, val in combined_values.items():
        if raw_name in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
            continue

        clean_name = re.sub(r"\s*\(.*?\)", "", raw_name)
        clean_name = re.sub(r"\s*\[.*?\]", "", clean_name).strip()

        is_chroma = "Chroma" in raw_name or clean_name.startswith("Chroma ") or clean_name.endswith("Chroma")
        lookup_name = clean_name.replace("Chroma ", "").replace("Chroma", "").strip()
        norm_lookup = re.sub(r"[^a-zA-Z0-9]", "", lookup_name).lower()
        norm_clean = re.sub(r"[^a-zA-Z0-9]", "", clean_name).lower()

        item_type = None
        rarity = None
        year = None

        # A. Official MM2 Catalog match
        cat_entry = catalog.get(lookup_name) or catalog.get(clean_name) or norm_catalog.get(norm_lookup) or norm_catalog.get(norm_clean)
        if cat_entry:
            item_type = cat_entry.get("itemType")
            rarity = cat_entry.get("rarity")
            year = cat_entry.get("year")

        # B. Category / Scraper metadata
        scraped_meta = item_metadata.get(raw_name) or item_metadata.get(clean_name) or item_metadata.get(lookup_name)
        if scraped_meta:
            if not item_type and scraped_meta.get("type"):
                item_type = scraped_meta.get("type")
            if not rarity and scraped_meta.get("rarity"):
                rarity = scraped_meta.get("rarity")
            if scraped_meta.get("is_chroma"):
                is_chroma = True

        # C. Keyword & format deduction
        if not item_type:
            m_type = re.search(r"\((Gun|Knife|Pet)\)", raw_name, re.IGNORECASE)
            if m_type:
                item_type = m_type.group(1).capitalize()
            elif clean_name.lower().endswith("gun") or "revolver" in clean_name.lower() or "luger" in clean_name.lower() or "blaster" in clean_name.lower():
                item_type = "Gun"
            elif clean_name.lower().endswith("knife") or clean_name.lower().endswith("blade") or clean_name.lower().endswith("dagger") or clean_name.lower().endswith("scythe") or clean_name.lower().endswith("axe"):
                item_type = "Knife"

        if not rarity:
            m_rar = re.search(r"\[(Godly|Ancient|Vintage|Legendary|Rare|Uncommon|Common|Unique)\]", raw_name, re.IGNORECASE)
            if m_rar:
                rarity = m_rar.group(1).capitalize()
            elif isinstance(val, str):
                v_low = val.lower()
                if "rare" in v_low: rarity = "Rare"
                elif "uncommon" in v_low: rarity = "Uncommon"
                elif "common" in v_low: rarity = "Common"
                elif "legendary" in v_low: rarity = "Legendary"

        # D. High collectible / Godly special overrides
        if lookup_name in ["Black Luger", "BlackLuger"]:
            item_type = "Gun"
            rarity = "Godly"
        elif lookup_name in ["BattleAxe2", "Battleaxe II", "Battle Axe II"]:
            item_type = "Knife"
            rarity = "Godly"
        elif lookup_name in ["Red Scratch", "Blue Scratch"]:
            item_type = "Knife"
            rarity = "Rare"
        elif "traveler" in norm_lookup and "axe" in norm_lookup:
            item_type = "Knife"
            rarity = "Ancient"
        elif "vampire" in norm_lookup and "axe" in norm_lookup:
            item_type = "Knife"
            rarity = "Godly"
        elif lookup_name in ["Checkers"]:
            item_type = "Knife"
            rarity = "Uncommon"

        if is_chroma and not rarity:
            rarity = "Godly"

        entries.append({
            "name": clean_name or raw_name,
            "raw": raw_name,
            "type": item_type,
            "rarity": rarity,
            "is_chroma": is_chroma,
            "year": year,
            "value": val
        })

    # Expand combined_values with convenience typed & bracketed keys
    extra_keys = {}
    for e in entries:
        c_name = e["name"]
        val = e["value"]
        t = e["type"]
        r = e["rarity"]
        if t:
            extra_keys[f"{c_name} ({t})"] = val
        if r:
            extra_keys[f"{c_name} [{r}]"] = val
        if t and r:
            extra_keys[f"{c_name} ({t}) [{r}]"] = val

    # Force explicit vintage keys
    for v_name, (v_val, v_type, v_rar) in vintages_explicit.items():
        extra_keys[v_name] = v_val
        extra_keys[f"{v_name} ({v_type})"] = v_val
        extra_keys[f"{v_name} [{v_rar}]"] = v_val
        extra_keys[f"{v_name} ({v_type}) [{v_rar}]"] = v_val

    combined_values.update(extra_keys)

    print(f"[Values System] Total verified catalog: {len(combined_values)} items, {len(entries)} structured entries.")

    payload = {
        "updated_at": int(time.time()),
        "updated_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "source": "Supreme Values",
        "count": len(combined_values),
        "values": combined_values,
        "entries": entries
    }
    for k, v in combined_values.items():
        payload[k] = v

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"[Values System] Saved local file: {output_path}")

    if os.path.exists(skins_path):
        update_skins_json_values(skins_path, combined_values)

    dest_repo = os.environ.get("DEST_REPO", DEFAULT_REPO)
    dest_token = os.environ.get("DEST_TOKEN") or os.environ.get("GITHUB_TOKEN") or DEFAULT_TOKEN
    dest_branch = os.environ.get("DEST_BRANCH", "main")

    if dest_repo and dest_token:
        print(f"[Values System] Pushing values.json and skins.json to GitHub: {dest_repo} ...")
        update_remote_github(dest_token, dest_repo, "values.json", json_bytes, dest_branch)
        if os.path.exists(skins_path):
            with open(skins_path, "rb") as sf:
                skins_bytes = sf.read()
            update_remote_github(dest_token, dest_repo, "skins.json", skins_bytes, dest_branch)

    # Also synchronize update_values.py, mm2_items_catalog.json, values.json to Lisi-prime/mm2-scraper (when running locally)
    if not os.environ.get("GITHUB_ACTIONS"):
        scraper_repo = "Lisi-prime/mm2-scraper"
        print(f"[Values System] Synchronizing scraper repo: {scraper_repo} ...")
        with open(__file__, "rb") as vf:
            script_bytes = vf.read()
        update_remote_github(dest_token, scraper_repo, "update_values.py", script_bytes, dest_branch)
        update_remote_github(dest_token, scraper_repo, "values.json", json_bytes, dest_branch)
        if os.path.exists(catalog_path):
            with open(catalog_path, "rb") as cf:
                cat_bytes = cf.read()
            update_remote_github(dest_token, scraper_repo, "mm2_items_catalog.json", cat_bytes, dest_branch)

if __name__ == "__main__":
    main()
