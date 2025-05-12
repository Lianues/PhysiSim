# PhysiSim (物理场景模拟器)

## 项目简介

PhysiSim 是一个基于组件的二维物理模拟器，旨在为用户提供一个直观、易用的平台，用于学习、实验和探索各种物理现象。它允许用户通过图形化界面构建复杂的物理场景，观察物体的运动、碰撞和相互作用，并进行简单的受力分析和脚本化控制。

## 当前状态

项目已成功完成 **里程碑 A** 的开发。主要成果包括：

*   搭建了稳定的实体组件系统 (ECS) 架构。
*   实现了核心物理引擎，包括精确的碰撞检测 (SAT) 与响应、多种连接器（弹簧、理想杆、理想绳、转轴）以及接触力模拟。
*   开发了功能丰富的高级GUI，支持场景构建、属性编辑、视图控制和模拟控制。
*   引入了受力分析可视化工具。
*   实现了场景的加载、保存以及对象预设系统。
*   物理引擎核心已迁移到基于约束动力学的 `ConstraintSolverSystem` ([`physi_sim/physics/constraint_solver_system.py:1`](physi_sim/physics/constraint_solver_system.py:1))，用于处理杆、绳和转轴等约束。

## 核心特性列表

*   **图形化场景构建**:
    *   支持创建和编辑多种几何形状：矩形、圆形、自定义多边形。
    *   直观的拖拽操作用于放置和调整物体。
*   **实体组件系统 (ECS) 架构**:
    *   灵活的架构，通过组合不同的组件来定义实体的行为和属性。
    *   核心组件包括：`TransformComponent` ([`physi_sim/core/component.py`](physi_sim/core/component.py)), `GeometryComponent` ([`physi_sim/core/component.py`](physi_sim/core/component.py)), `PhysicsBodyComponent` ([`physi_sim/core/component.py`](physi_sim/core/component.py)), `RenderComponent` ([`physi_sim/core/component.py`](physi_sim/core/component.py)), `ConnectionComponent` ([`physi_sim/core/component.py`](physi_sim/core/component.py)) 等。
*   **物理模拟引擎**:
    *   **动力学**: 精确模拟物体的平动和旋转运动。
    *   **碰撞检测与响应**:
        *   采用分离轴定理 (SAT) 进行精确的多边形间碰撞检测。
        *   支持圆形与圆形、圆形与多边形、多边形与多边形的碰撞对。
        *   基于冲量的碰撞响应模型。
    *   **接触力**: 模拟支持力和摩擦力（静摩擦和动摩擦）。
    *   **连接器**:
        *   **弹簧 (Spring)**: 基于胡克定律模拟弹性力。
        *   **理想轻杆 (Rod)**: 通过约束动力学 (`ConstraintSolverSystem` ([`physi_sim/physics/constraint_solver_system.py:1`](physi_sim/physics/constraint_solver_system.py:1))) 实现长度约束。
        *   **理想轻绳 (Rope)**: 通过约束动力学 (`ConstraintSolverSystem` ([`physi_sim/physics/constraint_solver_system.py:1`](physi_sim/physics/constraint_solver_system.py:1))) 实现最大长度约束和张力。
        *   **转轴/旋转关节 (Revolute Joint)**: 通过约束动力学 (`ConstraintSolverSystem` ([`physi_sim/physics/constraint_solver_system.py:1`](physi_sim/physics/constraint_solver_system.py:1))) 实现两物体间的相对旋转。
*   **高级GUI工具与交互**:
    *   **属性面板**: 实时查看和编辑选中实体的组件属性。
    *   **选择工具**: 支持单击选择、拖拽多选、框选、按类型选择物体。
    *   **视图控制**: 支持场景视图的平移和缩放。
    *   **模拟时间控制**: 控制模拟的开始、暂停、继续和重置。
    *   **受力分析可视化**:
        *   在“对象模式”下显示作用在单个物体上的合力与分力。
        *   在“质心模式”下显示作用在物体质心上的合力。
*   **场景管理**:
    *   支持新建、加载和保存场景 (使用JSON格式)。
    *   **预设系统**: 支持将单个实体或组合对象保存为预设，方便复用。
*   **基础脚本求解**:
    *   提供 `SolverModule` ([`physi_sim/physics/solver_module.py:1`](physi_sim/physics/solver_module.py:1))，用于基于 `SymPy` 进行简单的代数方程求解。

## 技术栈

*   **核心语言**: Python 3.x
*   **图形用户界面 (GUI)**: PySide6
*   **数值计算**: NumPy (广泛用于向量运算、物理计算等)
*   **符号计算**: SymPy (用于 [`SolverModule`](physi_sim/physics/solver_module.py:1))

## 项目结构概览

