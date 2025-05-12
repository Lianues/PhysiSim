from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QMessageBox, QInputDialog
from PySide6.QtGui import QCursor, QColor, QPen

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import ConnectionComponent, TransformComponent, IdentifierComponent, ConnectionType # Use ConnectionType Enum
from physi_sim.core.entity_manager import EntityManager

import uuid

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode

class RodToolHandler(BaseToolHandler):
    """
    处理轻杆绘制工具的逻辑。
    """

    def __init__(self):
        super().__init__()
        self.rod_creation_phase: int = 0
        self.rod_first_entity_id: Optional[uuid.UUID] = None
        self.rod_second_entity_id: Optional[uuid.UUID] = None
        self.rod_first_entity_click_pos_world: Optional[Vector2D] = None
        self.rod_second_entity_click_pos_world: Optional[Vector2D] = None
        # For highlighting during creation, mirror MainWindow attributes
        self.rod_pending_selection_id: Optional[uuid.UUID] = None
        self.rod_second_pending_selection_id: Optional[uuid.UUID] = None


    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("绘制轻杆工具已激活。请选择第一个实体。", 3000)
        self._reset_state(main_window)
        drawing_widget.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        self._reset_state(main_window)
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        drawing_widget.update()

    def _reset_state(self, main_window: 'MainWindow'):
        self.rod_creation_phase = 0
        self.rod_first_entity_id = None
        self.rod_second_entity_id = None
        self.rod_first_entity_click_pos_world = None
        self.rod_second_entity_click_pos_world = None
        self.rod_pending_selection_id = None
        self.rod_second_pending_selection_id = None
        # Reset MainWindow's corresponding attributes if they are used for rendering highlights
        main_window.rod_first_entity_id = None
        main_window.rod_second_entity_id = None
        main_window.rod_first_entity_click_pos_world = None
        main_window.rod_second_entity_click_pos_world = None
        main_window.rod_pending_selection_id = None
        main_window.rod_second_pending_selection_id = None


    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        click_pos_world = drawing_widget._get_world_coordinates(event.position())
        clicked_entity_id = main_window._get_entity_at_world_pos(click_pos_world)

        if self.rod_creation_phase == 0: # Selecting first entity
            if clicked_entity_id is not None:
                self.rod_first_entity_id = clicked_entity_id
                self.rod_pending_selection_id = clicked_entity_id # For highlight
                main_window.rod_pending_selection_id = clicked_entity_id # Update MainWindow for renderer

                self.rod_creation_phase = 1
                anchor_a_world = main_window._determine_anchor_point(
                    clicked_entity_id, click_pos_world, drawing_widget.is_snap_active
                )
                self.rod_first_entity_click_pos_world = anchor_a_world
                main_window.rod_first_entity_click_pos_world = anchor_a_world


                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"轻杆实体 A 已选 ({str(clicked_entity_id)[:8]})。请选择实体 B。", 3000)
                drawing_widget.update()
            else:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage("请点击一个实体作为轻杆的第一个连接点。", 2000)
        
        elif self.rod_creation_phase == 1: # Selecting second entity
            if clicked_entity_id is not None:
                if clicked_entity_id == self.rod_first_entity_id:
                    QMessageBox.warning(drawing_widget, "轻杆创建", "不能将轻杆连接到自身。")
                else:
                    self.rod_second_entity_id = clicked_entity_id
                    self.rod_second_pending_selection_id = clicked_entity_id # For highlight
                    main_window.rod_second_pending_selection_id = clicked_entity_id # Update MainWindow

                    self.rod_creation_phase = 2
                    anchor_b_world = main_window._determine_anchor_point(
                        clicked_entity_id, click_pos_world, drawing_widget.is_snap_active
                    )
                    self.rod_second_entity_click_pos_world = anchor_b_world
                    main_window.rod_second_entity_click_pos_world = anchor_b_world

                    if hasattr(main_window, 'status_bar'):
                        main_window.status_bar.showMessage(f"轻杆实体 B 已选 ({str(clicked_entity_id)[:8]})。输入参数...", 3000)
                    drawing_widget.update()
                    self._prompt_for_rod_parameters(main_window, drawing_widget)
            else: # Clicked on empty space
                QMessageBox.information(drawing_widget, "轻杆创建", "已取消选择第一个实体。")
                self._reset_state(main_window)
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage("绘制轻杆工具：请选择第一个实体。", 3000)
                drawing_widget.update()

    def _prompt_for_rod_parameters(self, main_window: 'MainWindow', drawing_widget: 'DrawingWidget'):
        if self.rod_first_entity_id is None or self.rod_second_entity_id is None:
            self._reset_state(main_window)
            return

        entity_manager = main_window.entity_manager
        default_target_length = 1.0

        transform_a = entity_manager.get_component(self.rod_first_entity_id, TransformComponent)
        transform_b = entity_manager.get_component(self.rod_second_entity_id, TransformComponent)

        anchor_a_world = self.rod_first_entity_click_pos_world if self.rod_first_entity_click_pos_world else (transform_a.position if transform_a else Vector2D(0,0))
        anchor_b_world = self.rod_second_entity_click_pos_world if self.rod_second_entity_click_pos_world else (transform_b.position if transform_b else Vector2D(0,0))
        
        if transform_a and transform_b:
            dist_vec = anchor_a_world - anchor_b_world
            calculated_dist = max(dist_vec.magnitude(), 0.01)
            default_target_length = round(calculated_dist, 2)

        # Prompt for target_length
        target_length_str, ok = QInputDialog.getText(drawing_widget, "轻杆参数", "目标长度 (target_length):", text=str(default_target_length))
        if not ok:
            self._reset_state(main_window); drawing_widget.update(); return
        try:
            target_length = float(target_length_str)
            if target_length <= 0: raise ValueError("目标长度必须为正数。")
        except ValueError as e:
            QMessageBox.warning(drawing_widget, "输入错误", f"无效的目标长度: {e}"); self._reset_state(main_window); drawing_widget.update(); return
        

        anchor_a_local = main_window._get_local_point_for_entity(self.rod_first_entity_id, anchor_a_world) or Vector2D(0,0)
        anchor_b_local = main_window._get_local_point_for_entity(self.rod_second_entity_id, anchor_b_world) or Vector2D(0,0)

        try:
            rod_params = {
                "target_length": target_length
            }
            new_rod_connection = entity_manager.create_independent_component(
                ConnectionComponent,
                source_entity_id=self.rod_first_entity_id,
                target_entity_id=self.rod_second_entity_id,
                connection_type=ConnectionType.ROD, # Use Enum
                parameters=rod_params,
                connection_point_a=anchor_a_local,
                connection_point_b=anchor_b_local
            )
            QMessageBox.information(drawing_widget, "轻杆创建成功", f"轻杆 (ID: {new_rod_connection.id}) 已创建。")
        except ValueError as e:
            QMessageBox.critical(drawing_widget, "轻杆创建失败", f"创建轻杆时出错: {e}")
        except Exception as e:
            QMessageBox.critical(drawing_widget, "轻杆创建失败", f"创建轻杆时发生未知错误: {e}")
        finally:
            self._reset_state(main_window)
            drawing_widget.update()

    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        pass # Similar to spring, no specific move action beyond snap point display

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        pass # Driven by clicks

    def paint_overlay(self, painter, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if self.rod_creation_phase == 1 and self.rod_first_entity_click_pos_world and drawing_widget.current_mouse_world_pos:
            pen = QPen(QColor(Qt.GlobalColor.darkRed), 1.5 / drawing_widget.pixels_per_world_unit, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            start_point_world = self.rod_first_entity_click_pos_world
            end_point_world = drawing_widget.current_mouse_world_pos
            
            painter.drawLine(QPointF(start_point_world.x, start_point_world.y), 
                             QPointF(end_point_world.x, end_point_world.y))