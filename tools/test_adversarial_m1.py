"""
SmartLib Milestone 1 Adversarial Stress Test Suite
Author: Challenger 1 (critic & specialist)
Empirically stress-tests:
1. Maker-Checker OTP validation (empty string, whitespace, wrong code, valid code, no leakage)
2. Telegram Webhook Secret Token validation & Account Takeover Prevention (/connect and /start)
3. Callback query authorization & vcode checking
4. RBAC & Debtor PII Protection in /reports/, /reports/excel/, stickers PDF, and import templates
5. XSS script breakout resistance in 3D reading room and reports
"""

import os
import sys
import shutil
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Create isolated test database copy
test_dir = BASE_DIR / 'backups' / 'audit'
test_dir.mkdir(parents=True, exist_ok=True)
test_db = test_dir / 'challenger_m1.sqlite3'

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

from django.test import Client
from django.test.utils import setup_test_environment
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.contrib.messages import get_messages

from users.models import CustomUser
from books.models import Book, BookCopy, Loan, Library, Genre
from books.views import _get_user_tg_linking_code, _build_books_3d_json, _mask_phone

setup_test_environment()

passed_count = 0
failed_count = 0
findings = []

def run_test(name, condition, details=""):
    global passed_count, failed_count
    if condition:
        passed_count += 1
        print(f"  [PASS] {name}")
    else:
        failed_count += 1
        print(f"  [FAIL] {name} -- {details}")
        findings.append(f"FAIL: {name} - {details}")

print("=====================================================================")
print("STARTING EMPIRICAL ADVERSARIAL STRESS TEST SUITE -- MILESTONE 1")
print("=====================================================================")

# Prepare common fixtures
lib = Library.objects.first() or Library.objects.create(name="Markaziy Kutubxona")
genre = Genre.objects.first() or Genre.objects.create(name="Badiiy")

# 1. Users
admin_user, _ = CustomUser.objects.get_or_create(
    username="adv_admin",
    defaults={'is_staff': True, 'is_superuser': True, 'status': 'admin', 'first_name': 'Adv', 'last_name': 'Admin'}
)
admin_user.set_password("pass1234")
admin_user.save()

librarian_user, _ = CustomUser.objects.get_or_create(
    username="adv_librarian",
    defaults={'is_staff': True, 'is_superuser': False, 'status': 'librarian', 'first_name': 'Adv', 'last_name': 'Librarian'}
)
librarian_user.set_password("pass1234")
librarian_user.telegram_chat_id = "777888999"
librarian_user.save()

student_user, _ = CustomUser.objects.get_or_create(
    username="adv_student",
    defaults={'is_staff': False, 'is_superuser': False, 'status': 'student', 'first_name': 'Adv', 'last_name': 'Student', 'phone': '+998901234567'}
)
student_user.set_password("pass1234")
student_user.telegram_chat_id = ""
student_user.save()

victim_user, _ = CustomUser.objects.get_or_create(
    username="advvictim",
    defaults={'is_staff': False, 'is_superuser': False, 'status': 'student', 'first_name': 'Adv', 'last_name': 'Victim'}
)
victim_user.set_password("victim_pass_secret")
victim_user.telegram_chat_id = ""
victim_user.save()

victim_user_underscore, _ = CustomUser.objects.get_or_create(
    username="adv_victim_with_underscore",
    defaults={'is_staff': False, 'is_superuser': False, 'status': 'student', 'first_name': 'Adv', 'last_name': 'VictimUnderscore'}
)
victim_user_underscore.set_password("victim_pass_secret")
victim_user_underscore.telegram_chat_id = ""
victim_user_underscore.save()

# Book & Copies
book, _ = Book.objects.get_or_create(
    title="Adversarial Testing In Practice",
    defaults={'author': 'Challenger', 'library': lib, 'genre': genre, 'pages': 250}
)
copy1, _ = BookCopy.objects.get_or_create(book=book, inventory_number="ADV-001", defaults={'is_available': True})
copy2, _ = BookCopy.objects.get_or_create(book=book, inventory_number="ADV-002", defaults={'is_available': True})
copy3, _ = BookCopy.objects.get_or_create(book=book, inventory_number="ADV-003", defaults={'is_available': True})
copy4, _ = BookCopy.objects.get_or_create(book=book, inventory_number="ADV-004", defaults={'is_available': True})