```
physi_sim/
├── main.py                 # 程序主入口
├── core/                   # 核心ECS架构、向量、组件基类、系统基类等
│   ├── entity_manager.py   # 实体和组件管理器
│   ├── component.py        # 各类组件定义
│   ├── system.py           # 系统基类
│   └── vector.py           # 二维向量类
├── physics/                # 物理引擎相关模块
│   ├── physics_system.py       # 基础动力学更新
│   ├── collision_system.py     # 碰撞检测与响应
│   ├── constraint_solver_system.py # 基于约束的动力学求解系统 (杆、绳、转轴等)
│   ├── constraint_solver.py    # 约束求解器实现
│   ├── force_calculator.py     # 力计算 (如重力、弹簧力等)
│   └── solver_module.py        # 基于SymPy的符号求解模块
├── graphics/               # 图形渲染与GUI交互
│   ├── renderer_system.py    # 场景渲染系统
│   ├── main_window.py        # 主应用程序窗口
│   ├── property_panel.py     # 属性编辑面板
│   └── drawing_tools/        # 各种绘图工具的处理器
├── scene/                  # 场景管理与序列化
│   ├── scene_manager.py      # 场景加载、保存、预设管理
│   └── scene_serializer.py   # 场景JSON序列化/反序列化
├── scripting/              # 用户脚本与事件处理 (里程碑B重点)
│   └── script_engine.py      # 脚本执行引擎 (初步)
└── assets/                 # 资源文件 (如预设)
```
*   **`core/`**: 包含项目的基础架构，如实体组件系统 (ECS) 的核心实现 (`EntityManager` ([`physi_sim/core/entity_manager.py`](physi_sim/core/entity_manager.py), `Component` ([`physi_sim/core/component.py`](physi_sim/core/component.py), `System` ([`physi_sim/core/system.py`](physi_sim/core/system.py)))、二维向量类 (`Vector2D` ([`physi_sim/core/vector.py`](physi_sim/core/vector.py))) 和其他通用工具。
*   **`physics/`**: 负责所有物理计算，包括动力学更新 (`PhysicsSystem` ([`physi_sim/physics/physics_system.py`](physi_sim/physics/physics_system.py)))、碰撞检测与响应 (`CollisionSystem` ([`physi_sim/physics/collision_system.py`](physi_sim/physics/collision_system.py)))、约束求解 (`ConstraintSolverSystem` ([`physi_sim/physics/constraint_solver_system.py:1`](physi_sim/physics/constraint_solver_system.py:1))) 和力计算 (`ForceCalculator` ([`physi_sim/physics/force_calculator.py`](physi_sim/physics/force_calculator.py)))。
*   **`graphics/`**: 处理所有与图形用户界面 (GUI) 和渲染相关的功能，包括场景的绘制 (`RendererSystem` ([`physi_sim/graphics/renderer_system.py`](physi_sim/graphics/renderer_system.py)))、主窗口 (`MainWindow` ([`physi_sim/graphics/main_window.py`](physi_sim/graphics/main_window.py)))、属性编辑面板 (`PropertyPanel` ([`physi_sim/graphics/property_panel.py`](physi_sim/graphics/property_panel.py))) 以及用户交互的绘图工具。
*   **`scene/`**: 管理场景的生命周期，包括场景的创建、加载、保存 (`SceneManager` ([`physi_sim/scene/scene_manager.py`](physi_sim/scene/scene_manager.py))) 以及将场景数据序列化为JSON格式或从JSON反序列化 (`SceneSerializer` ([`physi_sim/scene/scene_serializer.py`](physi_sim/scene/scene_serializer.py)))。
*   **`scripting/`**: (目前较基础) 包含脚本执行的相关逻辑，未来将扩展为用户事件规则系统。

## 如何运行 (初步)

1.  **确保环境**:
    *   已安装 Python (建议 3.8 或更高版本)。
    *   已安装必要的第三方库。可以通过 pip 安装：
        ```bash
        pip install PySide6 numpy sympy
        ```
2.  **运行程序**:
    在项目根目录下，执行以下命令启动模拟器：
    ```bash
    python physi_sim/main.py
    ```

## 后续计划 (简述)

*   **里程碑 B：用户事件规则系统**:
    *   设计并实现一个灵活的用户事件规则系统，允许用户通过 "IF-THEN" 结构定义场景中物体的行为逻辑，例如： "IF 物体A 接触 物体B THEN 物体A 改变颜色"。
    *   完善 `scripting/` ([`physi_sim/scripting/`](physi_sim/scripting/)) 模块，提供更强大的脚本API。
*   **持续改进**:
    *   **性能优化**: 针对大规模场景进行性能分析和优化。
    *   **高级碰撞处理**: 研究并实现更复杂的碰撞现象，如堆叠、连续碰撞检测 (CCD)。
    *   **更多物理模型**: 引入流体、软体等更高级的物理模型。
    *   **用户体验增强**: 持续打磨GUI，提升易用性和美观度。
    *   **文档完善**: 提供更详细的API文档和用户手册。

## 贡献指南

(暂无，未来如果项目发展需要，会在此处添加贡献指南。)

## 致谢

(暂无，未来如果项目发展需要，会在此处添加致谢信息。)