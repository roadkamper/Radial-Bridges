#!/usr/bin/env python3
"""Conservative annular bridge post-processor for Bambu Studio. Python 3.10+.
Run --inspect FILE first. See README.md for configuration and limitations.
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
from dataclasses import dataclass

MARK = '; RADIAL_BRIDGES_V1'
NUM = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
FEATURE = re.compile(r'^;\s*(?:FEATURE|TYPE):\s*(.*?)\s*$', re.I)
BOUNDARY = re.compile(r'^;\s*(?:FEATURE:|TYPE:|CHANGE_LAYER|LAYER_CHANGE|LAYER:|LAYER_HEIGHT:|Z_HEIGHT:|OBJECT_ID:|printing object|stop printing object)', re.I)

class Refusal(ValueError):
    pass

def check(ok, message):
    if not ok:
        raise Refusal(message)

@dataclass(slots=True)
class State:
    x: float | None = None
    y: float | None = None
    z: float | None = None
    e: float = 0.0
    f: float | None = None
    absolute: bool = True
    relative_e: bool = False
    mm: bool = True
    plane: str = "G17"
    incremental_arc: bool = True
    tool: str = "unknown"

@dataclass(slots=True)
class Move:
    index: int
    command: str
    before: State
    after: State
    de: float
    length: float
    args: dict

    @property
    def deposit(self):
        return self.de > 1e-8 and self.length > 1e-7

def command(line):
    code = line.split(';', 1)[0].strip()
    if not code:
        return '', {}
    m = re.match(r'([GMT]\d+(?:\.\d+)?)\b', code, re.I)
    if not m:
        return '?', {}
    cmd = m.group(1).upper()
    return cmd, {k.upper(): float(v) for k, v in re.findall(r'([A-Za-z])\s*(' + NUM + ')', code[m.end():])}

def parse(lines):
    state = State()
    moves = []
    for i, line in enumerate(lines):
        cmd, a = command(line)
        before = state
        state = copy.copy(state)
        if cmd in ('G17', 'G18', 'G19'):
            state.plane = cmd
        elif cmd in ('G90.1', 'G91.1'):
            state.incremental_arc = cmd == 'G91.1'
        elif cmd.startswith('T'):
            state.tool = cmd
        elif cmd == 'G90':
            state.absolute = True
        elif cmd == 'G91':
            state.absolute = False
        elif cmd == 'M82':
            state.relative_e = False
        elif cmd == 'M83':
            state.relative_e = True
        elif cmd in ('G20', 'G21'):
            state.mm = cmd == 'G21'
        elif cmd == 'G92':
            for axis in 'XYZE':
                if axis in a:
                    setattr(state, axis.lower(), a[axis])
        elif cmd in ('G0', 'G1', 'G2', 'G3', 'G00', 'G01'):
            for axis in 'XYZ':
                if axis in a:
                    old = getattr(state, axis.lower())
                    setattr(state, axis.lower(), a[axis] if state.absolute else (old + a[axis] if old is not None else None))
            if 'E' in a:
                state.e = state.e + a['E'] if state.relative_e else a['E']
            if 'F' in a:
                state.f = a['F']
        # Homing/coordinate-system selection invalidate inferred coordinates.
        elif cmd in ('G28', 'G53', 'G54', 'G55', 'G56', 'G57', 'G58', 'G59'):
            state.x = state.y = state.z = None
        length = 0.0
        if cmd in ('G0', 'G1', 'G2', 'G3', 'G00', 'G01') and None not in (before.x, before.y, state.x, state.y):
            length = math.hypot(state.x - before.x, state.y - before.y)
        if cmd in ('G2','G3') and None not in (before.x,before.y,state.x,state.y):
            try:
                _,_,r,_,sweep = arc_geometry(before,state,a,cmd)
                length = abs(sweep)*r
            except Refusal:
                pass
        moves.append(Move(i, cmd, before, state, state.e - before.e if cmd in ('G0','G1','G2','G3','G00','G01') else 0, length, a))
    return moves

def arc_geometry(before, after, args, cmd):
    check(before.plane == 'G17' and before.incremental_arc,
          'Arc requires XY plane and incremental I/J center offsets.')
    check('R' not in args and ('I' in args or 'J' in args),
          'Only XY arcs with I/J center offsets are supported; turn off arc fitting for R arcs.')
    cx,cy=before.x+args.get('I',0),before.y+args.get('J',0)
    radius=math.hypot(before.x-cx,before.y-cy)
    check(radius>0 and abs(math.hypot(after.x-cx,after.y-cy)-radius)<.05,
          'Arc endpoint does not match its center/radius.')
    first=math.atan2(before.y-cy,before.x-cx)
    last=math.atan2(after.y-cy,after.x-cx)
    sweep=(last-first)%(2*math.pi)
    if cmd=='G2':sweep=-((first-last)%(2*math.pi))
    if abs(sweep)<1e-10:sweep=-2*math.pi if cmd=='G2' else 2*math.pi
    return cx,cy,radius,first,sweep

def flatten_deposits(dep):
    result=[]
    for m in dep:
        if m.command not in ('G2','G3'):
            result.append(m);continue
        try:cx,cy,radius,first,sweep=arc_geometry(m.before,m.after,m.args,m.command)
        except Refusal as ex:raise Refusal(f'Line {m.index+1}: {ex}')
        # <=0.01 mm chord sag, and no angular step greater than 5 degrees.
        angle=min(math.radians(5),2*math.acos(max(-1,1-.01/radius)))
        steps=max(1,math.ceil(abs(sweep)/angle));previous=m.before
        check(steps<100000, f'Line {m.index+1}: arc is too large to inspect.')
        for k in range(1,steps+1):
            end=copy.copy(m.after)
            end.x=cx+radius*math.cos(first+sweep*k/steps)
            end.y=cy+radius*math.sin(first+sweep*k/steps)
            if k==steps:end.x,end.y=m.after.x,m.after.y
            result.append(Move(m.index,'G1',previous,end,m.de/steps,
                               math.hypot(end.x-previous.x,end.y-previous.y),{}))
            previous=end
    return result

def blocks(lines, moves):
    result = []
    active = None
    for i, line in enumerate(lines):
        if BOUNDARY.match(line):
            if active is not None:
                result.append((active, i))
                active = None
            m = FEATURE.match(line)
            if m and m.group(1).lower() in ('bridge', 'bridge infill', 'internal bridge', 'internal bridge infill'):
                active = i
    if active is not None:
        result.append((active, len(lines)))
    return [(s, e, [m for m in moves[s:e] if m.deposit]) for s, e in result if any(m.deposit for m in moves[s:e])]

def inspect(text):
    lines = text.splitlines(keepends=True)
    moves = parse(lines)
    out = []
    for n, (s, e, dep) in enumerate(blocks(lines, moves), 1):
        pts = [(st.x, st.y) for m in dep for st in (m.before, m.after)]
        out.append(dict(block=n, lines=[s+1,e], z=sorted(set(m.after.z for m in dep)),
                        xy_bounds=[min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)],
                        extrusion_moves=len(dep), extrusion_mm=round(sum(m.de for m in dep),5)))
    return out

def point_distance(px, py, m):
    x, y = m.before.x, m.before.y
    dx, dy = m.after.x-x, m.after.y-y
    t = max(0, min(1, ((px-x)*dx+(py-y)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-x-t*dx, py-y-t*dy)

# Commands retained in their original order at equivalent path progress.
PRESERVE = {'M106','M107','M204','M205','M400','G4','M73','M900','G17','G91.1'}
MODE_ONLY = {'M82','M83','G90','G21'}
MOTION = {'G0','G1','G00','G01','G2','G3'}
SAFE_G_PRESERVE = set()
UNSAFE_M = {'M200','M620','M621','M622','M623','M624','M625'}

def target_preserve(command):
    # Do not assume unknown firmware commands preserve position, units or tool.
    # M991 is retained for the tested Bambu layer-timelapse path.
    return command in PRESERVE|{'M991'}

def joinable_gap(left, right, lines, moves):
    """Remove only a balanced travel gap; never move other printed features.

    Travel-only Z lifts and repeated feature/layer comments can separate one
    physical bridge layer. One replacement removes those artificial boundaries.
    Unknown commands and object boundaries stay in their original positions.
    """
    gap=moves[left['stop']:right['start']]
    if abs(left['after'].z-right['before'].z)>1e-6:return False
    if abs(sum(m.de for m in gap))>1e-6:return False
    rates=[m.de/m.length for m in left['dep']+right['dep']]
    if max(rates)/min(rates)>=1.2:return False
    for m in gap:
        if re.match(r'^;\s*(?:OBJECT_ID:|printing object|stop printing object)',lines[m.index],re.I):return False
        if m.deposit or (m.de < -1e-8 and m.length>1e-7):return False
        if m.command not in MOTION|PRESERVE|MODE_ONLY|{''} and not (m.command=='G92' and set(m.args)<={'E'}):return False
        if m.command in MOTION:
            if set(m.args)-set('XYZEF'):return False
            if not m.after.mm or not m.after.absolute:return False
    return True

def gap_clear_of_ring(left,right,lines,moves,cx,cy,ri,ro,tol):
    """True when intervening printed paths are physically inside/outside the ring."""
    gap=moves[left['stop']:right['start']]
    if abs(sum(m.de for m in gap if not m.deposit))>.0001:return False
    for m in gap:
        if re.match(r'^;\s*(?:OBJECT_ID:|printing object|stop printing object)',lines[m.index],re.I):return False
        if m.command not in MOTION|PRESERVE|MODE_ONLY|{''} and not (m.command=='G92' and set(m.args)<={'E'}):return False
        if not m.deposit:continue
        low=point_distance(cx,cy,m)
        high=max(math.hypot(st.x-cx,st.y-cy) for st in (m.before,m.after))
        if low<=ro+tol and high>=ri-tol:return False
    return True

def rewrite(text, cfg, _allow_existing=False):
    if not _allow_existing:
        check(MARK not in text, 'Already processed. Re-slice the original project before running again.')
    required=['z_mm','center_x_mm','center_y_mm','inner_radius_mm','outer_radius_mm','pitch_mm']
    for key in required:
        check(isinstance(cfg.get(key),(int,float)) and not isinstance(cfg[key],bool) and math.isfinite(cfg[key]),f'Configure a finite numeric {key}.')
    cx,cy,ri,ro,pitch,z=(cfg[k] for k in ('center_x_mm','center_y_mm','inner_radius_mm','outer_radius_mm','pitch_mm','z_mm'))
    check(0<ri<ro and .1<=pitch<=1.5,'Require 0 < inner radius < outer radius and spacing 0.1–1.5 mm.')
    check(ro/ri<=1.5,'This selection is not a narrow ring. Select only the regions forming this ring at the same height.')
    ids=cfg.get('blocks',[cfg.get('block')])
    check(isinstance(ids,list) and ids and all(isinstance(n,int) and not isinstance(n,bool) and n>=1 for n in ids),'Select at least one valid bridge region.')
    check(len(set(ids))==len(ids),'Duplicate bridge regions selected.')
    ids=sorted(ids)
    lines=text.splitlines(keepends=True);moves=parse(lines);bs=blocks(lines,moves)
    check(max(ids)<=len(bs),'Selected bridge region does not exist in this slice.')
    pieces=[]
    for number in ids:
        block_start,_,original=bs[number-1]
        start,stop=original[0].index,original[-1].index+1
        for m in moves[block_start:start]:
            allowed=m.command in MOTION|MODE_ONLY|{''} or target_preserve(m.command) or (m.command=='G92' and set(m.args)<={'E'})
            check(allowed,f'Unsupported bridge setup command at line {m.index+1}: {lines[m.index].strip()}')
        before,after=moves[start].before,moves[stop-1].after
        check(before.mm and before.absolute,'Target must use millimeters and absolute XYZ coordinates.')
        check(None not in (before.x,before.y,before.z,before.f),'Target has unknown starting position/feedrate.')
        for m in moves[start:stop]:
            allowed=m.command in MOTION|MODE_ONLY|{''} or target_preserve(m.command) or (m.command=='G92' and set(m.args)<= {'E'})
            check(allowed,f'Unsupported command at line {m.index+1}: {lines[m.index].strip()}\nRegion #{number}, Z {z:.3f} mm. Original file unchanged. Share the sliced G-code so this command can be handled correctly.')
            if m.command in MOTION:
                permitted=set('XYZEFIJ') if m.command in ('G2','G3') else set('XYZEF')
                # Bambu uses P1 on non-extruding G2/G3 moves for spiral Z-hop.
                if m.command in ('G2','G3') and not m.deposit:permitted.add('P')
                check(set(m.args)<=permitted,f'Unsupported motion parameters at line {m.index+1}: {lines[m.index].strip()}')
            check(m.after.z is not None and m.before.z is not None,f'Line {m.index+1}: target has an unknown Z position.')
            if m.deposit:
                check(abs(m.after.z-z)<.002 and abs(m.before.z-z)<.002,
                      f'Line {m.index+1}: bridge extrusion must remain at Z {z:.5f} mm.')
            else:
                check(z-.002<=m.after.z<=z+5 and z-.002<=m.before.z<=z+5,
                      f'Line {m.index+1}: travel Z-hop exceeds the supported 5 mm range.')
        check(abs(sum(m.de for m in moves[start:stop] if not m.deposit))<.0001,
              f'Region #{number} contains unbalanced retract/unretract moves. Wipe retractions are supported when their matching unretract is inside the same bridge section.')
        flat=flatten_deposits(original)
        pieces.append(dict(number=number,block_start=block_start,start=start,stop=stop,before=before,after=after,dep=original,flat=flat,
                           length=sum(m.length for m in original),extrusion=sum(m.de for m in original)))
    # Never silently combine material/tool switches or different physical layers.
    first,last=pieces[0]['start'],pieces[-1]['stop']
    check(len({p['before'].tool for p in pieces})==1,'Selected regions use different tools. Choose regions for one tool only.')
    check(not any(m.command.startswith('T') or m.command in ('M620','M621','M622','M623','M624','M625') for m in moves[first:last]),
          'Selected regions cross a tool/object/conditional boundary. Choose a smaller same-height selection.')
    dep=[m for p in pieces for m in p['flat']]
    tol=float(cfg.get('geometry_tolerance_mm',.15));check(math.isfinite(tol) and 0<=tol<=.5,'Geometry tolerance must be 0–0.5 mm.')
    for m in dep:
        rmin=point_distance(cx,cy,m);rmax=max(math.hypot(st.x-cx,st.y-cy) for st in (m.before,m.after))
        check(rmin>=ri-tol and rmax<=ro+tol,'Extrusion falls outside the combined ring. Adjust dimensions or use Choose regions to exclude a different object.')
    total_len=sum(p['length'] for p in pieces);area=math.pi*(ro*ro-ri*ri)
    source_e_per_mm=sum(p['extrusion'] for p in pieces)/total_len
    check(.7<=total_len*pitch/area<=1.3,'Combined bridge coverage does not match a full ring at this spacing.')
    probes=max(72,math.ceil(2*math.pi*ro/max(2*pitch,1)))
    check(probes<=4000,'Ring exceeds supported size.')
    for rad in (ri+(ro-ri)*.2,(ri+ro)/2,ri+(ro-ri)*.8):
        for k in range(probes):
            a=2*math.pi*k/probes;px,py=cx+rad*math.cos(a),cy+rad*math.sin(a)
            check(any(point_distance(px,py,m)<=1.5*pitch+tol for m in dep),
                  'The combined selection still has a gap. Include the other bridge regions at this height using Choose regions.')
    for p in pieces:
        rates=[m.de/m.length for m in p['dep']]
        check(min(rates)>0 and max(rates)/min(rates)<1.2,f"Region #{p['number']} has inconsistent extrusion per mm.")
    density=float(cfg.get('spoke_density_percent',100))
    flow=float(cfg.get('bridge_flow_percent',100))/100
    turn_flow=float(cfg.get('turn_flow_percent',100))/100
    turn_speed=float(cfg.get('turn_speed_percent',100))/100
    angle_offset=float(cfg.get('start_angle_offset_deg',0))
    gap_factor=float(cfg.get('max_connected_gap_factor',2))
    travel_segment=float(cfg.get('travel_segment_mm',max(pitch,.2)))
    for value,lo,hi,name in ((density,50,200,'Spoke density'),(flow,.35,2,'Bridge flow'),(turn_flow,.1,2,'Turn flow'),(turn_speed,.1,1,'Turn speed'),(angle_offset,-360,360,'Start angle'),(gap_factor,1,4,'Connected gap'),(travel_segment,.1,5,'Travel segment')):
        check(math.isfinite(value) and lo<=value<=hi,f'{name} is outside the supported range.')
    count=max(12,round(total_len/(ro-ri)*density/100));count+=count%2
    check(count<=30000,'Too many spokes.')
    original_feed=min(m.after.f for p in pieces for m in p['dep'] if m.after.f is not None)
    requested=cfg.get('bridge_speed_mm_s');feed=min(original_feed,float(requested)*60) if requested is not None else original_feed
    source_width=float(cfg.get('source_line_width_mm',.42));target_width=float(cfg.get('bridge_width_mm',source_width))
    check(math.isfinite(source_width) and .1<=source_width<=2 and math.isfinite(target_width) and .1<=target_width<=2,
          'Bridge line width must be 0.1–2.0 mm.')
    width_scale=target_width/source_width
    check(.35<=width_scale<=2.5,'Bridge width adjustment is too large. Keep it between 35% and 250% of the sliced width.')
    pattern=cfg.get('pattern','zigzag')
    check(pattern in ('zigzag','outward','inward'),'Choose Zigzag, Monotonic outward, or Monotonic inward.')
    calibration=bool(cfg.get('calibration_mode',False));cal_range=float(cfg.get('calibration_range_mm',.1));cal_steps=int(cfg.get('calibration_steps',5))
    check(math.isfinite(cal_range) and .01<=cal_range<=.5 and 3<=cal_steps<=9,'Calibration range must be 0.01–0.5 mm with 3–9 sectors.')
    calibration_widths=[target_width-cal_range+2*cal_range*k/(cal_steps-1) for k in range(cal_steps)] if calibration else [target_width]
    check(min(calibration_widths)>=.1 and max(calibration_widths)<=2,'Calibration width range must stay between 0.1 and 2.0 mm.')
    check(min(w/source_width for w in calibration_widths)>=.35 and max(w/source_width for w in calibration_widths)<=2.5,
          'Calibration width range must stay between 35% and 250% of the sliced width.')
    calibration_scale=(sum(calibration_widths[min(cal_steps-1,k*cal_steps//count)]/source_width for k in range(count))/count
                       if calibration else width_scale)
    travel_feed=float(cfg.get('travel_speed_mm_s',100))*60
    retract=float(cfg.get('retract_mm',0));retract_feed=float(cfg.get('retract_speed_mm_s',30))*60
    check(math.isfinite(feed) and 0<feed<=original_feed and math.isfinite(travel_feed) and 0<travel_feed<=18000,'Invalid speed.')
    check(math.isfinite(retract) and 0<=retract<=2 and math.isfinite(retract_feed) and 0<retract_feed<=6000,'Invalid retraction setting.')
    # Calibration always starts at the 3-o'clock/rightmost point so the
    # physical sectors can be identified after printing.
    angle0=(0.0 if calibration else math.atan2(pieces[0]['before'].y-cy,pieces[0]['before'].x-cx))+math.radians(angle_offset)
    assigned=[[] for _ in pieces]
    for k in range(count):
        a=angle0+2*math.pi*k/count;px,py=cx+(ri+ro)/2*math.cos(a),cy+(ri+ro)/2*math.sin(a)
        nearest=min(range(len(pieces)),key=lambda j:min(point_distance(px,py,m) for m in pieces[j]['flat']))
        assigned[nearest].append(a)
    check(all(assigned),'A selected region does not cover any distinct radial area. Choose only the regions of the ring.')
    # Avoid giving a tiny fragment a disproportionately large extrusion allocation.
    for p,angles in zip(pieces,assigned):
        ratio=p['length']/(len(angles)*(ro-ri))*density/100
        check(.65<=ratio<=1.35,f"Region #{p['number']} overlaps another region or has incompatible density. Choose regions belonging to one bridge layer.")
    original_pieces=pieces
    merged=[];merged_angles=[]
    for p,angles in zip(pieces,assigned):
        if merged and joinable_gap(merged[-1],p,lines,moves):
            q=merged[-1]
            q.update(stop=p['stop'],after=p['after'],dep=q['dep']+p['dep'],
                     length=q['length']+p['length'],extrusion=q['extrusion']+p['extrusion'])
            merged_angles[-1]=sorted(merged_angles[-1]+angles)
        else:
            merged.append(dict(p));merged_angles.append(list(angles))
    pieces,assigned=merged,merged_angles
    # A single ring may be split by sparse infill elsewhere at the same Z. When
    # that intervening extrusion does not touch the annulus, print the entire
    # ring first, keep the intervening feature in place, and replace later ring
    # fragments with state-restoring travel only.
    continuous=bool(cfg.get('continuous_pass',True)) and len(pieces)>1 and all(
        gap_clear_of_ring(a,b,lines,moves,cx,cy,ri,ro,tol) for a,b in zip(pieces,pieces[1:]))
    if continuous:
        all_angles=sorted(a for group in assigned for a in group)
        assigned=[all_angles]+[[] for _ in pieces[1:]]
        pieces[0]['output_extrusion']=sum(p['extrusion'] for p in pieces)
        for p in pieces[1:]:p['output_extrusion']=0
    else:
        for p in pieces:p['output_extrusion']=p['extrusion']
    if cfg.get('clockwise',False):
        assigned=[angles[:1]+list(reversed(angles[1:])) for angles in assigned]
    check(not calibration or continuous or len(pieces)==1,
          'Calibration sweep needs one continuous ring pass. Enable continuous pass or choose a ring without intervening features touching the annulus.')
    replacements=[];preserved=[];generated_extrusion=0.;zigzag_connectors=0
    suppressed_source_retractions=0;suppressed_source_zhops=0
    for p,angles in zip(pieces,assigned):
        before,after=p['before'],p['after'];events=[];distance=0
        for m in moves[p['start']:p['stop']]:
            if target_preserve(m.command):
                events.append((distance/p['length'],lines[m.index].rstrip()));preserved.append(m.command)
            elif m.command in MOTION and not m.deposit and abs(m.de)>1e-8:
                # A connected zigzag replaces the sliced path's travel moves,
                # so its old balanced wipe retracts would only add seams.
                if pattern=='zigzag':
                    if m.de<0:suppressed_source_retractions+=1
                else:
                    events.append((distance/p['length'],f'G1 E{m.de:.6f} F{m.after.f:.1f}'))
            if m.command in MOTION and not m.deposit and abs(m.after.z-m.before.z)>1e-8:
                # Likewise, source Z-hops are obsolete while the zigzag remains
                # continuously deposited at the selected bridge height.
                if pattern=='zigzag':
                    if m.after.z>m.before.z:suppressed_source_zhops+=1
                else:
                    events.append((distance/p['length'],f'G1 Z{m.after.z:.5f} F{m.after.f:.1f}'))
            if m.deposit:distance+=m.length
        out=[MARK,f"; Combined region #{p['number']} at Z {z:.5f}",'; FEATURE: Bridge','M83']
        def xy(rad,a):return cx+rad*math.cos(a),cy+rad*math.sin(a)
        def travel(x,y):out.append(f'G1 X{x:.5f} Y{y:.5f} F{travel_feed:.1f}')
        def retract_move(sign):
            if retract:out.append(f'G1 E{sign*retract:.6f} F{retract_feed:.1f}')
        def arc_travel(rad,first,last):
            delta=(last-first+math.pi)%(2*math.pi)-math.pi
            steps=max(1,math.ceil(abs(delta)*rad/travel_segment))
            for k in range(1,steps+1):travel(*xy(rad,first+delta*k/steps))
        def arc_extrude(rad,first,last,width):
            delta=(last-first+math.pi)%(2*math.pi)-math.pi
            # Adjacent spokes get one direct endpoint-to-endpoint turn. This is
            # the actual short zigzag connector and avoids micro-segment noise.
            steps=1
            total=0.;x0,y0=xy(rad,first)
            for step in range(1,steps+1):
                x,y=xy(rad,first+delta*step/steps)
                amount=math.hypot(x-x0,y-y0)*source_e_per_mm*(width/source_width)*flow*turn_flow
                out.append(f'G1 X{x:.5f} Y{y:.5f} E{amount:.6f} F{feed*turn_speed:.1f}')
                total+=round(amount,6);x0,y0=x,y
            return total,steps
        ev=0
        if not angles:
            # A later fragment was moved into the first continuous pass. Keep
            # command timing and restore the exact state expected afterward.
            # This is travel-only cleanup: do not label it as another Bridge or
            # Studio will display a phantom second bridge section/layer.
            # Replace the original feature label too; otherwise Studio keeps
            # categorizing this travel-only cleanup as a second bridge.
            replacements.append((p['block_start'],p['block_start']+1,'; FEATURE: Travel\n'))
            out=[f"; Radial Bridges travel cleanup for region #{p['number']}",'M83']
            while ev<len(events):out.append(events[ev][1]);ev+=1
            a0=math.atan2(before.y-cy,before.x-cx);afinal=math.atan2(after.y-cy,after.x-cx)
            retract_move(-1);travel(*xy(ri,a0));arc_travel(ri,a0,afinal);travel(after.x,after.y);retract_move(1)
            out.extend([f'G92 E{after.e:.8f}','M83' if after.relative_e else 'M82',f'G1 F{after.f:.3f}','; End Radial Bridges travel cleanup'])
            replacements.append((p['start'],p['stop'],'\n'.join(out)+'\n'));continue
        # Stay within the annular travel corridor when changing fragment/sector.
        retract_move(-1)
        astart=math.atan2(before.y-cy,before.x-cx)
        start_rad=ro if pattern=='inward' else ri
        travel(*xy(start_rad,astart));arc_travel(start_rad,astart,angles[0]);retract_move(1)
        emitted=0;rad=start_rad;previous=angles[0]
        spoke_widths=[calibration_widths[min(cal_steps-1,k*cal_steps//len(angles))] for k in range(len(angles))] if calibration else [target_width]*len(angles)
        amounts=[p['output_extrusion']/len(angles)*(w/source_width)*flow*density/100 for w in spoke_widths]
        target_total=sum(amounts);last_sector=-1
        for k,a in enumerate(angles):
            while ev<len(events) and events[ev][0]<=k/len(angles):out.append(events[ev][1]);ev+=1
            if k and pattern=='zigzag':
                gap=abs((a-previous+math.pi)%(2*math.pi)-math.pi)*rad
                if gap<=gap_factor*pitch:
                    connector_e,connector_segments=arc_extrude(rad,previous,a,(spoke_widths[k-1]+spoke_widths[k])/2)
                    generated_extrusion+=connector_e;zigzag_connectors+=connector_segments
                else:
                    retract_move(-1);arc_travel(rad,previous,a);retract_move(1)
            elif k:
                retract_move(-1);arc_travel(rad,previous,a)
                target_start=ri if pattern=='outward' else ro
                travel(*xy(target_start,a));retract_move(1);rad=target_start
            if calibration:
                sector=min(cal_steps-1,k*cal_steps//len(angles))
                if sector!=last_sector:
                    out.append(f'; CALIBRATION SECTOR {sector+1}/{cal_steps} WIDTH {spoke_widths[k]:.5f} FLOW {100*spoke_widths[k]/source_width:.1f}%')
                    last_sector=sector
            rad=(ro if k%2==0 else ri) if pattern=='zigzag' else (ro if pattern=='outward' else ri)
            x,y=xy(rad,a)
            amount=round(amounts[k],6) if k<len(angles)-1 else round(target_total-emitted,6)
            emitted+=amount;generated_extrusion+=amount
            out.append(f'G1 X{x:.5f} Y{y:.5f} E{amount:.6f} F{feed:.1f}');previous=a
        while ev<len(events):out.append(events[ev][1]);ev+=1
        retract_move(-1)
        afinal=math.atan2(after.y-cy,after.x-cx)
        arc_travel(rad,previous,afinal);travel(after.x,after.y);retract_move(1)
        out.extend([f'G92 E{after.e:.8f}','M83' if after.relative_e else 'M82',f'G1 F{after.f:.3f}','; END_RADIAL_BRIDGES_V1'])
        replacements.append((p['start'],p['stop'],'\n'.join(out)+'\n'))
    # Each replacement restores its exit state. Gaps containing other printed
    # features or unsupported commands remain byte-for-byte intact.
    chunks=[];cursor=0
    for start,stop,replacement in replacements:
        chunks.extend([''.join(lines[cursor:start]),replacement]);cursor=stop
    chunks.append(''.join(lines[cursor:]))
    report=dict(block=ids[0],blocks=ids,combined_regions=len(ids),replaced_lines=[first+1,last],
                replaced_ranges=[[p['start']+1,p['stop']] for p in pieces],z_mm=z,spokes=count,
                output_sections=(1 if continuous else len(pieces)),joined_regions=len(original_pieces)-(1 if continuous else len(pieces)),
                section_note=('One continuous circular pass.' if len(pieces)==1 or continuous else
                    f'{len(pieces)} passes at Z {z:.5f} mm. Other printed features or incompatible commands separate them; their order is preserved.'),
                radial_span_mm=round(ro-ri,4),old_longest_span_mm=round(max(m.length for p in pieces for m in p['dep']),4),
                extrusion_mm=round(generated_extrusion,6),original_extrusion_mm=round(sum(p['extrusion'] for p in pieces),6),
                source_line_width_mm=round(source_width,4),bridge_width_mm=round(target_width,4),flow_percent=round(width_scale*flow*100,1),pattern=pattern,
                spoke_density_percent=density,turn_flow_percent=turn_flow*100,turn_speed_percent=turn_speed*100,
                calibration_mode=calibration,calibration_widths_mm=[round(w,4) for w in calibration_widths],
                zigzag_connectors=zigzag_connectors,suppressed_source_retractions=suppressed_source_retractions,
                suppressed_source_zhops=suppressed_source_zhops,
                inner_spacing_mm=round(2*math.pi*ri/count,4),
                outer_spacing_mm=round(2*math.pi*ro/count,4),bridge_speed_mm_s=feed/60,
                preserved_commands=sorted(set(preserved)))
    return ''.join(chunks),report

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('gcode', type=Path, help='Plain text G-code; Bambu Studio appends this filename to its hook command')
    ap.add_argument('--inspect', action='store_true', help='List bridge block IDs, Z and XY bounds; make no edits')
    ap.add_argument('--config', type=Path)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--in-place', action='store_true', help='For Bambu post-processing hook; retain a .radial-original.bak file')
    a = ap.parse_args()
    try:
        raw = a.gcode.read_bytes()
        check(not raw.startswith(b'PK'), 'Input is a 3MF/ZIP. Export plain G-code or extract Metadata/plate_N.gcode first.')
        text = raw.decode('utf-8-sig')
        check('\x00' not in text, 'Binary G-code is unsupported.')
        if a.inspect:
            print(json.dumps(inspect(text),indent=2)); return
        check(a.config is not None, 'Supply --config ring.json, or use --inspect.')
        check(not (a.in_place and a.output), 'Choose --output OR --in-place.')
        cfg = json.loads(a.config.read_text(encoding='utf-8-sig'))
        output, report = rewrite(text, cfg)
        dest = a.gcode if a.in_place else (a.output or a.gcode.with_name(a.gcode.stem+'.radial.gcode'))
        check(a.in_place or dest.resolve()!=a.gcode.resolve(), 'Use --in-place to replace input.')
        if a.in_place:
            backup = a.gcode.with_name(a.gcode.name+'.radial-original.bak')
            with backup.open('xb') as f:
                f.write(raw)
        else:
            check(not dest.exists(), 'Output already exists; choose a new output path.')
        fd, temp = tempfile.mkstemp(prefix='.radial-',dir=dest.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as f:
                f.write(output)
            os.replace(temp,dest)
        finally:
            if os.path.exists(temp): os.unlink(temp)
        print(json.dumps(dict(output=str(dest),**report),indent=2))
    except (ValueError, OSError, UnicodeError, TypeError, KeyError, OverflowError) as ex:
        print(f'Radial bridges: {ex}',file=sys.stderr)
        sys.exit(2)

if __name__ == '__main__':
    main()
