# Backup And Restore

Бэкап PostgreSQL:

```bash
cd /opt/eye_w
bash deploy/backup_db.sh
```

Скрипт создаёт `custom`-dump в `/opt/eye_w/backups/`.

Восстановление в пустую БД:

```bash
dropdb eye_w
createdb -O eye_user eye_w
pg_restore --clean --if-exists --no-owner -d postgresql://eye_user:your_password@localhost:5432/eye_w /opt/eye_w/backups/eye_w_YYYYMMDD_HHMMSS.dump
systemctl restart eye_w
```

Минимальный post-restore smoke:

```bash
cd /opt/eye_w
bash deploy/check_stack.sh
```
