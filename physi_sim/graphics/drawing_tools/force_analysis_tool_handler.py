from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from physi_sim.graphics.drawing_tools.base_tool_handler import BaseToolHandler
from physi_sim.core.component import IdentifierComponent
from physi_sim.core.entity_manager import EntityManager # For type hinting

import uuid

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow, DrawingWidget, ToolMode, ForceAnalysisDisplayMode

class ForceAnalysisToolHandler(BaseToolHandler):
    """
    处理受力分析工具的逻辑。
    """

    def __init__(self):
        super().__init__()
        # force_analysis_target_entity_id is managed by MainWindow
        # force_analysis_display_mode is managed by MainWindow

    def activate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        if hasattr(main_window, 'status_bar'):
            if main_window.force_analysis_target_entity_id is None:
                main_window.status_bar.showMessage("受力分析工具已激活。请点击一个实体进行分析。", 3000)
            else:
                # If an entity is already selected for analysis, reflect that
                entity_manager: EntityManager = main_window.entity_manager
                entity_name_comp = entity_manager.get_component(main_window.force_analysis_target_entity_id, IdentifierComponent)
                entity_display_name = str(main_window.force_analysis_target_entity_id)[:8]
                if entity_name_comp and entity_name_comp.name:
                    entity_display_name = f"'{entity_name_comp.name}' ({str(main_window.force_analysis_target_entity_id)[:8]})"
                main_window.status_bar.showMessage(f"受力分析: 实体 {entity_display_name}。模式: {main_window.force_analysis_display_mode.name}。", 3000)
        
        drawing_widget.setCursor(Qt.WhatsThisCursor) # Or another appropriate cursor

    def deactivate(self, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        # No specific state to reset within this handler itself, as MainWindow holds the state.
        # Clearing the target entity on deactivation might be too aggressive if the user
        # just temporarily switches tools. Let MainWindow manage that if needed.
        if hasattr(main_window, 'status_bar'):
            main_window.status_bar.clearMessage()
        drawing_widget.setCursor(Qt.CursorShape.ArrowCursor)
        drawing_widget.update() # Ensure any highlights are cleared if MainWindow logic dictates

    def handle_mouse_press(self, event, drawing_widget: 'DrawingWidget'):
        main_window: 'MainWindow' = drawing_widget.window()
        entity_manager: EntityManager = main_window.entity_manager
        click_pos_world = drawing_widget._get_world_coordinates(event.position())
        
        hit_entity_id = main_window._get_entity_at_world_pos(click_pos_world)

        if hit_entity_id is not None:
            if main_window.force_analysis_target_entity_id != hit_entity_id:
                main_window.force_analysis_target_entity_id = hit_entity_id
                entity_name_comp = entity_manager.get_component(hit_entity_id, IdentifierComponent)
                entity_display_name = str(hit_entity_id)[:8]
                if entity_name_comp and entity_name_comp.name:
                    entity_display_name = f"'{entity_name_comp.name}' ({str(hit_entity_id)[:8]})"
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage(f"受力分析: 已选中实体 {entity_display_name}。模式: {main_window.force_analysis_display_mode.name}。", 5000)
            # If clicking the same entity, no change in target, status message might refresh or stay.
        else: # Clicked on empty space
            if main_window.force_analysis_target_entity_id is not None:
                main_window.force_analysis_target_entity_id = None # Deselect
                if hasattr(main_window, 'status_bar'):
                    main_window.status_bar.showMessage("受力分析模式: 请点击一个实体进行分析。", 3000)
        
        drawing_widget.update() # Redraw for highlight changes

    def handle_mouse_move(self, event, drawing_widget: 'DrawingWidget'):
        # Force analysis tool typically doesn't have a dynamic preview on mouse move.
        pass

    def handle_mouse_release(self, event, drawing_widget: 'DrawingWidget'):
        # Actions are triggered by mouse press (selection).
        pass

    def paint_overlay(self, painter, drawing_widget: 'DrawingWidget'):
        # Any specific overlay for force analysis (beyond what RendererSystem does)
        # could be drawn here. For now, RendererSystem handles force vector display.
        pass