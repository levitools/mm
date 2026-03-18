#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import datetime
import logging
from flask import Flask, request
import threading
import time
import requests

# Tắt log
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.ERROR)

# Token bot - lấy từ biến môi trường
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# URL Telegram API
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Lưu dữ liệu tạm thời
user_data = {}
user_states = {}

# Flask app cho web server
app = Flask(__name__)

def format_currency(amount):
    """Định dạng tiền tệ"""
    return f"{amount:,.0f}₫".replace(",", ".")

def calculate_revenue(data):
    """Tính doanh thu theo cấu trúc Linh Trang"""
    
    # Doanh thu từng loại
    rev_1800 = data['ve_1800'] * 1800 * 1000
    rev_800 = data['ve_800'] * 800 * 1000
    rev_700 = data['ve_700'] * 700 * 1000
    rev_800nv = data['ve_800nv'] * 800 * 1000
    rev_700nv = data['ve_700nv'] * 700 * 1000
    
    # Tiền gốc từng loại
    goc_1800 = data['ve_1800'] * 1000 * 1000
    goc_800 = data['ve_800'] * 400 * 1000
    goc_700 = data['ve_700'] * 300 * 1000
    goc_800nv = data['ve_800nv'] * 400 * 1000
    goc_700nv = data['ve_700nv'] * 300 * 1000
    
    # Tiền ngọn từng loại (vé NV trừ 100k)
    ngon_1800 = rev_1800 - goc_1800
    ngon_800 = rev_800 - goc_800
    ngon_700 = rev_700 - goc_700
    ngon_800nv = rev_800nv - goc_800nv - (data['ve_800nv'] * 100 * 1000)
    ngon_700nv = rev_700nv - goc_700nv - (data['ve_700nv'] * 100 * 1000)
    
    # Tổng hợp
    total_ve = (data['ve_1800'] + data['ve_800'] + data['ve_700'] + 
                data['ve_800nv'] + data['ve_700nv'])
    
    total_revenue = rev_1800 + rev_800 + rev_700 + rev_800nv + rev_700nv
    total_goc = goc_1800 + goc_800 + goc_700 + goc_800nv + goc_700nv
    total_ngon = total_revenue - total_goc - (data['ve_800nv'] + data['ve_700nv']) * 100 * 1000
    
    return {
        'total_ve': total_ve,
        'total_revenue': total_revenue,
        'total_goc': total_goc,
        'total_ngon': total_ngon,
        'rev_1800': rev_1800, 'rev_800': rev_800, 'rev_700': rev_700,
        'rev_800nv': rev_800nv, 'rev_700nv': rev_700nv,
        'ngon_1800': ngon_1800, 'ngon_800': ngon_800, 'ngon_700': ngon_700,
        'ngon_800nv': ngon_800nv, 'ngon_700nv': ngon_700nv
    }

def format_output(data, calc, date_str):
    """Format kết quả đầu ra"""
    lines = []
    
    if data['ve_1800'] > 0:
        lines.append(f"• {data['ve_1800']} vé 1800 × 1.800k = {format_currency(calc['rev_1800'])} (ngọn {format_currency(calc['ngon_1800'])})")
    if data['ve_800'] > 0:
        lines.append(f"• {data['ve_800']} vé 800 × 800k = {format_currency(calc['rev_800'])} (ngọn {format_currency(calc['ngon_800'])})")
    if data['ve_700'] > 0:
        lines.append(f"• {data['ve_700']} vé 700 × 700k = {format_currency(calc['rev_700'])} (ngọn {format_currency(calc['ngon_700'])})")
    if data['ve_800nv'] > 0:
        lines.append(f"• {data['ve_800nv']} vé 800 NV × 800k = {format_currency(calc['rev_800nv'])} (ngọn {format_currency(calc['ngon_800nv'])} - trừ 100k/vé)")
    if data['ve_700nv'] > 0:
        lines.append(f"• {data['ve_700nv']} vé 700 NV × 700k = {format_currency(calc['rev_700nv'])} (ngọn {format_currency(calc['ngon_700nv'])} - trừ 100k/vé)")
    
    header = f"📊 *BÁO CÁO DOANH THU KS LINH TRANG{' ' + date_str if date_str else ''}*\n\n"
    body = "\n".join(lines)
    
    summary = f"""
📌 *TỔNG KẾT:*
• Tổng số vé: {calc['total_ve']} vé
• Tổng doanh thu: {format_currency(calc['total_revenue'])}
• Tổng tiền gốc: {format_currency(calc['total_goc'])}
• Tổng tiền ngọn NV: {format_currency(calc['total_ngon'])}"""

    return header + body + summary

