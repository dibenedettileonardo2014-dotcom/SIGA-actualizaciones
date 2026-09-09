from pathlib import Path
import json,hashlib,shutil,zipfile
root=Path(__file__).resolve().parents[1]
import re
launcher=(root/'desktop_launcher.py').read_text(encoding='utf-8')
version=re.search(r'APP_VERSION = "([^"]+)"',launcher)[1]
revision=re.search(r'APP_REVISION = "([^"]+)"',launcher)[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest().upper()
m=json.loads((root/'version.json').read_text(encoding='utf-8'));previous=m['version'];m['version']=m['displayVersion']=version;m['revision']=revision;m['notes']='Actualizador con respaldo, rollback, verificacion de reinicio y conservacion de datos.'
for arch in ['x64','x86']:
 folder=root/'release'/arch/'SIGA'
 assert (folder/'_internal/index.html').read_bytes()==(root/'index.html').read_bytes()
 assert (folder/'_internal/update_worker.ps1').read_bytes()==(root/'update_worker.ps1').read_bytes()
 executable=(folder/'SIGA.exe').read_bytes();offset=int.from_bytes(executable[60:64],'little')
 assert executable[offset:offset+4]==b'PE\0\0'
 assert int.from_bytes(executable[offset+4:offset+6],'little')=={'x86':0x14c,'x64':0x8664}[arch]
 exe=root/f'SIGA-{arch}.exe';shutil.copyfile(folder/'SIGA.exe',exe)
 z=root/f'SIGA-update-{version}-{arch}.zip'
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as out:
  for p in folder.rglob('*'):
   if p.is_file():out.write(p,p.relative_to(folder).as_posix())
 for dest in [root/f'SIGA-update-{arch}.zip',root/'hosting'/z.name,root/'hosting'/f'SIGA-update-{arch}.zip']:shutil.copyfile(z,dest)
 meta=m['architectures'][arch]
 for key in ['packageUrl','packageUrls']:
  meta[key]=[s.replace(previous,version) for s in meta[key]] if isinstance(meta[key],list) else meta[key].replace(previous,version)
 meta.update(sha256=sha(exe),size=exe.stat().st_size,packageSha256=sha(z),packageSize=z.stat().st_size)
 installer=root/'installer'/f'SIGA-Setup-{version}-{arch}.exe';shutil.copyfile(installer,root/installer.name)
 m['installers'][arch]={'url':f'https://raw.githubusercontent.com/dibenedettileonardo2014-dotcom/SIGA-actualizaciones/main/{installer.name}','sha256':sha(installer),'size':installer.stat().st_size}
shutil.copyfile(root/'SIGA-x64.exe',root/'SIGA.exe')
shutil.copytree(root/'release/x64/SIGA/_internal',root/'_internal',dirs_exist_ok=True)
z=root/f'SIGA-update-{version}-x64.zip'
for dest in [root/f'SIGA-update-{version}.zip',root/'SIGA-update.zip',root/'hosting'/f'SIGA-update-{version}.zip',root/'hosting/SIGA-update.zip']:shutil.copyfile(z,dest)
for key in ['sha256','size','packageSha256','packageSize']:m[key]=m['architectures']['x64'][key]
for key in ['packageUrl','packageUrls']:m[key]=[s.replace(previous,version) for s in m[key]] if isinstance(m[key],list) else m[key].replace(previous,version)
for dest in ['version.json','hosting/version.json','release/version.json']:(root/dest).write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Packages and manifests synchronized')
