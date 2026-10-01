# msi-ultrapower

**KDE Plasma'da MSI dizüstüleri için güç modları.**

[English](README.md) · **Türkçe** · [Русский](README.ru.md) · [Español](README.es.md) · [العربية](README.ar.md)

MSI dizüstünü tek tıkla performans, dengeli ya da batarya moduna geçirir. Her mod güç profilini,
ekranın yenileme hızını ve parlaklığını, fanı ve EC modunu, CPU turbo'yu, klavye ışığını, aygıt
güç tasarrufunu ve NVIDIA ekran kartını birlikte ayarlar; bir adım başarısız olursa hepsini geri alır.

![Güç Modları penceresi](docs/screenshot.png)

## Kurulum

KDE Plasma 6 kullanan Arch, CachyOS, EndeavourOS ya da Manjaro'da:

```sh
curl -fsSL https://raw.githubusercontent.com/bugrakaann/msi-ultrapower/main/install.sh | bash
```

Güncellemek için aynı komutu yeniden çalıştır. Fan, EC modu, Cooler Boost ve şarj sınırı için
AUR'dan [msi-ec](https://github.com/BeardOverflow/msi-ec) sürücüsünü de kur (`msi-ec-dkms-git`) ve
yeniden başlat. O olmadan da geri kalan her şey çalışır.

<details>
<summary>Elle kurulum</summary>

```sh
git clone https://github.com/bugrakaann/msi-ultrapower.git
cd msi-ultrapower
make install
```

</details>

## Nasıl kullanılır

1. Uygulama menüsünden **Güç Modları**'nı aç.
2. Bir mod seç. Pencere, bilgisayarında tam olarak neyin değişeceğini listeler.
3. **Uygula**'ya bas ve parolanı gir.

Uygulamayı ilk kullanmadan önceki haline dönmek için **Önceki ayarlara dön**'e bas. Batarya
modları NVIDIA'yı yeniden başlatınca tamamen kapatır; yeniden başlatman gerektiğinde pencere söyler.

### Modlar

| Mod | Ne yapar |
|---|---|
| **Maksimum performans** | Performans profili, turbo, Cooler Boost, en yüksek Hz, %100 parlaklık |
| **Performans · Manuel fan** | Aynısı, kendi fan eğrinle (MControlCenter'da ayarla) |
| **Dengeli** | Dengeli profil, otomatik fan, %60 parlaklık, NVIDIA boştayken uyur |
| **Maksimum batarya** | Güç tasarrufu, turbo kapalı, %30 parlaklık, NVIDIA kapalı, aygıtlar uyur, klavye ışığı kapalı |
| **Maksimum batarya · Düşük Hz** | Aynısı, ayrıca ekranın en düşük yenileme hızı |

Harici ekranların çözünürlüğü ve Hz'i değişmez. NVIDIA'ya bağlı çıkışlar batarya modlarında
kapanır, çünkü NVIDIA kapalıdır.

### Ayarlar (⚙)

- **Şarj sınırı** – pili %60, %80 ya da %100'e kadar doldur. %60–80 pil ömrünü uzatır.
- **Otomatik mod** – şarj aleti takılınca ya da çekilince mod değiştir.
- **Yönetici parolasını sorma** – mod değiştirme, şarj sınırı ve otomatik mod parola sormaz.
- **Oturum açınca sistem tepsisinde başlat** – tepsiden mod değiştir; pil, güç tüketimi ve sıcaklıkları gör.
- **Batarya modu seçenekleri** – aygıtlar uyusun, Bluetooth kapansın.
- **Dil** – English, Türkçe, Русский, Español, العربية.

### Komut satırı

Türkçe ve İngilizce komut adları birlikte çalışır.

```sh
msi-ultrapower dengeli          # performans, performans-manuel, dengeli, batarya, batarya-48
msi-ultrapower batarya --dene   # neyin değişeceğini göster, hiçbir şeyi değiştirme
msi-ultrapower geri             # ilk moddan önceki ayarlara dön
msi-ultrapower sarj 80          # şarj sınırı: 60, 80 ya da 100
msi-ultrapower durum            # şu anki değerler
msi-ultrapower doctor           # bu bilgisayarda neler çalışıyor
```

## Uyumluluk

MSI GF65 Thin 9SEXR üzerinde geliştirildi. Program tek bir modele göre değil, bilgisayarının
desteklediğine göre çalışır: EC ve fan modları, ekran yenileme hızları (120–240 Hz), Intel ya da
AMD turbo ve NVIDIA olup olmadığı algılanır. Olmayan özellikler atlanır ve pencerede gösterilir.

- **MUX anahtarı:** BIOS'ta GPU modu *Discrete* ise ekranı NVIDIA sürer ve program onu kapatmaz.
  Batarya modlarını tam kullanmak için BIOS'ta *MSHybrid/Optimus* seç.
- **TLP, auto-cpufreq, tuned** güç profilleriyle çakışır; biri çalışıyorsa program uyarır.

Modelinde nasıl çalıştığını bildirmek için `msi-ultrapower doctor` çıktısıyla
[bir issue aç](https://github.com/bugrakaann/msi-ultrapower/issues/new?template=model-report.md).

## Kaldırma

```sh
msi-ultrapower geri           # isteğe bağlı: önceki ayarlarına dön
sudo pacman -R msi-ultrapower
```

Ayarların `~/.config/msi-ultrapower` ve `~/.local/share/msi-ultrapower` içinde kalır.

## Sorun giderme

**Batarya modundan sonra masaüstü açılmıyor.** Ctrl+Alt+F3 ile metin konsoluna geç, giriş yap ve
şunu çalıştır:

```sh
sudo /usr/lib/msi-ultrapower/msi-ultrapower-gpu-boot hybrid
```

Sonra yeniden başlat. Bu yalnızca msi-ultrapower'ın eklediği NVIDIA engelini kaldırır.

**Bir şey başarısız oldu.** Penceredeki **Günlüğü göster**'e bas ya da aynı modu terminalden
çalıştırıp tüm çıktıyı gör.

## Sorumluluk reddi

msi-ultrapower resmi olmayan bir projedir; Micro-Star International (MSI) ile bağlantısı yoktur ve
MSI tarafından onaylanmamıştır. Gömülü denetleyici (EC), çekirdek modülü ve açılış ayarlarını
değiştirir; kullanım sorumluluğu sana aittir. Hiçbir garanti verilmez.

## Lisans

[GPL-3.0-or-later](LICENSE)
