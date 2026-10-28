"""
SmartLib to'liq avtomatik audit (smoke + flow test).
Ishga tushirish: tools\run_audit.bat
Asl bazaga tegmaydi - nusxa ustida ishlaydi.
"""
import os
import sys
import shutil
import sqlite3
import json
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

audit_dir = BASE_DIR / 'backups' / 'audit'
audit_dir.mkdir(parents=True, exist_ok=True)
audit_db = audit_dir / 'audit.sqlite3'
for suffix in ('', '-wal', '-shm'):
    p = Path(str(audit_db) + suffix)
    if p.exists():
        p.unlink()
src = sqlite3.connect(str(BASE_DIR / 'db.sqlite3'))
dst = sqlite3.connect(str(audit_db))
src.backup(dst)
dst.close()
src.close()
# media nusxasi (QR / rasm fayllari tekshiruvi uchun)
media_copy = audit_dir / 'audit_media'
if media_copy.exists():
    shutil.rmtree(media_copy, ignore_errors=True)
if (BASE_DIR / 'media').exists():
    shutil.copytree(BASE_DIR / 'media', media_copy)

os.environ['SMARTLIB_AUDIT_DB'] = str(audit_db)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings_audit'

import django  # noqa: E402
django.setup()

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.contrib import admin  # noqa: E402
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

setup_test_environment()

FAILS = []
OK = [0]


def record(label, ok, detail=''):
    if ok:
        OK[0] += 1
    else:
        FAILS.append(f"{label} :: {detail}")
        print(f"  [FAIL] {label} :: {detail}")


def hit(client, method, url, expect=(200,), label=None, **kw):
    label = label or f"{method} {url}"
    try:
        resp = getattr(client, method.lower())(url, **kw)
        ok = resp.status_code in expect
        detail = f"status={resp.status_code}"
        if not ok and resp.status_code == 500:
            detail += ' (500 SERVER ERROR)'
        record(label, ok, detail)
        return resp
    except Exception as exc:
        record(label, False, f"EXCEPTION {type(exc).__name__}: {exc}\n{traceback.format_exc(limit=6)}")
        return None


print("=== 0. Migratsiyalar (nusxada) ===")
try:
    call_command('migrate', interactive=False, verbosity=0)
    record('migrate', True)
except Exception as exc:
    record('migrate', False, repr(exc))

from users.models import CustomUser, Library, StudentBase  # noqa: E402
from books.models import Book, BookCopy, Genre, Loan, Reservation  # noqa: E402

books = list(Book.objects.all())
langs = ['uz', 'ru', 'en']

print("=== 1. Anonim foydalanuvchi ===")
anon = Client(raise_request_exception=False)
for lang in langs:
    anon.cookies['django_language'] = lang
    hit(anon, 'GET', '/', label=f'[{lang}] home')
    r_3d = hit(anon, 'GET', '/reading-room/', label=f'[{lang}] 3D reading room')
    record(f'[{lang}] 3D reading room canvas & json',
           r_3d is not None and b'readingRoomCanvasHost' in r_3d.content and b'books3dDataJson' in r_3d.content,
           '3D reading room elements missing')
    hit(anon, 'GET', '/?q=python', label=f'[{lang}] home search')
    hit(anon, 'GET', '/?q=%27%22%3Cscript%3E', label=f'[{lang}] home XSS search')
    hit(anon, 'GET', '/?genre=abc&library=-1', label=f'[{lang}] home bad filters')
    hit(anon, 'GET', '/login/', label=f'[{lang}] login')
    hit(anon, 'GET', '/register/', label=f'[{lang}] register')
    for b in books:
        hit(anon, 'GET', f'/book/{b.pk}/', label=f'[{lang}] book {b.pk}')
hit(anon, 'GET', '/book/999999/', expect=(404,), label='book 404')
hit(anon, 'GET', '/favicon.ico')
hit(anon, 'GET', '/api/student-lookup/?q=AA1234567')
hit(anon, 'GET', '/api/student-lookup/')
for url in ['/profile/', '/profile/edit/', '/reports/', '/reports/pdf/', '/librarian/']:
    hit(anon, 'GET', url, expect=(302,), label=f'anon protected {url}')
if books:
    hit(anon, 'POST', f'/book/{books[0].pk}/borrow/', expect=(302,), label='anon borrow redirect')
