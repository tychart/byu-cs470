# Modified 10.3.2023 by Chris Archibald to
#  - incorporate MCTS with other code
#  - pass command line param string to each AI

from __future__ import annotations

import re
from typing import Any

import numpy as np
import numpy.typing as npt

# Every board in this assignment is a 6x7 array of uint8 values
# (0 = empty, 1 = player one, 2 = player two).
Board = npt.NDArray[np.uint8]

MAX_VAL: int = 10_000


class AIPlayer:
    player_number: int
    name: str
    type: str
    player_string: str
    other_player_number: int
    depth_limit: int
    max_iterations: int

    def __init__(self, player_number: int, name: str, ptype: str, param: str | None) -> None:
        self.player_number = player_number
        self.name = name
        self.type = ptype
        self.player_string = f"Player {player_number}: " + self.name
        self.other_player_number = 1 if player_number == 2 else 2

        # Parameters for the different agents

        self.depth_limit = 3  # default depth-limit - change if you desire
        # Alpha-beta
        # Example of using command line param to overwrite depth limit
        if self.type == "ab" and param:
            self.depth_limit = int(param)

        # Expectimax
        # Example of using command line param to overwrite depth limit
        if self.type == "expmax" and param:
            self.depth_limit = int(param)

        # MCTS
        self.max_iterations = 1000  # Default max-iterations for MCTS - change if you desire
        # Example of using command line param to overwrite max-iterations for MCTS
        if self.type == "mcts" and param:
            self.max_iterations = int(param)

    def get_alpha_beta_move(self, board: Board) -> int:
        """
        Given the current state of the board, return the next move based on
        the alpha-beta pruning algorithm

        This will play against either itself or a human player

        INPUTS:
        board - a numpy array containing the state of the board using the
                following encoding:
                - the board maintains its same two dimensions
                    - row 0 is the top of the board and so is
                      the last row filled
                - spaces that are unoccupied are marked as 0
                - spaces that are occupied by player 1 have a 1 in them
                - spaces that are occupied by player 2 have a 2 in them

        RETURNS:
        The 0 based index of the column that represents the next move
        """
        moves: list[int] = get_valid_moves(board)
        best_move: int = np.random.choice(moves)

        # YOUR ALPHA-BETA CODE GOES HERE

        for move in moves:
            curr_board: Board = board.copy()
            make_move(curr_board, move, self.player_number)
            score: int = self.evaluation_function(board=board)

        return best_move

    def recursive_search_max(self, board: Board, depth_limit: int) -> int:
        if depth_limit <= 0:
            return self.evaluation_function(board)

        if is_winning_state(board=board, player_num=self.player_number):
            return MAX_VAL + depth_limit

        best_score: int = MAX_VAL * -1  # Well beyond the maximum score possible in a game

        for move in get_valid_moves(board):
            curr_board: Board = board.copy()
            make_move(curr_board, move, self.player_number)
            curr_score: int = self.recursive_search_min(
                board=curr_board, depth_limit=depth_limit - 1
            )
            best_score: int = max(curr_score, best_score)

        return best_score

    def recursive_search_min(self, board: Board, depth_limit: int) -> int:
        if depth_limit <= 0:
            return self.evaluation_function(board) * -1

        if is_winning_state(board=board, player_num=self.other_player_number):
            return MAX_VAL * -1 + depth_limit

        best_score: int = MAX_VAL  # Well beyond the maximum score possible in a game

        for move in get_valid_moves(board):
            curr_board: Board = board.copy()
            make_move(curr_board, move, self.other_player_number)
            curr_score: int = self.recursive_search_max(
                board=curr_board, depth_limit=depth_limit - 1
            )
            best_score: int = min(curr_score, best_score)

        return best_score

    def get_mcts_move(self, board: Board) -> int | None:
        """
        Use MCTS to get the next move
        """

        # How many iterations of MCTS will we do?
        max_iterations = 1000  # Modify to work for you

        # Make the MCTS root node from the current board state
        root = MCTSNode(board, self.player_number, None)

        # Run our MCTS iterations
        for _ in range(max_iterations):
            # Select + Expand
            cur_node = root.select()

            # Simulate + backpropate
            cur_node.simulate()

        # Print out the info from the root node
        root.print_node()
        move = root.max_child()
        print("MCTS chooses action", move)
        return move

    def get_expectimax_move(self, board: Board) -> int:
        """
        Given the current state of the board, return the next move based on
        the expectimax algorithm.

        This will play against the random player, who chooses any valid move
        with equal probability

        INPUTS:
        board - a numpy array containing the state of the board using the
                following encoding:
                - the board maintains its same two dimensions
                    - row 0 is the top of the board and so is
                      the last row filled
                - spaces that are unoccupied are marked as 0
                - spaces that are occupied by player 1 have a 1 in them
                - spaces that are occupied by player 2 have a 2 in them

        RETURNS:
        The 0 based index of the column that represents the next move
        """
        moves = get_valid_moves(board)
        best_move: int = np.random.choice(moves)

        # YOUR EXPECTIMAX CODE GOES HERE

        return best_move

    def evaluation_function(self, board: Board) -> int:
        """
        Given the current stat of the board, return the scalar value that
        represents the evaluation function for the current player

        INPUTS:
        board - a numpy array containing the state of the board using the
                following encoding:
                - the board maintains its same two dimensions
                    - row 0 is the top of the board and so is
                      the last row filled
                - spaces that are unoccupied are marked as 0
                - spaces that are occupied by player 1 have a 1 in them
                - spaces that are occupied by player 2 have a 2 in them

        RETURNS:
        The utility value for the current board
        """

        # YOUR EVALUATION FUNCTION GOES HERE

        counts_mine: dict[int, int] = evalutate_board(board=board, player_num=self.player_number)
        counts_theirs: dict[int, int] = evalutate_board(board=board, player_num=self.player_number)

        score_mine: int = 0
        score_theirs: int = 0

        # Multiplies the number in a row by the count of those numbers in a row
        for how_many, count in counts_mine.items():
            score_mine += how_many * count

        for how_many, count in counts_theirs.items():
            score_theirs += how_many * count

        return score_mine - score_theirs


