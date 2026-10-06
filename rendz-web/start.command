#!/bin/bash
# Запуск rendz на Mac: двойной клик по файлу (или в Терминале: bash start.command)
cd "$(dirname "$0")"

if ! command -v node >/dev/null 2>&1; then
  echo "Не найден Node.js. Установи его (бесплатно) и запусти этот файл ещё раз:"
  echo "  https://nodejs.org  (кнопка LTS)"
  echo "или через Homebrew:  brew install node"
  read -n 1 -s -r -p "Нажми любую клавишу…"
  exit 1
fi

node server.js
