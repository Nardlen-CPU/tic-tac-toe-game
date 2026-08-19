import pytest
from tic_tac_toe import (
    EMPTY,
    get_available_moves,
    find_winning_move,
    get_winning_line,
    check_win,
    check_draw,
)


def test_get_winning_line_row():
    board = [
        ['X', 'X', 'X'],
        [' ', 'O', ' '],
        ['O', ' ', ' '],
    ]
    line = get_winning_line(board, 'X')
    assert line == [(0, 0), (0, 1), (0, 2)]


def test_get_winning_line_col():
    board = [
        ['O', 'X', ' '],
        ['O', 'X', ' '],
        ['O', ' ', 'X'],
    ]
    line = get_winning_line(board, 'O')
    assert line == [(0, 0), (1, 0), (2, 0)]


def test_get_winning_line_diag():
    board = [
        ['X', 'O', ' '],
        ['O', 'X', ' '],
        [' ', ' ', 'X'],
    ]
    line = get_winning_line(board, 'X')
    assert line == [(0, 0), (1, 1), (2, 2)]


def test_check_draw():
    board = [
        ['X', 'O', 'X'],
        ['X', 'O', 'O'],
        ['O', 'X', 'X'],
    ]
    assert check_draw(board) is True


def test_find_winning_move_and_blocking():
    # Machine can win
    board = [
        ['X', 'O', 'X'],
        ['O', 'O', ' '],
        ['X', ' ', ' '],
    ]
    # For player O, winning move is (1,2)
    win = find_winning_move(board, 'O')
    assert win == (1, 2)

    # For player X, blocking move should be (1,2)
    block = find_winning_move(board, 'X')
    # No immediate winning move for X here
    assert block is None


def test_available_moves():
    board = [
        ['X', 'O', 'X'],
        [' ', 'O', ' '],
        ['O', ' ', 'X'],
    ]
    moves = get_available_moves(board)
    assert (1, 0) in moves and (1, 2) in moves
