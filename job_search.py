import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

# =============================================================================
# ACCOUNT 2 — Strategy, Consulting, Sales Ops, BDM, KAM, Program Mgmt
# Focus: Consulting firms, Pharma/Medical sales, FMCG commercial,
#        Strategy roles, Operations, Target companies (Meril etc.)
# Strategy: Different queries from Account 1, complementary not overlapping
# =============================================================================

SEARCH_QUERIES = [
    # --- Strategy & Consulting ---
    "strategy consultant India",
    "management consultant associate India",
    "consulting analyst India",
    "associate consultant strategy India",
    "business strategy analyst India",
    "corporate strategy analyst India",
    "strategy and operations manager India",
    "operations consultant India",

    # --- Sales Operations & Commercial ---
    "sales operations manager India",
    "sales operations analyst India",
    "commercial excellence manager India",
    "commercial operations India",
    "revenue operations manager India startup",

    # --- Business Development (specific sectors) ---
    "business development manager medtech",
    "business development manager medical devices",
    "business development manager pharma",
    "business development manager healthcare",
    "business development manager FMCG",
    "business development manager consumer",

    # --- Key Account Manager (specific sectors) ---
    "key account manager pharma India",
    "key account manager medical devices India",
    "key account manager FMCG India",
    "key account manager healthcare India",

    # --- Market Access / Medical Marketing ---
    "product manager pharma India",
    "product manager medical devices India",
    "market access manager pharma India",
    "brand manager pharma India",
    "brand manager FMCG India",
    "assistant brand manager FMCG",

    # --- Target companies direct search ---
    "Meril Life Sciences",
    "Meril medtech",
    "TTK healthcare jobs",
    "Narang medical India",
    "Biorad medisys",
    "Atlas surgical India",

    # --- Program / Project Manager (ops-focused) ---
    "program manager operations India",
    "program manager supply chain India",
    "project manager healthcare India",
    "project manager FMCG India",

    # --- Founder's Office / CoS (separate from Account 1 to catch more) ---
    "founder office strategy India",
    "chief of staff operations India",
    "chief of staff consulting India",
]

PAGES_PER_QUERY = 5

# Last 24 hrs — wide enough to get volume, dedup handles repeats
TIME_FILTER = "r86400"

# Entry, Associate, Mid-Senior
EXP_FILTER = "2%2C3%2C4"

# ---------------------------------------------------------------------------
# INCLUDE keywords — title must have at least one
# ---------------------------------------------------------------------------
INCLUDE_KEYWORDS = [
    # Strategy & Consulting
    "strategy consultant", "management consultant", "consulting analyst",
    "associate consultant", "strategy analyst", "strategy manager",
    "strategy and operations", "corporate strategy", "business strategy",
    "operations consultant",
    # Sales Ops & Commercial
    "sales operations", "commercial excellence", "commercial operations",
    "revenue operations",
    # BDM & KAM
    "business development manager", "business development",
    "key account manager", "kam",
    # Product & Brand (pharma/medtech/FMCG specific)
    "product manager", "associate product manager",
    "brand manager", "assistant brand manager",
    "product analyst",
    # Market access
    "market access", "medical marketing",
    # Program / Project
    "program manager", "project manager",
    # Founder's office / CoS
    "founder's office", "founders office", "chief of staff",
    # Other ops
    "business operations", "bizops",
    "market research analyst",
]

