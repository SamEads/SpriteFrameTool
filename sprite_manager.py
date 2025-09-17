import os, json

from PySide6.QtWidgets import ( 
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QGridLayout,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QGraphicsView,
    QGraphicsScene
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPixmap,
    QImage,
    QPen,
    QAction,
    QKeySequence
)
from PySide6.QtCore import Qt, QRectF

class ImageView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom = 1.0

    def wheelEvent(self, event):
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self._zoom *= zoomFactor
        self.scale(zoomFactor, zoomFactor)
        event.accept()

    def resetZoom(self):
        self.resetTransform()
        self._zoom = 1.0

class SpriteManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sprite Frame Tool")
        self.resize(700, 800)
        self.data = {}
        self.image_paths = []
        self.current_path = None
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.setup_ui()
        save_action = QAction(self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.export_json)
        self.addAction(save_action)

    def setup_ui(self):
        # main layout
        central = QWidget()
        splitter = QSplitter()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.addWidget(splitter)

        # left panel widget
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.addWidget(QLabel("Images"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        left.addWidget(self.tree, 10)
        self.btn_folder = QPushButton("Select Folder")
        self.btn_folder.clicked.connect(self.load_folder)
        left.addWidget(self.btn_folder)
        btn_export = QPushButton("Save")
        btn_export.clicked.connect(self.export_json)
        left.addWidget(btn_export)
        splitter.addWidget(left_widget)

        # right panel widget
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        self.graphics = ImageView()
        self.scene = QGraphicsScene()
        self.graphics.setScene(self.scene)
        right.addWidget(self.graphics, 10)

        controls = QGridLayout()
        right.addLayout(controls)
        controls.addWidget(QLabel("Frame Width"), 0, 0)
        self.width_entry = QLineEdit()
        self.width_entry.setFixedWidth(90)
        controls.addWidget(self.width_entry, 0, 1)
        controls.addWidget(QLabel("Frame Height"), 0, 2)
        self.height_entry = QLineEdit()
        self.height_entry.setFixedWidth(90)
        controls.addWidget(self.height_entry, 0, 3)
        controls.addWidget(QLabel("Frame Count X"), 1, 0)
        self.count_x_entry = QLineEdit()
        self.count_x_entry.setFixedWidth(90)
        controls.addWidget(self.count_x_entry, 1, 1)
        controls.addWidget(QLabel("Frame Count Y"), 1, 2)
        self.count_y_entry = QLineEdit()
        self.count_y_entry.setFixedWidth(90)
        controls.addWidget(self.count_y_entry, 1, 3)
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self.apply_frame)
        right.addWidget(btn_apply)
        splitter.addWidget(right_widget)

        # signals
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        self.width_entry.textChanged.connect(self.on_width_height_change)
        self.height_entry.textChanged.connect(self.on_width_height_change)
        self.count_x_entry.textChanged.connect(self.on_count_change)
        self.count_y_entry.textChanged.connect(self.on_count_change)

    def load_folder(self):
        # just refresh existing folder and assume the one that's open stays
        if hasattr(self, 'current_folder') and self.current_folder:
            folder = self.current_folder
        else:
            folder = QFileDialog.getExistingDirectory(self, "Select Folder")
            if not folder:
                return
            self.current_folder = folder
            self.btn_folder.setText("Refresh Folder")
            self.btn_folder.clicked.disconnect()
            self.btn_folder.clicked.connect(self.load_folder)
        
        self.image_paths = []
        self.tree.clear()
        
        # load frame data from json if there is one already
        json_path = os.path.join(folder, "data.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r") as f:
                    loaded = json.load(f)
                self.data = {os.path.join(folder, k): v for k, v in loaded.items()}
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load data.json: {e}")
                self.data = {}
        else:
            self.data = {}
        # build tree structure, folders first, but DONT show top-level folder node
        node_map = {}
        for root, dirs, files in os.walk(folder):
            rel_root = os.path.relpath(root, folder)
            if rel_root == ".":
                parent = self.tree
            else:
                parent = node_map.get(os.path.dirname(root), self.tree)
                node_id = QTreeWidgetItem(parent, [os.path.basename(root)])
                node_map[root] = node_id
                parent = node_id
            dirs.sort()
            files.sort()
            for d in dirs:
                pass
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    path = os.path.join(root, f)
                    self.image_paths.append(path)
                    item = QTreeWidgetItem(parent, [f])
                    item.setData(0, Qt.UserRole, path)
                    if path not in self.data:
                        item.setBackground(0, QBrush(QColor(120, 120, 40)))
                        font = item.font(0)
                        font.setBold(True)
                        item.setFont(0, font)
        
        # remove deleted images from json
        valid_paths = set(self.image_paths)
        self.data = {k: v for k, v in self.data.items() if k in valid_paths}

    def on_tree_select(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
        item = selected[0]
        path = item.data(0, Qt.UserRole)
        if path:
            self.current_path = path
            self.zoom = 1.0
            self.pan_x = 0
            self.pan_y = 0
            self.graphics.resetZoom()
            self.show_image()

    def show_image(self):
        path = self.current_path
        if not path or not os.path.exists(path):
            self.scene.clear()
            return
        img = QImage(path)
        if img.isNull():
            self.scene.clear()
            return
        pixmap = QPixmap.fromImage(img)
        
        # apply zoom
        zoomed_pixmap = pixmap.scaled(pixmap.width() * self.zoom, pixmap.height() * self.zoom, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.scene.clear()
        
        light_brush = QBrush(Qt.darkGray)
        self.scene.addRect(0, 0, zoomed_pixmap.width(), zoomed_pixmap.height(), brush=light_brush)
        self.scene.addPixmap(zoomed_pixmap)
        self.graphics.setSceneRect(QRectF(0, 0, zoomed_pixmap.width(), zoomed_pixmap.height()))
        
        entry = self.data.get(path)
        if entry:
            self.width_entry.setText(str(entry["frame_width"]))
            self.height_entry.setText(str(entry["frame_height"]))
            self.count_x_entry.setText(str(entry.get("frame_count_x", "")))
            self.count_y_entry.setText(str(entry.get("frame_count_y", "")))
        else:
            self.width_entry.clear()
            self.height_entry.clear()
            self.count_x_entry.clear()
            self.count_y_entry.clear()
        if entry:
            fw = entry.get("frame_width")
            fh = entry.get("frame_height")
            count_x = entry.get("frame_count_x")
            count_y = entry.get("frame_count_y")
        else:
            try:
                fw = int(self.width_entry.text())
                fh = int(self.height_entry.text())
                count_x = int(self.count_x_entry.text())
                count_y = int(self.count_y_entry.text())
            except Exception:
                fw = fh = count_x = count_y = None
        if fw and fh and count_x and count_y:
            pen = QPen(QColor(0, 225, 255))
            width = zoomed_pixmap.width()
            height = zoomed_pixmap.height()
            # vert lines
            for i in range(count_x + 1):
                x = i * fw * self.zoom
                if i == count_x:
                    x = width
                self.scene.addLine(x, 0, x, height, pen)
                
            # horizontal lines
            for j in range(count_y + 1):
                y = j * fh * self.zoom
                if j == count_y:
                    y = height
                self.scene.addLine(0, y, width, y, pen)

    def apply_frame(self):
        if not self.current_path:
            return
        img = QImage(self.current_path)
        w, h = img.width(), img.height()
        fw_text = self.width_entry.text()
        fh_text = self.height_entry.text()
        count_x_text = self.count_x_entry.text()
        count_y_text = self.count_y_entry.text()
        
        # if all fields are blank, set everything to image size and 1
        if not fw_text and not fh_text and not count_x_text and not count_y_text:
            fw, fh = w, h
            count_x, count_y = 1, 1
            self.width_entry.setText(str(fw))
            self.height_entry.setText(str(fh))
            self.count_x_entry.setText("1")
            self.count_y_entry.setText("1")
        elif count_x_text and count_y_text:
            try:
                count_x = int(count_x_text)
                count_y = int(count_y_text)
                if count_x <= 0 or count_y <= 0:
                    QMessageBox.critical(self, "Error", "Frame count X and Y must be greater than 0.")
                    return
                fw = w // count_x
                fh = h // count_y
                self.width_entry.setText(str(fw))
                self.height_entry.setText(str(fh))
            except ValueError:
                QMessageBox.critical(self, "Error", "Enter valid integers for frame count")
                return
        fw_text = self.width_entry.text()
        fh_text = self.height_entry.text()
        try:
            fw = int(fw_text)
            fh = int(fh_text)
            if fw <= 0 or fh <= 0:
                QMessageBox.critical(self, "Error", "Frame width and height must be greater than 0.")
                return
        except ValueError:
            QMessageBox.critical(self, "Error", "Enter valid integers for frame size")
            return
        count_x = w // fw
        count_y = h // fh
        self.count_x_entry.setText(str(count_x))
        self.count_y_entry.setText(str(count_y))
        self.data[self.current_path] = {
            "frame_width": fw,
            "frame_height": fh,
            "frame_count_x": count_x,
            "frame_count_y": count_y
        }
        
        # remove highlight from tree item if frame data is now set
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            self._clear_highlight_recursive(item)
        
        self.show_image()

    def _clear_highlight_recursive(self, item):
        if item is None:
            return
        path = item.data(0, Qt.UserRole)
        
        if path and path in self.data:
            if str(path).lower().endswith(('.png', '.jpg', '.jpeg')):
                item.setBackground(0, Qt.transparent)
                font = item.font(0)
                font.setBold(False)
                item.setFont(0, font)
            
        for i in range(item.childCount()):
            self._clear_highlight_recursive(item.child(i))

    def on_width_height_change(self):
        if not self.current_path:
            return
        img = QImage(self.current_path)
        w, h = img.width(), img.height()
        try:
            fw = int(self.width_entry.text())
            fh = int(self.height_entry.text())
            if fw <= 0 or fh <= 0:
                return
            count_x = w // fw
            count_y = h // fh
            self.count_x_entry.setText(str(count_x))
            self.count_y_entry.setText(str(count_y))
        except ValueError:
            pass

    def on_count_change(self):
        if not self.current_path:
            return
        img = QImage(self.current_path)
        w, h = img.width(), img.height()
        count_x_text = self.count_x_entry.text()
        count_y_text = self.count_y_entry.text()
        if count_x_text and not count_y_text:
            self.count_y_entry.setText("1")
            count_y_text = "1"
        if count_y_text and not count_x_text:
            self.count_x_entry.setText("1")
            count_x_text = "1"
        try:
            count_x = int(count_x_text)
            count_y = int(count_y_text)
            if count_x <= 0 or count_y <= 0:
                return
            fw = w // count_x
            fh = h // count_y
            self.width_entry.setText(str(fw))
            self.height_entry.setText(str(fh))
        except ValueError:
            pass

    def export_json(self):
        if not self.data:
            QMessageBox.critical(self, "Error", "No data to export")
            return
        if not self.image_paths:
            QMessageBox.critical(self, "Error", "No images loaded")
            return
        root_folder = os.path.commonpath(self.image_paths)
        save_path = os.path.join(root_folder, "data.json")
        output = {os.path.relpath(k, root_folder): v for k, v in self.data.items()}
        try:
            with open(save_path, "w") as f:
                json.dump(output, f, indent=4)
            QMessageBox.information(self, "Saved", f"Changes were saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")
