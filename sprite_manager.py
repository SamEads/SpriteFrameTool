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
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItemGroup,
    QGraphicsPolygonItem,
    QGraphicsLineItem
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPixmap,
    QImage,
    QPen,
    QAction,
    QKeySequence,
    QPolygonF
)
from PySide6.QtCore import (
    Qt,
    QRectF,
    QPointF
)

class OriginPoint(QGraphicsItemGroup):
    def __init__(self, sprite_manager, x=0, y=0, size=8):
        super().__init__()
        self.sprite_manager = sprite_manager
        self.size = size
        
        rhombus_points = [
            QPointF(0, -size),      # top
            QPointF(size, 0),       # right
            QPointF(0, size),       # bottom
            QPointF(-size, 0)       # left
        ]
        rhombus_polygon = QPolygonF(rhombus_points)
        self.rhombus = QGraphicsPolygonItem(rhombus_polygon)
        self.rhombus.setBrush(QBrush(QColor(128, 128, 128, 200)))
        self.rhombus.setPen(QPen(QColor(255, 255, 255), 1))
        
        # create anchor lines
        line_length = size * 0.5
        self.top_line = QGraphicsLineItem(0, -size, 0, -size - line_length)
        self.bottom_line = QGraphicsLineItem(0, size, 0, size + line_length)
        self.left_line = QGraphicsLineItem(-size, 0, -size - line_length, 0)
        self.right_line = QGraphicsLineItem(size, 0, size + line_length, 0)
        
        line_pen = QPen(QColor(255, 255, 255), 1)
        self.top_line.setPen(line_pen)
        self.bottom_line.setPen(line_pen)
        self.left_line.setPen(line_pen)
        self.right_line.setPen(line_pen)
        
        # add all parts to the group
        self.addToGroup(self.rhombus)
        self.addToGroup(self.top_line)
        self.addToGroup(self.bottom_line)
        self.addToGroup(self.left_line)
        self.addToGroup(self.right_line)
        
        # set position and properties
        self.setPos(x, y)
        self.setFlag(QGraphicsItemGroup.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.ItemSendsGeometryChanges, True)
        self.setZValue(1000)
        
        self.update_scale()

    def update_scale(self):
        if self.sprite_manager and self.sprite_manager.graphics_zoom > 0:
            scale_factor = 1.0 / self.sprite_manager.graphics_zoom
            self.setScale(scale_factor)

    def itemChange(self, change, value):
        if change == QGraphicsItemGroup.ItemPositionChange and self.scene():
            new_pos = value
            
            # snap to integer pixel coordinates in original image space
            if self.sprite_manager and self.sprite_manager.zoom > 0:
                # convert to original image coordinates, round to int, then back to zoomed
                original_x = new_pos.x() / self.sprite_manager.zoom
                original_y = new_pos.y() / self.sprite_manager.zoom
                snapped_original_x = round(original_x)
                snapped_original_y = round(original_y)
                new_pos.setX(snapped_original_x * self.sprite_manager.zoom)
                new_pos.setY(snapped_original_y * self.sprite_manager.zoom)
                
            if self.sprite_manager:
                # convert from zoomed coordinates to original image coordinates
                original_x = int(new_pos.x() / self.sprite_manager.zoom)
                original_y = int(new_pos.y() / self.sprite_manager.zoom)
                self.sprite_manager.origin_x_entry.setText(str(original_x))
                self.sprite_manager.origin_y_entry.setText(str(original_y))
                self.sprite_manager.update_data(self.sprite_manager.data[self.sprite_manager.current_path])
                
            return new_pos
        return super().itemChange(change, value)