class RandomPlayer:
    player_number: int
    type: str
    name: str
    player_string: str

    def __init__(self, player_number: int) -> None:
        self.player_number = player_number
        self.type = "random"
        self.name = "random"
        self.player_string = f"Player {player_number}: random"

    def get_move(self, board: Board) -> int:
        """
        Given the current board state select a random column from the available
        valid moves.

        INPUTS:
        board - a numpy array containing the state of the board using the
                following encoding:
                - the board maintains its same two dimensions
                    - row 0 is the top of the board and so is
                      the last row filled
                - spaces that are unoccupied are marked as 0
                - spaces that are occupied by player 1 have a 1 in them
                - spaces that are occupied by player 2 have a 2 in them

        RETURNS:
        The 0 based index of the column that represents the next move
        """
        valid_cols: list[int] = []
        for col in range(board.shape[1]):
            if 0 in board[:, col]:
                valid_cols.append(col)

        return np.random.choice(valid_cols)


class HumanPlayer:
    player_number: int
    type: str
    name: str
    player_string: str

    def __init__(self, player_number: int) -> None:
        self.player_number = player_number
        self.type = "human"
        self.name = "human"
        self.player_string = f"Player {player_number}: human"

    def get_move(self, board: Board) -> int:
        """
        Given the current board state returns the human input for next move

        INPUTS:
        board - a numpy array containing the state of the board using the
                following encoding:
                - the board maintains its same two dimensions
                    - row 0 is the top of the board and so is
                      the last row filled
                - spaces that are unoccupied are marked as 0
                - spaces that are occupied by player 1 have a 1 in them
                - spaces that are occupied by player 2 have a 2 in them

        RETURNS:
        The 0 based index of the column that represents the next move
        """

        valid_cols: list[int] = []
        for i, col in enumerate(board.T):
            if 0 in col:  # ty: ignore[unsupported-operator]  # ty types ndarray iteration as scalars
                valid_cols.append(i)

        move = int(input("Enter your move, Human: "))

        while move not in valid_cols:
            print(f"Column full, choose from:{valid_cols}")
            move = int(input("Enter your move: "))

        return move


