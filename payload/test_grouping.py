import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import backend as b
from radial_bridges import parse, rewrite, MARK, Refusal
from test_radial_bridges import sample,CFG

GAP='; FEATURE: Inner wall\n; UNRELATED_WALL_KEEP\nG1 X30 Y30 F5000\nG1 X31 Y30 E0.04 F1200\nM106 P2 S80\n; FEATURE: Bridge\n'

def radial_segments(segs,report):
    return [s for s in segs if math.hypot(s[2]-s[0],s[3]-s[1])>.8*report['radial_span_mm']]

def assert_adjusted_extrusion(test,src,out,report):
    old=sum(m.de for m in parse(src.splitlines()) if m.deposit)
    new=sum(m.de for m in parse(out.splitlines()) if m.deposit)
    test.assertAlmostEqual(new,old-report['original_extrusion_mm']+report['extrusion_mm'],places=5)

def split_sample():
    s=sample()
    ls=s.splitlines(keepends=True)
    split=next(i for i,l in enumerate(ls) if l.startswith('G1 X') and 'Y30.200000' in l)
    ls.insert(split,GAP)
    halfway=next(i for i,l in enumerate(ls) if 'Y24.200000' in l)
    ls.insert(halfway,'M106 P1 S200\nM400\nG92 E0\nM83\nM900 K0.02\n')
    return ''.join(ls)

def absolute_version(text):
    out=[];e=0
    for line in text.splitlines():
        from radial_bridges import command
        cmd,a=command(line)
        if cmd=='M83':out.append('M82');continue
        if cmd=='G92' and 'E' in a:e=a['E']
        if cmd in ('G0','G1') and 'E' in a:
            import re
            e+=a['E'];line=re.sub(r'E[-+0-9.]+',f'E{e:.8f}',line)
        out.append(line)
    return '\n'.join(out)+'\n'

