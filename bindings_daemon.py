import subprocess
import os
import sys
import json
import time
import math
import argparse
from PIL import Image, ImageDraw, ImageFont

def ensure_wayland_env():
    uid = os.getuid()
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
        wayland_files = [f for f in os.listdir(run_user) if f.startswith("wayland-")]
        if wayland_files:
            wayland_files.sort(key=lambda x: os.path.getmtime(os.path.join(run_user, x)), reverse=True)
            os.environ["WAYLAND_DISPLAY"] = wayland_files[0]

ensure_wayland_env()

HOME = os.path.expanduser("~")

# Пути к отслеживаемым файлам
WATCH_FILES = [
    os.path.join(HOME, ".config/hypr/bindings.conf"),
    os.path.join(HOME, ".config/hypr/input.conf"),
    os.path.join(HOME, ".config/hypr/looknfeel.conf"),
    os.path.join(HOME, ".config/hypr/hyprland.conf"),
]

BG_LINK = os.path.join(HOME, ".config/omarchy/current/background")
GENERATED_WALLPAPER = os.path.join(HOME, "Pictures/wallpaper_with_bindings.png")
CACHE_DIR = os.path.join(HOME, ".cache/omarchy")
SOURCE_WP_CACHE = os.path.join(CACHE_DIR, "last_source_wallpaper.txt")
FONT_PATH = "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf"

def get_locale_lang():
    lang = os.environ.get("LANG", "") or os.environ.get("LC_MESSAGES", "")
    if not lang:
        try:
            import locale
            lang = locale.getlocale(locale.LC_MESSAGES)[0]
        except Exception:
            lang = None
    if not lang:
        lang = "en"
    lang = lang.split(".")[0].split("_")[0].lower()
    return lang

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
    for f in WATCH_FILES:
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
    
    # 1. Проверяем текущую ссылку
    if os.path.exists(BG_LINK):
        resolved = os.path.realpath(BG_LINK)
        # Если ссылка указывает НЕ на наши сгенерированные обои, значит, юзер сменил обои
        if resolved != GENERATED_WALLPAPER:
            # Сохраняем как новые исходные обои
            with open(SOURCE_WP_CACHE, "w") as f:
                f.write(resolved)
            return resolved

    # 2. Если ссылка указывает на сгенерированные обои, читаем кэш
    if os.path.exists(SOURCE_WP_CACHE):
        with open(SOURCE_WP_CACHE, "r") as f:
            cached = f.read().strip()
            if os.path.exists(cached):
                return cached

    # 3. Дефолтный путь
    default_bg = os.path.join(HOME, ".config/omarchy/current/theme/backgrounds/1-synth-scape.jpg")
    if os.path.exists(default_bg):
        return default_bg
    return None

def get_keybindings():
    """Получает список всех горячих клавиш системы с фильтрацией и переводом"""
    bindings = []
    try:
        omarchy_bin = os.path.join(HOME, ".local/share/omarchy/bin/omarchy")
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
    
    output_dir = os.path.dirname(GENERATED_WALLPAPER)
    os.makedirs(output_dir, exist_ok=True)
    final_img.convert("RGB").save(GENERATED_WALLPAPER, "PNG")
    
    # Устанавливаем новые обои в системе
    os.environ["CURRENT_BACKGROUND_LINK"] = BG_LINK
    subprocess.run(["ln", "-nsf", GENERATED_WALLPAPER, BG_LINK])
    subprocess.run(["pkill", "-x", "swaybg"])
    
    # Запускаем swaybg через uwsm-app в фоне
    try:
        subprocess.Popen(
            ["uwsm-app", "--", "swaybg", "-i", BG_LINK, "-m", "fill"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        print(f"Error starting swaybg: {e}", file=sys.stderr)
        
    print(f"Wallpaper updated successfully! Source: {bg_path}")
    return True

def daemon_mode():
    """Запускает непрерывный мониторинг файлов"""
    print("Starting Omarchy Keybindings Wallpaper Daemon...")
    
    # Первоначальная генерация при старте
    wallpaper_generated = generate_wallpaper()
    
    last_mtimes = get_mtimes()
    
    while True:
        try:
            time.sleep(3)
            
            # Если обои еще не были успешно сгенерированы (например, ждали запуска Hyprland), пробуем снова
            if not wallpaper_generated:
                wallpaper_generated = generate_wallpaper()
                if wallpaper_generated:
                    last_mtimes = get_mtimes()
                continue
            
            # 1. Проверяем, сменил ли пользователь фоновую картинку
            if os.path.exists(BG_LINK):
                resolved = os.path.realpath(BG_LINK)
                if resolved != GENERATED_WALLPAPER:
                    print(f"Wallpaper change detected to: {resolved}")
                    # Сохраняем новый исходник
                    with open(SOURCE_WP_CACHE, "w") as f:
                        f.write(resolved)
                    wallpaper_generated = generate_wallpaper()
                    last_mtimes = get_mtimes()
                    continue
                    
            # 2. Проверяем изменения в файлах конфигурации
            config_changed = False
            current_mtimes = get_mtimes()
            for f in WATCH_FILES:
                if os.path.exists(f):
                    mtime = current_mtimes.get(f)
                    if mtime != last_mtimes.get(f):
                        print(f"Config change detected in: {f}")
                        config_changed = True
                        
            if config_changed:
                wallpaper_generated = generate_wallpaper()
                last_mtimes = current_mtimes
                
        except KeyboardInterrupt:
            print("Daemon stopped.")
            break
        except Exception as e:
            print(f"Daemon error: {e}", file=sys.stderr)
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