hit(anon, 'GET', '/admin/login/', label='admin login page')
hit(anon, 'POST', '/i18n/setlang/', expect=(302,), data={'language': 'ru', 'next': '/'}, label='setlang')
hit(anon, 'POST', '/login/', data={'username': 'nobody', 'password': 'x'}, label='login wrong creds')

print("=== 2. Ro'yxatdan o'tish oqimi ===")
r_hemis = hit(anon, 'GET', '/api/student-lookup/?q=AA1234567', expect=(200,), label='hemis lookup AA1234567')
record('hemis lookup found true', r_hemis is not None and b'"found": true' in r_hemis.content.lower(), 'AA1234567 not found')
reg = Client(raise_request_exception=False)
lib = Library.objects.first()
r = hit(reg, 'POST', '/register/', expect=(302,), data={
    'role': 'student', 'first_name': 'Audit', 'last_name': 'Test', 'username': 'audit_user_x',
    'phone': '+998900000000', 'email': 'a@a.uz', 'library': lib.pk if lib else '',
    'password': 'Pass12345', 'password_confirm': 'Pass12345', 'student_id': 'AA1234567',
}, label='register student')
# HEMIS auto-fill when first_name/last_name/faculty/group_name are left blank
hit(Client(raise_request_exception=False), 'POST', '/register/', expect=(302,), data={
    'role': 'student', 'first_name': '', 'last_name': '', 'username': 'audit_hemis_auto',
    'phone': '+998901234567', 'password': 'Pass12345', 'password_confirm': 'Pass12345',
    'student_id': 'AB7654321', 'faculty': '', 'group_name': '',
}, label='register student hemis auto-fill')
hemis_u = CustomUser.objects.filter(username='audit_hemis_auto').first()
record('hemis auto-filled student fields',
       hemis_u is not None and bool(hemis_u.first_name) and bool(hemis_u.faculty) and bool(hemis_u.group_name),
       f'u={hemis_u and (hemis_u.first_name, hemis_u.faculty, hemis_u.group_name)}')
for role in ['pupil', 'citizen']:
    hit(Client(raise_request_exception=False), 'POST', '/register/', expect=(302,), data={
        'role': role, 'first_name': role, 'last_name': 'T', 'username': f'audit_{role}',
        'password': 'Pass12345', 'password_confirm': 'Pass12345', 'library': '',
        'grade': '11', 'grade_letter': 'A', 'parent_phone': '+998901112233',
        'mahalla': 'Navbahor MFY', 'street': 'Mustaqillik', 'house_number': '45-uy', 'occupation': 'Muhandis',
    }, label=f'register {role}')
pupil_u = CustomUser.objects.filter(username='audit_pupil').first()
record('pupil fields saved',
       pupil_u is not None and pupil_u.grade == '11' and pupil_u.grade_letter == 'A' and pupil_u.parent_phone == '+998901112233',
       f'pupil={pupil_u and (pupil_u.grade, pupil_u.grade_letter, pupil_u.parent_phone)}')
citizen_u = CustomUser.objects.filter(username='audit_citizen').first()
record('citizen fields saved',
       citizen_u is not None and citizen_u.mahalla == 'Navbahor MFY' and citizen_u.occupation == 'Muhandis',
       f'citizen={citizen_u and (citizen_u.mahalla, citizen_u.occupation)}')
r_dup = hit(Client(raise_request_exception=False), 'POST', '/register/', expect=(200,), data={
    'username': 'audit_user_x', 'first_name': 'PreservedName', 'password': 'wrong', 'password_confirm': 'wrong'}, label='register duplicate')
record('register error preserves form_data', r_dup is not None and b'PreservedName' in r_dup.content, 'form_data lost')
hit(Client(raise_request_exception=False), 'POST', '/register/', expect=(302,), data={
    'username': 'audit_user_x', 'password': 'Pass12345', 'password_confirm': 'Pass12345'}, label='register duplicate same pass auto-login')
hit(Client(raise_request_exception=False), 'POST', '/login/', expect=(302,), data={
    'username': 'AUDIT_USER_X', 'password': 'Pass12345'}, label='login case-insensitive username')
hit(Client(raise_request_exception=False), 'POST', '/register/', data={
    'username': 'q1', 'password': 'a', 'password_confirm': 'b'}, label='register mismatch')
