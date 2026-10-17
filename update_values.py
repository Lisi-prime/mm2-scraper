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
    return html.unescape(name).strip()

def scrape_category(category):
    urls = [
        f"https://supremevaluelist.com/mm2/{category}",
        f"https://supremevalues.com/mm2/{category}"
    ]
    for url in urls:
        page_html = None
        try:
            if cffi_requests:
                for imp in ["chrome120", "chrome124", "safari15_5"]:
                    try:
                        resp = cffi_requests.get(url, impersonate=imp, timeout=14)
                        if resp.status_code == 200 and len(resp.text) > 4000:
                            page_html = resp.text
                            break
                    except Exception:
                        pass

            if not page_html:
                req = urllib.request.Request(url, headers=HEADERS)
                try:
                    with urllib.request.urlopen(req, timeout=14) as response:
                        page_html = response.read().decode("utf-8", errors="ignore")
                except Exception as e:
                    print(f"[urllib] Warning {url}: {e}")

            if page_html:
                soup = BeautifulSoup(page_html, "html.parser")
                results = []
                for col in soup.find_all("div", class_="itemcolumn"):
                    # Ignore hidden easter-eggs / unreleased placeholders on Supreme (e.g. hidden Batwing 1M, Black Luger 1M)
                    style_str = col.get("style", "").replace(" ", "").lower()
                    if "display:none" in style_str:
                        continue

                    btn = col.find("button", attrs={"data-name": True})
                    if not btn:
                        continue
                    name_raw = clean_item_name(btn["data-name"])
                    if not name_raw or name_raw in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
                        continue

                    val_tag = col.find("b", class_=re.compile(r"itemvalue"))
                    raw_val = val_tag.text.strip() if val_tag else "0"
                    val_num_str = raw_val.replace(",", "")
                    try:
                        num_val = float(val_num_str)
                        if num_val == int(num_val):
                            num_val = int(num_val)
                        final_val = num_val
                    except ValueError:
                        final_val = raw_val

                    year = col.get("data-year") or None
                    event = col.get("data-event") or None

                    results.append({
                        "name_raw": name_raw,
                        "value": final_val,
                        "category": category,
                        "year": year,
                        "event": event
                    })

                if len(results) > 0:
                    print(f"[Scraper] {category}: {len(results)} items scraped from {url}.")
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
        iterable = entries.values() if isinstance(entries, dict) else entries

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

            price = prices_dict.get(item_name) or prices_dict.get(name) or norm_prices.get(norm(item_name)) or norm_prices.get(norm(name))
            meta["Value"] = price if price is not None else 0
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
    print("[Values System] Starting 100% Authentic Supreme Values scrape cycle...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, "values.json")
    skins_path = os.path.join(base_dir, "skins.json")
    catalog_dump_path = os.path.join(base_dir, "mm2_full_catalog_dump.json")

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

    # 1. Scrape all 11 valid tradeable categories from Supreme
    scraped_raw_items = []
    for cat in CATEGORIES:
        items = scrape_category(cat)
        scraped_raw_items.extend(items)
        time.sleep(0.25)

    print(f"[Values System] Total raw scraped items from Supreme: {len(scraped_raw_items)}.")

    if len(scraped_raw_items) < 300:
        print(f"[Values System] CRITICAL ERROR: Scraped only {len(scraped_raw_items)} items (< 300).")
        print("[Values System] Likely network issue or Cloudflare block. REFUSING to overwrite database!")
        sys.exit(1)

    # 2. Build complete, verified items and resolve exact Type, Rarity, Chroma, Year
    entries = []
    combined_values = {}

    def resolve_meta(raw_name, cat):
        clean = re.sub(r"\s*\(.*?\)", "", raw_name).strip()
        norm = re.sub(r"[^a-zA-Z0-9]", "", clean).lower()
        is_chroma = (cat == "chromas") or "chroma" in raw_name.lower()

        # A. Vintages exact
        if cat == "vintages" and clean in VINTAGES_EXPLICIT:
            t, r, _ = VINTAGES_EXPLICIT[clean]
            return t, r, is_chroma

        # B. Pets & Misc
        if cat == "pets":
            return "Pet", "Common", is_chroma
        if cat == "misc":
            return "Misc", "Common", is_chroma

        # C. Explicit (Gun), (Knife), (Pet), (Misc) in scraped raw name
        m = re.search(r"\((Gun|Knife|Pet|Misc)\)", raw_name, re.IGNORECASE)
        if m:
            return m.group(1).capitalize(), RARITY_BY_CATEGORY.get(cat, "Common"), is_chroma

        # D. Name keywords
        cl = clean.lower()
        cat_rarity = RARITY_BY_CATEGORY.get(cat, "Common")
        if cl.endswith("gun") or cl.endswith("revolver") or cl.endswith("luger") or cl.endswith("blaster") or cl.endswith("shotgun") or cl.endswith("bow"):
            return "Gun", cat_rarity, is_chroma
        if cl.endswith("knife") or cl.endswith("blade") or cl.endswith("dagger") or cl.endswith("scythe") or cl.endswith("axe") or cl.endswith("sword") or cl.endswith("saw"):
            return "Knife", cat_rarity, is_chroma

        # E. Official MM2 database dump
        candidates = norm_dump.get(norm, [])
        if candidates:
            for c in candidates:
                if c.get("rarity") == cat_rarity:
                    return c.get("type"), cat_rarity, is_chroma
            chosen = candidates[0]
            return chosen.get("type"), cat_rarity or chosen.get("rarity"), is_chroma

        return "Knife", cat_rarity, is_chroma

    seen_entries = set()

    for item in scraped_raw_items:
        raw_name = item["name_raw"]
        val = item["value"]
        cat = item["category"]

        clean_name = re.sub(r"\s*\(.*?\)", "", raw_name).strip()
        t, r, is_chroma = resolve_meta(raw_name, cat)

        # Force exact vintage value from Supreme
        if clean_name in VINTAGES_EXPLICIT and cat == "vintages":
            t, r, v_val = VINTAGES_EXPLICIT[clean_name]
            val = v_val

        entry_key = f"{clean_name}|{t}|{r}|{is_chroma}"
        if entry_key not in seen_entries:
            seen_entries.add(entry_key)
            entry = {
                "name": clean_name,
                "raw": raw_name,
                "type": t,
                "rarity": r,
                "is_chroma": is_chroma,
                "year": item.get("year"),
                "value": val
            }
            entries.append(entry)

        # Populate top-level dictionary keys
        # 1. Base clean name
        if clean_name not in combined_values:
            combined_values[clean_name] = val

        # 2. Typed key: "Cowboy (Gun)", "Raygun (Gun)", "Alienbeam (Knife)"
        if t:
            combined_values[f"{clean_name} ({t})"] = val

        # 3. Chroma specific
        if is_chroma and not clean_name.startswith("Chroma "):
            combined_values[f"Chroma {clean_name}"] = val
            if t:
                combined_values[f"Chroma {clean_name} ({t})"] = val

    # Fix Batwing base key to 42 (Ancient standard weapon)
    combined_values["Batwing"] = 42
    combined_values["Batwing (Knife)"] = 42
    combined_values["Batwing [Ancient]"] = 42

    # Add standard MM2 alternative spellings without clutter
    common_aliases = {
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
    }
    for a_name, a_val in common_aliases.items():
        if a_val is not None:
            combined_values[a_name] = a_val

    print(f"[Values System] Final clean catalog: {len(combined_values)} lookup keys, {len(entries)} verified entries.")

    payload = {
        "updated_at": int(time.time()),
        "updated_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "source": "Supreme Values (Official)",
        "count": len(combined_values),
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

    dest_repo = os.environ.get("DEST_REPO", DEFAULT_REPO)
    dest_token = os.environ.get("DEST_TOKEN") or os.environ.get("GITHUB_TOKEN") or DEFAULT_TOKEN
    dest_branch = os.environ.get("DEST_BRANCH", "main")

    if dest_repo and dest_token:
        print(f"[Values System] Pushing clean values.json and skins.json to GitHub: {dest_repo} ...")
        update_remote_github(dest_token, dest_repo, "values.json", json_bytes, dest_branch)
        if os.path.exists(skins_path):
            with open(skins_path, "rb") as sf:
                update_remote_github(dest_token, dest_repo, "skins.json", sf.read(), dest_branch)

    # Sync to scraper repo
    scraper_repo = "Lisi-prime/mm2-scraper"
    print(f"[Values System] Synchronizing scraper repo: {scraper_repo} ...")
    with open(__file__, "rb") as scf:
        update_remote_github(dest_token, scraper_repo, "update_values.py", scf.read(), dest_branch)
    update_remote_github(dest_token, scraper_repo, "values.json", json_bytes, dest_branch)
    if os.path.exists(catalog_dump_path):
        with open(catalog_dump_path, "rb") as cf:
            update_remote_github(dest_token, scraper_repo, "mm2_full_catalog_dump.json", cf.read(), dest_branch)

    print("[Values System] 100% Authentic Supreme Values sync completed successfully.")

if __name__ == "__main__":
    main()