# ---------------------------------------------------------------------------
# EXCLUDE keywords
# ---------------------------------------------------------------------------
EXCLUDE_KEYWORDS = [
    # Too senior
    "senior", " sr.", " sr ", "lead ", "principal", "staff ",
    "vp ", "vice president", "director", "head of", "head -",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "deputy general manager", "dgm", "agm",
    "associate director", "associate vp",
    "national sales", "zonal sales", "zonal manager",
    # Too junior
    "intern", "internship", "fresher", "trainee",
    # Wrong functions — tech/engineering
    "software engineer", "software developer", "developer", "sde",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "full-stack", "qa engineer",
    "test engineer", "data engineer", "mlops", "cloud engineer",
    "technical program", "technical project", "it project",
    # Finance/admin
    "accountant", "finance manager", "chartered accountant", "ca ",
    "credit analyst", "loan officer", "underwriter", "actuary",
    "wealth management", "equity research", "portfolio manager",
    "fund manager", "stock", "trading", "fixed income",
    "compliance officer", "kyc analyst", "risk analyst",
    "insurance advisor", "claims analyst",
    # Medical/clinical (not business roles)
    "radiologist", "doctor", "physician", "nurse", "technician",
    "clinical research", "medical affairs", "pharmacovigilance",
    "therapeutic area", "medical science liaison",
    # Field/territory sales (too junior / wrong track)
    "territory sales manager", "area sales manager", "asm ",
    "field sales", "sales executive", "sales representative",
    "channel sales", "channel partner",
    "zsm", "rsm ", "regional sales manager",
    # Other unwanted
    "recruiter", "hr manager", "talent acquisition", "hrbp",
    "content writer", "graphic designer", "telecaller", "copywriter",
    "cyber", "cybersecurity", "network engineer",
    "influencer", "content creator",
    "quality assurance", "quality control",
    "procurement", "sourcing manager",
    "warehouse", "driver", "logistics coordinator",
]

# ---------------------------------------------------------------------------
# LOCATION filter
# ---------------------------------------------------------------------------
INCLUDE_LOCATIONS = [
    "hyderabad", "ahmedabad", "gurugram", "gurgaon",
    "bengaluru", "bangalore", "pune", "mumbai",
    "delhi", "noida", "chennai", "india", "remote", "pan india",
]

# ---------------------------------------------------------------------------
# SECTOR-FREE roles: pass without needing a sector word
# ---------------------------------------------------------------------------
SECTOR_FREE_ROLES = [
    "strategy consultant", "management consultant", "consulting analyst",
    "associate consultant", "strategy analyst", "strategy manager",
    "strategy and operations", "corporate strategy", "business strategy",
    "operations consultant",
    "sales operations", "commercial excellence", "revenue operations",
    "founder's office", "founders office", "chief of staff",
    "business operations", "bizops",
    "program manager",  # Account 2 allows program manager freely
]

# ---------------------------------------------------------------------------
# SECTOR-DEPENDENT roles: need a sector word in title
# ---------------------------------------------------------------------------
SECTOR_DEPENDENT_ROLES = [
    "business development manager", "business development",
    "key account manager",
    "product manager", "associate product manager",
    "brand manager", "assistant brand manager",
    "market access",
    "project manager",
    "commercial operations",
    "market research analyst",
]

ALLOWED_SECTORS = [
    "medtech", "med tech", "medical", "healthcare", "health",
    "pharma", "pharmaceutical", "diagnostics", "hospital",
    "fmcg", "consumer", "food", "beverage", "nutrition",
    "wellness", "beauty", "personal care", "retail", "d2c",
    "surgical", "implant", "device", "ortho",
    "ecommerce", "e-commerce", "startup", "saas", "tech",
    "edtech", "agritech", "proptech", "supply chain",
    "manufacturing", "industrial", "automotive",
    "renewable", "energy", "solar",
]

# ---------------------------------------------------------------------------
# BLOCKED companies — pure finance/broking/insurance
# (Consulting strategy at these is fine, but title check handles that via SECTOR_FREE)
# ---------------------------------------------------------------------------
BLOCKED_FINANCE_COMPANIES = [
    "zerodha", "groww", "upstox", "angel broking", "sharekhan",
    "motilal oswal", "iifl", "edelweiss",
    "nse ", "bse ", "sebi",
    "bajaj allianz", "hdfc life", "lic ", "sbi life",
    "digit insurance", "acko",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean(text):
    text = text or ""
    text = text.replace("&amp;", "and").replace("&", "and")
    text = text.replace("<", "").replace(">", "")
    return text.strip()

def make_dedup_key(title, company):
    t = re.sub(r'[^a-z0-9]', '', title.lower())[:40]
    c = re.sub(r'[^a-z0-9]', '', company.lower())[:20]
    return "{}__{}".format(t, c)

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)