hit(Client(raise_request_exception=False), 'POST', '/register/', data={
    'username': '', 'password': ''}, label='register empty')
hit(Client(raise_request_exception=False), 'POST', '/register/', data={
    'username': 'x', 'password': 'p', 'library': 'abc'}, expect=(200, 302), label='register bad library id')

print("=== 3. Oddiy foydalanuvchi oqimi ===")
user = CustomUser.objects.filter(username='audit_user_x').first()
uc = Client(raise_request_exception=False)
if user:
    uc.force_login(user)
    for lang in langs:
        uc.cookies['django_language'] = lang
        hit(uc, 'GET', '/', label=f'[{lang}] user home')
        hit(uc, 'GET', '/profile/', label=f'[{lang}] user profile')
        hit(uc, 'GET', '/profile/edit/', label=f'[{lang}] user profile edit')
        hit(uc, 'GET', '/reports/', label=f'[{lang}] user reports')
        for b in books:
            hit(uc, 'GET', f'/book/{b.pk}/', label=f'[{lang}] user book {b.pk}')
    hit(uc, 'GET', '/reports/pdf/', label='reports pdf')
    hit(uc, 'GET', '/reports/excel/', label='reports excel')
    hit(uc, 'GET', '/profile/id-card/pdf/', label='reader id card pdf')
    hit(uc, 'GET', '/profile/certificate/pdf/', label='reader certificate pdf')
    for b in books:
        hit(uc, 'POST', f'/book/{b.pk}/rate/', expect=(302,), data={'rating': '5', 'comment': 'Ajoyib kitob!'}, label=f'rate {b.pk}')
        hit(uc, 'POST', f'/book/{b.pk}/favorite/', expect=(302,), label=f'favorite {b.pk}')
        hit(uc, 'POST', f'/book/{b.pk}/borrow/', expect=(302,), label=f'borrow {b.pk}')
        hit(uc, 'POST', f'/book/{b.pk}/borrow/', expect=(302,), label=f'borrow again {b.pk}')
        hit(uc, 'POST', f'/book/{b.pk}/reserve/', expect=(302,), label=f'reserve {b.pk}')
        hit(uc, 'GET', f'/book/{b.pk}/', label=f'book after borrow {b.pk}')
    hit(uc, 'GET', '/?favorites=1', label='home favorites filter')
    hit(uc, 'POST', '/notifications/read/', expect=(302,), label='mark notifications read')
    hit(uc, 'GET', '/librarian/', expect=(302,), label='student forbidden from librarian desk')

    # Maker-Checker (Oldi-Berdi) tekshiruvi:
    pending_loans = list(Loan.objects.filter(user=user, is_returned=False))
    record('borrow created pending loans', len(pending_loans) > 0, 'no loans created')
    record('borrow pending status', all(l.status == 'borrow_pending' for l in pending_loans), 'not all pending')
    record('6-digit verification code generated', all(l.verification_code and len(l.verification_code) == 6 for l in pending_loans), 'invalid OTP')

    # 1. Talaba pending holatdagi kitob so'rovini bekor qilishi
    first_pending = Loan.objects.filter(user=user, status='borrow_pending').first()
    if first_pending:
        cancel_pk = first_pending.pk
        hit(uc, 'POST', f'/loan/{cancel_pk}/return/', expect=(302,), label=f'student cancel borrow request {cancel_pk}')
        record('cancelled pending loan deleted', not Loan.objects.filter(pk=cancel_pk).exists(), 'loan not deleted')

    # 2. Kutubxonachi paneli orqali olishni tasdiqlash
    su_user = CustomUser.objects.filter(is_superuser=True).first()
    lib_client = Client(raise_request_exception=False)
    if su_user:
        lib_client.force_login(su_user)
        hit(lib_client, 'GET', '/librarian/', label='librarian desk view')
        hit(lib_client, 'GET', '/librarian/?q=audit', label='librarian desk search')
        r_live = hit(lib_client, 'GET', '/api/librarian-live-status/', expect=(200,), label='librarian live status api')
        record('librarian live status json valid', r_live is not None and b'"total_pending"' in r_live.content, 'bad live status json')
        r_mqr = hit(lib_client, 'GET', '/librarian/mobile-qr/', expect=(200,), label='mobile entry qr png')
        record('mobile entry qr valid png', r_mqr is not None and r_mqr.content.startswith(b'\x89PNG'), 'not png')

        # Noto'g'ri kod bilan tasdiqlash rad etilishi kerak
        test_pending = Loan.objects.filter(user=user, status='borrow_pending').first()
        if test_pending:
            hit(lib_client, 'POST', f'/librarian/loan/{test_pending.pk}/approve-borrow/',
                data={'verification_code': '000000'}, expect=(302,), label='approve with wrong OTP')
            test_pending.refresh_from_db()
            record('wrong OTP did not activate loan', test_pending.status == 'borrow_pending', 'activated with bad OTP')

            # Rad etish (Reject) testi
            hit(lib_client, 'POST', f'/librarian/loan/{test_pending.pk}/reject-borrow/', expect=(302,), label='librarian reject borrow')
            record('rejected loan deleted and copy freed', not Loan.objects.filter(pk=test_pending.pk).exists(), 'loan not removed')

        # Qolgan barcha pending so'rovlarni to'g'ri kod bilan tasdiqlash
        for loan in Loan.objects.filter(user=user, status='borrow_pending'):
            hit(lib_client, 'POST', f'/librarian/loan/{loan.pk}/approve-borrow/',
                data={'verification_code': loan.verification_code}, expect=(302,), label=f'librarian approve borrow {loan.pk}')

    record('all remaining loans active', all(l.status == 'active' for l in Loan.objects.filter(user=user, is_returned=False)), 'not active')
    hit(uc, 'GET', '/profile/', label='profile with active approved loans')

    # 3. Talaba topshirish uchun so'rov yuborishi (return_pending)
    for loan in Loan.objects.filter(user=user, status='active'):
        hit(uc, 'POST', f'/loan/{loan.pk}/return/', expect=(302,), label=f'request return {loan.pk}')

    record('loans marked return_pending', all(l.status == 'return_pending' for l in Loan.objects.filter(user=user, is_returned=False)), 'not return_pending')

    # 4. Kutubxonachi kitobni qabul qilib topshirishni tasdiqlashi
    if su_user:
        for loan in Loan.objects.filter(user=user, status='return_pending'):
            hit(lib_client, 'POST', f'/librarian/loan/{loan.pk}/approve-return/',
                data={'verification_code': loan.verification_code}, expect=(302,), label=f'librarian approve return {loan.pk}')

    record('all loans returned', not Loan.objects.filter(user=user, is_returned=False).exists(), 'still active')
    hit(uc, 'GET', '/profile/', label='profile with history')
    other_loan = Loan.objects.exclude(user=user).first()
    if other_loan:
        hit(uc, 'POST', f'/loan/{other_loan.pk}/return/', expect=(404,), label='IDOR return other loan')
    other_res = Reservation.objects.exclude(user=user).first()
    if other_res:
        hit(uc, 'POST', f'/reservation/{other_res.pk}/cancel/', expect=(404,), label='IDOR cancel other res')

    # --- CSRF hujum simulyatsiyasi ---
    evil = Client(enforce_csrf_checks=True, raise_request_exception=False)
    evil.force_login(user)
    b0 = next((b for b in books if b.copies.filter(is_available=True).exists()), books[0] if books else None)
    if b0:
        before = Loan.objects.filter(user=user).count()
        hit(evil, 'GET', f'/book/{b0.pk}/borrow/', expect=(302,), label='CSRF GET borrow ignored')
        record('CSRF GET did not create loan', Loan.objects.filter(user=user).count() == before, 'loan created via GET!')
        hit(evil, 'POST', f'/book/{b0.pk}/borrow/', expect=(403,), label='CSRF POST without token -> 403')
        record('CSRF POST no token did not create loan', Loan.objects.filter(user=user).count() == before, 'loan created!')
        # Haqiqiy brauzer oqimi: sahifadan csrf token olib POST qilish
        page = evil.get(f'/book/{b0.pk}/')
        token = evil.cookies.get('csrftoken')
        if token:
            hit(evil, 'POST', f'/book/{b0.pk}/borrow/', expect=(302,),
                data={'csrfmiddlewaretoken': token.value}, label='real browser borrow with token')
            ln = Loan.objects.filter(user=user, is_returned=False).first()
            record('real borrow created loan', ln is not None, 'no loan')
            if ln:
                evil.get('/profile/')
                hit(evil, 'POST', f'/loan/{ln.pk}/return/', expect=(302,),
                    data={'csrfmiddlewaretoken': evil.cookies['csrftoken'].value}, label='real browser return with token')
        else:
            record('csrf cookie set on book page', False, 'no csrftoken cookie (form missing csrf_token?)')
    hit(evil, 'GET', '/logout/', expect=(302,), label='CSRF GET logout ignored')
    r_prof = evil.get('/profile/')
    record('GET logout did not log out', r_prof.status_code == 200, f'status={r_prof.status_code}')

    # --- Race condition: bazadagi UniqueConstraint ---
    from django.db import IntegrityError, transaction as _tx
    busy_loan = Loan.objects.filter(is_returned=False).first()
    if busy_loan is None:
        cp = BookCopy.objects.filter(is_available=True).first()
        busy_loan = Loan.objects.create(user=user, book_copy=cp) if cp else None
    if busy_loan:
        try:
            with _tx.atomic():
                Loan.objects.bulk_create([Loan(user=user, book_copy=busy_loan.book_copy, is_returned=False)])
            record('DB blocks double active loan', False, 'duplicate active loan inserted!')
        except IntegrityError:
            record('DB blocks double active loan', True)
    hit(uc, 'POST', '/profile/edit/', expect=(302,), data={
        'first_name': '', 'last_name': '', 'annual_goal': 'abc', 'library': 'zz'}, label='profile edit empty (zero data loss)')
    user.refresh_from_db()
    record('zero data loss first_name kept', user.first_name == 'Audit', f'first_name={user.first_name!r}')
    hit(uc, 'POST', '/profile/edit/', expect=(302,), data={'annual_goal': '25', 'role': 'citizen'}, label='profile edit goal')
    import io
    from django.core.files.uploadedfile import SimpleUploadedFile
    fake = SimpleUploadedFile('x.png', b'not-an-image', content_type='image/png')
    hit(uc, 'POST', '/profile/edit/', data={'profile_picture': fake}, label='profile edit fake image rejected')
    try:
        from PIL import Image
        buf = io.BytesIO()
        Image.new('RGB', (40, 40), 'red').save(buf, 'PNG')
        real = SimpleUploadedFile('r.png', buf.getvalue(), content_type='image/png')
        hit(uc, 'POST', '/profile/edit/', expect=(302,), data={'profile_picture': real}, label='profile edit real image')
        hit(uc, 'GET', '/profile/', label='profile with avatar')
        hit(uc, 'GET', '/', label='home with avatar')
    except Exception as exc:
        record('real image upload', False, repr(exc))
    for res in Reservation.objects.filter(user=user):
        hit(uc, 'POST', f'/reservation/{res.pk}/cancel/', expect=(302,), label=f'cancel res {res.pk}')
    hit(uc, 'POST', '/logout/', expect=(302,), label='logout')
    r_after = uc.get('/profile/')
    record('POST logout really logs out', r_after.status_code == 302, f'status={r_after.status_code}')
    hit(Client(raise_request_exception=False), 'POST', '/register/', data={
        'username': 'x_lib', 'password': 'p', 'library': '99999'}, expect=(302,), label='register nonexistent library id')
    hit(Client(raise_request_exception=False), 'POST', '/register/', data={
        'username': 'x_role', 'password': 'p', 'role': 'hacker'}, expect=(302,), label='register invalid role')
    xr = CustomUser.objects.filter(username='x_role').first()
    record('invalid role sanitized', xr is not None and xr.role == 'student', f'role={getattr(xr, "role", None)}')

