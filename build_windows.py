"""Rebuild the Windows installer from source on Linux or Windows.
Requires Python 3.10+, pip, ziglang 0.13.0 and NSIS 3.x (makensis on PATH).
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile

root=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--makensis',default=shutil.which('makensis') or 'makensis');ap.add_argument('--skip-installer',action='store_true',help='Build the launcher/runtime only, for signing before packaging.');a=ap.parse_args()
vendor=root/'vendor';vendor.mkdir(exist_ok=True)
lock=json.loads((root/'dependencies.json').read_text())
py=vendor/'python-3.12.10-embed-amd64.zip'
if not py.exists():urllib.request.urlretrieve('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip',py)
subprocess.run([sys.executable,'-m','pip','download','--only-binary=:all:','--platform','win_amd64','--python-version','312','--dest',str(vendor),'PySide6-Essentials==6.8.3'],check=True)
runtime=root/'payload/runtime';runtime.mkdir(parents=True,exist_ok=True)
for name,digest in lock.items():
    path=vendor/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise RuntimeError('Dependency checksum mismatch: '+name)
    with zipfile.ZipFile(path) as z:z.extractall(runtime)
(runtime/'python312._pth').write_text('python312.zip\n.\n..\nimport site\n')
subprocess.run([sys.executable,'-m','ziglang','rc','/fo',str(root/'launcher.res'),str(root/'launcher.rc')],check=True,cwd=root)
subprocess.run([sys.executable,'-m','ziglang','cc','-target','x86_64-windows-gnu','-O2','-municode','-Wl,--subsystem,windows',str(root/'launcher.c'),str(root/'launcher.res'),'-o',str(root/'payload/RadialBridges.exe'),'-luser32','-lshell32'],check=True,cwd=root)
if not a.skip_installer:
    subprocess.run([a.makensis,'-V3','installer.nsi'],check=True,cwd=root)
    print(root/'RadialBridges-Setup.exe')
else:print(root/'payload/RadialBridges.exe')
