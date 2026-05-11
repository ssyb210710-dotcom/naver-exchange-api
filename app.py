import re
from datetime import datetime
from flask_cors import CORS

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

URL_MAIN = "https://finance.naver.com/marketindex/"
URL_USD = "https://finance.naver.com/marketindex/exchangeDetail.naver?marketindexCd=FX_USDKRW"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def parse_number(text):
    cleaned = re.sub(r"[^0-9.]", "", text or "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def text_of(node):
    return node.get_text(" ", strip=True) if node else ""


def fetch_base_rate():
    response = requests.get(URL_MAIN, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for item in soup.select("div.market1 ul.data_lst li"):
        name_tag = item.select_one("h3.h_lst")
        value_tag = item.select_one("span.value")
        if not name_tag or not value_tag:
            continue

        name = text_of(name_tag)
        value = parse_number(text_of(value_tag))
        upper_name = name.upper().replace(" ", "")

        if value is not None and "USD" in upper_name:
            return value

    raise RuntimeError("USD 매매기준율을 찾지 못했습니다.")


def fetch_detail_rates():
    response = requests.get(URL_USD, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    page_text = soup.get_text("\n", strip=True)

    # 기본값
    cash_buy_rate = None
    cash_sell_rate = None
    remittance_send_rate = None
    remittance_receive_rate = None

    patterns = {
        "cash_buy_rate": r"현찰\s*사실\s*때\s*([0-9,]+\.\d+|[0-9,]+)",
        "cash_sell_rate": r"현찰\s*파실\s*때\s*([0-9,]+\.\d+|[0-9,]+)",
        "remittance_send_rate": r"송금\s*보내실\s*때\s*([0-9,]+\.\d+|[0-9,]+)",
        "remittance_receive_rate": r"송금\s*받으실\s*때\s*([0-9,]+\.\d+|[0-9,]+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, page_text)
        if match:
            value = parse_number(match.group(1))
            if key == "cash_buy_rate":
                cash_buy_rate = value
            elif key == "cash_sell_rate":
                cash_sell_rate = value
            elif key == "remittance_send_rate":
                remittance_send_rate = value
            elif key == "remittance_receive_rate":
                remittance_receive_rate = value

    return {
        "cash_buy_rate": cash_buy_rate,
        "cash_sell_rate": cash_sell_rate,
        "remittance_send_rate": remittance_send_rate,
        "remittance_receive_rate": remittance_receive_rate,
    }


@app.route("/")
def home():
    return "Exchange API is running"


@app.route("/ping")
def ping():
    return "pong"


@app.route("/api/rate")
def api_rate():
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        base_rate = fetch_base_rate()
        details = fetch_detail_rates()

        result = {
            "base_rate": base_rate,
            "cash_buy_rate": details["cash_buy_rate"] if details["cash_buy_rate"] is not None else base_rate,
            "cash_sell_rate": details["cash_sell_rate"] if details["cash_sell_rate"] is not None else base_rate,
            "remittance_send_rate": details["remittance_send_rate"],
            "remittance_receive_rate": details["remittance_receive_rate"],
            "updated_at": updated_at,
            "status": "ok",
            "source": "naver"
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "base_rate": None,
            "cash_buy_rate": None,
            "cash_sell_rate": None,
            "remittance_send_rate": None,
            "remittance_receive_rate": None,
            "updated_at": updated_at,
            "status": "error",
            "source": "naver",
            "message": str(e)
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)