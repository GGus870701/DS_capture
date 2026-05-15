import sys
import os
import math

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, 
    QGraphicsPixmapItem, QToolBar, QStatusBar, QFileDialog, 
    QColorDialog, QInputDialog, QMessageBox, QWidget, QVBoxLayout,
    QLineEdit, QLabel, QHBoxLayout, QComboBox,
    QPushButton
)
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QBrush, 
    QIcon, QAction, QFont, QCursor, QKeySequence,
    QMouseEvent, QTransform
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QRectF, QSize, QByteArray, QEvent,
    Signal, QBuffer, QIODevice
)
from PySide6.QtSvg import QSvgRenderer

from core.utils import set_qt_window_icon, get_resource_path, CONFIG_FILE
import json
import io
import ctypes
import win32clipboard
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# --- [SVG Icons Data] ---
SVG_ICONS = {
    "pen": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19l7-7 3 3-7 7-3-3z"></path><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"></path><path d="M2 2l5 5"></path><path d="M11 11l1 1"></path></svg>',
    "line": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line></svg>',
    "arrow": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>',
    "rect": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>',
    "ellipse": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle></svg>',
    "highlight": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11-6 6v3h9l3-3"></path><path d="m22 12-4.6 4.6a2 2 0 0 1-2.8 0l-5.2-5.2a2 2 0 0 1 0-2.8L14 4"></path></svg>',
    "mosaic": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="3" y1="15" x2="21" y2="15"></line><line x1="9" y1="3" x2="9" y2="21"></line><line x1="15" y1="3" x2="15" y2="21"></line></svg>',
    "text": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"></polyline><line x1="9" y1="20" x2="15" y2="20"></line><line x1="12" y1="4" x2="12" y2="20"></line></svg>',
    "crop": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 13V6a2 2 0 0 1 2-2h7"></path><path d="M18 11v7a2 2 0 0 1-2 2H9"></path><line x1="1" y1="6" x2="1" y2="6"></line><line x1="18" y1="23" x2="18" y2="23"></line></svg>',
    "undo": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7v6h6"></path><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"></path></svg>',
    "redo": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 7v6h-6"></path><path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3L21 13"></path></svg>',
    "save": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>',
    "save_as": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>',
    "zoom_extents": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>',
    "fill": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
    "copy": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>',
    "rotate": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>',
    "rotate_ccw": '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 4v6h6"></path><path d="M3.51 15a9 9 0 1 0 2.12-9.36L1 10"></path></svg>'
}

def get_svg_icon(name, color="#d2dae2"):
    svg_str = SVG_ICONS.get(name, "")
    if not svg_str: return QIcon()
    svg_str = svg_str.replace('currentColor', color)
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer = QSvgRenderer(QByteArray(svg_str.encode()))
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

# --- [Styles] ---
STYLE_SHEET = """
QMainWindow {
    background-color: #1e272e;
}
QToolTip {
    background-color: #2f3542;
    color: white;
    border: 1px solid #3d3d3d;
    font-family: 'Malgun Gothic';
    font-size: 13px;
    padding: 4px;
}
QToolBar {
    background-color: #2f3640;
    border-bottom: 1px solid #3d3d3d;
    spacing: 5px;
    padding: 5px;
}
QToolButton {
    background-color: transparent;
    border-radius: 4px;
    padding: 4px;
}
QToolButton:hover {
    background-color: #485460;
}
QToolButton:checked {
    background-color: #0fbcf9;
}
QStatusBar {
    background-color: #1e272e;
    color: #d2dae2;
    font-family: 'Malgun Gothic';
    font-size: 14px;
    font-weight: bold;
}
QSpinBox {
    background-color: #2f3542;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 2px;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
    background-color: #3d3d3d;
}
QSpinBox::up-arrow {
    image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><path d='M5 2L1 8h8z' fill='white'/></svg>");
    width: 12px;
    height: 12px;
}
QSpinBox::down-arrow {
    image: url("data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'><path d='M5 8L1 2h8z' fill='white'/></svg>");
    width: 12px;
    height: 12px;
}
QLabel {
    color: #d2dae2;
    font-family: 'Malgun Gothic';
    font-size: 14px;
    font-weight: bold;
}
QComboBox {
    background-color: #2f3542;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 2px 5px;
    font-family: 'Malgun Gothic';
    font-size: 14px;
}
QComboBox QAbstractItemView {
    background-color: #2f3542;
    color: #ffffff;
    selection-background-color: #57606f;
    outline: none;
    border: 1px solid #3d3d3d;
}

/* 커스텀 스핀박스 스타일 */
.CustomSpinBox {
    background-color: transparent;
}
.CustomSpinBox QLineEdit {
    background-color: #1e272e;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 2px;
    font-family: 'Malgun Gothic';
    font-size: 14px;
}
.CustomSpinBox QPushButton {
    background-color: #3d3d3d;
    color: #ffffff;
    border: 1px solid #555;
    border-radius: 2px;
    font-size: 10px;
    padding: 0px;
}
.CustomSpinBox QPushButton:hover {
    background-color: #485460;
}

/* 플로팅 버튼 스타일 */
#FloatingFitBtn {
    background-color: rgba(47, 53, 66, 200);
    color: white;
    border: 1px solid rgba(255, 255, 255, 30);
    border-radius: 6px;
    padding: 5px;
}
#FloatingFitBtn:hover {
    background-color: rgba(87, 96, 111, 230);
    border: 1px solid rgba(255, 255, 255, 80);
}
"""

