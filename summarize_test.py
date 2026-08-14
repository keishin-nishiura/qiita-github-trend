import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

repo_name = "guillaumemeyer/watermarks-remover"
description = "Strip multi-vendor AI provenance marks: Unicode text hygiene, statistical rewrite hooks, and C2PA/metadata from PNG/JPEG/SVG/PDF/DOCX/HTML/MD"

prompt = f"""以下のGitHubリポジトリ情報から、日本の読者向けに次の3項目を日本語でまとめてください。

リポジトリ名: {repo_name}
説明: {description}

①なぜ人気なのか(推測でよい)
②実務でのメリット
③どんな人におすすめか

※出典の文章をそのまま引用せず、必ず自分の言葉で言い換えること
"""

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=prompt,
)

print(response.text)