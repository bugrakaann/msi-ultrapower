# pil-modu — KDE Plasma'da MSI dizüstüleri için güç modları

[English](README.md) · **Türkçe**

Tek tıkla MSI dizüstünü performans, dengeli ya da batarya moduna geçirir. Her mod güç
profilini, ekranın yenileme hızını ve parlaklığını, MSI EC'yi (fan, shift mode, Cooler Boost),
CPU turbo'yu, klavye ışığını, aygıt güç tasarrufunu ve NVIDIA ekran kartını birlikte ayarlar.
Bir adım başarısız olursa hepsini geri alır.

![Güç Modları penceresi](docs/screenshot.png)

- **Uygulamadan önce gör.** Pencere *senin* bilgisayarında tam olarak hangi ayarların
  değişeceğini listeler ("11 ayar değişecek: parlaklık %100 → %30 …"). Bir modun üzerine
  gelince yaptığı her şey görünür.
- **Pil bakımı.** %60 / %80 / %100 şarj sınırı; açılışta geri yüklenir.
- **TLP gibi batarya modu, fazlasıyla.** PCI güç yönetimi, ses kartı ve disk tasarrufu; NVIDIA
  sonraki açılışta tamamen kapanır.
- **Otomatik mod.** Şarj aleti takılınca/çekilince mod değiştirir.
- **Sistem tepsisi.** Pencereyi açmadan mod ve şarj sınırı değiştir.
- **Canlı durum.** Pil, pildeyken anlık ve ortalama güç tüketimi, CPU/GPU sıcaklığı ve fan hızı, NVIDIA durumu (tepsi ipucunda da).
- **Diller.** English, Türkçe, Русский, Español, العربية (sağdan sola).

## Modlar

| Mod (komut) | Güç profili / turbo | EC / fan | Dahili ekran | NVIDIA |
|---|---|---|---|---|
| `performans` | performance / açık | turbo / Cooler Boost | en yüksek Hz · %100 | hep uyanık |
| `performans-manuel` | performance / açık | turbo / `advanced` (MControlCenter eğrisi) | en yüksek Hz · %100 | hep uyanık |
| `dengeli` | balanced / açık | comfort / otomatik | en yüksek Hz · %60 | boşta uyur |
| `batarya` | power-saver / kapalı | eco / otomatik | en yüksek Hz · %30 | yeniden başlatınca kapalı |
| `batarya-48` | power-saver / kapalı | eco / otomatik | en düşük Hz (örn. 48) · %30 | yeniden başlatınca kapalı |

