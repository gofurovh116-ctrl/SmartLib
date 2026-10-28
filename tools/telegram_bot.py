"""
SmartLib — Rasmiy Telegram Bot Daemon (Long-Polling).
Ishga tushirish:
    set TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
    D:\SmartLib\venv\Scripts\python.exe D:\SmartLib\tools\telegram_bot.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.utils import timezone
from django.db import transaction
from users.models import CustomUser
from books.models import Loan, Notification
from books.telegram_service import get_bot_token, send_telegram_message, notify_borrow_approved


def _api_call(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params or {}).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as exc:
        print(f"[TelegramAPI Warning] {method}: {exc}")
        return {'ok': False}


def handle_message(msg):
    chat = msg.get('chat') or {}
    chat_id = str(chat.get('id', '')).strip()
    text = (msg.get('text') or '').strip()
    if not chat_id or not text:
        return

    if text.startswith('/start'):
        parts = text.split(maxsplit=1)
        if len(parts) > 1:
            username_arg = parts[1].strip().lstrip('@')
            user = CustomUser.objects.filter(username__iexact=username_arg).first()
            if user:
                user.telegram_chat_id = chat_id
                user.save(update_fields=['telegram_chat_id'])
                send_telegram_message(
                    chat_id,
                    f"✅ <b>Tabriklaymiz, {user.full_display_name}!</b>\n\n"
                    f"Sizning SmartLib (@{user.username}) profilingiz Telegram botga muvaffaqiyatli ulandi.\n"
                    f"🆔 Chat ID: <code>{chat_id}</code>\n\n"
                    f"Buyruqlar:\n"
                    f"• /mybooks — Qo'lingizdagi kitoblar va kodlar\n"
                    f"• /xp — Kitobxonlik XP va intizom reytingi\n"
                    f"• /id — Chat ID raqamingizni ko'rish",
                    async_send=False,
                )
                return
        send_telegram_message(
            chat_id,
            f"👋 <b>SmartLib Rasmiy Botiga xush kelibsiz!</b>\n\n"
            f"Sizning Telegram Chat ID raqamingiz: <code>{chat_id}</code>\n\n"
            f"📌 <b>Hisobni ulashning 2 xil usuli:</b>\n"
            f"1) Shu yerdan: <code>/start login_nomingiz</code> deb yozing.\n"
            f"2) SmartLib saytidagi <b>Profilni tahrirlash</b> sahifasiga <code>{chat_id}</code> raqamini kiriting.",
            async_send=False,
        )

    elif text.startswith('/id'):
        send_telegram_message(
            chat_id,
            f"🆔 Sizning Telegram Chat ID raqamingiz: <code>{chat_id}</code>",
            async_send=False,
        )

    elif text.startswith('/mybooks') or text.startswith('/xp'):
        user = CustomUser.objects.filter(telegram_chat_id=chat_id).first()
        if not user:
            send_telegram_message(
                chat_id,
                f"⚠️ Sizning Telegram hisobingiz hali SmartLib profiliga ulanmagan.\n"
                f"Ulash uchun: <code>/start login_nomingiz</code> yoki saytda Chat ID (<code>{chat_id}</code>) ni saqlang.",
                async_send=False,
            )
            return
        summary = user.get_discipline_summary()
        active_loans = list(Loan.objects.filter(user=user, is_returned=False).select_related('book_copy__book'))
        lines = [
            f"👤 <b>{user.full_display_name}</b> (@{user.username})",
            f"🏆 XP Ball: <b>{summary['xp']} XP</b> | Intizom: <b>{summary['discipline_score']}%</b>",
            "",
        ]
        if active_loans:
            lines.append("📚 <b>Hozirgi kitoblaringiz:</b>")
            for idx, ln in enumerate(active_loans, 1):
                st = ln.get_status_display()
                overdue_str = f" 🚨 (Kechikkan: {ln.overdue_days} kun)" if ln.is_overdue else ""
                code_str = f" | Kod: <code>{ln.verification_code}</code>" if ln.verification_code else ""
                lines.append(
                    f"{idx}. <b>{ln.book_copy.book.title}</b> (<code>{ln.book_copy.inventory_number}</code>)\n"
                    f"   Holat: {st}{code_str} | Muddat: {ln.due_date.strftime('%d.%m.%Y')}{overdue_str}"
                )
        else:
            lines.append("✅ Hozir qo'lingizda faol ijara kitoblari yo'q.")
        send_telegram_message(chat_id, "\n".join(lines), async_send=False)


def handle_callback(token, cb):
    cb_id = cb.get('id')
    data = cb.get('data') or ''
    from_chat = str((cb.get('message') or {}).get('chat', {}).get('id', '')).strip()
    lib_user = CustomUser.objects.filter(telegram_chat_id=from_chat).first()
    if not lib_user or not (lib_user.is_staff or lib_user.is_superuser or lib_user.status in ('librarian', 'admin')):
        _api_call(token, 'answerCallbackQuery', {'callback_query_id': cb_id, 'text': 'Faqat kutubxonachilar tasdiqlashi mumkin!', 'show_alert': True})
        return

    if data.startswith('approve_borrow:'):
        parts = data.split(':')
        loan_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        with transaction.atomic():
            loan = Loan.objects.select_related('book_copy__book', 'user').filter(pk=loan_id, is_returned=False, status='borrow_pending').first()
            if not loan:
                _api_call(token, 'answerCallbackQuery', {'callback_query_id': cb_id, 'text': "So'rov allaqachon ko'rib chiqilgan.", 'show_alert': True})
                return
            loan.status = 'active'
            loan.issued_by = lib_user
            loan.borrowed_at = timezone.now()
            loan.due_date = timezone.now() + timedelta(days=10)
            loan.save()
            Notification.objects.create(
                user=loan.user,
                title="Kitob berilishi tasdiqlandi (Telegram)",
                message=f"«{loan.book_copy.book.title}» kitobi {lib_user.full_display_name} tomonidan tasdiqlandi.",
                link="/profile/",
            )
            notify_borrow_approved(loan)
        _api_call(token, 'answerCallbackQuery', {'callback_query_id': cb_id, 'text': '✅ Kitob berilishi tasdiqlandi!'})
        send_telegram_message(from_chat, f"✅ <b>{loan.book_copy.book.title}</b> kitobi {loan.user.full_display_name}ga berildi!", async_send=False)


def main():
    token = get_bot_token()
    if not token:
        print("[!] TELEGRAM_BOT_TOKEN o'rnatilmagan. Xabarlar D:\\SmartLib\\logs\\telegram_outbox.jsonl fayliga yozib boriladi.")
        return
    print("[*] SmartLib Telegram Bot ishga tushdi (Long-Polling)...")
    offset = 0
    while True:
        res = _api_call(token, 'getUpdates', {'offset': offset, 'timeout': 25})
        if res.get('ok'):
            for item in res.get('result', []):
                offset = max(offset, item['update_id'] + 1)
                if 'message' in item:
                    handle_message(item['message'])
                elif 'callback_query' in item:
                    handle_callback(token, item['callback_query'])
        else:
            time.sleep(3)


if __name__ == '__main__':
    main()
