from typing import Any, Optional, Dict, List, Tuple, Callable, Set
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QDoubleSpinBox,
    QCheckBox, QGroupBox, QFormLayout, QComboBox, QPushButton,
    QColorDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor

from physi_sim.core.entity_manager import EntityManager, EntityID # Import EntityID (likely UUID)
from physi_sim.core.component import Component, SpringComponent, ConnectionComponent, ConnectionType # Use ConnectionType Enum
from physi_sim.core.vector import Vector2D
from uuid import UUID # Import UUID
import dataclasses


class PropertyPanel(QWidget):
    """
    一个用于显示和编辑选中实体组件属性的面板。
    """
    # 信号：当属性被编辑时发射
    # 参数：object_id (UUID, 实体ID或弹簧ID), component_type_name (str), attribute_name (str), new_value (Any)
    property_changed = Signal(object, str, str, Any)

    # 信号：当弹簧锚点属性修改后，可能需要场景重绘
    spring_anchor_changed = Signal(UUID) # spring_id

    def __init__(self, entity_manager: EntityManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entity_manager = entity_manager
        self.current_selected_entity_ids: Set[UUID] = set()
        self.current_selected_connection_ids: Set[UUID] = set()
        self.component_widgets: Dict[str, QGroupBox] = {} # 存储组件对应的GroupBox
        # self.global_settings_group_box: Optional[QGroupBox] = None # Removed

        self._init_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_widget)
        self.properties_layout = QVBoxLayout(self.scroll_widget) # 布局将添加到可滚动区域的内容部件中
        self.properties_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.main_layout.addWidget(self.scroll_area)

        self.no_selection_label = QLabel("未选择任何对象", self) # Changed text
        self.no_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.properties_layout.addWidget(self.no_selection_label)
        self.hide() # Initially hidden

    @Slot(set, set) # Corrected Slot signature to match MainWindow's selection_changed signal
    def update_properties(self, selected_entity_ids: Set[UUID], selected_connection_ids: Set[UUID]):
        """
        当选中的对象集合发生变化时，更新属性面板的显示内容。
        """
        # Parameters are now guaranteed to be sets by the signal connection
        self.current_selected_entity_ids = selected_entity_ids
        self.current_selected_connection_ids = selected_connection_ids

        self._clear_properties()

        num_entities = len(self.current_selected_entity_ids)
        num_connections = len(self.current_selected_connection_ids)
        
        if num_entities == 0 and num_connections == 0:
            self.no_selection_label.setText("未选择任何对象")
            self.no_selection_label.show()
            self.hide() # Hide panel when nothing is selected
            return
        
        self.no_selection_label.hide()
        # if self.global_settings_group_box: # Removed
            # self.global_settings_group_box.hide()
            # self.global_settings_group_box.deleteLater()
            # self.global_settings_group_box = None

        self.show()

        if num_entities > 1:
            multi_select_label = QLabel(f"选中了 {num_entities} 个实体", self)
            self.properties_layout.addWidget(multi_select_label)
            # Optionally, if connections are also selected, add that info or handle as mixed.
            if num_connections > 0:
                 mixed_label = QLabel(f"同时选中了 {num_connections} 个连接", self)
                 self.properties_layout.addWidget(mixed_label)
            return # For now, stop if multiple entities selected

        if num_connections > 1:
            multi_select_label = QLabel(f"选中了 {num_connections} 个连接", self)
            self.properties_layout.addWidget(multi_select_label)
            # If entities also selected (should be num_entities == 0 or 1 here due to above check)
            if num_entities > 0: # This case means 1 entity and multiple connections, or 0 entities and multiple connections
                 mixed_label = QLabel(f"同时选中了 {num_entities} 个实体", self)
                 self.properties_layout.addWidget(mixed_label)
            return # Stop if multiple connections

        if num_entities == 1 and num_connections == 0:
            entity_id = list(self.current_selected_entity_ids)[0]
            # No need to check isinstance(entity_id, UUID) here as current_selected_entity_ids is now always a Set[UUID]
            components = self.entity_manager.get_all_components_for_entity(entity_id)
            if not components:
                display_id = str(entity_id)[:8]
                no_components_label = QLabel(f"实体 '{display_id}...' 没有组件", self)
                self.properties_layout.addWidget(no_components_label)
                return
            for component_instance in components.values():
                self._add_component_properties(entity_id, component_instance)

        elif num_connections == 1 and num_entities == 0:
            connection_id = list(self.current_selected_connection_ids)[0]
            # No need to check isinstance(connection_id, UUID) here
            
            # Try to identify if it's a SpringComponent first
            spring_component = self.entity_manager.get_independent_component_by_id(connection_id, SpringComponent)
            if spring_component:
                self._add_spring_properties(connection_id, spring_component)
            else:
                # Try to identify if it's a ConnectionComponent (Rod, Rope)
                connection_component = self.entity_manager.get_independent_component_by_id(connection_id, ConnectionComponent)
                if connection_component:
                    self._add_connection_properties(connection_id, connection_component)
                else:
                    # Fallback for other unknown connection types
                    conn_comp_generic = self.entity_manager.get_independent_component_by_id(connection_id, Component) # Try generic Component
                    if conn_comp_generic:
                        conn_type_name = conn_comp_generic.__class__.__name__
                        info_label = QLabel(f"选中连接: {conn_type_name} (ID: {str(connection_id)[:8]}...)\n(详细属性编辑待实现)", self)
                        self.properties_layout.addWidget(info_label)
                    else:
                        self._handle_invalid_selection(f"未找到连接 ID: {str(connection_id)[:8]}...")
        
        elif num_entities > 0 and num_connections > 0: # Mixed selection
            mixed_label = QLabel(f"混合选择: {num_entities} 个实体, {num_connections} 个连接。\n（属性编辑不支持混合选择）", self)
            self.properties_layout.addWidget(mixed_label)
            return
        else: # Should not be reached if logic above is correct
            self._handle_invalid_selection("未知选择状态")


    def _handle_invalid_selection(self, message: str = "无效选择"):
        self._clear_properties()
        self.no_selection_label.setText("无效选择")
        self.no_selection_label.show()
        self.hide() # Hide panel on invalid selection

    def _clear_properties(self):
        """
        清除当前显示的属性。
        """
        # 从后往前删除，避免索引问题
        for i in reversed(range(self.properties_layout.count())):
            item = self.properties_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget and widget != self.no_selection_label:
                    widget.deleteLater()
        self.component_widgets.clear()
        # self.no_selection_label should always be present, just shown/hidden
        self.no_selection_label.setText("未选择任何对象") # Reset text


    def _add_component_properties(self, entity_id: UUID, component: Component): # Added entity_id parameter
        component_class_name = component.__class__.__name__
        group_box = QGroupBox(component_class_name, self)
        form_layout = QFormLayout(group_box)

        if dataclasses.is_dataclass(component):
            fields = dataclasses.fields(component)
            for field in fields:
                attr_name = field.name
                attr_value = getattr(component, attr_name)
                attr_type = field.type

                # 忽略内部或非用户可编辑属性 (可以根据需要添加更复杂的逻辑)
                if attr_name.startswith("_"):
                    continue
                
                # Special handling for SpringComponent's entity IDs (read-only)
                if isinstance(component, SpringComponent) and attr_name in ("entity_a_id", "entity_b_id"):
                    label_widget = QLabel(str(attr_value), group_box)
                    label_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse) # Allow copying
                    form_layout.addRow(QLabel(f"{attr_name}:", group_box), label_widget)
                    continue


                editor = self._create_editor_for_attribute(
                    entity_id, # Pass entity_id
                    component_class_name,
                    attr_name,
                    attr_value,
                    attr_type,
                    is_spring_anchor=False # Not a spring anchor
                )
                if editor:
                    form_layout.addRow(QLabel(f"{attr_name}:", group_box), editor)
        else:
            # 对于非 dataclass 组件，可以尝试 __dict__，但需要更小心
            # 这里暂时只处理 dataclass
            label = QLabel("该组件类型不支持属性编辑或不是dataclass", group_box)
            form_layout.addRow(label)


        self.properties_layout.addWidget(group_box)
        self.component_widgets[component_class_name] = group_box

    def _create_editor_for_attribute(self, object_id: Optional[UUID], component_type_name: str, attr_name: str, attr_value: Any, attr_type: Any, is_spring_anchor: bool = False) -> Optional[QWidget]:
        editor: Optional[QWidget] = None
        
        # object_id is Optional[UUID] here (can be entity_id or spring_id)

        # 尝试解析 Union 类型, e.g., Optional[int] -> int
        actual_type = attr_type
        if hasattr(attr_type, "__origin__") and attr_type.__origin__ is list: # List[int]
            # 对于列表，目前简化处理，可以显示为字符串或只读
            # 或者如果元素类型简单，可以创建多个编辑器
            editor = QLineEdit(str(attr_value))
            editor.setReadOnly(True) # 简化：列表暂时只读
            return editor
        if hasattr(attr_type, "__args__"):
            # 针对 Optional[T] 或 Union[T, NoneType]
            non_none_args = [t for t in attr_type.__args__ if t is not type(None)]
            if len(non_none_args) == 1:
                actual_type = non_none_args[0]

        if actual_type is int:
            editor = QDoubleSpinBox(self) # 使用 QDoubleSpinBox 同时支持 int 和 float 的设置
            editor.setDecimals(0)
            editor.setRange(-2147483647, 2147483647) # int32范围 (corrected lower bound)
            editor.setValue(int(attr_value if attr_value is not None else 0))
            # Emit UUID directly
            editor.valueChanged.connect(
                lambda val, oid=object_id, ctn=component_type_name, an=attr_name:
                self.property_changed.emit(oid, ctn, an, int(val))
            )
        elif actual_type is float:
            editor = QDoubleSpinBox(self)
            editor.setDecimals(6) # 默认6位小数
            editor.setRange(-1.0e38, 1.0e38) # 大致的float范围
            editor.setValue(float(attr_value if attr_value is not None else 0.0))
            editor.valueChanged.connect(
                lambda val, oid=object_id, ctn=component_type_name, an=attr_name:
                self.property_changed.emit(oid, ctn, an, float(val))
            )
            # Make moment_of_inertia read-only
            if component_type_name == "PhysicsBodyComponent" and attr_name == "moment_of_inertia":
                editor.setReadOnly(True)
        elif actual_type is str:
            editor = QLineEdit(str(attr_value if attr_value is not None else ""), self)
            editor.textChanged.connect(
                lambda text, oid=object_id, ctn=component_type_name, an=attr_name:
                self.property_changed.emit(oid, ctn, an, text)
            )
        elif actual_type is bool:
            editor = QCheckBox(self)
            editor.setChecked(bool(attr_value if attr_value is not None else False))
            editor.stateChanged.connect(
                lambda state, oid=object_id, ctn=component_type_name, an=attr_name:
                self.property_changed.emit(oid, ctn, an, state == Qt.CheckState.Checked.value)
            )
        elif actual_type is Vector2D:
            # 对于 Vector2D，创建两个 QDoubleSpinBox
            vec_widget = QWidget(self)
            # 使用 QFormLayout 来更好地对齐 X, Y 标签和 SpinBox
            vec_form_layout = QFormLayout(vec_widget)
            vec_form_layout.setContentsMargins(0,0,0,0)
            # vec_form_layout.setSpacing(2) # 调整间距

            x_spinbox = QDoubleSpinBox(vec_widget)
            x_spinbox.setDecimals(3)
            x_spinbox.setRange(-1.0e6, 1.0e6)
            x_spinbox.setValue(attr_value.x if attr_value else 0.0) # Handle None attr_value
            # x_spinbox.setPrefix("X: ") # Prefix 不适用于 QFormLayout 的标签

            y_spinbox = QDoubleSpinBox(vec_widget)
            y_spinbox.setDecimals(3)
            y_spinbox.setRange(-1.0e6, 1.0e6)
            y_spinbox.setValue(attr_value.y if attr_value else 0.0) # Handle None attr_value
            # y_spinbox.setPrefix("Y: ")

            # 确保信号连接在 x_spinbox 和 y_spinbox 都创建之后
            # 当 x 变化时，y 使用当前的 y_spinbox.value()
            # 当 y 变化时，x 使用当前的 x_spinbox.value()
            x_spinbox.valueChanged.connect(
                lambda val, oid=object_id, _ctn=component_type_name, _an=attr_name, _ysb=y_spinbox, is_anchor=is_spring_anchor:
                self._emit_vector_change(oid, _ctn, _an, Vector2D(val, _ysb.value()), is_anchor)
            )
            y_spinbox.valueChanged.connect(
                lambda val, oid=object_id, _ctn=component_type_name, _an=attr_name, _xsb=x_spinbox, is_anchor=is_spring_anchor:
                self._emit_vector_change(oid, _ctn, _an, Vector2D(_xsb.value(), val), is_anchor)
            )

            vec_form_layout.addRow("X:", x_spinbox)
            vec_form_layout.addRow("Y:", y_spinbox)
            editor = vec_widget

        elif (isinstance(attr_value, (tuple, list))) and \
             len(attr_value) == 4 and \
             all(isinstance(i, (int, float)) for i in attr_value): # 假设是RGBA颜色 (int or float)

            # Ensure attr_value is not None before processing
            safe_attr_value = attr_value if attr_value is not None else (0,0,0,255) # Default to black if None
            
            current_color_tuple = tuple(int(c) for c in safe_attr_value) # Ensure int for QColor
            
            color_button = QPushButton(self)
            # Ensure current_qcolor uses the safe_attr_value
            current_qcolor = QColor(*current_color_tuple)
            self._update_button_color(color_button, current_qcolor)
            
            color_button.clicked.connect(
                lambda checked=False, btn=color_button, oid=object_id, ctn=component_type_name, an=attr_name, initial_c=current_qcolor:
                self._open_color_dialog(btn, oid, ctn, an, initial_c)
            )
            editor = color_button
        elif actual_type is UUID: # Handle UUID type as read-only
            editor = QLineEdit(str(attr_value if attr_value is not None else ""), self)
            editor.setReadOnly(True)
        else:
            # 对于未知类型或复杂类型，暂时显示为只读字符串
            editor = QLineEdit(str(attr_value if attr_value is not None else "None"), self)
            editor.setReadOnly(True)

        return editor

    def _emit_vector_change(self, object_id: Optional[UUID], component_type_name: str, attr_name: str, value: Vector2D, is_anchor: bool):
        self.property_changed.emit(object_id, component_type_name, attr_name, value)
        if is_anchor and object_id is not None: # If it's a spring anchor, emit specific signal
            self.spring_anchor_changed.emit(object_id)


    def _add_spring_properties(self, spring_id: UUID, spring_component: SpringComponent):
        group_box = QGroupBox("Spring Connection Properties", self)
        form_layout = QFormLayout(group_box)

        editable_attrs = {"rest_length", "stiffness_k", "damping_c", "anchor_a", "anchor_b"}

        if dataclasses.is_dataclass(spring_component):
            fields = dataclasses.fields(spring_component)
            for field in fields:
                attr_name = field.name
                attr_value = getattr(spring_component, attr_name)
                attr_type = field.type

                if attr_name.startswith("_"):
                    continue

                if attr_name in editable_attrs:
                    is_anchor = attr_name in ("anchor_a", "anchor_b")
                    editor = self._create_editor_for_attribute(
                        spring_id,
                        SpringComponent.__name__,
                        attr_name,
                        attr_value,
                        attr_type,
                        is_spring_anchor=is_anchor
                    )
                    if editor:
                        form_layout.addRow(QLabel(f"{attr_name}:", group_box), editor)
                elif attr_name in ("id", "entity_a_id", "entity_b_id"): # Read-only attributes
                    label_widget = QLabel(str(attr_value), group_box)
                    label_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    form_layout.addRow(QLabel(f"{attr_name}:", group_box), label_widget)
                # else: # Other fields, if any, are ignored for now
                    # pass

        self.properties_layout.addWidget(group_box)
        # Note: component_widgets is for entity components, spring has its own group box
        # If needed, a similar dict could be made for spring properties if multiple spring groups were possible.

    def _update_button_color(self, button: QPushButton, color: QColor):
        button.setStyleSheet(f"background-color: {color.name()}; color: {'black' if color.lightness() > 127 else 'white'};")

    def _open_color_dialog(self, button: QPushButton, object_id: Optional[UUID], component_type_name: str, attr_name: str, initial_color: QColor):
        dialog = QColorDialog(initial_color, self)
        if dialog.exec():
            new_color = dialog.selectedColor()
            self._update_button_color(button, new_color)
            self.property_changed.emit(object_id, component_type_name, attr_name, (new_color.red(), new_color.green(), new_color.blue(), new_color.alpha()))

    def _add_connection_properties(self, connection_id: UUID, conn_component: ConnectionComponent):
        group_box_title_prefix = conn_component.connection_type # "ROD" or "ROPE"
        group_box = QGroupBox(f"{group_box_title_prefix} Connection Properties", self)
        form_layout = QFormLayout(group_box)

        # Read-only attributes
        read_only_attrs = {"id", "source_entity_id", "target_entity_id", "connection_type"}
        # Directly editable attributes of ConnectionComponent
        direct_editable_attrs = {"connection_point_a", "connection_point_b", "is_broken", "break_threshold"}

        if dataclasses.is_dataclass(conn_component):
            fields = dataclasses.fields(conn_component)
            for field in fields:
                attr_name = field.name
                attr_value = getattr(conn_component, attr_name)
                attr_type = field.type

                if attr_name.startswith("_"):
                    continue

                if attr_name in read_only_attrs:
                    label_widget = QLabel(str(attr_value), group_box)
                    label_widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    form_layout.addRow(QLabel(f"{attr_name}:", group_box), label_widget)
                elif attr_name in direct_editable_attrs:
                    editor = self._create_editor_for_attribute(
                        connection_id,
                        ConnectionComponent.__name__,
                        attr_name,
                        attr_value,
                        attr_type,
                        is_spring_anchor=False
                    )
                    if editor:
                        form_layout.addRow(QLabel(f"{attr_name}:", group_box), editor)
                elif attr_name == "parameters":
                    # Handle the 'parameters' dictionary
                    parameters_group_box = QGroupBox("Parameters", group_box)
                    parameters_form_layout = QFormLayout(parameters_group_box)
                    
                    current_parameters_dict = attr_value # This is the dict e.g. {"target_length": 10.0, ...}
                    
                    param_keys_to_edit = []
                    if conn_component.connection_type == ConnectionType.ROD: # Use Enum
                        param_keys_to_edit = ["target_length"]
                    elif conn_component.connection_type == ConnectionType.ROPE: # Use Enum
                        param_keys_to_edit = ["natural_length"]

                    for param_key in param_keys_to_edit:
                        param_val = current_parameters_dict.get(param_key)
                        # All these are expected to be float.
                        # _create_editor_for_attribute handles None param_val by defaulting to 0.0 for float.
                        editor = self._create_editor_for_attribute(
                            connection_id,
                            ConnectionComponent.__name__,
                            f"parameters.{param_key}", # Hierarchical attribute name for the signal
                            param_val,
                            float, # Explicitly type as float for the editor creation
                            is_spring_anchor=False
                        )
                        if editor:
                            parameters_form_layout.addRow(QLabel(f"{param_key}:", parameters_group_box), editor)
                    
                    form_layout.addRow(parameters_group_box) # Add the parameters group to the main form layout for the connection
        
        self.properties_layout.addWidget(group_box)

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys

    # 模拟一些组件和实体管理器
    @dataclasses.dataclass
    class TransformComponent(Component):
        position: Vector2D = dataclasses.field(default_factory=lambda: Vector2D(0, 0))
        rotation: float = 0.0
        scale: Vector2D = dataclasses.field(default_factory=lambda: Vector2D(1, 1))
        visible: bool = True

    @dataclasses.dataclass
    class RenderComponent(Component):
        color: Tuple[int, int, int, int] = (255, 0, 0, 255) # RGBA
        z_order: int = 0
        shader: Optional[str] = None
        texture_path: List[str] = dataclasses.field(default_factory=list)


    class MockEntityManager:
        def __init__(self):
            self.entities = {
                "entity1": {
                    TransformComponent.__name__: TransformComponent(Vector2D(10, 20), 45.0, Vector2D(1.5, 1.5)),
                    RenderComponent.__name__: RenderComponent((0, 255, 0, 255), 1)
                },
                "entity2": {
                    TransformComponent.__name__: TransformComponent(Vector2D(-5, 15), 0.0, Vector2D(0.8, 0.8), False)
                }
            }

        def get_all_components_for_entity(self, entity_id: str) -> List[Component]:
            if entity_id in self.entities:
                return list(self.entities[entity_id].values())
            return []

        def get_component(self, entity_id: str, component_type: type) -> Optional[Component]:
            if entity_id in self.entities and component_type.__name__ in self.entities[entity_id]:
                return self.entities[entity_id][component_type.__name__]
            return None

        def update_component_attribute(self, entity_id: str, component_type_name: str, attribute_name: str, new_value: Any):
            print(f"Updating Entity: {entity_id}, Component: {component_type_name}, Attribute: {attribute_name}, New Value: {new_value}")
            # 在实际应用中，这里会找到对应的组件实例并更新其属性
            for entity, components_dict in self.entities.items():
                if entity == entity_id:
                    if component_type_name in components_dict:
                        component_instance = components_dict[component_type_name]
                        if hasattr(component_instance, attribute_name):
                            setattr(component_instance, attribute_name, new_value)
                            print(f"  Updated {attribute_name} to {getattr(component_instance, attribute_name)}")
                        else:
                            print(f"  Attribute {attribute_name} not found in {component_type_name}")
                    else:
                        print(f"  Component {component_type_name} not found for entity {entity_id}")
                    return


    app = QApplication(sys.argv)
    mock_em = MockEntityManager()
    panel = PropertyPanel(mock_em) # type: ignore

    # 模拟属性更改的处理 (Now receives Optional[UUID])
    def handle_property_change(entity_id_obj, component_type_name, attr_name, new_value):
        print(f"MainWindow received property_changed: Entity ID: {entity_id_obj}, Component: {component_type_name}, Attribute: {attr_name}, Value: {new_value}")
        # Mock EM expects string ID, convert UUID back for the mock
        entity_id_str = str(entity_id_obj) if entity_id_obj else ""
        mock_em.update_component_attribute(entity_id_str, component_type_name, attr_name, new_value)
        # 之后可能需要重新查询组件以验证，或触发场景更新
        # panel.update_properties(entity_id_obj) # 重新加载以显示更新（如果编辑器不直接反映）

    panel.property_changed.connect(handle_property_change)

    # panel.show() # Panel visibility is now controlled by update_properties

    # --- Mocking SpringComponent and its addition to EntityManager ---
    mock_spring_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    mock_spring = SpringComponent(
        id=mock_spring_id,
        entity_a_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"), # Dummy UUID
        entity_b_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"), # Dummy UUID
        rest_length=50.0,
        stiffness_k=10.0,
        damping_c=0.5,
        anchor_a=Vector2D(1,1),
        anchor_b=Vector2D(-1,-1)
    )

    # Add a mock method to EntityManager for the test
    def get_independent_component_by_id_mock(self, component_id: UUID, component_type: type):
        if component_id == mock_spring_id and component_type == SpringComponent:
            return mock_spring
        return None
    mock_em.get_independent_component_by_id = get_independent_component_by_id_mock.__get__(mock_em, MockEntityManager)
    # --- End Mocking SpringComponent ---


    # Simulate selection
    # panel.update_properties("ENTITY", UUID(mock_em.entities["entity1"]["TransformComponent"].id)) # Assuming components have IDs
    # For entity selection, let's use the mock entity_id string "entity1" and let PropertyPanel try to convert
    # A better mock would pass UUID directly if MainWindow does.
    # The current `update_properties` for ENTITY expects a UUID.
    # Let's create a mock entity_id for testing
    mock_entity1_id = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    
    # Adjust mock_em to use UUIDs as keys or adapt `get_all_components_for_entity`
    # For simplicity, let's assume `get_all_components_for_entity` can handle string keys from old test
    # but `update_properties` internally wants UUID for the entity part.
    # This test part needs care. Original test passed "entity1" (string).
    # The modified `update_properties` for "ENTITY" expects `selected_object_id` to be a UUID.
    
    # Let's make the mock `get_all_components_for_entity` accept UUID
    original_get_all_components = mock_em.get_all_components_for_entity
    def get_all_components_for_entity_uuid_mock(self, entity_id_uuid: UUID):
        # This mock is simplistic, assumes a mapping or specific test case
        if str(entity_id_uuid) == "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee": # Corresponds to "entity1" conceptually
             return list(self.entities["entity1"].values())
        return []
    mock_em.get_all_components_for_entity = get_all_components_for_entity_uuid_mock.__get__(mock_em, MockEntityManager)


    panel.update_properties("ENTITY", mock_entity1_id) # Simulate selecting an entity

    # Simulate selecting a spring
    def select_spring():
        print("\nSimulating Spring Selection...")
        panel.update_properties("SPRING_CONNECTION", mock_spring_id)

    # Simulate deselecting
    def deselect_all():
        print("\nSimulating Deselection...")
        panel.update_properties(None, None)

    # Simulate selecting another entity (entity2)
    mock_entity2_id = UUID("f<y_bin_540>f-ffff-ffff-ffff-ffffffffffff")
    def get_all_components_for_entity_uuid_mock_e2(self, entity_id_uuid: UUID):
        if str(entity_id_uuid) == "f<y_bin_540>f-ffff-ffff-ffff-ffffffffffff":
             return list(self.entities["entity2"].values())
        return []
    
    # Temporarily extend mock_em for entity2 with UUID
    # This is getting complex for a simple test, ideally mock_em uses UUIDs throughout
    _original_get_all_components_e2 = mock_em.get_all_components_for_entity
    def temp_get_all_comp(self, entity_id_uuid: UUID):
        if entity_id_uuid == mock_entity1_id:
            return list(self.entities["entity1"].values())
        if entity_id_uuid == mock_entity2_id:
            return list(self.entities["entity2"].values())
        return []
    mock_em.get_all_components_for_entity = temp_get_all_comp.__get__(mock_em, MockEntityManager)


    def select_entity2():
        print("\nSimulating Entity 2 Selection...")
        panel.update_properties("ENTITY", mock_entity2_id)


    from PySide6.QtCore import QTimer
    QTimer.singleShot(3000, select_spring)
    QTimer.singleShot(6000, select_entity2)
    QTimer.singleShot(9000, deselect_all)


    sys.exit(app.exec())