import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SEEN_JOBS_FILE = "seen_jobs.json"

SEARCH_QUERIES = [
    "product-manager",
    "associate-product-manager",
    "product-analyst",
    "business-analyst",
    "strategy-analyst",
    "strategy-consultant",
    "management-consultant",
    "gtm-manager",
    "operations-manager",
    "supply-chain-manager",
    "business-development-manager",
    "category-manager",
    "program-manager",
    "chief-of-staff",
    "sales-manager",
    "market-research-analyst",
    "growth-analyst",
    "consulting-analyst",
    "commercial-excellence",
]

INCLUDE_KEYWORDS = [
    "product manager", "associate product manager", "apm",
    "product analyst", "product operations", "product lead",
    "product owner", "strategy analyst", "strategy consultant",
    "strategy manager", "management consultant", "consulting analyst",
    "associate consultant", "business analyst", "sales manager",
    "sales operations", "sales analyst", "business development manager",
    "gtm manager", "go-to-market manager", "marketing manager",
    "brand manager", "category manager", "trade marketing manager",
    "operations manager", "operations analyst", "supply chain manager",
    "supply chain analyst", "demand planning", "process improvement",
    "business operations manager", "chief of staff", "program manager",
    "project manager", "growth analyst", "market research analyst",
    "market intelligence", "commercial excellence", "kpi analyst",
    "business development", "channel sales manager", "corporate strategy",
]

EXCLUDE_KEYWORDS = [
    "senior", "sr.", " sr ", "lead ", "principal", "staff ",
    "vp", "vice president", "director", "head of", "head -",
    "avp", "evp", "svp", "cxo", "ceo", "coo", "cto", "cfo",
    "general manager", "deputy general manager", "dgm", "agm",
    "associate director", "associate vp",
    "intern", "internship", "fresher", "trainee",
    "software engineer", "software developer", "developer",
    "data scientist", "machine learning", "devops", "backend",
    "frontend", "full stack", "full-stack", "qa engineer",
    "test engineer", "data engineer", "mlops", "cloud engineer",
    "accountant", "finance manager", "chartered accountant",
    "radiologist", "doctor", "physician", "nurse", "technician",
    "driver", "field technician", "warehouse", "blue collar",
    "recruiter", "hr manager", "talent acquisition",
    "content writer", "graphic designer", "telecaller",
]

INCLUDE_LOCATIONS = [
    "bengaluru", "bangalore", "hyderabad", "mumbai",
    "delhi", "gurugram", "gurgaon", "noida",
    "remote", "india", "pan india", "work from home",
    "chennai", "pune",
]

def clean(text):
    text = text or ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "and").replace("&lt;", "").replace("&gt;", "")
    text = text.replace("&#39;", "'").replace("&quot;", '"').replace("&", "and")
    return text.strip()

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(seen_jobs, f, indent=2)

def fetch_naukri_jobs(query):
    # Use Naukri's public search URL format
    url = f"https://www.naukri.com/{query}-jobs-in-india"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        print(f"  Status: {response.status_code}, Length: {len(response.text)}")
        return response.text
    except Exception as e:
        print(f"Error fetching Naukri '{query}': {e}")
        return ""

def parse_naukri_html(html):
    jobs = []

    # Extract JSON data embedded in Naukri's page
    json_match = re.search(r'"jobDetails"\s*:\s*(\[[\s\S]*?\])\s*,\s*"[a-z]', html)
    if json_match:
        try:
            job_list = json.loads(json_match.group(1))
            for job in job_list:
                title = clean(job.get("title", ""))
                company = clean(job.get("companyName", "Unknown"))
                location = clean(job.get("placeholders", [{}])[0].get("label", "India") if job.get("placeholders") else "India")
                url = job.get("jdURL", "")
                if url and not url.startswith("http"):
                    url = "https://www.naukri.com" + url
                posted = job.get("footerPlaceholderLabel", "Recently")
                if title and url:
                    jobs.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "posted": clean(str(posted)),
                    })
            return jobs
        except Exception as e:
            print(f"  JSON parse error: {e}")

    # Fallback: regex parse from HTML
    title_re = re.compile(r'title="([^"]+)"[^>]*class="[^"]*title[^"]*"', re.I)
    company_re = re.compile(r'class="[^"]*comp-name[^"]*"[^>]*>([^<]+)<', re.I)
    location_re = re.compile(r'class="[^"]*loc[^"]*"[^>]*>([^<]+)<', re.I)
    url_re = re.compile(r'href="(https://www\.naukri\.com/job-listings[^"]+)"', re.I)

    titles = title_re.findall(html)
    companies = company_re.findall(html)
    locations = location_re.findall(html)
    urls = url_re.findall(html)

    for i, title in enumerate(titles):
        if i >= len(urls):
            break
        jobs.append({
            "title": clean(title),
            "company": clean(companies[i]) if i < len(companies) else "Unknown",
            "location": clean(locations[i]) if i < len(locations) else "India",
            "url": urls[i],
            "posted": "Recently",
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
    return True

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.ok
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def main():
    seen_jobs = load_seen_jobs()
    new_jobs = []
    all_urls = set()

    for query in SEARCH_QUERIES:
        print(f"Fetching Naukri: '{query}'")
        html = fetch_naukri_jobs(query)
        jobs = parse_naukri_html(html)
        print(f"  Parsed {len(jobs)} jobs")

        for job in jobs:
            url = job["url"]
            if url in all_urls:
                continue
            all_urls.add(url)
            if url in seen_jobs:
                continue
            if not is_relevant(job):
                continue
            new_jobs.append(job)
            seen_jobs[url] = datetime.now(timezone.utc).isoformat()

    print(f"Total new jobs found: {len(new_jobs)}")

    if not new_jobs:
        print("No new matching jobs found.")
        save_seen_jobs(seen_jobs)
        return

    IST = timezone(timedelta(hours=5, minutes=30))
    batch_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    for job in new_jobs:
        message = (
            f"New Job Alert - Naukri\n\n"
            f"Found at: {batch_time}\n\n"
            f"Role: {job['title']}\n"
            f"Company: {job['company']}\n"
            f"Location: {job['location']}\n"
            f"Posted: {job['posted']}\n\n"
            f"Apply here: {job['url']}"
        )
        success = send_telegram(message)
        if success:
            print(f"Sent: {job['title']} at {job['company']}")
        else:
            print(f"Failed: {job['title']}")

    save_seen_jobs(seen_jobs)
    print("Done.")

if __name__ == "__main__":
    main()
