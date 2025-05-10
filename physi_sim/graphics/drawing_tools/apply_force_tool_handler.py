from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QInputDialog
from PySide6.QtGui import QCursor

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import PhysicsBodyComponent, ForceAccumulatorComponent, TransformComponent, IdentifierComponent
from physi_sim.core.entity_manager import EntityManager

import uuid

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode, ToolAttachmentMode

class ApplyForceToolHandler(BaseToolHandler):
    """
    处理施加力工具的逻辑。
    """

    def __init__(self):
        super().__init__()
        self.force_apply_phase: int = 0 # 0: 未开始, 1: 已选实体 (自由定位模式下等待选择作用点), 2: (已废弃, 直接弹窗)
        self.force_target_entity_id: Optional[uuid.UUID] = None
        self.force_application_point_world: Optional[Vector2D] = None
        # highlighted_force_entity_id is managed by DrawingWidget/MainWindow for rendering consistency

    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        self._reset_state(drawing_widget) # Reset state upon activation
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("施加力工具已激活。请选择一个实体。", 3000)
        drawing_widget.setCursor(Qt.CursorShape.PointingHandCursor)


    def deactivate(self, drawing_widget: 'DrawingWidget'):
        self._reset_state(drawing_widget)
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        # Ensure MainWindow's highlight state is also cleared
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, '_reset_force_application_state'): # Check if method exists
             main_window._reset_force_application_state() # Call MainWindow's reset
        else: # Fallback if direct call isn't available (e.g. during early refactoring)
            drawing_widget.highlighted_force_entity_id = None

        drawing_widget.update()


    def _reset_state(self, drawing_widget: 'DrawingWidget'):
        self.force_apply_phase = 0
        self.force_target_entity_id = None
        self.force_application_point_world = None
        # Let MainWindow handle its own highlight state reset via _reset_force_application_state
        # drawing_widget.highlighted_force_entity_id = None # This might be redundant if MainWindow handles it


    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        entity_manager: EntityManager = main_window.entity_manager
        click_pos_world = drawing_widget._get_world_coordinates(event.position())
        
        hit_entity_id = main_window._get_entity_at_world_pos(click_pos_world)

        if self.force_apply_phase == 0: # Phase 0: Select entity
            if hit_entity_id is not None:
                physics_body = entity_manager.get_component(hit_entity_id, PhysicsBodyComponent)
                force_accumulator = entity_manager.get_component(hit_entity_id, ForceAccumulatorComponent)
                transform_comp = entity_manager.get_component(hit_entity_id, TransformComponent)

                if physics_body and force_accumulator and transform_comp:
                    self.force_target_entity_id = hit_entity_id
                    drawing_widget.highlighted_force_entity_id = hit_entity_id # For visual feedback

                    entity_name_comp = entity_manager.get_component(hit_entity_id, IdentifierComponent)
                    entity_display_name = str(hit_entity_id)[:8]
                    if entity_name_comp and entity_name_comp.name:
                        entity_display_name = f"'{entity_name_comp.name}' ({str(hit_entity_id)[:8]})"

                    # Import ToolAttachmentMode here or ensure it's available
                    from physi_sim.graphics.main_window import ToolAttachmentMode

                    if main_window.force_application_mode == ToolAttachmentMode.CENTER_OF_MASS:
                        self.force_application_point_world = transform_comp.position
                        if hasattr(main_window, 'status_bar'):
                            main_window.status_bar.showMessage(f"已选中实体 {entity_display_name} (质心模式)。准备输入力。")
                        self._prompt_for_force_vector(main_window, drawing_widget, self.force_target_entity_id, self.force_application_point_world)
                        # _reset_state will be called by _prompt_for_force_vector or its cancellation
                    else: # FREE_POSITION mode
                        self.force_apply_phase = 1
                        if hasattr(main_window, 'status_bar'):
                            main_window.status_bar.showMessage(f"已选中实体 {entity_display_name} (自由定位)。请点击力的作用点。")
                    drawing_widget.update()
                else:
                    QMessageBox.information(drawing_widget, "选择实体失败", "选中的对象缺少必要的物理或变换组件，无法施加力。")
                    if hasattr(main_window, 'status_bar'):
                        main_window.status_bar.showMessage("选中的对象缺少必要组件，无法施加力。")
                    main_window._reset_force_application_state() # Calls our _reset_state indirectly
            else: # Clicked on empty space in phase 0
                if drawing_widget.highlighted_force_entity_id:
                     main_window._reset_force_application_state()
                elif hasattr(main_window, 'status_bar'):
                     main_window.status_bar.showMessage("请先点击一个实体以选择施力对象。")
        
        elif self.force_apply_phase == 1: # Phase 1: Select application point (only for FREE_POSITION mode)
            if self.force_target_entity_id is not None:
                from physi_sim.graphics.main_window import ToolAttachmentMode # Re-import for safety
                if main_window.force_application_mode == ToolAttachmentMode.FREE_POSITION:
                    self.force_application_point_world = click_pos_world
                    
                    entity_name_comp = entity_manager.get_component(self.force_target_entity_id, IdentifierComponent)
                    entity_display_name = str(self.force_target_entity_id)[:8]
                    if entity_name_comp and entity_name_comp.name:
                        entity_display_name = f"'{entity_name_comp.name}' ({str(self.force_target_entity_id)[:8]})"

                    if hasattr(main_window, 'status_bar'):
                        main_window.status_bar.showMessage(f"作用点选定于 {click_pos_world} (实体: {entity_display_name})。")
                    self._prompt_for_force_vector(main_window, drawing_widget, self.force_target_entity_id, self.force_application_point_world)
            else: # Should not happen
                self._reset_state(drawing_widget) # Call own reset
        else: # Target entity ID lost
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage("目标实体丢失，请重新点击一个实体。")
                self._reset_state(drawing_widget) # Call own reset
                # Optionally re-process this click as a phase 0 click, but safer to just reset.
        drawing_widget.update()

    def _prompt_for_force_vector(self, main_window: 'MainWindow', drawing_widget: 'DrawingWidget', entity_id: uuid.UUID, application_point_world: Vector2D):
        """Prompts the user for force components and applies the force."""
        if entity_id is None:
            QMessageBox.warning(drawing_widget, "错误", "目标实体ID无效。")
            self._reset_state(drawing_widget)
            return

        entity_manager = main_window.entity_manager
        entity_name_comp = entity_manager.get_component(entity_id, IdentifierComponent)
        entity_display_name = str(entity_id)[:8]
        if entity_name_comp and entity_name_comp.name:
            entity_display_name = f"'{entity_name_comp.name}' ({str(entity_id)[:8]})"
        
        title = f"为实体 {entity_display_name} 施加力"
        
        force_x_str, ok_x = QInputDialog.getText(drawing_widget, title, "输入力的 X 分量 (Fx):", text="10.0")
        if not ok_x:
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage("施加力操作已取消。")
            self._reset_state(drawing_widget) # Reset state on cancel
            return
        
        force_y_str, ok_y = QInputDialog.getText(drawing_widget, title, "输入力的 Y 分量 (Fy):", text="0.0")
        if not ok_y:
            if hasattr(main_window, 'status_bar'):
                main_window.status_bar.showMessage("施加力操作已取消。")
            self._reset_state(drawing_widget) # Reset state on cancel
            return
            
        try:
            force_x = float(force_x_str)
            force_y = float(force_y_str)
        except ValueError:
            QMessageBox.warning(drawing_widget, "输入错误", "无效的力分量。请输入数字。")
            self._reset_state(drawing_widget) # Reset state on error
            return

        force_vector = Vector2D(force_x, force_y)
        
        self._apply_external_force_at_point(main_window, entity_id, force_vector, application_point_world)
        
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage(f"已对实体 {entity_display_name} 在 {application_point_world} 施加力 {force_vector}。")
        
        self._reset_state(drawing_widget) # Reset tool state after successful application

    def _apply_external_force_at_point(self, main_window: 'MainWindow', entity_id: uuid.UUID, force_vector: Vector2D, application_point_world: Vector2D):
        """
        Applies an external force and the resulting torque to an entity.
        """
        entity_manager = main_window.entity_manager
        transform = entity_manager.get_component(entity_id, TransformComponent)
        accumulator = entity_manager.get_component(entity_id, ForceAccumulatorComponent)
        
        if not transform:
            print(f"错误: 实体 {entity_id} 缺少 TransformComponent。无法施加力。")
            QMessageBox.warning(main_window, "施加力失败", f"实体 {str(entity_id)[:8]}... 缺少 TransformComponent。")
            return
        if not accumulator:
            print(f"错误: 实体 {entity_id} 缺少 ForceAccumulatorComponent。无法施加力。")
            QMessageBox.warning(main_window, "施加力失败", f"实体 {str(entity_id)[:8]}... 缺少 ForceAccumulatorComponent。")
            return

        center_world = transform.position
        r_x = application_point_world.x - center_world.x
        r_y = application_point_world.y - center_world.y
        torque = r_x * force_vector.y - r_y * force_vector.x
        
        accumulator.net_force = accumulator.net_force + force_vector
        accumulator.net_torque += torque
        
        entity_name_comp = entity_manager.get_component(entity_id, IdentifierComponent)
        entity_display_name = str(entity_id)[:8]
        if entity_name_comp and entity_name_comp.name:
            entity_display_name = f"'{entity_name_comp.name}' ({str(entity_id)[:8]})"

        print(f"已对实体 {entity_display_name} (ID: {entity_id}) 施加力:")
        print(f"  力向量: {force_vector}")
        print(f"  作用点 (世界): {application_point_world}")
        print(f"  质心 (世界): {center_world}")
        print(f"  力臂 (r): Vector2D({r_x:.3f}, {r_y:.3f})")
        print(f"  计算出的力矩: {torque:.3f}")
        print(f"  累积力: {accumulator.net_force}")
        print(f"  累积力矩: {accumulator.net_torque:.3f}")


    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        # ApplyForce tool usually doesn't have a dynamic preview on mouse move,
        # other than potential snap points or entity highlighting, which are
        # handled by DrawingWidget's main paintEvent or by setting highlighted_force_entity_id.
        pass

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        # Mouse release is not a primary action trigger for this tool's phases.
        # Actions are triggered by mouse press (selection) or dialogs.
        pass

    def paint_overlay(self, painter, drawing_widget: 'DrawingWidget'):
        # If there's a need to draw a specific marker for the force application point
        # during phase 1 (before dialog), it would be done here.
        # For now, entity highlighting is the main visual feedback.
        pass