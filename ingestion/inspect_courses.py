
import requests
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

URL = "https://classes.usc.edu/home"
USER_AGENT = "USCAdvisorAI-StudentResearch/0.1"

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# Check automated access rules
parsed = urlparse(URL)
robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

try:
    response = session.get(robots_url, timeout=20)

    print("Robots.txt HTTP status:", response.status_code)

    if response.status_code == 404:
        print("No robots.txt file found at this URL.")
        print("Automated collection permission is not established.")
        print("Stopping before collecting course data.")
        raise SystemExit

    response.raise_for_status()

    robots = RobotFileParser()
    robots.parse(response.text.splitlines())

    allowed = robots.can_fetch(USER_AGENT, URL)

    print("Robots URL:", robots_url)
    print("Automated access allowed:", allowed)
    print("Crawl delay:", robots.crawl_delay(USER_AGENT))

    if not allowed:
        print("Stopping: automated collection is not allowed.")
        raise SystemExit

except requests.RequestException as error:
    print("Could not verify access rules:", error)
    raise SystemExit

# Inspect public HTML
response = session.get(URL, timeout=30)
print("\nHTTP status:", response.status_code)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

print("Page title:", soup.title.get_text(strip=True)
      if soup.title else "Not found")

print("\nFirst 1500 characters:")
print(soup.get_text(" ", strip=True)[:1500])

print("\nJavaScript files:")
for script in soup.find_all("script", src=True):
    print(script["src"])
