from PySide6.QtWidgets import QApplication
from sprite_manager import SpriteManager

def run_app():
    import sys
    app = QApplication(sys.argv)
    window = SpriteManager()
    window.show()
    sys.exit(app.exec())