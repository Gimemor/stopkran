#!/usr/bin/env bash
# Локальная среда «Стоп-кран»: Postgres + pgAdmin + FastAPI через docker compose.
#
#   ./run.sh            # поднять всё и дождаться готовности БД
#   ./run.sh --logs     # смотреть логи API
#   ./run.sh --down     # остановить (данные сохраняются)
#   ./run.sh --reset    # снести volume и поднять чистую БД
#   ./run.sh --no-pgadmin
set -euo pipefail

cd "$(dirname "$0")"

DB_USER="${POSTGRES_USER:-stopkran}"
DB_NAME="${POSTGRES_DB:-stopkran}"
PGADMIN_EMAIL="${PGADMIN_EMAIL:-admin@example.com}"
PGADMIN_PASSWORD="${PGADMIN_PASSWORD:-admin}"

WITH_PGADMIN=1
DO_DOWN=0
DO_RESET=0
DO_LOGS=0

for arg in "$@"; do
  case "$arg" in
    --down) DO_DOWN=1 ;;
    --reset) DO_RESET=1 ;;
    --logs) DO_LOGS=1 ;;
    --no-pgadmin) WITH_PGADMIN=0 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Неизвестный аргумент: $arg" >&2; exit 1 ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден в PATH." >&2
  exit 1
fi
if ! docker info --format '{{.ServerVersion}}' >/dev/null 2>&1; then
  echo "Docker daemon не отвечает. Запустите Docker Desktop." >&2
  exit 1
fi

if [ "$DO_DOWN" = "1" ]; then
  echo "Останавливаю окружение (данные сохраняются)..."
  docker compose down
  exit 0
fi

if [ "$DO_RESET" = "1" ]; then
  echo "Удаляю контейнеры и volume с данными..."
  docker compose down -v
fi

SERVICES=(db api)
if [ "$WITH_PGADMIN" = "1" ]; then
  SERVICES+=(pgadmin)
fi

echo "Собираю и запускаю: ${SERVICES[*]}"
docker compose up -d --build "${SERVICES[@]}"

printf "Ждём Postgres"
deadline=$(( $(date +%s) + 120 ))
until docker compose exec -T db pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo
    echo "Postgres не поднялся за 120 секунд. Логи: docker compose logs db" >&2
    exit 1
  fi
  printf "."
  sleep 2
done
echo " — готово."

if [ "$DO_LOGS" = "1" ]; then
  exec docker compose logs -f api
fi

cat <<EOF

Готово. Локальная среда запущена:

  API / Swagger : http://localhost:8000/docs
  Лента (JSON)  : http://localhost:8000/api/feed
  Postgres      : localhost:5432   db=$DB_NAME user=$DB_USER pass=stopkran
  pgAdmin       : http://localhost:5050   $PGADMIN_EMAIL / $PGADMIN_PASSWORD

Фронтенд: index.html открывайте через локальный сервер, не file://
  npx --yes serve -l 5500 .    →  http://localhost:5500

Логи:  ./run.sh --logs     Стоп:  ./run.sh --down     Чистая БД:  ./run.sh --reset
EOF
