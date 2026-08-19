import requests
import datetime
import os
import time
import json
from google import genai

github_headers = {
    "Authorization": f"Bearer {os.environ['GH_SEARCH_TOKEN'].strip()}",
    "Accept": "application/vnd.github+json",
}
gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"].strip())


def fetch_popular_repos(days=7, per_page=15, min_stars=500):
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    query = f"created:>{since} stars:>{min_stars} fork:false"
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    res = requests.get(url, params=params, headers=github_headers)
    res.raise_for_status()
    repos = res.json()["items"]
    return [r for r in repos if r["description"]]


def summarize_all_repos(repos, max_retries=3):
    repo_list_text = "\n".join(
        f"{i+1}. リポジトリ名: {r['full_name']} / 説明: {r['description']}"
        for i, r in enumerate(repos)
    )

    prompt = f"""以下は今週人気だったGitHubリポジトリの一覧です。それぞれについて、日本の読者向けに次の4項目を日本語でまとめてください。

{repo_list_text}

各リポジトリについて、以下のJSON配列形式で出力してください(他の文章は一切含めないこと):

[
  {{
    "full_name": "リポジトリ名",
    "overview": "①どんなツール・プロジェクトか(2〜3文)",
    "why_popular": "②なぜ人気なのか(推測でよい)",
    "merit": "③実務でのメリット",
    "recommended_for": "④どんな人におすすめか"
  }},
  ...
]

※出典の文章をそのまま引用せず、必ず自分の言葉で言い換えること
"""
    for attempt in range(max_retries):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"  JSON解析に失敗しました: {e}")
            return None
        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e):
                print(f"  クォータ上限のため中断します: {e}")
                return None
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  リトライします({attempt + 1}/{max_retries})... {wait}秒待機")
                time.sleep(wait)
            else:
                print(f"  失敗しました: {e}")
                return None


def build_article(repos_with_summary):
    lines = [
        f"直近1週間で新しく作成され、スター数が多かったGitHubリポジトリを{len(repos_with_summary)}件まとめました。",
        "",
    ]

    if len(repos_with_summary) >= 3:
        lines.append("### 🏆 今週のトップ3")
        for i, (repo, _) in enumerate(repos_with_summary[:3], start=1):
            lines.append(f"{i}. [{repo['full_name']}]({repo['html_url']}) (⭐{repo['stargazers_count']:,})")
        lines.append("")

    lines.append("---")
    lines.append("")

    for i, (repo, summary) in enumerate(repos_with_summary, start=1):
        lines.append(f"## {i}位: 📦 {repo['full_name']}")
        lines.append("")
        lines.append(f"| ⭐ Star数 | 言語 |")
        lines.append(f"|---|---|")
        lines.append(f"| {repo['stargazers_count']:,} | {repo['language'] or '-'} |")
        lines.append("")
        lines.append(f"### 概要")
        lines.append(summary['overview'])
        lines.append("")
        lines.append(f"### なぜ人気なのか")
        lines.append(summary['why_popular'])
        lines.append("")
        lines.append(f"### 実務でのメリット")
        lines.append(summary['merit'])
        lines.append("")
        lines.append(f"### どんな人におすすめか")
        lines.append(summary['recommended_for'])
        lines.append("")
        lines.append(repo['html_url'])  # 単独行のURL → Qiitaが自動でリンクカード化
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def build_tags(repos_with_summary):
    fixed_tags = ["GitHub", "GitHubTrending", "AI"]

    languages = {
        repo["language"]
        for repo, _ in repos_with_summary
        if repo["language"]
    }
    # Qiitaのタグ数上限は5個程度が実用的なので、言語タグは上位2つまで
    lang_tags = list(languages)[:2]

    return fixed_tags + lang_tags


def post_to_qiita(title, body, tags, private=True):
    url = "https://qiita.com/api/v2/items"
    headers = {
        "Authorization": f"Bearer {os.environ['QIITA_TOKEN'].strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "body": body,
        "tags": [{"name": t, "versions": []} for t in tags],
        "private": private,
    }
    res = requests.post(url, headers=headers, json=payload)
    res.raise_for_status()
    return res.json()


if __name__ == "__main__":
    repos = fetch_popular_repos()
    print(f"{len(repos)}件のリポジトリを取得しました\n")

    summaries = summarize_all_repos(repos)
    if not summaries:
        print("要約生成に失敗したため終了します")
        exit(1)

    summary_map = {s["full_name"]: s for s in summaries}
    repos_with_summary = [
        (r, summary_map[r["full_name"]]) for r in repos if r["full_name"] in summary_map
    ]

    article = build_article(repos_with_summary)
    with open("article.md", "w", encoding="utf-8") as f:
        f.write(article)

    print(f"\n記事を article.md に書き出しました({len(repos_with_summary)}件分)")

    today = datetime.date.today()
    title = f"{today.strftime('%Y年%m月第%W週')} GitHubで話題になったリポジトリまとめ"
    result = post_to_qiita(
        title=title,
        body=article,
        tags=build_tags(repos_with_summary),
        private=True,  # 自動投稿は常に限定共有。公開は確認後に手動で切り替える
    )
    print(f"Qiitaに投稿しました(下書き): {result['url']}")
