# DEVELOPMENT_LOG.md

**Обязательный журнал разработки проекта.**

---

## Назначение файла

DEVELOPMENT_LOG.md используется для:

- фиксации всех изменений
- описания добавленных фич
- фиксации архитектурных решений
- описания рефакторинга
- записи найденных проблем и их решений
- фиксации изменений в базе данных
- отслеживания эволюции проекта

---

## Правила ведения журнала

1. **Каждое изменение** записывается отдельным блоком.
2. **Нельзя добавлять новую функциональность** без записи в DEVELOPMENT_LOG.md.
3. **При изменении архитектуры** необходимо сначала обновить PROJECT_CONTEXT.md, затем зафиксировать изменение в DEVELOPMENT_LOG.md.
4. **Перед внесением изменений в код:** ознакомиться с PROJECT_CONTEXT.md и текущим DEVELOPMENT_LOG.md.
5. **После изменений** обязательно обновить DEVELOPMENT_LOG.md.

---

## Формат записи

```
[DATE] — Краткое название изменения

**Тип изменения:** Feature | Fix | Refactor | Architecture | Database | Improvement

**Описание:**  
Подробное описание того, что было сделано.

**Причина:**  
Почему это изменение было необходимо.

**Затронутые файлы:**  
- путь/к/файлу

**Связь с PROJECT_CONTEXT.md:**  
Указать разделы, которые были использованы или изменены.
```

---

## Записи

---

### [2025-02-18] — Касса и смены по павильонам

**Тип изменения:** Feature, Database

**Описание:**  
Реализована фича «касса и смены»: открытие и закрытие смен по павильонам 1 и 2. Модель `CashShift` (павильон, открыта/закрыта кем и когда, начальный и конечный остаток, статус OPEN/CLOSED). В таблицу `payments` добавлено поле `shift_id` — при приёме оплаты (форма документов и доплата за номера) платёж привязывается к текущей открытой смене соответствующего павильона (госпошлина и павильон 1 → смена павильона 1; павильон 2 → смена павильона 2). API: POST `/cash/shifts` (открыть), PATCH `/cash/shifts/{id}/close` (закрыть), GET `/cash/shifts/current?pavilion=1|2` (текущая смена и сумма по ней), GET `/cash/shifts` (список смен). Права: павильон 1 — оператор/менеджер/админ, павильон 2 — оператор изготовления/менеджер/админ; введена зависимость `RequireCashAccess`. Фронт: страница «Касса и смены» (`cash-shifts.html`) — открыть смену (начальный остаток), закрыть смену (ввод посчитанной суммы), отображение текущей смены и суммы по смене. Ссылка в меню для ролей с доступом к кассе. В nginx добавлен `location /cash`.

**Причина:**  
Учёт по сменам и остаткам в кассе по павильонам (v1.1, по RELEASE_PLAN).

**Затронутые файлы:**  
- backend/app/models/cash_shift.py (новый)
- backend/app/models/payment.py (поле shift_id, связь shift)
- backend/app/models/__init__.py (экспорт CashShift, ShiftStatus)
- backend/app/schemas/cash.py (новый)
- backend/app/api/cash.py (новый)
- backend/app/api/auth.py (RequireCashAccess)
- backend/app/api/orders.py (привязка shift_id при pay и pay_extra)
- backend/app/main.py (миграция cash_shifts, shift_id в payments; роутер cash_router)
- frontend/cash-shifts.html (новый)
- frontend/account.html (ссылка «Касса и смены»)
- deploy/nginx-eye_w.conf (location /cash)

**Связь с PROJECT_CONTEXT.md:**  
Фича «Кассы и смены» из плана v1.1.

---

### [2025-02-18] — Релиз 1.0

**Тип изменения:** Improvement