# CODE FOR MCTS
class MCTSNode:
    board: Board
    player_number: int
    other_player_number: int
    parent: MCTSNode | None
    moves: list[int]
    terminal: bool
    children: dict[int, MCTSNode | None]

    def __init__(self, board: Board, player_number: int, parent: MCTSNode | None) -> None:
        self.board = board
        self.player_number = player_number
        self.other_player_number = 1 if player_number == 2 else 2
        self.parent = parent
        self.moves = get_valid_moves(board)
        self.terminal = (
            (len(self.moves) == 0)
            or is_winning_state(board, player_number)
            or is_winning_state(board, self.other_player_number)
        )
        self.children: dict[int, MCTSNode | None] = {}
        for m in self.moves:
            self.children[m] = None

        # Set up stats for MCTS
        # Number of visits to this node
        self.n: int = 0

        # Total number of wins from this node (win = +1, loss = -1, tie = +0)
        # Note: these wins are from the perspective of the PARENT node of this node
        #       So, if self.player_number wins, that is -1, while if self.other_player_number wins
        #       that is a +1.  (Since parent will be using our UCB value to make choice)
        self.w: float = 0

        # c value to be used in the UCB calculation
        self.c: float = np.sqrt(2)

    def print_tree(self) -> None:
        # Debugging utility that will print the whole subtree starting at this node
        print("****")
        self.print_node()
        for m in self.moves:
            child = self.children[m]
            if child:
                child.print_tree()
        print("****")

    def print_node(self) -> None:
        # Debugging utility that will print this node's information
        print("Total Node visits and wins: ", self.n, self.w)
        print("Children: ")
        for m in self.moves:
            child = self.children[m]
            if child is None:
                print("   ", m, " is None")
            else:
                print("   ", m, ":", child.n, child.w, "UB: ", child.upper_bound(self.n))

    def max_child(self) -> int | None:
        # Return the most visited child
        # This is used at the root node to make a final decision
        max_n = 0
        max_m: int | None = None

        for m in self.moves:
            child = self.children[m]
            if child is None:
                continue
            if child.n > max_n:
                max_n = child.n
                max_m = m
        return max_m

    def upper_bound(self, N: int) -> float:
        # This function returns the UCB for this node
        # N is the number of samples for the parent node, to be used in UCB calculation

        # YOUR MCTS TASK 1 CODE GOES HERE

        # To do: return the UCB for this node (look in __init__ to see the values you can use)

        return 0

    def select(self) -> MCTSNode:
        # This recursive function combines the selection and expansion steps of the MCTS algorithm
        # It will return either:
        # A terminal node, if this is the node selected
        # The new node added to the tree, if a leaf node is selected

        max_ub = -np.inf  # Track the best upper bound found so far
        max_child: MCTSNode | None = None  # Track the best child found so far

        if self.terminal:
            # If this is a terminal node, then return it (the game is over)
            return self

        # For all of the children of this node
        for m in self.moves:
            child = self.children[m]
            if child is None:
                # If this child doesn't exist, then create it and return it
                new_board = np.copy(self.board)  # Copy board/state for the new child
                make_move(new_board, m, self.player_number)  # Make the move in the state

                # Create the child node
                new_child = MCTSNode(new_board, self.other_player_number, self)
                self.children[m] = new_child
                return new_child  # Return it

            # Child already exists, get it's UCB value
            current_ub = child.upper_bound(self.n)

            # Compare to previous best UCB
            if current_ub > max_ub:
                max_ub = current_ub
                max_child = child

        # Recursively return the select result for the best child
        if max_child is None:
            return self
        return max_child.select()

    def simulate(self) -> None:
        # This function will simulate a random game from this node's state and then call back on
        # its parent with the result

        # YOUR MCTS TASK 2 CODE GOES HERE

        # Pseudocode in comments:
        #################################
        # If this state is terminal (meaning the game is over) AND it is a winning state for
        #   self.other_player_number
        #   Then we are done and the result is 1 (since this is from parent's perspective)
        #
        # Else-if this state is terminal AND is a winning state for self.player_number
        #   Then we are done and the result is -1 (since this is from parent's perspective)
        #
        # Else-if this is not a terminal state
        # (if it is terminal and a tie (no-one won, then result is 0))
        #   Then we need to perform the random rollout
        #      1. Make a copy of the board to modify
        #      2. Keep track of which player's turn it is (first turn is current nodes
        #         self.player_number)
        #      3. Until the game is over:
        #            3.1  Make a random move for the player who's turn it is
        #            3.2  Check to see if someone won or the game ended in a tie
        #                 (Hint: you can check for a tie if there are no more valid moves)
        #            3.3  If the game is over, store the result
        #            3.4  If game is not over, change the player and continue the loop
        #
        # Update this node's total reward (self.w) and visit count (self.n) values to reflect
        # this visit and result

        # Back-propagate this result
        # You do this by calling back on the parent of this node with the result of this
        # simulation
        #    This should look like: self.parent.back(result)
        # Tip: you need to negate the result to account for the fact that the other player
        #    is the actor in the parent node, and so the scores will be from the opposite
        #    perspective
        pass

    def back(self, score: float) -> None:
        # This updates the stats for this node, then backpropagates things
        # to the parent (note the inverted score)
        self.n += 1
        self.w += score
        if self.parent is not None:
            self.parent.back(-score)  # Score inverted before passing along


# UTILITY FUNCTIONS

##### High speed matrix 45 degree rotation code #####

# =====================================================================
# 1. SETUP PHASE (Run exactly ONCE at initialization)
# =====================================================================
H, W = 6, 7
OUT_H, OUT_W = H + W - 1, min(H, W)  # 12 x 6 layout for both

# Generate basic pixel coordinates
y, x = np.indices((H, W))

# --- MAP A: Positive 45° (Top-Left to Bottom-Right Diagonals) ---
# Diagonals are grouped by (y + x)
rows_pos = y + x
cols_pos = y

