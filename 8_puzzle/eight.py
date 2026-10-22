import argparse
import sys
import time
from queue import PriorityQueue

# Code for AI Class Programming Assignment 1
# Written by Chris Archibald
# archibald@cs.byu.edu
# Last Updated January 24, 2020

# GOAL: (0 is the blank tile)
# 0 1 2
# 3 4 5
# 6 7 8

INFINITY: float = float("inf")


class Puzzle:
    """
    This is the 8-puzzle class.  You shouldn't have to modify it at all.
    """

    def __init__(self, arrangement: list[int]) -> None:
        """
        The state (and arrangement passed in) is a list of length 9, that stores
        which tile is in each place.
        In a solved puzzle, each place number holds the tile of the same number
        i.e. solution is state = [0,1,2,3,4,5,6,7,8]
        """
        self.state = arrangement[:]
        # The blank starts at 0 and is overwritten below once the 0 tile is found.
        # (Annotated int rather than None so static type checkers can see that
        # every later `self.blank` operation is on an int.)
        self.blank: int = 0

        for i in range(len(self.state)):
            if self.state[i] == 0:
                self.blank = i

    def print_puzzle(self) -> None:
        """
        Print a visual description of the puzzle to the output
        """
        k = 0
        for _ in range(3):
            for _ in range(3):
                print("", end="")
                print(self.state[k], end="")
                k = k + 1
            print("")

    def get_moves(self) -> list[str]:
        """
        The moves correspond to the motion of the tile into the blank space
        it can be U (up), D (down), R (right), or L (left)
        """
        invalid_moves = []
        if self.blank < 3:
            invalid_moves.append("D")
        if self.blank > 5:
            invalid_moves.append("U")
        if self.blank % 3 == 0:
            invalid_moves.append("R")
        if self.blank % 3 == 2:
            invalid_moves.append("L")

        base_moves = ["U", "D", "L", "R"]
        valid_moves = []
        for m in base_moves:
            if m not in invalid_moves:
                valid_moves.append(m)

        return valid_moves

    def do_move(self, move: str) -> None:
        """
        Modify the state by performing the given move.
        This assumes that the move is valid
        """
        swapi = 0
        if move == "U":
            swapi = self.blank + 3
        if move == "D":
            swapi = self.blank - 3
        if move == "L":
            swapi = self.blank + 1
        if move == "R":
            swapi = self.blank - 1

        temp = self.state[swapi]
        self.state[swapi] = self.state[self.blank]
        self.state[self.blank] = temp
        self.blank = swapi

    def undo_move(self, move: str) -> None:
        """
        This modifies the state by undoing the move.  For use in recursive search
        Assumes the move was a valid one
        """
        swapi = 0
        if move == "D":
            swapi = self.blank + 3
        if move == "U":
            swapi = self.blank - 3
        if move == "R":
            swapi = self.blank + 1
        if move == "L":
            swapi = self.blank - 1

        temp = self.state[swapi]
        self.state[swapi] = self.state[self.blank]
        self.state[self.blank] = temp
        self.blank = swapi

    def is_solved(self) -> bool:
        """
        Returns True if the puzzle is solved, False otherwise
        """
        ######## TASK 1.1 BEGIN ##########

        # Add code to determine whether this puzzle is solved

        return self.state == [0, 1, 2, 3, 4, 5, 6, 7, 8]

        ######## TASK 1.1 END   ##########

    def __repr__(self) -> str:
        return "".join([str(i) for i in self.state])

    def id(self) -> str:
        """
        Returns the string representation of this puzzle's state.
        Useful for storing state in a dictionary
        """
        return self.__repr__()


