import math
import unittest
from radial_bridges import rewrite, inspect, parse, Refusal, MARK

CFG = dict(block=1,z_mm=2,center_x_mm=30,center_y_mm=30,inner_radius_mm=10,outer_radius_mm=12,pitch_mm=.4)

def sample(relative=True):
    out=['G21','G90','M83' if relative else 'M82','G92 E0','G1 X0 Y0 Z2 F6000','; FEATURE: Bridge','M204 S1000']
    ev=0
    def extrusion(v):
        nonlocal ev
        ev+=v
        return v if relative else ev
    y=-11.8
    while y<12:
        ox=math.sqrt(144-y*y)
        ranges=[(-ox,ox)]
        if abs(y)<10:
            ix=math.sqrt(100-y*y)
            ranges=[(-ox,-ix),(ix,ox)]
        for left,right in ranges:
            out.extend([f'G1 X{30+left:.6f} Y{30+y:.6f} F6000',f'G1 X{30+right:.6f} E{extrusion((right-left)*.04):.8f} F1500'])
        y+=.4
    out.extend(['; FEATURE: Outer wall','G1 X50 Y50 F6000',f'G1 X51 E{extrusion(.04):.8f} F1800'])
    return '\n'.join(out)+'\n'

class Tests(unittest.TestCase):
    def test_unknown_state_commands_refused(self):
        for cmd in ('M206 X2','M620.10','M999','G10','G11'):
            src=sample().replace('M204 S1000','M204 S1000\n'+cmd)
            with self.assertRaises(Refusal):rewrite(src,CFG)
    def test_clockwise_first_spoke_and_direction(self):
        import backend as b
        _,_,ccw=b.convert(sample(),CFG)
        _,_,cw=b.convert(sample(),CFG|{'clockwise':True})
        spokes=lambda lines:[p for p in lines if math.hypot(p[2]-p[0],p[3]-p[1])>1.5]
        a,c=spokes(ccw),spokes(cw)
        for x,y in zip(a[0],c[0]):self.assertAlmostEqual(x,y,places=4)
        angles=lambda paths:[math.atan2((p[1]+p[3])/2-30,(p[0]+p[2])/2-30) for p in paths[:2]]
        x,y=angles(a);u,v=angles(c)
        self.assertGreater((y-x+math.pi)%(2*math.pi)-math.pi,0)
        self.assertLess((v-u+math.pi)%(2*math.pi)-math.pi,0)
    def test_relative_and_absolute_state_and_extrusion(self):
        for rel in (True,False):
            src=sample(rel)
            dst,r=rewrite(src,CFG)
            original=parse(src.splitlines())
            changed=parse(dst.splitlines())
            a,b=original[-1].after,changed[-1].after
            for attr in ('x','y','z','e','f','absolute','relative_e','mm'):
                self.assertAlmostEqual(getattr(a,attr),getattr(b,attr),places=6)
            self.assertEqual(len(inspect(src)),1)
            self.assertAlmostEqual(sum(m.de for m in changed if m.deposit),
                                   sum(m.de for m in original if m.deposit)-r['original_extrusion_mm']+r['extrusion_mm'],places=5)
            self.assertGreater(r['old_longest_span_mm'],r['radial_span_mm']*2)
            inside=False
            spokes=[]
            for line,m in zip(dst.splitlines(),changed):
                if line==MARK: inside=True
                if line=='; END_RADIAL_BRIDGES_V1': inside=False
                if inside and m.deposit:
                    if m.length>1.5:
                        spokes.append(m)
                        self.assertAlmostEqual(m.length,2,places=4)
                        ax,ay=m.before.x-30,m.before.y-30
                        bx,by=m.after.x-30,m.after.y-30
                        self.assertAlmostEqual(ax*by-ay*bx,0,places=3)
            self.assertEqual(len(spokes),r['spokes'])
            self.assertEqual(r['zigzag_connectors'],r['spokes']-1)
            start,stop=r['replaced_lines']
            self.assertTrue(dst.startswith(''.join(src.splitlines(keepends=True)[:start-1])))
            self.assertTrue(dst.endswith(''.join(src.splitlines(keepends=True)[stop:])))
    def test_wrong_geometry_z_block(self):
        for extra in ({'center_x_mm':31},{'z_mm':3},{'block':2},{'outer_radius_mm':15},{'inner_radius_mm':5},{'pitch_mm':None}):
            with self.assertRaises(Refusal): rewrite(sample(),CFG|extra)
    def test_repeat(self):
        out,_=rewrite(sample(),CFG)
        with self.assertRaises(Refusal): rewrite(out,CFG)
    def test_arc_and_unbalanced_retract(self):
        src=sample()
        for insert in ('G2 X30 Y30 I1 J1 E.1','G1 E-.8','M106 S200','G1 Z2.2'):
            altered=src.replace('; FEATURE: Outer wall',insert+'\nG1 X41 Y30 E.01\n; FEATURE: Outer wall')
            with self.assertRaises(Refusal): rewrite(altered,CFG)
    def test_missing_sector(self):
        src=sample()
        ls=src.splitlines()
        # Remove whole positive-Y half, retaining a syntactically valid partial bridge.
        cut=next(i for i,l in enumerate(ls) if l.startswith('G1 X') and 'Y30.200000' in l)
        src='\n'.join(ls[:cut]+['; FEATURE: Outer wall','G1 X50 Y50 F6000'])+'\n'
        with self.assertRaises(Refusal): rewrite(src,CFG)
    def test_configured_retraction_balances(self):
        dst,_=rewrite(sample(),CFG|{'retract_mm':.6})
        self.assertAlmostEqual(parse(dst.splitlines())[-1].after.e,parse(sample().splitlines())[-1].after.e,places=6)
    def test_zigzag_suppresses_source_wipe_and_keeps_safe_mcode(self):
        ls=sample().splitlines()
        idx=next(i for i,line in enumerate(ls) if i>15 and line.startswith('G1 X') and 'F6000' in line and ' E' not in line)
        ls[idx:idx]=['M991 S0 P-1','G1 X30 Y30 E-.2 F1800','G1 E.2 F1800']
        src='\n'.join(ls)+'\n';dst,report=rewrite(src,CFG)
        self.assertIn('M991 S0 P-1',dst)
        self.assertNotIn('X30 Y30 E-.2',dst)
        self.assertNotIn('G1 E-0.200000 F1800.0',dst)
        self.assertNotIn('G1 E0.200000 F1800.0',dst)
        self.assertEqual(report['suppressed_source_retractions'],1)
        self.assertEqual(report['zigzag_connectors'],report['spokes']-1)
        self.assertIn('M991',report['preserved_commands'])
        self.assertAlmostEqual(parse(src.splitlines())[-1].after.e,parse(dst.splitlines())[-1].after.e,places=6)
    def test_calibration_width_sweep(self):
        cfg=CFG|{'source_line_width_mm':.42,'bridge_width_mm':.55,'calibration_mode':True,'calibration_range_mm':.1,'calibration_steps':5}
        dst,report=rewrite(sample(),cfg)
        self.assertEqual(report['calibration_widths_mm'],[.45,.5,.55,.6,.65])
        self.assertEqual(dst.count('; CALIBRATION SECTOR '),5)
        for width in report['calibration_widths_mm']:
            self.assertIn(f'WIDTH {width:.5f}',dst)
        self.assertTrue(report['calibration_mode'])
    def test_bambu_spiral_z_hop_p1(self):
        ls=sample().splitlines()
        idx=next(i for i,line in enumerate(ls) if i>15 and line.startswith('G1 X') and 'F6000' in line and ' E' not in line)
        ls[idx:idx]=['G3 Z2.4 I1.068 J-.583 P1 F30000','G1 X31 Y30 Z2.4 F30000','G1 Z2 F30000']
        src='\n'.join(ls)+'\n';dst,report=rewrite(src,CFG)
        self.assertNotIn('G3 Z2.4',dst)
        self.assertNotIn('G1 Z2.40000 F30000.0',dst)
        self.assertEqual(report['suppressed_source_zhops'],1)
        changed=parse(dst.splitlines())
        self.assertTrue(all(abs(m.after.z-2)<1e-8 for m in changed if m.deposit))
        self.assertAlmostEqual(parse(src.splitlines())[-1].after.e,changed[-1].after.e,places=6)

if __name__=='__main__': unittest.main()
