from __future__ import annotations

import sys
import time

# Code for AI Class Sudoku Programming Assignment
# Written by Chris Archibald
# archibald@cs.byu.edu
# Last Updated February 5, 2020

# ---------------------------------------------------------------------------
# Write-up experiment switches
#
# These control which heuristics the search uses.  They exist so the heuristic
# comparison required by the write-up can be run without editing the code
# between runs: an experiment script imports this module and reassigns these
# module-level names before calling backtracking_search().
#
#   USE_MRV    - order variables by minimum remaining values (Task 4)
#   USE_DEGREE - break MRV ties by maximum degree (Task 3, via max_degree)
#   USE_LCV    - order values by least constraining value (Task 5)
#
# All three default to True, which is the full-heuristic solver, so a normal
# run (and grading) is unaffected by these switches.
# ---------------------------------------------------------------------------
USE_MRV: bool = False
USE_DEGREE: bool = True
USE_LCV: bool = False


def student_name() -> str:
    """
    This function returns your name.  This will be used for automated grading
    """

    # Task 1 CODE HERE

    # Change to be your name
    return "Tyler Chartrand"


class Cell:
    """
    This class represents a variable corresponding to an
    individual cell in the Sudoku puzzle
    It's domain is the set of digits it could be (1-9)

    """

    def __init__(self) -> None:

        # The domain contains a list of the values that this variable could take on
        self.domain: list[int] = list(range(1, 10))

        # The value assigned to this variable if it has been assigned
        # None means that it hasn't been assigned
        self.value: int | None = None

    def assign_value(self, value: int) -> None:
        """
        Assign [value] to be this variable's value
        This function sets the domain to be only this value, and sets the value to be the value
        """
        self.domain = [value]
        self.value = value

    def set_domain(self, domain: list[int]) -> None:
        """
        Set the domain of this variable to be [domain]
        Set the value to unassigned (= None)
        """
        self.domain = domain[:]
        self.value = None

    def remove_value(self, value: int) -> bool:
        """
        Remove [value] from this variable's domain
        Return True if the domain for this variable is now empty
        Return False if there is still at least one variable in the domain
        """
        if value in self.domain:
            self.domain.remove(value)
        return len(self.domain) == 0

    def copy_cell(self, other: Cell) -> None:
        """
        Set the domain and value of this cell to that of the input other cell
        """
        self.domain = other.domain[:]
        self.value = other.value


