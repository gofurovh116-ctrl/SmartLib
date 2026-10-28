from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Library, StudentBase, CustomUser


@admin.register(Library)
class LibraryAdmin(admin.ModelAdmin):
    list_display = ('name', 'institution_type', 'region', 'district')
    list_filter = ('institution_type', 'region')
    search_fields = ('name', 'region', 'district')


@admin.register(StudentBase)
class StudentBaseAdmin(admin.ModelAdmin):
    list_display = ('passport_id', 'first_name', 'last_name', 'group', 'faculty')
    search_fields = ('passport_id', 'first_name', 'last_name', 'group', 'faculty')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('first_name', 'last_name', 'status', 'library_display')
    list_display_links = ('first_name', 'last_name')
    list_filter = ('library__institution_type', 'library', 'role', 'status')
    list_select_related = ('library',)
    search_fields = ('username', 'first_name', 'last_name', 'phone', 'telegram_chat_id', 'student_id', 'faculty')

    fieldsets = UserAdmin.fieldsets + (
        ("SmartLib Ma'lumotlari", {
            'fields': (
                'role', 'status', 'phone', 'telegram_chat_id', 'profile_picture', 'library', 'annual_goal',
                'student_id', 'faculty', 'group_name',
                'grade', 'grade_letter', 'parent_phone',
                'mahalla', 'street', 'house_number', 'occupation',
            ),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("SmartLib Ma'lumotlari", {
            'fields': (
                'first_name', 'last_name', 'role', 'status', 'phone', 'library',
                'student_id', 'faculty', 'group_name',
            ),
        }),
    )

    def library_display(self, obj):
        return str(obj.library) if obj.library else "-"
    library_display.short_description = "Kutubxona"
