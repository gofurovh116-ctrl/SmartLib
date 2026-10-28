import csv
import io
import json
import os
import urllib.request
import urllib.parse
import zipfile
from datetime import timedelta
from xml.sax.saxutils import escape as xml_escape
import qrcode
from PIL import Image, ImageDraw
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from users.models import CustomUser, Library, StudentBase
from .models import Book, BookCopy, Genre, Loan, Reservation, Review, Favorite, Notification, AuditLog
from .telegram_service import (
    notify_borrow_request,
    notify_borrow_approved,
    notify_return_approved,
    notify_reservation_available,
    notify_overdue_reminder,
    send_telegram_message,
    get_bot_username,
)


def _safe_library_id(raw):
    """Foydalanuvchidan kelgan library ID ni xavfsiz tekshiradi.
    Faqat bazada haqiqatan mavjud bo'lgan kutubxona ID sini qaytaradi, aks holda None.
    (ValueError / IntegrityError -> 500 xatolarining oldini oladi)"""
    raw = str(raw or '').strip()
    if not raw.isdigit():
        return None
    lib_id = int(raw)
    return lib_id if Library.objects.filter(pk=lib_id).exists() else None


def favicon_view(request):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36">'
        '<rect x="6" y="6" width="12" height="24" rx="2" fill="#3B5BDB"/>'
        '<rect x="18" y="8" width="12" height="22" rx="2" fill="#3BC9DB"/>'
        '</svg>'
    )
    return HttpResponse(svg, content_type='image/svg+xml')


DEMO_HEMIS_STUDENTS = {
    'AA1234567': {
        'passport_id': 'AA1234567',
        'first_name': 'Javohir',
        'last_name': 'Tursunov',
        'group': '214-21 Dasturiy injiniring',
        'faculty': 'Dasturiy injiniring va raqamli texnologiyalar',
    },
    'AB7654321': {
        'passport_id': 'AB7654321',
        'first_name': 'Madina',
        'last_name': 'Karimova',
        'group': '102-22 Kiberxavfsizlik',
        'faculty': 'Axborot xavfsizligi fakulteti',
    },
    'AD9988776': {
        'passport_id': 'AD9988776',
        'first_name': 'Sardor',
        'last_name': 'Aliyev',
        'group': '305-20 Sun\'iy intellekt',
        'faculty': 'Kompyuter injiniringi fakulteti',
    },
}


def _resolve_student_base(code):
    q = (code or '').strip()[:50]
    if not q:
        return None
    student = StudentBase.objects.filter(passport_id__iexact=q).first()
    if student:
        return student
    demo = DEMO_HEMIS_STUDENTS.get(q.upper())
    if demo:
        student, _ = StudentBase.objects.get_or_create(
            passport_id=demo['passport_id'],
            defaults={
                'first_name': demo['first_name'],
                'last_name': demo['last_name'],
                'group': demo['group'],
                'faculty': demo['faculty'],
            },
        )
        return student
    return None


def student_lookup_api(request):
    q = request.GET.get('q', '').strip()[:50]
    if not q:
        return JsonResponse({'found': False})
    student = _resolve_student_base(q)
    if student:
        return JsonResponse({
            'found': True,
            'passport_id': student.passport_id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'group': student.group,
            'faculty': student.faculty,
        })
    return JsonResponse({'found': False})


def _build_books_3d_json(books_iterable):
    spine_palette = [
        '#8B261D', '#2D5A43', '#8C5A2B', '#234567', '#5E2B4E',
        '#7A3E1D', '#1F4B3F', '#6B4423', '#3A284B', '#923C24',
    ]
    items = []
    for idx, b in enumerate(books_iterable):
        avail = b.available_copies_count
        tot = b.total_copies
        items.append({
            'id': b.pk,
            'title': b.title,
            'author': b.author,
            'genre': b.genre.name if b.genre else "Adabiyot",
            'isbn': b.isbn or f"978-9943-{b.pk:04d}-1",
            'pages': b.pages or 320,
            'year': b.published_year or 2024,
            'available': avail,
            'total': tot,
            'annotation': (b.annotation or "SmartLib elektron va bosma fondidagi nodir asar.")[:180],
            'color': spine_palette[idx % len(spine_palette)],
            'detail_url': reverse('book_detail', args=[b.pk]),
            'read_url': reverse('book_read', args=[b.pk]),
        })
    if not items:
        items = [
            {
                'id': 1,
                'title': "O'tkan kunlar",
                'author': "Abdulla Qodiriy",
                'genre': "O'zbek klassikasi",
                'isbn': "978-9943-2310-0-9",
                'pages': 384,
                'year': 2024,
                'available': 5,
                'total': 5,
                'annotation': "O'zbek romanchiligining asoschisi Abdulla Qodiriyning o'lmas tarixiy-badiiy shoh asari.",
                'color': '#8B261D',
                'detail_url': '/',
                'read_url': '/',
            }
        ]
    return json.dumps(items)


def reading_room_view(request):
    books_qs = list(Book.objects.select_related('genre', 'library').prefetch_related('copies', 'reviews').all()[:36])
    return render(request, 'reading_room.html', {
        'books': books_qs,
        'books_3d_json': _build_books_3d_json(books_qs),
        'total_books_count': Book.objects.count(),
        'total_copies_count': BookCopy.objects.count(),
    })


def home_view(request):
    query = request.GET.get('q', '').strip()
    genre_id = request.GET.get('genre', '').strip()
    library_id = request.GET.get('library', '').strip()
    only_favorites = request.GET.get('favorites', '').strip() == '1'

    books_qs = Book.objects.select_related('genre', 'library').prefetch_related('copies', 'reviews').all()

    if query:
        books_qs = books_qs.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(isbn__icontains=query)
        )
    if genre_id.isdigit():
        books_qs = books_qs.filter(genre_id=int(genre_id))
    if library_id.isdigit():
        books_qs = books_qs.filter(library_id=int(library_id))

    favorite_book_ids = set()
    if request.user.is_authenticated:
        favorite_book_ids = set(
            Favorite.objects.filter(user=request.user).values_list('book_id', flat=True)
        )
        if only_favorites:
            books_qs = books_qs.filter(id__in=favorite_book_ids)

    # Eng faol kitobxonlar (o'qib qaytarilgan kitoblar bo'yicha, dublikatsiz)
    top_readers = list(
        CustomUser.objects
        .annotate(
            books_read_count=Count(
                'loans',
                filter=Q(loans__is_returned=True),
                distinct=True,
            )
        )
        .filter(books_read_count__gt=0)
        .order_by('-books_read_count')[:4]
    )
    for r in top_readers:
        r.rank_info = r.get_reader_rank(r.books_read_count)

    books_list = list(books_qs)
    context = {
        'books': books_list,
        'books_3d_json': _build_books_3d_json(books_list[:24]),
        'top_readers': top_readers,
        'genres': Genre.objects.all(),
        'libraries': Library.objects.all(),
        'query': query,
        'selected_genre': int(genre_id) if genre_id.isdigit() else None,
        'selected_library': int(library_id) if library_id.isdigit() else None,
        'favorite_book_ids': favorite_book_ids,
        'only_favorites': only_favorites,
    }
    return render(request, 'home.html', context)


def book_detail_view(request, pk):
    book = get_object_or_404(
        Book.objects.select_related('genre', 'library').prefetch_related('copies', 'reviews__user'),
        pk=pk,
    )
    available_count = book.available_copies_count
    total_count = book.total_copies
    reviews = list(book.reviews.all())

    user_has_active_loan = False
    user_loan = None
    user_has_reservation = False
    is_favorited = False
    user_review = None
    user_is_debtor = False
    if request.user.is_authenticated:
        user_loan = Loan.objects.filter(
            user=request.user,
            book_copy__book=book,
            is_returned=False,
        ).first()
        user_has_active_loan = user_loan is not None
        user_has_reservation = Reservation.objects.filter(
            user=request.user,
            book=book,
        ).exists()
        is_favorited = Favorite.objects.filter(user=request.user, book=book).exists()
        user_is_debtor = request.user.is_debtor
        for rev in reviews:
            if rev.user_id == request.user.id:
                user_review = rev
                break

    base_public = _get_public_tunnel_url() or f"http://{_get_local_lan_ip()}:8000"
    book_qr_target_url = f"{base_public.rstrip('/')}/book/{book.pk}/"

    context = {
        'book': book,
        'book_qr_target_url': book_qr_target_url,
        'available_count': available_count,
        'total_count': total_count,
        'user_has_active_loan': user_has_active_loan,
        'user_loan': user_loan,
        'user_has_reservation': user_has_reservation,
        'user_is_debtor': user_is_debtor,
        'is_librarian_or_admin': _is_librarian_or_admin(request.user),
        'reviews': reviews,
        'user_review': user_review,
        'is_favorited': is_favorited,
        'average_rating': book.average_rating,
        'reviews_count': len(reviews),
    }
    return render(request, 'book_detail.html', context)


def _require_post(request, fallback_url):
    """CSRF himoyasi: holatni o'zgartiruvchi amallar faqat POST + csrf_token bilan bajariladi.
    GET kelsa (masalan login'dan keyingi ?next= qaytish yoki begona saytdagi <img src>),
    hech narsa o'zgartirilmaydi - foydalanuvchi xavfsiz sahifaga yo'naltiriladi."""
    if request.method != 'POST':
        return redirect(fallback_url)
    return None


def _is_librarian_or_admin(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, 'status', '') in ('librarian', 'admin')))


def _client_ip(request):
    if not request:
        return "127.0.0.1"
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()[:64]
    return (request.META.get('REMOTE_ADDR') or '127.0.0.1')[:64]


def log_audit(request, action, target, details="", actor=None):
    """Module 6: O'zgarmas Xavfsizlik va Audit Jurnali yozuvi."""
    try:
        resolved_actor = actor
        if resolved_actor is None and request and getattr(request, 'user', None) and request.user.is_authenticated:
            resolved_actor = request.user
        AuditLog.objects.create(
            actor=resolved_actor,
            action=action,
            target=str(target)[:255],
            details=str(details)[:1000],
            ip_address=_client_ip(request),
        )
    except Exception:
        pass


