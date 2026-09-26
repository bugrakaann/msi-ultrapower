import importlib.util, importlib.machinery, tempfile, unittest
from pathlib import Path
loader=importlib.machinery.SourceFileLoader('profiles','/home/bugra/.local/bin/pil-modu')
spec=importlib.util.spec_from_loader('profiles',loader); app=importlib.util.module_from_spec(spec); loader.exec_module(app)
def output(name,ids=('old','new')):
 return dict(name=name,connected=True,enabled=True,scale=1.25,priority=1,brightness=1,pos={'x':0,'y':0},currentModeId=ids[0],modes=[dict(id=ids[0],refreshRate=120.11,size={'width':1920,'height':1080}),dict(id=ids[1],refreshRate=59.96,size={'width':1920,'height':1080}),dict(id='low',refreshRate=48.08,size={'width':1920,'height':1080})])
class Tests(unittest.TestCase):
 def test_modes_survive_id_change(self):
  self.assertEqual(app.mode_for(output('eDP-1',('a','b')),output('eDP-1')), 'a')
 def test_battery_external_choices(self):
  outputs=[output('eDP-1'),output('HDMI-A-1')]
  args=app.screen_plan(outputs,outputs,app.PRESETS['batarya'])
  self.assertIn('output.HDMI-A-1.disable',args); self.assertIn('output.eDP-1.mode.old',args)
  args=app.screen_plan(outputs,outputs,app.PRESETS['batarya'],'koru')
  self.assertIn('output.HDMI-A-1.mode.old',args)
 def test_no_panel_abort(self):
  with self.assertRaises(RuntimeError): app.screen_plan([],[],app.PRESETS['batarya'])
 def test_unsupported_hz_abort(self):
  with self.assertRaises(RuntimeError): app.mode_for(output('eDP-1'),hz=144)
 def test_restore(self):
  args=app.screen_plan([output('eDP-1',('a','b'))],[output('eDP-1')])
  self.assertIn('output.eDP-1.mode.a',args); self.assertIn('output.eDP-1.brightness.100',args)
 def test_hardware_failure_rollback(self):
  with tempfile.TemporaryDirectory() as d:
   first=Path(d)/'first'; first.write_text('old\n')
   second=Path(d)/'second'; second.write_text('old\n')
   old_allowed=app.hw.ALLOWED; app.hw.ALLOWED={str(first):{'old','new'},str(second):{'old','new'}}
   original_write=Path.write_text
   def failing(path,value,*args,**kwargs):
    if path==second and value=='new\n': raise OSError('injected failure')
    return original_write(path,value,*args,**kwargs)
   from unittest.mock import patch
   try:
    with patch.object(Path,'write_text',failing):
     with self.assertRaises(OSError): app.hw.apply({str(first):'new',str(second):'new'})
    self.assertEqual(first.read_text().strip(),'old')
   finally: app.hw.ALLOWED=old_allowed
if __name__=='__main__': unittest.main()