def parse_input(text):
    """Parse dữ liệu từ text input"""
    parts = text.split()
    date_match = re.search(r'(\d{1,2}/\d{1,4})', text)
    date = date_match.group(1) if date_match else ""
    
    ve_1800 = ve_800 = ve_700 = ve_800nv = ve_700nv = 0
    
    combined = " ".join(parts).lower()
    
    match_1800 = re.search(r'(\d+)\s*1800', combined)
    if match_1800:
        ve_1800 = int(match_1800.group(1))
    
    match_800 = re.search(r'(\d+)\s*800(?!nv)', combined)
    if match_800:
        ve_800 = int(match_800.group(1))
    
    match_700 = re.search(r'(\d+)\s*700(?!nv)', combined)
    if match_700:
        ve_700 = int(match_700.group(1))
    
    match_800nv = re.search(r'(\d+)\s*800nv', combined)
    if match_800nv:
        ve_800nv = int(match_800nv.group(1))
    
    match_700nv = re.search(r'(\d+)\s*700nv', combined)
    if match_700nv:
        ve_700nv = int(match_700nv.group(1))
    
    return {
        'date': date,
        've_1800': ve_1800,
        've_800': ve_800,
        've_700': ve_700,
        've_800nv': ve_800nv,
        've_700nv': ve_700nv
    }

def send_message(chat_id, text, parse_mode=None, keyboard=None):
    """Gửi tin nhắn đến user"""
    url = f"{TELEGRAM_API}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    
    try:
        requests.post(url, json=data)
    except:
        pass

def edit_message(chat_id, message_id, text, keyboard=None):
    """Sửa tin nhắn"""
    url = f"{TELEGRAM_API}/editMessageText"
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text
    }
    if keyboard:
        data["reply_markup"] = {"inline_keyboard": keyboard}
    
    try:
        requests.post(url, json=data)
    except:
        pass

def handle_update(update):
    """Xử lý update từ Telegram"""
    # Xử lý message
    if 'message' in update:
        msg = update['message']
        chat_id = msg['chat']['id']
        text = msg.get('text', '')
        
        # Kiểm tra nếu đang chờ input từ button
        if chat_id in user_states and user_states[chat_id].get('waiting'):
            handle_button_input(chat_id, text)
            return
        
        if text.startswith('/start'):
            keyboard = [[[{"text": "🚀 NHẬP LIỆU NHANH", "callback_data": "quick_menu"}]]]
            send_message(chat_id, 
                "🏨 *BOT TÍNH DOANH THU KS LINH TRANG* 🏨\n\n"
                "*CẤU TRÚC GIÁ:*\n"
                "• Vé 1800: 1.800k (gốc 1.000k, ngọn 800k)\n"
                "• Vé 800: 800k (gốc 400k, ngọn 400k)\n"
                "• Vé 700: 700k (gốc 300k, ngọn 400k)\n"
                "• Vé 800 NV: 800k (gốc 400k, ngọn 300k - trừ 100k)\n"
                "• Vé 700 NV: 700k (gốc 300k, ngọn 300k - trừ 100k)\n\n"
                "*CÁCH NHẬP:*\n"
                "`15/3 5 1800 10 800 8 700 3 800nv 2 700nv`\n"
                "hoặc nhấn nút bên dưới!",
                parse_mode='Markdown',
                keyboard=keyboard
            )
        elif text.startswith('/nhanh'):
            show_quick_menu(chat_id)
        else:
            # Parse và tính toán
            data = parse_input(text)
            
            if (data['ve_1800'] == 0 and data['ve_800'] == 0 and data['ve_700'] == 0 and 
                data['ve_800nv'] == 0 and data['ve_700nv'] == 0):
                send_message(chat_id, 
                    "❌ Không tìm thấy dữ liệu vé!\n"
                    "VD: `15/3 5 1800 10 800 8 700 3 800nv 2 700nv`",
                    parse_mode='Markdown'
                )
                return
            
            calc = calculate_revenue(data)
            output = format_output(data, calc, data['date'])
            send_message(chat_id, output, parse_mode='Markdown')
    
    # Xử lý callback query (khi nhấn button)
    elif 'callback_query' in update:
        query = update['callback_query']
        chat_id = query['message']['chat']['id']
        message_id = query['message']['message_id']
        data = query['data']
        
        if data == "quick_menu":
            show_quick_menu(chat_id, message_id)
        
        elif data.startswith("add_"):
            loai = data.replace("add_", "")
            ten_loai = {
                '1800': 'vé 1800 (1.800k)',
                '800': 'vé 800 (800k)',
                '700': 'vé 700 (700k)',
                '800nv': 'vé 800 NV (800k - trừ 100k)',
                '700nv': 'vé 700 NV (700k - trừ 100k)'
            }
            edit_message(chat_id, message_id, f"🔢 Nhập số lượng {ten_loai[loai]}:")
            user_states[chat_id] = {'waiting': loai}
        
        elif data == "calculate":
            if chat_id not in user_data or not user_data[chat_id]:
                edit_message(chat_id, message_id, "❌ Chưa nhập vé nào!")
                return
            
            calc = calculate_revenue(user_data[chat_id])
            output = format_output(user_data[chat_id], calc, user_data[chat_id].get('date', ''))
            edit_message(chat_id, message_id, output, parse_mode='Markdown')
            user_data[chat_id] = {}
        
        elif data == "reset":
            user_data[chat_id] = {}
            user_states[chat_id] = {}
            show_quick_menu(chat_id, message_id)
        
        elif data == "back":
            user_states[chat_id] = {}
            show_quick_menu(chat_id, message_id)

