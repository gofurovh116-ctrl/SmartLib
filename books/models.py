import io
import os
import secrets
import qrcode
from datetime import timedelta
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.files.base import ContentFile
from users.models import Library


class Genre(models.Model):
    name = models.CharField("Janr nomi", max_length=100, db_index=True)

    class Meta:
        verbose_name = "Janr "
        verbose_name_plural = "Janrlar"

    def __str__(self):
        return self.name


class Book(models.Model):
    # Asosiy Ma'lumotlar (PROTECT against accidental cascade data loss!)
    library = models.ForeignKey(
        Library,
        on_delete=models.PROTECT,
        related_name='books',
        verbose_name="Kutubxona",
    )
    title = models.CharField("Kitob nomi", max_length=255, db_index=True)
    author = models.CharField("Muallif", max_length=255, db_index=True)
    genre = models.ForeignKey(
        Genre,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Janr",
        related_name='books',
    )
    annotation = models.TextField("Annotatsiya", blank=True)

    # Bibliografiya (Koha/Irbis)
    isbn = models.CharField(
        "ISBN",
        max_length=50,
        blank=True,
        db_index=True,
        help_text="Xalqaro standart raqami",
    )
    udc = models.CharField(
        "UO'K (UDC)",
        max_length=50,
        blank=True,
        help_text="Universal O'nlik Tasnif",
    )
    bbk = models.CharField(
        "BBK",
        max_length=50,
        blank=True,
        help_text="Bibliografik Tasnif",
    )
    publisher = models.CharField("Nashriyot", max_length=200, blank=True, default="Ziyo Nashr")
    published_year = models.PositiveIntegerField("Nashr yili", null=True, blank=True, default=2024, db_index=True)
    pages = models.PositiveIntegerField("Betlar soni", null=True, blank=True, default=300)
    price = models.DecimalField(
        "Narxi",
        max_digits=12,
        decimal_places=1,
        default=0.0,
        help_text="Balansdagi narxi",
    )

    # Media va QR
    cover_image = models.ImageField("Muqova rasmi", upload_to='books/covers/', blank=True, null=True)
    pdf_file = models.FileField("Elektron nusxa (PDF)", upload_to='books/pdfs/', blank=True, null=True)
    audio_file = models.FileField("Audiokitob fayli (MP3/WAV)", upload_to='books/audio/', blank=True, null=True)
    qr_code = models.ImageField("QR Kod", upload_to='books/qrcodes/', blank=True, null=True)

    # Nusxalar soni (DoS protection: max 500 copies per batch)
    total_copies_count = models.PositiveIntegerField(
        "Jami nusxalar soni",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Kitob "
        verbose_name_plural = "Kitoblar (Bibliografiya)"
        ordering = ['id']

    def __str__(self):
        return f"{self.title} - {self.author}"

    @property
    def total_copies(self):
        # Uses prefetched cache if available (0 extra SQL queries!)
        all_copies = list(self.copies.all())
        return len(all_copies) if all_copies else self.total_copies_count

    @property
    def available_copies_count(self):
        # Uses prefetched cache if available (fixes N+1 query explosion!)
        all_copies = list(self.copies.all())
        if not all_copies:
            return self.total_copies_count
        return sum(1 for c in all_copies if c.is_available)

    def mavjud_dona(self):
        return self.available_copies_count
    mavjud_dona.short_description = "Mavjud (dona)"

    @property
    def reviews_count(self):
        all_reviews = list(self.reviews.all())
        return len(all_reviews)

    @property
    def average_rating(self):
        all_reviews = list(self.reviews.all())
        if not all_reviews:
            return 0.0
        return round(sum(r.rating for r in all_reviews) / len(all_reviews), 1)

    def generate_qr(self):
        qr = qrcode.QRCode(version=1, box_size=6, border=2)
        # Encode real URL so mobile cameras open the book detail page directly!
        qr.add_data(f"http://127.0.0.1:8000/book/{self.pk}/")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        filename = f"qr_book_{self.pk}.png"
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)

    def sync_copies(self):
        target = min(int(self.total_copies_count or 1), 500)
        current_count = self.copies.count()
        if current_count < target:
            needed = target - current_count
            existing_invs = set(
                BookCopy.objects.filter(inventory_number__startswith=f"INV-{self.pk}-")
                .values_list('inventory_number', flat=True)
            )
            new_objs = []
            idx = current_count + 1
            while len(new_objs) < needed and idx <= target + 1000:
                inv_num = f"INV-{self.pk}-{idx}"
                if inv_num not in existing_invs:
                    new_objs.append(BookCopy(
                        book=self,
                        inventory_number=inv_num,
                        is_available=True,
                    ))
                    existing_invs.add(inv_num)
                idx += 1
            if new_objs:
                BookCopy.objects.bulk_create(new_objs, ignore_conflicts=True)
        elif current_count > target:
            excess = current_count - target
            removable_ids = list(
                self.copies
                .filter(is_available=True, loans__isnull=True)
                .order_by('-id')
                .values_list('id', flat=True)[:excess]
            )
            if removable_ids:
                BookCopy.objects.filter(id__in=removable_ids).delete()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        qr_missing = not self.qr_code
        if not qr_missing:
            try:
                qr_missing = not os.path.isfile(self.qr_code.path)
            except Exception:
                qr_missing = True
        if qr_missing:
            self.generate_qr()
            super().save(update_fields=['qr_code'])
        self.sync_copies()



