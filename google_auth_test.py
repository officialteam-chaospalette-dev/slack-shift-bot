from __future__ import print_function
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 認証スコープ：カレンダーの読み書き
SCOPES = ['https://www.googleapis.com/auth/calendar']

def main():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # トークンがない or 無効ならブラウザ認証を実行
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # トークンを保存
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    # 登録済みカレンダー一覧を取得
    results = service.calendarList().list().execute()
    calendars = results.get('items', [])

    print("=== 利用可能なカレンダー ===")
    for cal in calendars:
        print(f"- {cal['summary']} ({cal['id']})")

if __name__ == '__main__':
    main()