Batarya modları klavye ışığını da kapatır; PCI aygıtları, ses kartı ve disk uyuyabilir
(Ayarlar'dan kapatılabilir). İstersen Bluetooth da kapanır. Harici ekranların Hz'i ve
çözünürlüğü hiçbir modda değişmez. Batarya modlarında yalnızca NVIDIA'ya bağlı çıkışlar
zorunlu kapanır; diğerleri seçimine göre.

Diğer modlar ve **Önceki ayarlara dön** bunları ilk moddan önceki haline döndürür.

## Gereksinimler ve uyumluluk

- **Arch tabanlı dağıtım** (Arch, CachyOS, EndeavourOS, Manjaro), **KDE Plasma 6** ve
  `power-profiles-daemon`.
- Fan, EC modu, Cooler Boost ve şarj sınırı için **[msi-ec](https://github.com/BeardOverflow/msi-ec)**
  (AUR: `msi-ec-dkms-git`). msi-ec belirli EC firmware sürümlerini destekler; yoksa bu ayarlar
  atlanır, geri kalanı çalışır.

Program tek bir modele göre değil, bulunduğu makineye göre davranır:

| Alan | Nasıl uyum sağlar |
|---|---|
| EC | EC'nin bildirdiği shift ve fan modlarını kullanır; olmayan modun yerine en yakını seçilir. EC'de `advanced` fan modu yoksa manuel fan modu kapanır. |
| Ekran | Panelin en yüksek / en düşük Hz'i kullanılır (120, 144, 165, 240 Hz paneller olur). Tek Hz'li panelde düşük Hz modu kapanır. |
| NVIDIA | PCI adresine göre değil üreticiye göre bulunur. NVIDIA yoksa GPU adımı atlanır. |
| **MUX anahtarı** | BIOS'ta GPU modu *Discrete* ise ve dahili ekranı NVIDIA sürüyorsa NVIDIA'yı kapatmak **reddedilir** (ekran kararırdı). BIOS'ta *MSHybrid/Optimus* seç. |
| CPU turbo | Intel (`intel_pstate/no_turbo`) ve AMD (`cpufreq/boost`). |
| Diğer | Pil, klavye ışığı ve Bluetooth adlarıyla aranır; olmayan atlanır. Çalışan TLP, auto-cpufreq ya da tuned çakışma olarak bildirilir. |

Bilgisayarında neyin çalıştığını görmek için `pil-modu doctor` çalıştır. GF65 Thin 9SEXR
üzerinde geliştirildi; başka modellerden gelen raporlar çok değerli
(bkz. [Modelini bildir](#modelini-bildir)).

## Kurulum

```
git clone https://github.com/bugrakaann/pil-modu.git
cd pil-modu
make install      # paketi derler ve pacman ile kurar (güncellemek için de aynı komut)
make uninstall    # kaldırır (sudo pacman -R pil-modu)
```

Kaldırmadan önce ekran ve donanım ayarlarını eski haline getirmek için `pil-modu geri`
çalıştır. Kişisel veriler `~/.local/share/pil-modu` ve `~/.config/pil-modu` içinde kalır.

## Kullanım

Uygulama menüsünde **Güç Modları**: modu seç, neyin değişeceğine bak, **Uygula**'ya bas.
⚙ düğmesi Ayarlar'ı açar (dil, batarya modu seçenekleri, otomatik mod, tepsi).

Komut satırı (İngilizce komut adları da çalışır):

```
pil-modu dengeli                 # modu uygula
pil-modu dengeli --harici koru   # harici ekranı açık tut (otomatik | koru | kapat)
pil-modu batarya --dene          # hiçbir şeyi değiştirmeden planı göster
pil-modu durum                   # gerçek değerleri göster
pil-modu geri                    # ilk moddan önceki ayarlara dön
pil-modu sarj 80                 # pil en fazla %80'e kadar dolsun (60 | 80 | 100)
pil-modu doctor                  # uyumluluk raporu
pil-modu-ui --tray               # sistem tepsisinde başlat
```

### Otomatik mod

Ayarlar'da *prizde* ve *pilde* için birer mod seç. Uygulama açık olduğu sürece (tepside olması
yeterli; *Oturum açınca sistem tepsisinde başlat*'ı aç) şarj aleti takılınca/çekilince mod
değişir. Otomatik geçişler NVIDIA açılış ayarına dokunmaz; böylece her fiş çekişinde açılış
imajı yeniden oluşturulmaz. NVIDIA'yı tamamen kapatmak için batarya modunu elle uygula.

### Parola sormadan

Ayarlar'daki *Yönetici parolasını sorma*, yerel ve etkin oturumdaki yöneticilerin (`wheel`)
iki pil-modu yardımcısını parolasız çalıştırmasına izin veren bir polkit kuralı ekler: mod
değiştirme, şarj sınırı ve otomatik mod artık parola sormaz. Başka hiçbir şeye izin verilmez.
Seçeneği kapatınca ya da paketi kaldırınca kural silinir.

## Modelini bildir

Şu komutun çıktısıyla bir issue aç:

```
pil-modu doctor
```

Model, EC firmware'i, kullanılabilir EC/fan modları, panel Hz'leri, NVIDIA'ya bağlı çıkışlar ve
çakışan servisler listelenir.

## Çeviriler

Çeviriler `po/` klasöründe. Bir dil eklemek ya da düzeltmek için `po/<kod>.po` dosyasını
düzenle ya da oluştur (`po/pil-modu.pot`'tan başla), denemek için `make locale && make run`
çalıştır ve pull request aç. Mevcut çeviriler makine destekli; anadili konuşanların
düzeltmeleri memnuniyetle karşılanır.

## Güvenlik ve geri alma

- Root yalnızca `/usr/lib/pil-modu/` içindeki iki küçük yardımcıyla ve `pkexec` üzerinden
  kullanılır. Polkit eylemleri (`io.github.pilmodu.*`) parolayı birkaç dakika hatırlar.
  Sürekli çalışan root servisi ya da sudo kuralı yoktur.
- Donanım yardımcısı yalnızca izin listesindeki dosyalara (`privileged/hardware.py`'deki
  `ALLOWED`) ve izin verilen değerlerle yazar.
- Ayarları uygular ve `COMMIT` bekler. KDE tarafı (profil, ekranlar) doğrulanamazsa her şey
  geri alınır.
- GPU yapılandırması başarısız olursa dosyalar geri alınır ve açılış imajları yeniden oluşturulur.

**Kurtarma:** Grafik oturum açılmazsa TTY'ye geç (Ctrl+Alt+F3) ve çalıştır:

```
sudo /usr/lib/pil-modu/pil-modu-gpu-boot hybrid
```

Sonra yeniden başlat. Bu yalnızca bu aracın koyduğu NVIDIA engelini kaldırır.

## Nereye ne kurulur

| Yol | Ne |
|---|---|
| `/usr/bin/pil-modu`, `/usr/bin/pil-modu-ui` | Komutlar |
| `/usr/lib/pil-modu/` | Root yardımcıları (polkit eylemleri buraya bağlı) |
| `/usr/lib/python3.X/site-packages/pil_modu/` | Program kodu |
| `/usr/share/polkit-1/actions/io.github.pilmodu.policy` | Polkit eylemleri |
| `/usr/lib/systemd/system/pil-modu-restore.service` | Açılışta donanım ayarlarını ve şarj sınırını geri yükler |
| `/usr/share/locale/*/LC_MESSAGES/pil-modu.mo` | Çeviriler |
| `/var/lib/pil-modu/` | Açılışta geri yüklenecek donanım değerleri ve şarj sınırı |
| `/etc/modprobe.d/90-pil-modu-nvidia.conf`, `/etc/udev/rules.d/50-pil-modu-nvidia.rules`, `/etc/{mkinitcpio,dracut}.conf.d/99-pil-modu-gpu.conf` | Yalnızca batarya modlarında: NVIDIA'yı açılışta kapatır |
| `~/.config/pil-modu/settings.json` | Ayarların |
| `~/.local/share/pil-modu/` | İlk moddan önceki ayarlar, aktif mod, geçmiş |

## Geliştirme

```
make test     # birim testleri
make run      # arayüzü kurmadan src/ içinden çalıştır
make po       # metinleri po/pil-modu.pot'a çıkar, çevirileri güncelle
make locale   # make run için çevirileri derle
make clean    # derleme artıklarını sil
```

Proje yapısı ve katmanlar için İngilizce README'deki *Development* bölümüne bak. Arayüz
donanıma kendisi dokunmaz; CLI'yi çalıştırır, böylece terminal ve pencere hep aynı davranır.

## Sorumluluk reddi

pil-modu resmi olmayan bir projedir; Micro-Star International (MSI) ile bağlantısı yoktur ve
MSI tarafından onaylanmamıştır. Gömülü denetleyiciye (EC), çekirdek modülü ve açılış ayarlarına
yazar; kullanım sorumluluğu sana aittir. Hiçbir garanti verilmez (lisansın 15–16. maddeleri).

## Lisans

GPL-3.0-or-later. Bkz. [LICENSE](LICENSE).
