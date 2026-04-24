# Серверный деплой

Актуальный документ для выката текущего стека:

- `FastAPI`
- `PostgreSQL`
- `nginx`
- `systemd`

## 1. Что должно быть на сервере

- код проекта в `/opt/eye_w`
- PostgreSQL
- nginx
- виртуальное окружение `backend/.venv`
- systemd-сервис `eye_w`

## 2. Базовая последовательность

```bash
cd /opt/eye_w
bash deploy/setup_server.sh
```

После этого проверить:

```bash
cd /opt/eye_w
bash deploy/check_stack.sh
```

`backend/.env` для production должен содержать:

```env
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://eye_user:your_password@localhost:5432/eye_w
JWT_SECRET=long_random_secret
CORS_ORIGINS=https://your-domain.example
SUPERUSER_LOGIN=admin
SUPERUSER_PASSWORD=strong_password
SUPERUSER_NAME=Администратор
```

## 3. systemd

`/etc/systemd/system/eye_w.service`

```ini
[Unit]
Description=Eye-W Backend
After=network.target postgresql.service

[Service]
User=eye_w
Group=eye_w
WorkingDirectory=/opt/eye_w/backend
EnvironmentFile=/opt/eye_w/backend/.env
ExecStart=/opt/eye_w/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Команды:

```bash
systemctl daemon-reload
systemctl enable eye_w
systemctl restart eye_w
systemctl status eye_w
```

## 4. nginx

Использовать конфиг:

- `deploy/nginx-eye_w.conf`

Подключение:

```bash
cp /opt/eye_w/deploy/nginx-eye_w.conf /etc/nginx/sites-available/eye_w
ln -sf /etc/nginx/sites-available/eye_w /etc/nginx/sites-enabled/eye_w
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

nginx должен проксировать как минимум:

- `/auth/`
- `/orders`
- `/cash/`
- `/employees`
- `/analytics`
- `/warehouse/`
- `/form-history`
- `/price-list`
- `/health`
- `/docs`
- `/openapi.json`

### HTTPS

Для релиза сайт должен работать через HTTPS. Базовый вариант через certbot:

```bash
apt-get update
apt-get install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.example
nginx -t
systemctl reload nginx
```

После выпуска сертификата проверьте, что:

- `http://your-domain.example` редиректит на `https://your-domain.example`;
- `/auth/login` и `/auth/me` работают через nginx;
- в `backend/.env` `CORS_ORIGINS` указывает на `https://your-domain.example`.

## 5. Автоматическая серверная проверка

После выката выполнить:

```bash
cd /opt/eye_w
bash deploy/check_stack.sh
```

Скрипт проверяет:

- что сервис не запущен от `root`
- `/health` напрямую и через nginx
- логин суперпользователя
- `/auth/me` напрямую и через nginx
- `/analytics/dashboard` через nginx
- ключевые статические страницы

Подробный чеклист: [docs/SMOKE_TEST.md](/Users/NotPlay/Documents/dev/pavilion/docs/SMOKE_TEST.md)

## 6. Бэкап и восстановление

```bash
cd /opt/eye_w
bash deploy/backup_db.sh
```

Runbook: [docs/BACKUP_AND_RESTORE.md](/Users/NotPlay/Documents/dev/pavilion/docs/BACKUP_AND_RESTORE.md)

## 7. Обновление

```bash
cd /opt/eye_w
bash deploy/backup_db.sh
bash deploy/setup_server.sh
bash deploy/check_stack.sh
```

Для сервера с данными бэкап перед обновлением обязателен. `setup_server.sh` сначала безопасно проверяет/создаёт базовую схему БД, затем применяет Alembic-миграции и перезапускает backend.

Пароль суперпользователя `setup_server.sh` больше не печатает в stdout. При необходимости смотреть на сервере:

```bash
grep '^SUPERUSER_PASSWORD=' /opt/eye_w/backend/.env
```

## 8. Если что-то не работает

Проверять:

```bash
systemctl status eye_w
journalctl -u eye_w --no-pager -n 100
nginx -t
curl http://127.0.0.1:8000/health
curl http://127.0.0.1/health
```
