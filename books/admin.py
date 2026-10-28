from django.contrib import admin
from .models import Genre, Book, BookCopy, Loan, Reservation, Review, Favorite, Notification, AuditLog


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 0


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'isbn_display', 'mavjud_dona', 'library')
    list_filter = ('genre', 'published_year', 'library')
    list_select_related = ('library', 'genre')
    search_fields = ('title', 'author', 'isbn', 'udc', 'bbk')
    inlines = [BookCopyInline]
    actions = ['print_book_stickers_action']

    fieldsets = (
        ("Asosiy Ma'lumotlar", {
            'fields': ('library', 'title', 'author', 'genre', 'annotation'),
        }),
        ("Bibliografiya (Koha/Irbis)", {
            'fields': ('isbn', 'udc', 'bbk', 'publisher', 'published_year', 'pages', 'price'),
        }),
        ("Media va QR", {
            'fields': ('cover_image', 'pdf_file', 'audio_file', 'qr_code'),
        }),
        ("Nusxalar", {
            'fields': ('total_copies_count',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('library', 'genre').prefetch_related('copies')

    def isbn_display(self, obj):
        return obj.isbn if obj.isbn else "-"
    isbn_display.short_description = "ISBN"

    @admin.action(description="🏷️ Tanlangan kitoblar uchun Shtrix-kod va QR stikerlar (A4 PDF)")
    def print_book_stickers_action(self, request, queryset):
        from .views import generate_stickers_pdf_response
        copies = list(
            BookCopy.objects.filter(book__in=queryset)
            .select_related('book', 'book__library')
            .order_by('book_id', 'id')
        )
        return generate_stickers_pdf_response(copies, filename="smartlib_admin_stikerlar_a4.pdf")


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ('inventory_number', 'book', 'is_available')
    list_filter = ('is_available', 'book__library')
    list_select_related = ('book', 'book__library')
    search_fields = ('inventory_number', 'book__title')
    actions = ['print_copy_stickers_action']

    @admin.action(description="🏷️ Tanlangan nusxalar uchun Shtrix-kod va QR stikerlar (A4 PDF)")
    def print_copy_stickers_action(self, request, queryset):
        from .views import generate_stickers_pdf_response
        copies = list(queryset.select_related('book', 'book__library').order_by('id'))
        return generate_stickers_pdf_response(copies, filename="smartlib_nusxa_stikerlar_a4.pdf")


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ('user', 'book_title', 'inv_raqam', 'status', 'verification_code', 'due_date', 'is_returned')
    list_filter = ('status', 'is_returned', 'borrowed_at')
    list_select_related = ('user', 'book_copy', 'book_copy__book', 'issued_by', 'received_by')
    search_fields = (
        'user__first_name', 'user__last_name', 'user__username',
        'book_copy__inventory_number', 'book_copy__book__title', 'verification_code',
    )
    actions = ['approve_borrow_action', 'approve_return_action']

    def book_title(self, obj):
        return obj.book_copy.book.title
    book_title.short_description = "Kitob"

    def inv_raqam(self, obj):
        return obj.book_copy.inventory_number
    inv_raqam.short_description = "Inv. Raqam"

    @admin.action(description="✅ Tanlangan so'rovlarni tasdiqlash (Kitobni berish)")
    def approve_borrow_action(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        for loan in queryset.filter(status='borrow_pending'):
            loan.status = 'active'
            loan.is_returned = False
            loan.issued_by = request.user
            loan.borrowed_at = timezone.now()
            loan.due_date = timezone.now() + timedelta(days=10)
            loan.save()

    @admin.action(description="📥 Tanlangan kitoblarni qaytarib olishni tasdiqlash")
    def approve_return_action(self, request, queryset):
        from django.utils import timezone
        for loan in queryset.filter(is_returned=False):
            loan.status = 'returned'
            loan.is_returned = True
            loan.received_by = request.user
            loan.returned_at = timezone.now()
            loan.save()


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at')
    list_select_related = ('user', 'book')
    search_fields = ('user__first_name', 'user__last_name', 'book__title')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    list_select_related = ('user', 'book')
    search_fields = ('user__username', 'user__first_name', 'book__title', 'comment')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'created_at')
    list_select_related = ('user', 'book')
    search_fields = ('user__username', 'book__title')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    list_select_related = ('user',)
    search_fields = ('user__username', 'title', 'message')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor', 'action', 'target', 'ip_address')
    list_filter = ('action', 'created_at')
    list_select_related = ('actor',)
    search_fields = ('actor__username', 'target', 'details', 'ip_address')
    readonly_fields = ('created_at',)
