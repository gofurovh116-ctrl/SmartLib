/* =========================================================
   SmartLib Admin Panel 3-Language Unification Engine
   Ensures 100% consistent language (UZ / RU / EN) across Jazzmin
   ========================================================= */
(function () {
    const ADMIN_DICT = {
        // Top Navbar & Breadcrumbs
        "Saytga o'tish": { uz: "Saytga o'tish", ru: "Перейти на сайт", en: "Back to Site" },
        "Dashboard": { uz: "Boshqaruv paneli", ru: "Панель управления", en: "Dashboard" },
        "Админпанель": { uz: "Boshqaruv paneli", ru: "Панель управления", en: "Dashboard" },
        "Boshqaruv paneli": { uz: "Boshqaruv paneli", ru: "Панель управления", en: "Dashboard" },
        "Home": { uz: "Bosh sahifa", ru: "Главная", en: "Home" },
        "Начало": { uz: "Bosh sahifa", ru: "Главная", en: "Home" },
        "Bosh sahifa": { uz: "Bosh sahifa", ru: "Главная", en: "Home" },

        // App Sections in Sidebar & Breadcrumbs
        "Users": { uz: "Foydalanuvchilar bo'limi", ru: "Пользователи и библиотеки", en: "Users & Libraries" },
        "Foydalanuvchilar bo'limi": { uz: "Foydalanuvchilar bo'limi", ru: "Пользователи и библиотеки", en: "Users & Libraries" },
        "Authentication and Authorization": { uz: "Huquqlar va Guruhlar", ru: "Права и группы", en: "Auth & Groups" },
        "Пользователи и группы": { uz: "Huquqlar va Guruhlar", ru: "Права и группы", en: "Auth & Groups" },
        "Foydalanuvchilar va guruhlar": { uz: "Huquqlar va Guruhlar", ru: "Права и группы", en: "Auth & Groups" },
        "Autentifikatsiya va avtorizatsiya": { uz: "Huquqlar va Guruhlar", ru: "Права и группы", en: "Auth & Groups" },
        "Groups": { uz: "Guruhlar", ru: "Группы", en: "Groups" },
        "Группы": { uz: "Guruhlar", ru: "Группы", en: "Groups" },
        "Guruhlar": { uz: "Guruhlar", ru: "Группы", en: "Groups" },
        "Books": { uz: "Kitoblar va Fond", ru: "Книги и фонд", en: "Books & Inventory" },
        "Kitoblar va Fond": { uz: "Kitoblar va Fond", ru: "Книги и фонд", en: "Books & Inventory" },

        // Model Plural Names
        "Kutubxonalar": { uz: "Kutubxonalar", ru: "Библиотеки", en: "Libraries" },
        "Foydalanuvchilar": { uz: "Foydalanuvchilar", ru: "Пользователи", en: "Users" },
        "Student bases": { uz: "Talabalar bazasi (HEMIS)", ru: "База студентов (HEMIS)", en: "Student Base (HEMIS)" },
        "Talabalar bazasi (HEMIS)": { uz: "Talabalar bazasi (HEMIS)", ru: "База студентов (HEMIS)", en: "Student Base (HEMIS)" },
        "Kitoblar (Bibliografiya)": { uz: "Kitoblar (Bibliografiya)", ru: "Книги (Библиография)", en: "Books (Bibliography)" },
        "Kitob Fondi (Inventar)": { uz: "Kitob Fondi (Inventar)", ru: "Книжный фонд (Инвентарь)", en: "Book Copies (Inventory)" },
        "Ijaralar Tarixi": { uz: "Ijaralar Tarixi", ru: "История аренд", en: "Loan History" },
        "Band qilinganlar": { uz: "Band qilinganlar", ru: "Бронирования (Очередь)", en: "Reservations" },
        "Janrlar": { uz: "Janrlar", ru: "Жанры", en: "Genres" },

        // Common Buttons & Actions
        "Search": { uz: "Qidirish", ru: "Найти", en: "Search" },
        "Найти": { uz: "Qidirish", ru: "Найти", en: "Search" },
        "Qidirish": { uz: "Qidirish", ru: "Найти", en: "Search" },
        "Go": { uz: "Bajarish", ru: "Выполнить", en: "Go" },
        "Выполнить": { uz: "Bajarish", ru: "Выполнить", en: "Go" },
        "Bajarish": { uz: "Bajarish", ru: "Выполнить", en: "Go" },
        "- Select an option -": { uz: "- Amalni tanlang -", ru: "- Выберите действие -", en: "- Select an action -" },
        "---------": { uz: "- Tanlang -", ru: "- Выберите -", en: "- Select -" },
        "Delete selected": { uz: "Tanlanganlarni o'chirish", ru: "Удалить выбранные", en: "Delete selected" },
        "Save": { uz: "Saqlash", ru: "Сохранить", en: "Save" },
        "Сохранить": { uz: "Saqlash", ru: "Сохранить", en: "Save" },
        "Saqlash": { uz: "Saqlash", ru: "Сохранить", en: "Save" },
        "Save and add another": { uz: "Saqlash va yana qo'shish", ru: "Сохранить и добавить другой", en: "Save and add another" },
        "Сохранить и добавить другой объект": { uz: "Saqlash va yana qo'shish", ru: "Сохранить и добавить другой", en: "Save and add another" },
        "Save and continue editing": { uz: "Saqlash va tahrirlashni davom ettirish", ru: "Сохранить и продолжить", en: "Save and continue editing" },
        "Сохранить и продолжить редактирование": { uz: "Saqlash va tahrirlashni davom ettirish", ru: "Сохранить и продолжить", en: "Save and continue editing" },
        "Delete": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
        "Удалить": { uz: "O'chirish", ru: "Удалить", en: "Delete" },
        "History": { uz: "Tarix", ru: "История", en: "History" },
        "История": { uz: "Tarix", ru: "История", en: "History" },
        "Recent actions": { uz: "So'nggi amallar", ru: "Последние действия", en: "Recent Actions" },
        "Последние действия": { uz: "So'nggi amallar", ru: "Последние действия", en: "Recent Actions" },
        "My actions": { uz: "Mening amallarim", ru: "Мои действия", en: "My Actions" },
        "Мои действия": { uz: "Mening amallarim", ru: "Мои действия", en: "My Actions" },
        "None available": { uz: "Hozircha yo'q", ru: "Нет записей", en: "None available" },
        "Пока нет": { uz: "Hozircha yo'q", ru: "Пока нет", en: "None available" },

        // Table Headers & Filters
        "Kitobxon": { uz: "Kitobxon", ru: "Читатель", en: "Reader" },
        "Kitob": { uz: "Kitob", ru: "Книга", en: "Book" },
        "Inv. Raqam": { uz: "Inv. Raqam", ru: "Инв. номер", en: "Inv. Number" },
        "Inventar raqami": { uz: "Inventar raqami", ru: "Инвентарный номер", en: "Inventory Number" },
        "Qaytarish muddati": { uz: "Qaytarish muddati", ru: "Срок возврата", en: "Due Date" },
        "Qaytarildimi?": { uz: "Qaytarildimi?", ru: "Возвращена?", en: "Returned?" },
        "Mavjudmi?": { uz: "Mavjudmi?", ru: "В наличии?", en: "Available?" },
        "Olingan vaqt": { uz: "Olingan vaqt", ru: "Дата выдачи", en: "Borrowed At" },
        "Kitob nomi": { uz: "Kitob nomi", ru: "Название книги", en: "Book Title" },
        "Muallif": { uz: "Muallif", ru: "Автор", en: "Author" },
        "Mavjud (dona)": { uz: "Mavjud (dona)", ru: "Доступно (шт.)", en: "Available (pcs)" },
        "Kutubxona": { uz: "Kutubxona", ru: "Библиотека", en: "Library" },
        "Kutubxona nomi": { uz: "Kutubxona nomi", ru: "Название библиотеки", en: "Library Name" },
        "Muassasa Turi": { uz: "Muassasa Turi", ru: "Тип учреждения", en: "Institution Type" },
        "Viloyat": { uz: "Viloyat", ru: "Область / Регион", en: "Region" },
        "Tuman/Shahar": { uz: "Tuman/Shahar", ru: "Район / Город", en: "District / City" },
        "Janr": { uz: "Janr", ru: "Жанр", en: "Genre" },
        "Janr nomi": { uz: "Janr nomi", ru: "Название жанра", en: "Genre Name" },
        "Nashr yili": { uz: "Nashr yili", ru: "Год издания", en: "Published Year" },
        "Talaba": { uz: "Talaba", ru: "Читатель / Студент", en: "Reader / Student" },
        "Yozilgan vaqti": { uz: "Yozilgan vaqti", ru: "Дата записи", en: "Created At" },
        "Created at": { uz: "Yozilgan vaqti", ru: "Дата записи", en: "Created At" },
        "Pasport / HEMIS ID": { uz: "Pasport / HEMIS ID", ru: "Паспорт / HEMIS ID", en: "Passport / HEMIS ID" },
        "Ism": { uz: "Ism", ru: "Имя", en: "First Name" },
        "Familiya": { uz: "Familiya", ru: "Фамилия", en: "Last Name" },
        "Guruh": { uz: "Guruh", ru: "Группа", en: "Group" },
        "Fakultet": { uz: "Fakultet", ru: "Факультет", en: "Faculty" },
        "Status": { uz: "Status", ru: "Статус", en: "Status" },

        // Form Tabs
        "Asosiy Ma'lumotlar": { uz: "Asosiy Ma'lumotlar", ru: "Основные данные", en: "General Info" },
        "Bibliografiya (Koha/Irbis)": { uz: "Bibliografiya (Koha/Irbis)", ru: "Библиография (Koha/Irbis)", en: "Bibliography (Koha/Irbis)" },
        "Media va QR": { uz: "Media va QR", ru: "Медиа и QR", en: "Media & QR" },
        "Nusxalar": { uz: "Nusxalar", ru: "Экземпляры", en: "Copies" },
        "SmartLib Ma'lumotlari": { uz: "SmartLib Ma'lumotlari", ru: "Данные SmartLib", en: "SmartLib Profile" },

        // Footer
        "All rights reserved.": { uz: "Barcha huquqlar himoyalangan.", ru: "Все права защищены.", en: "All rights reserved." },
        "Все права защищены.": { uz: "Barcha huquqlar himoyalangan.", ru: "Все права защищены.", en: "All rights reserved." },
        "Barcha huquqlar himoyalangan.": { uz: "Barcha huquqlar himoyalangan.", ru: "Все права защищены.", en: "All rights reserved." }
    };

    const MODEL_NAMES = {
        "Ijara": { uz: "Ijara", ru: "аренду", en: "Loan" },
        "Kitob": { uz: "Kitob", ru: "книгу", en: "Book" },
        "Kitob nusxasi": { uz: "Kitob nusxasi", ru: "экземпляр книги", en: "Book Copy" },
        "Band qilish": { uz: "Band qilish", ru: "бронирование", en: "Reservation" },
        "Janr": { uz: "Janr", ru: "жанр", en: "Genre" },
        "Kutubxona": { uz: "Kutubxona", ru: "библиотеку", en: "Library" },
        "Foydalanuvchi": { uz: "Foydalanuvchi", ru: "пользователя", en: "User" },
        "Talaba (HEMIS)": { uz: "Talaba (HEMIS)", ru: "студента (HEMIS)", en: "Student (HEMIS)" },
        "student base": { uz: "Talaba (HEMIS)", ru: "студента (HEMIS)", en: "Student (HEMIS)" },
        "Group": { uz: "Guruh", ru: "группу", en: "Group" },
        "guruh": { uz: "Guruh", ru: "группу", en: "Group" },
        "группа": { uz: "Guruh", ru: "группу", en: "Group" }
    };

    const DYNAMIC_ADMIN_PATTERNS = [
        {
            // Add <Model> / Добавить <Model> / <Model> qo'shish
            regex: /^(?:Add|Добавить)\s+(.+?)\s*$/i,
            uz: (m) => {
                const key = m[1].trim();
                const name = (MODEL_NAMES[key] && MODEL_NAMES[key].uz) || key;
                return `${name} qo'shish`;
            },
            ru: (m) => {
                const key = m[1].trim();
                const name = (MODEL_NAMES[key] && MODEL_NAMES[key].ru) || key;
                return `Добавить ${name}`;
            },
            en: (m) => {
                const key = m[1].trim();
                const name = (MODEL_NAMES[key] && MODEL_NAMES[key].en) || key;
                return `Add ${name}`;
            }
        },
        {
            // <Model> qo'shish
            regex: /^(.+?)\s+qo'shish$/i,
            uz: (m) => `${m[1].trim()} qo'shish`,
            ru: (m) => {
                const key = m[1].trim();
                const name = (MODEL_NAMES[key] && MODEL_NAMES[key].ru) || key;
                return `Добавить ${name}`;
            },
            en: (m) => {
                const key = m[1].trim();
                const name = (MODEL_NAMES[key] && MODEL_NAMES[key].en) || key;
                return `Add ${name}`;
            }
        },
        {
            // 0 of 3 selected / Выбрано 0 из 3 / 3 tadan 0 tasi tanlandi
            regex: /^(?:(\d+)\s+of\s+(\d+)\s+selected|Выбрано\s+(\d+)\s+из\s+(\d+)|(\d+)\s+tadan\s+(\d+)\s+tasi tanlandi)$/i,
            uz: (m) => {
                const sel = m[1] || m[3] || m[6] || 0;
                const tot = m[2] || m[4] || m[5] || 0;
                return `${tot} tadan ${sel} tasi tanlandi`;
            },
            ru: (m) => {
                const sel = m[1] || m[3] || m[6] || 0;
                const tot = m[2] || m[4] || m[5] || 0;
                return `Выбрано ${sel} из ${tot}`;
            },
            en: (m) => {
                const sel = m[1] || m[3] || m[6] || 0;
                const tot = m[2] || m[4] || m[5] || 0;
                return `${sel} of ${tot} selected`;
            }
        },
        {
            // Delete selected <Model> / Tanlangan <Model> ni o'chirish
            regex: /^(?:Delete selected|Удалить выбранные|Tanlangan)\s+(.+?)(?:\s+ni o'chirish)?$/i,
            uz: (m) => "Tanlanganlarni o'chirish",
            ru: (m) => "Удалить выбранные записи",
            en: (m) => "Delete selected items"
        }
    ];

    function translateAdminString(str, lang) {
        if (ADMIN_DICT[str] && ADMIN_DICT[str][lang]) {
            return ADMIN_DICT[str][lang];
        }
        for (const pat of DYNAMIC_ADMIN_PATTERNS) {
            const match = str.match(pat.regex);
            if (match && pat[lang]) {
                return pat[lang](match);
            }
        }
        return null;
    }

    function applyAdminLang(lang) {
        if (!['uz', 'ru', 'en'].includes(lang)) lang = 'uz';
        localStorage.setItem('smartlib_lang', lang);

        // Update active button in Admin navbar switcher
        document.querySelectorAll('.admin-lang-btn').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
        });

        // 1. Translate all <select><option> elements
        document.querySelectorAll('select option').forEach(opt => {
            const txt = (opt.textContent || '').trim().replace(/\s+/g, ' ');
            if (!txt) return;
            if (!opt.dataset.origAdminText) {
                if (translateAdminString(txt, 'uz') !== null) {
                    opt.dataset.origAdminText = txt;
                }
            }
            if (opt.dataset.origAdminText) {
                const tr = translateAdminString(opt.dataset.origAdminText, lang);
                if (tr) {
                    opt.textContent = tr;
                    opt.text = tr;
                }
            }
        });

        // 2. Translate top navbar search placeholders (e.g., "Search Foydalanuvchilar..." / "Найти Foydalanuvchilar...")
        document.querySelectorAll('input[placeholder]').forEach(inp => {
            const ph = (inp.getAttribute('placeholder') || '').trim();
            if (!ph) return;
            if (!inp.dataset.origPh) {
                inp.dataset.origPh = ph;
            }
            const orig = inp.dataset.origPh;
            if (orig.includes('Foydalanuvchilar')) {
                const map = {
                    uz: "Foydalanuvchilarni qidirish...",
                    ru: "Поиск пользователей...",
                    en: "Search users..."
                };
                inp.setAttribute('placeholder', map[lang]);
            } else if (orig.includes('Kitoblar')) {
                const map = {
                    uz: "Kitoblarni qidirish...",
                    ru: "Поиск книг...",
                    en: "Search books..."
                };
                inp.setAttribute('placeholder', map[lang]);
            } else if (orig === 'Search' || orig === 'Найти' || orig === 'Qidirish') {
                const map = { uz: "Qidirish...", ru: "Поиск...", en: "Search..." };
                inp.setAttribute('placeholder', map[lang]);
            }
        });

        // 3. Translate input[type="submit"] values
        document.querySelectorAll('input[type="submit"], button[type="submit"]').forEach(btn => {
            if (btn.tagName === 'INPUT') {
                const val = (btn.value || '').trim();
                if (!btn.dataset.origVal && translateAdminString(val, 'uz') !== null) {
                    btn.dataset.origVal = val;
                }
                if (btn.dataset.origVal) {
                    const tr = translateAdminString(btn.dataset.origVal, lang);
                    if (tr) btn.value = tr;
                }
            }
        });

        // 4. Walk all DOM text nodes
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while ((node = walker.nextNode())) {
            const parent = node.parentElement;
            if (!parent || parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE' || parent.tagName === 'OPTION') continue;
            const raw = node.nodeValue;
            const norm = raw.trim().replace(/\s+/g, ' ');
            if (!norm) continue;

            if (!node._origAdminText) {
                if (translateAdminString(norm, 'uz') !== null) {
                    node._origAdminText = norm;
                }
            }
            if (node._origAdminText) {
                const tr = translateAdminString(node._origAdminText, lang);
                if (tr) {
                    const lead = /^\s/.test(raw) ? ' ' : '';
                    const trail = /\s$/.test(raw) ? ' ' : '';
                    node.nodeValue = lead + tr + trail;
                }
            }
        }
    }

    function injectAdminLangSwitcher() {
        const rightNav = document.querySelector('ul.navbar-nav.ml-auto');
        if (!rightNav || document.getElementById('adminLangSwitcher')) return;

        const li = document.createElement('li');
        li.className = 'nav-item d-flex align-items-center';
        li.id = 'adminLangSwitcher';
        li.innerHTML = `
            <div class="admin-lang-switcher" title="Admin panel tili">
                <button type="button" class="admin-lang-btn" data-lang="uz">UZ</button>
                <button type="button" class="admin-lang-btn" data-lang="ru">RU</button>
                <button type="button" class="admin-lang-btn" data-lang="en">EN</button>
            </div>
        `;
        rightNav.insertBefore(li, rightNav.firstChild);

        li.querySelectorAll('.admin-lang-btn').forEach(btn => {
            btn.addEventListener('click', function () {
                applyAdminLang(this.getAttribute('data-lang'));
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        injectAdminLangSwitcher();
        const savedLang = localStorage.getItem('smartlib_lang') || 'uz';
        applyAdminLang(savedLang);
        // Re-apply after Select2 / Jazzmin async initialization
        setTimeout(() => applyAdminLang(localStorage.getItem('smartlib_lang') || 'uz'), 150);
        setTimeout(() => applyAdminLang(localStorage.getItem('smartlib_lang') || 'uz'), 500);
    });
})();
