import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

# ACCOUNT 2 — Strategy, Consulting, Founders Office, Target Companies
GENERAL_QUERIES = [
    "strategy consultant India",
    "management consultant associate India",
    "consulting analyst India",
    "associate consultant India",
    "operations consultant India",
    "founders office India",
    "corporate strategy analyst India",
    "business strategy analyst India",
    "growth manager India",
    "business transformation manager India",
    "operational excellence manager India",
    "process excellence manager India",
    "product strategy manager India",
    "bizops manager India",
    "strategy and operations India",
    "market access manager pharma",
    "product launch manager pharma",
    "zonal sales manager pharma",
    "area sales manager medical",
    "territory manager medical devices",
    "regional sales manager pharma",
    "performance marketing manager FMCG",
    "program manager healthcare",
    "project manager healthcare",
]

COMPANY_QUERIES = [
    "Meril Life Sciences",
    "INOR implants",
    "Biorad medisys",
    "TTK healthcare",
    "Sharma orthopaedics",
    "Matryx meditech",
    "Fortune labs medical",
    "Narang medical",
    "Atlas surgical",
    "Siora surgicals",
    "Maxx medical",
    "Biomed healthcare",
    "Auxein medical",
    "NRV ortho",
]

PAGES_PER_QUERY = 3

INCLUDE_KEYWORDS = [
    "strategy consultant", "strategy analyst", "strategy manager",
    "management consultant", "consulting analyst", "associate consultant",
    "business consultant", "operations consultant",
    "corporate strategy", "business strategy",
    "founders office", "founder's office",
    "bizops", "biz ops", "strategy and operations",
    "business transformation", "transformation manager",
    "operational excellence", "process excellence",
    "growth manager", "growth analyst",
    "product strategy", "product manager", "associate product manager",
    "market access", "product launch manager",
    "zonal sales", "area sales", "territory manager", "regional sales",
    "program manager", "project manager",
    "performance marketing",
    "market research analyst", "market intelligence",
    "commercial excellence",
    "business development manager", "business development",
    "key account manager",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", " sr ", "lead ", "principal", "staff ",
    "vp", "vice president", "director", "head of", "head -",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "deputy general manager", "dgm", "agm",
    "associate director", "associate vp",
    "intern", "internship", "fresher", "trainee",
    "chief of staff",
    "software engineer", "software developer", "developer",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "full-stack", "qa engineer",
    "test engineer", "data engineer", "mlops", "cloud engineer",
    "technical program", "technical project", "it project",
    "accountant", "finance manager", "chartered accountant",
    "radiologist", "doctor", "physician", "nurse", "technician",
    "driver", "field technician", "warehouse", "blue collar",
    "recruiter", "hr manager", "talent acquisition",
    "content writer", "graphic designer", "telecaller",
    "cyber", "cybersecurity", "network", "banking", "insurance",
    "channel sales", "channel partner", "influencer",
    # Slipping through fixes
    "engineer", "quality", "enablement",
    "finance operations", "customer success", "foaa",
    "it operations", "revenue operations", "sales operations engineer",
    "obesity", "oncology", "cardiology", "neurology", "dermatology",
    "therapeutic", "clinical", "medical affairs", "pharmacovigilance",
    "account management", "customer experience", "cx ",
    "global program", "global enablement",
]

INCLUDE_LOCATIONS = [
    "hyderabad", "ahmedabad", "gurugram", "gurgaon",
    "bengaluru", "bangalore", "pune", "mumbai",
    "delhi", "noida", "chennai",
    "remote", "india", "pan india", "work from home",
]

# Roles that MUST have a sector word in the title
SECTOR_DEPENDENT_ROLES = [
    "growth manager", "growth analyst",
    "program manager", "project manager",
    "business analyst", "operations manager", "operations analyst",
    "supply chain", "demand planning",
    "sales manager", "business development",
    "key account manager", "category manager",
    "brand manager", "marketing manager",
    "market research", "commercial",
    "process improvement", "process excellence",
    "performance marketing",
]

# Sector words — at least one must appear in title for sector-dependent roles
ALLOWED_SECTORS = [
    "medtech", "med tech", "medical", "healthcare", "health care",
    "pharma", "pharmaceutical", "diagnostics", "hospital", "clinical",
    "fmcg", "consumer", "food", "beverage", "nutrition",
    "wellness", "beauty", "personal care", "retail",
    "ortho", "surgical", "implant", "device",
]