@login_required
def borrow_book_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    blocked = _require_post(request, book_detail_url(book.pk))
    if blocked:
        return blocked

    try:
        with transaction.atomic():
            # Module 3: Qarzdorlik va Intizom nazorati — muddati o'tgan kitobi bor foydalanuvchiga yangi kitob berilmaydi!
            overdue_loan = (
                Loan.objects.filter(
                    user=request.user,
                    is_returned=False,
                    status__in=['active', 'return_pending'],
                    due_date__lt=timezone.now(),
                )
                .select_related('book_copy__book')
                .first()
            )
            if overdue_loan:
                messages.error(
                    request,
                    f"⛔ Sizda muddati o'tgan kitob mavjud («{overdue_loan.book_copy.book.title}», {overdue_loan.overdue_days} kun kechikkan, -{overdue_loan.penalty_points} XP jarima). Yangi kitob olish uchun avval qarzdorlikni yoping!",
                )
                return redirect('profile')

            already_borrowed = Loan.objects.filter(
                user=request.user,
                book_copy__book=book,
                is_returned=False,
            ).select_related('book_copy').first()

            if already_borrowed:
                if already_borrowed.status == 'borrow_pending':
                    messages.info(
                        request,
                        f"\"{book.title}\" kitobini olish uchun so'rovingiz mavjud! Tasdiqlash kodi: {already_borrowed.verification_code}. Kutubxonachiga ko'rsating.",
                    )
                else:
                    messages.info(
                        request,
                        f"Sizda \"{book.title}\" kitobi allaqachon mavjud (Inventar: {already_borrowed.book_copy.inventory_number}).",
                    )
                return redirect('profile')

            available_copy = (
                book.copies
                .select_for_update()
                .filter(is_available=True)
                .order_by('id')
                .first()
            )

            if not available_copy:
                messages.error(request, "Kechirasiz, hozirda ushbu kitobning bo'sh nusxasi qolmagan.")
                return redirect('book_detail', pk=book.pk)

            loan = Loan.objects.create(
                user=request.user,
                book_copy=available_copy,
                status='borrow_pending',
                borrowed_at=timezone.now(),
                is_returned=False,
            )
            Reservation.objects.filter(user=request.user, book=book).delete()
            Notification.objects.create(
                user=request.user,
                title="Kitob olish so'rovi yuborildi",
                message=f"\"{book.title}\" (Inv: {available_copy.inventory_number}) uchun so'rov yuborildi. Tasdiqlash kodi: {loan.verification_code}. Kutubxonachiga ko'rsatib kitobni qabul qiling.",
                link="/profile/",
            )
            # Kutubxonachilarga bildirishnoma
            librarians = CustomUser.objects.filter(
                Q(is_staff=True) | Q(is_superuser=True) | Q(status__in=['librarian', 'admin'])
            ).distinct()[:10]
            for lib_user in librarians:
                if lib_user != request.user:
                    Notification.objects.create(
                        user=lib_user,
                        title="Yangi kitob olish so'rovi",
                        message=f"{request.user.full_display_name} \"{book.title}\" ({available_copy.inventory_number}) kitobini so'radi. Kod: {loan.verification_code}",
                        link="/librarian/",
                    )
            notify_borrow_request(loan, librarians)
            log_audit(
                request,
                'BORROW_REQUEST',
                f"{book.title} ({available_copy.inventory_number})",
                f"Kitobxon: {request.user.username} | Kod: {loan.verification_code}",
            )
    except (IntegrityError, OperationalError):
        messages.error(request, "Bu nusxa hozirgina boshqa kitobxonga berildi. Iltimos, qayta urinib ko'ring.")
        return redirect('book_detail', pk=book.pk)

    messages.info(
        request,
        f"\"{book.title}\" kitobini olish uchun so'rov yuborildi! Tasdiqlash kodi: {loan.verification_code}. Kutubxonachidan tasdiqlatib oling.",
    )
    return redirect('profile')


def book_detail_url(pk):
    return reverse('book_detail', kwargs={'pk': pk})


@login_required
def return_book_view(request, loan_id):
    blocked = _require_post(request, reverse('profile'))
    if blocked:
        return blocked
    with transaction.atomic():
        loan = get_object_or_404(Loan.objects.select_related('book_copy__book'), pk=loan_id, user=request.user)
        if loan.is_returned:
            messages.info(request, "Ushbu kitob allaqachon topshirilgan.")
            return redirect('profile')

        if loan.status == 'borrow_pending':
            book_title = loan.book_copy.book.title
            loan.delete()
            messages.info(request, f"\"{book_title}\" kitobini olish so'rovi bekor qilindi.")
            return redirect('profile')

        if loan.status == 'active':
            loan.status = 'return_pending'
            if not loan.verification_code:
                loan.verification_code = loan.generate_code()
            loan.save()
            Notification.objects.create(
                user=request.user,
                title="Kitob topshirish so'rovi yuborildi",
                message=f"\"{loan.book_copy.book.title}\" kitobini topshirish kodi: {loan.verification_code}. Kitobni kutubxonachiga topshiring.",
                link="/profile/",
            )
            librarians = CustomUser.objects.filter(
                Q(is_staff=True) | Q(is_superuser=True) | Q(status__in=['librarian', 'admin'])
            ).distinct()[:10]
            for lib_user in librarians:
                if lib_user != request.user:
                    Notification.objects.create(
                        user=lib_user,
                        title="Kitob qaytarish so'rovi",
                        message=f"{request.user.full_display_name} \"{loan.book_copy.book.title}\" kitobini qaytarmoqda. Kod: {loan.verification_code}",
                        link="/librarian/",
                    )
            messages.info(
                request,
                f"\"{loan.book_copy.book.title}\" kitobini topshirish so'rovi yuborildi! Tasdiqlash kodi: {loan.verification_code}. Kitobni kutubxonachiga bering — kutubxonachi tasdiqlagach ijara yopiladi.",
            )
        elif loan.status == 'return_pending':
            messages.info(
                request,
                f"Kutubxonachi tasdig'i kutilmoqda. Tasdiqlash kodi: {loan.verification_code}. Kitobni kutubxonachiga topshiring.",
            )
    return redirect('profile')


@login_required
def librarian_desk_view(request):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ushbu sahifaga faqat kutubxonachi yoki administratorlar kirishi mumkin.")
        return redirect('home')

    q = request.GET.get('q', '').strip()
    pending_borrows_qs = (
        Loan.objects
        .filter(is_returned=False, status='borrow_pending')
        .select_related('user', 'book_copy__book')
        .order_by('-borrowed_at')
    )
    pending_returns_qs = (
        Loan.objects
        .filter(is_returned=False, status='return_pending')
        .select_related('user', 'book_copy__book')
        .order_by('-borrowed_at')
    )
    active_loans_qs = (
        Loan.objects
        .filter(is_returned=False, status='active')
        .select_related('user', 'book_copy__book')
        .order_by('due_date')
    )
    overdue_loans_qs = (
        Loan.objects
        .filter(is_returned=False, status__in=['active', 'return_pending'], due_date__lt=timezone.now())
        .select_related('user', 'book_copy__book', 'issued_by')
        .order_by('due_date')
    )
    completed_loans_qs = (
        Loan.objects
        .filter(is_returned=True)
        .select_related('user', 'book_copy__book', 'issued_by', 'received_by')
        .order_by('-returned_at')[:25]
    )

    if q:
        query_filter = (
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(book_copy__book__title__icontains=q) |
            Q(book_copy__inventory_number__icontains=q) |
            Q(verification_code__icontains=q)
        )
        pending_borrows_qs = pending_borrows_qs.filter(query_filter)
        pending_returns_qs = pending_returns_qs.filter(query_filter)
        active_loans_qs = active_loans_qs.filter(query_filter)
        overdue_loans_qs = overdue_loans_qs.filter(query_filter)

    pb_count = Loan.objects.filter(is_returned=False, status='borrow_pending').count()
    pr_count = Loan.objects.filter(is_returned=False, status='return_pending').count()
    al_count = Loan.objects.filter(is_returned=False, status='active').count()
    od_count = Loan.objects.filter(is_returned=False, status__in=['active', 'return_pending'], due_date__lt=timezone.now()).count()

    lan_ip = _get_local_lan_ip()
    lan_url = f"http://{lan_ip}:8000"
    public_url = _get_public_tunnel_url() or lan_url

    context = {
        'pending_borrows': pending_borrows_qs,
        'pending_returns': pending_returns_qs,
        'active_loans': active_loans_qs,
        'overdue_loans': overdue_loans_qs,
        'completed_loans': completed_loans_qs,
        'pending_borrows_count': pb_count,
        'pending_returns_count': pr_count,
        'active_loans_count': al_count,
        'overdue_loans_count': od_count,
        'search_query': q,
        'genres': Genre.objects.all(),
        'libraries': Library.objects.all(),
        'recent_audit_logs': AuditLog.objects.select_related('actor').all()[:30],
        'lan_url': lan_url,
        'public_url': public_url,
    }
    return render(request, 'librarian_desk.html', context)


def _get_local_lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return '127.0.0.1'


def _get_public_tunnel_url():
    try:
        from django.conf import settings as _s
        pub_file = os.path.join(_s.BASE_DIR, 'backups', 'public_url.txt')
        if os.path.isfile(pub_file):
            with open(pub_file, 'r', encoding='utf-8') as f:
                url = f.read().strip()
                if url.startswith('http'):
                    return url
    except Exception:
        pass
    return os.environ.get('SMARTLIB_PUBLIC_URL', '').strip()


def librarian_live_status_api(request):
    """Kompyuterdagi Kutubxonachi va telefondagi Kitobxon o'rtasida jonli (Real-Time) sinxronizatsiya API."""
    pb = Loan.objects.filter(is_returned=False, status='borrow_pending').count()
    pr = Loan.objects.filter(is_returned=False, status='return_pending').count()
    al = Loan.objects.filter(is_returned=False, status='active').count()
    user_sig = ""
    if request.user.is_authenticated:
        u_loans = list(
            Loan.objects.filter(user=request.user, is_returned=False)
            .values_list('id', 'status')
            .order_by('id')
        )
        user_sig = "|".join(f"{lid}:{st}" for lid, st in u_loans)
    resp = JsonResponse({
        'pending_borrows': pb,
        'pending_returns': pr,
        'active_loans': al,
        'total_pending': pb + pr,
        'user_signature': user_sig,
        'public_url': _get_public_tunnel_url() or f"http://{_get_local_lan_ip()}:8000",
    })
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


def mobile_entry_qr_png_view(request):
    """Kitobxonlar telefon kamerasi orqali skanerlab kirishi uchun QR-kod generatori."""
    target_url = request.GET.get('url', '').strip()
    if not target_url:
        target_url = _get_public_tunnel_url() or f"http://{_get_local_lan_ip()}:8000"
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1e1b4b", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


@login_required
def librarian_approve_borrow_view(request, loan_id):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ruxsat etilmagan amal!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    with transaction.atomic():
        loan = get_object_or_404(
            Loan.objects.select_related('book_copy__book', 'user'),
            pk=loan_id,
            is_returned=False,
            status='borrow_pending'
        )
        entered_code = request.POST.get('verification_code', '').strip()
        if entered_code and entered_code != loan.verification_code:
            messages.error(request, f"Noto'g'ri kod kiritildi! Kutilgan kod: {loan.verification_code}")
            return redirect('librarian_desk')

        loan.status = 'active'
        loan.issued_by = request.user
        loan.borrowed_at = timezone.now()
        loan.due_date = timezone.now() + timedelta(days=10)
        loan.save()

        Notification.objects.create(
            user=loan.user,
            title="Kitob berilishi tasdiqlandi",
            message=f"«{loan.book_copy.book.title}» (Inv: {loan.book_copy.inventory_number}) kitobi kutubxonachi ({request.user.full_display_name}) tomonidan berildi. Topshirish muddati: {loan.due_date.strftime('%d.%m.%Y')}.",
            link="/profile/",
        )
        notify_borrow_approved(loan)
        log_audit(
            request,
            'BORROW_APPROVED',
            f"{loan.book_copy.book.title} ({loan.book_copy.inventory_number})",
            f"Kitobxonga berildi: {loan.user.username} | Muddat: {loan.due_date.strftime('%d.%m.%Y')}",
        )
        messages.info(
            request,
            f"✅ «{loan.book_copy.book.title}» kitobi {loan.user.full_display_name}ga muvaffaqiyatli berildi! (Muddat: {loan.due_date.strftime('%d.%m.%Y')})",
        )
    return redirect('librarian_desk')


