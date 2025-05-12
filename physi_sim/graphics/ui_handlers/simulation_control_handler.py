from PySide6.QtWidgets import QInputDialog, QMessageBox, QApplication
from PySide6.QtCore import Qt

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow # Avoid circular import
    from physi_sim.scene.scene_serializer import SceneSerializer # For type hinting if methods are moved here

class SimulationControlHandler:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window

    def toggle_pause_resume(self):
        self.main_window.is_simulation_running = not self.main_window.is_simulation_running
        if self.main_window.is_simulation_running:
            if hasattr(self.main_window, 'pause_resume_action'):
                self.main_window.pause_resume_action.setText("暂停")
        else:
            if hasattr(self.main_window, 'pause_resume_action'):
                self.main_window.pause_resume_action.setText("继续")
        self.main_window._update_time_display()

    def jump_to_time(self):
        target_time_str, ok = QInputDialog.getText(
            self.main_window, 
            "跳转到时间", 
            "请输入目标模拟时间 (秒):", 
            text=f"{self.main_window.current_simulation_time:.2f}"
        )
        if not ok or not target_time_str:
            return

        try:
            target_time = float(target_time_str)
            if target_time < 0:
                QMessageBox.warning(self.main_window, "无效时间", "目标时间不能为负数。")
                return
        except ValueError:
            QMessageBox.warning(self.main_window, "无效输入", "请输入一个有效的时间数值。")
            return

        was_running = self.main_window.is_simulation_running
        if self.main_window.is_simulation_running:
            self.toggle_pause_resume() # Pauses simulation

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        if self.main_window._initial_scene_state_json is None:
            QMessageBox.critical(self.main_window, "无法跳转", "没有可用的初始场景状态。")
            QApplication.restoreOverrideCursor()
            if was_running: self.toggle_pause_resume() # Resume if it was running
            return
        
        try:
            # SceneSerializer needs to be imported or passed if this method is fully standalone
            from physi_sim.scene.scene_serializer import SceneSerializer
            SceneSerializer.deserialize_from_string(self.main_window.entity_manager, self.main_window._initial_scene_state_json)
            self.main_window.current_simulation_time = 0.0
            self.main_window.clear_selection()
            self.main_window._update_time_display()
        except Exception as e:
            QMessageBox.critical(self.main_window, "状态恢复错误", f"无法恢复初始场景状态: {e}")
            QApplication.restoreOverrideCursor()
            if was_running: self.toggle_pause_resume()
            return

        if target_time > self.main_window.dt / 2:
            steps_to_simulate = int(target_time / self.main_window.dt)
            for i in range(steps_to_simulate):
                if i % 100 == 0: QApplication.processEvents()
                self.main_window._perform_simulation_step_core(render=False)
            self.main_window.current_simulation_time = target_time # Precise time
        else:
            self.main_window.current_simulation_time = target_time
            
        self.main_window._update_time_display()
        self.main_window.drawing_widget.update()
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self.main_window, "跳转完成", f"已跳转到模拟时间: {self.main_window.current_simulation_time:.2f}s")

        if was_running:
            self.toggle_pause_resume() # Resumes simulation

    def set_current_as_initial_state(self):
        was_running = self.main_window.is_simulation_running
        if self.main_window.is_simulation_running:
            self.toggle_pause_resume()

        self.main_window._capture_and_store_initial_state()
        QMessageBox.information(self.main_window, "设置初始状态", "当前场景状态已设为新的时间起点 (t=0)。")
        self.main_window.drawing_widget.update()
        # Keep it paused after this operation.

    def toggle_gravity(self, checked: bool):
        if self.main_window.physics_system:
            self.main_window.physics_system.toggle_gravity(checked)
            status_message = "重力已启用。" if checked else "重力已禁用。"
            if hasattr(self.main_window, 'status_bar'):
                self.main_window.status_bar.showMessage(status_message, 2000)
        else:
            QMessageBox.warning(self.main_window, "错误", "物理系统尚未初始化，无法切换重力。")
            if hasattr(self.main_window, 'toggle_gravity_action'):
                self.main_window.toggle_gravity_action.setChecked(not checked)