MAP_POS_45 = np.full((OUT_H, OUT_W), H * W, dtype=np.int32)
MAP_POS_45[rows_pos, cols_pos] = y * W + x

# --- MAP B: Negative 45° (Top-Right to Bottom-Left Diagonals) ---
# Anti-diagonals are grouped by ((W - 1 - x) + y)
rows_neg = (W - 1 - x) + y
cols_neg = y

MAP_NEG_45 = np.full((OUT_H, OUT_W), H * W, dtype=np.int32)
MAP_NEG_45[rows_neg, cols_neg] = y * W + x


# =====================================================================
# 2. EXECUTION PHASE (Run thousands of times per second)
# =====================================================================
def rotate_45_diagonals(board: Board, flat_idx_map: np.ndarray[Any]) -> Board:
    """
    Transforms a 6x7 matrix so diagonals become solid horizontal lines.
    Zero-padding is restricted strictly to the outer edges.
    """
    # Append a trailing 0 to catch all out-of-bounds edge elements
    return np.append(board.ravel(), 0)[flat_idx_map]


##### End imported matrix 45 degree rotation code #####


## Setup Precompiled Regex Functions ##
pattern_strs_player1 = ["11", "111", "1111"]
pattern_strs_player2 = ["22", "222", "2222"]


patterns: dict[int, list[re.Pattern]] = {1: [], 2: []}

for pattern_str in pattern_strs_player1:
    patterns[1].append(re.compile(pattern=f"(?=({pattern_str}))"))

for pattern_str in pattern_strs_player2:
    patterns[2].append(re.compile(pattern=f"(?=({pattern_str}))"))


# This function will modify the board according to
# player_number moving into move column
def make_move(board: Board, move: int, player_number: int) -> None:
    row = 0
    while row < 6 and board[row, move] == 0:
        row += 1
    board[row - 1, move] = player_number


# This function will return a list of valid moves for the given board
def get_valid_moves(board: Board) -> list[int]:
    valid_moves: list[int] = []
    for c in range(7):
        if 0 in board[:, c]:
            valid_moves.append(c)
    return valid_moves


# This function returns true if player_num is winning on board
def is_winning_state(board: Board, player_num: int) -> bool:
    counts = evalutate_board(board=board, player_num=player_num)

    # 1 or more instance of 4 in a row
    return counts[4] > 0

    # def to_str(a: npt.NDArray[Any]) -> str:
    #     return "".join(a.astype(str))

    # def check_horizontal(b: Board) -> bool:
    #     return any(player_win_str in to_str(row) for row in b)

    # def check_vertical(b: Board) -> bool:
    #     return check_horizontal(b.T)

    # def check_diagonal(b: Board) -> bool:
    #     for op in (None, np.fliplr):
    #         op_board = op(b) if op is not None else b

    #         root_diag = np.diagonal(op_board, offset=0).astype(np.int64)
    #         if player_win_str in to_str(root_diag):
    #             return True

    #         for i in range(1, b.shape[1] - 3):
    #             for offset in (i, -i):
    #                 diag = np.diagonal(op_board, offset=offset).astype(np.int64)
    #                 if player_win_str in to_str(diag):
    #                     return True

    #     return False

    # return check_horizontal(board) or check_vertical(board) or check_diagonal(board)


# Student made function to abstract and reuse is_winning_state function code
def evalutate_board(board: Board, player_num: int) -> dict[int, int]:
    # Contains number of pieces in a row -> number of occurances of that many pieces in a row
    out_counts: dict[int, int] = {2: 0, 3: 0, 4: 0}

    def to_str(a: npt.NDArray[Any]) -> str:
        return "".join(a.astype(str))

    def check_horizontal(board: Board, start_row: int = 0, end_row: int = 5) -> None:

        for i in range(len(patterns[player_num])):
            for row_num in range(start_row, end_row + 1):
                row_str = to_str(board[row_num])

                # The first pattern detects 2 in a row, so it is offset by 2
                # Will add onto existing counts
                out_counts[i + 2] += len(
                    re.findall(pattern=patterns[player_num][i], string=row_str)
                )

    def check_vertical(board: Board) -> None:
        check_horizontal(board=board.T, start_row=0, end_row=6)

    def check_diagonal(board: Board) -> None:
        rotated_board_pos: Board = rotate_45_diagonals(board=board, flat_idx_map=MAP_POS_45)
        rotated_board_neg: Board = rotate_45_diagonals(board=board, flat_idx_map=MAP_NEG_45)

        check_horizontal(board=rotated_board_pos, start_row=3, end_row=8)
        check_horizontal(board=rotated_board_neg, start_row=3, end_row=8)

    check_horizontal(board=board)
    check_vertical(board=board)
    check_diagonal(board=board)

    return out_counts