@login_required
def librarian_reject_borrow_view(request, loan_id):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ruxsat etilmagan amal!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    with transaction.atomic():
        loan = get_object_or_404(
            Loan.objects.select_related('book_copy__book', 'user'),
            pk=loan_id,
            is_returned=False,
            status='borrow_pending'
        )
        book_title = loan.book_copy.book.title
        student = loan.user
        loan.delete()

        Notification.objects.create(
            user=student,
            title="Kitob so'rovi rad etildi",
            message=f"«{book_title}» kitobini olish so'rovi kutubxonachi tomonidan bekor qilindi.",
            link="/",
        )
        log_audit(
            request,
            'BORROW_REJECTED',
            book_title,
            f"So'rov rad etildi. Kitobxon: {student.username}",
        )
        messages.info(request, f"❌ {student.full_display_name}ning «{book_title}» uchun so'rovi bekor qilindi.")
    return redirect('librarian_desk')


@login_required
def librarian_approve_return_view(request, loan_id):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ruxsat etilmagan amal!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    with transaction.atomic():
        loan = get_object_or_404(
            Loan.objects.select_related('book_copy__book', 'user'),
            pk=loan_id,
            is_returned=False
        )
        entered_code = request.POST.get('verification_code', '').strip()
        if entered_code and loan.verification_code and entered_code != loan.verification_code:
            messages.error(request, f"Noto'g'ri kod kiritildi! Kutilgan kod: {loan.verification_code}")
            return redirect('librarian_desk')

        loan.status = 'returned'
        loan.is_returned = True
        loan.returned_at = timezone.now()
        loan.received_by = request.user
        loan.save()

        book = loan.book_copy.book
        waiting_reservations = list(
            Reservation.objects.filter(book=book)
            .exclude(user=loan.user)
            .select_related('user')
            .order_by('created_at')[:5]
        )
        for res_item in waiting_reservations:
            Notification.objects.create(
                user=res_item.user,
                title="Navbatdagi kitob bo'shadi!",
                message=f"Siz kutayotgan «{book.title}» kitobi kutubxonaga qaytarildi. Hoziroq olishingiz mumkin!",
                link=f"/book/{book.pk}/",
            )
            notify_reservation_available(res_item.user, book)

        Notification.objects.create(
            user=loan.user,
            title="Kitob qaytarildi va qabul qilindi",
            message=f"«{book.title}» ({loan.book_copy.inventory_number}) kitobi kutubxonachi ({request.user.full_display_name}) tomonidan qabul qilib olindi.",
            link="/profile/",
        )
        notify_return_approved(loan)
        log_audit(
            request,
            'RETURN_APPROVED',
            f"{book.title} ({loan.book_copy.inventory_number})",
            f"Qaytarib olindi. Kitobxon: {loan.user.username}",
        )
        messages.info(
            request,
            f"📥 «{book.title}» ({loan.book_copy.inventory_number}) kitobi {loan.user.full_display_name}dan muvaffaqiyatli qabul qilib olindi va ijara yopildi!",
        )
    return redirect('librarian_desk')


@login_required
def librarian_remind_overdue_view(request, loan_id):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ruxsat etilmagan amal!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    loan = get_object_or_404(
        Loan.objects.select_related('book_copy__book', 'user'),
        pk=loan_id,
        is_returned=False,
    )
    book = loan.book_copy.book
    days = loan.overdue_days
    penalty = loan.penalty_points
    Notification.objects.create(
        user=loan.user,
        title="🚨 DIQQAT: Kitob topshirish muddati o'tgan!",
        message=(
            f"Siz olgan «{book.title}» (Inv: {loan.book_copy.inventory_number}) kitobining topshirish muddati "
            f"{days} kunga o'tib ketdi (-{penalty} XP jarima). Iltimos, zudlik bilan kutubxonaga qaytaring!"
        ),
        link="/profile/",
    )
    tg_res = notify_overdue_reminder(loan)
    log_audit(
        request,
        'OVERDUE_REMIND',
        f"{book.title} ({loan.book_copy.inventory_number})",
        f"Qarzdor: {loan.user.username} | {days} kun kechikish (-{penalty} XP)",
    )
    tg_note = " (Telegram orqali ham yuborildi)" if tg_res.get('ok') else ""
    messages.info(
        request,
        f"🔔 {loan.user.full_display_name}ga «{book.title}» bo'yicha ogohlantirish xabarnomasi yuborildi{tg_note}!",
    )
    return redirect('librarian_desk')


@login_required
def librarian_remind_all_overdue_view(request):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ruxsat etilmagan amal!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    overdue_loans = list(
        Loan.objects.filter(
            is_returned=False,
            status__in=['active', 'return_pending'],
            due_date__lt=timezone.now(),
        ).select_related('book_copy__book', 'user')
    )
    for loan in overdue_loans:
        book = loan.book_copy.book
        Notification.objects.create(
            user=loan.user,
            title="🚨 DIQQAT: Kitob topshirish muddati o'tgan!",
            message=(
                f"Siz olgan «{book.title}» (Inv: {loan.book_copy.inventory_number}) kitobining topshirish muddati "
                f"{loan.overdue_days} kunga o'tib ketdi (-{loan.penalty_points} XP jarima). Iltimos, kutubxonaga qaytaring!"
            ),
            link="/profile/",
        )
        notify_overdue_reminder(loan)

    messages.info(request, f"🔔 Jami {len(overdue_loans)} nafar qarzdor kitobxonga ogohlantirish yuborildi!")
    return redirect('librarian_desk')


def book_read_view(request, pk):
    """Module 2: Brauzer ichidagi Interaktiv PDF Reader va Audio Kitob / AI Ovozli Mutolaa (TTS) Pleyeri."""
    book = get_object_or_404(
        Book.objects.select_related('genre', 'library'),
        pk=pk,
    )
    return render(request, 'book_reader.html', {
        'book': book,
    })


