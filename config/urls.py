from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from books import views

urlpatterns = [
    path('health/', views.health_check_view, name='health_check'),
    path('favicon.ico', views.favicon_view, name='favicon'),
    path('manifest.json', views.pwa_manifest_view, name='pwa_manifest'),
    path('sw.js', views.service_worker_view, name='service_worker'),
    path('offline/', views.offline_view, name='offline'),
    path('download/apk/', views.download_apk_view, name='download_apk'),
    path('download/pc/', views.download_pc_view, name='download_pc'),
    path('pwa-icon/<int:size>/', views.pwa_icon_view, name='pwa_icon'),
    path('api/student-lookup/', views.student_lookup_api, name='student_lookup_api'),
    path('api/isbn-lookup/', views.isbn_lookup_api, name='isbn_lookup_api'),
    path('api/librarian-live-status/', views.librarian_live_status_api, name='librarian_live_status_api'),
    path('librarian/mobile-qr/', views.mobile_entry_qr_png_view, name='mobile_entry_qr_png'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin/', admin.site.urls),
    path('', views.home_view, name='home'),
    path('reading-room/', views.reading_room_view, name='reading_room'),
    path('book/<int:pk>/', views.book_detail_view, name='book_detail'),
    path('book/<int:pk>/read/', views.book_read_view, name='book_read'),
    path('book/<int:pk>/stickers/pdf/', views.book_stickers_pdf_view, name='book_stickers_pdf'),
    path('book/<int:pk>/borrow/', views.borrow_book_view, name='borrow_book'),
    path('book/<int:pk>/reserve/', views.reserve_book_view, name='reserve_book'),
    path('book/<int:pk>/rate/', views.rate_book_view, name='rate_book'),
    path('book/<int:pk>/favorite/', views.toggle_favorite_view, name='toggle_favorite'),
    path('reservation/<int:res_id>/cancel/', views.cancel_reservation_view, name='cancel_reservation'),
    path('loan/<int:loan_id>/return/', views.return_book_view, name='return_book'),
    path('librarian/', views.librarian_desk_view, name='librarian_desk'),
    path('librarian/terminal/', views.librarian_terminal_view, name='librarian_terminal'),
    path('librarian/books/quick-add/', views.librarian_quick_add_book_view, name='librarian_quick_add_book'),
    path('librarian/import/template/', views.librarian_import_template_view, name='librarian_import_template'),
    path('librarian/import/', views.librarian_bulk_import_view, name='librarian_bulk_import'),
    path('librarian/stickers/pdf/', views.librarian_stickers_pdf_view, name='librarian_stickers_pdf'),
    path('librarian/loan/<int:loan_id>/approve-borrow/', views.librarian_approve_borrow_view, name='librarian_approve_borrow'),
    path('librarian/loan/<int:loan_id>/reject-borrow/', views.librarian_reject_borrow_view, name='librarian_reject_borrow'),
    path('librarian/loan/<int:loan_id>/approve-return/', views.librarian_approve_return_view, name='librarian_approve_return'),
    path('librarian/loan/<int:loan_id>/remind/', views.librarian_remind_overdue_view, name='librarian_remind_overdue'),
    path('librarian/overdue/remind-all/', views.librarian_remind_all_overdue_view, name='librarian_remind_all_overdue'),
    path('notifications/read/', views.mark_notifications_read_view, name='mark_notifications_read'),
    path('reports/', views.reports_view, name='reports'),
    path('reports/pdf/', views.reports_pdf_view, name='reports_pdf'),
    path('reports/excel/', views.reports_excel_view, name='reports_excel'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
    path('profile/telegram-test/', views.telegram_test_ping_view, name='telegram_test_ping'),
    path('profile/id-card/pdf/', views.reader_id_card_pdf_view, name='reader_id_card_pdf'),
    path('profile/certificate/pdf/', views.reader_certificate_pdf_view, name='reader_certificate_pdf'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
