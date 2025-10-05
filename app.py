from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv
import datetime, re, os, json, logging

# === .env 読み込み ===
load_dotenv()

# === Slack / Google 設定 ===
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "officialteam@chaospalette.com")

app = App(token=SLACK_BOT_TOKEN)
logging.basicConfig(level=logging.INFO)

# === Google Calendar 認証 ===
if os.getenv("GOOGLE_TOKEN_JSON"):
    # Renderなど環境変数から直接読み込み
    creds = Credentials.from_authorized_user_info(
        json.loads(os.getenv("GOOGLE_TOKEN_JSON")),
        ["https://www.googleapis.com/auth/calendar"]
    )
else:
    # ローカルでのtoken.json利用
    creds = Credentials.from_authorized_user_file(
        os.getenv("GOOGLE_TOKEN_FILE", "token.json"),
        ["https://www.googleapis.com/auth/calendar"]
    )

service = build("calendar", "v3", credentials=creds)

# === ユーザーごとの色設定 ===
USER_COLORS = {
    "U09K6QUEP0R": ("1", "[青]"),
    "U09K6QPLZEV": ("5", "[黄]"),
    "U09JM6U4RNF": ("4", "[赤]"),
    "U09K4EMTX17": ("2", "[緑]"),
}

# === シフト形式の抽出 ===
def parse_shifts(text):
    pattern = r"(\d{1,2})/(\d{1,2}).*?(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})"
    matches = re.findall(pattern, text)
    events = []
    current_year = datetime.datetime.now().year
    for m in matches:
        month, day, sh, sm, eh, em = map(int, m)
        start = datetime.datetime(current_year, month, day, sh, sm)
        end = datetime.datetime(current_year, month, day, eh, em)
        events.append((start, end))
    return events


# === メッセージ処理 ===
@app.event("message")
def handle_message(event, say):
    text = event.get("text", "")
    sender_id = event.get("user", "")
    logging.info(f"受信メッセージ: {text} from {sender_id}")

    # @ユーザー指定（登録対象）を検出
    mention_match = re.search(r"<@([A-Z0-9]+)>", text)
    target_user_id = mention_match.group(1) if mention_match else sender_id

    # Slackの表示名を取得
    try:
        info = app.client.users_info(user=target_user_id)
        display_name = info["user"]["profile"].get("display_name") or info["user"]["real_name"]
    except Exception:
        display_name = f"User_{target_user_id}"

    # === 削除コマンド ===
    if "削除" in text:
        delete_matches = re.findall(r"(\d{1,2})/(\d{1,2})", text)
        if not delete_matches:
            say(f"<@{sender_id}> 削除する日付が見つかりませんでした。")
            return

        current_year = datetime.datetime.now().year
        total_deleted = 0

        for month, day in delete_matches:
            month, day = int(month), int(day)
            start_day = datetime.datetime(current_year, month, day, 0, 0)
            end_day = start_day + datetime.timedelta(days=1)

            events_result = service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=start_day.isoformat() + "Z",
                timeMax=end_day.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            events = events_result.get("items", [])
            for e in events:
                summary = e.get("summary", "")
                if display_name in summary:
                    service.events().delete(calendarId=CALENDAR_ID, eventId=e["id"]).execute()
                    total_deleted += 1
                    logging.info(f"削除: {summary}")

        if total_deleted > 0:
            say(f"<@{sender_id}> さん、{display_name} さんの予定を {total_deleted} 件削除しました。")
        else:
            say(f"<@{sender_id}> さん、{display_name} さんの削除対象の予定は見つかりませんでした。")
        return

    # === 通常登録 ===
    shifts = parse_shifts(text)
    if not shifts:
        say(f"<@{sender_id}> シフト形式を確認できませんでした。")
        return

    color_id, label = USER_COLORS.get(target_user_id, ("1", "[青]"))
    for start, end in shifts:
        event_body = {
            "summary": f"シフト（{display_name}）",
            "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": end.isoformat(), "timeZone": "Asia/Tokyo"},
            "colorId": color_id,
            "description": f"Slack連携Bot登録 colorId={color_id}",
        }
        event = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
        logging.info(f"登録完了: {event.get('summary')} color={color_id}")

    say(f"<@{sender_id}> さん、{display_name} さんのシフトを {len(shifts)} 件 登録しました。")


# === メイン起動 ===
if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