client = Client()

# =====================================================================
# SUITE 1: MAKER-CHECKER OTP STRESS TESTS
# =====================================================================
print("\n--- SUITE 1: MAKER-CHECKER OTP VERIFICATION STRESS TESTS ---")

# Setup loan pending
loan1 = Loan.objects.create(
    book_copy=copy1,
    user=student_user,
    status='borrow_pending',
    verification_code='849201',
    is_returned=False
)

client.force_login(librarian_user)

# 1.1 Empty string OTP
resp = client.post(reverse('librarian_approve_borrow', args=[loan1.pk]), {'verification_code': ''}, follow=True)
loan1.refresh_from_db()
run_test("1.1 Empty string OTP rejects borrow activation", loan1.status == 'borrow_pending')
msgs = [m.message for m in get_messages(resp.wsgi_request)]
run_test("1.1 Error message displayed on empty string", any("Noto'g'ri yoki bo'sh" in m for m in msgs))
run_test("1.1 Expected OTP NOT leaked in error message", not any('849201' in m for m in msgs))

# 1.2 Whitespace OTP
resp = client.post(reverse('librarian_approve_borrow', args=[loan1.pk]), {'verification_code': '   '}, follow=True)
loan1.refresh_from_db()
run_test("1.2 Whitespace OTP rejects borrow activation", loan1.status == 'borrow_pending')
msgs = [m.message for m in get_messages(resp.wsgi_request)]
run_test("1.2 Error message displayed on whitespace OTP", any("Noto'g'ri yoki bo'sh" in m for m in msgs))
run_test("1.2 Expected OTP NOT leaked on whitespace OTP", not any('849201' in m for m in msgs))

# 1.3 Missing parameter OTP
resp = client.post(reverse('librarian_approve_borrow', args=[loan1.pk]), {}, follow=True)
loan1.refresh_from_db()
run_test("1.3 Missing verification_code parameter rejects borrow activation", loan1.status == 'borrow_pending')

# 1.4 Wrong OTP
resp = client.post(reverse('librarian_approve_borrow', args=[loan1.pk]), {'verification_code': '000000'}, follow=True)
loan1.refresh_from_db()
run_test("1.4 Wrong OTP rejects borrow activation", loan1.status == 'borrow_pending')
msgs = [m.message for m in get_messages(resp.wsgi_request)]
run_test("1.4 Expected OTP NOT leaked on wrong code", not any('849201' in m for m in msgs))

# 1.5 Valid OTP
resp = client.post(reverse('librarian_approve_borrow', args=[loan1.pk]), {'verification_code': '849201'}, follow=True)
loan1.refresh_from_db()
run_test("1.5 Valid OTP approves borrow activation", loan1.status == 'active' and loan1.issued_by == librarian_user)

# 1.6 Return flow OTP verification
loan2 = Loan.objects.create(
    book_copy=copy2,
    user=student_user,
    status='active',
    verification_code='654321',
    is_returned=False
)

# Return with empty code
resp = client.post(reverse('librarian_approve_return', args=[loan2.pk]), {'verification_code': ''}, follow=True)
loan2.refresh_from_db()
run_test("1.6 Empty string OTP rejects return activation", not loan2.is_returned and loan2.status == 'active')
msgs = [m.message for m in get_messages(resp.wsgi_request)]
run_test("1.6 Error message on empty return OTP", any("Noto'g'ri yoki bo'sh" in m for m in msgs))
run_test("1.6 Expected OTP NOT leaked on empty return OTP", not any('654321' in m for m in msgs))

# Return with whitespace code
resp = client.post(reverse('librarian_approve_return', args=[loan2.pk]), {'verification_code': '    '}, follow=True)
loan2.refresh_from_db()
run_test("1.7 Whitespace OTP rejects return activation", not loan2.is_returned and loan2.status == 'active')

# Return with wrong code
resp = client.post(reverse('librarian_approve_return', args=[loan2.pk]), {'verification_code': '111111'}, follow=True)
loan2.refresh_from_db()
run_test("1.8 Wrong code rejects return activation", not loan2.is_returned and loan2.status == 'active')