class CustomSpinBox(QWidget):
    valueChanged = Signal(int)

    def __init__(self, min_val=1, max_val=100, default=5, suffix="", parent=None):
        super().__init__(parent)
        self.setProperty("class", "CustomSpinBox")
        self._value = default
        self._min = min_val
        self._max = max_val
        self._suffix = suffix

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.edit = QLineEdit(str(default))
        self.edit.setFixedWidth(45)
        self.edit.setFixedHeight(30)
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.editingFinished.connect(self._on_edit)

        self.btn_up = QPushButton("▲")
        self.btn_up.setFixedSize(22, 14)
        self.btn_up.clicked.connect(self.step_up)

        self.btn_down = QPushButton("▼")
        self.btn_down.setFixedSize(22, 14)
        self.btn_down.clicked.connect(self.step_down)

        btn_layout = QVBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(1)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)

        layout.addWidget(self.edit)
        layout.addLayout(btn_layout)
        
        # 전체 위젯 크기 고정 (여백 문제 해결)
        self.setFixedWidth(75)

    def step_up(self):
        if self._value < self._max:
            self.setValue(self._value + 1)
            self.valueChanged.emit(self._value)

    def step_down(self):
        if self._value > self._min:
            self.setValue(self._value - 1)
            self.valueChanged.emit(self._value)

    def _on_edit(self):
        try:
            text = self.edit.text().replace(self._suffix, "").strip()
            val = int(text)
            self.setValue(val)
            self.valueChanged.emit(self._value)
        except ValueError:
            self.setValue(self._value)

    def value(self):
        return self._value

    def setValue(self, val):
        self._value = max(self._min, min(self._max, val))
        self.edit.setText(f"{self._value}{self._suffix}")

class DrawingCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setAlignment(Qt.AlignCenter)
        self.setBackgroundBrush(QBrush(QColor("#2f3640")))
        
        self.image_item = QGraphicsPixmapItem()
        self.scene().addItem(self.image_item)
        
        self.drawing = False
        self.last_point = QPoint()
        self.current_tool = "pen"
        self.pen_color = QColor(Qt.red)
        self.pen_width = 5
        self.saved_pen_width = 5 # 형광펜 전환 전 두께 저장용
        self.fill_color = QColor(255, 0, 0, 255)
        self.is_fill = False
        
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 20
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.panning = False
        self.pan_start = QPoint()
        
    def load_image(self, filepath):
        self.original_pixmap = QPixmap(filepath)
        self.image_item.setPixmap(self.original_pixmap)
        
        # 이미지 주변에 충분한 여백을 주어 모서리를 중앙으로 가져올 수 있게 함 (Overscroll)
        r = self.image_item.boundingRect()
        margin_w = r.width()
        margin_h = r.height()
        self.scene().setSceneRect(r.adjusted(-margin_w, -margin_h, margin_w, margin_h))
        
        self._push_undo()
        
    def _push_undo(self):
        self.undo_stack.append(self.image_item.pixmap().copy())
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        
    def undo(self):
        if len(self.undo_stack) > 1:
            self.redo_stack.append(self.undo_stack.pop())
            self.image_item.setPixmap(self.undo_stack[-1].copy())
            
    def redo(self):
        if self.redo_stack:
            pix = self.redo_stack.pop()
            self.undo_stack.append(pix.copy())
            self.image_item.setPixmap(pix)

    def _update_zoom_label(self):
        factor = int(self.transform().m11() * 100)
        if hasattr(self.window(), 'zoom_combo'):
            combo = self.window().zoom_combo
            combo.blockSignals(True)
            text = f"{factor}%"
            idx = combo.findText(text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentText(text)
            combo.blockSignals(False)

    def wheelEvent(self, event):
        zoom_in_factor = 1.05
        zoom_out_factor = 1 / zoom_in_factor
        
        # 1. 현재 마우스 위치의 씬 좌표 저장
        old_scene_pos = self.mapToScene(event.position().toPoint())
        
        # 2. 줌 배율 결정
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        # 3. 확대/축소 적용
        self.scale(zoom_factor, zoom_factor)
        
        # 4. 줌 적용 후 동일한 마우스 위치의 새로운 씬 좌표 계산
        new_scene_pos = self.mapToScene(event.position().toPoint())
        
        # 5. 두 씬 좌표의 차이만큼 뷰를 이동시켜 마우스 지점을 화면상에 고정
        delta = new_scene_pos - old_scene_pos
        self.translate(delta.x(), delta.y())
        
        # 수동 줌 조절 시 자동 맞춤 모드 해제
        if hasattr(self.window(), 'zoom_mode'):
            self.window().zoom_mode = 'manual'
            
        self._update_zoom_label()

    def mousePressEvent(self, event):
        self.setFocus()
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self.panning):
            self.pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.last_point = self.mapToScene(event.pos()).toPoint()
            self.start_point = self.last_point
            self.temp_pixmap = self.image_item.pixmap().copy()
            
    def mouseMoveEvent(self, event):
        # 1. 휠 버튼 드래그 이동 (Drag Pan)
        if (event.buttons() & Qt.MiddleButton):
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return

        # 2. 스페이스바 호버 이동 (Glide Pan - 클릭 불필요)
        if self.panning:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return

        pos = self.mapToScene(event.pos()).toPoint()
        
        # 상태바 도움말 갱신을 위해 부모에게 위치 알림 (필요시)
        if hasattr(self.window(), 'update_status_pos'):
            self.window().update_status_pos(pos.x(), pos.y())

        if self.drawing:
            if (self.current_tool == "pen" and event.modifiers() & Qt.ShiftModifier) or self.current_tool == "highlight":
                self._preview_step(pos, event.modifiers())
            elif self.current_tool == "pen":
                self._draw_step(pos, event.modifiers())
            else:
                # 도형 미리보기 (Preview)
                self._preview_step(pos, event.modifiers())
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self.panning):
            if self.panning:
                self.setCursor(Qt.OpenHandCursor)
            else:
                self.unsetCursor()
            return

        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            pos = self.mapToScene(event.pos()).toPoint()
            
            if self.current_tool in ["line", "arrow", "rect", "ellipse"] or (self.current_tool == "pen" and event.modifiers() & Qt.ShiftModifier) or self.current_tool == "highlight":
                self.image_item.setPixmap(self._get_final_drawing_pixmap(pos, event.modifiers()))
            elif self.current_tool == "mosaic":
                self._apply_mosaic(QRect(self.start_point, pos).normalized())
            elif self.current_tool == "text":
                self._add_text(self.start_point)
            elif self.current_tool == "crop":
                self._apply_crop(QRect(self.start_point, pos).normalized())
                
            self._push_undo()
            
            # 수정 상태 업데이트 (그리기 도구 사용 시)
            if self.current_tool != "crop": # 자르기는 별도 함수에서 처리
                if hasattr(self.window(), 'is_modified'):
                    self.window().is_modified = True
            
    def _get_final_drawing_pixmap(self, end_point, modifiers):
        # mouseMove의 preview 로직과 동일하게 최종본 생성
        final = self.temp_pixmap.copy()
        painter = QPainter(final)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        
        start = self.start_point
        end = end_point
        t = self.current_tool
        
        if t == "highlight":
            alpha_color = self.pen_color
            alpha_color.setAlpha(51)
            pen.setColor(alpha_color)
            end.setY(start.y())
            painter.setPen(pen)
            painter.drawLine(start, end)
        elif t == "pen" and modifiers & Qt.ShiftModifier:
            dx = abs(end.x() - start.x())
            dy = abs(end.y() - start.y())
            if dx > dy: end.setY(start.y())
            else: end.setX(start.x())
            painter.drawLine(start, end)
        elif t == "line": painter.drawLine(start, end)
        elif t == "arrow": self._draw_arrow(painter, start, end)
        elif t == "rect":
            rect = QRect(start, end).normalized()
            # 사각형은 모서리를 각지게 처리
            pen.setJoinStyle(Qt.MiterJoin)
            pen.setCapStyle(Qt.SquareCap)
            painter.setPen(pen)
            
            if self.is_fill:
                # 선 색상과 면 색상이 같으면 테두리 없이 면만 채워 경계면 문제 해결
                if self.pen_color.rgb() == self.fill_color.rgb() and self.fill_color.alpha() == 255:
                    painter.setPen(Qt.NoPen)
                painter.fillRect(rect, self.fill_color)
            painter.drawRect(rect)
        elif t == "ellipse":
            rect = QRect(start, end).normalized()
            if self.is_fill:
                if self.pen_color.rgb() == self.fill_color.rgb() and self.fill_color.alpha() == 255:
                    painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(self.fill_color))
            painter.drawEllipse(rect)
        painter.end()
        return final
            
    def _draw_step(self, end_point, modifiers):
        pixmap = self.image_item.pixmap()
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        
        if self.current_tool == "highlight":
            # 형광펜은 고정 20% 투명도 (사용자 요청)
            alpha_color = self.pen_color
            alpha_color.setAlpha(51) # 255 * 0.2 = 51
            pen.setColor(alpha_color)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            # 수평 고정
            end_point.setY(self.start_point.y())
        elif modifiers & Qt.ShiftModifier and self.current_tool == "pen":
            # Shift 누를 시 직선 (수직/수평 고정)
            dx = abs(end_point.x() - self.start_point.x())
            dy = abs(end_point.y() - self.start_point.y())
            if dx > dy: end_point.setY(self.start_point.y())
            else: end_point.setX(self.start_point.x())
            
        painter.setPen(pen)
        
        # 펜이나 형광펜 그리기
        if self.current_tool in ["pen", "highlight"]:
            if not (modifiers & Qt.ShiftModifier and self.current_tool == "pen"):
                # 일반 펜 드로잉 (Shift 직선은 Release에서 확정)
                painter.drawLine(self.last_point, end_point)
                self.last_point = end_point
            
        painter.end()
        self.image_item.setPixmap(pixmap)

    def _preview_step(self, end_point, modifiers):
        # 실시간 미리보기를 위해 복사본에 그리고 표시
        preview = self.temp_pixmap.copy()
        painter = QPainter(preview)
        painter.setRenderHint(QPainter.Antialiasing)
        
        pen = QPen(self.pen_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        if self.current_tool == "highlight":
            alpha_color = self.pen_color
            alpha_color.setAlpha(51)
            pen.setColor(alpha_color)
            end_point.setY(self.start_point.y())
        
        painter.setPen(pen)
        
        start = self.start_point
        end = end_point
        
        if self.current_tool == "pen" and modifiers & Qt.ShiftModifier:
            # Shift 직선 미리보기
            dx = abs(end.x() - start.x())
            dy = abs(end.y() - start.y())
            if dx > dy: end.setY(start.y())
            else: end.setX(start.x())
            painter.drawLine(start, end)
        elif self.current_tool == "highlight":
            painter.drawLine(start, end)
        elif self.current_tool == "line":
            painter.drawLine(start, end)
        elif self.current_tool == "arrow":
            self._draw_arrow(painter, start, end)
        elif self.current_tool == "rect":
            rect = QRect(start, end).normalized()
            # 사각형은 모서리를 각지게 처리
            pen.setJoinStyle(Qt.MiterJoin)
            pen.setCapStyle(Qt.SquareCap)
            painter.setPen(pen)
            
            if self.is_fill:
                if self.pen_color.rgb() == self.fill_color.rgb() and self.fill_color.alpha() == 255:
                    painter.setPen(Qt.NoPen)
                painter.fillRect(rect, self.fill_color)
            painter.drawRect(rect)
        elif self.current_tool == "ellipse":
            rect = QRect(start, end).normalized()
            if self.is_fill:
                if self.pen_color.rgb() == self.fill_color.rgb() and self.fill_color.alpha() == 255:
                    painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(self.fill_color))
            painter.drawEllipse(rect)
        elif self.current_tool == "mosaic":
            rect = QRect(start, end).normalized()
            painter.setPen(QPen(Qt.white, 1, Qt.DashLine))
            painter.drawRect(rect)
        elif self.current_tool == "crop":
            rect = QRect(start, end).normalized()
            painter.setPen(QPen(Qt.green, 2, Qt.DashLine))
            painter.drawRect(rect)
            
        painter.end()
        self.image_item.setPixmap(preview)
            
    def _apply_mosaic(self, rect):
        pixmap = self.image_item.pixmap()
        img = pixmap.toImage()
        target_rect = rect.intersected(img.rect())
        if target_rect.width() < 5 or target_rect.height() < 5: return
        
        region = img.copy(target_rect)
        small = region.scaled(max(1, target_rect.width() // 10), max(1, target_rect.height() // 10), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        mosaic = small.scaled(target_rect.width(), target_rect.height(), Qt.IgnoreAspectRatio, Qt.FastTransformation)
        
        painter = QPainter(pixmap)
        painter.drawImage(target_rect, mosaic)
        painter.end()
        self.image_item.setPixmap(pixmap)

    def _add_text(self, pos):
        text, ok = QInputDialog.getText(self, "텍스트 입력", "내용:")
        if ok and text:
            pixmap = self.image_item.pixmap()
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(self.pen_color))
            painter.setFont(QFont("Malgun Gothic", 20, QFont.Bold))
            painter.drawText(pos, text)
            painter.end()
            self.image_item.setPixmap(pixmap)

    def _apply_crop(self, rect):
        pixmap = self.image_item.pixmap()
        target_rect = rect.intersected(pixmap.rect())
        if target_rect.width() < 10 or target_rect.height() < 10: return
        
        cropped = pixmap.copy(target_rect)
        self.image_item.setPixmap(cropped)
        if hasattr(self.window(), 'is_modified'):
            self.window().is_modified = True
        
        # 자르기 후에도 여백 재설정
        r = cropped.boundingRect()
        margin_w = r.width()
        margin_h = r.height()
        self.scene().setSceneRect(r.adjusted(-margin_w, -margin_h, margin_w, margin_h))
        
        # 잘라내기 후 중앙 정렬을 위해 부모에게 알림 (옵션)
        if hasattr(self.window(), 'toggle_zoom'):
            self.window().toggle_zoom()

    def _draw_arrow(self, painter, start, end):
        painter.drawLine(start, end)
        angle = math.atan2(end.y() - start.y(), end.x() - start.x())
        size = self.pen_width * 4
        
        # 화살표 머리 지점 계산
        arrow_p1 = end - QPoint(int(size * math.cos(angle - math.pi/6)), int(size * math.sin(angle - math.pi/6)))
        arrow_p2 = end - QPoint(int(size * math.cos(angle + math.pi/6)), int(size * math.sin(angle + math.pi/6)))
        
        # 삼각형 내부 채우기 설정
        old_brush = painter.brush()
        painter.setBrush(QBrush(painter.pen().color()))
        painter.drawPolygon([end, arrow_p1, arrow_p2])
        painter.setBrush(old_brush) # 브러시 상태 복구

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.panning = True
            # 현재 마우스 위치를 시작점으로 저장
            self.pan_start = self.mapFromGlobal(QCursor.pos())
            self.setCursor(Qt.ClosedHandCursor)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self.panning = False
            self.unsetCursor()
            self.setDragMode(QGraphicsView.NoDrag)
        super().keyReleaseEvent(event)

    def get_current_pixmap(self):
        """현재 화면에 보이는 최종 이미지를 렌더링하여 반환 (QPixmap 캐시 이슈 방지)"""
        rect = self.image_item.boundingRect()
        img = QImage(rect.size().toSize(), QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        self.scene().render(painter, QRectF(img.rect()), rect)
        painter.end()
        return QPixmap.fromImage(img)

class ImageEditor(QMainWindow):
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.setWindowTitle(f"DS 이미지 편집기 - {os.path.basename(filepath)}")
        set_qt_window_icon(self)
        self.setStyleSheet(STYLE_SHEET)
        
        self._init_custom_colors()
        self.is_modified = False # 수정 여부 플래그
        self.canvas = DrawingCanvas()
        self.setCentralWidget(self.canvas)
        
        # 플로팅 화면 맞춤 버튼 추가 (닫기 버튼 아래쪽 위치 겨냥)
        self.fit_btn = QPushButton(self)
        self.fit_btn.setObjectName("FloatingFitBtn")
        self.fit_btn.setIcon(get_svg_icon("zoom_extents"))
        self.fit_btn.setIconSize(QSize(22, 22))
        self.fit_btn.setFixedSize(38, 38)
        self.fit_btn.setToolTip("화면 맞춤 (F)")
        self.fit_btn.setCursor(Qt.PointingHandCursor)
        self.fit_btn.clicked.connect(self.toggle_zoom)
        self.zoom_mode = 'fit'  # 'fit' 또는 'original'
        self._init_ui()
        self.canvas.load_image(filepath)
        
        self.resize(1400, 900)
        self.statusBar().showMessage("준비 완료")

    def _init_custom_colors(self):
        """그림판 스타일의 표준 색상 팔레트 설정"""
        palette = [
            "#000000", "#7F7F7F", "#880015", "#ED1C24", "#FF7F27", "#FFF200", "#22B14C", "#00A2E8", "#3F48CC", "#A349A4",
            "#FFFFFF", "#C3C3C3", "#B97A57", "#FFAEC9", "#FFC90E", "#EFE4B0", "#B5E61D", "#99D9EA", "#7092BE", "#C8BFE7",
            "#0E1111", "#232B2B", "#353839", "#414A4C", "#3B444B", "#2F4F4F", "#002147", "#191970", "#000080", "#003366"
        ]
        for i, hex_val in enumerate(palette):
            if i < 48: # Qt 커스텀 컬러 슬롯은 48개
                QColorDialog.setCustomColor(i, QColor(hex_val))
        
    def _init_ui(self):
        toolbar = QToolBar("메인 도구")
        toolbar.setIconSize(QSize(28, 28))
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        
        # [그룹 1: 저장 및 복사]
        save_act = QAction(get_svg_icon("save"), "저장 (SAVE)", self)
        save_act.setShortcut(QKeySequence.Save)
        save_act.setStatusTip("원본_mod 형식으로 같은 폴더에 저장합니다.")
        save_act.triggered.connect(self.save_image)
        toolbar.addAction(save_act)
        
        save_as_act = QAction(get_svg_icon("save_as"), "다른 이름으로 저장", self)
        save_as_act.setStatusTip("다른 이름으로 이미지를 저장합니다.")
        save_as_act.triggered.connect(self.save_as_image)
        toolbar.addAction(save_as_act)
        
        copy_act = QAction(get_svg_icon("copy"), "클립보드 복사 (Ctrl+C)", self)
        copy_act.setShortcut(QKeySequence.Copy)
        copy_act.setStatusTip("현재 이미지를 클립보드에 복사합니다(Ctrl+C).")
        copy_act.triggered.connect(self.copy_to_clipboard)
        toolbar.addAction(copy_act)
        
        toolbar.addSeparator()

        # [그룹 2: 실행 취소 및 재실행]
        undo_act = QAction(get_svg_icon("undo"), "실행 취소", self)
        undo_act.setShortcut(QKeySequence.Undo)
        undo_act.triggered.connect(self.canvas.undo)
        toolbar.addAction(undo_act)
        
        redo_act = QAction(get_svg_icon("redo"), "재실행", self)
        redo_act.setShortcut(QKeySequence.Redo)
        redo_act.triggered.connect(self.canvas.redo)
        toolbar.addAction(redo_act)
        
        toolbar.addSeparator()

        # [그룹 3: 그리기 도구]
        tools = [
            ("pen", "펜", "자유롭게 그리기 (Shift: 직선)", "pen"),
            ("line", "직선", "직선 그리기", "line"),
            ("arrow", "화살표", "화살표 그리기 (선 두께 조정 시 머리 크기 조정)", "arrow"),
            ("rect", "사각형", "사각형 그리기", "rect"),
            ("ellipse", "원", "원 그리기", "ellipse"),
            ("highlight", "형광펜", "반투명 형광펜 (수직 고정)", "highlight"),
            ("mosaic", "모자이크", "영역 모자이크 처리", "mosaic"),
            ("text", "텍스트", "글자 입력", "text")
        ]

        self.tool_actions = {}
        for tool_id, name, help_text, icon_key in tools:
            action = QAction(get_svg_icon(icon_key), name, self)
            action.setCheckable(True)
            action.setToolTip(name)
            action.setStatusTip(help_text)
            action.triggered.connect(lambda checked, t=tool_id: self.set_tool(t))
            toolbar.addAction(action)
            self.tool_actions[tool_id] = action

        self.tool_actions["pen"].setChecked(True)
        
        toolbar.addSeparator()

        # [변형 도구 그룹]
        crop_action = QAction(get_svg_icon("crop"), "자르기", self)
        crop_action.setCheckable(True)
        crop_action.setToolTip("이미지 자르기")
        crop_action.setStatusTip("이미지 자르기")
        crop_action.triggered.connect(lambda checked: self.set_tool("crop"))
        toolbar.addAction(crop_action)
        self.tool_actions["crop"] = crop_action
        
        rotate_ccw_act = QAction(get_svg_icon("rotate_ccw"), "왼쪽 90도 회전", self)
        rotate_ccw_act.setStatusTip("이미지를 반시계 방향으로 90도 회전합니다.")
        rotate_ccw_act.triggered.connect(lambda: self.rotate_image(-90))
        toolbar.addAction(rotate_ccw_act)
        
        rotate_cw_act = QAction(get_svg_icon("rotate"), "오른쪽 90도 회전", self)
        rotate_cw_act.setStatusTip("이미지를 시계 방향으로 90도 회전합니다.")
        rotate_cw_act.triggered.connect(lambda: self.rotate_image(90))
        toolbar.addAction(rotate_cw_act)

        toolbar.addSeparator()
        
        # 선 두께 설정
        toolbar.addWidget(QLabel(" 선 두께 "))
        self.width_spin = CustomSpinBox(1, 100, self.canvas.pen_width)
        self.width_spin.valueChanged.connect(self._change_width)
        toolbar.addWidget(self.width_spin)
        
        toolbar.addSeparator()
        
        # 선 색상 선택 버튼
        toolbar.addWidget(QLabel(" 선 색상 "))
        self.stroke_color_btn = QWidget()
        self.stroke_color_btn.setFixedSize(24, 24)
        self.stroke_color_btn.setCursor(Qt.PointingHandCursor)
        self.stroke_color_btn.setStyleSheet(f"background-color: {self.canvas.pen_color.name()}; border: 2px solid white; border-radius: 4px;")
        self.stroke_color_btn.mousePressEvent = lambda e: self._pick_color("stroke")
        toolbar.addWidget(self.stroke_color_btn)
        
        toolbar.addSeparator()

        # 채우기 사용 여부 및 색상
        fill_act = QAction(get_svg_icon("fill"), "채우기 사용", self)
        fill_act.setCheckable(True)
        fill_act.setChecked(self.canvas.is_fill)
        fill_act.triggered.connect(self._toggle_fill)
        toolbar.addAction(fill_act)

        toolbar.addWidget(QLabel(" 채우기 색상 "))
        self.fill_color_btn = QWidget()
        self.fill_color_btn.setFixedSize(24, 24)
        self.fill_color_btn.setCursor(Qt.PointingHandCursor)
        self.fill_color_btn.setStyleSheet(f"background-color: {self.canvas.fill_color.name(QColor.HexArgb)}; border: 2px solid #555; border-radius: 4px;")
        self.fill_color_btn.mousePressEvent = lambda e: self._pick_color("fill")
        toolbar.addWidget(self.fill_color_btn)
        
        toolbar.addSeparator()

        # 채우기 불투명도 설정
        toolbar.addWidget(QLabel(" 불투명도(%) "))
        self.alpha_spin = CustomSpinBox(0, 100, int(self.canvas.fill_color.alpha() / 255 * 100))
        self.alpha_spin.valueChanged.connect(self._change_alpha)
        toolbar.addWidget(self.alpha_spin)
        
        self.statusBar().setStyleSheet("QStatusBar::item { border: None; }")
        
        # 줌 퍼센트 표시 및 선택용 콤보박스
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.addItems(["10%", "25%", "50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%", "500%"])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setFixedWidth(90)
        self.zoom_combo.setFixedHeight(30)
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_combo_changed)
        self.statusBar().addPermanentWidget(self.zoom_combo)
        
    def _on_zoom_combo_changed(self, text):
        try:
            val = int(text.replace("%", ""))
            factor = val / 100.0
            # 현재 줌을 리셋하고 원하는 비율로 설정
            self.canvas.resetTransform()
            self.canvas.scale(factor, factor)
        except:
            pass
        
    def _change_width(self, val):
        self.canvas.pen_width = val

    def _change_alpha(self, val):
        # 0-100% 를 0-255 로 변환하여 적용
        alpha = int(val / 100 * 255)
        color = self.canvas.fill_color
        color.setAlpha(alpha)
        self.canvas.fill_color = color
        # 버튼 색상 업데이트
        border = "white" if self.canvas.is_fill else "#555"
        self.fill_color_btn.setStyleSheet(f"background-color: {color.name(QColor.HexArgb)}; border: 2px solid {border}; border-radius: 4px;")
        
    def _toggle_fill(self, checked):
        self.canvas.is_fill = checked
        self.fill_color_btn.setEnabled(checked)
        self.alpha_spin.setEnabled(checked)
        
        if checked:
            # 체크 시 선 색상을 채우기 색상으로 자동 매칭 (알파값은 현재 스핀박스 값 유지)
            new_fill_color = QColor(self.canvas.pen_color)
            alpha = int(self.alpha_spin.value() / 100 * 255)
            new_fill_color.setAlpha(alpha)
            self.canvas.fill_color = new_fill_color
            
        border = "white" if checked else "#555"
        self.fill_color_btn.setStyleSheet(f"background-color: {self.canvas.fill_color.name(QColor.HexArgb)}; border: 2px solid {border}; border-radius: 4px;")

    def _pick_color(self, type="stroke"):
        if type == "stroke":
            color = QColorDialog.getColor(self.canvas.pen_color, self, "선 색상 선택")
            if color.isValid():
                self.canvas.pen_color = color
                self.stroke_color_btn.setStyleSheet(f"background-color: {color.name()}; border: 2px solid white; border-radius: 4px;")
        else:
            # 채우기 색상은 알파 제외하고 선택 (외부 UI에서 관리)
            color = QColorDialog.getColor(self.canvas.fill_color, self, "채우기 색상 선택")
            if color.isValid():
                # 기존 알파값 유지
                color.setAlpha(self.canvas.fill_color.alpha())
                self.canvas.fill_color = color
                border = "white" if self.canvas.is_fill else "#555"
                self.fill_color_btn.setStyleSheet(f"background-color: {color.name(QColor.HexArgb)}; border: 2px solid {border}; border-radius: 4px;")
        
    def set_tool(self, tool_id):
        # 형광펜 전환 전 두께 저장 및 복원 로직
        if self.canvas.current_tool != "highlight" and tool_id == "highlight":
            self.canvas.saved_pen_width = self.canvas.pen_width
            self.canvas.pen_width = 25
            self.width_spin.setValue(25)
        elif self.canvas.current_tool == "highlight" and tool_id != "highlight":
            self.canvas.pen_width = self.canvas.saved_pen_width
            self.width_spin.setValue(self.canvas.saved_pen_width)

        for tid, act in self.tool_actions.items():
            act.setChecked(tid == tool_id)
        self.canvas.current_tool = tool_id
        self.statusBar().showMessage(f"선택된 도구: {self.tool_actions[tool_id].text()}")

    def update_status_pos(self, x, y):
        self.statusBar().showMessage(f"좌표: ({x}, {y})")

    def rotate_image(self, angle):
        """이미지를 회전 (angle: 90이면 시계방향, -90이면 반시계방향)"""
        if not self.canvas.image_item or self.canvas.image_item.pixmap().isNull():
            return
            
        # 1. 현재 픽스맵 가져오기
        pixmap = self.canvas.image_item.pixmap()
        
        # 2. 회전 적용
        transform = QTransform().rotate(angle)
        rotated_pixmap = pixmap.transformed(transform, Qt.SmoothTransformation)
        
        # 3. 캔버스 업데이트
        self.canvas.image_item.setPixmap(rotated_pixmap)
        
        # 4. 씬 영역 재설정 (이미지 크기가 변했으므로 여백 포함 재계산)
        r = self.canvas.image_item.boundingRect()
        margin_w = r.width()
        margin_h = r.height()
        self.canvas.scene().setSceneRect(r.adjusted(-margin_w, -margin_h, margin_w, margin_h))
        
        # 5. Undo 스택에 추가 및 수정 상태 업데이트
        self.canvas._push_undo()
        self.is_modified = True
        
        # 6. 회전 후 항상 화면 맞춤(Fit) 적용 및 중앙 정렬
        self.canvas.fitInView(self.canvas.image_item.boundingRect(), Qt.KeepAspectRatio)
        self.canvas.centerOn(self.canvas.image_item)
        self.zoom_mode = 'fit'
        self.canvas._update_zoom_label()
            
        direction = "시계 방향" if angle > 0 else "반시계 방향"
        self.statusBar().showMessage(f"{direction} 90도 회전 완료", 2000)

    def save_image(self):
        # settings.json에서 최신 저장 경로 불러오기
        save_dir = os.path.dirname(self.filepath)
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if config.get("save_dir"):
                        save_dir = config.get("save_dir")
        except: pass

        # 원본_mod 이름 생성 (이미 _mod인 경우 중복 방지)
        base_name, ext = os.path.splitext(os.path.basename(self.filepath))
        
        if base_name.endswith("_mod"):
            new_name = f"{base_name}{ext}"
        else:
            new_name = f"{base_name}_mod{ext}"
            
        target_path = os.path.join(save_dir, new_name)
        
        # 덮어쓰기 확인
        if os.path.exists(target_path):
            reply = QMessageBox.question(self, "덮어쓰기 확인", 
                                       f"이미 수정된 파일이 존재합니다:\n{new_name}\n\n덮어씌우시겠습니까?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        self.canvas.get_current_pixmap().save(target_path)
        QMessageBox.information(self, "저장 완료", f"이미지가 저장되었습니다:\n{new_name}")
        self.is_modified = False

    def save_as_image(self):
        # 최신 저장 경로를 초기 디렉토리로 설정
        init_dir = os.path.dirname(self.filepath)
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if config.get("save_dir"):
                        init_dir = config.get("save_dir")
        except: pass

        path, _ = QFileDialog.getSaveFileName(self, "다른 이름으로 저장", init_dir, "Images (*.png *.jpg *.bmp)")
        if path:
            self.canvas.get_current_pixmap().save(path)
            self.filepath = path
            self.setWindowTitle(f"DS 이미지 편집기 - {os.path.basename(path)}")
            self.is_modified = False

    def copy_to_clipboard(self):
        """현재 캔버스의 이미지를 클립보드에 표준 DIB 형식으로 복사"""
        pixmap = self.canvas.get_current_pixmap()
        if pixmap.isNull(): return
        
        # QPixmap -> 비트맵 데이터를 위해 메모리 버퍼 대신 임시 파일 사용 (PySide6 호환성 문제 방지)
        import tempfile
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".bmp")
        os.close(tmp_fd)
        pixmap.toImage().save(tmp_path, "BMP")
        
        with open(tmp_path, "rb") as f:
            data = f.read()[14:] # BMP 헤더 14바이트 제외
            
        try:
            os.remove(tmp_path)
        except:
            pass
        
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            self.statusBar().showMessage("클립보드에 복사되었습니다.", 3000)
        except Exception as e:
            QMessageBox.warning(self, "복사 실패", f"클립보드에 복사할 수 없습니다: {e}")

    def toggle_zoom(self):
        """화면 맞춤(Fit)과 100% 배율을 토글함"""
        if not self.canvas.image_item or self.canvas.image_item.pixmap().isNull():
            return
            
        # 상태에 따른 토글
        if self.zoom_mode == 'fit':
            # 현재 화면 맞춤 상태라면 -> 100% 배율로
            self.canvas.resetTransform()
            self.canvas.centerOn(self.canvas.image_item)
            self.zoom_mode = 'original'
            self.statusBar().showMessage("배율: 100%", 2000)
        else:
            # 그 외의 경우(100% 상태거나 수동 조절 중) -> 화면 맞춤으로
            self.canvas.fitInView(self.canvas.image_item.boundingRect(), Qt.KeepAspectRatio)
            self.canvas.centerOn(self.canvas.image_item)
            self.zoom_mode = 'fit'
            self.statusBar().showMessage("화면 맞춤 적용됨", 2000)
            
        self.canvas._update_zoom_label()

    def showEvent(self, event):
        super().showEvent(event)
        # 창이 완전히 뜬 후 화면 맞춤 수행
        if not self.canvas.image_item.pixmap().isNull():
            self.canvas.fitInView(self.canvas.image_item.boundingRect(), Qt.KeepAspectRatio)
            self.canvas.centerOn(self.canvas.image_item)
            self.canvas._update_zoom_label()
            self.zoom_mode = 'fit'

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 창 크기 변경 시(최대화 포함) 화면 맞춤 모드라면 계속 유지
        if self.zoom_mode == 'fit' and not self.canvas.image_item.pixmap().isNull():
            self.canvas.fitInView(self.canvas.image_item.boundingRect(), Qt.KeepAspectRatio)
            self.canvas.centerOn(self.canvas.image_item)
            self.canvas._update_zoom_label()
        
        # 플로팅 버튼 위치 조정 (우측 상단 닫기 버튼 아래 영역)
        if hasattr(self, 'fit_btn'):
            # 마진 10px 정도 주어 우측 상단 배치
            self.fit_btn.move(self.width() - self.fit_btn.width() - 20, 60)
            self.fit_btn.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Space:
            # 스페이스바는 캔버스로 전달
            self.canvas.keyPressEvent(event)
            return
        elif event.key() == Qt.Key_F:
            # 화면 맞춤 (Fit)
            self.toggle_zoom()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        """창을 닫을 때 수정 사항이 있으면 확인창 표시"""
        if self.is_modified:
            reply = QMessageBox.question(
                self, '저장되지 않은 변경 사항',
                "수정된 내용이 있습니다. 저장하지 않고 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.canvas.keyReleaseEvent(event)
            return
        super().keyReleaseEvent(event)

def run_editor(img_path):
    app = QApplication(sys.argv)
    # 스타일을 Fusion으로 고정하여 CSS 일관성 확보
    app.setStyle("Fusion")
    
    # 기본 폰트 설정
    font = QFont("Malgun Gothic", 10)
    app.setFont(font)
    
    editor = ImageEditor(img_path)
    editor.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        run_editor(sys.argv[1])
