import sys
import os
# Add the parent directory (project root) to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from physi_sim.graphics.main_window import MainWindow
from physi_sim.core.entity_manager import EntityManager
from physi_sim.graphics.renderer_system import RendererSystem
# Import SpringSystem here
from physi_sim.physics import PhysicsSystem, CollisionSystem, ConstraintSolver, SolverModule, SpringSystem, RopeSystem # Added RopeSystem
from physi_sim.core.utils import GRAVITY_ACCELERATION # Added
from physi_sim.core.component import IdentifierComponent, TransformComponent, GeometryComponent, RenderComponent, ShapeType # Import ShapeType
from physi_sim.core.component import PhysicsBodyComponent, ForceAccumulatorComponent, SurfaceComponent, ConnectionComponent, ConnectionType, ScriptExecutionComponent, SpringComponent # Use ConnectionType Enum
from physi_sim.core.vector import Vector2D
from uuid import UUID # For creating connections
from physi_sim.scripting import ScriptEngine
# PySide6.QtCore.Qt might be needed by RendererSystem if not already imported there for NoBrush
# from PySide6.QtCore import Qt, QTimer # QTimer no longer needed here

def main():
    app = QApplication(sys.argv)
    
    entity_manager = EntityManager()
    
    # Initialize Systems
    physics_system = PhysicsSystem(entity_manager, gravity=GRAVITY_ACCELERATION) # Restore GRAVITY
    collision_system = CollisionSystem(entity_manager) # Restore
    constraint_solver = ConstraintSolver(entity_manager, iterations=10) # PBD for RODs needs iterations
    script_engine = ScriptEngine(entity_manager) # Restore
    spring_system = SpringSystem(entity_manager) # Instantiate SpringSystem
    rope_system = RopeSystem(entity_manager) # Instantiate RopeSystem

    # 清空场景，确保测试环境纯净
    entity_manager.clear_all()
    
    # --- 偏心连接测试场景 (已移除) ---
            
    main_window = MainWindow(entity_manager) # MainWindow initialization, pass entity_manager
    
    # Set systems for MainWindow
    # main_window.entity_manager = entity_manager # This line is no longer needed as EM is set in __init__
    renderer_system_instance = RendererSystem(entity_manager) # drawing_widget no longer passed
    main_window.renderer_system = renderer_system_instance
    main_window.drawing_widget.renderer_system = renderer_system_instance # DrawingWidget still needs it
    main_window.physics_system = physics_system # Keep for potential integration later, but ensure its update is controlled
    main_window.collision_system = collision_system # Restore
    main_window.constraint_solver = constraint_solver # Restore
    main_window.script_engine = script_engine # Restore
    main_window.spring_system = spring_system # Set SpringSystem
    main_window.rope_system = rope_system # Set RopeSystem

    main_window.show()

    # --- Solver Module Test --- Restore
    print("\n--- Testing SolverModule ---")
    solver_module = SolverModule()
    # test_eqs = ["v_final = v_initial + a * t", "v_initial = 0", "a = 9.81", "t = 2"]
    # test_unks = ["v_final", "v_initial", "a", "t"] # Include knowns if they appear in equations
    # Solve for v_final specifically might require different handling or sympy features.
    # Let's solve the system as is.
    # Better test: solve for v_final when others are known.
    # test_eqs_2 = ["Eq(v_final, v_initial + a * t)", "Eq(v_initial, 0)", "Eq(a, 9.81)", "Eq(t, 2)"]
    # test_unks_2 = ["v_final"] # Unknown we want to solve for
    # This setup doesn't quite work with solve directly for one unknown when others are defined by Eq.
    # Let's use a simpler algebraic system test.
    test_eqs_3 = ["x + y - 10", "2*x - y - 5"]
    test_unks_3 = ["x", "y"]
    solution = solver_module.solve_algebraic_system(test_eqs_3, test_unks_3)
    print(f"Solving {test_eqs_3} for {test_unks_3}:")
    print(f"Solution: {solution}")
    print("--------------------------")

    sys.exit(app.exec())

if __name__ == '__main__':
    main()