class GroupTests(unittest.TestCase):
    def test_join_travel_only_sections_into_single_circle(self):
        gap='; FEATURE: Travel\nG1 E-0.6 F1800\nG1 Z2.4 F600\nG1 X30 Y30 F5000\nM106 P2 S80\nG1 Z2 F600\nG1 E0.6 F1800\n; CHANGE_LAYER\n; Z_HEIGHT: 2\n; FEATURE: Bridge\n'
        for src in (split_sample().replace(GAP,gap),absolute_version(split_sample().replace(GAP,gap))):
            r=b.analyze(src)[0];out,report,segs=b.convert(src,r['cfg'])
            self.assertEqual(report['combined_regions'],2)
            self.assertEqual(report['output_sections'],1)
            self.assertEqual(report['joined_regions'],1)
            self.assertEqual(out.count(MARK),1)
            self.assertNotIn('G1 Z2.40000',out)
            self.assertEqual(report['suppressed_source_retractions'],1)
            self.assertEqual(report['suppressed_source_zhops'],1)
            self.assertNotIn('; CHANGE_LAYER',out)
            self.assertEqual(len(segs),report['spokes']+report['zigzag_connectors'])
            old=parse(src.splitlines());new=parse(out.splitlines())
            assert_adjusted_extrusion(self,src,out,report)
            for key in ('x','y','z','e','f','relative_e','plane','incremental_arc'):
                a,c=getattr(old[-1].after,key),getattr(new[-1].after,key)
                if isinstance(a,float):self.assertAlmostEqual(a,c,places=6)
                else:self.assertEqual(a,c)
            # Spokes advance all the way around in a single angular sequence.
            spokes=radial_segments(segs,report);self.assertEqual(len(spokes),report['spokes'])
            angles=[math.atan2((ya+yb)/2-30,(xa+xb)/2-30) for xa,ya,xb,yb in spokes]
            steps=[(c-a)%(2*math.pi) for a,c in zip(angles,angles[1:]+angles[:1])]
            for step in steps:self.assertAlmostEqual(step,2*math.pi/len(spokes),places=5)
            self.assertEqual(out.count('M106 P2 S80'),1)
            self.assertTrue(all(abs(m.after.z-2)<1e-8 for m in new if m.deposit))
    def test_incompatible_gap_keeps_separate_passes(self):
        for gap in ('; FEATURE: Travel\nM104 S210\n; FEATURE: Bridge\n',
                    '; OBJECT_ID: 2\n; FEATURE: Bridge\n',
                    '; FEATURE: Travel\nG1 E0.5\n; FEATURE: Bridge\n'):
            src=split_sample().replace(GAP,gap)
            out,report,_=b.convert(src,b.analyze(src)[0]['cfg'])
            self.assertEqual(report['output_sections'],2)
            self.assertIn(gap,out)
            self.assertIn('order is preserved',report['section_note'])
    def test_inner_feature_becomes_one_pass_and_patterns_and_width(self):
        src=split_sample();region=b.analyze(src)[0]
        original_total=sum(m.de for m in parse(src.splitlines()) if m.deposit)
        source_bridge_e=sum(m.de for m in region['_dep']);unrelated_e=original_total-source_bridge_e
        for pattern in ('zigzag','outward','inward'):
            cfg=dict(region['cfg'],pattern=pattern,bridge_width_mm=.55,source_line_width_mm=.42)
            out,report,segs=b.convert(src,cfg)
            self.assertEqual(report['output_sections'],1)
            self.assertEqual(report['pattern'],pattern)
            self.assertAlmostEqual(report['flow_percent'],100*.55/.42,places=1)
            self.assertIn('; UNRELATED_WALL_KEEP',out)
            self.assertEqual(len(segs),report['spokes']+report['zigzag_connectors'])
            bridge_e=sum(m.de for m in parse(out.splitlines()) if m.deposit)-unrelated_e
            self.assertAlmostEqual(bridge_e,report['extrusion_mm'],places=5)
            if pattern=='zigzag':self.assertGreater(bridge_e,source_bridge_e*.55/.42)
            else:self.assertAlmostEqual(bridge_e,source_bridge_e*.55/.42,places=4)
            radii=[]
            spokes=radial_segments(segs,report);self.assertEqual(len(spokes),report['spokes'])
            for xa,ya,xb,yb in spokes:
                radii.append((math.hypot(xa-30,ya-30),math.hypot(xb-30,yb-30)))
            if pattern=='outward':self.assertTrue(all(a<b for a,b in radii))
            elif pattern=='inward':self.assertTrue(all(a>b for a,b in radii))
            else:self.assertTrue(all((a<b)==(i%2==0) for i,(a,b) in enumerate(radii)))
    def test_two_regions_auto_group_and_preserve_gaps(self):
        for src in (split_sample(),absolute_version(split_sample())):
            rs=b.analyze(src)
            self.assertEqual(len(rs),1);self.assertEqual(rs[0]['numbers'],[1,2])
            out,report,segs=b.convert(src,rs[0]['cfg'])
            self.assertEqual(report['combined_regions'],2);self.assertEqual(len(segs),report['spokes']+report['zigzag_connectors'])
            old=parse(src.splitlines());new=parse(out.splitlines())
            for key in ('x','y','z','e','f','relative_e'):
                self.assertAlmostEqual(getattr(old[-1].after,key),getattr(new[-1].after,key),places=6)
            assert_adjusted_extrusion(self,src,out,report)
            a,bound=report['replaced_ranges']
            gap=''.join(src.splitlines(keepends=True)[a[1]:bound[0]-1])
            self.assertIn('; UNRELATED_WALL_KEEP',gap)
            self.assertIn('; UNRELATED_WALL_KEEP',out)
            for cmd in ('M106 P1 S200','M400','M900 K0.02'):self.assertEqual(out.count(cmd),src.count(cmd))
            self.assertEqual(out.count(MARK),1)
            self.assertIn('; Radial Bridges travel cleanup for region #2',out)
            self.assertNotIn('; FEATURE: Bridge\n; Radial Bridges travel cleanup',out)
    def test_manual_subset_and_different_heights(self):
        r=b.analyze(split_sample())[0]
        only=b.combine_members([r['members'][0]])
        self.assertEqual(only['numbers'],[1])
        with self.assertRaises(Refusal):b.convert(split_sample(),only['cfg'])
        src=sample()+sample().replace('Z2','Z3')
        groups=b.analyze(src)
        self.assertEqual(len(groups),2)
        with self.assertRaisesRegex(Refusal,'same Z'):b.combine_members([groups[0]['members'][0],groups[1]['members'][0]])
    def test_exact_error(self):
        src=sample().replace('Y24.200000 F6000','Y24.200000 F6000\nG123 X1')
        self.assertIn('G123',src)
        with self.assertRaisesRegex(Refusal,r'line \d+: G123 X1'):rewrite(src,CFG)
    def test_full_circle_ij_arcs(self):
        ls=['G21','G90','G17','M83','G1 X40.2 Y30 Z2 F6000','; FEATURE: Bridge']
        for k in range(5):
            r=10.2+k*.4
            ls.extend([f'G1 X{30+r} Y30 F6000',f'G3 X{30+r} Y30 I{-r} J0 E{2*math.pi*r*.04} F1500'])
        ls.extend(['; FEATURE: Outer wall','G1 X45 Y30 F3000'])
        src='\n'.join(ls)+'\n';region=b.analyze(src)[0]
        out,report,segs=b.convert(src,region['cfg'])
        self.assertEqual(len(segs),report['spokes']+report['zigzag_connectors'])
        self.assertNotIn('G3 ',out)
        assert_adjusted_extrusion(self,src,out,report)
    def test_group_profile_hook(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'LOCALAPPDATA':td}):
            src=split_sample();r=b.analyze(src)[0]
            profile=b.save_profile(r['cfg'],r,'test');p=Path(td)/'test.gcode';p.write_text(src)
            report=b.hook(profile,p)
            self.assertEqual(report['combined_regions'],2)
            self.assertEqual(Path(report['backup']).read_text(),src)
            self.assertEqual(p.read_text().count(MARK),1)

if __name__=='__main__':unittest.main()
