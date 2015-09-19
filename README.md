![Chi](https://raw.githubusercontent.com/wiki/mdevaev/emonoda/chi.png) Emonoda -- 得物だ
=======

[![PyPI Version](https://img.shields.io/pypi/v/emonoda.svg)](https://pypi.python.org/pypi/emonoda/)
[![Python Versions](https://img.shields.io/pypi/pyversions/emonoda.svg)](https://pypi.python.org/pypi/emonoda/)
[![PyPI License](https://img.shields.io/pypi/l/emonoda.svg)](https://pypi.python.org/pypi/emonoda/)
[![Build Status](https://img.shields.io/travis/mdevaev/emonoda.svg)](https://travis-ci.org/mdevaev/emonoda)

**Emonoda** (moon. _得物だ_, рус. _это добыча_) -- это набор программ для организации и управления коллекцией торрентов. Он поможет вам следить за актуальностью раздач и автоматически обновлять торрент-файлы, а так же вычищать старые данные, просматривать мета-информацию и делать множество других вещей.  
За детальной информацией обращайтесь на вики: https://github.com/mdevaev/emonoda/wiki  

***

### Из коробки ###
* **`emfetch`** -- Следит за раздачами, используя плагины для популярных трекеров; обновляет торрент-файлы при добавлении новых серий или перезаливке; интегрируется с основными линуксовыми клиентами.
* **`emfile`** -- Позволяет читать метаданные торрент-файлов и выдает их в человекочитаемом, либо удобном для скриптов формате.
* **`emdiff`** -- Показывает разницу содержимого двух торрент-файлов в виде диффа.
* **`emfind`** -- Служит для выполнения различных поисковых запросов, например - найти в каталоге с данными файлы, не принадлежащими ни одному торренту, зарегистрированному в клиенте.
* **`emload`** -- Загружает торрент, используя модель "t.data" для хранения данных (см. документацию).
* **`emrm`** -- Удаляет торрент из клиента.

***

### Основные фичи ###
* **UNIX-way** -- система представлена в виде простых консольных программ с текстовыми конфигами. Не нужно разворачивать оракл, апач и кластер эллиптикса - просто поставьте **emonoda** и укажите в ее конфиге несколько несложных параметров.
* **Python** -- можно легко добавить поддержку других трекеров, используя готовый набор классов и функций.
* **Интегрируемость** -- программы стараются по-максимуму использовать все возможности торрент-клиентов. Например, **emfile** способна найти каталог, куда вы загружали указанный торрент, а **emfetch**, при обновлении торрент-файла, может сохранить его метку, назначенную в [ruTorrent](https://github.com/Novik/ruTorrent).
* **Прокси для каждого трекера** -- можно индивидуально настроить использование HTTP/Socks4/Socks5-прокси, если в вашей сети недоступен любимый ресурс.
* **Фингерпринты** -- перед тем, как логиниться на трекер, программа проверит содержимое сайта и сообщит вам, если вместо него вдруг показывается провайдерская заглушка.

***

### Поддерживаемые трекеры ###
* http://rutracker.org
* http://nnm-club.me
* http://rutor.org
* http://tfile.me
* http://pravtor.ru
* http://tr.anidub.com
* http://tabun.everypony.ru
* http://pornolab.net

***

### Поддерживаемые клиенты ###
* [RTorrent](http://rakshasa.github.io/rtorrent/)
* [KTorrent](http://ktorrent.pwsp.net/)
* [Transmission](http://www.transmissionbt.com/)

***

### Установка ###
##### Локальная установка из PyPI ####
Вы можете поставить **emonoda** в свой домашний каталог из [PyPI](https://pypi.python.org/pypi/emonoda), при этом программы будут доступны в `~/.local/bin`, например - `~/.local/bin/emfetch`. Для установки введите:
```
pip install --user --upgrade emonoda
```
##### Пакет для Arch Linux ####
Актуальный PKGBUILD находится в [AUR`е](https://aur4.archlinux.org/packages/emonoda/):
```
packer -S emonoda
```

***

### Скриншотик ###
![emfetch](https://raw.githubusercontent.com/wiki/mdevaev/emonoda/emfetch.png)
