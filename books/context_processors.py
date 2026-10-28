from django.utils import timezone
from .models import Notification, Loan


def smartlib_notifications(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'navbar_notifications': [],
            'overdue_alerts_count': 0,
            'pending_librarian_count': 0,
            'is_librarian_or_admin': False,
        }
    try:
        qs = Notification.objects.filter(user=user).order_by('-created_at')
        unread_count = qs.filter(is_read=False).count()
        latest_notifs = list(qs[:8])
        overdue_count = Loan.objects.filter(
            user=user,
            is_returned=False,
            due_date__lt=timezone.now(),
        ).exclude(status='borrow_pending').count()
        is_lib = bool(
            user.is_staff or user.is_superuser or getattr(user, 'status', '') in ('librarian', 'admin')
        )
        pending_lib = 0
        if is_lib:
            pending_lib = Loan.objects.filter(
                is_returned=False,
                status__in=('borrow_pending', 'return_pending'),
            ).count()
        return {
            'unread_notifications_count': unread_count + overdue_count,
            'navbar_notifications': latest_notifs,
            'overdue_alerts_count': overdue_count,
            'pending_librarian_count': pending_lib,
            'is_librarian_or_admin': is_lib,
        }
    except Exception:
        return {
            'unread_notifications_count': 0,
            'navbar_notifications': [],
            'overdue_alerts_count': 0,
            'pending_librarian_count': 0,
            'is_librarian_or_admin': False,
        }