# Return with valid code
resp = client.post(reverse('librarian_approve_return', args=[loan2.pk]), {'verification_code': '654321'}, follow=True)
loan2.refresh_from_db()
run_test("1.9 Valid code completes return activation", loan2.is_returned and loan2.status == 'returned' and loan2.received_by == librarian_user)

# =====================================================================
# SUITE 2: TELEGRAM WEBHOOK SECRET TOKEN & ACCOUNT TAKEOVER
# =====================================================================
print("\n--- SUITE 2: TELEGRAM WEBHOOK SECRET TOKEN & ACCOUNT TAKEOVER ---")

webhook_url = reverse('telegram_webhook')
anon_client = Client()

# 2.1 Secret Token Validation
orig_secret = getattr(settings, 'TELEGRAM_BOT_WEBHOOK_SECRET', None)
settings.TELEGRAM_BOT_WEBHOOK_SECRET = "Adversarial_Webhook_Secret_Token_123"

try:
    # No header
    resp = anon_client.post(webhook_url, data=json.dumps({'message': {'chat': {'id': 1}, 'text': '/help'}}), content_type='application/json')
    run_test("2.1 Missing secret token returns HTTP 403", resp.status_code == 403)
    run_test("2.1 Missing secret token returns invalid_secret_token JSON", resp.json().get('error') == 'invalid_secret_token')

    # Wrong header
    resp = anon_client.post(
        webhook_url,
        data=json.dumps({'message': {'chat': {'id': 1}, 'text': '/help'}}),
        content_type='application/json',
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='wrong_token_attack'
    )
    run_test("2.1 Wrong secret token returns HTTP 403", resp.status_code == 403)

    # Correct header
    resp = anon_client.post(
        webhook_url,
        data=json.dumps({'message': {'chat': {'id': 1}, 'text': '/help'}}),
        content_type='application/json',
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='Adversarial_Webhook_Secret_Token_123'
    )
    run_test("2.1 Valid secret token returns HTTP 200", resp.status_code == 200)

finally:
    settings.TELEGRAM_BOT_WEBHOOK_SECRET = orig_secret

# Backward compatibility test when secret is unset
resp = anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 1}, 'text': '/help'}}),
    content_type='application/json'
)
run_test("2.1 Backward compatible HTTP 200 when secret unset", resp.status_code == 200)

# 2.2 Account Takeover Prevention via /connect
victim_user.telegram_chat_id = ""
victim_user.save()
valid_linking_code = _get_user_tg_linking_code(victim_user)
run_test("2.2 Linking code is valid 6-digit string", len(valid_linking_code) == 6 and valid_linking_code.isdigit())

# Attacker attempts /connect victim_user (no code)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 999111}, 'text': f'/connect {victim_user.username}'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.2 /connect without code does NOT bind chat ID", victim_user.telegram_chat_id == "")

# Attacker attempts /connect victim_user 123456 (wrong code)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 999111}, 'text': f'/connect {victim_user.username} 000000'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.2 /connect with wrong code does NOT bind chat ID", victim_user.telegram_chat_id == "")

# Attacker attempts /ulanish victim_user (alias without code)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 999111}, 'text': f'/ulanish {victim_user.username}'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.2 /ulanish without code does NOT bind chat ID", victim_user.telegram_chat_id == "")

# Legitimate user connects with valid code
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 999111}, 'text': f'/connect {victim_user.username} {valid_linking_code}'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.2 /connect with valid code successfully binds chat ID", victim_user.telegram_chat_id == "999111")

# 2.3 Account Takeover Prevention via /start connect_
victim_user.telegram_chat_id = ""
victim_user.save()

# /start connect_victim (no code)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 888222}, 'text': f'/start connect_{victim_user.username}'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.3 /start connect_ without code does NOT bind chat ID", victim_user.telegram_chat_id == "")

# /start connect_victim_000000 (wrong code)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 888222}, 'text': f'/start connect_{victim_user.username}_000000'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.3 /start connect_ with wrong code does NOT bind chat ID", victim_user.telegram_chat_id == "")

# /start connect_victim_<valid_code> (valid code, username without underscore)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 888222}, 'text': f'/start connect_{victim_user.username}_{valid_linking_code}'}}),
    content_type='application/json'
)
victim_user.refresh_from_db()
run_test("2.3a /start connect_ with valid code for username WITHOUT underscore binds chat ID", victim_user.telegram_chat_id == "888222")