**Описание:**  
Выполнен план до релиза (RELEASE_PLAN.md). Добавлен RELEASE_PLAN.md с чеклистом и планом на v1.1. В INSTALL.md: инструкция по отключению default nginx при «Welcome to nginx!», рекомендация сменить пароль после первого входа, раздел «Резервное копирование БД» (pg_dump). В README указана версия 1.0, ссылка на RELEASE_PLAN. Версия API в backend/app/main.py изменена на 1.0.0. Чеклист в RELEASE_PLAN отмечен выполненным. Создан тег v1.0.

**Причина:**  
Официально зафиксировать релиз 1.0, завершить чеклист «до релиза».

**Затронутые файлы:**  
- RELEASE_PLAN.md (новый)
- INSTALL.md (nginx, пароль, бэкап)
- README.md (версия 1.0, ссылка на RELEASE_PLAN)
- backend/app/main.py (version="1.0.0")

**Связь с PROJECT_CONTEXT.md:**  
Без изменений.

---

### [2025-02-18] — Аудит: удаление неиспользуемых файлов

**Тип изменения:** Refactor, Improvement

**Описание:**  
Аудит проекта. Удалены: commit_msg.txt (старое сообщение коммита), scripts/deploy.sh (дублирует INSTALL + deploy/setup_server.sh), scripts/patch_zaiavlenie_placeholders.py (однократный скрипт, шаблон уже обновлён). В .gitignore добавлено *.code-workspace. Остальные файлы проверены — все модули backend и frontend используются.

**Причина:**  
Очистка репозитория от мусора и устаревших скриптов.

**Затронутые файлы:**  
- commit_msg.txt (удалён)
- scripts/deploy.sh (удалён)
- scripts/patch_zaiavlenie_placeholders.py (удалён)
- .gitignore (*.code-workspace)

**Связь с PROJECT_CONTEXT.md:**  
Без изменений.

---

### [2025-02-18] — Готовность к запуску: меню, аналитика, навигация

**Тип изменения:** Feature, Improvement

**Описание:**  
Подготовка к релизу. После входа — переход на страницу «Меню» (account.html). В меню: оформление заказов, изготовление номеров (для plate/manager/admin), админка (manager/admin), управление аккаунтами (admin). В админке добавлены: сводка за месяц, учёт по сотрудникам (день/месяц). В index.html добавлена ссылка «Меню». deploy/setup_server.sh добавляет DATABASE_URL в .env при отсутствии. Обновлены USER_GUIDE, INSTALL (логика входа).

**Причина:**  
Цель — готовый продукт к запуску. Единая точка входа (меню), полная аналитика в админке, упрощённая установка.

**Затронутые файлы:**  
- frontend/account.html (ссылка на plate, отображение имени)
- frontend/admin.html (month, employees analytics)
- frontend/index.html (ссылка Меню)
- frontend/login.html (редирект на account)
- deploy/setup_server.sh (DATABASE_URL)
- USER_GUIDE.md

**Связь с PROJECT_CONTEXT.md:**  
Без изменений архитектуры.

---

### [2025-02-18] — Этап C: веб-интерфейс павильона 2 (plate-operator)

**Тип изменения:** Feature

**Описание:**  
Завершён этап C. Добавлен эндпоинт GET /orders/plate-list — список заказов с номерами для павильона 2 с полями: id, public_id, status, total_amount, client (из form_data), total_paid, debt. Один запрос вместо N+1. Frontend plate-operator.html переведён на использование plate-list. Добавлена ссылка «Павильон 2» в шапку index.html. Обновлён USER_GUIDE: описание работы оператора павильона 2, ссылка на plate-operator.html.

**Причина:**  
OrderResponse не содержал form_data; список заказов требовал N запросов к /payments. Нужен единый эндпоинт с клиентом и суммами.

**Затронутые файлы:**  
- backend/app/api/orders.py (GET /orders/plate-list)
- frontend/plate-operator.html (loadOrders через plate-list)
- frontend/index.html (ссылка «Павильон 2»)
- USER_GUIDE.md (раздел Павильон 2)

**Связь с PROJECT_CONTEXT.md:**  
Без изменений архитектуры.

---

