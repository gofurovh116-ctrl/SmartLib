import html
import json
import os
import threading
import urllib.request
import urllib.error
from django.conf import settings
from django.utils import timezone


def escape_html(text):
    """Telegram HTML xabarlarida <, >, & kabi maxsus belgilarni xavfsiz escape qiladi."""
    return html.escape(str(text or ''))


def get_bot_token():
    return (
        os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        or getattr(settings, 'TELEGRAM_BOT_TOKEN', '').strip()
    )


def get_bot_username():
    return (
        os.environ.get('TELEGRAM_BOT_USERNAME', '').strip()
        or getattr(settings, 'TELEGRAM_BOT_USERNAME', 'SmartLibUzBot').strip()
    )


def _append_outbox_log(entry):
    try:
        base_dir = getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logs_dir = os.path.join(str(base_dir), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        outbox_path = os.path.join(logs_dir, 'telegram_outbox.jsonl')
        with open(outbox_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _dispatch_http(token, payload):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def answer_telegram_callback(callback_query_id, text=None, show_alert=False):
    """Telegram inline tugma bosilganda spinner yuklanishni to'xtatadi va bildirishnoma beradi."""
    token = get_bot_token()
    if not token or not callback_query_id:
        return False
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {'callback_query_id': str(callback_query_id)}
    if text:
        payload['text'] = text
        payload['show_alert'] = bool(show_alert)
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    def _run():
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return True


def send_telegram_message(chat_id, text, reply_markup=None, parse_mode='HTML', async_send=True):
    """Defensive Telegram dispatcher.
    - Never raises an exception or blocks web requests.
    - Logs all outgoing notifications to logs/telegram_outbox.jsonl for auditability.
    - Dispatches via Telegram Bot API if TELEGRAM_BOT_TOKEN is configured.
    """
    chat_id_str = str(chat_id or '').strip()
    if not chat_id_str:
        return {'ok': False, 'reason': 'empty_chat_id'}

    payload = {
        'chat_id': chat_id_str,
        'text': text,
        'parse_mode': parse_mode,
    }
    if reply_markup:
        payload['reply_markup'] = reply_markup

    token = get_bot_token()
    log_entry = {
        'timestamp': timezone.now().isoformat(),
        'chat_id': chat_id_str,
        'text': text,
        'has_token': bool(token),
    }
    _append_outbox_log(log_entry)

    if not token:
        return {'ok': True, 'simulated': True, 'reason': 'logged_to_outbox'}

    if async_send:
        t = threading.Thread(target=_dispatch_http, args=(token, payload), daemon=True)
        t.start()
        return {'ok': True, 'async': True}
    else:
        delivered = _dispatch_http(token, payload)
        return {'ok': delivered, 'async': False}


def notify_borrow_request(loan, librarians=None):
    book = loan.book_copy.book
    user = loan.user
    safe_title = escape_html(book.title)
    safe_name = escape_html(user.full_display_name)
    safe_username = escape_html(user.username)
    safe_inv = escape_html(loan.book_copy.inventory_number)
    safe_code = escape_html(loan.verification_code)

    if getattr(user, 'telegram_chat_id', ''):
        msg = (
            f"📚 <b>SmartLib — Kitob olish so'rovi</b>\n\n"
            f"Kitob: <b>{safe_title}</b>\n"
            f"Inventar: <code>{safe_inv}</code>\n"
            f"🔑 Tasdiqlash kodi: <b><code>{safe_code}</code></b>\n\n"
            f"Kutubxonachiga ushbu 6-xonali kodni ko'rsatib kitobni qabul qilib oling."
        )
        send_telegram_message(user.telegram_chat_id, msg)

    if librarians:
        for lib_user in librarians:
            if getattr(lib_user, 'telegram_chat_id', '') and lib_user != user:
                lib_msg = (
                    f"🛎 <b>Yangi kitob olish so'rovi!</b>\n\n"
                    f"👤 Kitobxon: <b>{safe_name}</b> (@{safe_username})\n"
                    f"📖 Kitob: <b>{safe_title}</b> (<code>{safe_inv}</code>)\n"
                    f"🔑 Tasdiqlash kodi: <b><code>{safe_code}</code></b>"
                )
                reply_markup = {
                    'inline_keyboard': [[
                        {'text': '✅ Tasdiqlash (Berildi)', 'callback_data': f'approve_borrow:{loan.pk}:{loan.verification_code}'},
                        {'text': '❌ Rad etish', 'callback_data': f'reject_borrow:{loan.pk}'},
                    ]]
                }
                send_telegram_message(lib_user.telegram_chat_id, lib_msg, reply_markup=reply_markup)


def notify_borrow_approved(loan):
    user = loan.user
    if not getattr(user, 'telegram_chat_id', ''):
        return
    book = loan.book_copy.book
    safe_title = escape_html(book.title)
    safe_inv = escape_html(loan.book_copy.inventory_number)
    issued_name = escape_html(loan.issued_by.full_display_name if loan.issued_by else 'Kutubxonachi')
    msg = (
        f"✅ <b>Kitob berilishi tasdiqlandi!</b>\n\n"
        f"📖 Kitob: <b>{safe_title}</b> (<code>{safe_inv}</code>)\n"
        f"📅 Qaytarish muddati: <b>{loan.due_date.strftime('%d.%m.%Y')}</b>\n"
        f"👨‍🏫 Bergan xodim: {issued_name}\n\n"
        f"<i>Kitobni o'z vaqtida qaytarib +35 XP ball to'plang!</i>"
    )
    send_telegram_message(user.telegram_chat_id, msg)


def notify_return_approved(loan):
    user = loan.user
    if not getattr(user, 'telegram_chat_id', ''):
        return
    book = loan.book_copy.book
    safe_title = escape_html(book.title)
    safe_inv = escape_html(loan.book_copy.inventory_number)
    msg = (
        f"📥 <b>Kitob muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"📖 Kitob: <b>{safe_title}</b> (<code>{safe_inv}</code>)\n"
        f"🏆 Sizga <b>+25 XP</b> kitobxonlik bali qo'shildi!\n\n"
        f"SmartLib kutubxonasidan foydalanganingiz uchun rahmat!"
    )
    send_telegram_message(user.telegram_chat_id, msg)


def notify_reservation_available(user, book):
    if not getattr(user, 'telegram_chat_id', ''):
        return
    safe_title = escape_html(book.title)
    msg = (
        f"🎉 <b>Navbatdagi kitob bo'shadi!</b>\n\n"
        f"Siz navbatda kutayotgan <b>«{safe_title}»</b> kitobi kutubxonaga qaytarildi.\n"
        f"Hoziroq SmartLib tizimiga kirib buyurtma berishingiz mumkin!"
    )
    send_telegram_message(user.telegram_chat_id, msg)


def notify_overdue_reminder(loan):
    user = loan.user
    book = loan.book_copy.book
    safe_name = escape_html(user.full_display_name)
    safe_title = escape_html(book.title)
    safe_inv = escape_html(loan.book_copy.inventory_number)
    msg = (
        f"🚨 <b>DIQQAT: Kitob topshirish muddati o'tgan!</b>\n\n"
        f"👤 Kitobxon: <b>{safe_name}</b>\n"
        f"📖 Kitob: <b>{safe_title}</b> (<code>{safe_inv}</code>)\n"
        f"⏳ Kechikkan kunlar: <b>{loan.overdue_days} kun</b>\n"
        f"⚠️ Jarima bali: <b>-{loan.penalty_points} XP</b>\n\n"
        f"Iltimos, kitobni zudlik bilan kutubxonaga topshiring! Qarzdorlik yopilmaguncha yangi kitob olish cheklangan."
    )
    if getattr(user, 'telegram_chat_id', ''):
        return send_telegram_message(user.telegram_chat_id, msg)
    return {'ok': False, 'reason': 'no_chat_id'}