def generate_stickers_pdf_response(copies_list, filename="smartlib_stickers_a4.pdf"):
    """Module 5: ReportLab orqali A4 formatda Code128 Shtrix-kod + QR Kod + Inventar stikerlar varag'ini yaratadi."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader
    from reportlab.graphics.barcode import code128

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4  # 595.27 x 841.89 pt

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    arial_path = r"C:\Windows\Fonts\arial.ttf"
    arial_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
        try:
            pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
            pdfmetrics.registerFont(TTFont("ArialUniBold", arial_bold_path))
            font_regular = "ArialUni"
            font_bold = "ArialUniBold"
        except Exception:
            pass

    # 2 ustun x 5 qator = har bir A4 varaqda 10 ta yirik, skaner-bop Shtrix-kod + QR stiker
    cols = 2
    rows = 5
    per_page = cols * rows
    margin_x = 24
    margin_y = 28
    gap_x = 14
    gap_y = 12
    card_w = (width - 2 * margin_x - (cols - 1) * gap_x) / cols
    card_h = (height - 2 * margin_y - (rows - 1) * gap_y) / rows

    if not copies_list:
        p.setFont(font_bold, 14)
        p.drawString(50, height - 60, "SMARTLIB — Chop etish uchun kitob nusxalari topilmadi.")
        p.showPage()
        p.save()
        buffer.seek(0)
        resp = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp

    for idx, copy_obj in enumerate(copies_list):
        pos_in_page = idx % per_page
        if idx > 0 and pos_in_page == 0:
            p.showPage()

        col = pos_in_page % cols
        row = pos_in_page // cols
        x = margin_x + col * (card_w + gap_x)
        y = height - margin_y - (row + 1) * card_h - row * gap_y

        book = copy_obj.book
        lib_name = (book.library.name if book.library else "SMARTLIB KUTUBXONASI")[:38]

        # Dashed cut border
        p.saveState()
        p.setDash(3, 3)
        p.setStrokeColor(colors.HexColor("#94a3b8"))
        p.setLineWidth(0.9)
        p.roundRect(x, y, card_w, card_h, 8, stroke=1, fill=0)
        p.restoreState()

        # Header ribbon
        header_h = 22
        p.setFillColor(colors.HexColor("#1e3a8a"))
        p.roundRect(x + 2, y + card_h - header_h - 2, card_w - 4, header_h, 6, stroke=0, fill=1)
        p.setFillColor(colors.white)
        p.setFont(font_bold, 8.5)
        p.drawString(x + 10, y + card_h - 16, f"SMARTLIB | {lib_name.upper()}")
        p.setFont(font_regular, 7.5)
        p.drawRightString(x + card_w - 10, y + card_h - 16, f"ID: #{book.pk}")

        # Book Title & Author
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont(font_bold, 10.5)
        title_str = book.title if len(book.title) <= 34 else book.title[:32] + "..."
        p.drawString(x + 10, y + card_h - 38, title_str)

        p.setFillColor(colors.HexColor("#475569"))
        p.setFont(font_regular, 8.5)
        author_str = book.author if len(book.author) <= 38 else book.author[:35] + "..."
        p.drawString(x + 10, y + card_h - 51, f"Muallif: {author_str}")

        meta_line = f"ISBN: {book.isbn or '-'}   |   UO'K: {book.udc or '-'}"
        p.setFont(font_regular, 7.5)
        p.drawString(x + 10, y + card_h - 63, meta_line[:46])

        # Code128 Barcode on Bottom-Left
        inv_code = str(copy_obj.inventory_number or f"INV-{book.pk}-1")
        try:
            bc = code128.Code128(inv_code, barHeight=28, barWidth=0.95)
            bc.drawOn(p, x + 4, y + 26)
        except Exception:
            pass

        # Human-readable Inventory Number badge
        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont(font_bold, 10)
        p.drawString(x + 12, y + 11, f"INV: {inv_code}")

        # QR Code on Bottom-Right
        base_pub = (_get_public_tunnel_url() or f"http://{_get_local_lan_ip()}:8000").rstrip('/')
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(f"{base_pub}/book/{book.pk}/?inv={inv_code}")
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format="PNG")
        qr_buf.seek(0)
        qr_size = 68
        p.drawImage(ImageReader(qr_buf), x + card_w - qr_size - 10, y + 10, width=qr_size, height=qr_size)

    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def book_stickers_pdf_view(request, pk):
    book = get_object_or_404(Book.objects.select_related('library'), pk=pk)
    copies = list(book.copies.select_related('book__library').order_by('id'))
    return generate_stickers_pdf_response(copies, filename=f"stikerlar_kitob_{book.pk}.pdf")


@login_required
def librarian_stickers_pdf_view(request):
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Faqat kutubxonachi yoki administratorlar stikerlarni chop etishi mumkin!")
        return redirect('home')
    q = request.GET.get('q', '').strip()
    book_id = request.GET.get('book_id', '').strip()
    copies_qs = BookCopy.objects.select_related('book__library').order_by('book_id', 'id')
    if book_id.isdigit():
        copies_qs = copies_qs.filter(book_id=int(book_id))
    if q:
        copies_qs = copies_qs.filter(
            Q(inventory_number__icontains=q) |
            Q(book__title__icontains=q) |
            Q(book__author__icontains=q) |
            Q(book__isbn__icontains=q)
        )
    copies = list(copies_qs[:200])
    return generate_stickers_pdf_response(copies, filename="smartlib_barcha_stikerlar_a4.pdf")


@login_required
def rate_book_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    blocked = _require_post(request, book_detail_url(book.pk))
    if blocked:
        return blocked

    raw_rating = str(request.POST.get('rating', '5')).strip()
    rating = int(raw_rating) if raw_rating.isdigit() and 1 <= int(raw_rating) <= 5 else 5
    comment = request.POST.get('comment', '').strip()[:1000]

    existing = Review.objects.filter(book=book, user=request.user).first()
    if existing:
        existing.rating = rating
        # Zero Data Loss: bo'sh izoh yuborilsa, avvalgi izoh o'chib ketmaydi
        if comment:
            existing.comment = comment
        existing.save()
    else:
        Review.objects.create(book=book, user=request.user, rating=rating, comment=comment)

    messages.info(request, "Taqriz va bahoyingiz saqlandi!")
    return redirect('book_detail', pk=book.pk)


@login_required
def toggle_favorite_view(request, pk):
    book = get_object_or_404(Book, pk=pk)
    blocked = _require_post(request, book_detail_url(book.pk))
    if blocked:
        return blocked

    fav = Favorite.objects.filter(user=request.user, book=book).first()
    if fav:
        fav.delete()
        messages.info(request, f"\"{book.title}\" sevimlilardan olib tashlandi.")
    else:
        Favorite.objects.create(user=request.user, book=book)
        messages.info(request, f"\"{book.title}\" sevimli kitoblarga qo'shildi!")

    next_url = request.POST.get('next', '').strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('book_detail', pk=book.pk)


@login_required
def mark_notifications_read_view(request):
    blocked = _require_post(request, reverse('profile'))
    if blocked:
        return blocked
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    next_url = request.POST.get('next', '').strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('profile')


@login_required
def reserve_book_view(request, pk):
    book = get_object_or_404(Book.objects.prefetch_related('copies'), pk=pk)
    blocked = _require_post(request, book_detail_url(book.pk))
    if blocked:
        return blocked
    if Loan.objects.filter(user=request.user, book_copy__book=book, is_returned=False).exists():
        messages.info(request, "Ushbu kitob hozirda sizning qo'lingizda mavjud.")
        return redirect('profile')
    if book.available_copies_count > 0:
        messages.info(request, "Kitob javonda mavjud! Navbatga yozilmasdan to'g'ridan-to'g'ri olishingiz mumkin.")
        return redirect('book_detail', pk=book.pk)

    try:
        Reservation.objects.get_or_create(user=request.user, book=book)
    except IntegrityError:
        pass  # parallel ikki marta bosish - UniqueConstraint allaqachon himoya qildi
    messages.info(request, "Navbatga yozildingiz.")
    return redirect('book_detail', pk=book.pk)


@login_required
def cancel_reservation_view(request, res_id):
    blocked = _require_post(request, reverse('profile'))
    if blocked:
        return blocked
    res = get_object_or_404(Reservation.objects.select_related('book'), pk=res_id, user=request.user)
    book_title = res.book.title
    res.delete()
    messages.info(request, f"\"{book_title}\" kitobi uchun navbat bekor qilindi.")
    return redirect('profile')


@login_required
def reports_view(request):
    total_books = Book.objects.count()
    total_copies = BookCopy.objects.count()
    active_loans = Loan.objects.filter(is_returned=False).count()
    overdue_loans = Loan.objects.filter(is_returned=False, due_date__lt=timezone.now()).count()
    total_members = CustomUser.objects.count()

    top_books = list(
        Book.objects
        .annotate(read_count=Count('copies__loans'))
        .filter(read_count__gt=0)
        .order_by('-read_count')[:5]
    )

    faculty_stats = list(
        Loan.objects
        .exclude(user__faculty='')
        .exclude(user__faculty__isnull=True)
        .values('user__faculty')
        .annotate(loan_count=Count('id'))
        .order_by('-loan_count')
    )

    genre_stats = list(
        Genre.objects
        .annotate(book_count=Count('books', distinct=True), loan_count=Count('books__copies__loans'))
        .order_by('-book_count')
    )

    context = {
        'total_books': total_books,
        'total_copies': total_copies,
        'active_loans': active_loans,
        'overdue_loans': overdue_loans,
        'total_members': total_members,
        'top_books': top_books,
        'faculty_stats': faculty_stats,
        'genre_stats': genre_stats,
        'chart_top_labels_json': json.dumps([b.title[:28] for b in top_books]),
        'chart_top_counts_json': json.dumps([b.read_count for b in top_books]),
        'chart_genre_labels_json': json.dumps([g.name for g in genre_stats]),
        'chart_genre_counts_json': json.dumps([g.book_count for g in genre_stats]),
    }
    return render(request, 'reports.html', context)


@login_required
def reports_pdf_view(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    arial_path = r"C:\Windows\Fonts\arial.ttf"
    arial_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
        try:
            pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
            pdfmetrics.registerFont(TTFont("ArialUniBold", arial_bold_path))
            font_regular = "ArialUni"
            font_bold = "ArialUniBold"
        except Exception:
            pass

    p.setFont(font_bold, 18)
    p.drawString(50, height - 60, "SMARTLIB — Kutubxona Hisoboti (PQ-9)")

    p.setFont(font_regular, 12)
    y = height - 95
    overdue_count = Loan.objects.filter(is_returned=False, due_date__lt=timezone.now()).count()
    p.drawString(50, y, f"Hisobot sanasi: {timezone.now().strftime('%d.%m.%Y %H:%M')}")
    y -= 28
    p.drawString(50, y, f"• Jami Kitoblar (nomda): {Book.objects.count()}")
    y -= 20
    p.drawString(50, y, f"• Jami Nusxalar (fond): {BookCopy.objects.count()}")
    y -= 20
    p.drawString(50, y, f"• Hozir o'qilmoqda: {Loan.objects.filter(is_returned=False).count()}")
    y -= 20
    p.drawString(50, y, f"• Muddati o'tgan ijaralar: {overdue_count}")
    y -= 20
    p.drawString(50, y, f"• Jami A'zolar soni: {CustomUser.objects.count()}")

    y -= 35
    p.setFont(font_bold, 14)
    p.drawString(50, y, "Eng ko'p o'qilgan kitoblar (Top 5):")
    y -= 24
    p.setFont(font_regular, 11)

    top_books = Book.objects.annotate(read_count=Count('copies__loans')).filter(read_count__gt=0).order_by('-read_count')[:5]
    for idx, b in enumerate(top_books, start=1):
        if y < 90:
            p.showPage()
            p.setFont(font_regular, 11)
            y = height - 60
        line_str = f"{idx}. {b.title[:50]} ({b.author[:30]}) — {b.read_count} marta o'qildi"
        p.drawString(60, y, line_str)
        y -= 20

    faculty_stats = (
        Loan.objects
        .exclude(user__faculty='')
        .exclude(user__faculty__isnull=True)
        .values('user__faculty')
        .annotate(loan_count=Count('id'))
        .order_by('-loan_count')
    )
    if faculty_stats:
        y -= 22
        if y < 120:
            p.showPage()
            y = height - 60
        p.setFont(font_bold, 14)
        p.drawString(50, y, "Fakultetlar kesimida kitobxonlik ko'rsatkichi:")
        y -= 24
        p.setFont(font_regular, 11)
        for idx, fs in enumerate(faculty_stats, start=1):
            if y < 70:
                p.showPage()
                p.setFont(font_regular, 11)
                y = height - 60
            p.drawString(60, y, f"{idx}. {fs['user__faculty'][:55]} — {fs['loan_count']} ta kitob")
            y -= 20

    p.setFont(font_regular, 10)
    p.drawString(50, 40, "Smart Library System | Loyiha muallifi: Xusniddin Gofurov")
    p.showPage()
    p.save()

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="smartlib_hisobot.pdf"'
    return response


def _build_xlsx_bytes(rows):
    """Tashqi kutubxonasiz toza OpenXML (.xlsx) fayl generatsiya qiladi."""
    sheet_rows_xml = []
    for r_idx, row in enumerate(rows, start=1):
        cells_xml = []
        for c_idx, val in enumerate(row):
            col_letter = chr(ord('A') + c_idx)
            cell_ref = f"{col_letter}{r_idx}"
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                cells_xml.append(f'<c r="{cell_ref}"><v>{val}</v></c>')
            else:
                safe_txt = xml_escape(str(val if val is not None else ''))
                cells_xml.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{safe_txt}</t></is></c>')
        sheet_rows_xml.append(f'<row r="{r_idx}">{"".join(cells_xml)}</row>')

    worksheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows_xml)}</sheetData>'
        '</worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="SmartLib Hisobot" sheetId="1" r:id="rId1"/></sheets>'
        '</workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    wb_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        '</Relationships>'
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>'
    )

    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types_xml)
        zf.writestr('_rels/.rels', rels_xml)
        zf.writestr('xl/workbook.xml', workbook_xml)
        zf.writestr('xl/_rels/workbook.xml.rels', wb_rels_xml)
        zf.writestr('xl/worksheets/sheet1.xml', worksheet_xml)
    return out.getvalue()


@login_required
def reports_excel_view(request):
    overdue_count = Loan.objects.filter(is_returned=False, due_date__lt=timezone.now()).count()
    rows = [
        ["SMARTLIB — KUTUBXONA HISOBOTI (PQ-9)", "", "", "", ""],
        ["Hisobot sanasi:", timezone.now().strftime('%d.%m.%Y %H:%M'), "", "", ""],
        ["", "", "", "", ""],
        ["Ko'rsatkich", "Qiymat", "", "", ""],
        ["Jami Kitoblar (nomda)", Book.objects.count(), "", "", ""],
        ["Jami Nusxalar (fond)", BookCopy.objects.count(), "", "", ""],
        ["Hozir o'qilmoqda", Loan.objects.filter(is_returned=False).count(), "", "", ""],
        ["Muddati o'tgan ijaralar", overdue_count, "", "", ""],
        ["Jami A'zolar soni", CustomUser.objects.count(), "", "", ""],
        ["", "", "", "", ""],
        ["KITOBLAR KATALOGI VA STATISTIKASI", "", "", "", ""],
        ["ID", "Kitob nomi", "Muallif", "Janr", "Mavjud / Jami", "O'qilgan marta"],
    ]
    books_with_stats = (
        Book.objects.select_related('genre')
        .prefetch_related('copies')
        .annotate(read_count=Count('copies__loans'))
        .order_by('-read_count', 'id')
    )
    for b in books_with_stats:
        rows.append([
            b.pk,
            b.title,
            b.author,
            b.genre.name if b.genre else "Umumiy",
            f"{b.available_copies_count} / {b.total_copies}",
            b.read_count,
        ])

    xlsx_data = _build_xlsx_bytes(rows)
    response = HttpResponse(
        xlsx_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="smartlib_hisobot.xlsx"'
    return response


@login_required
def profile_view(request):
    active_loans = (
        Loan.objects
        .filter(user=request.user, is_returned=False)
        .select_related('book_copy__book')
    )
    loan_history = (
        Loan.objects
        .filter(user=request.user, is_returned=True)
        .select_related('book_copy__book')
        .order_by('-returned_at')
    )
    reservations = (
        Reservation.objects
        .filter(user=request.user)
        .select_related('book')
        .prefetch_related('book__copies')
    )
    favorites = (
        Favorite.objects
        .filter(user=request.user)
        .select_related('book__genre', 'book__library')
        .prefetch_related('book__copies', 'book__reviews')
    )
    notifications = list(
        Notification.objects.filter(user=request.user).order_by('-created_at')[:10]
    )
    completed_count = loan_history.count()
    goal = max(1, request.user.annual_goal or 10)
    progress_percent = min(100, int((completed_count / goal) * 100))
    reader_rank = request.user.get_reader_rank(completed_count)
    discipline = request.user.get_discipline_summary()

    context = {
        'active_loans': active_loans,
        'loan_history': loan_history,
        'reservations': reservations,
        'favorites': favorites,
        'notifications': notifications,
        'completed_count': completed_count,
        'goal': goal,
        'progress_percent': progress_percent,
        'reader_rank': reader_rank,
        'discipline': discipline,
        'bot_username': get_bot_username(),
    }
    return render(request, 'profile.html', context)


@login_required
def reader_id_card_pdf_view(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    user = request.user
    completed_count = Loan.objects.filter(user=user, is_returned=True).count()
    rank = user.get_reader_rank(completed_count)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    arial_path = r"C:\Windows\Fonts\arial.ttf"
    arial_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
        try:
            pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
            pdfmetrics.registerFont(TTFont("ArialUniBold", arial_bold_path))
            font_regular = "ArialUni"
            font_bold = "ArialUniBold"
        except Exception:
            pass

    # ID Card Box
    card_x, card_y, card_w, card_h = 70, height - 340, 455, 250
    p.setStrokeColor(colors.HexColor("#1d4ed8"))
    p.setLineWidth(2)
    p.roundRect(card_x, card_y, card_w, card_h, 14, stroke=1, fill=0)

    # Header bar
    p.setFillColor(colors.HexColor("#1d4ed8"))
    p.roundRect(card_x, card_y + card_h - 52, card_w, 52, 14, stroke=0, fill=1)
    p.setFillColor(colors.white)
    p.setFont(font_bold, 15)
    p.drawString(card_x + 20, card_y + card_h - 32, "SMARTLIB — ELEKTRON KITOBXON GUVOHNOMASI")
    p.setFont(font_regular, 10)
    p.drawRightString(card_x + card_w - 20, card_y + card_h - 32, f"ID: SL-{user.pk:05d}")

    # Body info
    p.setFillColor(colors.HexColor("#0f172a"))
    p.setFont(font_bold, 14)
    p.drawString(card_x + 22, card_y + card_h - 82, f"F.I.Sh: {user.full_display_name}")

    p.setFont(font_regular, 11)
    y = card_y + card_h - 106
    p.drawString(card_x + 22, y, f"Login: @{user.username}  |  Maqom: {user.get_role_display()}")
    y -= 20
    p.drawString(card_x + 22, y, f"Kitobxon darajasi: {rank['title']} ({completed_count} ta kitob)")
    y -= 20
    lib_name = user.library.name if user.library else "Umumiy SmartLib Tarmog'i"
    p.drawString(card_x + 22, y, f"Kutubxona: {lib_name[:42]}")
    y -= 20
    extra_info = user.faculty or user.mahalla or user.phone or "-"
    p.drawString(card_x + 22, y, f"Qo'shimcha: {extra_info[:42]}")
    y -= 24
    p.setFont(font_regular, 9)
    p.setFillColor(colors.HexColor("#475569"))
    p.drawString(card_x + 22, y, f"Berilgan sana: {timezone.now().strftime('%d.%m.%Y')} | PQ-9 Yagona Kutubxona Tizimi")

    # QR Code on Right
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(f"SMARTLIB-READER:SL-{user.pk:05d}|USER:{user.username}|RANK:{rank['title']}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    p.drawImage(ImageReader(qr_buf), card_x + card_w - 125, card_y + 35, width=100, height=100)

    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="smartlib_id_{user.username}.pdf"'
    return response


@login_required
def reader_certificate_pdf_view(request):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.utils import ImageReader

    user = request.user
    completed_count = Loan.objects.filter(user=user, is_returned=True).count()
    rank = user.get_reader_rank(completed_count)

    buffer = io.BytesIO()
    page_size = landscape(A4)
    p = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size

    font_regular = "Helvetica"
    font_bold = "Helvetica-Bold"
    arial_path = r"C:\Windows\Fonts\arial.ttf"
    arial_bold_path = r"C:\Windows\Fonts\arialbd.ttf"
    if os.path.exists(arial_path) and os.path.exists(arial_bold_path):
        try:
            pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
            pdfmetrics.registerFont(TTFont("ArialUniBold", arial_bold_path))
            font_regular = "ArialUni"
            font_bold = "ArialUniBold"
        except Exception:
            pass

    # Outer & Inner Borders
    p.setStrokeColor(colors.HexColor("#1d4ed8"))
    p.setLineWidth(4)
    p.rect(28, 28, width - 56, height - 56)
    p.setStrokeColor(colors.HexColor("#f59f00"))
    p.setLineWidth(1.5)
    p.rect(36, 36, width - 72, height - 72)

    p.setFillColor(colors.HexColor("#1d4ed8"))
    p.setFont(font_bold, 28)
    p.drawCentredString(width / 2, height - 105, "SMARTLIB — FAXRIY SERTIFIKAT")

    p.setFillColor(colors.HexColor("#475569"))
    p.setFont(font_regular, 13)
    p.drawCentredString(width / 2, height - 135, "PQ-9 Qarori doirasida raqamlashtirilgan yagona kutubxona tizimi")

    p.setFillColor(colors.HexColor("#0f172a"))
    p.setFont(font_regular, 14)
    p.drawCentredString(width / 2, height - 185, "Ushbu sertifikat faol mutolaasi va kitobxonlik madaniyatiga qo'shgan hissasi uchun")

    p.setFillColor(colors.HexColor("#0d6efd"))
    p.setFont(font_bold, 26)
    p.drawCentredString(width / 2, height - 230, user.full_display_name.upper())

    p.setFillColor(colors.HexColor("#f59f00"))
    p.setFont(font_bold, 18)
    p.drawCentredString(width / 2, height - 275, f"« {rank['title'].upper()} »")

    p.setFillColor(colors.HexColor("#334155"))
    p.setFont(font_regular, 13)
    p.drawCentredString(
        width / 2,
        height - 310,
        f"unvoni bilan taqdirlanadi. O'qib tugatilgan kitoblar soni: {completed_count} ta (Yillik reja: {user.annual_goal} ta).",
    )

    # QR Verification
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(f"SMARTLIB-CERT:SL-{user.pk:05d}|NAME:{user.full_display_name}|RANK:{rank['title']}|BOOKS:{completed_count}")
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    p.drawImage(ImageReader(qr_buf), 65, 55, width=95, height=95)

    p.setFont(font_regular, 11)
    p.setFillColor(colors.HexColor("#475569"))
    p.drawString(175, 95, f"Sana: {timezone.now().strftime('%d.%m.%Y')}")
    p.drawString(175, 75, f"Sertifikat raqami: CERT-SL-{user.pk:05d}")
    p.drawRightString(width - 65, 85, "SmartLib Tizimi Direktori: Xusniddin Gofurov")

    p.showPage()
    p.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="smartlib_sertifikat_{user.username}.pdf"'
    return response


@login_required
def profile_edit_view(request):
    user = request.user
    libraries = Library.objects.all()

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', '').strip()
        student_id = request.POST.get('student_id', '').strip()
        faculty = request.POST.get('faculty', '').strip()
        group_name = request.POST.get('group_name', '').strip()
        grade = request.POST.get('grade', '').strip()
        grade_letter = request.POST.get('grade_letter', '').strip()
        parent_phone = request.POST.get('parent_phone', '').strip()
        mahalla = request.POST.get('mahalla', '').strip()
        street = request.POST.get('street', '').strip()
        house_number = request.POST.get('house_number', '').strip()
        occupation = request.POST.get('occupation', '').strip()
        telegram_chat_id = request.POST.get('telegram_chat_id', '').strip()[:64]
        library_id = _safe_library_id(request.POST.get('library'))
        annual_goal_raw = request.POST.get('annual_goal', '').strip()

        if 'profile_picture' in request.FILES:
            uploaded_file = request.FILES['profile_picture']
            if uploaded_file.size > 5 * 1024 * 1024:
                messages.error(request, "Rasm hajmi 5 MB dan oshmasligi kerak!")
                return render(request, 'profile_edit.html', {'user': user, 'libraries': libraries})
            try:
                img = Image.open(uploaded_file)
                img.verify()
                uploaded_file.seek(0)
            except Exception:
                messages.error(request, "Yuklangan fayl yaroqli rasm formati emas!")
                return render(request, 'profile_edit.html', {'user': user, 'libraries': libraries})

            # Eski rasmni diskdan tozalaymiz (Orphaned file leak oldini olish)
            if user.profile_picture and user.profile_picture.name:
                try:
                    if os.path.isfile(user.profile_picture.path):
                        os.remove(user.profile_picture.path)
                except Exception:
                    pass
            user.profile_picture = uploaded_file

        # Zero Data Loss: Bo'sh yuborilgan ma'lumot mavjud to'liq ma'lumotni o'chirib yubormasligi ta'minlanadi
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if phone:
            user.phone = phone
        if email:
            user.email = email
        if role in ('student', 'pupil', 'citizen'):
            user.role = role
        if student_id:
            user.student_id = student_id
        if faculty:
            user.faculty = faculty
        if group_name:
            user.group_name = group_name
        if grade:
            user.grade = grade
        if grade_letter:
            user.grade_letter = grade_letter
        if parent_phone:
            user.parent_phone = parent_phone
        if mahalla:
            user.mahalla = mahalla
        if street:
            user.street = street
        if house_number:
            user.house_number = house_number
        if occupation:
            user.occupation = occupation
        if telegram_chat_id:
            old_tg = user.telegram_chat_id
            user.telegram_chat_id = telegram_chat_id
            if telegram_chat_id != old_tg:
                send_telegram_message(
                    telegram_chat_id,
                    f"✅ <b>SmartLib — Telegram Xabarnoma ulandi!</b>\n\n"
                    f"👤 Foydalanuvchi: <b>{user.full_display_name}</b> (@{user.username})\n"
                    f"Endi kitob olish/topshirish kodlari va muddat eslatmalari shu yerga yuboriladi.",
                )
        if library_id:
            user.library_id = library_id
        if annual_goal_raw.isdigit() and 1 <= int(annual_goal_raw) <= 500:
            user.annual_goal = int(annual_goal_raw)

        user.save()
        messages.info(request, "Profil ma'lumotlari muvaffaqiyatli yangilandi!")
        return redirect('profile')

    return render(request, 'profile_edit.html', {'user': user, 'libraries': libraries, 'bot_username': get_bot_username()})


@login_required
def telegram_test_ping_view(request):
    blocked = _require_post(request, reverse('profile'))
    if blocked:
        return blocked
    chat_id = (request.user.telegram_chat_id or '').strip()
    if not chat_id:
        messages.error(request, "Avval «Tahrirlash» bo'limida Telegram Chat ID raqamingizni kiriting!")
        return redirect('profile_edit')
    res = send_telegram_message(
        chat_id,
        f"🔔 <b>SmartLib — Sinov xabarnomasi!</b>\n\n"
        f"Salom, <b>{request.user.full_display_name}</b>! Sizning Telegram bildirishnomalaringiz faol holatda ishlamoqda.",
    )
    if res.get('simulated'):
        messages.info(
            request,
            f"✈️ Sinov xabari Telegram navbat jurnaliga (ID: {chat_id}) yozildi! (Real bot orqali yuborish uchun TELEGRAM_BOT_TOKEN o'rnatiladi).",
        )
    elif res.get('ok'):
        messages.info(request, f"✈️ Telegram ({chat_id}) hisobingizga sinov xabari yuborildi!")
    else:
        messages.error(request, "Telegram xabarini yuborishda xatolik yuz berdi.")
    return redirect('profile')



def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    next_param = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is None and username:
            existing = CustomUser.objects.filter(username__iexact=username).first()
            if existing:
                user = authenticate(request, username=existing.username, password=password)
        if user is not None:
            login(request, user)
            if next_param and url_has_allowed_host_and_scheme(
                url=next_param,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_param)
            return redirect('home')
        else:
            messages.error(request, "Login yoki parol noto'g'ri!")

    return render(request, 'login.html', {'next': next_param})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    libraries = Library.objects.all()

    if request.method == 'POST':
        role = request.POST.get('role', 'student')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        raw_username = request.POST.get('username', '').strip()
        username = CustomUser.normalize_username(raw_username)
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        library_id = _safe_library_id(request.POST.get('library'))
        password = request.POST.get('password', '')
        if role not in ('student', 'pupil', 'citizen'):
            role = 'student'
        password_confirm = request.POST.get('password_confirm', '')

        student_id = request.POST.get('student_id', '').strip()
        faculty = request.POST.get('faculty', '').strip()
        group_name = request.POST.get('group_name', '').strip()
        if role == 'student' and student_id:
            sb = _resolve_student_base(student_id)
            if sb:
                if not first_name:
                    first_name = sb.first_name
                if not last_name:
                    last_name = sb.last_name
                if not group_name:
                    group_name = sb.group
                if not faculty:
                    faculty = sb.faculty

        if not username or not password:
            messages.error(request, "Login va parol kiritilishi shart!")
        elif password_confirm and password != password_confirm:
            messages.error(request, "Parollar mos kelmadi!")
        else:
            existing_user = CustomUser.objects.filter(username__iexact=username).first()
            if existing_user:
                auth_user = authenticate(request, username=existing_user.username, password=password)
                if auth_user is not None:
                    login(request, auth_user)
                    messages.info(request, "SmartLib tizimiga muvaffaqiyatli kirdingiz!")
                    return redirect('home')
                messages.error(request, f"\"{username}\" logini band! Iltimos, boshqa login tanlang yoki tizimga kiring.")
            else:
                try:
                    with transaction.atomic():
                        user = CustomUser(
                            username=username,
                            first_name=first_name,
                            last_name=last_name,
                            phone=phone,
                            email=email,
                            role=role,
                            library_id=library_id,
                            student_id=student_id,
                            faculty=faculty,
                            group_name=group_name,
                            grade=request.POST.get('grade', '').strip(),
                            grade_letter=request.POST.get('grade_letter', '').strip(),
                            parent_phone=request.POST.get('parent_phone', '').strip(),
                            mahalla=request.POST.get('mahalla', '').strip(),
                            street=request.POST.get('street', '').strip(),
                            house_number=request.POST.get('house_number', '').strip(),
                            occupation=request.POST.get('occupation', '').strip(),
                        )
                        user.set_password(password)
                        user.save()
                    login(request, user)
                    messages.info(request, "SmartLib tizimidan muvaffaqiyatli ro'yxatdan o'tdingiz!")
                    return redirect('home')
                except IntegrityError:
                    auth_user = authenticate(request, username=username, password=password)
                    if auth_user is not None:
                        login(request, auth_user)
                        messages.info(request, "SmartLib tizimidan muvaffaqiyatli ro'yxatdan o'tdingiz!")
                        return redirect('home')
                    messages.error(request, f"\"{username}\" logini band! Iltimos, boshqa login tanlang.")

    return render(request, 'register.html', {
        'libraries': libraries,
        'form_data': request.POST,
    })


def logout_view(request):
    # Logout faqat POST orqali (CSRF orqali majburan tizimdan chiqarib yuborishning oldini olish)
    if request.method == 'POST':
        logout(request)
        return redirect('home')
    if not request.user.is_authenticated:
        return redirect('home')
    return redirect('profile')


# ==============================================================================
# MODULE 4: SMART CATALOGING — ISBN AUTO-LOOKUP & BULK EXCEL/CSV IMPORT
# ==============================================================================
OFFLINE_ISBN_CATALOG = {
    '9789943231009': {
        'title': "O'tkan kunlar",
        'author': "Abdulla Qodiriy",
        'genre': "Badiiy adabiyot",
        'publisher': "Sharq Nashriyoti",
        'published_year': 2023,
        'pages': 384,
        'udc': "821.512.133",
        'bbk': "84(5O'zb)",
        'annotation': "O'zbek romanchiligining asoschisi Abdulla Qodiriyning o'lmas tarixiy-badiiy asari.",
    },
    '9789943000018': {
        'title': "Yulduzli tunlar",
        'author': "Pirimqul Qodirov",
        'genre': "Tarix",
        'publisher': "Yangi Asr Avlodi",
        'published_year': 2024,
        'pages': 512,
        'udc': "821.512.133-31",
        'bbk': "84(5O'zb)6",
        'annotation': "Zahiriddin Muhammad Bobur hayoti va davlat boshqaruvi haqida tarixiy roman.",
    },
    '9780132350884': {
        'title': "Clean Code: A Handbook of Agile Software Craftsmanship",
        'author': "Robert C. Martin",
        'genre': "Dasturlash",
        'publisher': "Prentice Hall",
        'published_year': 2022,
        'pages': 464,
        'udc': "004.42",
        'bbk': "32.973",
        'annotation': "Toza, xavfsiz va professional dasturiy kod yozish san'ati bo'yicha jahon standarti.",
    },
    '9780201616224': {
        'title': "The Pragmatic Programmer",
        'author': "Andrew Hunt, David Thomas",
        'genre': "Dasturlash",
        'publisher': "Addison-Wesley",
        'published_year': 2023,
        'pages': 352,
        'udc': "004.41",
        'bbk': "32.973",
        'annotation': "Katta muhandis va dasturchilar uchun amaliy arxitektura hamda algoritmik tajribalar.",
    },
    '9789943546103': {
        'title': "Atom odatlar (Atomic Habits)",
        'author': "James Clear",
        'genre': "Psixologiya va Biznes",
        'publisher': "Asaxiy Books",
        'published_year': 2024,
        'pages': 320,
        'udc': "159.9",
        'bbk': "88.5",
        'annotation': "Kichik o'zgarishlar orqali ulkan natijalarga erishish bo'yicha amaliy qo'llanma.",
    },
}


def isbn_lookup_api(request):
    """ISBN bo'yicha xalqaro (OpenLibrary) va lokal katalogdan 1-soniyada avto-to'ldirish API."""
    raw_isbn = request.GET.get('isbn', '').strip()
    clean_isbn = ''.join(ch for ch in raw_isbn if ch.isalnum())[:20]
    if not clean_isbn:
        return JsonResponse({'found': False, 'error': 'empty_isbn'})

    # 1. Check existing book in database
    existing_book = Book.objects.select_related('genre').filter(isbn__iexact=raw_isbn).first() or Book.objects.select_related('genre').filter(isbn__iexact=clean_isbn).first()
    if existing_book:
        return JsonResponse({
            'found': True,
            'source': 'local_db',
            'isbn': clean_isbn,
            'title': existing_book.title,
            'author': existing_book.author,
            'genre': existing_book.genre.name if existing_book.genre else 'Umumiy',
            'publisher': existing_book.publisher,
            'published_year': existing_book.published_year or 2024,
            'pages': existing_book.pages or 300,
            'udc': existing_book.udc,
            'bbk': existing_book.bbk,
            'annotation': existing_book.annotation,
        })

    # 2. Check curated offline ISBN catalog (works 100% offline!)
    if clean_isbn in OFFLINE_ISBN_CATALOG:
        item = OFFLINE_ISBN_CATALOG[clean_isbn]
        return JsonResponse({
            'found': True,
            'source': 'smartlib_catalog',
            'isbn': clean_isbn,
            **item,
        })

    # 3. Try OpenLibrary API with short defensive timeout
    try:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{urllib.parse.quote(clean_isbn)}&format=json&jscmd=data"
        req = urllib.request.Request(url, headers={'User-Agent': 'SmartLib/2.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            key = f"ISBN:{clean_isbn}"
            if key in data:
                bdata = data[key]
                authors = ", ".join(a.get('name', '') for a in bdata.get('authors', []) if a.get('name')) or "Noma'lum muallif"
                pubs = ", ".join(p.get('name', '') for p in bdata.get('publishers', []) if p.get('name')) or "Ziyo Nashr"
                pub_date = str(bdata.get('publish_date', '2024'))
                year_digits = ''.join(ch for ch in pub_date if ch.isdigit())[-4:]
                year_val = int(year_digits) if year_digits.isdigit() else 2024
                return JsonResponse({
                    'found': True,
                    'source': 'openlibrary',
                    'isbn': clean_isbn,
                    'title': bdata.get('title', 'Yangi Kitob'),
                    'author': authors,
                    'genre': 'Jahon adabiyoti',
                    'publisher': pubs,
                    'published_year': year_val,
                    'pages': int(bdata.get('number_of_pages') or 300),
                    'udc': '821',
                    'bbk': '84',
                    'annotation': bdata.get('subtitle', '') or f"Xalqaro ISBN ({clean_isbn}) katalogidan avtomatik yuklangan nashr.",
                })
    except Exception:
        pass

    return JsonResponse({'found': False, 'isbn': clean_isbn})


@login_required
def librarian_quick_add_book_view(request):
    """Kutubxonachi panelidan ISBN avto-to'ldirish orqali 1-klikda kitob qo'shish (Zero Data Loss)."""
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Ruxsat etilmagan amal!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    title = request.POST.get('title', '').strip()[:255]
    author = request.POST.get('author', '').strip()[:255]
    isbn = request.POST.get('isbn', '').strip()[:50]
    genre_name = request.POST.get('genre_name', '').strip()[:100] or "Umumiy"
    publisher = request.POST.get('publisher', '').strip()[:200] or "Ziyo Nashr"
    udc = request.POST.get('udc', '').strip()[:50]
    bbk = request.POST.get('bbk', '').strip()[:50]
    annotation = request.POST.get('annotation', '').strip()[:2000]
    year_raw = request.POST.get('published_year', '').strip()
    pages_raw = request.POST.get('pages', '').strip()
    copies_raw = request.POST.get('total_copies_count', '').strip()

    if not title or not author:
        messages.error(request, "Kitob nomi va muallifi kiritilishi shart!")
        return redirect('librarian_desk')

    published_year = int(year_raw) if year_raw.isdigit() and 1000 <= int(year_raw) <= 2100 else 2024
    pages = int(pages_raw) if pages_raw.isdigit() and 1 <= int(pages_raw) <= 10000 else 300
    copies_count = int(copies_raw) if copies_raw.isdigit() and 1 <= int(copies_raw) <= 500 else 3

    lib_id = _safe_library_id(request.POST.get('library'))
    library = Library.objects.filter(pk=lib_id).first() if lib_id else (request.user.library or Library.objects.first())
    if not library:
        library = Library.objects.create(name="Markaziy SmartLib Kutubxonasi", institution_type='arm')

    with transaction.atomic():
        genre_obj, _ = Genre.objects.get_or_create(name=genre_name)
        existing = None
        if isbn:
            existing = Book.objects.filter(library=library, isbn__iexact=isbn).first()
        if not existing:
            existing = Book.objects.filter(library=library, title__iexact=title, author__iexact=author).first()

        if existing:
            # Zero Data Loss: mavjud bo'sh maydonlarnigina to'ldiramiz va nusxalar sonini oshiramiz
            if isbn and not existing.isbn:
                existing.isbn = isbn
            if udc and not existing.udc:
                existing.udc = udc
            if bbk and not existing.bbk:
                existing.bbk = bbk
            if annotation and not existing.annotation:
                existing.annotation = annotation
            existing.total_copies_count = min(500, existing.total_copies + copies_count)
            existing.save()
            book = existing
            action_note = f"Mavjud kitob fondiga +{copies_count} ta yangi nusxa qo'shildi (Jami: {book.total_copies})"
        else:
            book = Book.objects.create(
                library=library,
                title=title,
                author=author,
                genre=genre_obj,
                isbn=isbn,
                udc=udc,
                bbk=bbk,
                publisher=publisher,
                published_year=published_year,
                pages=pages,
                total_copies_count=copies_count,
                annotation=annotation,
            )
            action_note = f"Yangi kitob va {copies_count} ta inventar nusxasi yaratildi"

        log_audit(request, 'ISBN_QUICK_ADD', f"{book.title} (ISBN: {isbn or '-'})", action_note)

    messages.info(request, f"📚 «{book.title}» — {action_note}!")
    return redirect('librarian_desk')


@login_required
def librarian_import_template_view(request):
    """Ommaviy kitob yuklash uchun tayyor Excel (.xlsx) namuna shabloni."""
    rows = [
        ["Kitob nomi", "Muallif", "Janr", "ISBN", "UO'K", "BBK", "Nashriyot", "Nashr yili", "Betlar", "Nusxalar soni", "Annotatsiya"],
        ["O'tkan kunlar", "Abdulla Qodiriy", "Badiiy adabiyot", "9789943231009", "821.512.133", "84(5O'zb)", "Sharq", 2024, 384, 5, "O'zbek romanchiligining durdonasi"],
        ["Clean Code", "Robert C. Martin", "Dasturlash", "9780132350884", "004.42", "32.973", "Prentice Hall", 2023, 464, 4, "Toza va xavfsiz kod yozish san'ati"],
        ["Atom odatlar", "James Clear", "Psixologiya va Biznes", "9789943546103", "159.9", "88.5", "Asaxiy Books", 2024, 320, 6, "Kichik odatlar orqali katta natijalar"],
    ]
    xlsx_data = _build_xlsx_bytes(rows)
    response = HttpResponse(
        xlsx_data,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="smartlib_import_shablon.xlsx"'
    return response


def _parse_uploaded_spreadsheet(uploaded_file):
    """Excel (.xlsx) yoki CSV (.csv) fayldan satrlarni xavfsiz o'qib oladi."""
    filename = (uploaded_file.name or '').lower()
    raw_bytes = uploaded_file.read()

    if filename.endswith('.csv'):
        text = None
        for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'latin-1'):
            try:
                text = raw_bytes.decode(enc)
                break
            except Exception:
                continue
        if not text:
            return []
        reader = csv.reader(io.StringIO(text))
        return [list(r) for r in reader if any(str(c).strip() for c in r)]

    # Try openpyxl first for .xlsx
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            cleaned = [str(cell).strip() if cell is not None else '' for cell in row]
            if any(cleaned):
                rows.append(cleaned)
        return rows
    except Exception:
        pass

    # Pure-Python XML fallback for .xlsx generated by _build_xlsx_bytes
    try:
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(raw_bytes), 'r') as zf:
            xml_content = zf.read('xl/worksheets/sheet1.xml')
        root = ET.fromstring(xml_content)
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        rows = []
        for row_el in root.findall('.//s:row', ns):
            row_vals = []
            for c_el in row_el.findall('s:c', ns):
                t_el = c_el.find('.//s:t', ns)
                v_el = c_el.find('s:v', ns)
                val = (t_el.text if t_el is not None else (v_el.text if v_el is not None else '')) or ''
                row_vals.append(val.strip())
            if any(row_vals):
                rows.append(row_vals)
        return rows
    except Exception:
        return []


