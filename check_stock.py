
import csv
import json
import os
import re
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ==========================================
# 設定
# ==========================================

PRODUCTS = [
    {
        "id": "0016903011",
        "name": "BOOKOFF監視商品1",
        "url": "https://shopping.bookoff.co.jp/used/0016903011",
    },
    {
        "id": "0010470946",
        "name": "BOOKOFF監視商品2",
        "url": "https://shopping.bookoff.co.jp/used/0010470946",
    },
    # 商品を追加する場合は、下のように追記
    # {
    #     "id": "0012345678",
    #     "name": "BOOKOFF監視商品2",
    #     "url": "https://shopping.bookoff.co.jp/used/0012345678",
    # },
]

STATUS_FILE = Path("status.json")
REQUEST_INTERVAL_SECONDS = 5

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_PASS"]
TO_EMAIL = os.environ["TO_EMAIL"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockMonitor/1.0)"
}

# ==========================================
# 状態ファイル
# ==========================================

def load_status():
    if not STATUS_FILE.exists():
        return {}

    try:
        with STATUS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        raise RuntimeError(
            "status.jsonを読み込めません。"
            "状態を初期化せず、内容を確認してください。"
        )


def save_status(status):
    temp_file = STATUS_FILE.with_suffix(".tmp")

    with temp_file.open("w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    temp_file.replace(STATUS_FILE)


# ==========================================
# 在庫判定
# ==========================================

def detect_stock(html):
    """
    戻り値:
      instock      : 購入可能と判断
      out_of_stock : 在庫なしと判断
      unknown      : 判定不能

    注意:
    以下のキーワードは仮の例です。
    実際の商品ページのHTMLに合わせて調整してください。
    """
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    # 在庫なしを先に判定
    sold_out_patterns = [
        "在庫なし",
        "在庫がありません",
        "入荷お知らせメール",
        "入荷お知らせを受け取る",
    ]

    if any(pattern in text for pattern in sold_out_patterns):
        return "out_of_stock"

    # 購入可能の候補キーワード
    in_stock_patterns = [
        "カートに入れる",
        "買い物かごに入れる",
    ]

    if any(pattern in text for pattern in in_stock_patterns):
        return "instock"

    return "unknown"


def check_product(product):
    try:
        response = requests.get(
            product["url"],
            headers=HEADERS,
            timeout=25,
        )

        if response.status_code in (403, 429):
            print(
                f'{product["name"]}: アクセス制限 '
                f'HTTP {response.status_code}'
            )
            return "unknown"

        response.raise_for_status()

        # HTTPエラーがなくても、想定外のページは要確認
        if "shopping.bookoff.co.jp" not in response.url:
            print(f'{product["name"]}: 想定外のURLに転送されました')
            return "unknown"

        status = detect_stock(response.text)

        print(f'{product["name"]}: {status}')
        return status

    except requests.RequestException as e:
        print(f'{product["name"]}: 取得エラー: {e}')
        return "unknown"


# ==========================================
# メール通知
# ==========================================

def send_mail(products):
    if not products:
        return

    msg = EmailMessage()
    msg["Subject"] = f"【BOOKOFF入荷通知】{len(products)}商品"
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    lines = [
        "BOOKOFF ONLINEで購入可能になった可能性のある商品があります。",
        "",
    ]

    for product in products:
        lines.extend([
            f'商品名: {product["name"]}',
            f'商品ID: {product["id"]}',
            f'商品URL: {product["url"]}',
            "",
        ])

    lines.extend([
        "在庫状況は変化する可能性があります。",
        "商品ページを開き、購入可能か確認してください。",
    ])

    msg.set_content("\n".join(lines))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(msg)

    print(f"{len(products)}商品についてメール通知しました。")


# ==========================================
# メイン処理
# ==========================================

def main():
    previous_status = load_status()
    updated_status = dict(previous_status)

    notifications = []

    for product in PRODUCTS:
        product_id = product["id"]
        old = previous_status.get(product_id)
        current = check_product(product)

        # 判定不能なら前回の状態を保持する
        if current == "unknown":
            print("状態を変更せず、次回に再確認します。")
            time.sleep(REQUEST_INTERVAL_SECONDS)
            continue

        # 初回は基準状態を記録するだけ。通知しない
        if old not in ("instock", "out_of_stock"):
            print("初回の状態を記録します。")
            updated_status[product_id] = current

        else:
            # 在庫なし → 購入可能になったときだけ通知
            if old == "out_of_stock" and current == "instock":
                notifications.append(product)

            updated_status[product_id] = current

        time.sleep(REQUEST_INTERVAL_SECONDS)

    # メール送信が失敗した場合に通知状態を先に保存しない
    send_mail(notifications)

    # 在庫状態をファイルへ保存
    save_status(updated_status)


if __name__ == "__main__":
    main()
