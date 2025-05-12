from PySide6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
import json
import os

from physi_sim.scene.scene_serializer import SceneSerializer

from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from physi_sim.graphics.main_window import MainWindow # Avoid circular import

class SceneFileHandler:
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window
        self.entity_manager = main_window.entity_manager
        self.scene_manager = main_window.scene_manager

    def new_scene(self):
        self.scene_manager.new_scene()
        self.main_window.clear_selection()
        # Reset tool-specific states if they are still in MainWindow (should be in handlers)
        # For now, assume tool handlers' deactivate/activate will manage their state.
        # If MainWindow still holds some specific states for tools like spring/rod/rope creation,
        # those would be reset here or by calling a general reset method in MainWindow.
        # self.main_window._reset_spring_selection() # Example, if still needed from MainWindow
        # self.main_window._reset_rod_selection()
        # self.main_window._reset_rope_selection()

        self.main_window._capture_and_store_initial_state()
        self.main_window._update_window_title()
        self.main_window.drawing_widget.update()

    def handle_open_scene(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "打开场景或快照文件",
            self.scene_manager.current_scene_filepath or ".",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    json_string = f.read()

                self.entity_manager.clear_all()
                self.main_window.clear_selection()

                serializer = SceneSerializer()
                loaded_data = serializer.deserialize_json_string_to_scene(json_string, self.entity_manager)

                if loaded_data.get("status") == "error":
                    QMessageBox.critical(self.main_window, "加载失败", f"无法加载文件: {loaded_data.get('message', '未知错误')}")
                    self.scene_manager.new_scene()
                    self.main_window._capture_and_store_initial_state()
                    self.main_window._update_window_title()
                    self.main_window.drawing_widget.update()
                    return

                loaded_time = loaded_data.get("simulation_time", 0.0)
                self.main_window.is_simulation_running = False
                if hasattr(self.main_window, 'pause_resume_action'):
                    self.main_window.pause_resume_action.setText("继续")

                self.scene_manager.current_scene_filepath = filepath
                self.main_window._update_window_title()
                self.main_window._capture_and_store_initial_state()
                self.main_window.current_simulation_time = loaded_time
                self.main_window._update_time_display()
                
                self.main_window.status_bar.showMessage(f"场景 '{os.path.basename(filepath)}' 已加载。时间: {loaded_time:.2f}s。此状态已设为新起点。", 5000)
                self.main_window.drawing_widget.update()
            except FileNotFoundError:
                QMessageBox.critical(self.main_window, "加载失败", f"文件未找到: {filepath}")
            except json.JSONDecodeError as e:
                QMessageBox.critical(self.main_window, "加载失败", f"JSON 解析错误: {e}\n文件: {filepath}")
            except ValueError as e:
                QMessageBox.critical(self.main_window, "加载失败", f"加载场景时出错: {e}\n文件: {filepath}")
            except Exception as e:
                QMessageBox.critical(self.main_window, "加载失败", f"加载场景时发生未知错误: {e}\n文件: {filepath}")
                self.scene_manager.new_scene()
                self.main_window._capture_and_store_initial_state()
                self.main_window._update_window_title()
                self.main_window.drawing_widget.update()

    def handle_save_snapshot_as(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "保存模拟快照为",
            self.scene_manager.current_scene_filepath or "模拟快照.json",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if filepath:
            try:
                serializer = SceneSerializer()
                json_string = serializer.serialize_scene_to_json_string(
                    self.entity_manager,
                    include_time=True,
                    current_time=self.main_window.current_simulation_time
                )
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(json_string)
                
                self.scene_manager.current_scene_filepath = filepath # Update for consistency
                self.main_window._update_window_title()
                QMessageBox.information(self.main_window, "保存成功", f"模拟快照已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self.main_window, "保存快照失败", f"保存模拟快照时出错: {e}")

    def handle_save_initial_setup_as(self):
        if self.main_window._initial_scene_state_json is None:
            QMessageBox.warning(self.main_window, "无法保存初始设置",
                                "没有已存储的初始场景状态。\n"
                                "请先加载一个场景，或使用“将当前存为新起点并另存为”。")
            return

        try:
            temp_data = json.loads(self.main_window._initial_scene_state_json)
            if "simulation_time" in temp_data:
                QMessageBox.warning(self.main_window, "状态警告", "内部初始状态似乎包含时间戳。将尝试移除它。")
                del temp_data["simulation_time"]
                self.main_window._initial_scene_state_json = json.dumps(temp_data, indent=2)
        except Exception:
            pass 

        filepath, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "保存初始设置为",
            "场景初始设置.json",
            "JSON 文件 (*.json);;所有文件 (*)"
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.main_window._initial_scene_state_json)
                QMessageBox.information(self.main_window, "保存成功", f"初始场景设置已保存到:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self.main_window, "保存失败", f"保存初始场景设置时发生错误: {e}")

    def handle_save_current_as_start_point_as(self):
        was_running = self.main_window.is_simulation_running
        if self.main_window.is_simulation_running:
            self.main_window._toggle_pause_resume() 

        self.main_window._capture_and_store_initial_state()
        self.handle_save_initial_setup_as() # Calls the method from this handler
        # Optionally restore simulation state, but usually a new start point implies pause.