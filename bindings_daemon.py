import subprocess
import os
import sys
import json
import time
import math
import argparse
import shutil
from PIL import Image, ImageDraw, ImageFont

HOME = os.path.expanduser("~")

def ensure_wayland_env():
    uid = os.getuid()

    if "OMARCHY_PATH" not in os.environ:
        os.environ["OMARCHY_PATH"] = "/usr/share/omarchy"

    extra_paths = [
        os.path.join(HOME, ".local/bin"),
        "/usr/local/bin",
        "/usr/bin",
        "/usr/share/omarchy/bin",
    ]
    current_paths = os.environ.get("PATH", "").split(":")
    for p in reversed(extra_paths):
        if p not in current_paths and os.path.isdir(p):
            current_paths.insert(0, p)
    os.environ["PATH"] = ":".join(current_paths)

    # Detect HYPRLAND_INSTANCE_SIGNATURE
    run_user_hypr = f"/run/user/{uid}/hypr"
    if os.path.exists(run_user_hypr):
        dirs = [d for d in os.listdir(run_user_hypr) if os.path.isdir(os.path.join(run_user_hypr, d))]
        if dirs:
            dirs.sort(key=lambda x: os.path.getmtime(os.path.join(run_user_hypr, x)), reverse=True)
            os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = dirs[0]
    else:
        tmp_hypr = "/tmp/hypr"
        if os.path.exists(tmp_hypr):
            dirs = [d for d in os.listdir(tmp_hypr) if os.path.isdir(os.path.join(tmp_hypr, d))]
            if dirs:
                dirs.sort(key=lambda x: os.path.getmtime(os.path.join(tmp_hypr, x)), reverse=True)
                os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = dirs[0]
                    
    # Detect WAYLAND_DISPLAY
    run_user = f"/run/user/{uid}"
    if os.path.exists(run_user):
        wayland_files = [
            f for f in os.listdir(run_user)
            if f.startswith("wayland-") and not f.endswith(".lock")
        ]
        if wayland_files:
            wayland_files.sort(key=lambda x: os.path.getmtime(os.path.join(run_user, x)), reverse=True)
            os.environ["WAYLAND_DISPLAY"] = wayland_files[0]

ensure_wayland_env()

def get_current_theme_name():
    """Определяет текущую тему Omarchy"""
    paths = [
        os.path.join(HOME, ".local/state/omarchy/current/theme.name"),
        os.path.join(HOME, ".config/omarchy/current/theme.name"),
    ]
    for p in paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    name = f.read().strip()
                    if name:
                        return name
            except Exception:
                pass
    return None

def get_bg_link():
    """Определяет путь к симлинку текущего фона в Omarchy (Quattro / Legacy)"""
    state_link = os.path.join(HOME, ".local/state/omarchy/current/background")
    config_link = os.path.join(HOME, ".config/omarchy/current/background")
    if os.path.exists(state_link) or os.path.isdir(os.path.dirname(state_link)):
        return state_link
    return config_link

def get_watch_files():
    """Возвращает список отслеживаемых конфигурационных файлов Hyprland (Lua и Conf) и темы Omarchy"""
    files = set()
    hypr_dir = os.path.join(HOME, ".config/hypr")
    if os.path.isdir(hypr_dir):
        files.add(hypr_dir)
        for f in os.listdir(hypr_dir):
            if f.endswith((".lua", ".conf")):
                files.add(os.path.join(hypr_dir, f))
    defaults = [
        os.path.join(HOME, ".config/hypr/bindings.lua"),
        os.path.join(HOME, ".config/hypr/bindings.conf"),
        os.path.join(HOME, ".config/hypr/input.lua"),
        os.path.join(HOME, ".config/hypr/input.conf"),
        os.path.join(HOME, ".config/hypr/looknfeel.lua"),
        os.path.join(HOME, ".config/hypr/looknfeel.conf"),
        os.path.join(HOME, ".config/hypr/hyprland.lua"),
        os.path.join(HOME, ".config/hypr/hyprland.conf"),
        os.path.join(HOME, ".config/hypr/monitors.lua"),
        os.path.join(HOME, ".config/hypr/autostart.lua"),
        os.path.join(HOME, ".local/state/omarchy/current/theme.name"),
        os.path.join(HOME, ".local/state/omarchy/current/theme"),
        os.path.join(HOME, ".config/omarchy/current/theme.name"),
        os.path.join(HOME, ".config/omarchy/current/theme"),
    ]
    for p in defaults:
        files.add(p)
    return sorted(list(files))

