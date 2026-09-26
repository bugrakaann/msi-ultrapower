#!/usr/bin/python3
"""Prepare Intel-only / hybrid boot. Never detach a live GPU or reboot."""
import os
from pathlib import Path
import subprocess
import sys
HEADER='# Managed by pil-modu gpu_boot.py\n'
MOD=Path('/etc/modprobe.d/90-pil-modu-nvidia.conf')
RULE=Path('/etc/udev/rules.d/50-pil-modu-nvidia.rules')
INIT=Path('/etc/mkinitcpio.conf.d/99-pil-modu-gpu.conf')
MODULES=('nvidia','nvidia_drm','nvidia_modeset','nvidia_uvm','nouveau','nova_core','nova_drm','i2c_nvidia_gpu')
CONFIG={
 MOD:HEADER+''.join(f'blacklist {m}\ninstall {m} /usr/bin/false\n' for m in MODULES),
 RULE:HEADER+''.join('ACTION=="add", SUBSYSTEM=="pci", KERNEL=="0000:01:00.'+str(i)+'", ATTR{vendor}=="0x10de", ATTR{power/control}="auto", ATTR{remove}="1"\n' for i in (1,2,3,0)),
 INIT:HEADER+'''pil_modu_modules=()
for pil_modu_module in "${MODULES[@]}"; do
    case "$pil_modu_module" in
        nvidia*|nouveau|nova_core|nova_drm|i2c_nvidia_gpu) ;;
        *) pil_modu_modules+=("$pil_modu_module") ;;
    esac
done
MODULES=("${pil_modu_modules[@]}")
unset pil_modu_modules pil_modu_module
'''
}
def write(path,content):
 if content is None:
  path.unlink(missing_ok=True)
 else:
  temp=path.with_suffix(path.suffix+'.tmp')
  temp.write_text(content); temp.chmod(0o644); temp.replace(path)
def configure(mode):
 if mode not in ('integrated','hybrid'): raise ValueError('Geçersiz GPU modu')
 if os.geteuid()!=0: raise RuntimeError('Yönetici yetkisi gerekiyor')
 igpu=Path('/sys/bus/pci/devices/0000:00:02.0')
 if not igpu.exists() or (igpu/'vendor').read_text().strip()!='0x8086': raise RuntimeError('Intel GPU doğrulanamadı')
 before={p:p.read_text() if p.exists() else None for p in CONFIG}
 if any(v is not None and not v.startswith(HEADER) for v in before.values()): raise RuntimeError('Beklenmeyen yapılandırma; mevcut dosyalara dokunulmadı')
 desired=CONFIG if mode=='integrated' else {p:None for p in CONFIG}
 if before==desired:
  print('GPU açılış tercihi zaten:',mode,flush=True); return
 # Back up exactly the files owned by this tool; no existing distro settings are removed.
 backup=Path('/var/lib/pil-modu'); backup.mkdir(parents=True,exist_ok=True)
 import json
 (backup/'gpu-before.json').write_text(json.dumps({str(p):v for p,v in before.items()},indent=2))
 try:
  for p,v in desired.items(): write(p,v)
  print('Açılış imajları hazırlanıyor; bu işlem birkaç dakika sürebilir...',flush=True)
  subprocess.run(['/usr/bin/mkinitcpio','-P'],check=True)
 except BaseException:
  for p,v in before.items(): write(p,v)
  print('GPU yapılandırması geri alındı; eski açılış imajları yeniden oluşturuluyor.',flush=True)
  subprocess.run(['/usr/bin/mkinitcpio','-P'],check=True)
  raise
 print('GPU açılış tercihi kaydedildi:',mode,flush=True)
 print('Değişiklik yeniden başlatınca geçerli olacak. Oturum kapatılmadı.',flush=True)
if __name__=='__main__':
 try: configure(sys.argv[1])
 except Exception as exc: print('GPU yapılandırma hatası:',exc,file=sys.stderr); sys.exit(1)