# These roles pass WITHOUT sector check — inherently cross-sector
SECTOR_FREE_ROLES = [
    "strategy consultant", "management consultant", "consulting analyst",
    "associate consultant", "strategy analyst", "corporate strategy",
    "business strategy", "operations consultant",
    "founders office", "founder's office",
    "bizops", "strategy and operations",
    "business transformation",
    "product manager", "associate product manager", "product analyst",
    "product strategy", "product lead", "product owner",
]


def clean(text):
    text = text or ""
    text = text.replace("&", "and").replace("<", "").replace(">", "")
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
        "?keywords={}&location=India&f_TPR=r7200&f_E=2%2C3%2C4%2C6&start={}"
    ).format(requests.utils.quote(query), start)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.text
    except Exception as e:
        print("Error fetching '{}': {}".format(query, e))
        return ""

def fetch_company_jobs(company):
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        "?keywords={}&location=India&start=0"
    ).format(requests.utils.quote(company))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.text
    except Exception as e:
        print("Error fetching company '{}': {}".format(company, e))
        return ""

def parse_jobs(html):
    jobs = []
    blocks = html.split('<div class="base-card')
    title_re = re.compile(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>\s*([^<]+)\s*</h3>', re.I)
    company_re = re.compile(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>[\s\S]*?<a[^>]*>\s*([^<]+)\s*</a>', re.I)
    location_re = re.compile(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>\s*([^<]+)\s*</span>', re.I)
    url_re = re.compile(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', re.I)

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

    if not any(k in title for k in INCLUDE_KEYWORDS):
        return False
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False
    if not any(l in location for l in INCLUDE_LOCATIONS):
        return False

    # Sector-free roles pass without sector check
    if any(k in title for k in SECTOR_FREE_ROLES):
        return True

    # Sector-dependent roles need a sector word in title
    is_sector_dependent = any(k in title for k in SECTOR_DEPENDENT_ROLES)
    if is_sector_dependent:
        if not any(s in title for s in ALLOWED_SECTORS):
            return False

    return True

def is_relevant_company(job):
    title = job["title"].lower()
    location = job["location"].lower()
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False
    if not any(l in location for l in INCLUDE_LOCATIONS):
        return False
    return True

def send_telegram(message):
    url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            print("Telegram error: {} - {}".format(response.status_code, response.text))
        return response.ok
    except Exception as e:
        print("Telegram error: {}".format(e))
        return False

def main():
    seen_jobs = load_seen_jobs()
    new_jobs = []
    seen_keys = set(seen_jobs.keys())

    for query in GENERAL_QUERIES:
        for page in range(PAGES_PER_QUERY):
            start = page * 25
            print("Fetching: '{}' page {}".format(query, page + 1))
            html = fetch_jobs(query, start=start)
            jobs = parse_jobs(html)
            if not jobs:
                print("  No results, stopping.")
                break
            for job in jobs:
                key = make_dedup_key(job["title"], job["company"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if not is_relevant(job):
                    continue
                new_jobs.append({"job": job, "tag": "LinkedIn"})
                seen_jobs[key] = datetime.now(timezone.utc).isoformat()

    for company in COMPANY_QUERIES:
        print("Fetching company: '{}'".format(company))
        html = fetch_company_jobs(company)
        jobs = parse_jobs(html)
        print("  Found {} results".format(len(jobs)))
        for job in jobs:
            key = make_dedup_key(job["title"], job["company"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if not is_relevant_company(job):
                continue
            new_jobs.append({"job": job, "tag": "Target Company"})
            seen_jobs[key] = datetime.now(timezone.utc).isoformat()

    print("Total new jobs found: {}".format(len(new_jobs)))

    if not new_jobs:
        print("No new matching jobs found.")
        save_seen_jobs(seen_jobs)
        return

    IST = timezone(timedelta(hours=5, minutes=30))
    batch_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    for item in new_jobs:
        job = item["job"]
        tag = item["tag"]
        message = (
            "{} | {} | {}\n"
            "{}\n"
            "{}\n\n"
            "{}"
        ).format(tag, job["title"], job["company"], job["location"], batch_time, job["url"])

        success = send_telegram(message)
        if success:
            print("Sent: {} at {}".format(job["title"], job["company"]))
        else:
            print("Failed: {}".format(job["title"]))

    save_seen_jobs(seen_jobs)
    print("Done.")

if __name__ == "__main__":
    main()