def show_quick_menu(chat_id, message_id=None):
    """Hiển thị menu nhập liệu nhanh"""
    if chat_id not in user_data:
        user_data[chat_id] = {
            'date': datetime.datetime.now().strftime("%d/%m/%Y"),
            've_1800': 0, 've_800': 0, 've_700': 0,
            've_800nv': 0, 've_700nv': 0
        }
    
    current = user_data[chat_id]
    total_ve = current['ve_1800'] + current['ve_800'] + current['ve_700'] + current['ve_800nv'] + current['ve_700nv']
    
    keyboard = [
        [[{"text": f"📅 Ngày: {current['date']}", "callback_data": "set_date"}]],
        [
            {"text": f"🔹 1800: {current['ve_1800']}", "callback_data": "add_1800"},
            {"text": f"🔸 800: {current['ve_800']}", "callback_data": "add_800"}
        ],
        [
            {"text": f"🔹 700: {current['ve_700']}", "callback_data": "add_700"},
            {"text": f"🔸 800NV: {current['ve_800nv']}", "callback_data": "add_800nv"}
        ],
        [{"text": f"🔹 700NV: {current['ve_700nv']}", "callback_data": "add_700nv"}],
        [
            {"text": "🧮 TÍNH TOÁN", "callback_data": "calculate"},
            {"text": "🔄 RESET", "callback_data": "reset"}
        ]
    ]
    
    summary = f"🏨 *KS LINH TRANG - NHẬP LIỆU NHANH*\n\n"
    summary += f"📊 *Tổng vé: {total_ve}*\n"
    summary += f"• 1800: {current['ve_1800']} | 800: {current['ve_800']}\n"
    summary += f"• 700: {current['ve_700']} | 800NV: {current['ve_800nv']}\n"
    summary += f"• 700NV: {current['ve_700nv']}"
    
    if message_id:
        edit_message(chat_id, message_id, summary, keyboard)
    else:
        send_message(chat_id, summary, parse_mode='Markdown', keyboard=keyboard)

def handle_button_input(chat_id, text):
    """Xử lý input từ button"""
    if chat_id not in user_data:
        user_data[chat_id] = {
            'date': datetime.datetime.now().strftime("%d/%m/%Y"),
            've_1800': 0, 've_800': 0, 've_700': 0,
            've_800nv': 0, 've_700nv': 0
        }
    
    field = user_states[chat_id].get('waiting')
    
    try:
        if field == 'date':
            if re.match(r'\d{1,2}/\d{1,4}', text):
                user_data[chat_id]['date'] = text
                send_message(chat_id, f"✅ Đã đặt ngày: {text}")
            else:
                send_message(chat_id, "❌ Sai định dạng! VD: 15/3 hoặc 15/3/2026")
                return
        else:
            number = int(text)
            if number < 0:
                send_message(chat_id, "❌ Số lượng phải >= 0")
                return
            
            user_data[chat_id][f've_{field}'] = number
            ten_loai = {
                '1800': '1800', '800': '800', '700': '700',
                '800nv': '800 NV', '700nv': '700 NV'
            }
            send_message(chat_id, f"✅ Đã thêm: {number} vé {ten_loai[field]}")
        
        user_states[chat_id] = {}
        show_quick_menu(chat_id)
        
    except ValueError:
        send_message(chat_id, "❌ Vui lòng nhập số!")

def get_updates(offset=None):
    """Lấy updates từ Telegram"""
    url = f"{TELEGRAM_API}/getUpdates"
    params = {"timeout": 30, "offset": offset}
    
    try:
        response = requests.get(url, params=params, timeout=35)
        if response.status_code == 200:
            return response.json().get("result", [])
    except:
        pass
    return []

def run_bot():
    """Chạy bot polling"""
    print("🤖 Bot đang khởi động...")
    offset = 0
    
    while True:
        try:
            updates = get_updates(offset)
            
            for update in updates:
                handle_update(update)
                offset = update["update_id"] + 1
            
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            time.sleep(5)

@app.route('/')
def home():
    return "🤖 Bot KS Linh Trang đang chạy 24/7!"

def keep_alive():
    """Chạy web server giữ bot alive"""
    app.run(host='0.0.0.0', port=8080)

def main():
    if not BOT_TOKEN:
        print("⚠️ LỖI: Chưa có BOT_TOKEN trong biến môi trường!")
        return
    
    print("✅ Bot KS Linh Trang - Sẵn sàng!")
    
    # Chạy bot trong thread riêng
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Chạy web server
    keep_alive()

if __name__ == "__main__":
    main()
