import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

# =============================================================================
# ACCOUNT 2 — Consulting | Sales Ops | BDM/KAM (Pharma/FMCG/Medtech) |
#             Brand Manager | Program Mgmt | Target Companies
#
# Philosophy:
#   - Complementary to Account 1 — NO overlap in search queries
#   - Consulting: ZS, EY, McKinsey, BCG, Deloitte type associate roles
#   - Commercial: BDM/KAM strictly in pharma, medtech, FMCG, consumer
#   - Brand: FMCG/pharma brand managers at entry/associate level
#   - Target companies: Meril, TTK, Narang, Biorad etc. scraped directly
#   - Sales Ops and commercial excellence — sector-free
#   - Experience: Entry (2) + Associate (3) only
# =============================================================================

SEARCH_QUERIES = [
    # --- Consulting (sector-free, strong brands) ---
    "associate consultant strategy India",
    "decision analytics associate consultant India",
    "strategy operations associate consultant India",
    "management consulting analyst India",
    "business consulting analyst India",
    "ZS associates India",
    "associate consultant EY India",
    "associate consultant Deloitte India",
    "associate consultant KPMG India",
    "associate consultant BCG India",
    "associate consultant McKinsey India",

    # --- Sales Operations & Commercial Excellence ---
    "sales operations manager India",
    "sales operations analyst India",
    "commercial excellence manager India",
    "commercial operations manager India",

    # --- BDM strictly in good sectors ---
    "business development manager medtech India",
    "business development manager medical devices India",
    "business development manager pharma India",
    "business development manager healthcare India",
    "business development manager FMCG India",
    "business development manager consumer India",

    # --- KAM strictly in good sectors ---
    "key account manager pharma India",
    "key account manager medical devices India",
    "key account manager FMCG India",
    "key account manager healthcare India",

    # --- Brand / Marketing (FMCG/pharma only) ---
    "assistant brand manager FMCG India",
    "brand manager pharma India",
    "brand manager consumer India",
    "associate brand manager India",
    "trade marketing manager FMCG India",
    "category manager FMCG India",

    # --- Market Access / Medical Marketing ---
    "market access manager pharma India",
    "medical marketing manager India",
    "product manager pharma India",
    "product manager medical devices India",

    # --- Program / Project Manager (ops focused) ---
    "program manager supply chain India",
    "program manager operations healthcare India",
    "project manager FMCG India",
    "project manager healthcare India",

    # --- Target companies direct ---
    "Meril Life Sciences",
    "TTK healthcare India",
    "Narang medical India",
    "Biorad medisys India",
    "Atlas surgical India",
    "Siora surgicals India",
]

PAGES_PER_QUERY = 5
TIME_FILTER = "r86400"
EXP_FILTER = "2%2C3"   # Entry + Associate only

# ---------------------------------------------------------------------------
# INCLUDE — title must have at least one
# ---------------------------------------------------------------------------
INCLUDE_KEYWORDS = [
    # Consulting
    "associate consultant", "consulting analyst", "management consultant",
    "strategy consultant", "business consultant",
    "decision analytics", "strategy operations consultant",
    # Sales Ops / Commercial
    "sales operations", "commercial excellence", "commercial operations",
    # BDM
    "business development manager",
    # KAM
    "key account manager",
    # Brand / Category
    "brand manager", "assistant brand manager", "associate brand manager",
    "trade marketing", "category manager",
    # Medical marketing / market access
    "market access", "medical marketing",
    "product manager",
    # Program / Project
    "program manager", "project manager",
    # Founders / Strategy (catches target company results)
    "founder's office", "founders office",
    "strategy manager", "strategy analyst",
    "bizops", "business operations",
]

# ---------------------------------------------------------------------------
# EXCLUDE
# ---------------------------------------------------------------------------
EXCLUDE_KEYWORDS = [
    # Seniority
    "senior", " sr.", " sr ", "lead ", "principal", "staff ",
    "vp ", "v.p.", "vice president", "director", "head of", "head -",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "deputy general manager", "dgm", "agm",
    "associate director", "associate vp", "group manager",
    "national manager", "cluster manager", "zonal manager",
    "national sales", "zonal sales",
    # Too junior
    "intern", "internship", "fresher", "trainee",
    # Engineering
    "software engineer", "software developer", "sde ", "developer",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "qa engineer", "test engineer",
    "data engineer", "mlops", "cloud engineer",
    "technical product", "technical program", "technical project",
    "it project", "it operations",
    # Finance/core banking
    "accountant", "finance manager", "chartered accountant",
    "credit analyst", "loan officer", "underwriter",
    "equity research", "portfolio manager", "fund manager",
    "wealth management", "stock analyst", "trading",
    "fixed income", "compliance officer", "kyc", "risk analyst",
    "insurance advisor", "claims",
    # Medical/clinical (not commercial)
    "radiologist", "doctor", "physician", "nurse", "technician",
    "clinical research", "medical affairs", "pharmacovigilance",
    "medical science liaison", "msl ",
    # Field/territory sales (wrong track)
    "territory sales manager", "area sales manager",
    "regional sales manager", "field sales",
    "sales executive", "sales representative", "sales officer",
    "channel sales", "channel partner",
    "asm ", "zsm ", "rsm ",
    # Other
    "recruiter", "hr manager", "talent acquisition",
    "content writer", "graphic designer", "telecaller",
    "cybersecurity", "network engineer",
    "quality assurance", "quality control",
    "procurement manager", "sourcing manager",
    "warehouse", "logistics coordinator",
]