### [2025-02-14] — PATCH /employees, docker-compose, раздел «Как тестировать»

**Тип изменения:** Feature, Improvement

**Описание:**  
Реализован PATCH /employees/{id}: обновление сотрудника (name, role, telegram_id, is_active); все поля опциональны. Схема EmployeeUpdate в schemas/employee.py. В README добавлен раздел «Как тестировать» (PostgreSQL локально или через docker-compose, запуск backend и frontend, проверка формы и API). В корне добавлен docker-compose.yml для поднятия PostgreSQL (образ postgres:16-alpine, БД eye_w, пользователь eye_user) для удобного локального теста. В таблицу эндпоинтов README добавлены POST и PATCH для employees.

**Причина:**  
Оставшаяся по плану задача (PATCH /employees); запрос пользователя подготовить тестирование.

**Затронутые файлы:**  
- backend/app/schemas/employee.py (EmployeeUpdate)
- backend/app/api/employees.py (PATCH /employees/{id})
- README.md (эндпоинты, раздел «Как тестировать»)
- docker-compose.yml (новый)

**Связь с PROJECT_CONTEXT.md:**  
Без изменений архитектуры.

---

### [2025-02-14] — Этапы 6 и 7: Telegram-бот павильона 2 и бот владельца

**Тип изменения:** Feature

**Описание:**  
Реализованы этапы 6 и 7. **Бот павильона 2 (bot_plate/):** при оплате заказа с need_plate backend отправляет уведомление в Telegram (сервис telegram_notify.py, переменная TELEGRAM_BOT_TOKEN_PLATE, получатели — employees с role=ROLE_PLATE_OPERATOR и telegram_id). Сообщение с кнопками «Изготовлен», «Доплата получена», «Проблема». Отдельный процесс (bot_plate/main.py) обрабатывает callback, вызывает PATCH /orders/{id}/status с заголовком X-Telegram-User-Id. В API при наличии заголовка проверяется, что telegram_id принадлежит оператору павильона 2. **Бот владельца (bot_owner/):** команды /today, /month, /employees; запросы к /analytics/today, /analytics/month, /analytics/employees. Доступ только для пользователей с role=ROLE_ADMIN (endpoint GET /auth/check-admin?telegram_id=). Добавлены .env.example для ботов, обновлён README.

**Причина:**  
План разработки: боты павильона 2 и владельца (PROJECT_CONTEXT, разделы 11, 4.3).

**Затронутые файлы:**  
- backend/app/services/telegram_notify.py (новый)
- backend/app/api/orders.py (вызов уведомления, проверка X-Telegram-User-Id при PATCH)
- backend/app/api/auth.py (новый, check-admin)
- backend/app/main.py
- backend/requirements.txt (httpx)
- backend/.env.example
- bot_plate/ (main.py, config.py, requirements.txt, .env.example)
- bot_owner/ (main.py, config.py, requirements.txt, .env.example)
- README.md

**Связь с PROJECT_CONTEXT.md:**  
Разделы 4.3, 10, 11.

---

### [2025-02-14] — Этапы 8 и 9: аналитика API, логирование, обработка ошибок, README

**Тип изменения:** Feature

**Описание:**  
Реализованы этапы 8 и 9. **Этап 8:** добавлены GET /analytics/today, GET /analytics/month (выручка, госпошлина, доход павильонов, количество заказов, средний чек), GET /analytics/employees (учёт по сотрудникам за день или месяц, query-параметр period=day|month). **Этап 9:** настроено логирование (core/logging_config.py), логи при старте и при создании/оплате заказа; добавлен глобальный обработчик исключений (ответ 500 в формате JSON); создан README.md с инструкциями по запуску backend и frontend, переменным окружения и списком эндпоинтов.

**Причина:**  
План разработки: аналитика для бота владельца, стабилизация и документация запуска.

**Затронутые файлы:**  
- backend/app/api/analytics.py (новый)
- backend/app/schemas/analytics.py (новый)
- backend/app/core/logging_config.py (новый)
- backend/app/main.py
- backend/app/api/orders.py
- README.md (новый)