def fetch_jobs(query, start=0):
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        "?keywords={}&location=India&f_TPR={}&f_E={}&start={}"
    ).format(requests.utils.quote(query), TIME_FILTER, EXP_FILTER, start)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        return response.text
    except Exception as e:
        print("Fetch error '{}': {}".format(query, e))
        return ""

def parse_jobs(html):
    jobs = []
    blocks = html.split('<div class="base-card')
    title_re = re.compile(
        r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*([^<]+)\s*</h3>', re.I)
    company_re = re.compile(
        r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>[\s\S]*?<a[^>]*>\s*([^<]+)\s*</a>', re.I)
    location_re = re.compile(
        r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+)\s*</span>', re.I)
    url_re = re.compile(
        r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', re.I)

    for block in blocks:
        title_m = title_re.search(block)
        url_m = url_re.search(block)
        if not title_m or not url_m:
            continue
        company_m = company_re.search(block)
        location_m = location_re.search(block)
        jobs.append({
            "title": clean(title_m.group(1)),
            "company": clean(company_m.group(1) if company_m else "Unknown"),
            "location": clean(location_m.group(1) if location_m else "India"),
            "url": url_m.group(1).strip().split("?")[0],
        })
    return jobs

def is_blocked_company(company):
    c = company.lower()
    return any(bc in c for bc in BLOCKED_FINANCE_COMPANIES)

def is_relevant(job):
    title = job["title"].lower()
    location = job["location"].lower()
    company = job["company"].lower()

    if not any(k in title for k in INCLUDE_KEYWORDS):
        return False
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False
    if not any(l in location for l in INCLUDE_LOCATIONS):
        return False
    if is_blocked_company(company):
        return False

    # Sector-free roles pass directly
    if any(k in title for k in SECTOR_FREE_ROLES):
        return True

    # Sector-dependent roles need sector word
    if any(k in title for k in SECTOR_DEPENDENT_ROLES):
        if any(s in title for s in ALLOWED_SECTORS):
            return True
        return False

    return True

def send_telegram(message):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            print("Telegram error: {} - {}".format(response.status_code, response.text[:200]))
        return response.ok
    except Exception as e:
        print("Telegram error: {}".format(e))
        return False

def main():
    seen_jobs = load_seen_jobs()
    new_jobs = []
    seen_keys = set(seen_jobs.keys())

    for query in SEARCH_QUERIES:
        found_in_query = 0
        for page in range(PAGES_PER_QUERY):
            start = page * 25
            print("Fetching: '{}' page {}".format(query, page + 1))
            html = fetch_jobs(query, start=start)
            jobs = parse_jobs(html)
            if not jobs:
                print("  No results on page {}, stopping query.".format(page + 1))
                break
            for job in jobs:
                key = make_dedup_key(job["title"], job["company"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if not is_relevant(job):
                    continue
                new_jobs.append(job)
                found_in_query += 1
                seen_jobs[key] = datetime.now(timezone.utc).isoformat()
        print("  → {} new relevant jobs from this query".format(found_in_query))

    print("\nTotal new jobs found: {}".format(len(new_jobs)))

    if not new_jobs:
        print("No new matching jobs found.")
        save_seen_jobs(seen_jobs)
        return

    IST = timezone(timedelta(hours=5, minutes=30))
    batch_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    sent = 0
    for job in new_jobs:
        message = (
            "<b>{}</b> | {}\n"
            "{}\n"
            "{}\n\n"
            "{}"
        ).format(job["title"], job["company"], job["location"], batch_time, job["url"])

        success = send_telegram(message)
        if success:
            sent += 1
            print("Sent: {} @ {}".format(job["title"], job["company"]))
        else:
            print("Failed: {}".format(job["title"]))

    print("\nSent {}/{} jobs.".format(sent, len(new_jobs)))
    save_seen_jobs(seen_jobs)
    print("Done.")

if __name__ == "__main__":
    main()