INCLUDE_LOCATIONS = [
    "hyderabad", "ahmedabad", "gurugram", "gurgaon",
    "bengaluru", "bangalore", "pune", "mumbai",
    "delhi", "noida", "chennai", "india", "remote", "pan india",
]

# Roles that pass with NO sector check needed
SECTOR_FREE_ROLES = [
    "associate consultant", "consulting analyst", "management consultant",
    "strategy consultant", "business consultant",
    "decision analytics", "strategy operations consultant",
    "sales operations", "commercial excellence", "commercial operations",
    "founder's office", "founders office",
    "strategy manager", "strategy analyst",
    "bizops", "business operations",
    "program manager",
]

# These MUST have a sector word
SECTOR_DEPENDENT_ROLES = [
    "business development manager",
    "key account manager",
    "brand manager", "assistant brand manager", "associate brand manager",
    "trade marketing", "category manager",
    "market access", "medical marketing",
    "product manager",
    "project manager",
]

ALLOWED_SECTORS = [
    "medtech", "med tech", "medical", "healthcare", "health",
    "pharma", "pharmaceutical", "diagnostics", "hospital",
    "surgical", "implant", "device", "ortho",
    "fmcg", "consumer", "food", "beverage", "nutrition",
    "wellness", "beauty", "personal care", "d2c", "retail",
    "ecommerce", "e-commerce", "startup", "saas", "tech",
    "edtech", "agritech", "manufacturing", "industrial", "automotive",
    "renewable", "energy", "solar", "supply chain",
]

BLOCKED_COMPANIES = [
    "zerodha", "groww", "upstox", "angel broking", "sharekhan",
    "motilal oswal", "iifl", "edelweiss", "nuvama",
    "bajaj allianz", "hdfc life", "sbi life", "lic india",
    "digit insurance", "acko", "kotak securities",
]


def clean(text):
    text = text or ""
    text = text.replace("&amp;", "and").replace("&", "and")
    text = re.sub(r'<[^>]+>', '', text)
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
        resp = requests.get(url, headers=headers, timeout=20)
        return resp.text
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
    if any(bc in company for bc in BLOCKED_COMPANIES):
        return False

    if any(k in title for k in SECTOR_FREE_ROLES):
        return True

    if any(k in title for k in SECTOR_DEPENDENT_ROLES):
        return any(s in title for s in ALLOWED_SECTORS)

    return True

def send_telegram(message):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.ok:
            print("Telegram error: {}".format(resp.text[:200]))
        return resp.ok
    except Exception as e:
        print("Telegram error: {}".format(e))
        return False

def main():
    seen_jobs = load_seen_jobs()
    new_jobs = []
    seen_keys = set(seen_jobs.keys())

    for query in SEARCH_QUERIES:
        found = 0
        for page in range(PAGES_PER_QUERY):
            html = fetch_jobs(query, start=page * 25)
            jobs = parse_jobs(html)
            if not jobs:
                break
            for job in jobs:
                key = make_dedup_key(job["title"], job["company"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if not is_relevant(job):
                    continue
                new_jobs.append(job)
                found += 1
                seen_jobs[key] = datetime.now(timezone.utc).isoformat()
        print("'{}' → {} new".format(query, found))

    print("\nTotal new: {}".format(len(new_jobs)))
    if not new_jobs:
        save_seen_jobs(seen_jobs)
        return

    IST = timezone(timedelta(hours=5, minutes=30))
    batch_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    for job in new_jobs:
        msg = "<b>[A2] {}</b> | {}\n{}\n{}\n\n{}".format(
            job["title"], job["company"], job["location"], batch_time, job["url"])
        if send_telegram(msg):
            print("Sent: {} @ {}".format(job["title"], job["company"]))

    save_seen_jobs(seen_jobs)
    print("Done.")

if __name__ == "__main__":
    main()
