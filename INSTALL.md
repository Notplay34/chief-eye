# Как установить и запустить систему «Павильоны МРЭО»

> Актуальный документ для локальной установки и первого запуска.
> Если нужен только общий обзор проекта, начните с `README.md`.
> Если нужен продакшн-деплой, используйте `DEPLOYMENT.md`.

**Для кого:** владелец или человек, который настраивает сервер.  
**Что получится:** рабочий сайт, куда заходят операторы и оформляют заказы.

---

## Вариант 1: Сервер уже настроен (только обновить код)

Если система уже стояла раньше и нужно просто подтянуть новую версию:

```bash
cd /opt/eye_w
git pull
bash deploy/setup_server.sh
```

**Если после обновления не работают новые разделы** (например Склад, касса номеров) — сервер возвращает HTML вместо данных. Обновите конфиг nginx и перезагрузите его:

```bash
cp /opt/eye_w/deploy/nginx-eye_w.conf /etc/nginx/sites-available/eye_w
nginx -t && systemctl reload nginx
systemctl restart eye_w
```

Готово. Откройте сайт в браузере.

---

## Вариант 2: Чистый сервер с нуля

### Шаг 1. Подключиться к серверу

Через SSH, например:

```
ssh root@ВАШ_IP
```

(подставьте свой IP или домен)

---

### Шаг 2. Установить нужные программы

Скопируйте и выполните одну команду:

```bash
apt update && apt install -y python3.11 python3.11-venv python3-pip postgresql nginx git
```

---

### Шаг 3. Создать базу данных

**Важно:** база должна быть с кодировкой **UTF-8**, иначе при сохранении заказов с русским текстом будет ошибка «conversion between UTF8 and SQL_ASCII is not supported».

```bash
su - postgres
psql -c "CREATE USER eye_user WITH PASSWORD 'eye_pass';"
psql -c "CREATE DATABASE eye_w OWNER eye_user ENCODING 'UTF8' LC_COLLATE='C.UTF-8' LC_CTYPE='C.UTF-8' TEMPLATE=template0;"
exit
```

Если появится ошибка «locale C.UTF-8 does not exist», создайте базу так:  
`psql -c "CREATE DATABASE eye_w OWNER eye_user ENCODING 'UTF8' TEMPLATE=template0;"`

(Если `sudo` есть: `sudo -u postgres psql -c "..."` вместо входа в `su - postgres`.)

Пароль `eye_pass` можно заменить на свой — тогда его нужно будет указать в следующем шаге.

---

### Шаг 4. Скачать код проекта

**Если код на GitHub:**

```bash
cd /opt
git clone https://github.com/Notplay34/eye_w.git
cd eye_w
```

**Если код копируете с компьютера (Windows PowerShell):**

```powershell
scp -r c:\dev\mreo\eye_w root@ВАШ_IP:/opt/eye_w
```

Потом на сервере: `cd /opt/eye_w`.

---

### Шаг 5. Настроить backend

```bash
cd /opt/eye_w/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Создать файл с настройками:

```bash
nano .env
```

Вставить (подставьте свой пароль БД, если меняли):

```
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://eye_user:eye_pass@localhost:5432/eye_w
JWT_SECRET=придумайте_длинный_секретный_ключ_минимум_32_символа
SUPERUSER_LOGIN=admin
SUPERUSER_PASSWORD=ваш_надёжный_пароль
SUPERUSER_NAME=Администратор
CORS_ORIGINS=https://ваш-домен.ru
```

Пароль суперпользователя (**SUPERUSER_PASSWORD**) задайте свой; после первого входа обязательно смените его в интерфейсе (Меню → Управление аккаунтами). Если не задать все `SUPERUSER_*`, стартовая учётка автоматически не создастся.

Сохранить: `Ctrl+O`, `Enter`, `Ctrl+X`.

---

### Шаг 6. Создать сервис и nginx

Скопировать и выполнить:

```bash
cat > /etc/systemd/system/eye_w.service << 'EOF'
[Unit]
Description=Eye-W Backend
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/opt/eye_w/backend
ExecStart=/opt/eye_w/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable eye_w
systemctl start eye_w
```

Настроить nginx:

```bash
cp /opt/eye_w/deploy/nginx-eye_w.conf /etc/nginx/sites-available/eye_w
ln -sf /etc/nginx/sites-available/eye_w /etc/nginx/sites-enabled/eye_w
nginx -t
systemctl reload nginx
```

---

### Шаг 7. Проверить

Откройте в браузере:

- `http://ВАШ_IP` — должна открыться страница входа.
- Войдите: логин и пароль из `backend/.env` (`SUPERUSER_LOGIN`, `SUPERUSER_PASSWORD`).

Если страница открылась и вход прошёл — всё работает. **Сразу после первого входа смените пароль** суперпользователя (Меню → Управление аккаунтами).

**Если видите «Welcome to nginx!»** вместо формы входа — отключите стандартный сайт nginx:

```bash
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

**После первого входа обязательно смените пароль** суперпользователя: Меню → Управление аккаунтами → выбрать пользователя (например «Сергей») → задать новый пароль. Дефолтный пароль из .env не оставляйте в продакшене.

---

## Если что-то пошло не так

**Сайт не открывается:**
- Проверьте: `systemctl status eye_w` — сервис должен быть `active (running)`.
- Проверьте: `curl http://127.0.0.1:8000/health` — должен вернуть `{"status":"ok"}`.

**Не входит в систему:**
- Убедитесь, что в `backend/.env` есть `JWT_SECRET`.
- Перезапустите: `systemctl restart eye_w`.

**Ошибка базы данных:**
- Проверьте, что PostgreSQL запущен: `systemctl status postgresql`.
- Проверьте пароль в `DATABASE_URL` в `backend/.env`.

**«Внутренняя ошибка сервера» при нажатии «Принять наличные»:**
- Касса в системе не нужна — платёж пишется в БД. Смотрите лог: `journalctl -u eye_w --no-pager -n 50`.
- **«conversion between UTF8 and SQL_ASCII is not supported»** — база создана без UTF-8. Пересоздайте БД с кодировкой UTF-8 (см. ниже «Пересоздание БД с UTF-8»).
- Другие ошибки: после обновления кода выполните `systemctl restart eye_w` — при старте недостающие колонки добавляются автоматически.

**Пересоздание БД с UTF-8** (если была ошибка SQL_ASCII):

```bash
su - postgres
psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'eye_w' AND pid <> pg_backend_pid();"
psql -c "DROP DATABASE eye_w;"
psql -c "CREATE DATABASE eye_w OWNER eye_user ENCODING 'UTF8' LC_COLLATE='C.UTF-8' LC_CTYPE='C.UTF-8' TEMPLATE=template0;"
exit
systemctl restart eye_w
```

После этого зайдите на сайт снова; стартовая учётка будет создана только если в `backend/.env` заданы все `SUPERUSER_*`. Старые заказы в БД пропадут.

---

## Резервное копирование БД (рекомендуется)

Периодически сохраняйте копию базы на сервере или скачивайте на свой компьютер:

```bash
su - postgres -c "pg_dump eye_w" > /root/eye_w_backup_$(date +%Y%m%d).sql
```

Восстановление (если понадобится): `psql -U eye_user eye_w < файл_бэкапа.sql`.

---

## Обновление после изменений в коде

```bash
cd /opt/eye_w
git pull
systemctl restart eye_w
```

Или одной командой (если используете setup_server.sh):

```bash
cd /opt/eye_w && git pull && bash deploy/setup_server.sh
```
