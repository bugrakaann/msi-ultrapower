#!/usr/bin/python3
import json
from pathlib import Path
import sys
import subprocess
EC='/sys/devices/platform/msi-ec/'
CPU='/sys/devices/system/cpu/intel_pstate/'
GPU='/sys/bus/pci/devices/0000:01:00.'
LED='/sys/class/leds/msiacpi::kbd_backlight/brightness'
ALLOWED={EC+'shift_mode':set('eco comfort sport turbo'.split()), EC+'fan_mode':set('auto silent basic advanced'.split()), EC+'cooler_boost':{'on','off'}, CPU+'no_turbo':{'0','1'}, LED:{'0','1','2','3'}, **{GPU+str(i)+'/power/control':{'auto','on'} for i in range(4)}}
def read_state():
 return {p:Path(p).read_text().strip() for p in ALLOWED if Path(p).exists()}
def writable(state):
 state=dict(state)
 if state.get(EC+'shift_mode')=='unspecified': state[EC+'shift_mode']='comfort'
 return state
def validate(state):
 for p,v in state.items():
  if p not in ALLOWED or v not in ALLOWED[p] or not Path(p).exists(): raise ValueError('Desteklenmeyen ayar: '+p+'='+str(v))
def apply(state):
 validate(state)
 before=read_state(); changed=[]
 try:
  for p,v in state.items():
   if before[p]==v: continue
   Path(p).write_text(v+'\n'); changed.append(p)
   if Path(p).read_text().strip()!=v: raise RuntimeError('Doğrulanamadı: '+p)
 except BaseException:
  for p in reversed(changed):
   try: Path(p).write_text(writable(before)[p]+'\n')
   except Exception as e: print('Geri alma hatası:',p,e,file=sys.stderr)
  raise
 return before

def persist(state):
 validate(state)
 folder=Path('/var/lib/pil-modu')
 folder.mkdir(parents=True,exist_ok=True)
 target=folder/'hardware.json'
 temp=folder/'hardware.tmp'
 temp.write_text(json.dumps(state,indent=2)); temp.chmod(0o600)
 installed=Path('/usr/local/lib/pil-modu/hardware.py')
 installed.parent.mkdir(parents=True,exist_ok=True)
 installed.write_text(Path(__file__).read_text()); installed.chmod(0o644)
 unit=Path('/etc/systemd/system/pil-modu-restore.service')
 unit.write_text('''[Unit]
Description=Restore selected MSI power settings
After=systemd-modules-load.service
Before=display-manager.service
ConditionPathExists=/var/lib/pil-modu/hardware.json

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/pil-modu/hardware.py --restore
ProtectHome=yes
ProtectSystem=full

[Install]
WantedBy=multi-user.target
''')
 subprocess.run(['systemctl','daemon-reload'],check=True)
 subprocess.run(['systemctl','enable','pil-modu-restore.service'],check=True)
 temp.replace(target)

def restore():
 state=json.loads(Path('/var/lib/pil-modu/hardware.json').read_text())
 # GPU functions intentionally disappear in Intel-only boot mode.
 state={p:v for p,v in state.items() if not p.startswith(GPU) or Path(p).exists()}
 apply(state)

if __name__=='__main__':
 try:
  if sys.argv[1]=='--restore':
   restore()
  else:
   target=json.loads(sys.argv[1])
   before=apply(target); print('READY',flush=True)
   if sys.stdin.readline().strip()!='COMMIT':
    apply(writable(before)); print('ROLLED_BACK',flush=True)
   else:
    try: persist(target)
    except BaseException:
     apply(writable(before))
     raise
 except Exception as e:
  print(e,file=sys.stderr); sys.exit(1)
