"""Radial Bridges desktop UI. CLI --hook mode intentionally needs no Qt imports."""
import argparse
import json
import os
from pathlib import Path
import sys
import traceback
import backend as b

ROOT=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('file',nargs='?')
    ap.add_argument('--hook',action='store_true')
    ap.add_argument('--profile')
    ap.add_argument('--self-test',action='store_true')
    ap.add_argument('--screenshot')
    a=ap.parse_args()
    if a.self_test:
        import unittest
        suite=unittest.defaultTestLoader.discover(str(ROOT),pattern='test_*.py')
        return 0 if unittest.TextTestRunner(stream=sys.stderr or open(os.devnull,'w'),verbosity=2).run(suite).wasSuccessful() else 1
    if a.hook:
        try:
            if not a.file or not a.profile:raise ValueError('Hook needs --profile and a G-code filename.')
            r=b.hook(a.profile,a.file)
            if sys.stdout:print(json.dumps(r))
            return 0
        except Exception as ex:
            msg=f'Radial Bridges: {ex}'
            b.atomic_write(b.data_dir()/'last-error.txt',msg)
            if sys.stderr:print(msg,file=sys.stderr)
            return 2
    return gui(a)

def gui(args):
    if os.name=='nt':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OolieIndustries.RadialBridges')
        except (AttributeError,OSError):pass
    from PySide6.QtCore import Qt,QThread,Signal,QTimer,QPointF,QRectF
    from PySide6.QtGui import QColor,QPainter,QPen,QPainterPath,QIcon,QDesktopServices
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
        QPushButton,QComboBox,QFormLayout,QDoubleSpinBox,QSpinBox,QGroupBox,QFileDialog,QMessageBox,
        QSplitter,QDialog,QPlainTextEdit,QDialogButtonBox,QScrollArea,QProgressBar,QFrame,QCheckBox)

    class Task(QThread):
        result=Signal(object)
        failed=Signal(str)
        def __init__(self,fn):super().__init__();self.fn=fn
        def run(self):
            try:self.result.emit(self.fn())
            except Exception as ex:self.failed.emit(str(ex))

    class Canvas(QWidget):
        regionClicked=Signal(int)
        def __init__(self,title,color):
            super().__init__();self.title=title;self.color=color;self.lines=[];self.bounds=None
            self.zoom=1.;self.pan=QPointF();self.drag=None
            self.region_members=[];self.selected_numbers=set();self.press=None;self.moved=False
            self.setMinimumSize(280,330)
            self.setToolTip('Scroll to zoom at the pointer. Drag to pan. Double-click or Fit to reset.')
            self.controls=QWidget(self);bar=QHBoxLayout(self.controls);bar.setContentsMargins(0,0,0,0);bar.setSpacing(4)
            for label,action in [('−',lambda:self.zoom_at(1/1.4)),('+',lambda:self.zoom_at(1.4)),('Fit',self.fit_view)]:
                button=QPushButton(label);button.setFixedHeight(27);button.setFixedWidth(42 if label=='Fit' else 29)
                button.setStyleSheet('padding:2px;');button.clicked.connect(action);bar.addWidget(button)
            self.controls.adjustSize();self.controls.setEnabled(False)
        def resizeEvent(self,event):
            self.controls.move(self.width()-self.controls.width()-12,38)
        def fit_view(self):
            self.zoom=1.;self.pan=QPointF();self.drag=None;self.unsetCursor();self.update()
        def set_data(self,lines,bounds=None):
            self.region_members=[];self.selected_numbers=set()
            self.lines=lines;self.bounds=bounds
            if lines and bounds is None:
                xs=[v for line in lines for v in (line[0],line[2])];ys=[v for line in lines for v in (line[1],line[3])]
                self.bounds=(min(xs),min(ys),max(xs),max(ys))
            self.controls.setEnabled(bool(lines));self.fit_view()
        def set_regions(self,members,numbers):
            self.set_data([line for member in members for line in member['segments']])
            self.region_members=members;self.selected_numbers=set(numbers)
            self.setToolTip('Click a bridge line to toggle its detected region. Orange: selected; blue: excluded. Drag to pan, scroll to zoom, double-click to fit.')
            self.update()
        def screen_point(self,x,y):
            x0,y0,x1,y1=self.bounds;span=max(x1-x0,y1-y0,1)
            plot=self.plot_rect();scale=min(plot.width()-24,plot.height()-24)/span*self.zoom
            return plot.center()+self.pan+QPointF((x-(x0+x1)/2)*scale,-(y-(y0+y1)/2)*scale)
        def hit_region(self,pos):
            best=8.;found=None
            for member in self.region_members:
                for xa,ya,xb,yb in member['segments']:
                    a=self.screen_point(xa,ya);c=self.screen_point(xb,yb);v=c-a;w=pos-a
                    length=v.x()*v.x()+v.y()*v.y()
                    t=max(0.,min(1.,(w.x()*v.x()+w.y()*v.y())/length)) if length else 0.
                    distance=(pos-(a+v*t)).manhattanLength()
                    if distance<best:best=distance;found=member['number']
            return found
        def plot_rect(self):return QRectF(12,72,max(1,self.width()-24),max(1,self.height()-110))
        def zoom_at(self,factor,anchor=None):
            if not self.lines:return
            center=self.plot_rect().center();anchor=anchor if anchor is not None else center
            new=max(.25,min(80.,self.zoom*factor));ratio=new/self.zoom
            self.pan=anchor-center-(anchor-center-self.pan)*ratio
            self.zoom=new;self.update()
        def wheelEvent(self,event):
            if self.lines and self.plot_rect().contains(event.position()):
                delta=event.angleDelta().y() or event.pixelDelta().y()
                self.zoom_at(1.2**max(-10,min(10,delta/120)),event.position());event.accept()
            else:event.ignore()
        def mousePressEvent(self,event):
            if self.lines and event.button()==Qt.LeftButton and self.plot_rect().contains(event.position()):
                self.drag=event.position();self.press=event.position();self.moved=False;self.setCursor(Qt.ClosedHandCursor);event.accept()
        def mouseMoveEvent(self,event):
            if self.drag is not None:
                if (event.position()-self.press).manhattanLength()>4:self.moved=True
                self.pan+=event.position()-self.drag;self.drag=event.position();self.update();event.accept()
        def mouseReleaseEvent(self,event):
            if self.drag is not None and not self.moved and self.region_members:
                number=self.hit_region(event.position())
                if number is not None:self.regionClicked.emit(number)
            self.drag=None;self.unsetCursor()
        def mouseDoubleClickEvent(self,event):
            if event.button()==Qt.LeftButton:self.fit_view();event.accept()
        def paintEvent(self,event):
            p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
            p.fillRect(self.rect(),QColor('#101923'))
            p.setPen(QColor('#dde6ef'));p.drawText(18,28,self.title)
            if not self.lines:
                p.setPen(QColor('#8193a5'))
                p.drawText(self.rect(),Qt.AlignCenter,'Open a sliced file to see bridge paths' if self.title.startswith('Original') else 'Preview radial paths before saving')
                return
            box=self.bounds
            x0,y0,x1,y1=box;span=max(x1-x0,y1-y0,1)
            plot=self.plot_rect();scale=min(plot.width()-24,plot.height()-24)/span*self.zoom
            cx,cy=(x0+x1)/2,(y0+y1)/2
            def pt(x,y):return plot.center()+self.pan+QPointF((x-cx)*scale,-(y-cy)*scale)
            p.save();p.setClipRect(plot)
            p.setPen(QPen(QColor('#1d2b3a'),1))
            for k in range(-5,6):
                ofs=k*span/10
                p.drawLine(pt(cx-span/2,cy+ofs),pt(cx+span/2,cy+ofs))
                p.drawLine(pt(cx+ofs,cy-span/2),pt(cx+ofs,cy+span/2))
            groups=[(member['segments'],'#ffb454' if member['number'] in self.selected_numbers else '#497ba7') for member in self.region_members] if self.region_members else [(self.lines,self.color)]
            for lines,color in groups:
                path=QPainterPath()
                for xa,ya,xb,yb in lines:
                    path.moveTo(pt(xa,ya));path.lineTo(pt(xb,yb))
                p.setPen(QPen(QColor(color),1.5 if self.region_members else 1.05));p.drawPath(path)
            p.restore();p.setPen(QColor('#8193a5'));p.drawText(18,self.height()-15,(f'{len(self.selected_numbers)}/{len(self.region_members)} regions · Orange selected · Blue excluded · Click to toggle' if self.region_members else f'{len(self.lines):,} paths · {self.zoom:.1f}× · Scroll / drag'))

    class Window(QMainWindow):
        def __init__(self):
            super().__init__();self.setWindowTitle('Radial Bridges');self.resize(1280,940)
            if (ROOT/'app.ico').exists():self.setWindowIcon(QIcon(str(ROOT/'app.ico')))
            self.text=None;self.regions=[];self.source=None;self.converted=None;self.report=None;self.output=None;self.jobs=[];self.plate=None;self.selected_region=None;self.valid_cfg=None;self.preview_cache={}
            self.settings=b.read_settings();self.bambu=b.find_bambu();self.loading=False
            root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root);layout.setContentsMargins(24,20,24,18);layout.setSpacing(14)
            header=QHBoxLayout();titles=QVBoxLayout()
            title=QLabel('Radial Bridges');title.setObjectName('title');titles.addWidget(title)
            sub=QLabel('Shorter paths across circular rings. Built for Bambu Studio.');sub.setObjectName('muted');titles.addWidget(sub)
            header.addLayout(titles);header.addStretch()
            self.openbtn=QPushButton('Open sliced file…');self.openbtn.setObjectName('primary');self.openbtn.clicked.connect(self.choose_file);header.addWidget(self.openbtn)
            self.clearbtn=QPushButton('Clear model');self.clearbtn.clicked.connect(self.clear_model);self.clearbtn.setEnabled(False);header.addWidget(self.clearbtn)
            helpbtn=QPushButton('Help');helpbtn.clicked.connect(self.help);header.addWidget(helpbtn);layout.addLayout(header)
            self.filelabel=QLabel('Choose a .gcode or sliced .gcode.3mf file. Your original file stays unchanged.');self.filelabel.setWordWrap(True);self.filelabel.setObjectName('muted');layout.addWidget(self.filelabel)
            self.body=QWidget();body=QHBoxLayout(self.body);body.setContentsMargins(0,0,0,0);body.setSpacing(16)
            left=QWidget();left.setFixedWidth(350);lv=QVBoxLayout(left);lv.setContentsMargins(0,0,0,0);lv.setSpacing(12)
            sel=QGroupBox('1  Choose a bridge height');sl=QVBoxLayout(sel)
            self.combo=QComboBox();self.combo.setToolTip('Select a bridge height. A checkmark means its settings and radial preview are saved in this session and will be included in the combined export.');self.combo.currentIndexChanged.connect(self.select_region);sl.addWidget(self.combo)
            self.choosebtn=QPushButton('Choose regions…');self.choosebtn.clicked.connect(self.choose_regions);self.choosebtn.setEnabled(False);sl.addWidget(self.choosebtn)
            self.allregionsbtn=QPushButton('Select all regions at this height');self.allregionsbtn.setEnabled(False)
            self.allregionsbtn.setToolTip('Include every detected bridge region at the current physical height. Other heights keep their saved previews.')
            self.allregionsbtn.clicked.connect(lambda:self.apply_selection([r['number'] for r in self.before.region_members]));sl.addWidget(self.allregionsbtn)
            self.region_note=QLabel('Bridge layers appear here after loading.');self.region_note.setWordWrap(True);self.region_note.setObjectName('muted');sl.addWidget(self.region_note);lv.addWidget(sel)
            formbox=QGroupBox('2  Review estimated dimensions');self.formbox=formbox;formbox.setEnabled(False);form=QFormLayout(formbox);form.setSpacing(8)
            self.fields={}
            specs=[('center_x_mm','Center X (mm)',-10000,10000),('center_y_mm','Center Y (mm)',-10000,10000),('inner_radius_mm','Inner radius (mm)',.001,10000),('outer_radius_mm','Outer radius (mm)',.001,10000),('pitch_mm','Line spacing (mm)',.1,1.5),('bridge_width_mm','Bridge width (mm)',.1,2),('bridge_speed_mm_s','Bridge speed (mm/s)',0,500),('retract_mm','Retraction (mm)',0,2)]
            field_tips={
                'center_x_mm':'X coordinate of the ring center. The automatic estimate is normally best.',
                'center_y_mm':'Y coordinate of the ring center. The automatic estimate is normally best.',
                'inner_radius_mm':'Distance from the ring center to the inner edge of the bridge area.',
                'outer_radius_mm':'Distance from the ring center to the outer edge of the bridge area.',
                'pitch_mm':'Center-to-center spacing between neighboring radial bridge lines. Smaller values make more lines.',
                'bridge_width_mm':'Extrusion width used for the new bridge lines. Increase this when very thin layers produce weak bridges.',
                'bridge_speed_mm_s':'Maximum speed for generated bridge extrusion. Keep original uses the slower sliced bridge speed.',
                'retract_mm':'Retraction used only for necessary non-printing moves. Connected Zigzag turns do not retract.'}
            for key,label,lo,hi in specs:
                w=QDoubleSpinBox();w.setRange(lo,hi);w.setDecimals(5 if key not in ('bridge_speed_mm_s','retract_mm') else 2);w.setSingleStep(.1)
                if key=='bridge_speed_mm_s':w.setSpecialValueText('Keep original')
                w.setToolTip(field_tips[key]);w.valueChanged.connect(self.invalidate);self.fields[key]=w;form.addRow(label,w)
            self.pattern=QComboBox();self.pattern.addItem('Zigzag (recommended)','zigzag');self.pattern.addItem('Monotonic outward','outward');self.pattern.addItem('Monotonic inward','inward');self.pattern.setToolTip('Zigzag joins neighboring spokes with short extruded turns and avoids intermediate retractions. Monotonic patterns print every spoke in one direction and require travel moves.');self.pattern.currentIndexChanged.connect(self.invalidate);form.addRow('Pattern',self.pattern)
            self.continuous=QCheckBox('Make one continuous ring pass');self.continuous.setToolTip('When safe, combine bridge fragments at this same Z height into one uninterrupted trip around the ring.');self.continuous.setChecked(True);self.continuous.toggled.connect(self.invalidate);form.addRow(self.continuous)
            thick=QPushButton('Set 0.55 mm thick bridge');thick.setToolTip('Useful starting test for a 0.4 mm nozzle and a very thin bridge layer. Preview before printing.');thick.clicked.connect(lambda:self.fields['bridge_width_mm'].setValue(.55));form.addRow(thick)
            self.calibration=QCheckBox('Calibration sweep around ring');self.calibration.setToolTip('Divide the ring into sectors with different bridge widths so one print can identify the strongest setting.');self.calibration.toggled.connect(self.invalidate);form.addRow(self.calibration)
            self.calrange=QDoubleSpinBox();self.calrange.setRange(.01,.5);self.calrange.setDecimals(2);self.calrange.setSingleStep(.01);self.calrange.setValue(.1);self.calrange.setSuffix(' mm');self.calrange.setToolTip('Amount added to and subtracted from the selected bridge width across the calibration sectors.');self.calrange.valueChanged.connect(self.invalidate);form.addRow('Sweep ±',self.calrange)
            self.calsteps=QSpinBox();self.calsteps.setRange(3,9);self.calsteps.setValue(5);self.calsteps.setToolTip('Number of width samples printed around the calibration ring. Width increases counterclockwise from 3 o’clock.');self.calsteps.valueChanged.connect(self.invalidate);form.addRow('Sweep sectors',self.calsteps)
            self.calibration.toggled.connect(self.calrange.setEnabled);self.calibration.toggled.connect(self.calsteps.setEnabled);self.calrange.setEnabled(False);self.calsteps.setEnabled(False)
            reset=QPushButton('Reset to automatic estimates');reset.clicked.connect(self.reset_current);form.addRow(reset)
            note=QLabel('For a 0.08 mm layer, try 0.55 mm width, then inspect flow in Studio. Line spacing stays independently adjustable. Check support under both ends.');note.setWordWrap(True);note.setMinimumHeight(65);note.setObjectName('muted');form.addRow(note);lv.addWidget(formbox)
            self.finebox=QGroupBox('Fine tuning');self.finebox.setEnabled(False);fine=QFormLayout(self.finebox);self.fine_fields={}
            self.fine_defaults={}
            tuning=[
                ('bridge_flow_percent','Extra bridge flow (%)',35,200,100,'Multiplies bridge extrusion independently of line width. 100 keeps width-based flow unchanged.'),
                ('spoke_density_percent','Spoke density (%)',50,200,100,'Controls the generated spoke count. 200 doubles spokes and material; each spoke retains its extrusion per mm. Original spacing is still used for geometry validation.'),
                ('turn_flow_percent','Zigzag turn flow (%)',10,200,100,'Extrusion multiplier for the short connected Zigzag turns only. Does not change the radial spokes.'),
                ('turn_speed_percent','Zigzag turn speed (%)',10,100,100,'Speed of connected turns relative to bridge speed. Cannot exceed the bridge speed.'),
                ('travel_speed_mm_s','Travel speed (mm/s)',1,300,100,'Speed for generated non-printing XY moves. Does not change unrelated source travel.'),
                ('retract_speed_mm_s','Retract speed (mm/s)',1,100,30,'Speed of generated retract/unretract moves. Retraction amount is set above. Connected turns never retract.'),
                ('start_angle_offset_deg','Start offset (degrees)',-360,360,0,'Rotates the radial layout and calibration sectors relative to the automatic start. Positive is counterclockwise. Travel still respects the ring corridor.'),
                ('max_connected_gap_factor','Max connected gap (× spacing)',1,4,2,'Largest gap that Zigzag may connect with extrusion. Larger gaps use travel. Increasing this may extrude across wider gaps; inspect support.'),
                ('travel_segment_mm','Travel curve segment (mm)',.1,5,.4,'Maximum approximate segment length for non-printing travel around the ring. Smaller values make smoother travel and more G-code.'),
                ('geometry_tolerance_mm','Geometry tolerance (mm)',0,.5,.15,'Tolerance used when validating ring coverage and intervening features. Increasing it does not add support or fix an incorrect ring.'),
                ('source_line_width_mm','Source width override (mm)',.1,2,.42,'Original sliced bridge width used as the extrusion scaling reference. Normally keep the detected value; this does not change nozzle size.')]
            for key,label,lo,hi,default,tip in tuning:
                w=QDoubleSpinBox();w.setRange(lo,hi);w.setDecimals(3);w.setSingleStep(1 if hi>=100 else .05);w.setValue(default);w.setToolTip(tip)
                w.valueChanged.connect(self.invalidate);self.fine_fields[key]=w;self.fine_defaults[key]=default;fine.addRow(label,w)
            self.clockwise=QCheckBox('Print clockwise');self.clockwise.setToolTip('Reverse the order around the ring. Radial inward/outward direction is still controlled by Pattern. Calibration sectors follow the selected printing direction.');self.clockwise.toggled.connect(self.invalidate);fine.addRow(self.clockwise)
            fine_reset=QPushButton('Reset fine tuning');fine_reset.setToolTip('Reset only advanced controls for this height. Main dimensions, width, pattern and calibration are kept.');fine_reset.clicked.connect(self.reset_fine);fine.addRow(fine_reset)
            fine_note=QLabel('Fan, temperature, acceleration, pressure advance and layer height remain controlled by your Studio preset. These are not safely inferred from a sliced path.');fine_note.setWordWrap(True);fine.addRow(fine_note);lv.addWidget(self.finebox)
            self.previewbtn=QPushButton('Generate Radial Bridge Preview');self.previewbtn.setToolTip('Validate the selected ring and generate the proposed radial toolpath for inspection before saving.');self.previewbtn.setObjectName('primary');self.previewbtn.clicked.connect(self.preview);lv.addWidget(self.previewbtn)
            self.stats=QLabel('Preview checks the geometry before allowing export.');self.stats.setWordWrap(True);lv.addWidget(self.stats);lv.addStretch();left.setMinimumHeight(740);scroll=QScrollArea();scroll.setWidget(left);scroll.setWidgetResizable(True);scroll.setFixedWidth(372);scroll.setFrameShape(QFrame.NoFrame);body.addWidget(scroll)
            views=QWidget();vv=QVBoxLayout(views);vv.setContentsMargins(0,0,0,0)
            self.sectionlabel=QLabel();self.sectionlabel.setWordWrap(True);self.sectionlabel.hide();vv.addWidget(self.sectionlabel)
            self.view_split=QSplitter(Qt.Horizontal);self.before=Canvas('Original bridges','#57aaf4');self.after=Canvas('Radial bridges','#35dbb3');self.view_split.addWidget(self.before);self.view_split.addWidget(self.after);vv.addWidget(self.view_split,1)
            self.before.regionClicked.connect(self.toggle_region)
            foot=QLabel('Scroll to zoom · Drag to pan · Double-click or Fit to reset. Open exported G-code in Studio to inspect travel and support.');foot.setObjectName('muted');foot.setWordWrap(True);vv.addWidget(foot)
            action=QHBoxLayout();self.savebtn=QPushButton('Save radial G-code…');self.savebtn.setObjectName('primary');self.savebtn.clicked.connect(self.save_output)
            self.bambubtn=QPushButton('Open result in Bambu Studio');self.bambubtn.clicked.connect(self.open_bambu)
            self.hookbtn=QPushButton('Use inside Bambu Studio…');self.hookbtn.clicked.connect(self.integration)
            action.addWidget(self.savebtn);action.addWidget(self.bambubtn);vv.addLayout(action);vv.addWidget(self.hookbtn);body.addWidget(views,1);layout.addWidget(self.body,1)
            self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setFixedHeight(4);self.progress.hide();layout.addWidget(self.progress)
            self.status=QLabel('Version 1.8.0 · Fine tuning · All 1.5.1 features retained · Runs locally');self.status.setObjectName('muted');self.status.setWordWrap(True);layout.addWidget(self.status)
            self.invalidate();self.setAcceptDrops(True)
        def dragEnterEvent(self,e):
            if e.mimeData().hasUrls():e.acceptProposedAction()
        def dropEvent(self,e):
            if not self.jobs and e.mimeData().hasUrls():self.load_file(e.mimeData().urls()[0].toLocalFile())
        def busy(self,value):
            self.body.setEnabled(not value);self.openbtn.setEnabled(not value);self.clearbtn.setEnabled(not value and self.source is not None);self.progress.setVisible(value)
        def work(self,fn,done,message):
            self.busy(True);self.status.setText(message)
            task=Task(fn);self.jobs.append(task)
            task.result.connect(done);task.failed.connect(self.error)
            def finish():
                self.jobs.remove(task);self.busy(False);task.deleteLater()
            task.finished.connect(finish);task.start()
        def error(self,message):
            self.status.setText('Could not complete: '+message)
            box=QMessageBox(self);box.setWindowTitle('Radial Bridges');box.setIcon(QMessageBox.Warning);box.setText(message);box.setTextInteractionFlags(Qt.TextSelectableByMouse);box.addButton(QMessageBox.Ok)
            copybtn=box.addButton('Copy error',QMessageBox.ActionRole);copybtn.clicked.connect(lambda:QApplication.clipboard().setText(message));box.exec()
        def clear_model(self):
            if self.jobs:return
            self.text=None;self.source=None;self.regions=[];self.selected_region=None;self.plate=None
            self.converted=None;self.report=None;self.output=None;self.valid_cfg=None;self.preview_cache={}
            self.sectionlabel.hide()
            self.combo.blockSignals(True);self.combo.clear();self.combo.blockSignals(False)
            self.loading=True
            for key,field in self.fields.items():field.setValue(.4 if key=='pitch_mm' else max(0,field.minimum()))
            self.pattern.setCurrentIndex(0);self.continuous.setChecked(True)
            self.calibration.setChecked(False);self.calrange.setValue(.1);self.calsteps.setValue(5)
            for key,w in self.fine_fields.items():w.setValue(self.fine_defaults[key])
            self.clockwise.setChecked(False)
            self.loading=False;self.before.set_data([]);self.invalidate()
            self.clearbtn.setEnabled(False);self.choosebtn.setEnabled(False);self.formbox.setEnabled(False)
            self.allregionsbtn.setEnabled(False)
            self.finebox.setEnabled(False)
            self.filelabel.setText('Choose a .gcode or sliced .gcode.3mf file. Your original file stays unchanged.')
            self.region_note.setText('Regions at the same height are combined automatically.')
            self.status.setText('Model cleared. Open another sliced file when ready.')
        def choose_regions(self):
            idx=self.combo.currentIndex()
            if idx<0:return
            group=self.regions[idx];members=group['members'] or [group]
            dialog=QDialog(self);dialog.setWindowTitle('Combine regions at this height');dialog.resize(530,360);lay=QVBoxLayout(dialog)
            msg=QLabel(f"Select the regions forming this ring at Z {group['z']:.3f} mm.\nDifferent physical layer heights stay separate.");msg.setWordWrap(True);lay.addWidget(msg)
            area=QScrollArea();area.setWidgetResizable(True);inner=QWidget();iv=QVBoxLayout(inner);checks=[]
            for member in members:
                cb=QCheckBox(f"Region #{member['number']} — {len(member['segments']):,} extrusion segments")
                cb.setToolTip('Include this detected bridge region in the combined radial ring at the selected height.')
                cb.setChecked(member['number'] in self.region()['numbers']);checks.append(cb);iv.addWidget(cb)
            iv.addStretch();area.setWidget(inner);lay.addWidget(area)
            allbtn=QPushButton('Select all at this height');allbtn.clicked.connect(lambda:[cb.setChecked(True) for cb in checks]);lay.addWidget(allbtn)
            buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);lay.addWidget(buttons)
            if dialog.exec()==QDialog.Accepted:
                chosen=[r for r,cb in zip(members,checks) if cb.isChecked()]
                self.apply_selection([r['number'] for r in chosen])
        def toggle_region(self,number):
            numbers=set(self.region()['numbers'])
            if number in numbers:numbers.remove(number)
            else:numbers.add(number)
            self.apply_selection(numbers)
        def apply_selection(self,numbers):
            if not numbers:
                self.status.setText('Keep at least one bridge region selected. Click another region to include it first.');return
            idx=self.combo.currentIndex();members=self.regions[idx]['members'] or [self.regions[idx]]
            try:
                cfg=self.config();combined=b.combine_members([r for r in members if r['number'] in numbers]);combined['members']=members
                tuning=set(self.fine_fields)|{'bridge_width_mm','bridge_speed_mm_s','retract_mm','pattern','continuous_pass','calibration_mode','calibration_range_mm','calibration_steps','clockwise'}
                for key,value in cfg.items():
                    if key in tuning:combined['cfg'][key]=value
                self.regions[idx]=combined;self.preview_cache.pop(idx,None);self.converted=None;self.output=None
                zoom,pan=self.before.zoom,QPointF(self.before.pan)
                self.refresh_height_labels();self.apply_region(combined,False)
                self.before.zoom=zoom;self.before.pan=pan;self.before.update()
                self.status.setText('Selection changed. Orange regions will be converted; blue regions keep their original paths. Generate again for this height.')
            except Exception as ex:self.error(str(ex))
        def choose_file(self):
            path,_=QFileDialog.getOpenFileName(self,'Open sliced file',self.settings.get('last_dir',''),'Sliced files (*.gcode *.3mf);;All files (*)')
            if path:self.load_file(path)
        def load_file(self,path):
            try:
                choices=b.plate_names(path)
                plate=None
                if len(choices)>1:
                    from PySide6.QtWidgets import QInputDialog
                    plate,ok=QInputDialog.getItem(self,'Choose plate','Sliced plate:',choices,0,False)
                    if not ok:return
                elif choices:plate=choices[0]
                def read():
                    text=b.read_input(path,plate)
                    return text,b.analyze(text)
                def done(result):
                    self.text,self.regions=result;self.source=Path(path);self.plate=plate
                    self.preview_cache={};self.converted=None;self.output=None;self.report=None;self.valid_cfg=None
                    self.settings['last_dir']=str(self.source.parent);b.write_settings(self.settings)
                    self.filelabel.setText(self.source.name+(f'  /  {plate}' if plate else ''))
                    self.combo.blockSignals(True);self.combo.clear()
                    for r in self.regions:self.combo.addItem('')
                    self.refresh_height_labels()
                    idx=next((i for i,r in enumerate(self.regions) if r['plausible']),0)
                    self.combo.setCurrentIndex(idx);self.combo.blockSignals(False);self.select_region(idx)
                    self.clearbtn.setEnabled(True);self.status.setText(f'Loaded {len(self.regions)} bridge height(s). Same-height regions are combined automatically.')
                self.work(read,done,'Reading G-code and estimating ring geometry…')
            except Exception as ex:self.error(str(ex))
        def region(self):
            return self.selected_region
        def select_region(self,index):
            if not 0<=index<len(self.regions):return
            self.apply_region(self.regions[index])
        def refresh_height_labels(self):
            for index,r in enumerate(self.regions):
                ready='✓  ' if index in self.preview_cache else ''
                self.combo.setItemText(index,f"{ready}Z {r['z']:.3f} mm  ·  {len(r['numbers'])} region(s)")
        def apply_region(self,r,use_cache=True):
            index=self.combo.currentIndex();record=self.preview_cache.get(index) if use_cache else None
            if record:r=record['region']
            cfg=record['cfg'] if record else r['cfg']
            self.selected_region=r;self.formbox.setEnabled(True);self.finebox.setEnabled(True);self.loading=True
            for key,w in self.fields.items():w.setValue(cfg.get(key) or 0)
            self.pattern.setCurrentIndex(max(0,self.pattern.findData(cfg.get('pattern','zigzag'))));self.continuous.setChecked(cfg.get('continuous_pass',True))
            self.calibration.setChecked(cfg.get('calibration_mode',False));self.calrange.setValue(cfg.get('calibration_range_mm',.1));self.calsteps.setValue(cfg.get('calibration_steps',5))
            for key,w in self.fine_fields.items():w.setValue(cfg.get(key,max(cfg['pitch_mm'],.2) if key=='travel_segment_mm' else self.fine_defaults[key]))
            self.clockwise.setChecked(cfg.get('clockwise',False))
            self.loading=False;self.before.set_regions(r['members'] or [r],r['numbers']);self.choosebtn.setEnabled(True);self.previewbtn.setEnabled(True)
            self.allregionsbtn.setEnabled(True)
            ready=f"Generated and saved · {len(self.preview_cache)} height(s) ready" if record else 'Possible full ring. Generate a preview to add this height.'
            self.region_note.setText(f"Z {r['z']:.3f} mm · {len(r['numbers'])} region(s) selected\n{len(r['segments']):,} paths combined\n"+(ready if r['plausible'] else 'Review the selected regions and dimensions; validation may refuse them.'))
            if record:
                self.report=record['report'];self.valid_cfg=record['cfg'];self.after.set_data(record['lines']);self.show_report(record['report'])
                self.status.setText(f"Restored saved preview at Z {r['z']:.3f} mm. {len(self.preview_cache)} height(s) will be exported.")
            else:
                self.report=None;self.valid_cfg=None;self.after.set_data([]);self.sectionlabel.hide();self.stats.setText('Generate a preview for this height. Completed heights remain saved.')
            ready_to_export=bool(self.preview_cache) and self.converted is not None
            self.savebtn.setEnabled(ready_to_export);self.hookbtn.setEnabled(ready_to_export);self.bambubtn.setEnabled(self.output is not None)
        def reset_current(self):
            index=self.combo.currentIndex()
            if not 0<=index<len(self.regions):return
            if index in self.preview_cache:del self.preview_cache[index]
            self.converted=None;self.output=None;self.refresh_height_labels();self.apply_region(self.regions[index],False)
        def reset_fine(self):
            self.loading=True
            for key,w in self.fine_fields.items():w.setValue(self.region()['cfg'].get(key,self.fine_defaults[key]) if self.region() else self.fine_defaults[key])
            self.clockwise.setChecked(False);self.loading=False;self.invalidate()
        def invalidate(self,*unused):
            if self.loading:return
            index=self.combo.currentIndex();removed=index in self.preview_cache
            if removed:
                del self.preview_cache[index];self.converted=None;self.output=None;self.refresh_height_labels()
            self.report=None;self.valid_cfg=None
            self.sectionlabel.hide()
            self.after.set_data([]);self.bambubtn.setEnabled(False)
            ready=bool(self.preview_cache) and self.converted is not None
            self.savebtn.setEnabled(ready);self.hookbtn.setEnabled(ready)
            self.previewbtn.setEnabled(self.region() is not None);self.stats.setText('Generate this height again to save its changed settings.' if removed else 'Preview checks this height before adding it to the export.')
        def config(self):
            cfg=dict(self.region()['cfg'])
            cfg.update({k:w.value() for k,w in self.fields.items()})
            cfg.update({k:w.value() for k,w in self.fine_fields.items()});cfg['clockwise']=self.clockwise.isChecked()
            cfg['pattern']=self.pattern.currentData();cfg['continuous_pass']=self.continuous.isChecked()
            cfg['calibration_mode']=self.calibration.isChecked();cfg['calibration_range_mm']=self.calrange.value();cfg['calibration_steps']=self.calsteps.value()
            if not cfg['bridge_speed_mm_s']:cfg['bridge_speed_mm_s']=None
            return cfg
        def preview(self):
            cfg=self.config();text=self.text;index=self.combo.currentIndex();region=self.region()
            items=[(key,record['cfg'],record['region']) for key,record in sorted(self.preview_cache.items()) if key!=index]
            items.append((index,cfg,region));items.sort(key=lambda item:item[0])
            def done(result):
                self.converted,reports,previews=result;self.output=None
                for (key,item_cfg,item_region),report,lines in zip(items,reports,previews):
                    self.preview_cache[key]=dict(cfg=item_cfg,region=item_region,report=report,lines=lines)
                record=self.preview_cache[index];self.report=record['report'];self.valid_cfg=record['cfg'];self.after.set_data(record['lines'])
                self.refresh_height_labels();self.show_report(self.report)
                self.savebtn.setEnabled(True);self.hookbtn.setEnabled(True);self.bambubtn.setEnabled(False)
                self.region_note.setText(f"Z {region['z']:.3f} mm · {len(region['numbers'])} region(s) selected\n{len(region['segments']):,} paths combined\nGenerated and saved · {len(self.preview_cache)} height(s) ready")
                self.status.setText(f"Geometry checks passed. {len(self.preview_cache)} bridge height(s) will be included when saved or used in Studio.")
            self.work(lambda:b.convert_many(text,[item[1] for item in items]),done,'Validating and rebuilding all generated bridge heights…')
        def show_report(self,r):
            names={'zigzag':'Zigzag','outward':'Monotonic outward','inward':'Monotonic inward'}
            direction='clockwise' if self.clockwise.isChecked() else 'counterclockwise'
            cal=(f"\nCalibration {direction}, start offset {self.fine_fields['start_angle_offset_deg'].value():g}°: {', '.join(f'{w:.3f}' for w in r['calibration_widths_mm'])} mm" if r['calibration_mode'] else '')
            toplabel=f"Z {r['z_mm']:.5f} mm · {r['section_note']}"+(f" Calibration {direction}: {' / '.join(f'{w:.3f}' for w in r['calibration_widths_mm'])} mm." if r['calibration_mode'] else '')
            turns=(f" · {r['zigzag_connectors']:,} connected turns" if r['pattern']=='zigzag' else '')
            self.sectionlabel.setText(toplabel);self.sectionlabel.show();self.stats.setText(f"{r['combined_regions']} region(s) · Z {r['z_mm']:.5f} mm\n{r['section_note']}\n{names[r['pattern']]} · width {r['source_line_width_mm']:.3f} → {r['bridge_width_mm']:.3f} mm ({r['flow_percent']:.0f}% flow){cal}\nLongest path: {r['old_longest_span_mm']:.2f} → {r['radial_span_mm']:.2f} mm\n{r['spokes']:,} radial spokes{turns} · {r['bridge_speed_mm_s']:.1f} mm/s\nSpacing: {r['inner_spacing_mm']:.3f}–{r['outer_spacing_mm']:.3f} mm")
        def save_output(self):
            if not self.converted:return
            base=self.source.name
            if base.lower().endswith('.gcode.3mf'):base=base[:-10]
            else:base=self.source.stem
            suffix='-'+Path(self.plate).stem if self.plate else ''
            name=str(self.source.parent/(base+suffix+'.radial.gcode'))
            path,_=QFileDialog.getSaveFileName(self,'Save radial G-code',name,'G-code (*.gcode)')
            if not path:return
            try:
                if Path(path).resolve()==self.source.resolve():raise ValueError('Choose a new filename to keep the original unchanged.')
                b.atomic_write(path,self.converted);self.output=Path(path);self.bambubtn.setEnabled(True)
                self.status.setText(f'Saved {self.output} with {len(self.preview_cache)} radial bridge height(s). Open it in Bambu Studio to inspect.')
            except Exception as ex:self.error(str(ex))
        def locate_bambu(self):
            if self.bambu and Path(self.bambu).is_file():return True
            p,_=QFileDialog.getOpenFileName(self,'Locate Bambu Studio executable','C:/Program Files','Bambu Studio (bambu-studio.exe);;Executables (*.exe)')
            if not p:return False
            self.bambu=p;self.settings['bambu_path']=p;b.write_settings(self.settings);return True
        def open_bambu(self):
            try:
                if self.locate_bambu():b.launch_bambu(self.bambu,self.output)
            except Exception as ex:self.error(str(ex))
        def integration(self):
            try:
                records=[self.preview_cache[key] for key in sorted(self.preview_cache)]
                profile=b.save_profiles([(record['cfg'],record['region']) for record in records],str(self.source))
                exe=ROOT/'RadialBridges.exe'
                command=f'"{exe}" --hook --profile "{profile}"'
                dialog=QDialog(self);dialog.setWindowTitle('Use inside Bambu Studio');dialog.resize(760,420);lay=QVBoxLayout(dialog)
                info=QLabel(f'1. Click Copy command below.\n2. In Studio, enable Advanced settings.\n3. Open Process → Others → Post-processing scripts and paste the command.\n4. Re-slice and inspect the exported result.\n\nThis profile includes all {len(records)} generated bridge height(s). If you move, resize or re-slice the model differently, reopen its slice here to create a new command.');info.setWordWrap(True);lay.addWidget(info)
                cmd=QPlainTextEdit(command);cmd.setReadOnly(True);cmd.setMaximumHeight(95);lay.addWidget(cmd)
                note=QLabel('Remove the command from Studio when done with this project. The hook keeps a backup before editing. No printer settings files are changed by this app.');note.setWordWrap(True);note.setObjectName('muted');lay.addWidget(note)
                buttons=QHBoxLayout();copybtn=QPushButton('Copy command');copybtn.setObjectName('primary')
                def copy():QApplication.clipboard().setText(command);copybtn.setText('Copied')
                copybtn.clicked.connect(copy);buttons.addWidget(copybtn)
                back=QPushButton('Open backup folder');back.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(b.data_dir()))));buttons.addWidget(back)
                close=QPushButton('Close');close.clicked.connect(dialog.accept);buttons.addWidget(close);lay.addLayout(buttons);dialog.exec()
            except Exception as ex:self.error(str(ex))
        def help(self):
            QMessageBox.information(self,'Using Radial Bridges','Open a sliced G-code or G-code 3MF file. Choose a bridge height, then click Generate Radial Bridge Preview. A checkmark appears beside that height. You can switch to another Z height, use different settings, and return without losing the first preview. Saving or creating the Studio hook includes every checkmarked height.\n\nThe app estimates center, radii, spacing, and sliced bridge width; adjust the fields if needed. Hover over any input for a description. Save a new G-code and use Open result in Bambu Studio to inspect.\n\nFor automatic conversion, choose Use inside Bambu Studio and paste the generated command in Studio’s Post-processing scripts field. No config-file editing is needed.\n\nScroll over either preview to zoom at your pointer. Drag to pan, or use + / − / Fit. Double-click resets the view.\n\nZigzag continuously extrudes short turns between neighboring radial spokes, removing obsolete source wipe retractions and Z-hops. Monotonic outward or inward prints every spoke in one direction. Bridge width scales bridge extrusion; increasing 0.42 to 0.55 mm gives about 131% flow. Match line spacing to the width if you want adjacent paths to touch.\n\nCalibration sweep tests 3–9 widths on one ring. Widths increase counterclockwise from the 3 o’clock/rightmost point. Use the best-looking sector as your new Bridge width, turn calibration off, and preview again.\n\nSame-height regions are combined automatically. One continuous ring pass can move separated bridge fragments ahead of intervening same-layer features only when those features do not touch the ring. Safe Bambu M-codes are preserved. Different Z heights keep independent previews and settings. Clear model resets the loaded file and previews. Check material under both ends of the bridges. No print has been physically validated.\n\nYour files stay local. Settings and hook backups are stored under LocalAppData / Radial Bridges.')
        def closeEvent(self,event):
            if self.jobs:
                self.status.setText('Wait for the current operation to finish before closing.');event.ignore()
            else:event.accept()

    app=QApplication(sys.argv[:1]);app.setApplicationName('Radial Bridges');app.setApplicationDisplayName('Radial Bridges');app.setOrganizationName('Oolie Industries');app.setStyle('Fusion')
    if (ROOT/'app.ico').exists():app.setWindowIcon(QIcon(str(ROOT/'app.ico')))
    app.setStyleSheet('''QWidget{background:#18232f;color:#e5edf5;font-family:"Segoe UI";font-size:13px;} QLabel#title{font-size:30px;font-weight:700;} QLabel#muted{color:#9cafc0;} QGroupBox{border:1px solid #344657;border-radius:8px;margin-top:14px;padding:15px 12px 10px;} QGroupBox::title{subcontrol-origin:margin;left:12px;color:#bdcbd8;font-weight:600;} QPushButton{background:#283b4b;border:1px solid #41596c;border-radius:6px;padding:10px 13px;font-weight:600;} QPushButton:hover{background:#365268;} QPushButton:disabled{background:#202d38;color:#617486;border-color:#2c3a47;} QPushButton#primary{background:#087c69;border:1px solid #0d9d85;color:white;} QPushButton#primary:hover{background:#0b9981;} QPushButton#primary:disabled{background:#21423f;color:#75908b;border-color:#315551;} QComboBox,QDoubleSpinBox,QPlainTextEdit{background:#101923;border:1px solid #405365;border-radius:4px;padding:6px;selection-background-color:#087c69;} QProgressBar{border:0;background:#24384b;} QProgressBar::chunk{background:#35dbb3;} QToolTip{background:#263e50;color:white;border:1px solid #557086;}''')
    win=Window();win.show()
    if args.file:QTimer.singleShot(100,lambda:win.load_file(args.file))
    if args.screenshot:
        def shot():
            if win.jobs:QTimer.singleShot(200,shot);return
            if win.text and not win.converted:
                win.preview();QTimer.singleShot(300,shot);return
            win.grab().save(args.screenshot);app.quit()
        QTimer.singleShot(500,shot)
    return app.exec()

if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        msg=traceback.format_exc()
        try:b.atomic_write(b.data_dir()/'startup-error.txt',msg)
        except Exception:pass
        if sys.stderr:print(msg,file=sys.stderr)
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Radial Bridges could not start. Details were saved in LocalAppData / Radial Bridges / startup-error.txt.','Radial Bridges',16)
        sys.exit(1)
