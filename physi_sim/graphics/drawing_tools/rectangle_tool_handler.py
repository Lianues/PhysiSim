from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import (
    TransformComponent, GeometryComponent, ShapeType, RenderComponent,
    PhysicsBodyComponent, ForceAccumulatorComponent, IdentifierComponent
)
import math # For moment of inertia calculation

# Use a forward reference for MainWindow and DrawingWidget
from typing import TYPE_CHECKING, Optional, Tuple
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode


class RectangleToolHandler(BaseToolHandler):
    """
    处理矩形绘制工具的逻辑。
    """

    def __init__(self):
        super().__init__()
        self._drawing_start_pos: Optional[Vector2D] = None
        self._is_drawing: bool = False
        self._preview_rect: Optional[Tuple[float, float, float, float]] = None # x, y, w, h (world coords)

    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("绘制矩形工具已激活。点击并拖拽以绘制矩形。", 3000)
        self._is_drawing = False
        self._drawing_start_pos = None
        self._preview_rect = None
        drawing_widget.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self, drawing_widget: 'DrawingWidget'):
        self._is_drawing = False
        self._drawing_start_pos = None
        self._preview_rect = None
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        drawing_widget.update() # Clear any preview

    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        click_pos_world = drawing_widget._get_world_coordinates(event.position())
        self._drawing_start_pos = click_pos_world
        self._is_drawing = True
        self._preview_rect = (click_pos_world.x, click_pos_world.y, 0, 0)
        drawing_widget.update()

    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        if self._is_drawing and self._drawing_start_pos:
            current_world_pos = drawing_widget._get_world_coordinates(event.position())
            start_x = self._drawing_start_pos.x
            start_y = self._drawing_start_pos.y
            end_x = current_world_pos.x
            end_y = current_world_pos.y

            rect_x = min(start_x, end_x)
            rect_y = min(start_y, end_y) # Bottom Y for Y-up world
            rect_w = abs(start_x - end_x)
            rect_h = abs(start_y - end_y)
            self._preview_rect = (rect_x, rect_y, rect_w, rect_h)
            drawing_widget.update()

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        if self._is_drawing and self._drawing_start_pos:
            main_window: 'MainWindow' = drawing_widget.window()
            scene_release_pos = drawing_widget._get_world_coordinates(event.position())

            start_x = self._drawing_start_pos.x
            start_y = self._drawing_start_pos.y
            end_x = scene_release_pos.x
            end_y = scene_release_pos.y

            rect_x = min(start_x, end_x)
            rect_y = min(start_y, end_y)
            rect_w = abs(start_x - end_x)
            rect_h = abs(start_y - end_y)

            if rect_w > 1e-3 and rect_h > 1e-3: # Ensure valid rectangle (small threshold)
                entity_manager = main_window.entity_manager
                new_entity_uuid_obj = entity_manager.create_entity()

                ident_comp = entity_manager.get_component(new_entity_uuid_obj, IdentifierComponent)
                if ident_comp:
                    ident_comp.name = "New Rectangle"
                    # ID is already set by create_entity and assigned to IdentifierComponent by default
                else: # Should not happen if create_entity works as expected
                    entity_manager.add_component(new_entity_uuid_obj, IdentifierComponent(id=str(new_entity_uuid_obj), name="New Rectangle"))

                center_x = rect_x + rect_w / 2.0
                center_y = rect_y + rect_h / 2.0

                entity_manager.add_component(new_entity_uuid_obj, TransformComponent(position=Vector2D(center_x, center_y)))
                entity_manager.add_component(new_entity_uuid_obj, GeometryComponent(shape_type=ShapeType.RECTANGLE, parameters={"width": rect_w, "height": rect_h}))
                entity_manager.add_component(new_entity_uuid_obj, RenderComponent())
                
                physics_body_comp = PhysicsBodyComponent() # Default mass=1.0
                entity_manager.add_component(new_entity_uuid_obj, physics_body_comp)
                entity_manager.add_component(new_entity_uuid_obj, ForceAccumulatorComponent())

                mass = physics_body_comp.mass
                if mass <= 0:
                    physics_body_comp.moment_of_inertia = float('inf')
                else:
                    inertia = (1.0 / 12.0) * mass * (rect_w**2 + rect_h**2)
                    physics_body_comp.moment_of_inertia = max(inertia, 1e-6) # Ensure positive

                print(f"Created Rectangle: ID={new_entity_uuid_obj}, Pos=({center_x},{center_y}), Size=({rect_w}x{rect_h}), MoI={physics_body_comp.moment_of_inertia}")
            
            self._is_drawing = False
            self._drawing_start_pos = None
            self._preview_rect = None
            drawing_widget.update() # Clear preview and redraw scene

    def paint_overlay(self, painter: QPainter, drawing_widget: 'DrawingWidget'):
        if self._is_drawing and self._preview_rect:
            preview_pen = QPen(QColor(Qt.GlobalColor.blue))
            preview_pen.setWidthF(1.0 / drawing_widget.pixels_per_world_unit) # Thin line
            preview_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            painter.setPen(preview_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            x, y, w, h = self._preview_rect # These are world units
            painter.drawRect(QRectF(x, y, w, h))