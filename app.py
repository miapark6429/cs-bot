from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL")

def get_notion_text():
    url = f"https://api.notion.com/v1/blocks/{NOTION_PAGE_ID}/children"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
    }
    res = requests.get(url, headers=headers).json()
    texts = []
    for block in res.get("results", []):
        block_type = block.get("type")
        rich = block.get(block_type, {}).get("rich_text", [])
        for r in rich:
            t = r.get("plain_text", "")
            if t:
                texts.append(t)
    return "\n".join(texts)

def get_claude_reply(question, knowledge):
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "system": f"당신은 B2B SaaS 서비스의 CS 전담 상담사입니다. 고객은 기업의 실무 담당자입니다. 정중하고 격식있게 답변하세요. 150자 내외로 간결하게 작성하세요. 모르는 내용은 추측하지 마세요. 가격과 계약조건은 담당자 연결로 안내하세요. 답변 본문만 출력하세요.\n\n[참고 지식베이스]\n{knowledge}",
        "messages": [{"role": "user", "content": question}]
    }
    res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
    data = res.json()
    print("Claude response:", data)
    if "content" not in data:
        return f"AI 답변 생성 실패: {data.get('error', {}).get('message', '알 수 없는 오류')}"
    return data["content"][0]["text"]

def send_slack(name, email, company, question, reply):
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    text = f"""*📬 새 문의가 접수되었습니다*

*이름:* {name}
*이메일:* {email}
*회사명:* {company}

*문의 내용*
{question}

*🤖 AI 답변 초안*
{reply}"""
    body = {"channel": SLACK_CHANNEL, "text": text}
    requests.post("https://slack.com/api/chat.postMessage", headers=headers, json=body)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    entity = data.get("entity", {})
    refers = data.get("refers", {})
    user = refers.get("user", {})

    question = entity.get("plainText", "")
    name = user.get("name", "")
    email = user.get("email", "")
    company = user.get("profile", {}).get("companyName", "")

    if not question:
        return jsonify({"ok": True})

    knowledge = get_notion_text()
    reply = get_claude_reply(question, knowledge)
    send_slack(name, email, company, question, reply)

    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
