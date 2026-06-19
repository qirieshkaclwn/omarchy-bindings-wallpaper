# Omarchy Keybindings Wallpaper

*Читать на других языках: [English](README.md).*

![Демонстрация работы](preview.png)

Легковесный фоновый демон для дистрибутива Omarchy (на базе Hyprland), который автоматически рендерит шпаргалку с горячими клавишами системы прямо на ваши текущие обои в виде красивой полупрозрачной панели.

---

## Возможности

1. **Динамическая верстка и адаптивность:** 
   Скрипт анализирует количество уникальных биндов и автоматически распределяет их в сетку от 1 до 4 колонок. Панель центрируется на экране как по вертикали, так и по горизонтали.
2. **Умная фильтрация и компактность:**
   * Объединяет повторяющиеся числовые комбинации (например, переключение воркспейсов `SUPER + 1..9` группируется в одну емкую строку).
   * Исключает ярлыки запуска сторонних приложений и веб-сайтов (Signal, Obsidian, WhatsApp, Docker, почта и т.д.), чтобы не перегружать экран.
   * Оставляет только ключевые системные действия, а также запуск Терминала и Браузера.
   * Общий объем списка жестко лимитирован до 50 биндов (вмещается в 2 компактные колонки).
3. **Автоматическое обновление (Event-Driven):**
   * Следит за файлами настроек в `~/.config/hypr/` и мгновенно перерисовывает обои при добавлении или изменении любого бинда.
   * Отслеживает ручную смену темы обоев или переключение картинок, накладывая шпаргалку на новые обои «на лету».
4. **Системная интеграция:**
   * Запускается и работает как стандартная служба пользователя systemd. Не расходует процессор и память впустую (проверка изменений происходит раз в 3 секунды).
   * Защищен от бесконечного цикла самоперезаписи обоев.

---

## Требования

Для работы плагина необходимы:
* Python 3
* Библиотека для работы с изображениями Pillow (`pip install Pillow`)
* Установленный шрифт JetBrains Mono Nerd Font (по умолчанию ожидается по пути `/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf`)
* Утилита отрисовки обоев swaybg (стандартная для Omarchy)

---

## Установка

Вы можете установить и запустить расширение одной командой:

```bash
git clone https://github.com/qirieshkaclwn/omarchy-bindings-wallpaper.git ~/.config/omarchy/extensions/bindings-wallpaper && mkdir -p ~/.config/systemd/user/ && ln -sf ~/.config/omarchy/extensions/bindings-wallpaper/omarchy-bindings-wallpaper.service ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now omarchy-bindings-wallpaper.service
```

Или выполните шаги установки вручную:

1. **Склонируйте репозиторий** в директорию расширений:
   ```bash
   git clone https://github.com/qirieshkaclwn/omarchy-bindings-wallpaper.git ~/.config/omarchy/extensions/bindings-wallpaper
   ```

2. **Зарегистрируйте службу systemd**, создав символическую ссылку:
   ```bash
   mkdir -p ~/.config/systemd/user/
   ln -sf ~/.config/omarchy/extensions/bindings-wallpaper/omarchy-bindings-wallpaper.service ~/.config/systemd/user/
   ```

3. **Запустите службу**:
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now omarchy-bindings-wallpaper.service
   ```

---

## Проверка работы

Вы можете проверить состояние работающей службы с помощью команды:
```bash
systemctl --user status omarchy-bindings-wallpaper.service
```

Любые изменения в файле `~/.config/hypr/bindings.conf` теперь автоматически отобразятся на ваших обоях в течение 3 секунд!

---

## Лицензия

Этот проект распространяется под лицензией [MIT License](LICENSE).