@login_required
def librarian_bulk_import_view(request):
    """Module 4: Excel (.xlsx) yoki CSV fayldan kitoblarni ommaviy import qilish (Zero Data Loss)."""
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Faqat kutubxonachi yoki administratorlar ommaviy import qilishi mumkin!")
        return redirect('home')
    blocked = _require_post(request, reverse('librarian_desk'))
    if blocked:
        return blocked

    uploaded = request.FILES.get('import_file')
    if not uploaded:
        messages.error(request, "Iltimos, Excel (.xlsx) yoki CSV (.csv) faylni tanlang!")
        return redirect('librarian_desk')
    if uploaded.size > 10 * 1024 * 1024:
        messages.error(request, "Fayl hajmi 10 MB dan oshmasligi kerak!")
        return redirect('librarian_desk')

    rows = _parse_uploaded_spreadsheet(uploaded)
    if not rows or len(rows) < 2:
        messages.error(request, "Faylda kitob ma'lumotlari topilmadi yoki format noto'g'ri!")
        return redirect('librarian_desk')

    library = request.user.library or Library.objects.first()
    if not library:
        library = Library.objects.create(name="Markaziy SmartLib Kutubxonasi", institution_type='arm')

    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for row in rows[1:201]:  # DoS guard: max 200 books per batch
            cols = list(row) + [''] * 11
            title = str(cols[0]).strip()[:255]
            author = str(cols[1]).strip()[:255]
            if not title or not author or title.lower() in ('kitob nomi', 'title'):
                continue
            genre_name = str(cols[2]).strip()[:100] or "Umumiy"
            isbn = str(cols[3]).strip()[:50]
            udc = str(cols[4]).strip()[:50]
            bbk = str(cols[5]).strip()[:50]
            publisher = str(cols[6]).strip()[:200] or "Ziyo Nashr"
            year_str = str(cols[7]).strip().split('.')[0]
            pages_str = str(cols[8]).strip().split('.')[0]
            copies_str = str(cols[9]).strip().split('.')[0]
            annotation = str(cols[10]).strip()[:2000]

            pub_year = int(year_str) if year_str.isdigit() and 1000 <= int(year_str) <= 2100 else 2024
            pages = int(pages_str) if pages_str.isdigit() and 1 <= int(pages_str) <= 10000 else 300
            copies_cnt = int(copies_str) if copies_str.isdigit() and 1 <= int(copies_str) <= 500 else 3

            genre_obj, _ = Genre.objects.get_or_create(name=genre_name)
            existing = None
            if isbn:
                existing = Book.objects.filter(library=library, isbn__iexact=isbn).first()
            if not existing:
                existing = Book.objects.filter(library=library, title__iexact=title, author__iexact=author).first()

            if existing:
                # Zero Data Loss: faqat bo'sh maydonlarni to'ldiramiz
                if isbn and not existing.isbn:
                    existing.isbn = isbn
                if udc and not existing.udc:
                    existing.udc = udc
                if bbk and not existing.bbk:
                    existing.bbk = bbk
                if annotation and not existing.annotation:
                    existing.annotation = annotation
                existing.total_copies_count = max(existing.total_copies_count, copies_cnt)
                existing.save()
                updated_count += 1
            else:
                Book.objects.create(
                    library=library,
                    title=title,
                    author=author,
                    genre=genre_obj,
                    isbn=isbn,
                    udc=udc,
                    bbk=bbk,
                    publisher=publisher,
                    published_year=pub_year,
                    pages=pages,
                    total_copies_count=copies_cnt,
                    annotation=annotation,
                )
                created_count += 1

        log_audit(
            request,
            'BULK_IMPORT',
            uploaded.name,
            f"Yangi kitoblar: {created_count} ta | Yangilangan: {updated_count} ta",
        )

    messages.info(
        request,
        f"✅ Ommaviy import yakunlandi! Yangi qo'shilgan kitoblar: {created_count} ta, boyitilgan kitoblar: {updated_count} ta.",
    )
    return redirect('librarian_desk')