class SearchNode:
    """
    Our search node class
    """

    def __init__(self, cost: int, puzzle: Puzzle, path: str, options: argparse.Namespace) -> None:
        """
        Initialize all the relevant parts of the search node
        """
        self.cost = cost
        self.puzzle = puzzle
        self.path = path
        self.options = options
        self.h = heuristic(self, self.options)
        self.compute_f_value()

    def compute_f_value(self) -> None:
        """
        Compute the f-value for this node
        """
        ######## TASK 1.3 BEGIN ##########

        # Modify these lines to implement the search algorithms (greedy, Uniform-cost or A*)
        self.f_value = 0

        if self.options.type == "g":
            # greedy search algorithm
            self.f_value = self.h  # Change this to implement greedy!

        elif self.options.type == "u":
            # uniform cost search algorithm
            self.f_value = self.cost  # Change this to implement uniform cost search!

        elif self.options.type == "a":
            # A* search algorithm
            self.f_value = self.cost + self.h  # Change this to implement A*!

        else:
            print("Invalid search type (-t) selected: Valid options are g, u, and a")
            sys.exit()

        ######## TASK 1.3 END   ##########

    # Comparison operator. Don't modify this or best-first search might stop working
    def __lt__(self, other: "SearchNode") -> bool:
        """
        Comparison operator so that nodes will be sorted in priority queue based on f-value
        """
        return self.f_value < other.f_value


def heuristic(node: SearchNode, options: argparse.Namespace) -> int:
    """
    This is the function that is called from the SearchNode
    class to get the heuristic value for a node
    """
    if options.function == "top":
        return tiles_out_of_place(node.puzzle)
    elif options.function == "torc":
        return tiles_out_of_row_column(node.puzzle)
    elif options.function == "md":
        return manhattan_distance_to_goal(node.puzzle)
    else:
        print("Invalid heristic selected. Options are top, torc, and md")
        sys.exit()


def tiles_out_of_place(puzzle: Puzzle) -> int:
    """
    This heuristic counts the number of tiles out of place.
    """
    # Keep track of the number of tiles out of place
    num_out_of_place = 0

    # Cycle through all of the places in the puzzle and see if the right tile is there
    # (We ignore place 0 since that is where the blank tile goes and we shouldn't count it)
    for i in range(1, len(puzzle.state)):
        # The tile in place i ( puzzle.state[i] ) should be tile i.
        # If it isn't increment out of place counter
        # (To compare tile (string) with place (int), we must first convert from
        # string to int as such:
        #  int(puzzle.state[i])

        if puzzle.state[i] != i:
            num_out_of_place += 1

    return num_out_of_place


def tiles_out_of_row_column(puzzle: Puzzle) -> int:
    """
    This heuristic counts the number of tiles that are in the wrong row,
    the number of tiles that are in the wrong column
    and returns the sum of these two numbers.
    Remember not to count the blank tile as being out of place, or the heuristic is inadmissible
    """
    ######## TASK 1.4.1 BEGIN   ##########

    # YOUR TASK 1.4.1 CODE HERE

    wrong_pos_count = 0

    for tile in range(1, len(puzzle.state)):
        pos = puzzle.state.index(tile)

        if get_tile_row(pos) != get_tile_row(tile):
            wrong_pos_count += 1

        if get_tile_column(pos) != get_tile_column(tile):
            wrong_pos_count += 1

    return wrong_pos_count

    ######## TASK 1.4.1 END   ##########


def manhattan_distance_to_goal(puzzle: Puzzle) -> int:
    """
    This heuristic should calculate the sum of all the manhattan distances for each tile to get to
    its goal position.  Again, make sure not to include the distance from the blank to its goal.
    """

    ######## TASK 1.4.2 BEGIN   #########

    # YOUR TASK 1.4.2 CODE HERE

    total_dist = 0

    for tile in range(1, len(puzzle.state)):
        pos = puzzle.state.index(tile)

        total_dist += abs(get_tile_row(tile) - get_tile_row(pos))
        total_dist += abs(get_tile_column(tile) - get_tile_column(pos))

    return total_dist

    ######## TASK 1.4.2 END   ##########


def get_tile_row(tile: int) -> int:
    """
    Return the row of the given tile location (Helper function for you to use)
    """
    return int(tile / 3)


def get_tile_column(tile: int) -> int:
    """
    Return the column of the given tile location (Helper function for you to use)
    """
    return tile % 3