class Sudoku:
    """
    This class contains all of the cells for an entire Sudoku puzzle
    """

    def __init__(self) -> None:
        """
        Initialize this puzzle by creating all of the cells (initially empty)
        """
        self.cells: list[list[Cell]] = [[Cell() for j in range(9)] for i in range(9)]

    def copy_puzzle(self, other: Sudoku) -> None:
        """
        Set all of this puzzle's cells to be the same as the other puzzle (input to function)
        """
        [[self.cells[j][i].copy_cell(other.cells[j][i]) for j in range(9)] for i in range(9)]

    def to_string(self) -> str:
        """
        Return a single string representation of the puzzle. For storage purposes
        """
        output_string = ""
        for r in range(9):
            for c in range(9):
                if self.cells[r][c].value:
                    output_string += str(self.cells[r][c].value)
                else:
                    output_string += "."
        return output_string

    def print_puzzle(self) -> None:
        """
        Display the puzzle to the output, in human readable form
        """
        for r in range(9):
            if (r % 3) == 0 and r > 0:
                print("")
            for c in range(9):
                if (c % 3) == 0 and c > 0:
                    print(" ", end="")
                if self.cells[r][c].value is None:
                    print(".", end="")
                else:
                    print(self.cells[r][c].value, end="")
            print("")

    def is_solved(self) -> bool:
        """
        Return true if every cell has been assigned a value
        This assumes that only valid assignments have been made
        """
        for r in range(9):
            for c in range(9):
                if self.cells[r][c].value is None:
                    return False
        return True

    def input_puzzle(self, puzzle_string: str) -> None:
        """
        Initialize this puzzle to match the starting state specified by [puzzle string]
        This is done by assigning all of the cells to be their given value (if specified)
        Then forward-checking is performed for every variable assingment that has been made
        """

        # Cycle through the puzzle and assign all the cells that are given in the input string
        r = 0
        c = 0
        for v in puzzle_string:
            if v != ".":
                self.cells[r][c].assign_value(int(v))
            c += 1
            if c > 8:
                c = 0
                r += 1

        # Cycle through the puzzle and perform forward checking for every variable that
        # was assigned a value
        for r in range(9):
            for c in range(9):
                # Bind the value to a local so it is narrowed to int below
                value = self.cells[r][c].value
                if value is not None:
                    success = self.forward_check(r, c, value)
                    if not success:
                        ### This puzzle has some serious problem.  Exit now.
                        print("Contradiction in Puzzle! Invalid input. Exiting")
                        print(" Puzzle string: ", puzzle_string)
                        sys.exit()

    # TASK 2 stub: add the missing return, then delete the ty: ignore on the next line.
    def forward_check(self, row: int, column: int, value: int, mode: str = "remove") -> bool | int:
        """
        Perform forward checking for the assignment of [value] to the cell at [row], [column]
        If [mode] == remove, then values should actually be removed other cell domains.
        Use the remove_value() function from the Cell class.
        Return False if any domain is empty as a result of forward checking, True otherwise.
        If [mode] == count, then values shouldn't be removed, but merely a count returned
        of how many values forward checking would remove
        """

        # TASK 2 Code here

        counter: int = 0

        # For row
        for c in range(len(self.cells[row])):
            if c == column:
                continue
            if mode == "remove" and self.cells[row][c].remove_value(value):
                return False
            if mode == "count" and value in self.cells[row][c].domain:
                counter += 1

        # For col
        for r in range(len(self.cells)):
            if r == row:
                continue
            if mode == "remove" and self.cells[r][column].remove_value(value):
                return False
            if mode == "count" and value in self.cells[r][column].domain:
                counter += 1

        # For grid
        row_start: int = (row // 3) * 3
        col_start: int = (column // 3) * 3

        for r in range(row_start, row_start + 3):
            for c in range(col_start, col_start + 3):
                # If already counted curr item, or if curr item is actually the evaluated item
                if r == row or c == column:
                    continue
                if mode == "remove" and self.cells[r][c].remove_value(value):
                    return False
                if mode == "count" and value in self.cells[r][c].domain:
                    counter += 1

        # Return the total count of all cells that had the value in their domain
        if mode == "count":
            return counter

        # If it got here on remove mode, then all of the cells still have at least one value in
        # their domain
        return True

    def get_row_column(self, grid: int, cell: int) -> tuple[int, int]:
        """
        Return the row and column indices for a given [grid] and [cell] location
        """
        base_r = 3 * int(grid / 3)
        base_c = 3 * (grid % 3)
        off_r = int(cell / 3)
        off_c = cell % 3
        return base_r + off_r, base_c + off_c

    def get_grid_cell(self, row: int, column: int) -> tuple[int, int]:
        """
        Return the grid and cell indices for a given [row] and [column] location
        """
        grid = 3 * int(row / 3) + int(column / 3)
        base_r = 3 * int(grid / 3)
        base_c = 3 * (grid % 3)
        off_r = row - base_r
        off_c = column - base_c
        cell = 3 * int(off_r) + int(off_c)
        return grid, cell


# Other functions (not in Sudoku class)
# When [puzzle] is an input
# it is an object of the Sudoku puzzle class [Sudoku]


def mrv(puzzle: Sudoku, unassigned: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Return a list of the (row, column) tuples, out of the list of [unassigned] cells given
    that have the minimum remaining values
    [unassigned] is a list of (row, column) tuples corresponding to cell locations
    """

    # TASK 4 Code here

    sorted_dict: dict[tuple[int, int], int] = {}
    min_remaining_values_count = 1000

    for coord in unassigned:
        curr_num = len(puzzle.cells[coord[0]][coord[1]].domain)
        sorted_dict[coord] = curr_num

        if curr_num < min_remaining_values_count:
            min_remaining_values_count = curr_num

    out_list = []
    for coord, num in sorted_dict.items():
        if num == min_remaining_values_count:
            out_list.append(coord)

    return out_list


def max_degree(puzzle: Sudoku, tied: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Return a list of the (row, column) tuples, out of the list of [tied] cells
    (according to mrv) given that have the maximum degree, i.e. are connected to the most
    unassigned other variables
    This uses the count_constraints function
    """
    max_c = 0
    mc_variables: list[tuple[int, int]] = []
    for t in tied:
        cur_c = count_constraints(puzzle, t[0], t[1])
        if cur_c == max_c:
            mc_variables.append(t)
        if cur_c > max_c:
            max_c = cur_c
            mc_variables = [t]

    return mc_variables


# TASK 3 stub: add the return statement, then delete the ty: ignore on the next line.
def count_constraints(puzzle: Sudoku, row: int, column: int) -> int:
    """
    Count the number of unassigned variables that are in the same row, column and grid as
    the input location [row], [column]
    return this number
    This is called by the max_degree function
    """

    # TASK 3 CODE HERE

    counter: int = 0

    # For row
    for c in range(len(puzzle.cells[row])):
        if puzzle.cells[row][c].value is None:
            counter += 1

    # For col
    for r in range(len(puzzle.cells)):
        if puzzle.cells[r][column].value is None:
            counter += 1

    # For grid
    row_start: int = (row // 3) * 3
    col_start: int = (column // 3) * 3

    for r in range(row_start, row_start + 3):
        for c in range(col_start, col_start + 3):
            if puzzle.cells[r][c].value is None:
                counter += 1

    return counter

    # MODIFY THIS
    # return 0


def get_unassigned_variables(puzzle: Sudoku) -> list[tuple[int, int]]:
    """
    Return a list of the variables in the puzzle that haven't been assigned a value
    yet. These will be (row, column) tuples
    """
    unassigned: list[tuple[int, int]] = []
    for r in range(9):
        for c in range(9):
            # Unassigned cells have a value of None
            if puzzle.cells[r][c].value is None:
                unassigned.append((r, c))
    return unassigned


def select_variable(puzzle: Sudoku) -> tuple[int, int]:
    """
    This function will return the row and column location of the variable that should be
    selected next from [puzzle].
    It will do this using the minimum-remaining-values heuristic, with ties broken by the
    degree heuristic, and any remaining ties broken arbitrarily
    """

    # 0. Get the initial list of all unassigned variables
    unassigned = get_unassigned_variables(puzzle)

    # 1. Use MRV heuristic to get list of variables with the min remaining values
    #    Without MRV (USE_MRV == False) no variable is preferred, so every unassigned
    #    variable stays a candidate and selection falls back to scan order (row-major)
    candidates: list[tuple[int, int]] = mrv(puzzle, unassigned) if USE_MRV else unassigned

    # If MRV identifies a unique variable, then return it
    if len(candidates) == 1:
        return candidates[0][0], candidates[0][1]

    # 2. Refine list to those with maximum degree
    #    Without the degree heuristic (USE_DEGREE == False) ties stay unbroken, so the
    #    remaining tie is resolved arbitrarily by taking the first candidate below
    if USE_DEGREE:
        candidates = max_degree(puzzle, candidates)

    # 3. Return first variable in the list.  This will be the only one if there was a
    #    unique most constraining variable, or the "alphabetically first" or "arbitrary" one of
    #    them if there were ties
    return candidates[0][0], candidates[0][1]


def order_values(puzzle: Sudoku, row: int, column: int) -> list[int]:
    """
    For the variable at the given row and column, return the values of this variables domain,
    ordered by the least-constraining value heuristic.  You can use the forward_check() function
    in the 'count' mode to count the number of values that would be removed from other variables'
    domains by a particular variable=value assignment
    """

    # Get the current domain for this variable
    domain: list[int] = puzzle.cells[row][column].domain[:]

    # Without the least-constraining-value heuristic (USE_LCV == False) the domain is used
    # in its natural order instead of being ordered by how many values each choice removes
    if not USE_LCV:
        return domain

    val_dict: dict[int, int] = {}
    out_list: list[int] = []

    # TASK 5 CODE HERE

    for value in domain:
        val_dict[value] = puzzle.forward_check(row, column, value, mode="count")

    sorted_list: list[tuple[int, int]] = sorted(val_dict.items(), key=lambda item: item[1])

    for val, _ in sorted_list:
        out_list.append(val)

    # Change this to return an ordered list
    return out_list


def backtracking_search(puzzle: Sudoku) -> Sudoku | None:
    """
    Perform a recursive backtracking search on [puzzle],
    ensuring that a copy is made of the puzzle
    before modifying it and recursing.

    If unsuccessful, a None value is returned
    If successful, this function returns the solved puzzle object
    """

    # PSEUDO-CODE to help with structuring this function

    # TASK 6 CODE HERE

    # 1. Base case, is input [puzzle] solved? If so, return the puzzle. Use is_solved() function
    #    to see if the puzzle is solved.

    if puzzle.is_solved():
        return puzzle

    # 2. Select a variable to assign next ( use select_variable() function, which returns
    #    row and column of the variable

    coord: tuple[int, int] = select_variable(puzzle)

    # 3. Select an ordering over the values (use order_values(r,c) where r, c are the row
    #    and column of the selected variable.  It returns a list of values

    # Uses least constraining value huristic (controlled by the USE_LCV switch; with it
    # turned off, order_values() simply returns the domain in its natural order)
    next_values: list[int] = order_values(puzzle, coord[0], coord[1])

    # 4. For each value in the ordered list:

    for curr_value in next_values:
        # 4.1 Get a copy of the puzzle to modify
        #     4.1.a Create new puzzle

        curr_puzzle: Sudoku = Sudoku()

        #     4.1.b Set it to be equal to the current puzzle (use copy_puzzle())

        curr_puzzle.copy_puzzle(puzzle)

        # 4.2 Assign current value to selected variable (use assign_value())

        curr_puzzle.cells[coord[0]][coord[1]].assign_value(curr_value)

        # 4.3 Forward check from this assignment (use forward_check(), in 'remove' mode)
        #     which will return False if this assignment is invalid (empty domain was found)
        #     or True if it is valid.

        if curr_puzzle.forward_check(coord[0], coord[1], curr_value, mode="remove"):
            # 4.4 If forward checking detects a problem, then continue to the next value

            # 4.5 If forward checking doesn't detect problem, then recurse on the
            #     modified puzzle (call backtracking_search())

            returned_puzzle: Sudoku | None = backtracking_search(curr_puzzle)

            # 4.6 If the search succeeds (return value of backtracking is not None)
            #     return solved puzzle! (this is what backtracking_search should return)

            if returned_puzzle is not None:
                return returned_puzzle

        # 4.7 If search is a failure, continue with next value for this variable

    # 5. If all values for the chosen variable failed, return failure (None)
    return None


def print_search_statistics(search_times: list[float], num_failed: int = 0) -> None:
    """
    Print the timing summary used by the write-up: how many puzzles were solved, how long
    the search itself took, and the average/min/max per-puzzle search time.
    Only backtracking_search() time is counted, so parsing and printing the puzzles do not
    inflate the numbers.
    """
    num_solved = len(search_times)

    print("\n**************")
    print(f" Solved {num_solved} puzzles (search time only, parsing/printing excluded)")

    if num_solved == 0:
        print(" No puzzles finished -- no timings to report")
        return

    total_time = sum(search_times)
    print(f" Total search time  = {total_time:.3f} seconds")
    print(f" Average solve time = {total_time / num_solved:.3f} seconds")
    print(f" Fastest puzzle     = {min(search_times):.3f} seconds")
    print(f" Slowest puzzle     = {max(search_times):.3f} seconds")
    if num_failed:
        print(f" Plus {num_failed} puzzle(s) that could not be solved")


if __name__ == "__main__":
    # The puzzle file is required; the switches are optional, so the write-up configurations
    # can be run without editing the file, e.g.
    #   python sudoku.py puzzles.txt --no-mrv --no-degree --no-lcv
    puzzle_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    switch_args = {a for a in sys.argv[1:] if a.startswith("--")}

    if len(puzzle_args) != 1 or switch_args - {"--no-mrv", "--no-degree", "--no-lcv"}:
        print("USAGE: python pa2.py PUZZLE_FILE.txt [--no-mrv] [--no-degree] [--no-lcv]")
    else:
        if "--no-mrv" in switch_args:
            USE_MRV = False
        if "--no-degree" in switch_args:
            USE_DEGREE = False
        if "--no-lcv" in switch_args:
            USE_LCV = False

        # Show the active configuration so a pasted transcript is self-documenting
        print(
            f"Searching for solutions to puzzles from file: {puzzle_args[0]}"
            f"  [mrv={USE_MRV} degree={USE_DEGREE} lcv={USE_LCV}]"
        )

        # How many puzzles do we want to solve
        max_to_solve = 10

        # Variable to keep track of the number of puzzles solved
        num_solved = 0

        # Number of puzzles the search failed on (only ever 0 or 1, since we stop there)
        num_failed = 0

        # Time spent inside backtracking_search() for each puzzle that finished
        search_times: list[float] = []

        try:
            # Open puzzle file
            with open(puzzle_args[0]) as pf:
                # Each puzzle takes up a single line in the file
                for ps in pf.readlines():
                    # Report the running totals before starting, so the numbers are already on
                    # screen if this puzzle turns out to take too long
                    if search_times:
                        totals = sum(search_times)
                        print(
                            f"\n--- {num_solved} puzzle(s) done: total {totals:.3f}s,"
                            f" average {totals / num_solved:.3f}s ---",
                            flush=True,
                        )

                    print("\nSearching to find solution to following puzzle:", ps)

                    # Create a new puzzle to solve
                    p = Sudoku()

                    # Initialize the puzzle to match the file
                    p.input_puzzle(ps.rstrip())

                    # Display the puzzle (before it has been solved)
                    p.print_puzzle()

                    # Time only the search itself, so printing and parsing do not inflate it
                    puzzle_start = time.perf_counter()
                    success_p = backtracking_search(p)
                    search_time = time.perf_counter() - puzzle_start

                    # If the puzzle was solved (success_p is the puzzle, None if no solution)
                    if success_p:
                        search_times.append(search_time)
                        num_solved += 1

                        print("\n Successfully solved puzzle!  Here is solution:\n")

                        # Display the solution to the puzzle
                        success_p.print_puzzle()

                        # Progress report, so partial results survive an early stop
                        print(
                            f"\n[{num_solved} solved] this puzzle: {search_time:.3f}s |"
                            f" total: {sum(search_times):.3f}s |"
                            f" average: {sum(search_times) / num_solved:.3f}s",
                            flush=True,
                        )

                    else:
                        num_failed += 1
                        print("\n!! Unable to solve puzzle !!\n")
                        break

                    # Stop when we solve enough
                    if num_solved > max_to_solve:
                        break
        except KeyboardInterrupt:
            # Ctrl-C during a long solve: keep everything already measured
            print(
                "\n\n Interrupted by user -- reporting the puzzles that finished",
                flush=True,
            )

        # Print Statistics
        print_search_statistics(search_times, num_failed)