# /start connect_<username_with_underscore>_<valid_code>
valid_code_underscore = _get_user_tg_linking_code(victim_user_underscore)
anon_client.post(
    webhook_url,
    data=json.dumps({'message': {'chat': {'id': 888333}, 'text': f'/start connect_{victim_user_underscore.username}_{valid_code_underscore}'}}),
    content_type='application/json'
)
victim_user_underscore.refresh_from_db()
run_test("2.3b /start connect_ with valid code for username WITH underscore binds chat ID", victim_user_underscore.telegram_chat_id == "888333", details=f"Target username '{victim_user_underscore.username}' truncated by split('_', 1) in views.py line 2860")

# 2.4 Callback query authorization and vcode validation
loan3 = Loan.objects.create(
    book_copy=copy3,
    user=student_user,
    status='borrow_pending',
    verification_code='334455',
    is_returned=False
)

# Callback from non-librarian chat ID
anon_client.post(
    webhook_url,
    data=json.dumps({
        'callback_query': {
            'id': 'cb_test_1',
            'from': {'id': 555000},  # Not librarian
            'data': f'approve_borrow:{loan3.pk}:334455'
        }
    }),
    content_type='application/json'
)
loan3.refresh_from_db()
run_test("2.4 Callback approve_borrow from non-librarian chat ID rejected", loan3.status == 'borrow_pending')

# Callback from librarian chat ID with wrong vcode
anon_client.post(
    webhook_url,
    data=json.dumps({
        'callback_query': {
            'id': 'cb_test_2',
            'from': {'id': int(librarian_user.telegram_chat_id)},
            'data': f'approve_borrow:{loan3.pk}:wrong_vcode'
        }
    }),
    content_type='application/json'
)
loan3.refresh_from_db()
run_test("2.4 Callback approve_borrow with wrong vcode rejected", loan3.status == 'borrow_pending')

# Callback from librarian chat ID with empty vcode
anon_client.post(
    webhook_url,
    data=json.dumps({
        'callback_query': {
            'id': 'cb_test_3',
            'from': {'id': int(librarian_user.telegram_chat_id)},
            'data': f'approve_borrow:{loan3.pk}:'
        }
    }),
    content_type='application/json'
)
loan3.refresh_from_db()
run_test("2.4 Callback approve_borrow with empty vcode rejected", loan3.status == 'borrow_pending')

# Callback from librarian chat ID with valid vcode
anon_client.post(
    webhook_url,
    data=json.dumps({
        'callback_query': {
            'id': 'cb_test_4',
            'from': {'id': int(librarian_user.telegram_chat_id)},
            'data': f'approve_borrow:{loan3.pk}:334455'
        }
    }),
    content_type='application/json'
)
loan3.refresh_from_db()
run_test("2.4 Callback approve_borrow with valid vcode succeeds", loan3.status == 'active' and loan3.issued_by == librarian_user)

# =====================================================================
# SUITE 3: RBAC & DEBTOR PII PROTECTION
# =====================================================================
print("\n--- SUITE 3: RBAC & DEBTOR PII PROTECTION ---")

# Create an overdue loan for testing PII exposure
overdue_loan = Loan.objects.create(
    book_copy=copy4,
    user=student_user,
    status='active',
    borrowed_at=timezone.now() - timedelta(days=25),
    due_date=timezone.now() - timedelta(days=15),
    is_returned=False
)

reader_client = Client()
reader_client.force_login(student_user)

# 3.1 Reports View
resp = reader_client.get(reverse('reports'))
run_test("3.1 Reader accessing /reports/ gets HTTP 200", resp.status_code == 200)
run_test("3.1 Context is_librarian_or_admin is False for reader", resp.context.get('is_librarian_or_admin') is False)
run_test("3.1 Context overdue_list is empty for reader", len(resp.context.get('overdue_list', [])) == 0)
html_content = resp.content.decode('utf-8')
run_test("3.1 Debtor phone (+998901234567) NOT visible in HTML for reader", "+998901234567" not in html_content and "+998 90 123 45 67" not in html_content)
run_test("3.1 Remind overdue action button NOT present for reader", "librarian_remind_overdue" not in html_content)