def run_iterative_search(start_node: SearchNode) -> tuple[int, int] | tuple[None, None]:
    """
    This runs an iterative deepening search
    It caps the depth of the search at 40 (no 8-puzzles have solutions this long)
    """
    # Our initial depth limit
    depth_limit = 1

    # Maximum depth limit
    max_depth_limit = 40

    # Keep track of the total number of nodes we expand
    total_expanded = 0

    # Keep trying until our depth limit hits 40
    while depth_limit < max_depth_limit:
        # Store visited nodes along the current search path
        visited = dict()
        visited["N"] = 0

        # Mark the initial state as visited
        visited[start_node.puzzle.id()] = True

        # Run depth-limited search starting at initial node (which points to initial state)
        path_length = run_dfs(start_node, depth_limit, visited)

        # See how many nodes we expanded on this iteration and add it to our total
        total_expanded += visited["N"]

        # Check to see if a solution was found
        if path_length is not None:
            # It was! Print out information and return the search stats
            print("Expanded ", total_expanded, "nodes")
            print("IDS Found solution at depth", depth_limit)
            return total_expanded, path_length

        # No solution was found at this depth limit, so increment our depth-limit
        depth_limit += 1

    # No solution was found at any depth-limit, so
    # return None,None (Which signifies no solution found)
    return None, None


def run_dfs(node: SearchNode, depth_limit: int, visited: dict[str, int]) -> int | None:
    """
    Recursive Depth-Limited Search:

    Check node to see if it is goal, if it is, print solution and return path length
    If not and if depth-limit hasn't been reached, recurse on all children
    """
    visited["N"] = visited["N"] + 1  # Increment our node expansion counter

    # Check to see if this is a goal node
    if node.puzzle.is_solved():
        # It is! Print out solution and return solution length
        print("Iterative Deepening SOLVED THE PUZZLE! SOLUTION = ", node.path)
        return len(node.path)

    # Check to see if the depth limit has been reached (number of actions that have been taken)
    if len(node.path) >= depth_limit:
        # It has. Return None, signifying that no path was found
        return None

    # Generate successors and recurse on them

    # Get the list of moves we can try from this node's state
    moves = node.puzzle.get_moves()

    # For each possible move
    for m in moves:
        # Execute the move/action
        node.puzzle.do_move(m)
        node.compute_f_value()

        # Add this move to the node's path
        node.path = node.path + m
        # Add 1 to node's cost
        node.cost = node.cost + 1
        # Check to see if we have already visited this node
        if node.puzzle.id() not in visited:
            # We haven't. Now we will, so add it to visited
            visited[node.puzzle.id()] = True

            # Recurse on this new state
            path_length = run_dfs(node, depth_limit, visited)

            # Check to see if a solution was found down this path (return value of None means no)
            if path_length is not None:
                # It was! Return this solution path length to whoever called us
                return path_length

            # Remove this state from the visited list.
            # We only check for duplicates along current search path
            del visited[node.puzzle.id()]

        # That move didn't lead to a solution, so lets try the next one
        # First, though, we need to undo the move (to return puzzle
        # to state before we tried that move)
        node.puzzle.undo_move(m)
        # Remove that last move we tried from the path
        node.path = node.path[0:-1]
        # Remove 1 from node's cost
        node.cost = node.cost - 1

    # Couldn't find a solution here or at any of my successors, so return None
    # This node is not on a solution path under the depth-limit
    return None


