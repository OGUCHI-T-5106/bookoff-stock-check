import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText

URL = "https://shopping.bookoff.co.jp/used/0016903011"
URL = "https://shopping.bookoff.co.jp/used/0019201603"

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_PASS = os.environ["GMAIL_PASS"]
TO_EMAIL = os.environ["TO_EMAIL"]


def send_mail():
    msg = MIMEText(
        f"BOOKOFFの商品が入荷しました。\n\n{URL}",
        "plain",
        "utf-8"
    )

    msg["Subject"] = "【BOOKOFF】入荷通知"
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_PASS)
        smtp.send_message(msg)


headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/136.0 Safari/537.36"
    )
}

response = requests.get(URL, headers=headers, timeout=30)
response.raise_for_status()

html = response.text
soup = BeautifulSoup(html, "html.parser")

text = soup.get_text()

# BOOKOFFの商品ページでは「在庫あり」が表示される
if "在庫あり" in text:
    send_mail()
    print("在庫あり。メール送信しました。")
else:
    print("在庫なし")
