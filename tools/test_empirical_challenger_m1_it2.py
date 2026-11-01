"""
Milestone 1 Iteration 2 Re-verification Empirical Stress Harness
Challenger: challenger_m1_it2
Empirically tests edge cases for:
1. Deep link underscore parsing in books/views.py (telegram_webhook_view)
2. Deep link underscore parsing in tools/telegram_bot.py (handle_message)
3. 1-click button rendering in templates/profile.html
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Isolated test DB
test_dir = BASE_DIR / 'backups' / 'audit'
test_dir.mkdir(parents=True, exist_ok=True)
test_db = test_dir / 'challenger_m1_it2.sqlite3'

for suffix in ('', '-wal', '-shm'):
    p = Path(str(test_db) + suffix)
    if p.exists():
        p.unlink()

src = sqlite3.connect(str(BASE_DIR / 'db.sqlite3'))
dst = sqlite3.connect(str(test_db))
src.backup(dst)
dst.close()
src.close()

os.environ['SMARTLIB_AUDIT_DB'] = str(test_db)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_audit'

import django
django.setup()

from django.test import Client, RequestFactory
from django.template.loader import render_to_string
from django.urls import reverse
from users.models import CustomUser
from books.views import _get_user_tg_linking_code
import tools.telegram_bot as tb

passed = 0
failed = 0
failures = []

def run_test(name, condition, details=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} -- {details}")
        failures.append(f"{name}: {details}")

print("=====================================================================")
print("RUNNING CHALLENGER EMPIRICAL RE-VERIFICATION (M1 ITERATION 2)")
print("=====================================================================")

client = Client()
webhook_url = reverse('telegram_webhook')

# --- TEST SET 1: DEEP LINK PARSING IN books/views.py ---
print("\n--- 1. DEEP LINK UNDERSCORE PARSING IN books/views.py ---")

test_usernames = [
    "user_one",
    "alpha_beta_gamma",
    "lead_trail_user_",
    "_lead_trail_user",
    "user_ending_123456",
    "very_long_complex_username_with_many_underscores_123",
]

for uname in test_usernames:
    u, _ = CustomUser.objects.get_or_create(
        username=uname,
        defaults={
            'first_name': 'Test',
            'last_name': uname,
            'role': 'student',
            'phone': '+998901112233'
        }
    )
    u.telegram_chat_id = ""
    u.save()
    
    code = _get_user_tg_linking_code(u)
    run_test(f"1. Code generated for {uname} is 6 digits", len(code) == 6 and code.isdigit())
    
    # Negative test: connect without code
    client.post(
        webhook_url,
        data=json.dumps({'message': {'chat': {'id': 1001}, 'text': f'/start connect_{uname}'}}),
        content_type='application/json'
    )
    u.refresh_from_db()
    run_test(f"1. /start connect_{uname} (no code) does NOT bind", u.telegram_chat_id == "")
    
    # Negative test: connect with wrong 6-digit code
    client.post(
        webhook_url,
        data=json.dumps({'message': {'chat': {'id': 1002}, 'text': f'/start connect_{uname}_000000'}}),
        content_type='application/json'
    )
    u.refresh_from_db()
    run_test(f"1. /start connect_{uname}_000000 (wrong code) does NOT bind", u.telegram_chat_id == "")

    # Negative test: connect with non-digit 6-character code
    client.post(
        webhook_url,
        data=json.dumps({'message': {'chat': {'id': 1003}, 'text': f'/start connect_{uname}_abcdef'}}),
        content_type='application/json'
    )
    u.refresh_from_db()
    run_test(f"1. /start connect_{uname}_abcdef (alpha code) does NOT bind", u.telegram_chat_id == "")

    # Positive test: connect with valid 6-digit code
    target_chat_id = f"777{passed}"
    resp = client.post(
        webhook_url,
        data=json.dumps({'message': {'chat': {'id': target_chat_id}, 'text': f'/start connect_{uname}_{code}'}}),
        content_type='application/json'
    )
    u.refresh_from_db()
    run_test(f"1. /start connect_{uname}_{code} binds chat_id", u.telegram_chat_id == target_chat_id)
    run_test(f"1. Webhook returns HTTP 200 for {uname}", resp.status_code == 200)

# Edge case: non-existent username with underscores
resp_nonexistent = client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 99999}, 'text': '/start connect_non_existent_user_with_underscores_123456'}}),
    content_type='application/json'
)
run_test("1. Non-existent username with underscores returns HTTP 200 without crashing", resp_nonexistent.status_code == 200)


# --- TEST SET 2: STANDALONE TELEGRAM_BOT.PY HANDLE_MESSAGE ---
print("\n--- 2. STANDALONE telegram_bot.py handle_message PARSING ---")

sent_messages = []
def mock_send(chat_id, text, **kwargs):
    sent_messages.append({'chat_id': str(chat_id), 'text': text})

orig_send = tb.send_telegram_message
tb.send_telegram_message = mock_send

try:
    for uname in ["bot_user_underscore", "multi_part_bot_user_name"]:
        u, _ = CustomUser.objects.get_or_create(
            username=uname,
            defaults={'first_name': 'Bot', 'last_name': uname, 'role': 'student'}
        )
        u.telegram_chat_id = ""
        u.save()
        code = _get_user_tg_linking_code(u)

        # /start connect_<username>_<code_digit>
        sent_messages.clear()
        tb.handle_message({
            'chat': {'id': 555123},
            'text': f'/start connect_{uname}_{code}'
        })
        u.refresh_from_db()
        run_test(f"2. telegram_bot.py /start connect_{uname}_{code} binds chat_id", u.telegram_chat_id == "555123")
        run_test(f"2. telegram_bot.py sends success message", any("muvaffaqiyatli ulandi" in m['text'] for m in sent_messages))

        # Space-separated code fallback: /start connect_<username> <code>
        u.telegram_chat_id = ""
        u.save()
        sent_messages.clear()
        tb.handle_message({
            'chat': {'id': 555124},
            'text': f'/start connect_{uname} {code}'
        })
        u.refresh_from_db()
        run_test(f"2. telegram_bot.py space-separated /start connect_{uname} {code} binds chat_id", u.telegram_chat_id == "555124")

finally:
    tb.send_telegram_message = orig_send


# --- TEST SET 3: TEMPLATE profile.html 1-CLICK BUTTON ---
print("\n--- 3. TEMPLATE profile.html 1-CLICK BUTTON RENDERING ---")

test_user_profile, _ = CustomUser.objects.get_or_create(
    username="profile_user_with_underscore",
    defaults={'first_name': 'Profile', 'last_name': 'User', 'role': 'student'}
)
test_user_profile.telegram_chat_id = ""
test_user_profile.save()
expected_code = _get_user_tg_linking_code(test_user_profile)

# Context when unlinked
ctx_unlinked = {
    'user': test_user_profile,
    'bot_username': 'SmartLibUzBot',
    'telegram_link_code': expected_code,
    'discipline': {'is_debtor': False},
    'active_loans': [],
    'reservations': [],
    'loan_history': [],
    'total_read': 0,
    'active_count': 0,
    'reserved_count': 0,
}

rendered_html = render_to_string('profile.html', ctx_unlinked)

expected_link = f"https://t.me/SmartLibUzBot?start=connect_profile_user_with_underscore_{expected_code}"
run_test("3. profile.html contains 1-click button with correct start parameter", expected_link in rendered_html)
run_test("3. profile.html contains '1-Klikda Botga Ulash' button text", "1-Klikda Botga Ulash" in rendered_html)

# Context with custom bot username
ctx_custom_bot = dict(ctx_unlinked)
ctx_custom_bot['bot_username'] = 'CustomLibraryBot'
rendered_custom = render_to_string('profile.html', ctx_custom_bot)
expected_custom_link = f"https://t.me/CustomLibraryBot?start=connect_profile_user_with_underscore_{expected_code}"
run_test("3. profile.html respects custom bot_username", expected_custom_link in rendered_custom)

# Context when already linked (telegram_chat_id exists)
test_user_profile.telegram_chat_id = "12345678"
test_user_profile.save()
ctx_linked = dict(ctx_unlinked)
ctx_linked['user'] = test_user_profile
rendered_linked = render_to_string('profile.html', ctx_linked)
run_test("3. When linked, 1-click connect button is NOT shown", "start=connect_" not in rendered_linked)
run_test("3. When linked, 'Botni ochish' button IS shown", "Botni ochish" in rendered_linked)

# Clean up test database copy
for suffix in ('', '-wal', '-shm'):
    p = Path(str(test_db) + suffix)
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass

print("\n=====================================================================")
print(f"CHALLENGER STRESS HARNESS: {passed} PASSED, {failed} FAILED")
print("=====================================================================")

if failed > 0:
    print("\nFAILURES:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("ALL EMPIRICAL TESTS PASSED WITH 100% SUCCESS!")
    sys.exit(0)