def run_ida_search(start_node: SearchNode) -> tuple[int, int] | tuple[None, None]:
    """
    This runs an iterative deepening A* (IDA*) search -- Part 2 of the assignment.

    IDA* is the same depth-first skeleton as run_iterative_search/run_dfs, except that
    the cutoff is no longer the path length.  Each iteration searches depth-first and
    prunes every node whose f-value exceeds the current cost bound; if the iteration
    fails it raises the bound to the smallest f-value that overshot it and tries again.

    IDA* always evaluates nodes as f = g + h = cost + heuristic, so it always uses the A*
    evaluation function: -t defaults to a when -s ida is used, and any other explicit -t is
    rejected in __main__ instead of being silently ignored.

    Returns (nodes_expanded, path_length) on success or (None, None) on failure, so the
    stats-collection code in __main__ works unchanged.
    """
    ######## PART 2 (IDA*) BEGIN ##########

    # YOUR IDA* OUTER LOOP HERE
    #
    # Suggested shape (mirror run_iterative_search):
    #   - start the bound at the start node's f-value under A* (g + h), i.e. h(start)
    #   - each iteration: reset the per-path visited structure and expansion counter,
    #     call run_ida_dfs(start_node, bound, visited), then add visited["N"] to a
    #     running total_expanded
    #   - if the DFS reported a solution, print the stats and return
    #     (total_expanded, path_length)
    #   - otherwise set bound = visited["next"] and iterate again

    # Our initial bound
    bound: int = start_node.h

    # Keep track of the total number of nodes we expand
    total_expanded = 0

    # Keep trying until our bound limit for the F value becomes infinity, because that indicates
    # that the function has ran out of routes to check, and so the answer must not exist
    while bound < INFINITY:
        # Store visited nodes along the current search path
        visited: dict[str, int | float | bool] = dict()
        visited["N"] = 0

        # The highest possible number, every failed solution will be better than this, so it
        # will get overwritten when needed by the run_ida_dfs
        visited["next"] = INFINITY

        # Mark the initial state as visited
        visited[start_node.puzzle.id()] = True

        # Run depth-limited search starting at initial node (which points to initial state)
        path_length: int | None = run_ida_dfs(start_node, bound, visited)

        # See how many nodes we expanded on this iteration and add it to our total
        total_expanded += visited["N"]

        # Check to see if a solution was found
        if path_length is not None:
            # It was! Print out information and return the search stats
            print("Expanded ", total_expanded, "nodes")
            print("IDA* Found solution at f bound", bound)
            return total_expanded, path_length

        # No solution was found at this bound limit, so we expand the bound
        # to be the lowest f value we have found so far
        bound: int | float = visited["next"]

    # No solution was found at any depth-limit, so
    # return None,None (Which signifies no solution found)
    return None, None

    ######## PART 2 (IDA*) END   ##########


def run_ida_dfs(
    node: SearchNode, bound: int | float, visited: dict[str, int | float | bool]
) -> int | None:
    """
    Recursive depth-first search for IDA*:

    Check node to see if it is goal, if it is, print solution and return path length.
    If not, prune the node when its f-value exceeds the current cost bound, recording
    that f-value as the next bound to try.  Otherwise recurse on all of its children.

    `visited` is the same mutable-dict trick used by run_dfs (state id -> True marks the
    current search path, "N" counts node expansions).  It also carries the next bound to
    try under the "next" key, which is how that value gets back to run_ida_search
    without fighting `nonlocal`.

    Returns the solution path length if a solution was found, or None if this bound was
    exhausted without finding one.
    """
    ######## PART 2 (IDA*) BEGIN ##########

    # YOUR IDA* RECURSIVE DFS HERE
    #
    # Suggested shape (mirror run_dfs):
    #   - visited["N"] += 1
    #   - return len(node.path) if node.puzzle.is_solved()
    #   - prune (and record the overshoot in visited["next"]) when
    #     node.f_value > bound
    #   - for each move: do_move, recompute the f-value, extend path/cost, skip states
    #     already on the search path, recurse, then undo_move / restore path / restore
    #     cost on backtrack (and drop the state from visited)

    visited["N"] += 1  # Increment our node expansion counter

    # Check to see if this is a goal node
    if node.puzzle.is_solved():
        # It is! Print out solution and return solution length
        print("Iterative Deepening A* SOLVED THE PUZZLE! SOLUTION = ", node.path)
        return len(node.path)

    # # Check to see if the bound has been reached (f value is too high)
    # if len(node.path) >= bound:
    #     # It has. Return None, signifying that no path was found
    #     return None

    # If the current node's f value is lower than the current next value, then it will get
    # overwritten. This leads to the "next" value being the lowest from this search operation
    if node.f_value > bound:
        visited["next"] = min(visited["next"], node.f_value)
        return None

    # Generate successors and recurse on them

    # Get the list of moves we can try from this node's state
    moves = node.puzzle.get_moves()

    # moves.sort(by a* algorithm?)

    # For each possible move
    for m in moves:
        # Execute the move/action
        node.puzzle.do_move(m)
        node.compute_f_value()

        # Add this move to the node's path
        node.path = node.path + m
        # Add 1 to node's cost
        node.cost = node.cost + 1
        # Check to see if we have already visited this node
        if node.puzzle.id() not in visited:
            # We haven't. Now we will, so add it to visited
            visited[node.puzzle.id()] = True

            # Recurse on this new state
            path_length = run_ida_dfs(node, bound, visited)

            # Check to see if a solution was found down this path (return value of None means no)
            if path_length is not None:
                # It was! Return this solution path length to whoever called us
                return path_length

            # Remove this state from the visited list.
            # We only check for duplicates along current search path
            del visited[node.puzzle.id()]

        # That move didn't lead to a solution, so lets try the next one
        # First, though, we need to undo the move (to return puzzle
        # to state before we tried that move)
        node.puzzle.undo_move(m)

        # Remove that last move we tried from the path
        node.path = node.path[0:-1]

        # Remove 1 from node's cost
        node.cost = node.cost - 1

    # Couldn't find a solution here or at any of my successors, so return None
    # This node is not on a solution path under the depth-limit
    return None

    ######## PART 2 (IDA*) END   ##########


