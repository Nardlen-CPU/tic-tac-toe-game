import random
from tic_tac_toe import get_machine_move, EMPTY


def test_alphabeta_move_exists_4x4():
    # empty 4x4 board
    board = [[EMPTY]*4 for _ in range(4)]
    rng = random.Random(42)
    mv = get_machine_move(board, 'O', 'X', 'Grandmaster', rng=rng)
    assert mv is not None
    r, c = mv
    assert 0 <= r < 4 and 0 <= c < 4


def test_alphabeta_move_on_partial_board():
    board = [[EMPTY]*4 for _ in range(4)]
    # occupy some cells
    board[0][0] = 'X'
    board[1][1] = 'O'
    rng = random.Random(123)
    mv = get_machine_move(board, 'O', 'X', 'Grandmaster', rng=rng)
    assert mv is not None
    r, c = mv
    assert board[r][c] == EMPTY
