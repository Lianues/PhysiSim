import uuid
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QColor

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.entity_manager import EntityManager
from physi_sim.core.component import (
    IdentifierComponent,
    TransformComponent,
    PhysicsBodyComponent,
    ConnectionComponent,
    ConnectionType # Will use REVOLUTE_JOINT
)
from physi_sim.core.vector import Vector2D
# from physi_sim.physics.collision_system import CollisionSystem # Not strictly needed here anymore

# Forward declaration for type hinting and enum access
# from ..enums import ToolAttachmentMode # No longer needed for this tool
# from physi_sim.graphics.main_window import MainWindow, DrawingWidget # Keep if needed for other type hints

class CreateRevoluteJointPhase:
    SELECT_BODY_A = 1
    DEFINE_ANCHOR_A = 2
    SELECT_BODY_B = 3
    DEFINE_ANCHOR_B = 4

class CreateRevoluteJointToolHandler(BaseToolHandler):
    """
    工具处理器，用于在两个动态物体之间创建转动关节。
    """
    def __init__(self, entity_manager: EntityManager):
        super().__init__()
        self.entity_manager = entity_manager
        self.current_phase = CreateRevoluteJointPhase.SELECT_BODY_A
        self.selected_body_A_id: uuid.UUID | None = None
        self.selected_body_B_id: uuid.UUID | None = None
        self.anchor_A_local: Vector2D | None = None
        # self.anchor_B_local: Vector2D | None = None # Will be determined at DEFINE_ANCHOR_B

        self.preview_line_start_world: Vector2D | None = None # For drawing line from first anchor to mouse

    def activate(self, drawing_widget): # drawing_widget is of type DrawingWidget
        self.reset_state()
        main_window = drawing_widget.window() # Expected to be MainWindow
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("创建转动关节：请选择第一个动态物体。")
        if hasattr(main_window, 'clear_selection'):
            main_window.clear_selection()
        drawing_widget.update()

    def deactivate(self, drawing_widget): # drawing_widget is of type DrawingWidget
        self.reset_state()
        main_window = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.clearMessage()
        # Clear highlights specific to this tool
        if hasattr(main_window, 'rod_pending_selection_id'):
            main_window.rod_pending_selection_id = None
        if hasattr(main_window, 'rod_second_pending_selection_id'):
            main_window.rod_second_pending_selection_id = None
        drawing_widget.update()

    def reset_state(self):
        self.current_phase = CreateRevoluteJointPhase.SELECT_BODY_A
        self.selected_body_A_id = None
        self.selected_body_B_id = None
        self.anchor_A_local = None
        self.preview_line_start_world = None

    def handle_mouse_press(self, event: QMouseEvent, drawing_widget): # drawing_widget is of type DrawingWidget
        if event.button() != Qt.MouseButton.LeftButton:
            return

        world_pos = drawing_widget._get_world_coordinates(event.position())
        main_window = drawing_widget.window() # Expected to be MainWindow

        if self.current_phase == CreateRevoluteJointPhase.SELECT_BODY_A:
            entity_id = main_window._get_entity_at_world_pos(world_pos)
            if entity_id:
                phys_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                if phys_body and not phys_body.is_fixed:
                    self.selected_body_A_id = entity_id
                    self.current_phase = CreateRevoluteJointPhase.DEFINE_ANCHOR_A
                    main_window.status_bar.showMessage(f"物体 A 已选择 ({str(entity_id)[:8]})。请在物体 A 上点击定义锚点 (Shift切换吸附)。")
                    main_window.rod_pending_selection_id = self.selected_body_A_id # Highlight
                    drawing_widget.update()
                else:
                    main_window.status_bar.showMessage("无效选择。请选择一个可移动的动态物体作为物体 A。")
            else:
                main_window.status_bar.showMessage("未选中任何物体。请选择第一个动态物体。")

        elif self.current_phase == CreateRevoluteJointPhase.DEFINE_ANCHOR_A:
            clicked_entity_id = main_window._get_entity_at_world_pos(world_pos)
            if clicked_entity_id == self.selected_body_A_id:
                world_anchor_on_A = main_window._determine_anchor_point(
                    self.selected_body_A_id, world_pos, drawing_widget.is_snap_active
                )
                self.anchor_A_local = main_window._get_local_point_for_entity(
                    self.selected_body_A_id, world_anchor_on_A
                )
                if self.anchor_A_local is not None:
                    self.preview_line_start_world = world_anchor_on_A # Anchor A in world coords
                    self.current_phase = CreateRevoluteJointPhase.SELECT_BODY_B
                    main_window.status_bar.showMessage(f"物体 A 锚点已定义。请选择第二个动态物体 (B)。")
                    # Keep body A highlighted, maybe change highlight for anchor B selection
                    main_window.rod_second_pending_selection_id = None # Clear potential B highlight
                    drawing_widget.update()
                else:
                    main_window.status_bar.showMessage("错误：无法计算物体 A 的局部锚点。请重试。")
                    # Don't reset fully, allow re-click on Body A for anchor
            else:
                main_window.status_bar.showMessage("请在第一个选中的物体 (A) 上点击以定义锚点。")

        elif self.current_phase == CreateRevoluteJointPhase.SELECT_BODY_B:
            entity_id = main_window._get_entity_at_world_pos(world_pos)
            if entity_id and entity_id != self.selected_body_A_id:
                phys_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                if phys_body and not phys_body.is_fixed:
                    self.selected_body_B_id = entity_id
                    self.current_phase = CreateRevoluteJointPhase.DEFINE_ANCHOR_B
                    main_window.status_bar.showMessage(f"物体 B 已选择 ({str(entity_id)[:8]})。请在物体 B 上点击定义锚点 (Shift切换吸附)。")
                    main_window.rod_second_pending_selection_id = self.selected_body_B_id # Highlight B
                    drawing_widget.update()
                else:
                    main_window.status_bar.showMessage("无效选择。请选择一个可移动的动态物体作为物体 B。")
            elif entity_id == self.selected_body_A_id:
                 main_window.status_bar.showMessage("不能将物体 A 连接到自身。请选择另一个动态物体作为 B。")
            else:
                main_window.status_bar.showMessage("未选中任何物体。请选择第二个动态物体 (B)。")

        elif self.current_phase == CreateRevoluteJointPhase.DEFINE_ANCHOR_B:
            clicked_entity_id = main_window._get_entity_at_world_pos(world_pos)
            if clicked_entity_id == self.selected_body_B_id:
                world_anchor_on_B = main_window._determine_anchor_point(
                    self.selected_body_B_id, world_pos, drawing_widget.is_snap_active
                )
                local_anchor_B = main_window._get_local_point_for_entity(
                    self.selected_body_B_id, world_anchor_on_B
                )
                if local_anchor_B is not None and self.anchor_A_local is not None:
                    conn_id = uuid.uuid4()
                    conn_comp = ConnectionComponent(
                        id=conn_id,
                        source_entity_id=self.selected_body_A_id,
                        target_entity_id=self.selected_body_B_id,
                        connection_type=ConnectionType.REVOLUTE_JOINT,
                        connection_point_a=self.anchor_A_local,
                        connection_point_b=local_anchor_B,
                        parameters={} # REVOLUTE_JOINT might not need parameters if it's a pure position constraint
                    )
                    self.entity_manager.add_independent_component(conn_comp)
                    print(f"转动关节已创建: ID={str(conn_id)[:8]} between A ({str(self.selected_body_A_id)[:8]} @ {self.anchor_A_local}) and B ({str(self.selected_body_B_id)[:8]} @ {local_anchor_B})")

                    # --- Begin: Immediately adjust Body B's position and angle to satisfy joint ---
                    transform_A = self.entity_manager.get_component(self.selected_body_A_id, TransformComponent)
                    transform_B = self.entity_manager.get_component(self.selected_body_B_id, TransformComponent)

                    if transform_A and transform_B:
                        # Calculate the world position of anchor A on body A
                        world_anchor_A = transform_A.position + self.anchor_A_local.rotate(transform_A.angle)
                        
                        # We want the world position of anchor B on body B to coincide with world_anchor_A.
                        # Let P_A_world be world_anchor_A.
                        # Let p_B_local be local_anchor_B.
                        # We need to find new transform_B.position (r_B') and transform_B.angle (theta_B') such that:
                        # r_B' + R(theta_B') * p_B_local = P_A_world
                        
                        # For simplicity, let's assume we only adjust position of B for now,
                        # keeping its angle (theta_B) the same. This is a common approach for initial snapping.
                        # If angle also needs to be constrained (e.g. to match A's angle or a specific relative angle),
                        # that would be a different type of joint or an additional constraint.
                        # A revolute joint allows free relative rotation.
                        
                        rotated_local_anchor_B = local_anchor_B.rotate(transform_B.angle) # Use B's current angle
                        new_pos_B = world_anchor_A - rotated_local_anchor_B
                        
                        transform_B.position = new_pos_B
                        print(f"立即调整物体 B ({str(self.selected_body_B_id)[:8]}) 位置到 {new_pos_B} 以匹配物体 A 的锚点。")
                        # Note: If body B has other constraints, this direct move might temporarily violate them
                        # until the next physics step. This is usually acceptable for user-created joints.
                        
                        # Ensure physics body velocity is also consistent if objects were moving.
                        # For simplicity during creation, we might not need to adjust velocity immediately,
                        # as the next physics step will apply constraint forces.
                        # However, if objects have high velocity, a sudden position snap without velocity
                        # adjustment can lead to large impulses.
                        # For now, we'll only adjust position.

                    # --- End: Immediate adjustment ---

                    # Disable collision between all entities in the newly formed or extended linkage group
                    if hasattr(main_window, 'collision_system') and main_window.collision_system is not None and \
                       self.selected_body_A_id is not None : # Ensure body A is selected
                        
                        # First, always disable collision between the two directly connected bodies
                        if self.selected_body_B_id: # Ensure body B is also selected
                             main_window.collision_system.disable_collision_pair(self.selected_body_A_id, self.selected_body_B_id)
                             print(f"自动禁用碰撞 (直接连接): {str(self.selected_body_A_id)[:8]} 和 {str(self.selected_body_B_id)[:8]}")

                        # Then, find the entire group connected to body A (which now includes body B)
                        # and disable collisions between all pairs in that group.
                        linked_group = self.entity_manager.get_revolute_linked_entities(self.selected_body_A_id)
                        
                        if len(linked_group) > 1:
                            group_list = list(linked_group)
                            for i in range(len(group_list)):
                                for j in range(i + 1, len(group_list)):
                                    entity1_id = group_list[i]
                                    entity2_id = group_list[j]
                                    # Check if collision wasn't already disabled (e.g. direct pair above)
                                    # disable_collision_pair should ideally be idempotent or handle this.
                                    main_window.collision_system.disable_collision_pair(entity1_id, entity2_id)
                                    print(f"自动禁用碰撞 (链内): {str(entity1_id)[:8]} 和 {str(entity2_id)[:8]}")
                    
                    main_window.status_bar.showMessage(f"转动关节已创建! 请选择第一个物体开始新的关节创建，或切换工具。")
                    self.reset_state_for_next_joint(drawing_widget)
                else:
                    main_window.status_bar.showMessage("错误：无法计算物体 B 的局部锚点。请重试。")
                    # Don't reset fully, allow re-click on Body B for anchor
            else:
                main_window.status_bar.showMessage("请在第二个选中的物体 (B) 上点击以定义锚点。")

    def handle_mouse_move(self, event: QMouseEvent, drawing_widget):
        if self.current_phase == CreateRevoluteJointPhase.SELECT_BODY_B and self.preview_line_start_world:
            drawing_widget.update() # To redraw preview line from anchor A to mouse
        elif self.current_phase == CreateRevoluteJointPhase.DEFINE_ANCHOR_B and self.preview_line_start_world:
            # Line from anchor A to current mouse position on body B (or just mouse pos)
            drawing_widget.update() 

    def handle_mouse_release(self, event: QMouseEvent, drawing_widget):
        pass

    def paint_overlay(self, painter: QPainter, drawing_widget):
        if self.preview_line_start_world and drawing_widget.current_mouse_world_pos:
            # Draw line from anchor_A (world) to current mouse pos
            if self.current_phase == CreateRevoluteJointPhase.SELECT_BODY_B or \
               self.current_phase == CreateRevoluteJointPhase.DEFINE_ANCHOR_B:
                
                painter.save()
                pen = QPen(QColor(0, 200, 0, 150)) # Greenish preview
                pen.setStyle(Qt.PenStyle.DashLine)
                pen.setWidthF(1.5 / drawing_widget.pixels_per_world_unit)
                painter.setPen(pen)
                
                painter.drawLine(
                    QPointF(self.preview_line_start_world.x, self.preview_line_start_world.y),
                    QPointF(drawing_widget.current_mouse_world_pos.x, drawing_widget.current_mouse_world_pos.y)
                )
                painter.restore()
                
    def reset_state_for_next_joint(self, drawing_widget):
        """Resets state to allow user to select a new Body A."""
        self.reset_state() # Full reset to SELECT_BODY_A
        main_window = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
             main_window.status_bar.showMessage("创建转动关节：请选择第一个动态物体。")
        if hasattr(main_window, 'rod_pending_selection_id'): # Clear highlights
            main_window.rod_pending_selection_id = None
        if hasattr(main_window, 'rod_second_pending_selection_id'):
            main_window.rod_second_pending_selection_id = None
        drawing_widget.update()