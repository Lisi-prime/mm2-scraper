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
    "pets"
]

DEFAULT_REPO = "Lisi-prime/mm2_skin"
DEFAULT_TOKEN = "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"

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
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
    # Try supremevalues.com first, then fallback to supremevaluelist.com
    urls = [
        f"https://supremevalues.com/mm2/{category}",
        f"https://supremevaluelist.com/mm2/{category}"
    ]
    for url in urls:
        page_html = None
        if cffi_requests:
            try:
                resp = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", timeout=15)
                if resp.status_code == 200:
                    page_html = resp.text
            except Exception as e:
                print(f"[curl_cffi] Warning {url}: {e}")

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
                    
                    results[name_clean] = final_val

                    # Add convenient aliases
                    if "Chroma " in name_clean:
                        suffix = name_clean.replace("Chroma ", "") + "Chroma"
                        results[suffix] = final_val
                    if name_clean == "Battle Axe II":
                        results["BattleAxe2"] = final_val
                        results["BattleAxe II"] = final_val
                    elif name_clean == "Elderwood Blade":
                        results["ElderwoodBlade"] = final_val
                    elif name_clean == "Elderwood Revolver":
                        results["ElderwoodRevolver"] = final_val
                    elif name_clean == "Elderwood Scythe":
                        results["ElderwoodScythe"] = final_val
                    elif name_clean == "Heart Wand":
                        results["HeartWand"] = final_val
                    elif name_clean == "Traveler's Gun":
                        results["Travelers Gun"] = final_val
                    elif name_clean == "Traveler's Axe":
                        results["Travelers Axe"] = final_val
                    elif name_clean == "Vampire's Gun":
                        results["Vampires Gun"] = final_val
                    elif name_clean == "Vampire's Axe":
                        results["Vampires Axe"] = final_val

                if "Batwing" in results:
                    results["Batwing"] = 42

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
    
    # 1. Base values from accurate_supreme_values.json or existing values.json
    combined = {}
    if os.path.exists(accurate_json):
        try:
            with open(accurate_json, "r", encoding="utf-8") as f:
                combined.update(json.load(f))
        except Exception:
            pass

    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                prev_vals = d.get("values", d)
                if isinstance(prev_vals, dict) and len(prev_vals) > 50:
                    for k, v in prev_vals.items():
                        if k not in combined:
                            combined[k] = v
        except Exception:
            pass

    print(f"[Values System] Initial base catalog size: {len(combined)} items.")

    # 2. Live scrape all categories
    scraped_total = 0
    scraped_data = {}
    for cat in CATEGORIES:
        items = scrape_category(cat)
        scraped_total += len(items)
        scraped_data.update(items)
        time.sleep(0.3)

    if scraped_total > 50:
        combined.update(scraped_data)
        print(f"[Values System] Scrape successful: {scraped_total} items updated.")
    else:
        print(f"[Values System] Warning: Live scrape returned {scraped_total} items. Retaining previous catalog of {len(combined)} items.")

    combined["Batwing"] = 42
    for bad in ["Default Knife", "Default Gun", "DefaultKnife", "DefaultGun"]:
        if bad in combined:
            del combined[bad]

    # Add base candidates for items with (Gun) / (Knife)
    base_candidates = {}
    for name, val in list(combined.items()):
        m = re.match(r"^(.+?)\s*\((Gun|Knife)\)$", name, re.IGNORECASE)
        if m:
            base_name = m.group(1).strip()
            if base_name not in base_candidates:
                base_candidates[base_name] = []
            base_candidates[base_name].append(val)

    for base_name, val_list in base_candidates.items():
        if base_name not in combined:
            combined[base_name] = val_list[0]

    print(f"[Values System] Total verified catalog: {len(combined)} items.")

    # Protection: Never overwrite with less than 100 items!
    if len(combined) < 100:
        print("[Values System] Error: Catalog has fewer than 100 items. Aborting to protect existing files.")
        return

    payload = {
        "updated_at": int(time.time()),
        "updated_str": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "source": "Supreme Values",
        "count": len(combined),
        "values": combined
    }
    for k, v in combined.items():
        payload[k] = v

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    with open(output_path, "wb") as f:
        f.write(json_bytes)
    print(f"[Values System] Saved local file: {output_path}")

    if os.path.exists(skins_path):
        update_skins_json_values(skins_path, combined)

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

if __name__ == "__main__":
    main()
