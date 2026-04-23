#!/bin/bash
# Всё для запуска на сервере: JWT_SECRET, nginx, перезапуск.
# Запускать из корня проекта: cd /opt/eye_w && bash deploy/setup_server.sh

set -e
cd "$(dirname "$0")/.."

echo "=== 1. backend/.env ==="
if [ ! -f backend/.env ]; then
  touch backend/.env
fi
if ! grep -q '^DATABASE_URL=' backend/.env 2>/dev/null; then
  echo "DATABASE_URL=postgresql+asyncpg://eye_user:eye_pass@localhost:5432/eye_w" >> backend/.env
  echo "Добавлен DATABASE_URL (при необходимости измените пароль)"
fi
if ! grep -q '^JWT_SECRET=' backend/.env 2>/dev/null; then
  SECRET="eye_w_$(openssl rand -hex 24 2>/dev/null || echo "secret_$(date +%s)")"
  echo "JWT_SECRET=$SECRET" >> backend/.env
  echo "Добавлен JWT_SECRET в backend/.env"
else
  echo "JWT_SECRET уже задан"
fi

echo "=== 2. Nginx ==="
cp deploy/nginx-eye_w.conf /etc/nginx/sites-available/eye_w
# Убрать default_server, чтобы не конфликтовать с другими сайтами в sites-enabled
sed -i 's/ listen 80 default_server;/ listen 80;/' /etc/nginx/sites-available/eye_w
ln -sf /etc/nginx/sites-available/eye_w /etc/nginx/sites-enabled/eye_w 2>/dev/null || true
nginx -t
systemctl reload nginx
echo "Nginx обновлён"

if command -v curl >/dev/null 2>&1; then
  echo "=== 2b. Проверка: доходит ли токен до бэкенда через nginx ==="
  TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/login -d "username=sergey151&password=1wq21wq2" -H "Content-Type: application/x-www-form-urlencoded" 2>/dev/null | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
  if [ -n "$TOKEN" ]; then
    CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" http://127.0.0.1/auth/me 2>/dev/null)
    if [ "$CODE" = "200" ]; then
      echo "OK: nginx передаёт Authorization, /auth/me вернул 200"
    else
      echo "ВНИМАНИЕ: /auth/me через nginx вернул $CODE (нужно 200). Убедитесь что в location /auth/ есть: proxy_set_header Authorization \$http_authorization;"
    fi
  else
    echo "Токен не получен (проверьте: systemctl status eye_w)"
  fi
fi

echo "=== 3. Backend (systemd) ==="
if [ ! -f /etc/systemd/system/eye_w.service ]; then
  cat > /etc/systemd/system/eye_w.service << 'SVC'
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
SVC
  systemctl daemon-reload
  systemctl enable eye_w
  echo "Создан сервис eye_w.service"
fi
if systemctl restart eye_w 2>/dev/null; then
  echo "Сервис eye_w перезапущен"
else
  echo "Запуск сервиса: systemctl start eye_w"
  systemctl start eye_w 2>/dev/null || true
fi

echo ""
echo "Готово. Откройте сайт и войдите: sergey151 / 1wq21wq2"