GENERATED_DIR = os.path.join(HOME, "Pictures")
GENERATED_PREFIX = "wallpaper_with_bindings"
CACHE_DIR = os.path.join(HOME, ".cache/omarchy")
SOURCE_WP_CACHE = os.path.join(CACHE_DIR, "last_source_wallpaper.txt")
LAST_THEME_CACHE = os.path.join(CACHE_DIR, "last_theme.txt")
FONT_PATH = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf"

def is_generated(path):
    """Проверяет, является ли путь одним из сгенерированных демоном обоев"""
    if not path:
        return False
    try:
        real = os.path.realpath(path)
        base = os.path.basename(real)
        return base.startswith(GENERATED_PREFIX) and base.endswith(".png")
    except Exception:
        return False

def cleanup_old_wallpapers(current_path, keep=2):
    """Удаляет старые сгенерированные файлы обоев, сохраняя актуальные"""
    try:
        if not os.path.isdir(GENERATED_DIR):
            return
        files = []
        for fname in os.listdir(GENERATED_DIR):
            if fname.startswith(GENERATED_PREFIX) and fname.endswith(".png"):
                full_path = os.path.join(GENERATED_DIR, fname)
                if os.path.isfile(full_path):
                    files.append(full_path)
        # Сортируем по времени модификации: самые новые первыми
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for old_file in files[keep:]:
            if old_file != current_path:
                try:
                    os.remove(old_file)
                except OSError:
                    pass
    except Exception as e:
        print(f"Error during cleanup of old wallpapers: {e}", file=sys.stderr)

def get_locale_lang():
    # Если в любой из переменных локали указан русский, используем его (актуально при LANG=en и LC_TIME=ru)
    for key, val in os.environ.items():
        if (key.startswith("LC_") or key == "LANG") and "ru" in val.lower():
            return "ru"
            
    # Стандартный поиск по приоритетам
    for var in ["LC_MESSAGES", "LANG", "LC_TIME", "LC_NUMERIC", "LC_MONETARY"]:
        val = os.environ.get(var, "")
        if val:
            lang = val.split(".")[0].split("_")[0].lower()
            if lang and lang != "en":
                return lang
                
    try:
        import locale
        for cat in [locale.LC_MESSAGES, locale.LC_TIME, locale.LC_NUMERIC]:
            lang = locale.getlocale(cat)[0]
            if lang:
                lang = lang.split(".")[0].split("_")[0].lower()
                if lang:
                    return lang
    except Exception:
        pass
        
    return "en"

LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")