**Связь с PROJECT_CONTEXT.md:**  
Разделы 3 (финансовый учёт), 4 (архитектура).

---

### [2025-02-14] — Этап 4: генерация документов (docx) и кнопка «Печать»

**Тип изменения:** Feature

**Описание:**  
Реализован этап 4 плана. Сервис `app/services/docx_service.py`: чтение шаблонов из `templates/`, замена плейсхолдеров `{{ ... }}` по словарю (form_data заказа + маппинг полей формы на имена из шаблонов, дата документа). Добавлен endpoint `GET /orders/{order_id}/documents/{template_name}` — возврат сгенерированного docx (StreamingResponse). Список разрешённых шаблонов ограничен. Во frontend: после оплаты сохраняется `lastOrderId`; по кнопке «Печать документов» запрашиваются документы по типу услуги (и number.docx при необходимости), открываются в новой вкладке для скачивания/печати.

**Причина:**  
Требование плана и PROJECT_CONTEXT: генерация документов для печати.

**Затронутые файлы:**  
- backend/app/services/docx_service.py (новый)
- backend/app/api/documents.py (новый)
- backend/app/main.py
- backend/requirements.txt (python-docx)
- frontend/app.js

**Связь с PROJECT_CONTEXT.md:**  
Разделы 2.1, 13 (поля формы, шаблоны).

---

### [2025-02-14] — Этапы 1–3 плана: бэкенд, заказы/оплата, связка с frontend

**Тип изменения:** Feature

**Описание:**  
Реализованы этапы 1–3 плана разработки. **Этап 1:** структура backend (FastAPI, SQLAlchemy async, PostgreSQL), конфиг и database.py, модели Employee, Order, Payment, Plate, запуск API с CORS и /health, создание таблиц при старте. **Этап 2:** схемы Pydantic для заказа (OrderCreate, OrderResponse), POST /orders (расчёт сумм, сохранение), валидация переходов статусов (order_status.py), POST /orders/{id}/pay (запись в payments, статус PAID), GET /orders и GET /orders/{id}, PATCH /orders/{id}/status. **Этап 3:** в frontend добавлены API_BASE_URL (localhost:8000), отправка формы на POST /orders и POST /orders/{id}/pay по кнопке «Принять наличные», обработка ошибок (alert), GET /employees и выбор оператора (select, employee_id в заказе). Добавлен роутер /employees (GET, POST).

**Причина:**  
Выполнение плана по DEVELOPMENT_PLAN.md.

**Затронутые файлы:**  
- backend/ (новые: app/main.py, config.py, core/database.py, models/, api/orders.py, api/employees.py, schemas/, services/order_service.py, services/order_status.py, requirements.txt)
- frontend/index.html, frontend/app.js, frontend/styles.css

**Связь с PROJECT_CONTEXT.md:**  
Разделы 2, 4, 5, 8, 9, 10, 13.

---

### [2025-02-14] — План разработки (DEVELOPMENT_PLAN.md)

**Тип изменения:** Architecture

**Описание:**  
Создан файл DEVELOPMENT_PLAN.md с разбивкой разработки на этапы и небольшие задачи: основа бэкенда (1), заказы и платежи API (2), связка frontend–backend (3), генерация docx (4), сотрудники (5), Telegram-бот павильона 2 (6), бот владельца (7), аналитика API (8), стабилизация (9). Указан порядок выполнения и связи между этапами.

**Причина:**  
Нужен единый понятный план с конкретными шагами для реализации системы по PROJECT_CONTEXT.

**Затронутые файлы:**  
- DEVELOPMENT_PLAN.md (новый)

**Связь с PROJECT_CONTEXT.md:**  
План опирается на разделы 2–13.

---

### [2025-02-14] — Перенос шаблонов в templates/, удаление dist

**Тип изменения:** Refactor

