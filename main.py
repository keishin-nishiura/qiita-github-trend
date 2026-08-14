import requests
import datetime
import os

def fetch_popular_repos(days=7, per_page=15, min_stars=500):
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    query = f"created:>{since} stars:>{min_stars} fork:false"
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
    }
    headers = {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    }
    res = requests.get(url, params=params, headers=headers)
    res.raise_for_status()
    return res.json()["items"]

if __name__ == "__main__":
    repos = fetch_popular_repos()
    repos = [r for r in repos if r["description"]]
    for r in repos:
        print(r["full_name"], r["stargazers_count"], r["language"], "-", r["description"])