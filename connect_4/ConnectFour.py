# Modified 10.3.2023 by Chris Archibald to
#  - run multiple experiments automatically
#  - incorporate MCTS with other code
#  - pass command line param string to each AI
#  - bypass tkinter when it doesn't exist, as that has proven problematic for some users

from __future__ import annotations

# system libs
import argparse
import multiprocessing as mp
import sys
from collections.abc import Callable
from multiprocessing.connection import Connection

# 3rd party libs
import numpy as np
import numpy.typing as npt

# See if they have tkinter
try:
    import tkinter as tk

    graphics = True
except ImportError:
    graphics = False

# Local libs
from Player import AIPlayer, HumanPlayer, RandomPlayer

# Every board is a 6x7 array of uint8 values (0 = empty, 1 = player one, 2 = player two).
Board = npt.NDArray[np.uint8]

# Any object that can pick a move for a board.
AnyPlayer = AIPlayer | RandomPlayer | HumanPlayer

# A bound method that picks a column for the given board.
MoveFunc = Callable[[Board], int | None]


# https://stackoverflow.com/a/37737985
def turn_worker(board: Board, send_end: Connection, p_func: MoveFunc) -> None:
    send_end.send(p_func(board))


# List of symbols
symbols: list[str] = [".", "X", "O"]


# This is the main game class that will store the information
# necessary for the game to play and also run the game
class Game:
    players: list[AnyPlayer]
    colors: list[str]
    current_turn: int
    board: Board
    gui_board: list[list[int]]
    game_over: bool
    winner: str | None
    loser: str | None
    ai_turn_limit: int
    interactive: bool
    # Only created when the tkinter GUI is actually in use.
    player_string: tk.Label
    c: tk.Canvas

    def __init__(
        self,
        player1: AnyPlayer,
        player2: AnyPlayer,
        time: int,
        interactive: bool,
    ) -> None:
        self.players = [player1, player2]
        self.colors = ["yellow", "red"]
        self.current_turn = 0
        self.board = np.zeros((6, 7), dtype=np.uint8)
        self.gui_board: list[list[int]] = []
        self.game_over = False
        self.winner = None
        self.loser = None
        self.ai_turn_limit = time
        self.interactive = interactive

        global graphics
        if not interactive:
            graphics = False

        if graphics:
            # https://stackoverflow.com/a/38159672
            root = tk.Tk()
            root.title("Connect 4")
            self.player_string = tk.Label(root, text=player1.player_string)
            self.player_string.pack()
            self.c = tk.Canvas(root, width=700, height=600)
            self.c.pack()

            for row in range(0, 700, 100):
                column: list[int] = []
                for col in range(0, 700, 100):
                    column.append(self.c.create_oval(row, col, row + 100, col + 100, fill=""))
                self.gui_board.append(column)

            tk.Button(root, text="Next Move", command=self.make_move).pack()
            root.mainloop()
        else:
            if interactive:
                self.print_board()
            self.gameloop()

    def gameloop(self) -> None:
        while True:
            if self.interactive:
                command = input("Press enter to continue game, Type x to end game: ")
                if command == "x":
                    break

            self.make_move()
            if self.game_over:
                break

        if self.interactive:
            print("Game is over.  Thanks for playing")

    def make_move(self) -> None:
        if not self.game_over:
            current_player = self.players[self.current_turn]

            if isinstance(current_player, AIPlayer):
                if current_player.type == "mcts":
                    p_func: MoveFunc = current_player.get_mcts_move
                elif current_player.type == "expmax":
                    p_func = current_player.get_expectimax_move
                else:
                    p_func = current_player.get_alpha_beta_move

                try:
                    recv_end, send_end = mp.Pipe(False)
                    p = mp.Process(target=turn_worker, args=(self.board, send_end, p_func))
                    p.start()
                    if p.join(self.ai_turn_limit) is None and p.is_alive():
                        p.terminate()
                        raise Exception("Player Exceeded time limit")
                except Exception as e:
                    uh_oh = "Uh oh.... something is wrong with Player {}"
                    print(uh_oh.format(current_player.player_number))
                    print(e)
                    raise Exception("Game Over") from e

                move: int | None = recv_end.recv()
            else:
                move = current_player.get_move(self.board)

            if move is not None:
                self.update_board(int(move), current_player.player_number)

            if self.game_won(current_player.player_number):
                # Set the winner and losers
                self.winner = current_player.name
                self.loser = self.players[int(not self.current_turn)].name
                # Mark the game as over
                self.game_over = True
                if graphics:
                    self.player_string.configure(
                        text=self.players[self.current_turn].player_string + " wins!"
                    )
                else:
                    print(self.players[self.current_turn].player_string + " wins!")
                print("Game over!")
            elif self.game_tied():
                # Mark the game as over
                self.game_over = True
                if graphics:
                    self.player_string.configure(text="Game ends in a tie!")
                else:
                    print("Game ends in a tie!")
            else:
                self.current_turn = int(not self.current_turn)
                if graphics:
                    self.player_string.configure(text=self.players[self.current_turn].name)
                else:
                    print(
                        "Current Turn: ",
                        self.players[self.current_turn].name,
                        "  using symbol : ",
                        symbols[self.players[self.current_turn].player_number],
                    )

    def update_board(self, move: int, player_num: int) -> None:
        if 0 in self.board[:, move]:
            update_row = -1
            for row in range(1, self.board.shape[0]):
                update_row = -1
                if self.board[row, move] > 0 and self.board[row - 1, move] == 0:
                    update_row = row - 1
                elif row == self.board.shape[0] - 1 and self.board[row, move] == 0:
                    update_row = row

                if update_row >= 0:
                    self.board[update_row, move] = player_num
                    if self.interactive:
                        if graphics:
                            self.c.itemconfig(
                                self.gui_board[move][update_row],
                                fill=self.colors[self.current_turn],
                            )
                        else:
                            self.print_board()
                    break
        else:
            err = f"Invalid move by player {player_num}. Column {move}"
            raise Exception(err)

    def print_board(self) -> None:
        for r in range(0, self.board.shape[0]):
            for c in range(0, self.board.shape[1]):
                if self.board[r, c] == 0:
                    print(" . ", end="")
                elif self.board[r, c] == 1:
                    print(" X ", end="")
                elif self.board[r, c] == 2:
                    print(" O ", end="")
            print(" ")

        # Display the column names as well
        print("---------------------")

        for c in range(0, self.board.shape[1]):
            print(f" {c} ", end="")
        print(" ")

    def game_tied(self) -> bool:
        return 0 not in self.board

    def game_won(self, player_num: int) -> bool:
        player_win_str = f"{player_num}{player_num}{player_num}{player_num}"
        board = self.board

        def to_str(a: npt.NDArray[np.int_]) -> str:
            return "".join(a.astype(str))

        def check_horizontal(b: Board) -> bool:
            return any(player_win_str in to_str(row) for row in b)

        def check_verticle(b: Board) -> bool:
            return check_horizontal(b.T)

        def check_diagonal(b: Board) -> bool:
            for op in (None, np.fliplr):
                op_board = op(b) if op is not None else b

                root_diag = np.diagonal(op_board, offset=0).astype(np.int_)
                if player_win_str in to_str(root_diag):
                    return True

                for i in range(1, b.shape[1] - 3):
                    for offset in (i, -i):
                        diag = np.diagonal(op_board, offset=offset).astype(np.int_)
                        if player_win_str in to_str(diag):
                            return True

            return False

        return check_horizontal(board) or check_verticle(board) or check_diagonal(board)


