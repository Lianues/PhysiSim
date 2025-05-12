from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.entity_manager import EntityManager
from physi_sim.core.component import (
    IdentifierComponent,
    TransformComponent,
    PhysicsBodyComponent,
    RenderComponent,
    GeometryComponent,
    ShapeType,
    ForceAccumulatorComponent # Added ForceAccumulatorComponent
)
from physi_sim.core.vector import Vector2D

# Forward declaration for type hinting if DrawingWidget is in another module
# from ..main_window import DrawingWidget # Assuming DrawingWidget is in main_window.py

class AxisToolHandler(BaseToolHandler):
    """
    工具处理器，用于在场景中放置转轴点（作为特殊实体）。
    """
    def __init__(self, entity_manager: EntityManager):
        super().__init__()
        self.entity_manager = entity_manager
        self.axis_radius_world = 0.1 # 转轴点在世界坐标中的渲染半径
        self.axis_fill_color = (100, 100, 255, 200) # RGBA for axis points (e.g., a distinct blue)
        self.axis_stroke_color = (50, 50, 150, 255)

    def handle_mouse_press(self, event: QMouseEvent, drawing_widget): # drawing_widget is of type DrawingWidget
        """
        处理鼠标按下事件，在点击位置创建一个转轴实体。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            world_pos = drawing_widget._get_world_coordinates(event.position())
            
            # 创建转轴实体
            entity_id = self.entity_manager.create_entity()
            
            self.entity_manager.add_component(
                entity_id,
                IdentifierComponent(id=entity_id, name=f"Axis_{str(entity_id)[:8]}", type_tags=["AXIS_POINT"])
            )
            self.entity_manager.add_component(
                entity_id,
                TransformComponent(position=world_pos)
            )
            
            # Make axis points dynamic by default so they can move with connected objects
            axis_mass = 0.05 # Small mass for the axis point itself
            # Moment of inertia for a small disk: 0.5 * m * r^2
            axis_inertia = 0.5 * axis_mass * (self.axis_radius_world ** 2)
            if axis_inertia <= 1e-9: # Ensure inertia is a small positive value if mass/radius are tiny
                axis_inertia = 1e-6

            self.entity_manager.add_component(
                entity_id,
                PhysicsBodyComponent(
                    is_fixed=False,
                    mass=axis_mass,
                    moment_of_inertia=axis_inertia,
                    restitution=0.1, # Low bounciness for axis itself
                    static_friction_coefficient=0.3, # Default friction
                    dynamic_friction_coefficient=0.2
                )
            )
            self.entity_manager.add_component(
                entity_id,
                RenderComponent(
                    fill_color=self.axis_fill_color,
                    stroke_color=self.axis_stroke_color,
                    stroke_width=1.0 / drawing_widget.pixels_per_world_unit, # Thinner stroke for small points
                    z_order=10 # Ensure axis points are rendered above most other objects if needed
                )
            )
            self.entity_manager.add_component(
                entity_id,
                GeometryComponent(
                    shape_type=ShapeType.CIRCLE,
                    parameters={"radius": self.axis_radius_world}
                )
            )
            self.entity_manager.add_component(
                entity_id,
                ForceAccumulatorComponent() # Add ForceAccumulator for physics processing
            )
            
            print(f"转轴点已创建: ID={str(entity_id)[:8]} at {world_pos}")
            drawing_widget.update() # 请求重绘以显示新转轴点

    def handle_mouse_move(self, event: QMouseEvent, drawing_widget):
        """放置转轴工具在鼠标移动时不需要特殊处理。"""
        pass

    def handle_mouse_release(self, event: QMouseEvent, drawing_widget):
        """放置转轴工具在鼠标释放时不需要特殊处理。"""
        pass

    def activate(self, drawing_widget):
        main_window = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("放置转轴点工具：点击场景以放置一个可移动的转轴点。")

    def deactivate(self, drawing_widget):
        main_window = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.clearMessage()