from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator


class Library(models.Model):
    INSTITUTION_TYPES = [
        ('arm', "Oliy Ta'lim (ARM)"),
        ('school', "Maktab Kutubxonasi"),
        ('public', "Viloyat/Tuman AKM (Jamoat)"),
    ]

    name = models.CharField("Kutubxona nomi", max_length=255, db_index=True)
    institution_type = models.CharField(
        "Muassasa Turi",
        max_length=50,
        choices=INSTITUTION_TYPES,
        default='arm',
        db_index=True,
    )
    region = models.CharField("Viloyat", max_length=150, blank=True, default="Toshkent shaxri")
    district = models.CharField("Tuman/Shahar", max_length=150, blank=True)
    address = models.TextField("Aniq Manzil", blank=True)

    class Meta:
        verbose_name = "Kutubxona "
        verbose_name_plural = "Kutubxonalar"

    def __str__(self):
        return f"{self.name} ({self.get_institution_type_display()})"


class StudentBase(models.Model):
    passport_id = models.CharField("Pasport / HEMIS ID", max_length=50, unique=True, db_index=True)
    first_name = models.CharField("Ism", max_length=100)
    last_name = models.CharField("Familiya", max_length=100)
    group = models.CharField("Guruh", max_length=50)
    faculty = models.CharField("Fakultet", max_length=150, blank=True)

    class Meta:
        verbose_name = "Talaba (HEMIS) "
        verbose_name_plural = "Talabalar bazasi (HEMIS)"

    def __str__(self):
        return f"{self.passport_id} - {self.first_name} {self.last_name}"



class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('student', "Talaba (Universitet)"),
        ('pupil', "O'quvchi (Maktab)"),
        ('citizen', "Mustaqil Kitobxon (Aholi)"),
    ]
    STATUS_CHOICES = [
        ('user', "Foydalanuvchi"),
        ('librarian', "Kutubxonachi"),
        ('admin', "Admin"),
    ]

    role = models.CharField(
        "Kim sifatida kirmoqchisiz?",
        max_length=30,
        choices=ROLE_CHOICES,
        default='student',
        db_index=True,
    )
    status = models.CharField(
        "Status",
        max_length=30,
        choices=STATUS_CHOICES,
        default='user',
        db_index=True,
    )
    phone = models.CharField("Telefon raqam", max_length=30, blank=True)
    telegram_chat_id = models.CharField(
        "Telegram Chat ID",
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Telegram bot (@SmartLibBot) orqali xabarnomalar olish uchun Chat ID",
    )
    profile_picture = models.ImageField("Profil Rasmi", upload_to='profiles/', blank=True, null=True)
    library = models.ForeignKey(
        Library,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Kutubxona",
        related_name='members',
    )
    annual_goal = models.PositiveIntegerField(
        "Yillik Reja",
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(500)],
    )

    # Talaba (Universitet) fields
    student_id = models.CharField("Student ID (Hemis)", max_length=50, blank=True, db_index=True)
    faculty = models.CharField("Fakultet", max_length=150, blank=True, db_index=True)
    group_name = models.CharField("Guruh", max_length=50, blank=True)

    # O'quvchi (Maktab) fields
    grade = models.CharField("Sinf (Masalan: 11)", max_length=20, blank=True)
    grade_letter = models.CharField("Sinf Harfi (Masalan: A)", max_length=10, blank=True)
    parent_phone = models.CharField("Ota-ona telefoni", max_length=30, blank=True)

    # Mustaqil Kitobxon (Aholi) fields
    mahalla = models.CharField("Mahalla Nomi", max_length=150, blank=True)
    street = models.CharField("Ko'cha", max_length=150, blank=True)
    house_number = models.CharField("Uy raqami", max_length=50, blank=True)
    occupation = models.CharField("Kasbi / Ish joyi", max_length=150, blank=True)

    class Meta:
        verbose_name = "Foydalanuvchi "
        verbose_name_plural = "Foydalanuvchilar"

    @property
    def initials(self):
        fn = (self.first_name or "").strip()
        ln = (self.last_name or "").strip()
        un = (self.username or "").strip()
        first = (fn or un or "U")[0].upper()
        last = ln[0].upper() if ln else ""
        return f"{first}{last}"

    @property
    def full_display_name(self):
        full = f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip()
        return full if full else self.username

    def get_reader_rank(self, completed_count=None):
        if completed_count is None:
            completed_count = getattr(self, 'books_read_count', None)
        if completed_count is None:
            completed_count = self.loans.filter(is_returned=True).count()
        if completed_count >= 10:
            return {'title': "SmartLib Akademigi", 'icon': 'fa-crown', 'color': '#f59f00', 'level': 4}
        if completed_count >= 5:
            return {'title': "Ziyo Elchisi", 'icon': 'fa-award', 'color': '#198754', 'level': 3}
        if completed_count >= 1:
            return {'title': "Faol Kitobxon", 'icon': 'fa-book-open-reader', 'color': '#0d6efd', 'level': 2}
        return {'title': "Yangi Kitobxon", 'icon': 'fa-seedling', 'color': '#64748b', 'level': 1}

    def get_discipline_summary(self):
        from django.utils import timezone
        now = timezone.now()
        all_loans = list(self.loans.all())
        returned_loans = [l for l in all_loans if l.is_returned]
        active_overdue = [
            l for l in all_loans
            if not l.is_returned and l.status in ('active', 'return_pending') and l.due_date < now
        ]
        earned_xp = len(returned_loans) * 25
        for rl in returned_loans:
            if rl.returned_at and rl.due_date and rl.returned_at <= rl.due_date:
                earned_xp += 10
        penalty = sum(l.penalty_points for l in active_overdue)
        net_xp = max(0, earned_xp - penalty)
        discipline_score = max(0, 100 - min(100, penalty * 2))
        return {
            'xp': net_xp,
            'earned_xp': earned_xp,
            'penalty': penalty,
            'discipline_score': discipline_score,
            'is_debtor': len(active_overdue) > 0,
            'overdue_count': len(active_overdue),
        }

    @property
    def xp_points(self):
        return self.get_discipline_summary()['xp']

    @property
    def is_debtor(self):
        from django.utils import timezone
        return self.loans.filter(
            is_returned=False,
            status__in=['active', 'return_pending'],
            due_date__lt=timezone.now(),
        ).exists()

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.is_staff = True
            if self.status == 'user':
                self.status = 'admin'
        elif self.status in ('admin', 'librarian'):
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_display_name} ({self.get_status_display()})"