@receiver(post_delete, sender=Book)
def cleanup_book_media_on_delete(sender, instance, **kwargs):
    for field_name in ('qr_code', 'cover_image', 'pdf_file', 'audio_file'):
        f = getattr(instance, field_name, None)
        if f and f.name:
            try:
                if os.path.isfile(f.path):
                    os.remove(f.path)
            except Exception:
                pass


class BookCopy(models.Model):
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='copies',
        verbose_name="Kitob",
    )
    inventory_number = models.CharField("Inventar raqami", max_length=50, unique=True, db_index=True)
    is_available = models.BooleanField("Mavjudmi?", default=True, db_index=True)

    class Meta:
        verbose_name = "Kitob nusxasi "
        verbose_name_plural = "Kitob Fondi (Inventar)"

    def __str__(self):
        status_txt = "Bo'sh" if self.is_available else "Band"
        return f"{self.inventory_number} ({self.book.title}) [{status_txt}]"

    def refresh_availability(self):
        active_loans_exist = self.loans.filter(is_returned=False).exists()
        new_state = not active_loans_exist
        if self.is_available != new_state:
            self.is_available = new_state
            self.save(update_fields=['is_available'])


def default_due_date():
    return timezone.now() + timedelta(days=10)


class Loan(models.Model):
    STATUS_CHOICES = [
        ('borrow_pending', "Olish tasdig'i kutilmoqda"),
        ('active', "Qo'lida (Berilgan)"),
        ('return_pending', "Qaytarish tasdig'i kutilmoqda"),
        ('returned', "Qaytarilgan"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='loans',
        verbose_name="Kitobxon",
    )
    book_copy = models.ForeignKey(
        BookCopy,
        on_delete=models.PROTECT,
        related_name='loans',
        verbose_name="Kitob nusxasi",
    )
    status = models.CharField(
        "Holati",
        max_length=25,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True,
    )
    verification_code = models.CharField(
        "Tasdiqlash kodi (6-xonali)",
        max_length=10,
        blank=True,
        db_index=True,
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='issued_loans',
        verbose_name="Kitobni bergan kutubxonachi",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_loans',
        verbose_name="Qabul qilgan kutubxonachi",
    )
    borrowed_at = models.DateTimeField("Olingan vaqt", default=timezone.now, db_index=True)
    due_date = models.DateTimeField("Qaytarish muddati", default=default_due_date, db_index=True)
    returned_at = models.DateTimeField("Qaytarilgan vaqt", null=True, blank=True)
    is_returned = models.BooleanField("Qaytarildimi?", default=False, db_index=True)

    class Meta:
        verbose_name = "Ijara "
        verbose_name_plural = "Ijaralar Tarixi"
        ordering = ['-borrowed_at']
        constraints = [
            # Baza darajasidagi kafolat: bitta inventar nusxasi bir vaqtda faqat
            # bitta kitobxonda bo'lishi mumkin (parallel so'rovlar / race condition himoyasi).
            models.UniqueConstraint(
                fields=['book_copy'],
                condition=models.Q(is_returned=False),
                name='unique_active_loan_per_copy',
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.book_copy.book.title} ({self.book_copy.inventory_number})"

    @property
    def is_overdue(self):
        if self.is_returned or self.status == 'borrow_pending':
            return False
        return timezone.now() > self.due_date

    @property
    def overdue_days(self):
        if not self.is_overdue:
            return 0
        delta = timezone.now() - self.due_date
        return max(1, delta.days + (1 if delta.seconds > 0 else 0))

    @property
    def penalty_points(self):
        return self.overdue_days * 5

    @staticmethod
    def generate_code():
        return f"{secrets.randbelow(900000) + 100000}"

    def clean(self):
        super().clean()
        if not self.is_returned and self.book_copy_id:
            conflict = (
                Loan.objects
                .filter(book_copy_id=self.book_copy_id, is_returned=False)
                .exclude(pk=self.pk)
                .exists()
            )
            if conflict:
                raise ValidationError({
                    'book_copy': "Ushbu inventar nusxasi hozirda boshqa kitobxonda band! Boshqa nusxani tanlang."
                })

    def save(self, *args, **kwargs):
        if self.is_returned:
            self.status = 'returned'
            if not self.returned_at:
                self.returned_at = timezone.now()
        else:
            if self.status == 'returned':
                self.is_returned = True
                if not self.returned_at:
                    self.returned_at = timezone.now()
            else:
                self.returned_at = None
        if not self.verification_code and self.status in ('borrow_pending', 'return_pending'):
            self.verification_code = self.generate_code()
        super().save(*args, **kwargs)
        self.book_copy.refresh_availability()


@receiver(post_delete, sender=Loan)
def update_copy_on_loan_delete(sender, instance, **kwargs):
    if instance.book_copy_id:
        try:
            instance.book_copy.refresh_availability()
        except BookCopy.DoesNotExist:
            pass


class Reservation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name="Talaba",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name="Kitob",
    )
    created_at = models.DateTimeField("Yozilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "Band qilish "
        verbose_name_plural = "Band qilinganlar"

        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'book'], name='unique_user_book_reservation')
        ]

    def __str__(self):
        return f"{self.user} -> {self.book}"


