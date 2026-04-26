#!/bin/bash
# Всё для запуска на сервере: env, nginx, перезапуск.
# Запускать из корня проекта: cd /opt/eye_w && bash deploy/setup_server.sh

set -e
cd "$(dirname "$0")/.."

APP_USER="eye_w"
APP_GROUP="$APP_USER"
PROJECT_ROOT="/opt/eye_w"

if ! command -v curl >/dev/null 2>&1; then
  echo "=== 0. Установка curl ==="
  apt-get update
  apt-get install -y curl
fi

echo "=== 0b. Системный пользователь приложения ==="
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir /var/lib/"$APP_USER" --shell /usr/sbin/nologin "$APP_USER"
  echo "Создан пользователь $APP_USER"
fi
chown -R "$APP_USER":"$APP_GROUP" "$PROJECT_ROOT"/backend "$PROJECT_ROOT"/frontend "$PROJECT_ROOT"/templates

echo "=== 1. backend/.env ==="
if [ ! -f backend/.env ]; then
  touch backend/.env
fi

set_env_if_missing_or_empty() {
  KEY="$1"
  VALUE="$2"
  DESCRIPTION="$3"
  CURRENT="$(sed -n "s/^${KEY}=//p" backend/.env | head -n1)"
  if [ -z "$CURRENT" ]; then
    if grep -q "^${KEY}=" backend/.env 2>/dev/null; then
      sed -i "s|^${KEY}=.*|${KEY}=${VALUE}|" backend/.env
    else
      echo "${KEY}=${VALUE}" >> backend/.env
    fi
    echo "${DESCRIPTION}"
  fi
}

set_env_if_missing_or_empty "DATABASE_URL" "postgresql+asyncpg://eye_user:eye_pass@localhost:5432/eye_w" "Добавлен DATABASE_URL (при необходимости измените пароль)"
set_env_if_missing_or_empty "APP_ENV" "production" "Добавлен APP_ENV=production"

SECRET_CURRENT="$(sed -n 's/^JWT_SECRET=//p' backend/.env | head -n1)"
if [ -z "$SECRET_CURRENT" ]; then
  SECRET="eye_w_$(openssl rand -hex 24 2>/dev/null || echo "secret_$(date +%s)")"
  set_env_if_missing_or_empty "JWT_SECRET" "$SECRET" "Добавлен JWT_SECRET в backend/.env"
else
  echo "JWT_SECRET уже задан"
fi

set_env_if_missing_or_empty "CORS_ORIGINS" "http://localhost,http://127.0.0.1" "Добавлен CORS_ORIGINS (обновите под ваш домен)"
set_env_if_missing_or_empty "SUPERUSER_LOGIN" "admin" "Добавлен SUPERUSER_LOGIN=admin"
set_env_if_missing_or_empty "SUPERUSER_NAME" "Администратор" "Добавлен SUPERUSER_NAME=Администратор"

SUPERPASS="$(sed -n 's/^SUPERUSER_PASSWORD=//p' backend/.env | head -n1)"
if [ -z "$SUPERPASS" ]; then
  SUPERPASS="$(openssl rand -base64 18 2>/dev/null | tr -d '\n' || echo "ChangeMe_$(date +%s)")"
  set_env_if_missing_or_empty "SUPERUSER_PASSWORD" "$SUPERPASS" "Добавлен SUPERUSER_PASSWORD в backend/.env"
fi

echo "=== 2. Nginx ==="
cp deploy/nginx-eye_w.conf /etc/nginx/sites-available/eye_w
# Убрать default_server, чтобы не конфликтовать с другими сайтами в sites-enabled
sed -i 's/ listen 80 default_server;/ listen 80;/' /etc/nginx/sites-available/eye_w
if [ -L /etc/nginx/sites-enabled/default ]; then
  unlink /etc/nginx/sites-enabled/default
fi
ln -sf /etc/nginx/sites-available/eye_w /etc/nginx/sites-enabled/eye_w 2>/dev/null || true
nginx -t
systemctl reload nginx
echo "Nginx обновлён"

echo "=== 2b. Проверка nginx/auth выполняется после рестарта в deploy/check_stack.sh ==="

echo "=== 3. Backend (systemd) ==="
echo "=== 3a. Зависимости backend ==="
if [ -x "$PROJECT_ROOT/backend/.venv/bin/pip" ]; then
  "$PROJECT_ROOT/backend/.venv/bin/pip" install -r "$PROJECT_ROOT/backend/requirements.txt"
else
  echo "pip не найден в $PROJECT_ROOT/backend/.venv/bin/pip — пропускаю обновление зависимостей"
fi

echo "=== 3b. Базовая схема БД ==="
set -a
# shellcheck disable=SC1091
. "$PROJECT_ROOT/backend/.env"
set +a
if [ -x "$PROJECT_ROOT/backend/.venv/bin/python" ]; then
  (cd "$PROJECT_ROOT/backend" && "$PROJECT_ROOT/backend/.venv/bin/python" -m app.bootstrap.create_schema)
else
  echo "python не найден в $PROJECT_ROOT/backend/.venv/bin/python — пропускаю bootstrap схемы"
fi

echo "=== 3c. Миграции БД ==="
if [ -x "$PROJECT_ROOT/backend/.venv/bin/alembic" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$PROJECT_ROOT/backend/.env"
  set +a
  (cd "$PROJECT_ROOT" && "$PROJECT_ROOT/backend/.venv/bin/alembic" upgrade head)
else
  echo "Alembic не найден в backend/.venv/bin/alembic — пропускаю миграции"
fi

if [ ! -f /etc/systemd/system/eye_w.service ]; then
  true
fi
cat > /etc/systemd/system/eye_w.service << SVC
[Unit]
Description=Eye-W Backend
After=network.target postgresql.service

[Service]
User=$APP_USER
Group=$APP_GROUP
WorkingDirectory=$PROJECT_ROOT/backend
EnvironmentFile=$PROJECT_ROOT/backend/.env
ExecStart=$PROJECT_ROOT/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload
systemctl enable eye_w >/dev/null 2>&1 || true
if systemctl restart eye_w 2>/dev/null; then
  echo "Сервис eye_w перезапущен"
else
  echo "Запуск сервиса: systemctl start eye_w"
  systemctl start eye_w 2>/dev/null || true
fi

echo ""
echo "Готово. Откройте сайт и войдите:"
echo "  Логин: $(sed -n 's/^SUPERUSER_LOGIN=//p' backend/.env | head -n1)"
echo "  Пароль не выводится в stdout."
echo "  Посмотреть его на сервере: grep '^SUPERUSER_PASSWORD=' $PROJECT_ROOT/backend/.env"
echo "После первого входа смените пароль и настройте HTTPS отдельным этапом."
