import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import backend as b
from test_radial_bridges import sample,CFG

class BackendTests(unittest.TestCase):
    def test_selected_subset_profile(self):
        from test_grouping import split_sample
        group=b.analyze(split_sample())[0]
        selected=b.combine_members([group['members'][0]])
        selected['members']=group['members']
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'LOCALAPPDATA':td}):
            p=b.save_profile(selected['cfg'],selected,'synthetic')
            target=json.loads(p.read_text())['targets'][0]
            self.assertEqual(target['member_signatures'],[group['members'][0]['signature']])
    def test_conflicting_multi_height_targets(self):
        cfg=b.analyze(sample())[0]['cfg']
        with self.assertRaises(b.Refusal):b.convert_many(sample(),[cfg,cfg])
        with self.assertRaises(b.Refusal):b.convert_many(sample(),[dict(cfg,blocks=[1,4]),dict(cfg,blocks=[2,3],z_mm=3)])
        out,_,_=b.convert(sample(),cfg)
        with self.assertRaises(b.Refusal):b.convert_many(out,[cfg])
    def test_estimates_and_conversion(self):
        text=sample().replace('; FEATURE: Bridge','; FEATURE: Bridge\n; LINE_WIDTH: 0.420318',1);r=b.analyze(text)[0]
        self.assertTrue(r['plausible'])
        self.assertAlmostEqual(r['cfg']['center_x_mm'],30,places=3)
        self.assertAlmostEqual(r['cfg']['center_y_mm'],30,places=3)
        self.assertAlmostEqual(r['cfg']['inner_radius_mm'],10,places=3)
        self.assertAlmostEqual(r['cfg']['outer_radius_mm'],12,places=3)
        self.assertAlmostEqual(r['cfg']['source_line_width_mm'],.420318,places=5)
        self.assertAlmostEqual(r['cfg']['bridge_width_mm'],.420318,places=5)
        result,report,lines=b.convert(text,r['cfg'])
        self.assertEqual(len(lines),report['spokes']+report['zigzag_connectors'])
    def test_3mf_read_and_original_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.gcode.3mf'
            with zipfile.ZipFile(p,'w') as z:z.writestr('Metadata/plate_1.gcode',sample());z.writestr('Metadata/plate_2.gcode',sample(False))
            before=p.read_bytes()
            self.assertEqual(len(b.plate_names(p)),2)
            self.assertEqual(b.read_input(p,'Metadata/plate_2.gcode'),sample(False))
            self.assertEqual(p.read_bytes(),before)
    def test_hook_profile_and_backup(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'LOCALAPPDATA':td}):
            src=sample();r=b.analyze(src)[0]
            profile=b.save_profile(CFG,r,'test')
            p=Path(td)/'export.gcode';p.write_text('; timestamp changed\n'+src)
            original=p.read_bytes()
            report=b.hook(profile,p)
            self.assertEqual(Path(report['backup']).read_bytes(),original)
            self.assertIn(b.MARK,p.read_text())
            p.write_text(src.replace('Z2','Z3'))
            before=p.read_bytes()
            with self.assertRaises(b.Refusal):b.hook(profile,p)
            self.assertEqual(before,p.read_bytes())
    def test_zip_with_no_gcode(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'a.3mf'
            with zipfile.ZipFile(p,'w') as z:z.writestr('3D/3dmodel.model','example')
            with self.assertRaises(b.Refusal):b.read_input(p)
    def test_multiple_heights_convert_and_hook(self):
        src=sample()+sample().replace('Z2','Z3')
        groups=b.analyze(src)
        self.assertEqual([r['z'] for r in groups],[2,3])
        modified,reports,previews=b.convert_many(src,[r['cfg'] for r in groups])
        self.assertEqual(modified.count(b.MARK),2)
        self.assertEqual([r['z_mm'] for r in reports],[2,3])
        self.assertTrue(all(previews))
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'LOCALAPPDATA':td}):
            profile=b.save_profiles([(r['cfg'],r) for r in groups],'multi-height test')
            p=Path(td)/'multi.gcode';p.write_text(src)
            report=b.hook(profile,p)
            self.assertEqual(p.read_text().count(b.MARK),2)
            self.assertEqual(report['converted_heights_mm'],[2,3])
    def test_fine_tuning(self):
        src=sample();cfg=b.analyze(src)[0]['cfg']
        _,base,_=b.convert(src,cfg)
        out,tuned,lines=b.convert(src,dict(cfg,bridge_flow_percent=120,turn_flow_percent=50,turn_speed_percent=50,spoke_density_percent=150,start_angle_offset_deg=30,clockwise=True,travel_speed_mm_s=80,retract_speed_mm_s=25,travel_segment_mm=.3))
        self.assertAlmostEqual(tuned['spokes']/base['spokes'],1.5,delta=.03)
        self.assertEqual(tuned['flow_percent'],120)
        self.assertEqual(tuned['turn_flow_percent'],50)
        self.assertEqual(tuned['turn_speed_percent'],50)
        self.assertIn('F4800.0',out)
        self.assertTrue(lines)
        for key,value in [('bridge_flow_percent',0),('spoke_density_percent',201),('turn_speed_percent',110),('travel_segment_mm',0)]:
            with self.assertRaises(b.Refusal):b.convert(src,dict(cfg,**{key:value}))

if __name__=='__main__':unittest.main()
