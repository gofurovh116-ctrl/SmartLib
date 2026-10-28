import os
import django
from datetime import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import Library, StudentBase, CustomUser
from books.models import Genre, Book, BookCopy, Loan, Reservation


def run_seed():
    # 1. Libraries
    tatu_lib, _ = Library.objects.get_or_create(
        name="TATU Axborot Resurs Markazi",
        defaults={
            'institution_type': 'arm',
            'region': "Toshkent shaxri",
            'district': "Yunusobod tumani",
            'address': "Amir Temur shoh ko'chasi, 108-uy",
        }
    )
    sanat_lib, _ = Library.objects.get_or_create(
        name="O'zbekiston Davlat San'at va Madaniyat Instituti",
        defaults={
            'institution_type': 'arm',
            'region': "Toshkent shaxri",
            'district': "Mirzo Ulug'bek tumani",
            'address': "Yalang'och dahasi, 127A-uy",
        }
    )

    # 2. StudentBase
    StudentBase.objects.get_or_create(
        passport_id="AA1234567",
        defaults={
            'first_name': "Botir",
            'last_name': "Qodirov",
            'group': "912-21",
            'faculty': "Dasturiy injiniring",
        }
    )

    # 3. Admin / Main User (Xusniddin G'ofurov)
    admin_user, created = CustomUser.objects.get_or_create(
        username="admin",
        defaults={
            'first_name': "Xusniddin",
            'last_name': "G'ofurov",
            'phone': "+998500025041",
            'email': "xusniddin@smartlib.uz",
            'status': "user",
            'role': "student",
            'annual_goal': 10,
            'is_staff': True,
            'is_superuser': True,
        }
    )
    # Zero Data Loss: parol faqat yangi yaratilgan admin uchun o'rnatiladi.
    # Mavjud admin parolini hech qachon qayta yozmaymiz!
    if created:
        admin_user.set_password("admin")
        admin_user.save()

    # 4. Genres (exact 5 genres from photo 22)
    genres_list = [
        "Biznes",
        "Tarix",
        "Fantastika",
        "Badiiy Adabiyot",
        "Dasturlash",
    ]
    genre_objs = {}
    for g_name in genres_list:
        g, _ = Genre.objects.get_or_create(name=g_name)
        genre_objs[g_name] = g

    # 5. Books (exact 8 books from photo 2 & photo 14)
    books_data = [
        {
            'title': "Shum Bola",
            'author': "G'afur G'ulom",
            'genre': genre_objs["Badiiy Adabiyot"],
            'isbn': "",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 256,
            'total_copies_count': 1,
        },
        {
            'title': "Boy Ota, Kambag'al Ota",
            'author': "Robert Kiyosaki",
            'genre': genre_objs["Biznes"],
            'isbn': "978-321982",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 419,
            'total_copies_count': 5,
        },
        {
            'title': "Temur Tuzuklari",
            'author': "Amir Temur",
            'genre': genre_objs["Tarix"],
            'isbn': "978-756052",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 320,
            'total_copies_count': 5,
        },
        {
            'title': "Clean Code",
            'author': "Robert Martin",
            'genre': genre_objs["Dasturlash"],
            'isbn': "978-420149",
            'publisher': "Prentice Hall",
            'published_year': 2024,
            'pages': 464,
            'total_copies_count': 5,
        },
        {
            'title': "Shaytanat",
            'author': "Tohir Malik",
            'genre': genre_objs["Badiiy Adabiyot"],
            'isbn': "978-502081",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 444,
            'total_copies_count': 5,
        },
        {
            'title': "Alkimyogar",
            'author': "Paulo Koelo",
            'genre': genre_objs["Fantastika"],
            'isbn': "978-266191",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 240,
            'total_copies_count': 5,
        },
        {
            'title': "Django Framework",
            'author': "Gofur J.",
            'genre': genre_objs["Dasturlash"],
            'isbn': "978-816535",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 380,
            'total_copies_count': 5,
        },
        {
            'title': "Python Asoslari",
            'author': "Eshmatov T.",
            'genre': genre_objs["Dasturlash"],
            'isbn': "978-480112",
            'publisher': "Ziyo Nashr",
            'published_year': 2024,
            'pages': 310,
            'total_copies_count': 5,
        },
    ]

    book_objs = {}
    for b_info in books_data:
        book, _ = Book.objects.get_or_create(
            title=b_info['title'],
            defaults={
                'library': tatu_lib,
                'author': b_info['author'],
                'genre': b_info['genre'],
                'isbn': b_info['isbn'],
                'publisher': b_info['publisher'],
                'published_year': b_info['published_year'],
                'pages': b_info['pages'],
                'total_copies_count': b_info['total_copies_count'],
            }
        )
        book_objs[b_info['title']] = book

    # Boy Ota uchun INV-7-1 / INV-7-2 nusxalari (faqat hali mavjud bo'lmasa - idempotent)
    boy_ota = book_objs["Boy Ota, Kambag'al Ota"]
    copies = list(boy_ota.copies.order_by('id'))
    already_ok = {c.inventory_number for c in copies[:2]} == {"INV-7-1", "INV-7-2"}
    taken_elsewhere = BookCopy.objects.filter(
        inventory_number__in=["INV-7-1", "INV-7-2"]
    ).exclude(book=boy_ota).exists()
    if len(copies) >= 2 and not already_ok and not taken_elsewhere:
        c1, c2 = copies[0], copies[1]
        if c1.inventory_number != "INV-7-1" and not BookCopy.objects.filter(inventory_number="INV-7-1").exists():
            c1.inventory_number = "INV-7-1"
            c1.save(update_fields=['inventory_number'])
        if c2.inventory_number != "INV-7-2" and not BookCopy.objects.filter(inventory_number="INV-7-2").exists():
            c2.inventory_number = "INV-7-2"
            c2.save(update_fields=['inventory_number'])

    if len(copies) >= 2:
        c1, c2 = copies[0], copies[1]
        if Loan.objects.count() == 0:
            Loan.objects.create(
                user=admin_user,
                book_copy=c1,
                borrowed_at=timezone.make_aware(datetime(2026, 1, 27, 2, 40)),
                due_date=timezone.make_aware(datetime(2026, 2, 6, 2, 40)),
                returned_at=timezone.make_aware(datetime(2026, 1, 27, 2, 56)),
                is_returned=True,
            )
            Loan.objects.create(
                user=admin_user,
                book_copy=c2,
                borrowed_at=timezone.make_aware(datetime(2026, 1, 27, 3, 1)),
                due_date=timezone.make_aware(datetime(2026, 2, 6, 3, 1)),
                returned_at=timezone.make_aware(datetime(2026, 1, 27, 3, 1)),
                is_returned=True,
            )

    # 6. Reservations matching photo 18
    if Reservation.objects.count() == 0:
        Reservation.objects.create(
            user=admin_user,
            book=book_objs["Shum Bola"],
        )
        Reservation.objects.create(
            user=admin_user,
            book=book_objs["Shaytanat"],
        )

    print("SmartLib database seeded successfully!")


if __name__ == '__main__':
    run_seed()