print("=== 4. Admin panel (superuser) ===")
su = CustomUser.objects.filter(is_superuser=True).first()
ac = Client(raise_request_exception=False)
if su:
    ac.force_login(su)
    hit(ac, 'GET', '/admin/', label='admin index')
    for model, model_admin in admin.site._registry.items():
        app, name = model._meta.app_label, model._meta.model_name
        base = f'/admin/{app}/{name}/'
        hit(ac, 'GET', base, label=f'admin list {app}.{name}')
        hit(ac, 'GET', base + '?q=a', label=f'admin search {app}.{name}')
        hit(ac, 'GET', base + 'add/', label=f'admin add {app}.{name}')
        for obj in model.objects.all()[:3]:
            hit(ac, 'GET', f'{base}{obj.pk}/change/', label=f'admin change {app}.{name}.{obj.pk}')
            hit(ac, 'GET', f'{base}{obj.pk}/history/', label=f'admin history {app}.{name}.{obj.pk}')
        # filtrlar
        for f in getattr(model_admin, 'list_filter', ()):
            if isinstance(f, str):
                hit(ac, 'GET', base + f'?{f}__isnull=False', expect=(200, 302), label=f'admin filter {app}.{name}.{f}')
    for lang in langs:
        ac.cookies['django_language'] = lang
        hit(ac, 'GET', '/admin/', label=f'[{lang}] admin index')
        hit(ac, 'GET', '/', label=f'[{lang}] admin user home')
        hit(ac, 'GET', '/profile/', label=f'[{lang}] admin profile')
        hit(ac, 'GET', '/reports/', label=f'[{lang}] admin reports')

    # Admin orqali kitob qo'shish (QR + nusxalar generatsiyasi)
    g = Genre.objects.first()
    resp = hit(ac, 'POST', '/admin/books/book/add/', expect=(302,), data={
        'library': lib.pk if lib else '', 'title': 'Audit Kitob', 'author': 'Audit Muallif',
        'genre': g.pk if g else '', 'annotation': 'x', 'isbn': '', 'udc': '', 'bbk': '',
        'publisher': 'P', 'published_year': '2024', 'pages': '100', 'price': '0',
        'total_copies_count': '3',
        'copies-TOTAL_FORMS': '0', 'copies-INITIAL_FORMS': '0',
        'copies-MIN_NUM_FORMS': '0', 'copies-MAX_NUM_FORMS': '1000',
    }, label='admin add book')
    if resp is not None and resp.status_code == 200:
        ctx = getattr(resp, 'context', None)
        try:
            errs = [f.errors for f in ctx['adminform'].form] if ctx else []
            print('    form errors:', ctx['adminform'].form.errors, ctx.get('inline_admin_formsets'))
        except Exception:
            pass
    nb = Book.objects.filter(title='Audit Kitob').first()
    record('admin add book -> 3 copies', bool(nb) and nb.copies.count() == 3,
           f'copies={nb.copies.count() if nb else None}')
    record('admin add book -> QR', bool(nb) and bool(nb.qr_code), 'qr missing')
    if nb:
        hit(anon, 'GET', f'/book/{nb.pk}/', label='new book detail')

    # Admin orqali ijara (Loan) qo'shish
    free_copy = BookCopy.objects.filter(is_available=True).first()
    if free_copy:
        resp = hit(ac, 'POST', '/admin/books/loan/add/', expect=(302,), data={
            'user': su.pk, 'book_copy': free_copy.pk, 'status': 'active',
            'borrowed_at_0': '2026-10-01', 'borrowed_at_1': '10:00:00',
            'due_date_0': '2026-10-05', 'due_date_1': '10:00:00',
        }, label='admin add loan (overdue)')
        if resp is not None and resp.status_code == 200:
            ctx = getattr(resp, 'context', None)
            if ctx and 'adminform' in ctx:
                print('    loan form errors:', ctx['adminform'].form.errors)
        busy = BookCopy.objects.filter(is_available=False).first()
        if busy:
            r2 = hit(ac, 'POST', '/admin/books/loan/add/', expect=(200,), data={
                'user': su.pk, 'book_copy': busy.pk, 'status': 'active',
                'borrowed_at_0': '2026-10-01', 'borrowed_at_1': '10:00:00',
                'due_date_0': '2026-10-05', 'due_date_1': '10:00:00',
            }, label='admin add loan on busy copy -> validation')
    hit(ac, 'GET', '/reports/', label='reports with overdue')
    hit(ac, 'GET', '/reports/pdf/', label='reports pdf with overdue')
    hit(ac, 'GET', '/profile/', label='admin profile with overdue')
    for b in Book.objects.all():
        hit(ac, 'GET', f'/book/{b.pk}/', label=f'book final {b.pk}')
        hit(ac, 'GET', f'/book/{b.pk}/read/', label=f'book interactive reader {b.pk}')

    # Module 1: Telegram Chat ID & Test Ping
    hit(ac, 'POST', '/profile/edit/', expect=(302,), data={'telegram_chat_id': '9988776655'}, label='save telegram_chat_id')
    su.refresh_from_db()
    record('telegram_chat_id saved', su.telegram_chat_id == '9988776655', f'val={su.telegram_chat_id}')
    hit(ac, 'POST', '/profile/telegram-test/', expect=(302,), label='telegram test ping')

    # Module 3: Overdue Debtor Borrow Block & Librarian Overdue Reminder
    overdue_ln = Loan.objects.filter(user=su, is_returned=False).first()
    if overdue_ln:
        record('overdue_days > 0', overdue_ln.overdue_days > 0, f'days={overdue_ln.overdue_days}')
        record('penalty_points > 0', overdue_ln.penalty_points > 0, f'penalty={overdue_ln.penalty_points}')
        other_book = Book.objects.exclude(pk=overdue_ln.book_copy.book_id).first()
        if other_book:
            before_cnt = Loan.objects.filter(user=su, is_returned=False).count()
            hit(ac, 'POST', f'/book/{other_book.pk}/borrow/', expect=(302,), label='debtor borrow blocked')
            after_cnt = Loan.objects.filter(user=su, is_returned=False).count()
            record('debtor blocked from new borrow', before_cnt == after_cnt, f'{before_cnt} vs {after_cnt}')
        hit(ac, 'POST', f'/librarian/loan/{overdue_ln.pk}/remind/', expect=(302,), label='librarian remind single overdue')
        hit(ac, 'POST', '/librarian/overdue/remind-all/', expect=(302,), label='librarian remind all overdue')

    # Module 5: Barcode (Code128) + QR Stickers A4 PDF
    first_book = Book.objects.first()
    if first_book:
        r_stk = hit(ac, 'GET', f'/book/{first_book.pk}/stickers/pdf/', expect=(200,), label='book stickers pdf')
        record('book stickers pdf valid', r_stk is not None and r_stk.content.startswith(b'%PDF'), 'not PDF')
    r_all_stk = hit(ac, 'GET', '/librarian/stickers/pdf/', expect=(200,), label='librarian all stickers pdf')
    record('librarian stickers pdf valid', r_all_stk is not None and r_all_stk.content.startswith(b'%PDF'), 'not PDF')
    hit(ac, 'GET', '/librarian/', expect=(200,), label='librarian desk with overdue tab')

    # Module 4: ISBN Auto-Lookup, Quick Add & Bulk Excel/CSV Import
    r_isbn = hit(ac, 'GET', '/api/isbn-lookup/?isbn=9789943231009', expect=(200,), label='isbn lookup api')
    record('isbn lookup found', r_isbn is not None and b'"found": true' in r_isbn.content.lower(), 'isbn not found')
    hit(ac, 'POST', '/librarian/books/quick-add/', expect=(302,), data={
        'isbn': '9780132350884', 'title': 'Clean Code', 'author': 'Robert C. Martin',
        'genre_name': 'Dasturlash', 'publisher': 'Prentice Hall', 'published_year': '2023',
        'pages': '464', 'total_copies_count': '2', 'annotation': 'Agile craftsmanship',
    }, label='librarian quick add book')
    record('quick add book created', Book.objects.filter(title='Clean Code').exists(), 'Clean Code missing')
    r_tpl = hit(ac, 'GET', '/librarian/import/template/', expect=(200,), label='librarian import template xlsx')
    record('import template valid xlsx', r_tpl is not None and r_tpl.content.startswith(b'PK'), 'not xlsx')
    csv_bytes = "Kitob nomi,Muallif,Janr,ISBN,UO'K,BBK,Nashriyot,Nashr yili,Betlar,Nusxalar soni,Annotatsiya\nPragmatic Programmer,Andrew Hunt,Dasturlash,9780201616224,004,32.9,Addison,2024,352,2,Amaliy dasturlash\n".encode('utf-8')
    csv_upload = SimpleUploadedFile('books.csv', csv_bytes, content_type='text/csv')
    hit(ac, 'POST', '/librarian/import/', expect=(302,), data={'import_file': csv_upload}, label='librarian bulk import csv')
    record('bulk import created book', Book.objects.filter(title='Pragmatic Programmer').exists(), 'Pragmatic Programmer missing')

    # Module 6: Librarian Fast Scanner-Terminal (Kiosk) & Immutable AuditLog
    hit(ac, 'GET', '/librarian/terminal/', expect=(200,), label='librarian terminal get')
    if overdue_ln:
        inv_num = overdue_ln.book_copy.inventory_number
        hit(ac, 'POST', '/librarian/terminal/', expect=(200,), data={'scan_code': inv_num}, label='terminal scan return')
        overdue_ln.refresh_from_db()
        record('terminal scan returned overdue loan', overdue_ln.is_returned, f'is_returned={overdue_ln.is_returned}')

    # Module 7: PWA Manifest, Service Worker, Dynamic Icons & Offline Page
    r_man = hit(anon, 'GET', '/manifest.json', expect=(200,), label='pwa manifest.json')
    record('pwa manifest valid', r_man is not None and b'"SmartLib"' in r_man.content, 'invalid manifest')
    r_sw = hit(anon, 'GET', '/sw.js', expect=(200,), label='pwa service worker sw.js')
    record('pwa sw valid', r_sw is not None and b'CACHE_NAME' in r_sw.content, 'invalid sw.js')
    r_ic192 = hit(anon, 'GET', '/pwa-icon/192/', expect=(200,), label='pwa icon 192')
    record('pwa icon 192 valid png', r_ic192 is not None and r_ic192.content.startswith(b'\x89PNG'), 'not png')
    r_ic512 = hit(anon, 'GET', '/pwa-icon/512/', expect=(200,), label='pwa icon 512')
    record('pwa icon 512 valid png', r_ic512 is not None and r_ic512.content.startswith(b'\x89PNG'), 'not png')
    hit(anon, 'GET', '/offline/', expect=(200,), label='pwa offline page')

    # Module 8: Enhanced Analytics, Telegram Webhook Gateway & Live Backup Download
    r_rep_xl = hit(ac, 'GET', '/reports/excel/', expect=(200,), label='reports excel export')
    record('reports excel valid PK', r_rep_xl is not None and r_rep_xl.content.startswith(b'PK'), 'invalid excel')
    hit(anon, 'GET', '/api/telegram-webhook/', expect=(200,), label='telegram webhook get')
    tg_webhook_payload = json.dumps({
        'update_id': 9999,
        'message': {
            'message_id': 1,
            'chat': {'id': 123456789},
            'from': {'id': 123456789, 'username': 'test_reader'},
            'text': '/kitob python'
        }
    })
    r_tg_post = hit(anon, 'POST', '/api/telegram-webhook/', expect=(200,), data=tg_webhook_payload, content_type='application/json', label='telegram webhook post /kitob')
    record('telegram webhook post json ok', r_tg_post is not None and b'"ok": true' in r_tg_post.content.lower(), 'webhook fail')
    r_bkp = hit(ac, 'GET', '/librarian/backup/download/', expect=(200,), label='librarian backup download')
    record('backup download sql valid', r_bkp is not None and len(r_bkp.content) > 100, 'backup empty')
    try:
        call_command('send_due_reminders')
        record('send_due_reminders command', True)
    except Exception as exc:
        record('send_due_reminders command', False, str(exc))
    try:
        call_command('backup_database')
        record('backup_database command', True)
    except Exception as exc:
        record('backup_database command', False, str(exc))

print("=== 5. Ma'lumotlar yaxlitligi ===")
for c in BookCopy.objects.all():
    active = c.loans.filter(is_returned=False).exists()
    if c.is_available == active:
        record(f'copy {c.inventory_number} availability', False, f'is_available={c.is_available} active_loan={active}')
dups = Loan.objects.filter(is_returned=False).values('book_copy').order_by()
from django.db.models import Count  # noqa: E402
dup = dups.annotate(n=Count('id')).filter(n__gt=1)
record('no double active loans', not dup.exists(), str(list(dup)))
for b in Book.objects.all():
    if b.qr_code:
        record(f'qr file exists book {b.pk}', os.path.isfile(b.qr_code.path), b.qr_code.path)

print()
print(f"=== NATIJA: {OK[0]} ta OK, {len(FAILS)} ta XATO ===")
for f in FAILS:
    print(' -', f.splitlines()[0])
sys.exit(1 if FAILS else 0)