**Описание:**  
Шаблоны docx из dist/main/templates скопированы в папку templates/ в корне проекта. Папка dist удалена. В PROJECT_CONTEXT (раздел 13) указано, что шаблоны хранятся в templates/.

**Причина:**  
Отказ от артефакта старого приложения (dist); сохранение только нужных шаблонов для будущей генерации документов на бэкенде.

**Затронутые файлы:**  
- templates/ (новые: akt_pp.docx, DKP.docx, dkp_dar.docx, dkp_pieces.docx, doverennost.docx, mreo.docx, number.docx, prokuratura.docx, zaiavlenie.docx)
- PROJECT_CONTEXT.md
- dist/ (удалён)

**Связь с PROJECT_CONTEXT.md:**  
Раздел 13 — уточнено расположение шаблонов.

---

### [2025-02-14] — Виртуальное окружение, .gitignore и правило Git-коммитов

**Тип изменения:** Architecture

**Описание:**  
Создано виртуальное окружение Python (`.venv`) в корне проекта. Добавлен `.gitignore` (исключены `.venv`, `dist/`, `__pycache__`, `.env`, IDE/OS-файлы). Добавлено правило в `.cursor/rules/git-commits.mdc`: после каждого крупного изменения выполнять коммит и пуш с грамотным сообщением на русском.

**Причина:**  
Изолированная среда для бэкенда (FastAPI); не коммитить артефакты и лишнее; фиксировать крупные изменения в Git с понятными сообщениями.

**Затронутые файлы:**  
- .gitignore (новый)
- .cursor/rules/git-commits.mdc (новый)
- .venv/ (создано, в .gitignore)

**Связь с PROJECT_CONTEXT.md:**  
Без изменений контекста.

---

### [2025-02-14] — Поля формы из dist и расширение веб-формы

**Тип изменения:** Feature

**Описание:**  
По плейсхолдерам `{{...}}` в шаблонах docx (dist/main/templates, в т.ч. DKP.docx) восстановлен список полей формы. В PROJECT_CONTEXT.md добавлен раздел 13 «Поля формы оператора (по шаблонам dist)». Веб-форма расширена: блоки «Покупатель/клиент» (ФИО, Паспорт, Адрес, Телефон, Комментарий), «Продавец» (ФИО, Паспорт, Адрес), «Транспортное средство» (VIN, Марка модель, Тип ТС, Год выпуска, Двигатель, № шасси, № кузова, Цвет, СРТС, Гос. номер, ПТС), «Услуга и оплата» дополнена полем «Сумма ДКП». Сводка для документов и app.js обновлены под новые поля; одна форма по-прежнему заполняет блоки итогов и превью.

**Причина:**  
Привести веб-форму в соответствие с полями из прежнего приложения (dist), чтобы одна форма заполняла все документы по шаблонам.

**Затронутые файлы:**  
- PROJECT_CONTEXT.md (раздел 13)
- frontend/index.html
- frontend/styles.css
- frontend/app.js

**Связь с PROJECT_CONTEXT.md:**  
Добавлен раздел 13. Использованы разделы 2.1 (Павильон 1), 4.2 (Frontend).

---

### [2025-02-14] — Разделы 8–12 в PROJECT_CONTEXT

**Тип изменения:** Architecture