# ==============================================================================
# MODULE 6: LIBRARIAN FAST SCANNER-TERMINAL (KIOSK) & AUDIT LOG
# ==============================================================================
@login_required
def librarian_terminal_view(request):
    """Kutubxonachi uchun 1-soniyada ishlovchi Shtrix-kod / QR / OTP Kiosk-Terminali va Xavfsizlik Jurnali."""
    if not _is_librarian_or_admin(request.user):
        messages.error(request, "Terminalga faqat kutubxonachi yoki administratorlar kirishi mumkin!")
        return redirect('home')

    scan_result = None

    if request.method == 'POST':
        raw_scan = request.POST.get('scan_code', '').strip()
        student_query = request.POST.get('student_query', '').strip()

        # Extract ?inv=INV-x-y if a full QR URL was scanned
        scan_code = raw_scan
        if 'inv=' in raw_scan:
            try:
                parsed = urllib.parse.urlparse(raw_scan)
                qs = urllib.parse.parse_qs(parsed.query)
                if 'inv' in qs and qs['inv']:
                    scan_code = qs['inv'][0].strip()
            except Exception:
                pass
        if 'USER:' in student_query:
            try:
                for part in student_query.split('|'):
                    if part.upper().startswith('USER:'):
                        student_query = part.split(':', 1)[1].strip()
                        break
            except Exception:
                pass

        with transaction.atomic():
            # 1. Check if scan_code is a 6-digit OTP verification_code
            otp_loan = (
                Loan.objects.select_related('book_copy__book', 'user')
                .filter(verification_code=scan_code, is_returned=False)
                .first()
            ) if scan_code else None

            if otp_loan:
                if otp_loan.status == 'borrow_pending':
                    otp_loan.status = 'active'
                    otp_loan.issued_by = request.user
                    otp_loan.borrowed_at = timezone.now()
                    otp_loan.due_date = timezone.now() + timedelta(days=10)
                    otp_loan.save()
                    notify_borrow_approved(otp_loan)
                    log_audit(
                        request,
                        'TERMINAL_SCAN',
                        f"{otp_loan.book_copy.inventory_number} -> {otp_loan.user.username}",
                        f"6-xonali kod ({scan_code}) orqali kitob berildi",
                    )
                    scan_result = {
                        'status': 'success',
                        'badge': 'KITOB BERILDI (OTP TASDIQLANDI)',
                        'title': otp_loan.book_copy.book.title,
                        'inv': otp_loan.book_copy.inventory_number,
                        'user': otp_loan.user.full_display_name,
                        'detail': f"Qaytarish muddati: {otp_loan.due_date.strftime('%d.%m.%Y')}",
                    }
                    messages.info(request, f"⚡ Terminal: «{otp_loan.book_copy.book.title}» kitobi {otp_loan.user.full_display_name}ga berildi!")
                else:
                    otp_loan.status = 'returned'
                    otp_loan.is_returned = True
                    otp_loan.returned_at = timezone.now()
                    otp_loan.received_by = request.user
                    otp_loan.save()
                    notify_return_approved(otp_loan)
                    log_audit(
                        request,
                        'TERMINAL_SCAN',
                        f"{otp_loan.book_copy.inventory_number} <- {otp_loan.user.username}",
                        f"6-xonali kod ({scan_code}) orqali kitob qaytarib olindi",
                    )
                    scan_result = {
                        'status': 'returned',
                        'badge': 'KITOB QAYTARIB OLINDI',
                        'title': otp_loan.book_copy.book.title,
                        'inv': otp_loan.book_copy.inventory_number,
                        'user': otp_loan.user.full_display_name,
                        'detail': "Nusxa kutubxona fondiga bo'sh holatda qaytdi (+25 XP).",
                    }
                    messages.info(request, f"⚡ Terminal: «{otp_loan.book_copy.book.title}» kitobi {otp_loan.user.full_display_name}dan qabul qilindi!")
            else:
                # 2. Check if scan_code is an Inventory Barcode (INV-x-y)
                copy_obj = (
                    BookCopy.objects.select_related('book')
                    .filter(inventory_number__iexact=scan_code)
                    .first()
                ) if scan_code else None

                if copy_obj:
                    active_loan = (
                        Loan.objects.select_related('user', 'book_copy__book')
                        .filter(book_copy=copy_obj, is_returned=False)
                        .first()
                    )
                    if active_loan:
                        if active_loan.status == 'borrow_pending':
                            active_loan.status = 'active'
                            active_loan.issued_by = request.user
                            active_loan.borrowed_at = timezone.now()
                            active_loan.due_date = timezone.now() + timedelta(days=10)
                            active_loan.save()
                            notify_borrow_approved(active_loan)
                            log_audit(
                                request,
                                'TERMINAL_SCAN',
                                f"{copy_obj.inventory_number} -> {active_loan.user.username}",
                                "Shtrix-kod skaneri orqali so'rov tasdiqlandi va kitob berildi",
                            )
                            scan_result = {
                                'status': 'success',
                                'badge': 'SO\'ROV TASDIQLANDI VA BERILDI',
                                'title': copy_obj.book.title,
                                'inv': copy_obj.inventory_number,
                                'user': active_loan.user.full_display_name,
                                'detail': f"Topshirish muddati: {active_loan.due_date.strftime('%d.%m.%Y')}",
                            }
                            messages.info(request, f"⚡ Shtrix-kod ({copy_obj.inventory_number}): Kitob {active_loan.user.full_display_name}ga berildi!")
                        else:
                            active_loan.status = 'returned'
                            active_loan.is_returned = True
                            active_loan.returned_at = timezone.now()
                            active_loan.received_by = request.user
                            active_loan.save()
                            notify_return_approved(active_loan)
                            log_audit(
                                request,
                                'TERMINAL_SCAN',
                                f"{copy_obj.inventory_number} <- {active_loan.user.username}",
                                "Shtrix-kod skaneri orqali kitob kutubxonaga qaytarib olindi",
                            )
                            scan_result = {
                                'status': 'returned',
                                'badge': 'SHTRIX-KOD ORQALI QABUL QILINDI',
                                'title': copy_obj.book.title,
                                'inv': copy_obj.inventory_number,
                                'user': active_loan.user.full_display_name,
                                'detail': "Ijara yopildi va kitob javonga qaytarildi.",
                            }
                            messages.info(request, f"⚡ Shtrix-kod ({copy_obj.inventory_number}): Kitob {active_loan.user.full_display_name}dan qaytarib olindi!")
                    else:
                        # Copy is available on the shelf! If student_query is provided, issue directly!
                        if student_query:
                            clean_sq = student_query.lstrip('@')
                            if clean_sq.upper().startswith('SL-') and clean_sq[3:].isdigit():
                                target_user = CustomUser.objects.filter(pk=int(clean_sq[3:])).first()
                            else:
                                target_user = (
                                    CustomUser.objects.filter(username__iexact=clean_sq).first()
                                    or CustomUser.objects.filter(student_id__iexact=clean_sq).first()
                                )
                            if not target_user:
                                messages.error(request, f"«{student_query}» bo'yicha kitobxon topilmadi!")
                            elif target_user.is_debtor:
                                messages.error(request, f"⛔ {target_user.full_display_name}da muddati o'tgan qarzdorlik mavjud! Yangi kitob berish bloklangan.")
                            else:
                                new_loan = Loan.objects.create(
                                    user=target_user,
                                    book_copy=copy_obj,
                                    status='active',
                                    issued_by=request.user,
                                    borrowed_at=timezone.now(),
                                    due_date=timezone.now() + timedelta(days=10),
                                    is_returned=False,
                                )
                                notify_borrow_approved(new_loan)
                                log_audit(
                                    request,
                                    'TERMINAL_SCAN',
                                    f"{copy_obj.inventory_number} -> {target_user.username}",
                                    "Terminal orqali to'g'ridan-to'g'ri kitob berildi",
                                )
                                scan_result = {
                                    'status': 'success',
                                    'badge': 'TO\'G\'RIDAN-TO\'G\'RI KITOB BERILDI',
                                    'title': copy_obj.book.title,
                                    'inv': copy_obj.inventory_number,
                                    'user': target_user.full_display_name,
                                    'detail': f"Muddat: {new_loan.due_date.strftime('%d.%m.%Y')}",
                                }
                                messages.info(request, f"⚡ «{copy_obj.book.title}» ({copy_obj.inventory_number}) {target_user.full_display_name}ga rasmiylashtirildi!")
                        else:
                            scan_result = {
                                'status': 'available',
                                'badge': 'NUSXA JAVONDA BO\'SH (BERISHGA TAYYOR)',
                                'title': copy_obj.book.title,
                                'inv': copy_obj.inventory_number,
                                'user': "Hozir hech kimda band emas",
                                'detail': "Kitobxonga berish uchun o'ng tarafga talaba loginini (yoki ID raqamini) yozib skanerlang.",
                            }
                else:
                    messages.error(request, f"«{raw_scan}» bo'yicha faol kod yoki inventar shtrix-kodi topilmadi!")

    audit_logs = AuditLog.objects.select_related('actor').all()[:40]
    all_copies_hint = BookCopy.objects.select_related('book').order_by('id')[:120]
    pending_otps_hint = Loan.objects.filter(is_returned=False, status__in=['borrow_pending', 'return_pending']).select_related('user', 'book_copy__book')[:50]
    readers_hint = CustomUser.objects.order_by('username')[:120]
    return render(request, 'librarian_terminal.html', {
        'scan_result': scan_result,
        'audit_logs': audit_logs,
        'all_copies_hint': all_copies_hint,
        'pending_otps_hint': pending_otps_hint,
        'readers_hint': readers_hint,
    })


