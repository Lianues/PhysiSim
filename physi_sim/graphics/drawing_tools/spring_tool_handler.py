from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QMessageBox, QInputDialog
from PySide6.QtGui import QCursor, QPen, QColor

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.vector import Vector2D
from physi_sim.core.component import SpringComponent, TransformComponent, IdentifierComponent
from physi_sim.core.entity_manager import EntityManager

import uuid

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode

class SpringToolHandler(BaseToolHandler):
    """
    处理弹簧绘制工具的逻辑。
    """

    def __init__(self):
        super().__init__()
        # State managed by this handler, mirroring MainWindow's spring creation state
        self.spring_creation_phase: int = 0
        self.spring_first_entity_id: Optional[uuid.UUID] = None
        self.spring_second_entity_id: Optional[uuid.UUID] = None
        self.spring_first_entity_click_pos_world: Optional[Vector2D] = None
        self.spring_second_entity_click_pos_world: Optional[Vector2D] = None

    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.showMessage("绘制弹簧工具已激活。请选择第一个实体。", 3000)
        self._reset_state(main_window) # Reset state upon activation
        drawing_widget.setCursor(Qt.CursorShape.CrossCursor) # Or a specific spring cursor

    def deactivate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        self._reset_state(main_window)
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        drawing_widget.update()

    def _reset_state(self, main_window: 'MainWindow'):
        self.spring_creation_phase = 0
        self.spring_first_entity_id = None
        self.spring_second_entity_id = None
        self.spring_first_entity_click_pos_world = None
        self.spring_second_entity_click_pos_world = None
        # Also reset the corresponding attributes in MainWindow if they are still used for rendering highlights
        main_window.spring_first_entity_id = None
        main_window.spring_second_entity_id = None
        main_window.spring_first_entity_click_pos_world = None
        main_window.spring_second_entity_click_pos_world = None


    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        entity_manager: EntityManager = main_window.entity_manager
        click_pos_world = drawing_widget._get_world_coordinates(event.position())
        
        clicked_entity_id = main_window._get_entity_at_world_pos(click_pos_world)

        if self.spring_creation_phase == 0: # Selecting first entity
            if clicked_entity_id is not None:
                self.spring_first_entity_id = clicked_entity_id
                main_window.spring_first_entity_id = clicked_entity_id # For highlight
                self.spring_creation_phase = 1
                
                anchor_a_world = main_window._determine_anchor_point(
                    clicked_entity_id,
                    click_pos_world,
                    drawing_widget.is_snap_active
                )
                self.spring_first_entity_click_pos_world = anchor_a_world
                main_window.spring_first_entity_click_pos_world = anchor_a_world # For highlight/preview

                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"弹簧实体 A 已选 ({str(clicked_entity_id)[:8]})。请选择实体 B。", 3000)
                drawing_widget.update()
            else:
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage("请点击一个实体作为弹簧的第一个连接点。", 2000)
        
        elif self.spring_creation_phase == 1: # Selecting second entity
            if clicked_entity_id is not None:
                if clicked_entity_id == self.spring_first_entity_id:
                    QMessageBox.warning(drawing_widget, "弹簧创建", "不能将弹簧连接到自身。")
                else:
                    self.spring_second_entity_id = clicked_entity_id
                    main_window.spring_second_entity_id = clicked_entity_id # For highlight
                    self.spring_creation_phase = 2

                    anchor_b_world = main_window._determine_anchor_point(
                        clicked_entity_id,
                        click_pos_world,
                        drawing_widget.is_snap_active
                    )
                    self.spring_second_entity_click_pos_world = anchor_b_world
                    main_window.spring_second_entity_click_pos_world = anchor_b_world

                    if hasattr(main_window, 'status_bar'):
                        main_window.status_bar.showMessage(f"弹簧实体 B 已选 ({str(clicked_entity_id)[:8]})。输入参数...", 3000)
                    drawing_widget.update()
                    self._prompt_for_spring_parameters(main_window, drawing_widget)
            else: # Clicked on empty space
                QMessageBox.information(drawing_widget, "弹簧创建", "已取消选择第一个实体。")
                self._reset_state(main_window)
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage("绘制弹簧工具：请选择第一个实体。", 3000)
                drawing_widget.update()

    def _prompt_for_spring_parameters(self, main_window: 'MainWindow', drawing_widget: 'DrawingWidget'):
        if self.spring_first_entity_id is None or self.spring_second_entity_id is None:
            self._reset_state(main_window)
            return

        entity_manager = main_window.entity_manager
        default_rest_length = 1.0
        transform_a = entity_manager.get_component(self.spring_first_entity_id, TransformComponent)
        transform_b = entity_manager.get_component(self.spring_second_entity_id, TransformComponent)

        # Use the determined anchor points for default rest length calculation
        anchor_a_world = self.spring_first_entity_click_pos_world if self.spring_first_entity_click_pos_world else (transform_a.position if transform_a else Vector2D(0,0))
        anchor_b_world = self.spring_second_entity_click_pos_world if self.spring_second_entity_click_pos_world else (transform_b.position if transform_b else Vector2D(0,0))

        if transform_a and transform_b: # Check if transforms exist
            dist_vec = anchor_a_world - anchor_b_world
            calculated_dist = max(dist_vec.magnitude(), 0.1)
            default_rest_length = round(calculated_dist, 2)

        rest_length_str, ok1 = QInputDialog.getText(drawing_widget, "弹簧参数", "静止长度 (rest_length):", text=str(default_rest_length))
        if not ok1:
            self._reset_state(main_window)
            drawing_widget.update()
            return
        try:
            rest_length = float(rest_length_str)
            if rest_length < 0: raise ValueError("静止长度必须为非负数。")
        except ValueError as e:
            QMessageBox.warning(drawing_widget, "输入错误", f"无效的静止长度: {e}")
            self._reset_state(main_window)
            drawing_widget.update()
            return

        stiffness_k_str, ok2 = QInputDialog.getText(drawing_widget, "弹簧参数", "刚度系数 (stiffness_k):", text="10.0")
        if not ok2:
            self._reset_state(main_window)
            drawing_widget.update()
            return
        try:
            stiffness_k = float(stiffness_k_str)
            if stiffness_k <= 0: raise ValueError("刚度系数 k 必须为正数。")
        except ValueError as e:
            QMessageBox.warning(drawing_widget, "输入错误", f"无效的刚度系数: {e}")
            self._reset_state(main_window)
            drawing_widget.update()
            return

        damping_c_str, ok3 = QInputDialog.getText(drawing_widget, "弹簧参数", "阻尼系数 (damping_c, 可选):", text="0.1")
        if not ok3:
            self._reset_state(main_window)
            drawing_widget.update()
            return
        try:
            damping_c = float(damping_c_str)
            if damping_c < 0: raise ValueError("阻尼系数 c 必须为非负数。")
        except ValueError as e:
            QMessageBox.warning(drawing_widget, "输入错误", f"无效的阻尼系数: {e}")
            self._reset_state(main_window)
            drawing_widget.update()
            return

        anchor_a_local = main_window._get_local_point_for_entity(self.spring_first_entity_id, anchor_a_world) or Vector2D(0,0)
        anchor_b_local = main_window._get_local_point_for_entity(self.spring_second_entity_id, anchor_b_world) or Vector2D(0,0)

        try:
            spring_comp = entity_manager.create_independent_component(
                SpringComponent,
                entity_a_id=self.spring_first_entity_id,
                entity_b_id=self.spring_second_entity_id,
                rest_length=rest_length,
                stiffness_k=stiffness_k,
                damping_c=damping_c,
                anchor_a=anchor_a_local,
                anchor_b=anchor_b_local
            )
            QMessageBox.information(drawing_widget, "弹簧创建成功", f"弹簧 (ID: {spring_comp.id}) 已成功创建！")
        except ValueError as e:
            QMessageBox.critical(drawing_widget, "弹簧创建失败", f"创建弹簧组件时出错: {e}")
        except Exception as e:
            QMessageBox.critical(drawing_widget, "弹簧创建失败", f"创建弹簧时发生未知错误: {e}")
        finally:
            self._reset_state(main_window)
            drawing_widget.update()

    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        # Spring tool typically doesn't have a continuous preview during mouse move
        # other than the snap points, which are handled by DrawingWidget's main paintEvent.
        # If a line preview from the first selected anchor to the mouse is desired,
        # it would be implemented here and in paint_overlay.
        # For now, consistent with original behavior, no specific mouse move action.
        pass

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        # Mouse release is not the primary action trigger for spring creation;
        # it's driven by clicks.
        pass

    def paint_overlay(self, painter, drawing_widget: 'DrawingWidget'):
        # If a preview line from the first anchor to the current mouse position is desired
        # when spring_creation_phase == 1, it would be drawn here.
        # This requires self.spring_first_entity_click_pos_world and drawing_widget.current_mouse_world_pos
        main_window: 'MainWindow' = drawing_widget.window()
        if self.spring_creation_phase == 1 and self.spring_first_entity_click_pos_world and drawing_widget.current_mouse_world_pos:
            pen = QPen(QColor(Qt.GlobalColor.darkCyan), 1.5 / drawing_widget.pixels_per_world_unit, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            start_point_world = self.spring_first_entity_click_pos_world
            end_point_world = drawing_widget.current_mouse_world_pos # This should be updated by DrawingWidget
            
            # The painter is already transformed to world coordinates by DrawingWidget.paintEvent
            painter.drawLine(QPointF(start_point_world.x, start_point_world.y), 
                             QPointF(end_point_world.x, end_point_world.y))