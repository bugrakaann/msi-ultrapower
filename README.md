# pil-modu — MSI GF65 / KDE güç modları

Tek tıkla performans, dengeli ya da batarya moduna geçer. Güç profilini,
ekran Hz'ini ve parlaklığını, MSI EC (fan, shift mode), CPU turbo, klavye
ışığı ve NVIDIA GPU'yu birlikte ayarlar. Bir şey ters giderse hepsini geri alır.

| Mod | Güç profili / turbo | EC / fan | Dahili ekran | NVIDIA |
|---|---|---|---|---|
| `performans` | performance / açık | turbo / Cooler Boost | 120 Hz · %100 | hep uyanık |
| `performans-manuel` | performance / açık | turbo / `advanced` (MControlCenter eğrisi) | 120 Hz · %100 | hep uyanık |
| `dengeli` | balanced / açık | comfort / otomatik | 120 Hz · %60 | boşta uyur |
| `batarya` | power-saver / kapalı | eco / otomatik | 120 Hz · %30 | yeniden başlatınca kapalı |
| `batarya-48` | power-saver / kapalı | eco / otomatik | 48 Hz · %30 | yeniden başlatınca kapalı |

Batarya modlarında klavye ışığı ve harici ekran (NVIDIA'ya bağlı HDMI) kapanır.

## Kullanım

Uygulama menüsünde **Güç Modları**. Bir karta tıkla, ayrıntılara bak, **Uygula**'ya bas.

Komut satırından:

```
pil-modu dengeli                 # modu uygula
pil-modu dengeli --harici koru   # harici ekranı açık tut (otomatik | koru | kapat)
pil-modu batarya --dene          # hiçbir şeyi değiştirmeden planı göster
pil-modu durum                   # gerçek değerleri göster
pil-modu geri                    # ilk moddan önceki ayarlara dön
```

## Kurulum

```
cd ~/Projeler/pil-modu
make install     # ~/.local/bin/pil-modu, pil-modu-ui ve menü girdisini oluşturur
make test        # testleri çalıştırır
make run         # arayüzü kurmadan buradan çalıştırır
```

Bağımlılıklar (pacman): `python`, `pyside6`, `power-profiles-daemon`, `kscreen`
(`kscreen-doctor`), `polkit` (`pkexec`), `msi-ec` çekirdek modülü.

Başlatıcılar yalnızca bu klasördeki `src/`'yi gösterir. Kodu düzenlediğinde
yeniden kurman gerekmez.

## Proje yapısı

```
pil-modu/
├── src/pil_modu/          ← asıl program (bir Python "paketi")
│   ├── presets.py         ← MODLAR BURADA. Bir modu değiştirmek için yalnızca burayı düzenle.
│   ├── cli.py             ← komut satırı: argümanlar, kilit, hata mesajı
│   ├── controller.py      ← bir mod geçişinin tamamı: planla → uygula → doğrula → kaydet / geri al
│   ├── plan.py            ← neyin değişeceğini hesaplar (hiçbir şeye dokunmaz)
│   ├── display.py         ← ekran planı ve doğrulaması (kscreen-doctor)
│   ├── system.py          ← dış komutlar: powerprofilesctl, kscreen-doctor
│   ├── elevated.py        ← root yardımcılarını pkexec ile çağırır
│   ├── status.py          ← pil, NVIDIA, EC durumunu okur (hiçbir şey yazmaz)
│   ├── state.py           ← ~/.local/share/pil-modu içindeki JSON ve günlük dosyaları
│   ├── paths.py           ← tüm dosya yolları
│   ├── privileged/        ← ROOT olarak çalışan kod; yalnızca standart kütüphane
│   │   ├── hardware.py    ← sysfs'e yazar, açılışta geri yükler (systemd)
│   │   └── gpu_boot.py    ← NVIDIA'yı sonraki açılış için kapatır/açar (mkinitcpio)
│   └── ui/                ← grafik arayüz (PySide6)
│       ├── app.py         ← giriş noktası
│       ├── window.py      ← ana pencere
│       ├── widgets.py     ← mod kartı, bilgi şeridi, stil
│       └── runner.py      ← CLI'yi arka planda çalıştırır
├── tests/                 ← birim testleri (make test)
├── data/                  ← .desktop menü girdisi şablonu
├── scripts/               ← install.sh / uninstall.sh
├── Makefile               ← kısa komutlar: make install, make test
└── pyproject.toml         ← paketin kimlik kartı (ad, sürüm, bağımlılıklar)
```

Katmanlar tek yönde birbirini kullanır:

```
ui ──(alt süreç)──▶ cli ──▶ controller ──▶ plan / display   (saf hesaplama)
                                      ├──▶ system            (KDE komutları)
                                      ├──▶ elevated ──pkexec──▶ privileged/*   (root)
                                      └──▶ state             (dosyalar)
```

* **Arayüz donanıma dokunmaz.** CLI'yi çalıştırıp çıktısını gösterir. Böylece
  terminal ve arayüz her zaman aynı şekilde davranır.
* **`plan.py` ve `display.py` saf fonksiyonlardır.** Veri alıp veri döndürürler,
  bu yüzden gerçek ekran olmadan test edilebilirler.
* **Root kodu küçük ve bağımsızdır.** `privileged/` paketin geri kalanını import
  etmez. Yalnızca izin listesindeki (`ALLOWED`) dosyalara yazar.

## Nereye ne kaydedilir

| Yol | Sahibi | Ne |
|---|---|---|
| `~/.local/share/pil-modu/original-v2.json` | sen | İlk moddan önceki ayarlar (`geri` bunu kullanır) |
| `~/.local/share/pil-modu/active.json` | sen | Son seçilen mod |
| `~/.local/share/pil-modu/history.log` | sen | Geçiş günlüğü |
| `/var/lib/pil-modu/hardware.json` | root | Açılışta geri yüklenecek donanım değerleri |
| `/usr/local/lib/pil-modu/hardware.py` | root | `hardware.py`'nin açılış servisi için kopyası |
| `/etc/systemd/system/pil-modu-restore.service` | root | Açılışta bir kez çalışır |
| `/etc/modprobe.d/90-pil-modu-nvidia.conf`, `/etc/udev/rules.d/50-pil-modu-nvidia.rules`, `/etc/mkinitcpio.conf.d/99-pil-modu-gpu.conf` | root | Yalnızca batarya modunda: NVIDIA'yı açılışta devre dışı bırakır |

## Güvenlik ve geri alma

* Yönetici parolası, donanımı yazan kısa süreli `pkexec` işlemi için istenir.
  Parolasız sudo kuralı ya da sürekli çalışan root servisi yoktur.
* Donanım yardımcısı ayarları uygular, sonra `COMMIT` bekler. KDE tarafı
  (profil, ekran) doğrulanamazsa her şey eski haline döner.
* GPU yapılandırması başarısız olursa dosyalar geri alınır ve açılış imajları
  yeniden oluşturulur.
* Elektrik kesintisinde tam atomiklik garanti edilemez; `pil-modu geri` kullan.

**Kurtarma:** Grafik arayüz açılmazsa TTY'de (Ctrl+Alt+F3):

```
sudo /usr/bin/python3 /home/bugra/Projeler/pil-modu/src/pil_modu/privileged/gpu_boot.py hybrid
```

Başarıyla bitince yeniden başlat. Bu yalnızca bu aracın koyduğu NVIDIA engelini kaldırır.

## Notlar

* Modlar elle seçilir. Adaptör takılınca otomatik mod değişmez.
* KDE güç yönetimi ya da MControlCenter sonradan ayarları değiştirebilir;
  `pil-modu durum` gerçek değerleri gösterir.
* EC'nin `unspecified` değeri geri yazılamadığı için yerine `comfort` kullanılır.
* Panelin 59,96 Hz modu sürücü tarafından reddedildiği için batarya modu 120 Hz'de kalır;
  `batarya-48` ise 48 Hz kullanır.
