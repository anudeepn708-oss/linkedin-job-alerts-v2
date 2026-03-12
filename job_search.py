import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")
SEEN_JOBS_FILE = "seen_jobs.json"

# Sector-specific queries — role always paired with sector
SEARCH_QUERIES = [
    "product manager healthcare",
    "product manager medical devices",
    "product manager FMCG",
    "product manager pharma",
    "business analyst healthcare",
    "business analyst FMCG",
    "strategy consultant",
    "management consultant",
    "consulting analyst",
    "operations consultant",
    "strategy analyst",
    "corporate strategy",
    "founders office",
    "operations manager healthcare",
    "operations manager FMCG",
    "supply chain manager FMCG",
    "category manager FMCG",
    "sales manager healthcare",
    "sales manager medical devices",
    "brand manager FMCG",
    "market research analyst FMCG",
    "growth analyst",
    "business development manager healthcare",
    "business development manager pharma",
]

# Role must contain one of these
INCLUDE_ROLES = [
    "product manager", "associate product manager", "apm",
    "product analyst", "product lead", "product owner",
    "business analyst", "strategy analyst", "strategy consultant",
    "strategy manager", "management consultant", "consulting analyst",
    "associate consultant", "operations consultant",
    "operations manager", "operations analyst",
    "supply chain manager", "supply chain analyst",
    "demand planning", "category manager",
    "sales manager", "sales analyst",
    "brand manager", "trade marketing",
    "business development manager",
    "market research analyst", "market intelligence",
    "growth analyst", "corporate strategy",
    "founders office", "founder's office",
    "program manager", "project manager",
    "process improvement", "commercial excellence",
]

# Sectors — job title must contain at least one
# EXCEPT for pure strategy/consulting roles which pass without sector check
STRATEGY_ROLES = [
    "strategy consultant", "management consultant", "consulting analyst",
    "associate consultant", "strategy analyst", "corporate strategy",
    "operations consultant", "founders office", "founder's office",
    "growth analyst",
]

ALLOWED_SECTORS = [
    "healthcare", "health care", "medical", "medtech", "med tech",
    "pharma", "pharmaceutical", "diagnostics", "hospital", "clinical",
    "fmcg", "consumer goods", "consumer product", "food", "beverage",
    "retail", "nutrition", "wellness", "beauty", "personal care",
]

# Hard excludes — never pass regardless
EXCLUDE_KEYWORDS = [
    "senior", "sr.", " sr ", "lead ", "principal",
    "vp", "vice president", "director", "head of",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "dgm", "agm",
    "associate director", "associate vp",
    "intern", "internship", "fresher", "trainee",
    "software engineer", "software developer", "developer",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "qa engineer", "test engineer",
    "data engineer", "cloud engineer", "it ", "information technology",
    "technical program", "technical project", "it project",
    "application manager", "erp", "sap", "crm developer",
    "accountant", "finance manager", "chartered accountant",
    "radiologist", "doctor", "physician", "nurse", "technician",
    "driver", "field technician", "warehouse",
    "recruiter", "hr manager", "talent acquisition",
    "content writer", "graphic designer", "telecaller",
    "cyber", "cybersecurity", "network engineer",
    "banking", "insurance", "mortgage", "loan",
    "chief of staff",
    "channel sales", "channel partner",
    "influencer", "social media",
]

def clean(text):
    text = text or ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "and").replace("&lt;", "").replace("&gt;", "")
    text = text.replace("&", "and").replace("|", "-").replace("#", "")
    text = text.encode('ascii', 'ignore').decode('ascii')
    return text.strip()

def make_dedup_key(title, company):
    t = re.sub(r'[^a-z0-9]', '', title.lower())
    c = re.sub(r'[^a-z0-9]', '', company.lower())
    return "{}__{}".format(t[:40], c[:20])

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)

def fetch_adzuna_jobs(query, page=1):
    url = "https://api.adzuna.com/v1/api/jobs/in/search/{}".format(page)
    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "what": query,
        "where": "India",
        "results_per_page": 50,
        "max_days_old": 1,
        "sort_by": "date",
        "content-type": "application/json",
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        return response.json()
    except Exception as e:
        print("Error fetching Adzuna '{}': {}".format(query, e))
        return {}

def parse_adzuna_jobs(data):
    jobs = []
    try:
        for job in data.get("results", []):
            title = clean(job.get("title", ""))
            company = clean(job.get("company", {}).get("display_name", "Unknown"))
            location = clean(job.get("location", {}).get("display_name", "India"))
            url = job.get("redirect_url", "")
            created = job.get("created", "")
            category = clean(job.get("category", {}).get("label", ""))
            try:
                dt = datetime.strptime(created[:10], "%Y-%m-%d")
                posted = dt.strftime("%d %b %Y")
            except Exception:
                posted = "Recently"
            if not title or not url:
                continue
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "posted": posted,
                "category": category,
            })
    except Exception as e:
        print("Parse error: {}".format(e))
    return jobs

def is_relevant(job):
    title = job["title"].lower()
    category = job.get("category", "").lower()
    combined = title + " " + category

    # Hard excludes first
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False

    # Must match a role
    has_role = any(k in title for k in INCLUDE_ROLES)
    if not has_role:
        return False

    # Pure strategy/consulting roles pass without sector check
    is_strategy = any(k in title for k in STRATEGY_ROLES)
    if is_strategy:
        return True

    # All other roles need a sector match
    has_sector = any(s in combined for s in ALLOWED_SECTORS)
    if not has_sector:
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

    for query in SEARCH_QUERIES:
        print("Fetching Adzuna: '{}'".format(query))
        data = fetch_adzuna_jobs(query)
        total = data.get("count", 0)
        jobs = parse_adzuna_jobs(data)
        print("  Total available: {}, Fetched: {}".format(total, len(jobs)))

        for job in jobs:
            dedup_key = make_dedup_key(job["title"], job["company"])
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            if not is_relevant(job):
                continue
            new_jobs.append(job)
            seen_jobs[dedup_key] = datetime.now(timezone.utc).isoformat()

    print("Total new jobs found: {}".format(len(new_jobs)))

    if not new_jobs:
        print("No new matching jobs found.")
        save_seen_jobs(seen_jobs)
        return

    IST = timezone(timedelta(hours=5, minutes=30))
    batch_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    for job in new_jobs:
        message = (
            "New Job Alert - Adzuna\n\n"
            "Found at: {}\n\n"
            "Role: {}\n"
            "Company: {}\n"
            "Location: {}\n"
            "Posted: {}\n\n"
            "Apply here: {}"
        ).format(batch_time, job["title"], job["company"], job["location"], job["posted"], job["url"])

        success = send_telegram(message)
        if success:
            print("Sent: {} at {}".format(job["title"], job["company"]))
        else:
            print("Failed: {}".format(job["title"]))

    save_seen_jobs(seen_jobs)
    print("Done.")

if __name__ == "__main__":
    main()
