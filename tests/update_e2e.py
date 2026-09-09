from pathlib import Path
import hashlib,json,os,subprocess,sys,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
arch=sys.argv[1]; mode=sys.argv[2] if len(sys.argv)>2 else 'worker'
base=ROOT/'.tools'/('update-e2e-'+mode+'-'+arch)
install=base/'SIGA';install.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(ROOT/f'SIGA-update-1.4.43-{arch}.zip') as z:z.extractall(install)
work=install/'Updater';work.mkdir(exist_ok=True)
env={**os.environ,'LOCALAPPDATA':str(base),'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS':'--remote-debugging-port=9229'}
exe=install/'SIGA.exe'
for name in ['Documentos/control.txt','database.json','configuration.json','oauth-password-reset.dat']:
 p=install/name;p.parent.mkdir(exist_ok=True);p.write_text('SIGA preservation test '+name,encoding='utf-8')
data={str(p.relative_to(install)):hashlib.sha256(p.read_bytes()).hexdigest() for p in install.rglob('*') if p.is_file() and p.name in ['control.txt','database.json','configuration.json','oauth-password-reset.dat']}

def evaluate(expression):
 f=base/'expression.js';f.write_text(expression,encoding='utf-8')
 r=subprocess.run(['node',str(ROOT/'tests/native_webview.cjs'),str(f)],capture_output=True,text=True,encoding='utf-8',timeout=150)
 if r.returncode:raise RuntimeError(r.stderr)
 return json.loads(r.stdout.strip())

def until(expression,seconds=100):
 end=time.time()+seconds
 while time.time()<end:
  try:
   result=evaluate(expression)
   if result:return result
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('Timed out: '+expression)

def close():
 subprocess.run(['powershell','-NoProfile','-Command',"Get-Process SIGA -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq '"+str(exe).replace("'","''")+"'} | ForEach-Object {Stop-Process -Id $_.Id -Force}"],capture_output=True)

try:
 old=subprocess.Popen([str(exe)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
 version=until("window.pywebview?.api?.get_installed_version ? window.pywebview.api.get_installed_version() : null")
 assert version['version']=='1.4.43',version
 assert evaluate("localStorage.setItem('siga_update_test_preserve','persistent');localStorage.getItem('siga_update_test_preserve')")=='persistent'
 print(arch,mode,'previous version and persistent profile verified',flush=True)
 if mode=='published':
  ready=until("window.pywebview.api.prepare_available_update()",240)
  assert ready.get('ready') and ready['version']=='1.4.44',ready
  print(arch,'official release detected and downloaded',flush=True)
  assert evaluate("window.pywebview.api.apply_prepared_update()")['ok']
 else:
  close();old.wait(timeout=20)
  manifest=json.loads((ROOT/'version.json').read_text());meta=manifest['architectures'][arch]
  source=ROOT/f'SIGA-update-1.4.44-{arch}.zip'
  job={'target':str(install),'work':str(work),'source':str(source),'sha256':meta['packageSha256'],'version':manifest['version'],'revision':manifest['revision'],'parent':2147483647}
  (work/'prepared-update.json').write_text('{}')
  if mode=='rollback':job['revision']='unconfirmed-startup'
  jobfile=work/'apply-job.json';jobfile.write_text(json.dumps(job))
  worker=subprocess.Popen(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'update_worker.ps1'),'-Job',str(jobfile)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
 updated=until("window.pywebview?.api?.get_installed_version ? window.pywebview.api.get_installed_version().then(v=>v.version==='1.4.44'?v:null) : null",180)
 assert updated['architecture']==arch,updated
 assert evaluate("localStorage.getItem('siga_update_test_preserve')")=='persistent'
 for name,digest in data.items():assert hashlib.sha256((install/name).read_bytes()).hexdigest()==digest,name
 assert hashlib.sha256(exe.read_bytes()).hexdigest().upper()==json.loads((ROOT/'version.json').read_text())['architectures'][arch]['sha256']
 if mode=='rollback':
  assert worker.wait(timeout=110)==1
  restored=until("window.pywebview?.api?.get_installed_version ? window.pywebview.api.get_installed_version().then(v=>v.version==='1.4.43'?v:null) : null")
  assert json.loads((work/'transaction.json').read_text(encoding='utf-8-sig'))['status']=='rolled-back'
  assert evaluate("localStorage.getItem('siga_update_test_preserve')")=='persistent'
  for name,digest in data.items():assert hashlib.sha256((install/name).read_bytes()).hexdigest()==digest,name
  with zipfile.ZipFile(ROOT/f'SIGA-update-1.4.43-{arch}.zip') as z:assert exe.read_bytes()==z.read('SIGA.exe')
  print(arch,'PASS forced startup failure restored and relaunched 1.4.43; data and profile preserved',flush=True)
 if mode=='worker':
  assert worker.wait(timeout=100)==0,(work/'worker-error.log').read_text() if (work/'worker-error.log').exists() else 'worker exit'
  assert json.loads((work/'transaction.json').read_text(encoding='utf-8-sig'))['status']=='committed'
 assert not (work/'prepared-update.json').exists()
 print(arch,mode,'PASS updated executable, real WebView restart, architecture, localStorage, documents, database, settings and credential file preserved',flush=True)
 (base/'result.json').write_text(json.dumps({'architecture':arch,'mode':mode,'from':'1.4.43','to':updated,'dataPreserved':list(data),'profilePreserved':True}))
finally:close()