def run_best_first_search(
    fringe: PriorityQueue[SearchNode], options: argparse.Namespace
) -> tuple[int, int] | tuple[None, None]:
    """
    Runs an arbitrary best-first search.  To change which search is run, modify the f-value
    computation in the search nodes

    fringe is a priority queue of search nodes, ordered by f-values
    """
    # Create our data structure to track visited/expanded states
    visited = dict()

    # Variable to tell when we are done
    done = False

    # Main search loop.  Keep going as long as we are not done and the FRINGE isn't empty
    while not done and not fringe.empty():
        # Get the next SearchNode from the FRINGE
        cur_node = fringe.get()

        # Add it to our set of visited/expanded states (join creates a string from the state)
        visited[cur_node.puzzle.id()] = True

        # Don't continue if the cost is too much
        if cur_node.cost > 200:
            # None of the puzzles are this long, so we shouldn't continue further on this path
            continue

        # Check to see if this node's puzzle state is a goal state
        if cur_node.puzzle.is_solved():
            # It is! We are done, print out details
            done = True
            print("Best-First SOLVED THE PUZZLE: SOLUTION = ", cur_node.path)
            print("Expanded ", len(visited), "states")
            return len(visited), len(cur_node.path)

        else:
            # Generate this SearchNode's successors and add them to the FRINGE

            # Get the possible moves (actions) for this state
            moves = cur_node.puzzle.get_moves()

            # For each move, do the move, create SearchNode from successor, then add to FRINGE
            for m in moves:
                # Create new puzzle that new node will point to
                np = Puzzle(cur_node.puzzle.state)

                # Execute the move/action
                np.do_move(m)

                # Add to the FRINGE, as long as we haven't visited that puzzle
                if np.id() not in visited:
                    # Create the new SearchNode
                    new_node = SearchNode(cur_node.cost + 1, np, cur_node.path + m, options)

                    # Add it to the FRINGE, along with its f-value (stored inside the node)
                    fringe.put(new_node)

    # We didn't find a solution (the loop only exits without a return when done is False)
    print("NO SOLUTION FOUND!")
    return None, None


