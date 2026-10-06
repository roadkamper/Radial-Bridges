"""Local file handling, ring estimation and Bambu post-processing integration."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid
import zipfile
from radial_bridges import parse, blocks, rewrite, point_distance, check, Refusal, MARK, flatten_deposits

VERSION = '1.8.0'
MAX_BYTES = 150 * 1024 * 1024

def data_dir():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))
    p = base/'Radial Bridges'
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_settings():
    try: return json.loads((data_dir()/'settings.json').read_text(encoding='utf-8'))
    except (OSError,ValueError): return {}

def write_settings(settings):
    atomic_write(data_dir()/'settings.json',json.dumps(settings,indent=2))

def atomic_write(path,text):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(prefix='.radial-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:f.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def plate_names(path):
    if not zipfile.is_zipfile(path): return []
    with zipfile.ZipFile(path) as z:
        return [i.filename for i in z.infolist() if re.fullmatch(r'Metadata/plate_\d+\.gcode',i.filename,re.I)]

def read_input(path,plate=None):
    path=Path(path)
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            choices=plate_names(path)
            check(choices,'This 3MF contains no sliced G-code. In Studio, slice first and export the sliced plate file.')
            plate=plate or choices[0]
            check(plate in choices,'Selected plate is not present.')
            check(z.getinfo(plate).file_size<=MAX_BYTES,'This plate exceeds the 150 MB limit.')
            raw=z.read(plate)
    else:
        check(path.stat().st_size<=MAX_BYTES,'This G-code exceeds the 150 MB limit.')
        raw=path.read_bytes()
    text=raw.decode('utf-8-sig')
    check('\x00' not in text,'Binary G-code is not supported. Export plain text G-code.')
    check(MARK not in text,'This file already contains radial bridges. Open a fresh original slice to modify it again.')
    return text

def signature(dep):
    # Machine positions only: stable across comments, timestamps and E-mode changes.
    seq=[tuple(round(v,3) for v in (m.before.x,m.before.y,m.after.x,m.after.y,m.after.z)) for m in dep]
    if any(m.command in ('G2','G3') for m in dep):
        seq.append([(m.command,{k:round(v,5) for k,v in m.args.items() if k in ('I','J','R')}) for m in dep])
    return hashlib.sha256(json.dumps(seq,separators=(',',':')).encode()).hexdigest()

def estimate(dep,number,source_width=.42):
    pts=[(st.x,st.y) for m in dep for st in (m.before,m.after)]
    cx=(min(x for x,y in pts)+max(x for x,y in pts))/2
    cy=(min(y for x,y in pts)+max(y for x,y in pts))/2
    ro=max(math.hypot(x-cx,y-cy) for x,y in pts)
    ri=min(point_distance(cx,cy,m) for m in dep)
    length=sum(m.length for m in dep)
    pitch=math.pi*(ro*ro-ri*ri)/length if length else 0
    cfg=dict(block=number,z_mm=dep[0].after.z,center_x_mm=round(cx,5),center_y_mm=round(cy,5),
             inner_radius_mm=round(ri,5),outer_radius_mm=round(ro,5),pitch_mm=round(pitch,5),
             source_line_width_mm=round(source_width,5),bridge_width_mm=round(source_width,5),
             pattern='zigzag',continuous_pass=True,calibration_mode=False,calibration_range_mm=.1,calibration_steps=5,
             bridge_speed_mm_s=None,travel_speed_mm_s=100,
             retract_mm=0,retract_speed_mm_s=30,geometry_tolerance_mm=.15)
    plausible=(ri>0 and ro/ri<=1.5 and .1<=pitch<=1.5 and len({m.after.z for m in dep})==1)
    return cfg,plausible

def segments(dep):
    return [(m.before.x,m.before.y,m.after.x,m.after.y) for m in dep]

def make_region(raw_dep, ids, line_ranges, members=None, source_width=.42):
    flat=flatten_deposits(raw_dep)
    cfg,plausible=estimate(flat,ids[0],source_width)
    cfg['blocks']=ids
    return dict(number=ids[0],numbers=ids,z=cfg['z_mm'],cfg=cfg,plausible=plausible,
                signature=signature(raw_dep),segments=segments(flat),
                longest=max(m.length for m in raw_dep),lines=line_ranges,
                _dep=raw_dep,members=members or [])

def combine_members(members):
    check(members,'Select at least one bridge region.')
    check(max(r['z'] for r in members)-min(r['z'] for r in members)<.001,
          'Only regions at the same Z height can be combined. Different layers stay separate.')
    members=sorted(members,key=lambda r:r['number'])
    width=sum(r['cfg'].get('source_line_width_mm',.42)*sum(m.length for m in r['_dep']) for r in members)/sum(m.length for r in members for m in r['_dep'])
    return make_region([m for r in members for m in r['_dep']],
                       [r['number'] for r in members],[r['lines'] for r in members],members,width)

def analyze(text, combine=True):
    lines=text.splitlines(keepends=True);moves=parse(lines);raw=[]
    for n,(start,end,dep) in enumerate(blocks(lines,moves),1):
        check(all(m.after.z is not None for m in dep),f'Region #{n} has no known layer height.')
        widths=[float(m.group(1)) for line in lines[start:min(end,start+20)] if (m:=re.match(r'^;\s*LINE_WIDTH:\s*('+r'[-+]?\d*\.?\d+'+r')',line,re.I))]
        r=make_region(dep,[n],[start+1,end],source_width=(widths[0] if widths else .42));raw.append(r)
    check(raw,'No labeled bridge regions found. Export sliced G-code with Bambu feature comments.')
    if not combine:return raw
    groups=[]
    for r in raw:
        # A tolerance handles harmless decimal representation differences.
        group=next((g for g in groups if abs(g[0]['z']-r['z'])<.001 and
                    g[0]['_dep'][0].before.tool==r['_dep'][0].before.tool),None)
        if group is None:groups.append([r])
        else:group.append(r)
    return [combine_members(g) for g in groups]

def convert(text,cfg):
    result,report=rewrite(text,cfg)
    lines=result.splitlines();moves=parse(lines);active=False;dep=[]
    for line,m in zip(lines,moves):
        if line==MARK:active=True
        elif line=='; END_RADIAL_BRIDGES_V1':active=False
        elif active and m.deposit:dep.append(m)
    return result,report,segments(dep)

def generated_sections(text):
    """Return every generated extrusion section grouped by physical Z."""
    lines=text.splitlines();moves=parse(lines);active=False;dep=[];sections=[]
    for line,m in zip(lines,moves):
        if line==MARK:
            active=True;dep=[]
        elif line=='; END_RADIAL_BRIDGES_V1':
            if active and dep:sections.append((dep[0].after.z,segments(dep)))
            active=False;dep=[]
        elif active and m.deposit:dep.append(m)
    return sections

def convert_many(text,cfgs):
    """Convert independent bridge heights into one output without renumbering targets."""
    check(cfgs,'Generate at least one radial bridge preview.')
    check(MARK not in text,'Open a fresh original slice; this file already contains radial bridges.')
    occupied=set()
    ranges=[];heights=[]
    for cfg in cfgs:
        ids=set(cfg.get('blocks') or [cfg['block']])
        check(not occupied.intersection(ids),'Two generated height sections select the same bridge region.')
        check(not any(abs(cfg['z_mm']-z)<.001 for z in heights),'Generate one combined selection per physical bridge height.')
        heights.append(cfg['z_mm']);ranges.append((min(ids),max(ids)))
        occupied.update(ids)
    ordered=sorted(ranges)
    check(all(a[1]<c[0] for a,c in zip(ordered,ordered[1:])),
          'Bridge heights have interleaved source regions. Convert a non-interleaved selection instead.')
    indexed=list(enumerate(cfgs))
    # Later blocks are replaced first so earlier configured block numbers remain stable.
    indexed.sort(key=lambda item:max(item[1].get('blocks') or [item[1]['block']]),reverse=True)
    modified=text;by_index={}
    for original_index,cfg in indexed:
        modified,report=rewrite(modified,cfg,_allow_existing=True)
        by_index[original_index]=report
    sections=generated_sections(modified);previews=[]
    for cfg in cfgs:
        matches=[lines for z,lines in sections if abs(z-cfg['z_mm'])<.001]
        check(matches,f"Could not isolate the generated preview at Z {cfg['z_mm']:.3f} mm.")
        previews.append([line for section in matches for line in section])
    return modified,[by_index[i] for i in range(len(cfgs))],previews

def save_profile(cfg,region,source_label):
    return save_profiles([(cfg,region)],source_label)

def save_profiles(items,source_label):
    check(items,'Generate at least one bridge height before creating a Studio profile.')
    p=data_dir()/'profiles'/(uuid.uuid4().hex+'.json')
    targets=[]
    for cfg,region in items:
        members=[r for r in (region.get('members') or [region]) if r['number'] in region['numbers']]
        targets.append(dict(config=cfg,signature=region['signature'],
                            member_signatures=[r['signature'] for r in members]))
    profile=dict(version=3,targets=targets,source=source_label,created=time.time())
    atomic_write(p,json.dumps(profile,indent=2))
    return p

def hook(profile_path,gcode):
    profile=json.loads(Path(profile_path).read_text(encoding='utf-8'))
    text=read_input(gcode);raw=analyze(text,combine=False)
    targets=profile.get('targets')
    if targets is None:
        targets=[dict(config=profile['config'],signature=profile['signature'],
                      member_signatures=profile.get('member_signatures',[profile['signature']]))]
    cfgs=[]
    for target in targets:
        selected=[]
        for sig in target.get('member_signatures',[target['signature']]):
            matches=[r for r in raw if r['signature']==sig]
            check(len(matches)==1,'The selected bridge geometry changed or is ambiguous. Reopen this slice in Radial Bridges and copy a new Studio command.')
            selected.append(matches[0])
        combined=combine_members(selected)
        cfg=dict(target['config']);cfg['block']=combined['number'];cfg['blocks']=combined['numbers'];cfg['z_mm']=combined['z']
        cfgs.append(cfg)
    modified,reports,_=convert_many(text,cfgs);report=dict(reports[0])
    report['conversions']=reports;report['converted_heights_mm']=[r['z_mm'] for r in reports]
    p=Path(gcode);backups=data_dir()/'backups';backups.mkdir(exist_ok=True)
    backup=backups/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]+'.gcode')
    backup.write_bytes(p.read_bytes());atomic_write(p,modified);report['backup']=str(backup)
    atomic_write(data_dir()/'last-hook.json',json.dumps(report,indent=2))
    return report

def find_bambu():
    settings=read_settings()
    candidates=[settings.get('bambu_path','')]
    for env in ('ProgramFiles','ProgramFiles(x86)','LOCALAPPDATA'):
        root=Path(os.environ.get(env,'C:/Program Files'))
        for suffix in ('Bambu Studio/bambu-studio.exe','BambuStudio/bambu-studio.exe','Programs/Bambu Studio/bambu-studio.exe'):
            candidates.append(str(root/suffix))
    if os.name=='nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\bambu-studio.exe',0,winreg.KEY_READ|view) as k:
                        candidates.append(winreg.QueryValue(k,None))
                except OSError:pass
                try:
                    with winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall',0,winreg.KEY_READ|view) as parent:
                        for i in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                with winreg.OpenKey(parent,winreg.EnumKey(parent,i)) as k:
                                    name=winreg.QueryValueEx(k,'DisplayName')[0]
                                    if 'Bambu Studio' in name:
                                        directory=winreg.QueryValueEx(k,'InstallLocation')[0]
                                        candidates.append(str(Path(directory)/'bambu-studio.exe'))
                            except OSError:pass
                except OSError:pass
    return next((p for p in candidates if p and Path(p).is_file()),'')

def launch_bambu(exe,gcode):
    check(Path(exe).is_file(),'Locate bambu-studio.exe first.')
    check(Path(gcode).is_file(),'Save the converted G-code first.')
    return subprocess.Popen([str(exe),'--gcodeviewer',str(Path(gcode).resolve())])
