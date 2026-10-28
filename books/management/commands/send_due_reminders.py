import os
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from books.models import Loan, Notification
from books.telegram_service import notify_overdue_reminder, send_telegram_message


class Command(BaseCommand):
    help = "Muddati yaqinlashgan (1 kun qolgan) va muddati o'tgan kitoblar uchun Telegram va sayt xabarnomalarini avtomatik yuborish."

    def handle(self, *args, **options):
        now = timezone.now()
        tomorrow = now + timedelta(days=1)

        # 1. Muddati o'tgan kitoblar (Overdue)
        overdue_loans = (
            Loan.objects
            .filter(is_returned=False, status__in=['active', 'return_pending'], due_date__lt=now)
            .select_related('book_copy__book', 'user')
        )
        overdue_count = 0
        for loan in overdue_loans:
            user = loan.user
            book = loan.book_copy.book

            # In-app bildirishnoma (agar bugun yuborilmagan bo'lsa)
            recent_notif = Notification.objects.filter(
                user=user,
                title__contains="topshirish muddati o'tgan",
                created_at__date=now.date(),
            ).exists()

            if not recent_notif:
                Notification.objects.create(
                    user=user,
                    title="🚨 DIQQAT: Kitob topshirish muddati o'tgan!",
                    message=(
                        f"«{book.title}» (Inv: {loan.book_copy.inventory_number}) kitobining qaytarish muddati "
                        f"{loan.overdue_days} kunga kechikdi (-{loan.penalty_points} XP jarima). Zudlik bilan kutubxonaga topshiring!"
                    ),
                    link="/profile/",
                )
                notify_overdue_reminder(loan)
                overdue_count += 1

        # 2. Muddati yaqinlashgan kitoblar (1 kun yoki bugun topshirishi kerak bo'lganlar)
        upcoming_loans = (
            Loan.objects
            .filter(
                is_returned=False,
                status='active',
                due_date__gte=now,
                due_date__lte=tomorrow,
            )
            .select_related('book_copy__book', 'user')
        )
        upcoming_count = 0
        for loan in upcoming_loans:
            user = loan.user
            book = loan.book_copy.book

            recent_notif = Notification.objects.filter(
                user=user,
                title__contains="topshirish muddati yaqinlashdi",
                created_at__date=now.date(),
            ).exists()

            if not recent_notif:
                due_str = loan.due_date.strftime('%d.%m.%Y')
                Notification.objects.create(
                    user=user,
                    title="⏳ Eslatma: Kitob topshirish muddati yaqinlashdi",
                    message=(
                        f"Siz olgan «{book.title}» kitobining topshirish muddati: {due_str}. "
                        f"O'z vaqtida topshirib +35 XP ball to'plang!"
                    ),
                    link="/profile/",
                )
                if getattr(user, 'telegram_chat_id', ''):
                    tg_msg = (
                        f"⏳ <b>Eslatma: Kitob topshirish muddati yaqinlashmoqda!</b>\n\n"
                        f"👤 Kitobxon: <b>{user.full_display_name}</b>\n"
                        f"📖 Kitob: <b>{book.title}</b> (<code>{loan.book_copy.inventory_number}</code>)\n"
                        f"📅 Qaytarish sanasi: <b>{due_str}</b>\n\n"
                        f"<i>Kitobni o'z vaqtida topshirib intizom ko'rsatkichingizni va +35 XP ballingizni saqlab qoling!</i>"
                    )
                    send_telegram_message(user.telegram_chat_id, tg_msg)
                upcoming_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Eslatmalar yuborildi: {overdue_count} ta qarzdorlik, {upcoming_count} ta yaqinlashgan muddat."
            )
        )
