from abc import ABC, abstractmethod

class BaseToolHandler(ABC):
    """
    工具处理器基类/接口，定义了绘图工具处理鼠标事件和绘制行为的统一接口。
    """

    @abstractmethod
    def handle_mouse_press(self, event, drawing_widget):
        """处理鼠标按下事件"""
        pass

    @abstractmethod
    def handle_mouse_move(self, event, drawing_widget):
        """处理鼠标移动事件"""
        pass

    @abstractmethod
    def handle_mouse_release(self, event, drawing_widget):
        """处理鼠标释放事件"""
        pass

    def paint_overlay(self, painter, drawing_widget):
        """
        可选方法，用于工具特定的临时绘制。
        默认不执行任何操作。
        """
        pass

    def activate(self, drawing_widget):
        """
        可选方法，工具激活时调用。
        默认不执行任何操作。
        """
        pass

    def deactivate(self, drawing_widget):
        """
        可选方法，工具失活时调用。
        默认不执行任何操作。
        """
        pass