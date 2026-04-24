import sys, json, os
from datetime import datetime, date
from PyQt6.QtWidgets import (QApplication, QWidget, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLineEdit, QListWidget,
                             QListWidgetItem, QDateTimeEdit, QDialog, QLabel,
                             QMenu, QAbstractItemView, QSizeGrip)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class DDLDialog(QDialog):
    def __init__(self, current_dt=None):
        super().__init__()
        self.setWindowTitle("设置截止日期")
        layout = QVBoxLayout(self)
        self.dt_edit = QDateTimeEdit(current_dt or QDateTime.currentDateTime().addDays(1))
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setDisplayFormat("yyyy-MM-dd")
        btn = QPushButton("确定")
        btn.clicked.connect(self.accept)
        layout.addWidget(QLabel("选择截止日期:"))
        layout.addWidget(self.dt_edit)
        layout.addWidget(btn)

class QuadrantNote(QWidget):
    def __init__(self):
        super().__init__()
        self.save_file = "notes_data.json"
        self.m_drag = self.m_resizable = self.is_pinned = False
        self.margin = 20 # 判定范围

        self.initUI()
        self.load_data()

        self.sentinel = QTimer(self)
        self.sentinel.timeout.connect(self.check_pin_state)
        self.sentinel.start(1000)

    def initUI(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window | Qt.WindowType.WindowMinMaxButtonsHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setWindowOpacity(0.9)
        self.setMinimumSize(450, 500)
        self.resize(600, 600)
        self.setWindowIcon(QIcon(resource_path("icon.ico")))

        self.main_v_layout = QVBoxLayout(self)
        self.main_v_layout.setContentsMargins(0, 0, 0, 0)
        self.main_v_layout.setSpacing(0)

        # --- 标题栏 ---
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet(
            "background-color: rgba(45, 45, 45, 230); border-top-left-radius: 12px; border-top-right-radius: 12px;")
        title_layout = QHBoxLayout(self.title_bar)

        self.fixed_title_label = QLabel("四象限便签——RXM")
        self.fixed_title_label.setStyleSheet("color: #eee; font-weight: bold; background: transparent; padding-left: 5px;")

        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(22, 22)
        self.pin_btn.setStyleSheet("color: white; border: none; font-size: 14px;")
        self.pin_btn.clicked.connect(self.toggle_pin)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setStyleSheet("background-color: #ff5f56; color: white; border-radius: 11px; border: none;")
        close_btn.clicked.connect(self.close)

        title_layout.addWidget(self.fixed_title_label); title_layout.addStretch()
        title_layout.addWidget(self.pin_btn); title_layout.addWidget(close_btn)

        # --- 网格容器 ---
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet(
            "background-color: rgba(255, 255, 255, 190); border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;")
        grid_layout = QGridLayout(self.grid_container)
        grid_layout.setSpacing(10)
        grid_layout.setContentsMargins(10, 10, 10, 20) # 底部留出一点手柄空间

        self.quadrant_titles, self.list_widgets = [], []
        configs = [("重要·紧急", "#FFB3BA"), ("重要·不紧急", "#BAFFC9"), ("不重要·紧急", "#FFFFBA"), ("不重要·不紧急", "#E0E0E0")]

        for i, (def_title, color) in enumerate(configs):
            container = QWidget()
            container.setStyleSheet(f"background-color: {color}; border-radius: 10px;")
            v_box = QVBoxLayout(container)
            t_edit = QLineEdit(def_title)
            t_edit.setStyleSheet("font-weight: bold; background: transparent; border: none;")
            t_edit.textChanged.connect(self.save_data)
            lw = QListWidget()
            lw.setStyleSheet("border: none; background: transparent;")
            lw.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
            lw.setDefaultDropAction(Qt.DropAction.MoveAction)
            lw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            lw.customContextMenuRequested.connect(lambda pos, w=lw: self.show_menu(pos, w))
            lw.itemDoubleClicked.connect(self.on_item_double_clicked)
            lw.itemChanged.connect(self.on_item_changed)
            lw.model().rowsMoved.connect(self.save_data)
            add_btn = QPushButton("+ 新增事项")
            add_btn.setStyleSheet("text-align: left; color: #666; background: transparent; border: none; font-size: 11px;")
            add_btn.clicked.connect(lambda _, w=lw: self.add_task(w))
            v_box.addWidget(t_edit); v_box.addWidget(lw); v_box.addWidget(add_btn)
            self.quadrant_titles.append(t_edit); self.list_widgets.append(lw)
            grid_layout.addWidget(container, i // 2, i % 2)

        self.main_v_layout.addWidget(self.title_bar)
        self.main_v_layout.addWidget(self.grid_container)

        # --- 新增：右下角拉伸斜杠手柄 ---
        self.size_grip = QSizeGrip(self)
        self.size_grip.setFixedSize(20, 20)
        self.size_grip.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        # 只有在非固定状态下才画斜杠
        if not self.is_pinned:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(100, 100, 100, 150))
            pen.setWidth(2)
            painter.setPen(pen)
            # 在右下角画三条拉伸斜杠
            w, h = self.width(), self.height()
            painter.drawLine(w-15, h-5, w-5, h-15)
            painter.drawLine(w-11, h-5, w-5, h-11)
            painter.drawLine(w-7, h-5, w-5, h-7)

    def resizeEvent(self, event):
        # 手柄位置永远保持在右下角
        self.size_grip.move(self.width() - self.size_grip.width(), self.height() - self.size_grip.height())
        super().resizeEvent(event)

    def toggle_pin(self):
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.title_bar.hide()
            self.size_grip.hide() # 固定时隐藏手柄
            self.grid_container.setStyleSheet("background-color: rgba(255, 255, 255, 100); border-radius: 12px;")
            self.pin_btn.setText("📍"); self.lower()
        else:
            self.title_bar.show()
            self.size_grip.show() # 取消固定显示手柄
            self.grid_container.setStyleSheet("background-color: rgba(255, 255, 255, 190); border-bottom-left-radius: 12px; border-bottom-right-radius: 12px;")
            self.pin_btn.setText("📌"); self.raise_()
        self.update() # 重新触发重绘

    def check_pin_state(self):
        if self.is_pinned and (self.isMinimized() or not self.isVisible()):
            self.showNormal(); self.lower()

    def mouseDoubleClickEvent(self, event):
        if self.is_pinned: self.toggle_pin()

    def mousePressEvent(self, event):
        if self.is_pinned or event.button() != Qt.MouseButton.LeftButton: return
        pos = event.position().toPoint()
        if self.title_bar.geometry().contains(pos):
            self.m_drag = True
            self.m_DragPosition = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.m_drag and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.m_DragPosition)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.m_drag = False
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def add_task(self, lw, text="", checked=False, ddl=""):
        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setData(Qt.ItemDataRole.UserRole, ddl)
        lw.addItem(item)
        if not text: lw.editItem(item)
        else: self.update_display(item)
        self.save_data()

    def on_item_double_clicked(self, item):
        item.listWidget().blockSignals(True)
        item.setText(item.text().split("  [")[0])
        item.listWidget().blockSignals(False)

    def on_item_changed(self, item):
        self.update_display(item); self.save_data()

    def update_display(self, item):
        lw = item.listWidget()
        if not lw: return
        base_text, ddl_str = item.text().split("  [")[0], item.data(Qt.ItemDataRole.UserRole)
        display_text = base_text
        if ddl_str:
            try:
                delta = (datetime.strptime(ddl_str, "%Y-%m-%d").date() - date.today()).days
                display_text += f"  [{'剩 ' + str(delta) if delta > 0 else '今天' if delta == 0 else '逾期 ' + str(abs(delta))} 天]"
            except: pass
        lw.blockSignals(True)
        item.setText(display_text)
        font = item.font(); is_done = item.checkState() == Qt.CheckState.Checked
        font.setStrikeOut(is_done); item.setFont(font)
        item.setForeground(QColor("#888888" if is_done else "#333333"))
        lw.blockSignals(False)

    def show_menu(self, pos, lw):
        item = lw.itemAt(pos)
        if not item: return
        menu = QMenu()
        set_act, clear_act, del_act = menu.addAction("📅 设置日期"), menu.addAction("清空日期"), menu.addAction("删除任务")
        action = menu.exec(lw.mapToGlobal(pos))
        if action == set_act:
            cur_data = item.data(Qt.ItemDataRole.UserRole)
            dialog = DDLDialog(QDateTime.fromString(cur_data, "yyyy-MM-dd") if cur_data else None)
            if dialog.exec():
                item.setData(Qt.ItemDataRole.UserRole, dialog.dt_edit.date().toString("yyyy-MM-dd"))
                self.update_display(item); self.save_data()
        elif action == clear_act:
            item.setData(Qt.ItemDataRole.UserRole, ""); self.update_display(item); self.save_data()
        elif action == del_act:
            lw.takeItem(lw.row(item)); self.save_data()

    def save_data(self):
        data = {"quadrants": []}
        for i in range(4):
            lw = self.list_widgets[i]
            tasks = [{"text": lw.item(j).text().split("  [")[0], "done": lw.item(j).checkState() == Qt.CheckState.Checked, "ddl": lw.item(j).data(Qt.ItemDataRole.UserRole)} for j in range(lw.count())]
            data["quadrants"].append({"title": self.quadrant_titles[i].text(), "tasks": tasks})
        with open(self.save_file, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

    def load_data(self):
        if not os.path.exists(self.save_file): return
        try:
            with open(self.save_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for i, qd in enumerate(data.get("quadrants", [])):
                    if i < 4:
                        self.quadrant_titles[i].setText(qd["title"])
                        for t in qd.get("tasks", []): self.add_task(self.list_widgets[i], t["text"], t["done"], t.get("ddl", ""))
        except: pass

    def wheelEvent(self, event):
        o = self.windowOpacity()
        self.setWindowOpacity(min(1.0, max(0.2, o + (0.05 if event.angleDelta().y() > 0 else -0.05))))

if __name__ == '__main__':
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rxm.quadrant.v1")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path("icon.ico")))
    ex = QuadrantNote(); ex.show()
    sys.exit(app.exec())