def load_translations():
    lang = get_locale_lang()
    # Fallback default values (English)
    translations = {
        "header_text": "SYSTEM KEYBINDINGS",
        "go_to_workspace": "Go to workspace 1..",
        "move_window_to_workspace": "Move window to workspace 1..",
        "move_window_silently_to_workspace": "Move window silently to workspace 1..",
        "go_to_window_group": "Go to window group 1.."
    }
    
    locale_file = os.path.join(LOCALES_DIR, f"{lang}.json")
    if os.path.exists(locale_file):
        try:
            with open(locale_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                translations.update(loaded)
        except Exception as e:
            print(f"Error loading locale file {locale_file}: {e}", file=sys.stderr)
            
    return translations

TRANSLATIONS = load_translations()

def get_mtimes():
    """Получает время модификации отслеживаемых файлов"""
    mtimes = {}
    for f in get_watch_files():
        if os.path.exists(f):
            mtimes[f] = os.path.getmtime(f)
    return mtimes

def get_screen_resolution():
    """Получает разрешение активного монитора"""
    width, height = 1920, 1080
    try:
        mon_out = subprocess.check_output(["hyprctl", "monitors", "-j"]).decode("utf-8")
        mon_data = json.loads(mon_out)
        for m in mon_data:
            if m.get("focused"):
                width = m.get("width", 1920)
                height = m.get("height", 1080)
                break
    except Exception as e:
        print(f"Error getting resolution: {e}", file=sys.stderr)
    return width, height

def get_source_wallpaper():
    """Определяет путь к исходным обоям без наложенных биндов"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    bg_link = get_bg_link()
    current_theme = get_current_theme_name()
    last_theme = None
    if os.path.exists(LAST_THEME_CACHE):
        try:
            with open(LAST_THEME_CACHE, "r", encoding="utf-8") as f:
                last_theme = f.read().strip()
        except Exception:
            pass

    theme_changed = bool(current_theme and last_theme and current_theme != last_theme)
    
    # 1. Проверяем текущую ссылку
    if os.path.lexists(bg_link):
        resolved = os.path.realpath(bg_link)
        # Если ссылка указывает НЕ на наши сгенерированные обои, значит, юзер/система сменили обои
        if not is_generated(resolved) and os.path.exists(resolved):
            # Сохраняем как новые исходные обои
            with open(SOURCE_WP_CACHE, "w", encoding="utf-8") as f:
                f.write(resolved)
            if current_theme:
                with open(LAST_THEME_CACHE, "w", encoding="utf-8") as f:
                    f.write(current_theme)
            return resolved

    # 2. Если ссылка указывает на сгенерированные обои или пока недоступна, читаем кэш (если тема не менялась)
    if not theme_changed and os.path.exists(SOURCE_WP_CACHE):
        try:
            with open(SOURCE_WP_CACHE, "r", encoding="utf-8") as f:
                cached = f.read().strip()
                if os.path.exists(cached) and not is_generated(cached):
                    return cached
        except Exception:
            pass

    # 3. Дефолтные пути и поиск обоев темы (Quattro и legacy)
    candidates = [
        os.path.join(HOME, ".local/state/omarchy/current/theme/backgrounds"),
        os.path.join(HOME, f".config/omarchy/backgrounds/{current_theme}") if current_theme else "",
        f"/usr/share/omarchy/themes/{current_theme}/backgrounds" if current_theme else "",
        os.path.join(HOME, ".config/omarchy/current/theme/backgrounds"),
        "/usr/share/omarchy/themes",
    ]
    for cdir in candidates:
        if cdir and os.path.isdir(cdir):
            for root, _, files in os.walk(cdir):
                img_files = sorted([os.path.join(root, f) for f in files if f.lower().endswith((".jpg", ".png", ".jpeg", ".webp"))])
                if img_files:
                    picked = img_files[0]
                    with open(SOURCE_WP_CACHE, "w", encoding="utf-8") as f:
                        f.write(picked)
                    if current_theme:
                        with open(LAST_THEME_CACHE, "w", encoding="utf-8") as f:
                            f.write(current_theme)
                    return picked

    return None

def get_keybindings():
    """Получает список всех горячих клавиш системы с фильтрацией и переводом"""
    bindings = []
    try:
        omarchy_bin = (
            shutil.which("omarchy")
            or os.path.join(HOME, ".local/share/omarchy/bin/omarchy")
            or "/usr/share/omarchy/bin/omarchy"
            or "/usr/bin/omarchy"
        )
        cmd_out = subprocess.check_output([omarchy_bin, "menu", "keybindings", "--print"]).decode("utf-8")
        for line in cmd_out.splitlines():
            if "→" in line:
                parts = line.split("→")
                shortcut = parts[0].strip()
                action = parts[1].strip()
                
                # Очистка HTML-сущностей
                action = action.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'")
                
                # Переводим с помощью локали (сохраняя оригинальное имя для фильтрации)
                original_action = action
                action = TRANSLATIONS.get(action, action)
                    
                bindings.append((shortcut, action, original_action))
    except Exception as e:
        print(f"Error reading keybindings: {e}", file=sys.stderr)
        
    # Фильтрация и ограничение
    seen_shortcuts = set()
    filtered = []
    
    workspace_switches = []
    workspace_moves = []
    workspace_silent_moves = []
    group_switches = []
    
    for shortcut, action, original_action in bindings:
        if "XF86" in shortcut or "switch:" in shortcut:
            continue
        if shortcut in seen_shortcuts:
            continue
            
        original_action_lower = original_action.lower()
        
        # Фильтруем запуск отдельных сторонних программ (Obsidian, Signal, Email, Spotify, и т.д.)
        is_allowed = True
        for app in ["signal", "obsidian", "typora", "docker", "music", "spotify", "editor", "passwords", 
                    "chatgpt", "grok", "whatsapp", "google messages", "google photos", "youtube", "email", 
                    "calendar", "file manager", "nautilus", "1password", "cliamp", "lazydocker", "signal-desktop"]:
            if app in original_action_lower:
                is_allowed = False
                break
                
        # Но явно разрешаем Терминал и Браузер
        if "terminal" in original_action_lower or "tmux" in original_action_lower or "browser" in original_action_lower:
            is_allowed = True
            
        if not is_allowed:
            continue
            
        seen_shortcuts.add(shortcut)
        
        # Группируем числовые бинды для компактности
        if shortcut.startswith("SUPER + ") and shortcut[8:].isdigit():
            workspace_switches.append(int(shortcut[8:]))
        elif shortcut.startswith("SUPER SHIFT + ") and shortcut[14:].isdigit():
            workspace_moves.append(int(shortcut[14:]))
        elif shortcut.startswith("SUPER SHIFT ALT + ") and shortcut[18:].isdigit():
            workspace_silent_moves.append(int(shortcut[18:]))
        elif shortcut.startswith("SUPER ALT + ") and shortcut[12:].isdigit():
            group_switches.append(int(shortcut[12:]))
        else:
            filtered.append((shortcut, action))
            
    # Добавляем объединенные числовые бинды в начало
    if workspace_switches:
        filtered.insert(0, ("SUPER + 1..9", f"{TRANSLATIONS['go_to_workspace']}{max(workspace_switches)}"))
    if workspace_moves:
        filtered.insert(1, ("SUPER SHIFT + 1..9", f"{TRANSLATIONS['move_window_to_workspace']}{max(workspace_moves)}"))
    if workspace_silent_moves:
        filtered.insert(2, ("SUPER SHIFT ALT + 1..9", f"{TRANSLATIONS['move_window_silently_to_workspace']}{max(workspace_silent_moves)}"))
    if group_switches:
        filtered.insert(3, ("SUPER ALT + 1..5", f"{TRANSLATIONS['go_to_window_group']}{max(group_switches)}"))
        
    # Ограничиваем общим количеством 50 биндов
    return filtered[:50]

def generate_wallpaper():
    """Генерирует новые обои с наложением биндов"""
    print("Generating wallpaper...")
    ensure_wayland_env()
    width, height = get_screen_resolution()
    bg_path = get_source_wallpaper()
    
    if not bg_path:
        print("Error: Source wallpaper not found.", file=sys.stderr)
        return False
        
    bindings = get_keybindings()
    if not bindings:
        print("Error: No keybindings found.", file=sys.stderr)
        return False
        
    # We expect at least a few standard bindings. If we only got static ones, it means hyprctl/system discovery failed.
    has_super = any(b[0].startswith("SUPER") for b in bindings)
    if len(bindings) < 5 or not has_super:
        print("Error: Could not retrieve system keybindings (only got static or too few). Retrying later...", file=sys.stderr)
        return False
        
    # Открываем фоновую картинку
    try:
        img = Image.open(bg_path)
    except Exception as e:
        print(f"Failed to open source image {bg_path}: {e}", file=sys.stderr)
        return False
        
    # Кадрируем под пропорции экрана
    img_ratio = img.width / img.height
    screen_ratio = width / height
    if img_ratio > screen_ratio:
        new_width = int(img.height * screen_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / screen_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))
        
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Создаем оверлей
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Загружаем шрифт (крупнее: 14px для текста, 24px для заголовка)
    try:
        title_font = ImageFont.truetype(FONT_PATH, 24)
        text_font = ImageFont.truetype(FONT_PATH, 14)
        text_bold = ImageFont.truetype(FONT_PATH, 14)
    except IOError:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        text_bold = ImageFont.load_default()
        
    # Рассчитываем сетку колонок
    # Максимум 25 строк на колонку
    max_rows = 25
    N = len(bindings)
    num_columns = min(4, math.ceil(N / max_rows))
    rows_per_col = math.ceil(N / num_columns)
    
    col_width = 500
    gap = 40
    card_width = num_columns * col_width + (num_columns - 1) * gap + 60
    
    # Высота строки 26px, отступы сверху/снизу 110px
    row_height = 26
    card_height = rows_per_col * row_height + 110
    
    card_x1 = (width - card_width) // 2
    card_y1 = (height - card_height) // 2  # Центрируем по вертикали
    card_x2 = card_x1 + card_width
    card_y2 = card_y1 + card_height
    
    # Рисуем подложку карточки
    draw.rounded_rectangle(
        [card_x1, card_y1, card_x2, card_y2],
        radius=15,
        fill=(15, 17, 26, 170),      # Catppuccin Mocha с прозрачностью
        outline=(255, 255, 255, 30), # Тонкая граница
        width=1
    )
    
    # Рисуем заголовок
    header_text = f"   {TRANSLATIONS['header_text']}"
    draw.text((card_x1 + 30, card_y1 + 25), header_text, font=title_font, fill=(137, 220, 235, 255))
    
    # Разделитель
    draw.line(
        [(card_x1 + 30, card_y1 + 75), (card_x2 - 30, card_y1 + 75)],
        fill=(255, 255, 255, 30),
        width=1
    )
    
    # Распределяем бинды по колонкам и рисуем их
    columns = [bindings[i:i + rows_per_col] for i in range(0, N, rows_per_col)]
    
    for col_idx, col_data in enumerate(columns):
        if col_idx >= num_columns:
            break
        col_x = card_x1 + 30 + col_idx * (col_width + gap)
        y_offset = card_y1 + 95
        
        for shortcut, action in col_data:
            # Ограничиваем длину бинда, чтобы не вылезал за границы колонки
            shortcut_disp = shortcut[:22]
            action_disp = action[:28] + "..." if len(action) > 30 else action
            
            # Сочетание клавиш
            draw.text((col_x, y_offset), shortcut_disp, font=text_bold, fill=(137, 180, 250, 255))
            
            # Стрелочка
            draw.text((col_x + 195, y_offset), "→", font=text_font, fill=(166, 173, 200, 120))
            
            # Действие
            draw.text((col_x + 225, y_offset), action_disp, font=text_font, fill=(205, 214, 244, 255))
            
            y_offset += row_height
            
    # Объединяем и сохраняем
    final_img = Image.alpha_composite(img.convert("RGBA"), overlay)
    
    os.makedirs(GENERATED_DIR, exist_ok=True)
    # Генерируем уникальное имя файла с миллисекундной меткой времени,
    # чтобы обойти кэширование изображений по URL в QtQuick / omarchy-shell
    timestamp = int(time.time() * 1000)
    output_path = os.path.join(GENERATED_DIR, f"{GENERATED_PREFIX}_{timestamp}.png")
    tmp_path = output_path + ".tmp"
    final_img.convert("RGB").save(tmp_path, "PNG")
    os.replace(tmp_path, output_path)
    
    # Устанавливаем новые обои в системе
    bg_link = get_bg_link()
    os.makedirs(os.path.dirname(bg_link), exist_ok=True)
    os.environ["CURRENT_BACKGROUND_LINK"] = bg_link
    subprocess.run(["ln", "-nsf", output_path, bg_link])
    
    # В Omarchy Quattro обои устанавливаются через omarchy-shell
    if shutil.which("omarchy-shell"):
        res = subprocess.run(["omarchy-shell", "-q", "background", "set", output_path])
        if res.returncode != 0:
            print(f"omarchy-shell background set failed with code {res.returncode}", file=sys.stderr, flush=True)
        
    # Запускаем swaybg через uwsm-app в фоне (для совместимости со старыми версиями)
    if shutil.which("swaybg"):
        subprocess.run(["pkill", "-x", "swaybg"])
        try:
            subprocess.Popen(
                ["uwsm-app", "--", "swaybg", "-i", bg_link, "-m", "fill"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        except Exception as e:
            print(f"Error starting swaybg: {e}", file=sys.stderr, flush=True)
            
    # Удаляем старые версии сгенерированных обоев (оставляем текущий и 1 предыдущий на время перехода)
    cleanup_old_wallpapers(output_path, keep=2)
    
    print(f"Wallpaper updated successfully! Source: {bg_path}", flush=True)
    return True

def daemon_mode():
    """Запускает непрерывный мониторинг файлов"""
    print("Starting Omarchy Keybindings Wallpaper Daemon...", flush=True)
    
    # Первоначальная генерация при старте
    wallpaper_generated = generate_wallpaper()
    
    last_mtimes = get_mtimes()
    last_theme = get_current_theme_name()
    
    while True:
        try:
            time.sleep(3)
            
            # Если обои еще не были успешно сгенерированы (например, ждали запуска Hyprland), пробуем снова
            if not wallpaper_generated:
                wallpaper_generated = generate_wallpaper()
                if wallpaper_generated:
                    last_mtimes = get_mtimes()
                    last_theme = get_current_theme_name()
                continue
            
            # 1. Проверяем смену темы Omarchy
            current_theme = get_current_theme_name()
            if current_theme and current_theme != last_theme:
                print(f"Theme change detected: {last_theme} -> {current_theme}", flush=True)
                last_theme = current_theme
                wallpaper_generated = generate_wallpaper()
                last_mtimes = get_mtimes()
                continue

            # 2. Проверяем, сменил ли пользователь/система фоновую картинку
            bg_link = get_bg_link()
            if os.path.lexists(bg_link):
                resolved = os.path.realpath(bg_link)
                if not is_generated(resolved) and os.path.exists(resolved):
                    print(f"Wallpaper change detected to: {resolved}", flush=True)
                    # Сохраняем новый исходник
                    with open(SOURCE_WP_CACHE, "w", encoding="utf-8") as f:
                        f.write(resolved)
                    if current_theme:
                        with open(LAST_THEME_CACHE, "w", encoding="utf-8") as f:
                            f.write(current_theme)
                    wallpaper_generated = generate_wallpaper()
                    last_mtimes = get_mtimes()
                    continue
                    
            # 3. Проверяем изменения в файлах конфигурации
            current_mtimes = get_mtimes()
            if current_mtimes != last_mtimes:
                print("Config change detected in watched files", flush=True)
                wallpaper_generated = generate_wallpaper()
                last_mtimes = current_mtimes
                
        except KeyboardInterrupt:
            print("Daemon stopped.", flush=True)
            break
        except Exception as e:
            print(f"Daemon error: {e}", file=sys.stderr, flush=True)
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Omarchy Keybindings Wallpaper Generator")
    parser.add_argument("--daemon", action="store_true", help="Run in background daemon mode")
    parser.add_argument("--generate", action="store_true", help="Generate wallpaper once and exit")
    
    args = parser.parse_args()
    
    if args.daemon:
        daemon_mode()
    elif args.generate:
        generate_wallpaper()
    else:
        # По умолчанию генерируем один раз
        generate_wallpaper()
