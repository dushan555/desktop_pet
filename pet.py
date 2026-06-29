import sys
import os
import random
from PyQt6.QtCore import Qt, QTimer, QPoint, QSize
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QMenu, QSystemTrayIcon
from PyQt6.QtGui import QPixmap, QMovie, QAction, QCursor, QIcon

# States
STATE_IDLE = 0
STATE_WALK_LEFT = 1
STATE_WALK_RIGHT = 2
STATE_SLEEP = 3
STATE_DRAGGED = 4
STATE_EATING = 5

class DesktopPet(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Window settings: 
        # - FramelessWindowHint: No title bar
        # - WindowStaysOnTopHint: Always on top
        # - NoDropShadowWindowHint: Clear cut edges without shadow artifact
        # - ToolTip: Keeps it on top, hides from Dock, and natively NEVER steals focus on macOS
        # - WindowDoesNotAcceptFocus: Double insurance to prevent taking keyboard focus
        self.flags = (
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.NoDropShadowWindowHint |
            Qt.WindowType.ToolTip |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlags(self.flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
        # High DPI support (Retina screen)
        self.width = 128
        self.height = 128
        self.resize(self.width, self.height)
        
        # Default positioning (bottom right corner)
        screen = QApplication.primaryScreen().geometry()
        self.x = screen.width() - self.width - 100
        self.y = screen.height() - self.height - 100
        self.move(self.x, self.y)
        
        # Setup label to display the frame images
        self.label = QLabel(self)
        self.label.setFixedSize(self.width, self.height)
        self.label.setScaledContents(True)
        
        # Load assets
        self.assets_dir = "assets"
        self.load_assets()
        
        # Behavior states
        self.state = STATE_IDLE
        self.current_frame = 0
        self.is_dragging = False
        self.click_through = False # Master click-through switch
        self.drag_position = QPoint()
        
        # Setup macOS menu-bar Tray Icon (extremely important so users can toggle modes when click-through is on)
        self.create_tray_icon()
        
        # Timers
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(400) # Default delay
        
        self.behavior_timer = QTimer(self)
        self.behavior_timer.timeout.connect(self.update_behavior)
        self.behavior_timer.start(5000) # Check every 5 seconds
        
        # Render first frame
        self.set_state(STATE_IDLE)
        self.update_animation_frame()
        
    def load_assets(self):
        self.frames = {
            STATE_IDLE: [
                QPixmap(os.path.join(self.assets_dir, "idle_1.png")),
                QPixmap(os.path.join(self.assets_dir, "idle_2.png"))
            ],
            STATE_WALK_LEFT: [
                QPixmap(os.path.join(self.assets_dir, "walk_l1.png")),
                QPixmap(os.path.join(self.assets_dir, "walk_l2.png"))
            ],
            STATE_WALK_RIGHT: [
                QPixmap(os.path.join(self.assets_dir, "walk_r1.png")),
                QPixmap(os.path.join(self.assets_dir, "walk_r2.png"))
            ],
            STATE_SLEEP: [
                QPixmap(os.path.join(self.assets_dir, "sleep_1.png")),
                QPixmap(os.path.join(self.assets_dir, "sleep_2.png"))
            ],
            STATE_DRAGGED: [
                QPixmap(os.path.join(self.assets_dir, "drag.png"))
            ],
            STATE_EATING: [
                QPixmap(os.path.join(self.assets_dir, "idle_1.png")),
                QPixmap(os.path.join(self.assets_dir, "idle_2.png"))
            ]
        }
        
    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Use hamster frame as tray icon
        icon_pixmap = QPixmap(os.path.join(self.assets_dir, "idle_1.png")).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio)
        self.tray_icon.setIcon(QIcon(icon_pixmap))
        
        # System Tray Menu
        self.tray_menu = QMenu()
        
        feed_action = QAction("喂食 (Feed Seed)", self)
        feed_action.triggered.connect(self.feed_pet)
        self.tray_menu.addAction(feed_action)
        
        sleep_action = QAction("睡觉 (Go to Sleep)", self)
        sleep_action.triggered.connect(lambda: self.set_state(STATE_SLEEP))
        self.tray_menu.addAction(sleep_action)
        
        wake_action = QAction("唤醒 (Wake Up)", self)
        wake_action.triggered.connect(lambda: self.set_state(STATE_IDLE))
        self.tray_menu.addAction(wake_action)
        
        self.tray_menu.addSeparator()
        
        self.toggle_penetrate_action = QAction("鼠标穿透 (Click-Through Mode) [OFF]", self)
        self.toggle_penetrate_action.triggered.connect(self.toggle_mouse_penetration)
        self.tray_menu.addAction(self.toggle_penetrate_action)
        
        self.tray_menu.addSeparator()
        
        exit_action = QAction("退出 (Exit)", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        
    def set_state(self, new_state):
        if self.state == new_state:
            return
        self.state = new_state
        self.current_frame = 0
        
        # Adjust timer speed based on behavior
        if self.state == STATE_WALK_LEFT or self.state == STATE_WALK_RIGHT:
            self.anim_timer.setInterval(250)
        elif self.state == STATE_SLEEP:
            self.anim_timer.setInterval(800)
        elif self.state == STATE_EATING:
            self.anim_timer.setInterval(200)
        else:
            self.anim_timer.setInterval(400)
            
        self.update_animation_frame()
        
    # --- Dragging Support (Only active if click-through is OFF) ---
    def mousePressEvent(self, event):
        if self.click_through:
            event.ignore()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.set_state(STATE_DRAGGED)
            event.accept()
            
    def mouseMoveEvent(self, event):
        if self.click_through:
            event.ignore()
            return
        if event.buttons() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            
    def mouseReleaseEvent(self, event):
        if self.click_through:
            event.ignore()
            return
        if self.is_dragging:
            self.is_dragging = False
            self.set_state(STATE_IDLE)
            event.accept()
            
    def contextMenuEvent(self, event):
        if self.click_through:
            event.ignore()
            return
        # Right-click menu directly on pet (only works if click-through is OFF)
        menu = QMenu(self)
        
        feed_action = QAction("喂食 (Feed Seed)", self)
        feed_action.triggered.connect(self.feed_pet)
        menu.addAction(feed_action)
        
        sleep_action = QAction("睡觉 (Go to Sleep)", self)
        sleep_action.triggered.connect(lambda: self.set_state(STATE_SLEEP))
        menu.addAction(sleep_action)
        
        wake_action = QAction("唤醒 (Wake Up)", self)
        wake_action.triggered.connect(lambda: self.set_state(STATE_IDLE))
        menu.addAction(wake_action)
        
        menu.addSeparator()
        
        toggle_penetrate_action = QAction("鼠标穿透 (Click-Through Mode) [OFF]", self)
        toggle_penetrate_action.triggered.connect(self.toggle_mouse_penetration)
        menu.addAction(toggle_penetrate_action)
        
        menu.addSeparator()
        
        exit_action = QAction("退出桌面宠物 (Exit)", self)
        exit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(exit_action)
        
        menu.exec(event.globalPos())

    def toggle_mouse_penetration(self):
        """Toggle whether clicks pass completely through the pet to background windows"""
        self.click_through = not self.click_through
        
        # Toggle attributes
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, self.click_through)
        
        # Dynamically toggle WindowTransparentForInput (perfect for macOS window server passthrough)
        self.hide()
        current_flags = (
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.NoDropShadowWindowHint |
            Qt.WindowType.ToolTip |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if self.click_through:
            current_flags |= Qt.WindowType.WindowTransparentForInput
            self.toggle_penetrate_action.setText("鼠标穿透 (Click-Through Mode) [ON]")
        else:
            self.toggle_penetrate_action.setText("鼠标穿透 (Click-Through Mode) [OFF]")
            
        self.setWindowFlags(current_flags)
        self.show()
        
        # Print helper guide in terminal
        if self.click_through:
            print("🐾 [鼠标穿透已开启] 此时点击宠物会直接穿透。您可以通过右上角/顶部菜单栏的宠物图标随时关闭穿透。")

    def feed_pet(self):
        self.set_state(STATE_EATING)
        # Revert back to idle after 3 seconds of eating
        QTimer.singleShot(3000, lambda: self.set_state(STATE_IDLE) if self.state == STATE_EATING else None)

    # --- Behavior Machine ---
    def update_behavior(self):
        if not self.is_dragging and self.state != STATE_DRAGGED and self.state != STATE_EATING:
            if self.state == STATE_SLEEP:
                if random.random() < 0.15:
                    self.set_state(STATE_IDLE)
            else:
                choices = [STATE_IDLE, STATE_WALK_LEFT, STATE_WALK_RIGHT, STATE_SLEEP]
                weights = [0.45, 0.25, 0.25, 0.05]
                new_state = random.choices(choices, weights=weights)[0]
                self.set_state(new_state)
                
        # Set next random behavior interval (4 to 8 seconds)
        self.behavior_timer.setInterval(random.randint(4000, 8000))

    # --- Animation & Screen Boundaries ---
    def update_animation(self):
        # Movement physics
        dx = 0
        if self.state == STATE_WALK_LEFT:
            dx = -3
        elif self.state == STATE_WALK_RIGHT:
            dx = 3
            
        if dx != 0:
            screen_width = QApplication.primaryScreen().geometry().width()
            pos = self.pos()
            new_x = pos.x() + dx
            # Screen loop bounds
            if new_x < -self.width:
                new_x = screen_width
            elif new_x > screen_width:
                new_x = -self.width
            self.move(new_x, pos.y())
            
        # Cycle frame
        frame_list = self.frames[self.state]
        self.current_frame = (self.current_frame + 1) % len(frame_list)
        self.update_animation_frame()
        
    def update_animation_frame(self):
        pixmap = self.frames[self.state][self.current_frame]
        self.label.setPixmap(pixmap)
        
        # If click-through is NOT enabled, we still use pixel mask to make the transparent outline around the hamster click-through!
        # This allows clicking through the empty margins of the 128x128 window.
        if not self.click_through:
            self.setMask(pixmap.mask())
        else:
            # Under full click-through, the entire window allows mouse event pass through natively
            self.clearMask()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet.show()
    sys.exit(app.exec())