# ==============================================================================
# MODULE 7: PROGRESSIVE WEB APP (PWA) — MANIFEST, DYNAMIC ICONS, SERVICE WORKER
# ==============================================================================
def pwa_manifest_view(request):
    manifest = {
        "name": "SmartLib — Raqamlashtirilgan Yagona Kutubxona Ekotizimi",
        "short_name": "SmartLib",
        "description": "PQ-9 Qarori doirasida yaratilgan intellektual elektron kutubxona, Cloud PDF Reader, AI Audio va Shtrix-kod/QR tizimi.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#f4f7fe",
        "theme_color": "#2563eb",
        "icons": [
            {
                "src": "/pwa-icon/192/",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/pwa-icon/512/",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    }
    return JsonResponse(manifest, content_type='application/manifest+json')


def pwa_icon_view(request, size=192):
    """Chrome / Android / iOS / Windows PWA o'rnatish talablariga 100% mos PNG ikona generatori."""
    dim = 512 if int(size) >= 512 else 192
    img = Image.new('RGBA', (dim, dim), (30, 27, 75, 255))
    draw = ImageDraw.Draw(img)
    # Inner rounded accent badge
    pad = int(dim * 0.14)
    draw.rounded_rectangle([pad, pad, dim - pad, dim - pad], radius=int(dim * 0.18), fill=(37, 99, 235, 255))
    # Two stylized book pages
    left_x1, left_y1 = int(dim * 0.24), int(dim * 0.25)
    left_x2, left_y2 = int(dim * 0.48), int(dim * 0.75)
    right_x1, right_y1 = int(dim * 0.52), int(dim * 0.28)
    right_x2, right_y2 = int(dim * 0.76), int(dim * 0.75)
    draw.rounded_rectangle([left_x1, left_y1, left_x2, left_y2], radius=int(dim * 0.04), fill=(255, 255, 255, 255))
    draw.rounded_rectangle([right_x1, right_y1, right_x2, right_y2], radius=int(dim * 0.04), fill=(56, 189, 248, 255))

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return HttpResponse(buf.getvalue(), content_type='image/png')


def service_worker_view(request):
    """Root-scoped PWA Service Worker (Safe Network-first + Offline Navigation Fallback)."""
    sw_js = """
const CACHE_NAME = 'smartlib-pwa-v5';
const PRECACHE_URLS = [
    '/offline/',
    '/manifest.json'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.map((k) => (k !== CACHE_NAME ? caches.delete(k) : Promise.resolve()))
        )).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;
    const url = new URL(event.request.url);
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin/')) {
        return;
    }
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => caches.match('/offline/'))
        );
    }
});
""".strip()
    resp = HttpResponse(sw_js, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


def offline_view(request):
    return render(request, 'offline.html')


def download_apk_view(request):
    """Telefon uchun Android APK faylini to'g'ridan-to'g'ri yuklab olish."""
    apk_path = os.path.join(settings.BASE_DIR, 'dist', 'SmartLib.apk')
    if not os.path.exists(apk_path):
        apk_path = os.path.join(settings.MEDIA_ROOT, 'SmartLib.apk')
    if os.path.exists(apk_path):
        resp = FileResponse(open(apk_path, 'rb'), content_type='application/vnd.android.package-archive')
        resp['Content-Disposition'] = 'attachment; filename="SmartLib.apk"'
        return resp
    raise Http404("SmartLib.apk fayli topilmadi.")


def download_pc_view(request):
    """Kompyuter (Windows) uchun ish stoli dasturini (.exe) yuklab olish."""
    exe_path = os.path.join(settings.BASE_DIR, 'dist', 'SmartLib_Desktop.exe')
    if not os.path.exists(exe_path):
        exe_path = os.path.join(settings.MEDIA_ROOT, 'SmartLib_Desktop.exe')
    if os.path.exists(exe_path):
        resp = FileResponse(open(exe_path, 'rb'), content_type='application/octet-stream')
        resp['Content-Disposition'] = 'attachment; filename="SmartLib_Desktop.exe"'
        return resp
    raise Http404("SmartLib_Desktop.exe fayli topilmadi.")


def health_check_view(request):
    """Render bulut monitoringi va Keep-Alive xizmati uchun engil health check."""
    return JsonResponse({
        'status': 'healthy',
        'app': 'SmartLib',
        'timestamp': timezone.now().isoformat(),
        'keep_alive': True,
    })

