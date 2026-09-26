# MSI GF65 güç modları

| Mod | CPU profili / turbo | EC / fan | Ekran | Dahili parlaklık | NVIDIA |
|---|---|---|---|---|---|
| performans | performance / açık | turbo / Cooler Boost açık | 120 Hz | %100 | uyanık |
| performans-manuel | performance / açık | turbo / `advanced`, Cooler Boost kapalı | 120 Hz | %100 | uyanık |
| dengeli | balanced / açık | comfort / otomatik | 120 Hz | %60 | boşta otomatik uyku |
| batarya | power-saver / kapalı | eco / otomatik | 120 Hz | %30 | yeniden başlatınca devre dışı |

Maksimum bataryada klavye ışığı kapanır. Diğer modlarda başlangıç değeri geri gelir. Fanları durdurmaz; termal denetim firmware'de kalır. Performans modunda Cooler Boost yüksek fan sesi yaratır. Donanımın güç ve sıcaklık sınırları geçerlidir; overclock uygulanmaz.

Uygulama menüsünde Güç: Maksimum Performans / Dengeli / Maksimum Batarya seçenekleri bulunur.

```
~/.local/bin/pil-modu performans
~/.local/bin/pil-modu performans-manuel
~/.local/bin/pil-modu dengeli
~/.local/bin/pil-modu batarya
~/.local/bin/pil-modu dengeli --harici koru
~/.local/bin/pil-modu dengeli --harici kapat
~/.local/bin/pil-modu durum
~/.local/bin/pil-modu geri
```

`--dene` yalnızca planı gösterir. Maksimum batarya NVIDIA ve ona bağlı HDMI çıkışını devre dışı bırakır. `--harici koru` batarya modunda kabul edilmez; çift ekran için dengeli veya performans seçilir. GPU kapatma/açma geçişleri yeniden başlatma gerektirir. Script canlı ekran sürücüsünü sökmez ve bilgisayarı yeniden başlatmaz.

Batarya modunda `/etc/modprobe.d/90-pil-modu-nvidia.conf`, `/etc/udev/rules.d/50-pil-modu-nvidia.rules`, `/etc/mkinitcpio.conf.d/99-pil-modu-gpu.conf` oluşturulur ve `mkinitcpio -P` çalıştırılır. NVIDIA sürücülerinin yüklenmesi engellenir, bu bilgisayarın NVIDIA PCI işlevleri açılışta kaldırılır. Dengeli/performans/geri bu üç dosyayı kaldırıp imajları yeniler; sonraki açılışta NVIDIA yeniden kullanılabilir. Diğer sistem yapılandırmaları silinmez. GPU yapılandırması başarısız olursa dosyalar geri alınır ve eski imajlar yeniden oluşturulmaya çalışılır. CPU ve ekran profili ayrı aşamadır; hata mesajı bunu belirtir.

Kurtarma: grafik arayüz açılmazsa TTY üzerinden `sudo /usr/bin/python3 /home/bugra/.local/share/pil-modu/gpu_boot.py hybrid` çalıştırıp başarılı tamamlandıktan sonra yeniden başlat. Bu işlem yalnızca scriptin sahip olduğu GPU engelini kaldırır.

İlk uygulamadan önce profil, ekran modu/konumu/önceliği/ölçeği/parlaklığı ve değiştirilen donanım değerleri original-v2.json dosyasına kaydedilir. Geçişler bu kaydı ezmez. `geri` başarılı olursa kayıt kaldırılır. Bağlı olmayan ekranlar atlanır. EC'nin unspecified değeri yazılamadığı için kayıtta bu değer varsa comfort geri yüklenir. Günlük history.log dosyasındadır.

Yönetici yetkisi yalnızca donanım ayarlarını yazan kısa süreli pkexec işlemi için istenir. Parolasız sudo kuralı veya sürekli root servisi kurulmaz. Donanım yazma ve KDE uygulama hatalarında önceki değerlere dönüş denenir. Elektrik kesintisi veya süreçlerin zorla öldürülmesi halinde tam atomiklik garanti edilmez; `geri` kullanılabilir.

Modlar elle seçilir. Seçilen EC, CPU turbo ve ilgili donanım değerleri pil-modu-restore.service ile açılışta geri yüklenir; adaptör değişiminde otomatik mod seçilmez. KDE güç yönetiminden ya da MControlCenter'dan yapılan sonraki değişiklikler mod ayarlarını değiştirebilir. `durum` seçilen etiketin yanında gerçek değerleri gösterir.

Panelde görünen 59,96 Hz seçeneği sürücü tarafından reddedildiği için kullanıcının tercihiyle üç mod da 120 Hz kullanır.

Grafik arayüz: uygulama menüsünde **Güç Modları** veya `~/.local/bin/pil-modu-ui`. Üç mod, harici ekran seçimi, canlı NVIDIA durumu ve geri dönüş içerir.

Açılışta donanım geri yükleme: root sahipli `/usr/local/lib/pil-modu/hardware.py`, `/var/lib/pil-modu/hardware.json` ve `/etc/systemd/system/pil-modu-restore.service`. Servis açılışta bir kez çalışır; sürekli çalışan süreç bırakmaz.
