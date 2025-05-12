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
    ConnectionType
)
from physi_sim.core.vector import Vector2D
from physi_sim.physics.collision_system import CollisionSystem
# Forward declaration for type hinting and enum access
from ..enums import ToolAttachmentMode # Updated import from new enums file
# from physi_sim.graphics.main_window import MainWindow, DrawingWidget # Keep if needed for other type hints

class ConnectToAxisToolPhase:
    SELECT_AXIS = 1
    SELECT_DYNAMIC_OBJECT = 2
    DEFINE_ANCHOR_ON_OBJECT = 3

class ConnectToAxisToolHandler(BaseToolHandler):
    """
    工具处理器，用于将动态物体连接到转轴点。
    """
    def __init__(self, entity_manager: EntityManager):
        super().__init__()
        self.entity_manager = entity_manager
        self.current_phase = ConnectToAxisToolPhase.SELECT_AXIS
        self.selected_axis_id: uuid.UUID | None = None
        self.selected_dynamic_object_id: uuid.UUID | None = None
        self.preview_line_start_world: Vector2D | None = None # For drawing line from axis to mouse

    def activate(self, drawing_widget): # drawing_widget is of type DrawingWidget
        self.reset_state()
        main_window = drawing_widget.window() # Expected to be MainWindow
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("连接到转轴工具：请先选择一个转轴点。")
        # Clear any previous selections from other tools that might interfere
        if hasattr(main_window, 'clear_selection'):
            main_window.clear_selection()
        drawing_widget.update()


    def deactivate(self, drawing_widget): # drawing_widget is of type DrawingWidget
        self.reset_state()
        main_window = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.clearMessage()
        # Clear highlights specific to this tool
        if hasattr(main_window, 'rod_pending_selection_id'): # Using rod_pending as a generic highlight
            main_window.rod_pending_selection_id = None
        if hasattr(main_window, 'rod_second_pending_selection_id'):
            main_window.rod_second_pending_selection_id = None
        drawing_widget.update()

    def reset_state(self):
        self.current_phase = ConnectToAxisToolPhase.SELECT_AXIS
        self.selected_axis_id = None
        self.selected_dynamic_object_id = None
        self.preview_line_start_world = None

    def handle_mouse_press(self, event: QMouseEvent, drawing_widget): # drawing_widget is of type DrawingWidget
        if event.button() != Qt.MouseButton.LeftButton:
            return

        world_pos = drawing_widget._get_world_coordinates(event.position())
        main_window = drawing_widget.window() # Expected to be MainWindow

        if self.current_phase == ConnectToAxisToolPhase.SELECT_AXIS:
            entity_id = main_window._get_entity_at_world_pos(world_pos)
            if entity_id:
                ident = self.entity_manager.get_component(entity_id, IdentifierComponent)
                if ident and "AXIS_POINT" in ident.type_tags: # Updated tag
                    self.selected_axis_id = entity_id
                    self.current_phase = ConnectToAxisToolPhase.SELECT_DYNAMIC_OBJECT
                    transform_axis = self.entity_manager.get_component(self.selected_axis_id, TransformComponent)
                    if transform_axis:
                        self.preview_line_start_world = transform_axis.position
                    main_window.status_bar.showMessage(f"转轴点已选择 ({str(entity_id)[:8]})。请选择要连接的动态物体。")
                    main_window.rod_pending_selection_id = self.selected_axis_id # Highlight selected axis
                    drawing_widget.update()
                else:
                    main_window.status_bar.showMessage("无效选择。请选择一个转轴点。")
            else:
                main_window.status_bar.showMessage("未选中任何物体。请选择一个转轴点。")

        elif self.current_phase == ConnectToAxisToolPhase.SELECT_DYNAMIC_OBJECT:
            entity_id = main_window._get_entity_at_world_pos(world_pos)
            if entity_id and entity_id != self.selected_axis_id:
                phys_body = self.entity_manager.get_component(entity_id, PhysicsBodyComponent)
                if phys_body and not phys_body.is_fixed:
                    self.selected_dynamic_object_id = entity_id
                    self.current_phase = ConnectToAxisToolPhase.DEFINE_ANCHOR_ON_OBJECT
                    main_window.status_bar.showMessage(f"物体已选择 ({str(entity_id)[:8]})。请在物体上点击定义锚点 (Shift切换吸附)。")
                    main_window.rod_second_pending_selection_id = self.selected_dynamic_object_id # Highlight selected object
                    drawing_widget.update()
                else:
                    main_window.status_bar.showMessage("无效选择。请选择一个可移动的动态物体。")
            elif entity_id == self.selected_axis_id:
                 main_window.status_bar.showMessage("不能将转轴点连接到自身。请选择一个动态物体。")
            else:
                main_window.status_bar.showMessage("未选中任何物体。请选择一个动态物体。")
        
        elif self.current_phase == ConnectToAxisToolPhase.DEFINE_ANCHOR_ON_OBJECT:
            # Ensure click is on the selected dynamic object
            clicked_entity_id = main_window._get_entity_at_world_pos(world_pos)
            if clicked_entity_id == self.selected_dynamic_object_id:
                # Determine anchor point (world coords), considering snap (via drawing_widget.is_snap_active)
                # drawing_widget.is_snap_active is controlled by the Shift key.
                world_anchor_on_object = main_window._determine_anchor_point(
                    self.selected_dynamic_object_id,
                    world_pos,
                    drawing_widget.is_snap_active # This now correctly reflects Shift state
                )
                
                # Convert world anchor to local coordinates of the dynamic object
                local_anchor_pA = main_window._get_local_point_for_entity(
                    self.selected_dynamic_object_id,
                    world_anchor_on_object
                )
                
                if local_anchor_pA is not None:
                    if drawing_widget.is_snap_active:
                        print(f"连接到转轴 (吸附模式): 锚点 {local_anchor_pA} for entity {str(self.selected_dynamic_object_id)[:8]}")
                    else:
                        print(f"连接到转轴 (自由定位模式): 锚点 {local_anchor_pA} for entity {str(self.selected_dynamic_object_id)[:8]}")
                    # Create ConnectionComponent
                    conn_id = uuid.uuid4()
                    conn_comp = ConnectionComponent(
                        id=conn_id,
                        source_entity_id=self.selected_dynamic_object_id,
                        target_entity_id=self.selected_axis_id,
                        connection_type=ConnectionType.REVOLUTE_JOINT_AXIS, # Updated ConnectionType
                        connection_point_a=local_anchor_pA,
                        connection_point_b=Vector2D(0, 0), # Anchor on axis is its origin
                        parameters={}
                    )
                    self.entity_manager.add_independent_component(conn_comp)
                    print(f"旋转关节已创建: ID={str(conn_id)[:8]} between Entity {str(self.selected_dynamic_object_id)[:8]} (anchor: {local_anchor_pA}) and Axis {str(self.selected_axis_id)[:8]}")

                    # --- Begin: Immediately adjust dynamic object's position ---
                    if self.selected_dynamic_object_id and self.selected_axis_id:
                        transform_A = self.entity_manager.get_component(self.selected_dynamic_object_id, TransformComponent)
                        transform_Axis = self.entity_manager.get_component(self.selected_axis_id, TransformComponent)

                        if transform_A and transform_Axis:
                            P_axis_world = transform_Axis.position
                            p_A_local = conn_comp.connection_point_a # This is local_anchor_pA
                            angle_A = transform_A.angle
                            
                            # pA_world_offset = R(angleA) * pA_local
                            pA_world_offset = p_A_local.rotate(angle_A)
                            
                            # posA_new = P_axis_world - pA_world_offset
                            posA_new = P_axis_world - pA_world_offset
                            
                            transform_A.position = posA_new
                            print(f"立即调整物体 {str(self.selected_dynamic_object_id)[:8]} 位置到 {posA_new} 以匹配转轴 {str(self.selected_axis_id)[:8]}")
                            drawing_widget.update() # Update view immediately after position change
                        else:
                            print("警告: 无法获取物体或转轴的TransformComponent以进行即时位置调整。")
                    # --- End: Immediately adjust dynamic object's position ---
                    
                    # Automatic collision disabling
                    if hasattr(main_window, 'collision_system') and main_window.collision_system is not None:
                        collision_sys: CollisionSystem = main_window.collision_system
                        newly_connected_object_id = self.selected_dynamic_object_id
                        axis_id = self.selected_axis_id

                        # 1. Disable collision between the dynamic object and the axis entity itself
                        if newly_connected_object_id and axis_id:
                            collision_sys.disable_collision_pair(newly_connected_object_id, axis_id)
                            print(f"自动禁用碰撞 (物体-转轴): {str(newly_connected_object_id)[:8]} 和 {str(axis_id)[:8]}")

                        # 2. Disable collision between the newly connected object and other objects on the same axis
                        all_connections = self.entity_manager.get_all_independent_components_of_type(ConnectionComponent)
                        for other_conn in all_connections:
                            if other_conn.id == conn_id: # Skip the connection just made
                                continue
                            if other_conn.connection_type == ConnectionType.REVOLUTE_JOINT_AXIS and \
                               other_conn.target_entity_id == axis_id and \
                               other_conn.source_entity_id != newly_connected_object_id:
                                
                                other_dynamic_object_id = other_conn.source_entity_id
                                collision_sys.disable_collision_pair(newly_connected_object_id, other_dynamic_object_id)
                                print(f"自动禁用碰撞 (同轴物体): {str(newly_connected_object_id)[:8]} 和 {str(other_dynamic_object_id)[:8]}")
                    else:
                        print("警告: CollisionSystem 在 MainWindow 中不可用，无法自动禁用碰撞。")

                    main_window.status_bar.showMessage(f"关节已创建! 请选择下一个转轴点或切换工具。")
                    self.reset_state_for_next_connection(drawing_widget) # Reset for next connection
                else:
                    main_window.status_bar.showMessage("错误：无法计算局部锚点。请重试。")
                    self.reset_state_for_next_connection(drawing_widget) # Reset on error
            else:
                main_window.status_bar.showMessage("请在先前选中的动态物体上点击以定义锚点。")


    def handle_mouse_move(self, event: QMouseEvent, drawing_widget): # drawing_widget is of type DrawingWidget
        if self.current_phase == ConnectToAxisToolPhase.SELECT_DYNAMIC_OBJECT and self.preview_line_start_world:
            drawing_widget.update() # To redraw preview line
        elif self.current_phase == ConnectToAxisToolPhase.DEFINE_ANCHOR_ON_OBJECT and self.preview_line_start_world:
            # Optionally, update line to snap point preview on the dynamic object
            drawing_widget.update()


    def handle_mouse_release(self, event: QMouseEvent, drawing_widget):
        pass

    def paint_overlay(self, painter: QPainter, drawing_widget): # drawing_widget is of type DrawingWidget
        if self.preview_line_start_world and drawing_widget.current_mouse_world_pos:
            if self.current_phase == ConnectToAxisToolPhase.SELECT_DYNAMIC_OBJECT or \
               self.current_phase == ConnectToAxisToolPhase.DEFINE_ANCHOR_ON_OBJECT:
                
                painter.save() # Save current painter state (e.g., pen, brush)
                
                pen = QPen(QColor(0, 200, 0, 150)) # Greenish preview line
                pen.setStyle(Qt.PenStyle.DashLine)
                # Set width in world units, painter is already scaled.
                pen.setWidthF(1.5 / drawing_widget.pixels_per_world_unit)
                painter.setPen(pen)
                
                # Painter is already in world coordinates, draw directly.
                painter.drawLine(
                    QPointF(self.preview_line_start_world.x, self.preview_line_start_world.y),
                    QPointF(drawing_widget.current_mouse_world_pos.x, drawing_widget.current_mouse_world_pos.y)
                )
                
                painter.restore() # Restore painter state to what it was before this method call
                
    def reset_state_for_next_connection(self, drawing_widget):
        """Resets state to allow user to select a new axis or object."""
        self.current_phase = ConnectToAxisToolPhase.SELECT_AXIS
        self.selected_axis_id = None
        self.selected_dynamic_object_id = None
        self.preview_line_start_world = None
        
        main_window = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
             main_window.status_bar.showMessage("连接到转轴工具：请先选择一个转轴点。")
        if hasattr(main_window, 'rod_pending_selection_id'): # Clear highlights
            main_window.rod_pending_selection_id = None
        if hasattr(main_window, 'rod_second_pending_selection_id'):
            main_window.rod_second_pending_selection_id = None
        drawing_widget.update()