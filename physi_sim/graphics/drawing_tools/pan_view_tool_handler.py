from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QCursor

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D # Not strictly needed for pan, but good for consistency

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode

class PanViewToolHandler(BaseToolHandler):
    """
    处理平移视图工具的逻辑。
    """

    def __init__(self):
        super().__init__()
        self.is_panning: bool = False
        self.last_pan_pos: Optional[QPointF] = None

    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("平移视图工具已激活。按住左键拖拽以平移视图。", 3000)
        self.is_panning = False
        self.last_pan_pos = None
        drawing_widget.setCursor(Qt.CursorShape.OpenHandCursor)

    def deactivate(self, drawing_widget: 'DrawingWidget'):
        self.is_panning = False
        self.last_pan_pos = None
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        drawing_widget.update()

    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.last_pan_pos = event.position() # QPointF in widget coordinates
            drawing_widget.setCursor(Qt.CursorShape.ClosedHandCursor)

    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        if self.is_panning and self.last_pan_pos:
            current_pos_screen = event.position()
            delta_screen = current_pos_screen - self.last_pan_pos
            
            # Update DrawingWidget's view_offset directly
            # Note: This assumes DrawingWidget has view_offset and pixels_per_world_unit
            if drawing_widget.pixels_per_world_unit != 0: # Avoid division by zero
                drawing_widget.view_offset.x -= delta_screen.x() / drawing_widget.pixels_per_world_unit
                # Y-axis is inverted in screen coordinates vs world for DrawingWidget
                drawing_widget.view_offset.y += delta_screen.y() / drawing_widget.pixels_per_world_unit
            
            self.last_pan_pos = current_pos_screen
            drawing_widget.update()

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        if event.button() == Qt.MouseButton.LeftButton and self.is_panning:
            self.is_panning = False
            self.last_pan_pos = None
            drawing_widget.setCursor(Qt.CursorShape.OpenHandCursor) # Back to open hand if tool still active
            drawing_widget.update()

    def paint_overlay(self, painter, drawing_widget: 'DrawingWidget'):
        # Pan tool typically doesn't need a specific overlay
        pass