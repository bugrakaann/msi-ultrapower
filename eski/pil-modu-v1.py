#!/usr/bin/env python3
"""KDE için elle seçilen, geri alınabilir pil profilleri."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path.home() / '.local/share/pil-modu'
STATE = ROOT / 'onceki.json'

def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()

def screens():
    return json.loads(run('kscreen-doctor', '-j'))['outputs']

def plan(saved, current, mode):
    args = []
    old = {o['name']: o for o in saved['outputs']}
    panel = next((o for o in current if o['connected'] and o['name'].startswith('eDP')), None)
    if mode != 'normal' and panel is None:
        raise RuntimeError('Dahili ekran bulunamadı; ayarlar değiştirilmedi.')
    for o in current:
        if not o['connected'] or o['name'] not in old:
            continue
        prev = old[o['name']]
        prefix = 'output.' + o['name'] + '.'
        enabled = prev['enabled']
        if mode == 'tek':
            enabled = o['name'] == panel['name']
        elif mode == 'cift':
            enabled = True
        args.append(prefix + ('enable' if enabled else 'disable'))
        if enabled:
            pos = prev['pos']
            args.append(prefix + f"position.{pos['x']},{pos['y']}")
        # Only panel brightness is changed; refresh rate and mode stay untouched.
        if o['name'].startswith('eDP'):
            brightness = round(prev.get('brightness', 1) * 100)
            if mode != 'normal':
                brightness = min(brightness, 60)
            args.append(prefix + f'brightness.{brightness}')
    if not any(a.endswith('.enable') for a in args):
        raise RuntimeError('Geri yüklenecek bağlı ekran yok; mevcut düzen korundu.')
    return args

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mod', choices=['tek', 'cift', 'normal', 'durum'])
    parser.add_argument('--dene', action='store_true', help='Sadece uygulanacak komutları göster')
    opt = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = screens()
        profile = run('powerprofilesctl', 'get')
        if opt.mod == 'durum':
            print('Güç profili:', profile)
            print('Geri dönüş kaydı:', STATE.exists())
            for o in current:
                print(o['name'], 'açık' if o['enabled'] else 'kapalı', 'bağlı' if o['connected'] else 'bağlı değil')
            p = Path('/sys/bus/pci/devices/0000:01:00.0/power/runtime_status')
            if p.exists():
                print('NVIDIA:', p.read_text().strip())
            return
        if opt.mod == 'normal' and not STATE.exists():
            print('Geri dönüş kaydı yok; hiçbir ayar değiştirilmedi.')
            return
        saved = json.loads(STATE.read_text()) if STATE.exists() else {'profile': profile, 'outputs': current}
        args = plan(saved, current, opt.mod)
        target = saved['profile'] if opt.mod == 'normal' else 'balanced'
        if opt.dene:
            print('powerprofilesctl set', target)
            print('kscreen-doctor', *args)
            return
        if not STATE.exists():
            temp = STATE.with_suffix('.tmp')
            temp.write_text(json.dumps(saved, indent=2))
            os.chmod(temp, 0o600)
            temp.replace(STATE)
        try:
            run('powerprofilesctl', 'set', target)
            run('kscreen-doctor', *args)
        except Exception:
            run('powerprofilesctl', 'set', profile)
            raise
        if opt.mod == 'normal':
            STATE.unlink()
        print('Uygulandı:', opt.mod)
        print('Kontrol: pil-modu durum | Geri dönüş: pil-modu normal')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('İşlem tamamlanamadı:', exc, getattr(exc, 'stderr', ''), file=sys.stderr)
        print('Önceki ayar kaydı korunur. Geri dönüş: pil-modu normal', file=sys.stderr)
        sys.exit(1)
