from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QColor, QPen

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import (
    TransformComponent, GeometryComponent, ShapeType, RenderComponent,
    PhysicsBodyComponent, ForceAccumulatorComponent, IdentifierComponent
)
import math # For moment of inertia calculation

# Use a forward reference for MainWindow and DrawingWidget
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode

class CircleToolHandler(BaseToolHandler):
    """
    处理圆形绘制工具的逻辑。
    """
    MIN_RADIUS_THRESHOLD: float = 0.05 # 世界单位，最小半径阈值

    def __init__(self):
        super().__init__()
        self.is_drawing_circle: bool = False
        self.circle_center_world: Optional[Vector2D] = None
        self.circle_radius_world: float = 0.0

    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("绘制圆形工具已激活。点击并拖拽以绘制圆形。", 3000)
        self.is_drawing_circle = False
        self.circle_center_world = None
        self.circle_radius_world = 0.0
        drawing_widget.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self, drawing_widget: 'DrawingWidget'):
        self.is_drawing_circle = False
        self.circle_center_world = None
        self.circle_radius_world = 0.0
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        drawing_widget.update() # Clear any preview

    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        click_pos_world = drawing_widget._get_world_coordinates(event.position())
        self.is_drawing_circle = True
        self.circle_center_world = click_pos_world
        self.circle_radius_world = 0.0
        drawing_widget.update()

    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        if self.is_drawing_circle and self.circle_center_world:
            current_world_pos = drawing_widget._get_world_coordinates(event.position())
            self.circle_radius_world = (current_world_pos - self.circle_center_world).magnitude()
            drawing_widget.update()

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        if self.is_drawing_circle and self.circle_center_world:
            main_window: 'MainWindow' = drawing_widget.window()
            # Radius is already set by mouse_move
            final_center = self.circle_center_world
            final_radius = self.circle_radius_world

            if final_radius > self.MIN_RADIUS_THRESHOLD:
                entity_manager = main_window.entity_manager
                new_entity_id = entity_manager.create_entity()

                entity_manager.add_component(new_entity_id, IdentifierComponent(id=str(new_entity_id), name="New Circle"))
                entity_manager.add_component(new_entity_id, TransformComponent(position=final_center))
                entity_manager.add_component(new_entity_id, GeometryComponent(shape_type=ShapeType.CIRCLE, parameters={'radius': final_radius}))
                entity_manager.add_component(new_entity_id, RenderComponent())
                
                physics_body_comp = PhysicsBodyComponent(mass=1.0)
                entity_manager.add_component(new_entity_id, physics_body_comp)
                entity_manager.add_component(new_entity_id, ForceAccumulatorComponent())

                mass = physics_body_comp.mass
                if mass <= 0:
                    physics_body_comp.moment_of_inertia = float('inf')
                else:
                    inertia = 0.5 * mass * final_radius**2
                    physics_body_comp.moment_of_inertia = max(inertia, 1e-6) # Ensure positive
                
                print(f"Created Circle: ID={new_entity_id}, Center={final_center}, Radius={final_radius}, MoI={physics_body_comp.moment_of_inertia}")
            else:
                print(f"Circle creation cancelled: radius {final_radius} is below threshold {self.MIN_RADIUS_THRESHOLD}.")

            self.is_drawing_circle = False
            self.circle_center_world = None
            self.circle_radius_world = 0.0
            drawing_widget.update() # Clear preview and redraw scene

    def paint_overlay(self, painter: QPainter, drawing_widget: 'DrawingWidget'):
        if self.is_drawing_circle and self.circle_center_world:
            preview_pen = QPen(QColor(Qt.GlobalColor.blue))
            preview_pen.setWidthF(1.0 / drawing_widget.pixels_per_world_unit)
            preview_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(preview_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            center_world = self.circle_center_world
            radius_world = self.circle_radius_world
            painter.drawEllipse(QPointF(center_world.x, center_world.y), radius_world, radius_world)

            # Draw preview center marker
            center_marker_size_pixels = 4
            center_marker_size_world = center_marker_size_pixels / drawing_widget.pixels_per_world_unit
            center_pen = QPen(QColor(Qt.GlobalColor.blue))
            center_pen.setWidthF(1.5 / drawing_widget.pixels_per_world_unit)
            painter.setPen(center_pen)
            painter.drawLine(QPointF(center_world.x - center_marker_size_world / 2, center_world.y),
                             QPointF(center_world.x + center_marker_size_world / 2, center_world.y))
            painter.drawLine(QPointF(center_world.x, center_world.y - center_marker_size_world / 2),
                             QPointF(center_world.x, center_world.y + center_marker_size_world / 2))