class Review(models.Model):
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reviews',
        verbose_name="Kitob",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='book_reviews',
        verbose_name="Kitobxon",
    )
    rating = models.PositiveSmallIntegerField(
        "Baho (1-5)",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        db_index=True,
    )
    comment = models.TextField("Fikr / Taqriz", blank=True)
    created_at = models.DateTimeField("Yozilgan vaqti", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Kitob taqrizi "
        verbose_name_plural = "Kitob taqrizlari (Reyting)"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['book', 'user'], name='unique_user_book_review')
        ]

    def __str__(self):
        return f"{self.user} -> {self.book.title} ({self.rating}★)"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name="Kitobxon",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name="Kitob",
    )
    created_at = models.DateTimeField("Qo'shilgan vaqti", auto_now_add=True)

    class Meta:
        verbose_name = "Sevimli kitob "
        verbose_name_plural = "Sevimli kitoblar (Wishlist)"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'book'], name='unique_user_favorite_book')
        ]

    def __str__(self):
        return f"{self.user} ❤️ {self.book.title}"


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name="Qabul qiluvchi",
    )
    title = models.CharField("Sarlavha", max_length=200)
    message = models.TextField("Xabar matni")
    link = models.CharField("Havola", max_length=255, blank=True)
    is_read = models.BooleanField("O'qildimi?", default=False, db_index=True)
    created_at = models.DateTimeField("Yaratilgan vaqt", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Bildirishnoma "
        verbose_name_plural = "Bildirishnomalar"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user}: {self.title}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('BORROW_REQUEST', "Kitob olish so'rovi"),
        ('BORROW_APPROVED', "Kitob berilishi tasdiqlandi"),
        ('BORROW_REJECTED', "Kitob so'rovi rad etildi"),
        ('RETURN_APPROVED', "Kitob qaytarib olindi"),
        ('TERMINAL_SCAN', "Tezkor Skaner-Terminal amali"),
        ('BULK_IMPORT', "Ommaviy Excel/CSV Import"),
        ('ISBN_QUICK_ADD', "ISBN orqali tezkor kitob qo'shish"),
        ('OVERDUE_REMIND', "Qarzdorga ogohlantirish yuborildi"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Bajaruvchi xodim / Foydalanuvchi",
    )
    action = models.CharField(
        "Amal turi",
        max_length=50,
        choices=ACTION_CHOICES,
        db_index=True,
    )
    target = models.CharField("Obyekt (Kitob / Nusxa / Kitobxon)", max_length=255)
    details = models.TextField("Tafsilotlar", blank=True)
    ip_address = models.CharField("IP Manzil", max_length=64, blank=True)
    created_at = models.DateTimeField("Vaqt", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Xavfsizlik Audit Jurnali "
        verbose_name_plural = "Xavfsizlik Audit Jurnali"
        ordering = ['-created_at']

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"[{self.created_at.strftime('%d.%m.%Y %H:%M')}] {actor_name} -> {self.action}: {self.target}"
