import sympy
from typing import List, Dict, Any, Optional, Union

class SolverModule:
    """Provides functionality to solve algebraic equation systems using SymPy."""

    def solve_algebraic_system(self,
                               equations: List[str],
                               unknowns: List[str]) -> Union[List[Dict[str, Any]], str, None]:
        """
        Solves a system of algebraic equations given as strings.

        Args:
            equations: List of equation strings (e.g., "x + y - 5", "Eq(x, y + 1)").
                       Assumes equations are implicitly equal to zero if not using Eq().
            unknowns: List of unknown variable names as strings (e.g., ["x", "y"]).

        Returns:
            - List of dictionaries, where each dict is a solution {var_name: value}.
            - A string message indicating no solution, infinite solutions, or an error.
            - None if an unexpected error occurs during processing.
        """
        if not equations or not unknowns:
            return "Error: Equations or unknowns list cannot be empty."

        try:
            # 1. Convert unknown strings to SymPy symbols
            # Join the list of unknown strings into a single comma-separated string
            symbols_str = ','.join(unknowns)
            parsed_symbols = sympy.symbols(symbols_str)

            if not isinstance(parsed_symbols, tuple): # If only one unknown, symbols() returns a single symbol
                 symbols = (parsed_symbols,)
            else:
                 symbols = parsed_symbols

            # Ensure the number of symbols matches the unknowns list
            if len(symbols) != len(unknowns):
                 return f"Error: Could not correctly parse all unknowns: {unknowns}"

            symbol_map = {str(s): s for s in symbols} # Map string name back to symbol if needed

            # 2. Convert equation strings to SymPy expressions/equations
            parsed_equations = []
            for eq_str in equations:
                # Try to parse using sympify, assuming implicit "= 0" if no Eq()
                # For safety, only allow basic math and registered symbols in the context
                local_dict = {name: sym for name, sym in symbol_map.items()}
                # Add safe math functions if needed: local_dict.update({'sin': sympy.sin, ...})

                try:
                     # Attempt to parse. If it doesn't contain 'Eq(', assume implicit '= 0'.
                     if 'Eq(' not in eq_str:
                         expr = sympy.sympify(eq_str, locals=local_dict)
                         parsed_equations.append(expr) # Implicitly expr = 0
                     else:
                         # If Eq() is used, parse it directly
                         # Need to ensure Eq is available in the context
                         local_dict['Eq'] = sympy.Eq
                         eq_obj = sympy.sympify(eq_str, locals=local_dict)
                         if isinstance(eq_obj, sympy.Equality):
                             parsed_equations.append(eq_obj)
                         else:
                              # If sympify results in non-Eq, treat as implicit = 0
                              # This might happen if Eq was part of a larger expression not resulting in Eq
                              parsed_equations.append(eq_obj)
                             # return f"Error: Could not parse equation string with Eq(): {eq_str}"

                except (SyntaxError, TypeError, NameError, sympy.SympifyError) as parse_err:
                    return f"Error parsing equation '{eq_str}': {parse_err}"

            if not parsed_equations:
                 return "Error: No valid equations were parsed."

            # 3. Solve the system
            # Use dict=True to get solutions as dictionaries
            # Use check=False to handle under/overdetermined systems without errors
            solution = sympy.solve(parsed_equations, symbols, dict=True, check=False)

            # 4. Process the solution
            if isinstance(solution, list) and len(solution) > 0 and isinstance(solution[0], dict):
                # Found one or more distinct solutions
                processed_solutions = []
                for sol_dict in solution:
                    processed_dict = {}
                    for sym, val in sol_dict.items():
                        try:
                            # Convert SymPy numbers to Python float/int
                            if isinstance(val, (sympy.Float, sympy.Rational)):
                                processed_dict[str(sym)] = float(val)
                            elif isinstance(val, sympy.Integer):
                                 processed_dict[str(sym)] = int(val)
                            else:
                                 # Keep other types (like symbols if underdetermined) as string representation
                                 processed_dict[str(sym)] = str(val)
                        except Exception:
                             processed_dict[str(sym)] = str(val) # Fallback to string
                    processed_solutions.append(processed_dict)
                return processed_solutions
            elif isinstance(solution, list) and len(solution) == 0:
                # No solution found by solve
                # Need to be careful, solve might return empty list for infinite solutions too in some cases
                # Let's try nonlinsolve for potentially better info on infinite/no solutions
                try:
                     nonlin_sol = sympy.nonlinsolve(parsed_equations, symbols)
                     if nonlin_sol == sympy.EmptySet:
                         return "No solution found."
                     elif nonlin_sol.is_FiniteSet:
                         # This case should ideally be handled by the dict=True solve above,
                         # but as a fallback, process the FiniteSet if needed.
                         # For now, treat empty list from solve() as "No solution".
                         return "No solution found."
                     else:
                         # Likely infinite solutions if nonlinsolve returns a set with symbols
                         return "Infinite solutions or unable to determine uniqueness."
                except NotImplementedError:
                     return "Solver does not support this type of system (potentially non-algebraic or complex)."
                except Exception:
                     return "Could not determine solution status (solve returned empty list)."

            elif isinstance(solution, dict):
                 # Single solution dictionary (older sympy versions might do this?)
                 processed_dict = {}
                 for sym, val in solution.items():
                      try:
                           if isinstance(val, (sympy.Float, sympy.Rational)):
                               processed_dict[str(sym)] = float(val)
                           elif isinstance(val, sympy.Integer):
                                processed_dict[str(sym)] = int(val)
                           else:
                                processed_dict[str(sym)] = str(val)
                      except Exception:
                           processed_dict[str(sym)] = str(val)
                 return [processed_dict] # Return as list of dicts for consistency
            else:
                # Unexpected result from solve
                return f"Solver returned an unexpected result type: {type(solution)}"

        except (SyntaxError, TypeError, NameError, AttributeError, ValueError, NotImplementedError) as e:
            return f"Error during solving process: {e}"
        except Exception as e:
            # Catch any other unexpected errors
            import traceback
            print("--- SOLVER UNEXPECTED ERROR ---")
            traceback.print_exc()
            print("-----------------------------")
            return f"An unexpected error occurred: {e}"