def play_game(
    player1name: str,
    player2name: str,
    player1: str,
    player2: str,
    time: int,
    params1: str | None,
    params2: str | None,
    interactive: bool,
    stats: dict[str, dict[str, int]],
) -> None:
    """
    Creates player objects based on the string parameters that are passed
    to it and creates game, which then plays

    INPUTS:
    player1 - a string ['ab', 'random', 'human', 'mcts', 'expmax']
    player2 - a string ['ab', 'random', 'human', 'mcts', 'expmax']
    """

    def make_player(name: str, method: str, num: int, params: str | None) -> AnyPlayer:
        if method == "ab" or method == "expmax" or method == "mcts":
            return AIPlayer(num, name, method, params)
        elif method == "random":
            return RandomPlayer(num)
        elif method == "human":
            return HumanPlayer(num)
        raise ValueError(f"Unknown player type: {method}")

    g = Game(
        make_player(player1name, player1, 1, params1),
        make_player(player2name, player2, 2, params2),
        time,
        interactive,
    )

    # Update stats with winner, loser, or ties
    if g.winner is not None and g.loser is not None:
        stats[g.winner]["wins"] += 1
        stats[g.loser]["losses"] += 1
    else:
        stats[player1name]["ties"] += 1
        stats[player2name]["ties"] += 1


# This function sets up everything for the experiments, and repeatedly calls play_game to run
# the games
def main(
    player1: str,
    player2: str,
    time: int,
    n: int,
    params1: str | None,
    params2: str | None,
) -> None:
    # Set up this run of the program

    # Create player names
    p1name = player1
    if params1:
        p1name += params1
    p2name = player2
    if params2:
        p2name += params2

    if p1name == p2name:
        print("Error: players must be different or have different parameters!")
        sys.exit()

    # Get list of player names
    pnames = [p1name, p2name]

    # Access to player and paramstrings
    pstring = {p1name: player1, p2name: player2}
    params = {p1name: params1, p2name: params2}

    # Store what happened in each game
    stats: dict[str, dict[str, int]] = {
        p1name: {"wins": 0, "ties": 0, "losses": 0},
        p2name: {"wins": 0, "ties": 0, "losses": 0},
    }

    # Are we running in interactive mode?
    interactive = False
    if n == 1 or "human" in pnames:
        interactive = True

    # Play 2n games (Each player goes first n times)
    N = 2 * n
    # Unless n = 1, then we only play one game
    if n == 1:
        N = 1

    print(f"Playing {N} games between {p1name} and {p2name}")

    for _ in range(N):
        # Play game with current player list
        play_game(
            pnames[0],
            pnames[1],
            pstring[pnames[0]],
            pstring[pnames[1]],
            time,
            params[pnames[0]],
            params[pnames[1]],
            interactive,
            stats,
        )

        # Reverse the order of the players
        pnames.reverse()

    # Display the results of the games
    print("Experiment results: ")
    print(stats)


if __name__ == "__main__":
    player_types = ["ab", "random", "human", "mcts", "expmax"]
    parser = argparse.ArgumentParser()
    parser.add_argument("player1", choices=player_types)
    parser.add_argument("player2", choices=player_types)
    parser.add_argument("-p1", "--params1", help="Parameter string for agent 1", default=None)
    parser.add_argument("-p2", "--params2", help="Parameter string for agent 2", default=None)
    parser.add_argument(
        "-n",
        "--number",
        help="Number of games each player goes first in match. If this number is 1, "
        "game will be interactive.",
        type=int,
        default=1,
    )
    parser.add_argument(
        "-t",
        "--time",
        type=int,
        default=60,
        help="Time to wait for a move in seconds (int)",
    )
    args = parser.parse_args()

    main(args.player1, args.player2, args.time, args.number, args.params1, args.params2)
