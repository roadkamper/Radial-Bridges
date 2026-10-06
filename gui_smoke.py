import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'payload'))
from PySide6.QtWidgets import QApplication,QFileDialog,QPushButton
from PySide6.QtCore import QTimer,QPointF,QPoint,Qt
from PySide6.QtGui import QWheelEvent,QMouseEvent
from PySide6.QtTest import QTest
import app
from test_grouping import split_sample as sample

with tempfile.TemporaryDirectory() as td:
    os.environ['LOCALAPPDATA']=td
    p=Path(td);source=p/'sample.gcode';source_text=sample()+sample().replace('Z2','Z3');source.write_text(source_text);output=p/'converted.gcode';fake=p/'bambu-studio.exe';fake.touch()
    errors=[];stage=[0];attempts=[0]
    class Smoke(QApplication):
        def exec(self):
            def poll():
                try:
                    attempts[0]+=1
                    if attempts[0]>200:raise AssertionError('GUI timed out')
                    w=next(v for v in self.topLevelWidgets() if v.windowTitle()=='Radial Bridges')
                    assert self.applicationName()=='Radial Bridges'
                    assert self.applicationDisplayName()=='Radial Bridges'
                    assert not self.windowIcon().isNull()
                    if w.jobs:QTimer.singleShot(30,poll);return
                    if stage[0]==0:
                        assert w.previewbtn.text()=='Generate Radial Bridge Preview'
                        assert all(field.toolTip() for field in w.fields.values())
                        assert w.combo.toolTip() and w.pattern.toolTip() and w.continuous.toolTip()
                        assert w.calibration.toolTip() and w.calrange.toolTip() and w.calsteps.toolTip()
                        assert len(w.fine_fields)==11 and all(x.toolTip() for x in w.fine_fields.values())
                        w.load_file(str(source));stage[0]=1
                    elif stage[0]==1:
                        assert len(w.regions)==2
                        assert w.region()["numbers"]==[1,2]
                        w.fields['bridge_width_mm'].setValue(.55)
                        w.pattern.setCurrentIndex(w.pattern.findData('zigzag'))
                        w.continuous.setChecked(True)
                        w.calibration.setChecked(True);w.calrange.setValue(.1);w.calsteps.setValue(5)
                        w.preview();stage[0]=2
                    elif stage[0]==2:
                        assert len(w.preview_cache)==1 and w.combo.itemText(0).startswith('✓')
                        assert w.report['pattern']=='zigzag' and w.report['output_sections']==1
                        assert w.report['zigzag_connectors']==w.report['spokes']-1
                        assert abs(w.report['bridge_width_mm']-.55)<1e-8 and w.report['flow_percent']==131.0
                        assert w.report['calibration_mode'] and w.report['calibration_widths_mm']==[.45,.5,.55,.6,.65]
                        w._smoke_first=(list(w.after.lines),w.fields['bridge_width_mm'].value(),w.pattern.currentData(),w.calibration.isChecked())
                        w.combo.setCurrentIndex(1)
                        assert not w.after.lines and len(w.preview_cache)==1
                        w.fields['bridge_width_mm'].setValue(.50);w.pattern.setCurrentIndex(w.pattern.findData('outward'));w.calibration.setChecked(False)
                        w.fine_fields['bridge_flow_percent'].setValue(110);w.clockwise.setChecked(True)
                        w.preview();stage[0]=3
                    else:
                        assert len(w.preview_cache)==2 and w.combo.itemText(0).startswith('✓') and w.combo.itemText(1).startswith('✓')
                        assert w.converted.count('; RADIAL_BRIDGES_V1')==2
                        assert w.report['pattern']=='outward' and abs(w.report['bridge_width_mm']-.50)<1e-8
                        w.combo.setCurrentIndex(0)
                        assert w.after.lines==w._smoke_first[0]
                        assert w.fields['bridge_width_mm'].value()==w._smoke_first[1]
                        assert w.pattern.currentData()==w._smoke_first[2] and w.calibration.isChecked()==w._smoke_first[3]
                        assert w.fine_fields['bridge_flow_percent'].value()==100 and not w.clockwise.isChecked()
                        assets=Path(__file__).parent/'docs/assets'
                        if assets.exists():
                            from PySide6.QtWidgets import QScrollArea
                            w.grab().save(str(assets/'app-preview.png'))
                            scroll=w.findChild(QScrollArea);scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum());self.processEvents()
                            w.grab().save(str(assets/'fine-tuning.png'))
                            scroll.verticalScrollBar().setValue(0);self.processEvents()
                        assert w.converted and w.savebtn.isEnabled() and w.hookbtn.isEnabled()
                        assert w.report['pattern']=='zigzag' and w.report['output_sections']==1
                        assert w.report['zigzag_connectors']==w.report['spokes']-1
                        assert abs(w.report['bridge_width_mm']-.55)<1e-8 and w.report['flow_percent']==131.0
                        assert w.report['calibration_mode'] and w.report['calibration_widths_mm']==[.45,.5,.55,.6,.65]
                        for canvas in (w.before,w.after):
                            anchor=QPointF((canvas.plot_rect().center()+QPointF(35,25)).toPoint())
                            before=(anchor-canvas.plot_rect().center()-canvas.pan)/canvas.zoom
                            wheel=QWheelEvent(anchor,canvas.mapToGlobal(anchor.toPoint()),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
                            self.sendEvent(canvas,wheel)
                            assert canvas.zoom>1
                            after=(anchor-canvas.plot_rect().center()-canvas.pan)/canvas.zoom
                            assert (after-before).manhattanLength()<1e-6,'Zoom must stay anchored to the cursor'
                            pan=QPointF(canvas.pan)
                            QTest.mousePress(canvas,Qt.LeftButton,pos=anchor.toPoint())
                            self.sendEvent(canvas,QMouseEvent(QMouseEvent.MouseMove,anchor+QPointF(20,15),canvas.mapToGlobal((anchor+QPointF(20,15)).toPoint()),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
                            QTest.mouseRelease(canvas,Qt.LeftButton,pos=(anchor+QPointF(20,15)).toPoint())
                            assert (canvas.pan-pan-QPointF(20,15)).manhattanLength()<1e-6
                            next(x for x in canvas.findChildren(QPushButton) if x.text()=='Fit').click()
                            assert canvas.zoom==1 and canvas.pan==QPointF()
                            next(x for x in canvas.findChildren(QPushButton) if x.text()=='+').click()
                            assert canvas.zoom>1
                            QTest.mouseDClick(canvas,Qt.LeftButton,pos=anchor.toPoint())
                            assert canvas.zoom==1 and canvas.pan==QPointF()
                        w.after.zoom_at(2.5,QPointF(w.after.plot_rect().right()-24,w.after.plot_rect().center().y()))
                        w.grab().save(str(Path(__file__).parent/'ui-v1.5.png'))
                        with patch.object(QFileDialog,'getSaveFileName',return_value=(str(output),'G-code')):w.save_output()
                        assert output.is_file() and output.read_text().count('; RADIAL_BRIDGES_V1')==2 and w.bambubtn.isEnabled()
                        w.bambu=str(fake)
                        with patch('backend.launch_bambu') as launch:
                            w.open_bambu();launch.assert_called_once_with(str(fake),output)
                        def dialog_action():
                            d=self.activeModalWidget()
                            buttons=d.findChildren(QPushButton)
                            next(x for x in buttons if x.text()=='Copy command').click()
                            assert '--hook --profile' in self.clipboard().text()
                            d.accept()
                        QTimer.singleShot(100,dialog_action)
                        w.integration()
                        profiles=list((p/'Radial Bridges/profiles').glob('*.json'));assert profiles
                        import json
                        assert len(json.loads(profiles[-1].read_text())['targets'])==2
                        assert source.read_text()==source_text
                        w.fields['center_x_mm'].setValue(31)
                        assert not w.savebtn.isEnabled() and not w.hookbtn.isEnabled()
                        def select_one():
                            from PySide6.QtWidgets import QCheckBox
                            d=self.activeModalWidget();checks=d.findChildren(QCheckBox);assert len(checks)==2;checks[1].setChecked(False);d.accept()
                        QTimer.singleShot(100,select_one);w.choose_regions();assert w.region()['numbers']==[1]
                        canvas=w.before;canvas.zoom_at(1.6);old_zoom=canvas.zoom;old_pan=QPointF(canvas.pan)
                        member=canvas.region_members[1]
                        line=next(line for line in member['segments'] if canvas.plot_rect().contains(canvas.screen_point((line[0]+line[2])/2,(line[1]+line[3])/2)) and canvas.hit_region(QPointF(canvas.screen_point((line[0]+line[2])/2,(line[1]+line[3])/2).toPoint()))==member['number'])
                        pos=canvas.screen_point((line[0]+line[2])/2,(line[1]+line[3])/2).toPoint()
                        QTest.mouseClick(canvas,Qt.LeftButton,pos=pos)
                        assert w.region()['numbers']==[1,2] and canvas.selected_numbers=={1,2}
                        assert canvas.zoom==old_zoom and canvas.pan==old_pan
                        assert len(w.preview_cache)==1,'Selecting regions must preserve other heights'
                        QTest.mouseClick(canvas,Qt.LeftButton,pos=pos)
                        assert w.region()['numbers']==[1] and canvas.selected_numbers=={1}
                        assert w.config()['bridge_width_mm']==.55
                        w.clearbtn.click()
                        assert w.text is None and w.source is None and w.output is None and w.valid_cfg is None
                        assert not w.preview_cache
                        assert not w.before.lines and not w.after.lines and w.combo.count()==0
                        assert not w.calibration.isChecked() and not w.calrange.isEnabled()
                        assert w.before.zoom==w.after.zoom==1 and w.after.pan==QPointF()
                        assert not w.after.controls.isEnabled()
                        assert not w.previewbtn.isEnabled() and not w.hookbtn.isEnabled() and not w.clearbtn.isEnabled()
                        assert output.exists() and source.exists()
                        print('GUI smoke passed: all 1.5.1 controls plus two-height preview memory, settings restoration, combined save/profile, zoom, grouping, Clear model, Bambu launch, and invalidation.')
                        self.quit();return
                    QTimer.singleShot(30,poll)
                except Exception as ex:
                    errors.append(ex);self.quit()
            QTimer.singleShot(100,poll)
            return super().exec()
    from argparse import Namespace
    with patch('PySide6.QtWidgets.QApplication',Smoke):
        app.gui(Namespace(file=None,screenshot=None))
    if errors:raise errors[0]