# Example Usage (can be removed or kept for direct testing)
if __name__ == '__main__':
    solver = SolverModule()

    print("--- Test Case 1: Unique Solution ---")
    eqs1 = ["x + y - 5", "x - y - 1"]
    unks1 = ["x", "y"]
    sol1 = solver.solve_algebraic_system(eqs1, unks1)
    print(f"Equations: {eqs1}, Unknowns: {unks1} -> Solution: {sol1}") # Expected: [{'x': 3.0, 'y': 2.0}]

    print("\n--- Test Case 2: No Solution ---")
    eqs2 = ["x + y - 1", "x + y - 2"]
    unks2 = ["x", "y"]
    sol2 = solver.solve_algebraic_system(eqs2, unks2)
    print(f"Equations: {eqs2}, Unknowns: {unks2} -> Solution: {sol2}") # Expected: "No solution found."

    print("\n--- Test Case 3: Infinite Solutions ---")
    eqs3 = ["x + y - 1"] # Underdetermined
    unks3 = ["x", "y"]
    sol3 = solver.solve_algebraic_system(eqs3, unks3)
    print(f"Equations: {eqs3}, Unknowns: {unks3} -> Solution: {sol3}") # Expected: [{'x': '1 - y', 'y': 'y'}] or similar infinite msg

    print("\n--- Test Case 4: Using Eq() ---")
    eqs4 = ["Eq(a, b * 2)", "Eq(b, 3)"]
    unks4 = ["a", "b"]
    sol4 = solver.solve_algebraic_system(eqs4, unks4)
    print(f"Equations: {eqs4}, Unknowns: {unks4} -> Solution: {sol4}") # Expected: [{'a': 6.0, 'b': 3.0}]

    print("\n--- Test Case 5: Parsing Error ---")
    eqs5 = ["x + = 3"]
    unks5 = ["x"]
    sol5 = solver.solve_algebraic_system(eqs5, unks5)
    print(f"Equations: {eqs5}, Unknowns: {unks5} -> Solution: {sol5}") # Expected: Error message

    print("\n--- Test Case 6: Single Variable ---")
    eqs6 = ["2*z - 10"]
    unks6 = ["z"]
    sol6 = solver.solve_algebraic_system(eqs6, unks6)
    print(f"Equations: {eqs6}, Unknowns: {unks6} -> Solution: {sol6}") # Expected: [{'z': 5.0}]