class ImageView(QGraphicsView):
    def __init__(self, sprite_manager=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sprite_manager = sprite_manager
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom = 1.0
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

    def wheelEvent(self, event):
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self._zoom *= zoomFactor
        self.scale(zoomFactor, zoomFactor)
        
        # update origin point scale
        if self.sprite_manager and self.sprite_manager.origin_point:
            # update the sprite manager's zoom value to match graphics view zoom
            self.sprite_manager.graphics_zoom = self._zoom
            self.sprite_manager.origin_point.update_scale()
            
        event.accept()

    def resetZoom(self):
        self.resetTransform()
        self._zoom = 1.0
        
        # update origin point scale when zoom is reset
        if self.sprite_manager and self.sprite_manager.origin_point:
            self.sprite_manager.graphics_zoom = self._zoom
            self.sprite_manager.origin_point.update_scale()

class SpriteManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sprite Frame Tool")
        self.resize(800, 600)
        self.data = {}
        self.image_paths = []
        self.current_path = None
        self.img_width = 0
        self.img_height = 0
        self.zoom = 1.0
        self.graphics_zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.origin_point = None
        self.setup_ui()
        
        save_action = QAction(self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.export_json)
        self.addAction(save_action)

    def setup_ui(self):
        # main layout
        central = QWidget()
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.addWidget(splitter)

        # left panel widget (directory tree + properties)
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.addWidget(QLabel("Images"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        left.addWidget(self.tree, 10)
        self.btn_folder = QPushButton("Select Folder")
        self.btn_folder.clicked.connect(self.load_folder)
        left.addWidget(self.btn_folder)
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.export_json)
        left.addWidget(btn_save)

        # properties tree below images tree
        left.addWidget(QLabel("Properties"))
        self.property_tree = QTreeWidget(left_widget)
        self.property_tree.setHeaderLabels(["Property", "Value"])
        header = self.property_tree.header()
        header.resizeSection(0, 180)
        header.resizeSection(1, 100)
        left.addWidget(self.property_tree, 5)

        left_widget.setMaximumWidth(400)
        left_widget.setMinimumWidth(200)
        splitter.addWidget(left_widget)

        # middle panel widget (sprite view)
        middle_widget = QWidget()
        middle_layout = QVBoxLayout(middle_widget)
        self.graphics = ImageView(self)
        self.scene = QGraphicsScene()
        self.graphics.setScene(self.scene)
        middle_layout.addWidget(self.graphics, 10)
        splitter.addWidget(middle_widget)
        self.img_size_label = QLabel("")
        middle_layout.addWidget(self.img_size_label)

        self.prop_origin_x = QTreeWidgetItem(self.property_tree, ["Origin X"])
        self.origin_x_entry = QLineEdit()
        self.origin_x_entry.setStyleSheet("border: none;")
        self.property_tree.setItemWidget(self.prop_origin_x, 1, self.origin_x_entry)
        self.origin_x_entry.editingFinished.connect(self.on_origin_change)

        self.prop_origin_y = QTreeWidgetItem(self.property_tree, ["Origin Y"])
        self.origin_y_entry = QLineEdit()
        self.origin_y_entry.setStyleSheet("border: none;")
        self.property_tree.setItemWidget(self.prop_origin_y, 1, self.origin_y_entry)
        self.origin_y_entry.editingFinished.connect(self.on_origin_change)

        self.prop_count_x = QTreeWidgetItem(self.property_tree, ["Frame Count X"])
        self.count_x_entry = QLineEdit()
        self.count_x_entry.setStyleSheet("border: none;")
        self.property_tree.setItemWidget(self.prop_count_x, 1, self.count_x_entry)
        self.count_x_entry.editingFinished.connect(self.on_count_change)

        self.prop_count_y = QTreeWidgetItem(self.property_tree, ["Frame Count Y"])
        self.count_y_entry = QLineEdit()
        self.count_y_entry.setStyleSheet("border: none;")
        self.property_tree.setItemWidget(self.prop_count_y, 1, self.count_y_entry)
        self.count_y_entry.editingFinished.connect(self.on_count_change)

        self.property_tree.expandAll()
        self.tree.itemSelectionChanged.connect(self.on_tree_select)
        splitter.setSizes([400, 600])

    def center_origin(self):
        try:
            fw = int(self.count_x_entry.text())
            fh = int(self.count_y_entry.text())
            origin_x = fw // 2
            origin_y = fh // 2
            self.origin_x_entry.setText(str(origin_x))
            self.origin_y_entry.setText(str(origin_y))
        except Exception:
            pass

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
            for _ in dirs:
                pass
            for f in files:
                if f.lower().endswith((".png", ".jpg", ".jpeg")):
                    path = os.path.join(root, f)
                    self.image_paths.append(path)
                    item = QTreeWidgetItem(parent, [f])
                    item.setData(0, Qt.UserRole, path)
                    '''
                    if path not in self.data:
                        item.setBackground(0, QBrush(QColor(120, 120, 40)))
                        font = item.font(0)
                        font.setBold(True)
                        item.setFont(0, font)
                    '''
        
        # remove deleted images from json
        valid_paths = set(self.image_paths)
        self.data = {k: v for k, v in self.data.items() if k in valid_paths}
        # ensure every image has origin_x and origin_y
        for path in self.image_paths:
            if path not in self.data:
                self.data[path] = {}

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
            if self.origin_point:
                self.scene.removeItem(self.origin_point)
                self.origin_point = None
            self.apply_frame()

    def show_image(self):
        path = self.current_path
        if not path or not os.path.exists(path):
            self.scene.clear()
            self.origin_point = None
            self.img_size_label.setText("")
            return
        img = QImage(path)
        if img.isNull():
            self.scene.clear()
            self.origin_point = None
            self.img_size_label.setText("")
            return
        pixmap = QPixmap.fromImage(img)
        self.img_width = img.width()
        self.img_height = img.height()
        
        # apply zoom
        zoomed_pixmap = pixmap.scaled(pixmap.width() * self.zoom, pixmap.height() * self.zoom, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.scene.clear()
        self.origin_point = None
        
        self.graphics.setSceneRect(QRectF(-10, -10, zoomed_pixmap.width() + 20, zoomed_pixmap.height() + 20))
        self.scene.addPixmap(zoomed_pixmap)
        
        origin_x = int(float(self.origin_x_entry.text()))
        origin_y = int(float(self.origin_y_entry.text()))
        
        count_x = int(float(self.count_x_entry.text()))
        count_y = int(float(self.count_y_entry.text()))
        
        self.img_size_label.setText(f"Image size: {self.img_width} x {self.img_height}\nFrame size: {int(self.img_width/count_x)} x {int(self.img_height/count_y)}")
        
        pen = QPen(QColor(0, 225, 255), 0)
        for i in range(count_x + 1):
            x = (i / count_x) * self.img_width * self.zoom
            if i == count_x:
                x = self.img_width
            self.scene.addLine(x, 0, x, self.img_height, pen)
        for i in range(count_y + 1):
            y = (i / count_y) * self.img_height * self.zoom
            if i == count_y:
                y = self.img_height
            self.scene.addLine(0, y, self.img_width, y, pen)
            
        # remove existing origin point if it exists
        if self.origin_point:
            self.scene.removeItem(self.origin_point)
            
        # create new origin point
        origin_zoomed_x = origin_x * self.zoom
        origin_zoomed_y = origin_y * self.zoom
        self.origin_point = OriginPoint(self, origin_zoomed_x, origin_zoomed_y, 6)
        self.graphics_zoom = self.graphics._zoom
        self.scene.addItem(self.origin_point)

    def apply_frame(self):
        if not self.current_path:
            return
        
        entry = self.data.get(self.current_path)        
        if entry:
            self.count_x_entry.setText(str(entry["frame_count_x"]))
            self.count_y_entry.setText(str(entry["frame_count_y"]))
            if "origin_x" in entry:
                self.origin_x_entry.setText(str(entry["origin_x"]))
            if "origin_y" in entry:
                self.origin_y_entry.setText(str(entry["origin_y"]))
        else:
            self.count_x_entry.setText(str(1))
            self.count_y_entry.setText(str(1))
            self.origin_x_entry.setText(str(0))
            self.origin_y_entry.setText(str(0))
        
        self.show_image()

    def update_data(self, entry):
        frame_count_x = int(float(self.count_x_entry.text()))
        frame_count_y = int(float(self.count_y_entry.text()))
        
        entry["frame_count_x"] = frame_count_x
        entry["frame_count_y"] = frame_count_y
        
        entry["origin_x"] = int(float(self.origin_x_entry.text()))
        entry["origin_y"] = int(float(self.origin_y_entry.text()))
        
        entry["frame_width"] = self.img_width // frame_count_x
        entry["frame_height"] = self.img_height // frame_count_y

    def on_count_change(self):
        if not self.current_path:
            return
        count_x_text = self.count_x_entry.text()
        count_y_text = self.count_y_entry.text()
        if count_x_text and not count_y_text:
            count_y_text = "1"
            self.count_y_entry.setText(count_y_text)
        if count_y_text and not count_x_text:
            count_x_text = "1"
            self.count_x_entry.setText(count_x_text)
        try:
            count_x = int(count_x_text)
            count_y = int(count_y_text)
            if count_x <= 0:
                self.count_x_entry.setText("1")
            if count_y <= 0:
                self.count_y_entry.setText("1")
            entry = self.data[self.current_path]
            self.show_image()
            self.update_data(entry)
        except ValueError:
            pass

    def on_origin_change(self):
        if self.origin_point:
            try:
                # int vals only
                origin_x = int(float(self.origin_x_entry.text()))
                origin_y = int(float(self.origin_y_entry.text()))
                
                # update text fields to show the integer values a float was typed
                self.origin_x_entry.setText(str(origin_x))
                self.origin_y_entry.setText(str(origin_y))
                
                # convert to zoomed coordinates
                zoomed_x = origin_x * self.zoom
                zoomed_y = origin_y * self.zoom
                
                self.origin_point.setPos(zoomed_x, zoomed_y)
                
                entry = self.data[self.current_path]
                self.update_data(entry)
            except ValueError:
                pass

    def export_json(self):
        if not self.data:
            QMessageBox.critical(self, "Error", "No data to export")
            return
        if not self.image_paths:
            QMessageBox.critical(self, "Error", "No images loaded")
            return
        if self.current_path:
            self.update_data(self.data[self.current_path])
        root_folder = os.path.commonpath(self.image_paths)
        save_path = os.path.join(root_folder, "data.json")
        output = {os.path.relpath(k, root_folder): v for k, v in self.data.items()}
        try:
            with open(save_path, "w") as f:
                json.dump(output, f, indent=4)
            QMessageBox.information(self, "Saved", f"Changes were saved")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")