def getOptions(args: list[str] = sys.argv[1:]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="8-Puzzle Solver.")
    parser.add_argument("file", metavar="FILENAME", type=str, help="File of puzzles to solve")
    parser.add_argument(
        "-s",
        "--search",
        help=(
            "Search type: Options: ids (iterative deepening search), "
            "ida (iterative deepening A*), or bfs (best first search)"
        ),
        default="ids",
    )
    parser.add_argument(
        "-f",
        "--function",
        help=(
            "Heuristic function used: Options: top (tiles out of place), torc "
            "(tiles out of row/column), or md (manhattan distance)"
        ),
        default="top",
    )
    parser.add_argument(
        "-t",
        "--type",
        help=(
            "Evaluation function type: Options: g (greedy), u (uniform cost), or a (a-star). "
            "Defaults to u, or to a when -s ida is used (IDA* requires a-star)"
        ),
        default=None,
    )
    options = parser.parse_args(args)

    # IDA* is only valid with the A* evaluation function, so -t defaults to a for it.
    # (None here means the user didn't pass -t at all, so nothing was requested to reject.)
    if options.type is None:
        options.type = "a" if options.search == "ida" else "u"

    return options


if __name__ == "__main__":
    # Get command line options
    options = getOptions()
    print(options)
    print("Searching for solutions to puzzles from file: ", sys.argv[1])

    # Open puzzle file
    with open(options.file) as pf:
        puzzle_lines = pf.readlines()

    # You can modify the maximum number of puzzles to solve if you want to test on more puzzles
    max_to_solve = 40
    # max_to_solve = 1

    # Variables to keep track of solving statistics
    num_solved = 0
    exp_num = 0
    tot_time = 0.0
    path_length = 0

    for ps in puzzle_lines:
        print("Searching to find solution to following puzzle:", ps)

        # Create puzzle from file line
        a = [int(i) for i in ps.rstrip()]
        p = Puzzle(a)

        # Print the puzzle to the screen
        p.print_puzzle()

        # Create the initial search node corresponding to the given puzzle state
        start_node = SearchNode(0, p, "", options)

        # Create the priority Queue to store the SearchNodes in
        pq = PriorityQueue()

        # Insert the initial state into the Queue
        pq.put(start_node)

        # Get initial timing info
        start = time.time()

        # Run the given search search (each returns number of nodes
        # expanded and the length of the path found)
        if options.search == "bfs":
            # Run the best-first searches
            exp, pl = run_best_first_search(pq, options)
        elif options.search == "ids":
            # Use this line to run the iterative deepening-search
            exp, pl = run_iterative_search(start_node)
        elif options.search == "ida":
            # Use this line to run the iterative deepening A* search (Part 2)
            # IDA* always evaluates nodes with f = g + h, so any other -t would just be
            # silently ignored (and produce results you didn't ask for).  Refuse the
            # combination instead.  -t defaults to a for -s ida, so only an explicit
            # -t g / -t u can trip this check.
            if options.type != "a":
                print(
                    "Invalid search options: IDA* (-s ida) always uses the A* evaluation "
                    f"function (f = g + h), so -t {options.type} cannot be used with it. "
                    "Use -t a or omit -t."
                )
                sys.exit()

            exp, pl = run_ida_search(start_node)
        else:
            print("Search option not valid. Can be bfs, ids, or ida")
            sys.exit()

        if exp is None or pl is None:
            print("PUZZLE NOT SOLVED")
            break

        # Keep track of statistics so we can compare search methods
        exp_num += exp
        path_length += pl
        print("Solution path length is : ", pl)

        # Calculate Timing info
        end = time.time()
        tot_time += end - start
        num_solved += 1

        # Stop after we have solved the specified number of puzzles
        if num_solved >= max_to_solve:
            break

    print("Done with solving puzzles.\n\n")

    # Print out statistics about this batch
    if num_solved > 0:
        print("Solved", num_solved, "puzzles from file: ", sys.argv[1])
        print(f"Total time taken: {tot_time:.2f} seconds")
        print("Average nodes expanded: ", float(exp_num) / float(num_solved))
        print(f"Average search time: {(tot_time / num_solved):,.4f} seconds")
        print("Average solution length: ", path_length / num_solved)
    else:
        print(
            "A puzzle was not solved.  This means you haven't correctly ",
            "implemented something. Please double check your code and try again.",
        )