**Описание:**  
В PROJECT_CONTEXT.md добавлены разделы 8–12 с единым оформлением (заголовки ##, списки): жизненный цикл заказа (Order Lifecycle), логика финансов, роли пользователей, Telegram-бот павильона 2, принцип «Единый источник правды».

**Причина:**  
Включить в основной документ архитектуры ранее описанные правила (статусы заказа, финансы, роли, бот, источник правды), чтобы они были частью единого контекста.

**Затронутые файлы:**  
- PROJECT_CONTEXT.md

**Связь с PROJECT_CONTEXT.md:**  
Добавлены разделы 8–12.

---

### [2025-02-14] — Ссылка на журнал в PROJECT_CONTEXT

**Тип изменения:** Improvement

**Описание:**  
В раздел 7 «Связь с кодом» PROJECT_CONTEXT.md добавлен пункт 4: обращаться к DEVELOPMENT_LOG.md, чтобы учитывать принятые решения, описанные проблемы и их решения и не повторять ошибок.

**Причина:**  
Необходимость явно разрешить и рекомендовать использование журнала как источника опыта проекта при разработке.

**Затронутые файлы:**  
- PROJECT_CONTEXT.md

**Связь с PROJECT_CONTEXT.md:**  
Изменён раздел 7 (связь с кодом).

---

### [2025-02-14] — Введение обязательного журнала разработки

**Тип изменения:** Architecture

**Описание:**  
Создан файл DEVELOPMENT_LOG.md в корне проекта. Определены назначение журнала, правила ведения и формат записей. В журнал внесены ретроспективные записи о ранее выполненных работах (PROJECT_CONTEXT, правило Cursor, веб-форма операторов).

**Причина:**  
Необходимость единого места фиксации эволюции проекта и согласованности с PROJECT_CONTEXT.md.

**Затронутые файлы:**  
- DEVELOPMENT_LOG.md (новый)

**Связь с PROJECT_CONTEXT.md:**  
Раздел 7 (связь с кодом): добавлено требование вести журнал разработки.

---

### [2025-02-14] — Веб-форма для операторов Павильона 1

**Тип изменения:** Feature

**Описание:**  
Добавлено простое веб-приложение для павильона 1 (оформление документов): одна основная форма с полями клиента, типом услуги, госпошлиной, доп. услугами и номером. Блоки «Итого и оплата», «Сводка для документов» и «Документы для печати» заполняются автоматически на основе основной формы. Реализованы кнопки «Принять наличные» и «Печать документов», выбор оператора (localStorage). Список документов привязан к шаблонам из dist/main/templates.

**Причина:**  
Требование PROJECT_CONTEXT: простое веб-приложение для павильона 1; замена/дополнение прежнего десктоп-приложения удобной веб-формой для операторов.

**Затронутые файлы:**  
- frontend/index.html (новый)
- frontend/styles.css (новый)
- frontend/app.js (новый)

**Связь с PROJECT_CONTEXT.md:**  
Разделы 2.1 (Павильон 1), 4.2 (Frontend). Архитектура не менялась.

---

### [2025-02-14] — Правило Cursor «перед написанием кода»

**Тип изменения:** Architecture

**Описание:**  
Создано правило в .cursor/rules/project-context.mdc с alwaysApply: true. Правило обязывает перед написанием кода ознакомляться с PROJECT_CONTEXT.md, проверять соответствие архитектуре, не нарушать структуру проекта, не добавлять лишние зависимости; при необходимости изменений архитектуры — сначала предлагать их, а не менять молча.

**Причина:**  
Обеспечение согласованности разработки с PROJECT_CONTEXT.md.

**Затронутые файлы:**  
- .cursor/rules/project-context.mdc (новый)

**Связь с PROJECT_CONTEXT.md:**  
Используются разделы 1–6 (цели, структура, архитектура, сущности, принципы).

---

### [2025-02-14] — Создание PROJECT_CONTEXT.md

**Тип изменения:** Architecture

**Описание:**  
В корне проекта создан основной документ архитектуры и логики PROJECT_CONTEXT.md: описание проекта, структура бизнеса (павильоны 1 и 2), финансовый учёт, стек (Python/FastAPI/PostgreSQL, веб, Telegram), сущности БД (orders, payments, plates, employees), жизненный цикл заказа, логика финансов, роли, принцип «единый источник правды».

**Причина:**  
Необходимость единого источника правды по архитектуре и логике для дальнейшей разработки.

**Затронутые файлы:**  
- PROJECT_CONTEXT.md (новый)

**Связь с PROJECT_CONTEXT.md:**  
Файл создан; последующие правки расширяли разделы 8–12.

---

*Конец записей. Новые изменения добавляются сверху этого блока (после «## Записи» и разделителя).*