# 3.2 Excel export phone masking
resp_excel = reader_client.get(reverse('reports_excel'))
run_test("3.2 Reader accessing /reports/excel/ gets HTTP 200", resp_excel.status_code == 200)
masked_phone = _mask_phone("+998901234567")
run_test("3.2 Phone masking utility masks middle digits", "***" in masked_phone and "1234" not in masked_phone)

# 3.3 Book Stickers PDF Access Restriction
resp = reader_client.get(reverse('book_stickers_pdf', args=[book.pk]))
run_test("3.3 Non-librarian blocked from book_stickers_pdf (redirect)", resp.status_code == 302 and resp.url == reverse('home'))

resp = anon_client.get(reverse('book_stickers_pdf', args=[book.pk]))
run_test("3.3 Anon blocked from book_stickers_pdf (redirect to login)", resp.status_code == 302 and 'login' in resp.url)

lib_client = Client()
lib_client.force_login(librarian_user)
resp = lib_client.get(reverse('book_stickers_pdf', args=[book.pk]))
run_test("3.3 Librarian allowed access to book_stickers_pdf (HTTP 200)", resp.status_code == 200 and resp['Content-Type'] == 'application/pdf')

# 3.4 Librarian Import Template Access Restriction
resp = reader_client.get(reverse('librarian_import_template'))
run_test("3.4 Non-librarian blocked from librarian_import_template (redirect)", resp.status_code == 302 and resp.url == reverse('home'))

resp = lib_client.get(reverse('librarian_import_template'))
run_test("3.4 Librarian allowed access to librarian_import_template (HTTP 200)", resp.status_code == 200 and 'spreadsheet' in resp['Content-Type'])

# =====================================================================
# SUITE 4: XSS SCRIPT BREAKOUT RESISTANCE
# =====================================================================
print("\n--- SUITE 4: XSS SCRIPT BREAKOUT RESISTANCE ---")

xss_book = Book(
    pk=999,
    title="XSS Attack </script><script>alert('pwned')</script>",
    author="Bad Actor <img src=x onerror=alert(1)>",
    annotation="Safe test <script>test</script>",
    pages=100,
    published_year=2024,
    genre=genre
)
xss_json = _build_books_3d_json([xss_book])

run_test("4.1 Raw </script> tag NOT present in 3D books json", "</script>" not in xss_json)
run_test("4.1 < character escaped as \\u003c", "\\u003c" in xss_json)
run_test("4.1 > character escaped as \\u003e", "\\u003e" in xss_json)

# Check reading room view renders safely with contracts intact
resp_rr = anon_client.get(reverse('reading_room'))
run_test("4.1 Reading room view returns HTTP 200", resp_rr.status_code == 200)
rr_content = resp_rr.content.decode('utf-8')
run_test("4.1 readingRoomCanvasHost DOM ID preserved", 'id="readingRoomCanvasHost"' in rr_content or "readingRoomCanvasHost" in rr_content)
run_test("4.1 books3dDataJson DOM ID preserved", 'id="books3dDataJson"' in rr_content)

# Reports template json_script verification
resp_rep = lib_client.get(reverse('reports'))
rep_content = resp_rep.content.decode('utf-8')
run_test("4.2 reports.html uses chartTopLabelsData json_script", 'id="chartTopLabelsData"' in rep_content)
run_test("4.2 reports.html uses chartTopCountsData json_script", 'id="chartTopCountsData"' in rep_content)
run_test("4.2 reports.html uses chartGenreLabelsData json_script", 'id="chartGenreLabelsData"' in rep_content)
run_test("4.2 reports.html uses chartGenreCountsData json_script", 'id="chartGenreCountsData"' in rep_content)
run_test("4.2 reports.html does NOT contain unescaped raw chart_top_labels_json", "chart_top_labels_json" not in rep_content)

# =====================================================================
# SUMMARY
# =====================================================================
total_tests = passed_count + failed_count
print("\n=====================================================================")
print(f"ADVERSARIAL STRESS TEST RESULTS: {passed_count}/{total_tests} PASSED, {failed_count} FAILED")
print("=====================================================================")

if failed_count > 0:
    print("\nFAILURES:")
    for f in findings:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("ALL EMPIRICAL ADVERSARIAL STRESS TESTS PASSED SUCCESSFULLY!")
    sys.exit(0)
