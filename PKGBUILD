# Maintainer: qirieshkaclwn <https://github.com/qirieshkaclwn>
pkgname=omarchy-bindings-wallpaper-git
pkgver=1.0.0.r6.ac31bb6
pkgrel=1
pkgdesc="A lightweight background daemon for Omarchy that renders system keybindings onto your wallpaper"
arch=('any')
url="https://github.com/qirieshkaclwn/omarchy-bindings-wallpaper"
license=('MIT')
depends=('python' 'python-pillow' 'swaybg')
makedepends=('git')
provides=('omarchy-bindings-wallpaper')
conflicts=('omarchy-bindings-wallpaper')
source=("${pkgname}::git+https://github.com/qirieshkaclwn/omarchy-bindings-wallpaper.git")
sha256sums=('SKIP')

pkgver() {
    cd "${srcdir}/${pkgname}"
    printf "1.0.0.r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
    cd "${srcdir}/${pkgname}"
    
    # Создаем пути для установки
    install -d "${pkgdir}/usr/share/omarchy/extensions/bindings-wallpaper/locales"
    
    # Копируем локализацию
    install -m644 locales/*.json "${pkgdir}/usr/share/omarchy/extensions/bindings-wallpaper/locales/"
    
    # Копируем исполняемый файл демона
    install -m755 bindings_daemon.py "${pkgdir}/usr/share/omarchy/extensions/bindings-wallpaper/bindings_daemon.py"
    
    # Модифицируем службу systemd для системного пути
    sed -i 's|%h/.config|/usr/share|g' omarchy-bindings-wallpaper.service
    
    # Устанавливаем службу в системную директорию systemd для пользователей
    install -Dm644 omarchy-bindings-wallpaper.service "${pkgdir}/usr/lib/systemd/user/omarchy-bindings-wallpaper.service"
    
    # Устанавливаем документацию и лицензию
    install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
    install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
    install -Dm644 README.ru.md "${pkgdir}/usr/share/doc/${pkgname}/README.ru.md"
}
