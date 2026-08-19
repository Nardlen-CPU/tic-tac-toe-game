import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path


EMPTY = ' '
HISTORY_FILE = Path(__file__).with_name('tic_tac_toe_history.json')

GAME_MODES = {
    '1': 'Player vs Player',
    '2': 'Player vs Machine',
}

BOARD_SIZES = {
    '1': 3,
    '2': 4,
    '3': 5,
}

DIFFICULTIES = {
    '1': 'Easy',
    '2': 'Intermediate',
    '3': 'Hard',
}


def clear_screen():
    if sys.platform.startswith('win'):
        os.system('cls')
    else:
        os.system('clear')


def pause():
    input('Press Enter to continue...')


def format_duration(total_seconds):
    total_seconds = int(total_seconds)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{seconds:02d}'
    return f'{minutes}:{seconds:02d}'


def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open('r', encoding='utf-8') as history_file:
            history = json.load(history_file)
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(history, list):
        return history
    return []


def save_history(history):
    try:
        with HISTORY_FILE.open('w', encoding='utf-8') as history_file:
            json.dump(history, history_file, indent=2)
    except OSError:
        print('Could not save game history.')


def print_board(board):
    size = len(board)
    print('    ' + '   '.join(str(index) for index in range(size)))
    for row_index, row in enumerate(board):
        print(f'{row_index}   ' + ' | '.join(row))
        if row_index < size - 1:
            print('   ' + '+'.join(['---'] * size))


def get_lines(board):
    size = len(board)
    rows = board
    columns = [[board[row][col] for row in range(size)] for col in range(size)]
    diagonals = [
        [board[index][index] for index in range(size)],
        [board[index][size - 1 - index] for index in range(size)],
    ]
    return rows + columns + diagonals


def check_win(board, player):
    return any(all(cell == player for cell in line) for line in get_lines(board))


def check_draw(board):
    return all(cell != EMPTY for row in board for cell in row)


def get_available_moves(board):
    size = len(board)
    return [
        (row, col)
        for row in range(size)
        for col in range(size)
        if board[row][col] == EMPTY
    ]


def choose_from_menu(title, options, prompt):
    while True:
        clear_screen()
        print(title)
        print()
        for key, label in options.items():
            print(f'{key}. {label}')

        choice = input(f'\n{prompt}: ').strip()
        if choice in options:
            return choice

        print('Invalid choice. Please try again.')
        pause()


def choose_game_settings():
    mode_choice = choose_from_menu(
        'Tic Tac Toe',
        GAME_MODES,
        'Choose a game mode',
    )
    size_choice = choose_from_menu(
        'Board Size',
        {key: f'{size} x {size}' for key, size in BOARD_SIZES.items()},
        'Choose board size',
    )
    difficulty_choice = choose_from_menu(
        'Game Level',
        DIFFICULTIES,
        'Choose level',
    )

    return {
        'mode': GAME_MODES[mode_choice],
        'board_size': BOARD_SIZES[size_choice],
        'difficulty': DIFFICULTIES[difficulty_choice],
    }


def print_score_card(settings, elapsed_seconds, history):
    print('Score Card')
    print(f"Mode: {settings['mode']}")
    print(f"Board: {settings['board_size']} x {settings['board_size']}")
    print(f"Level: {settings['difficulty']}")
    print(f'Time played: {format_duration(elapsed_seconds)}')
    print(f'Previous games: {len(history)}')


def print_history(history, limit=None):
    if not history:
        print('No previous games yet.')
        return

    shown_history = history[-limit:] if limit else history
    first_game_number = len(history) - len(shown_history) + 1

    print('Previously Played Games')
    print('No. | Date                | Mode              | Board | Level        | Result       | Time')
    print('-' * 91)

    for offset, game in enumerate(shown_history, first_game_number):
        board = f"{game.get('board_size', '?')}x{game.get('board_size', '?')}"
        print(
            f'{offset:>3} | '
            f"{game.get('played_at', 'Unknown'):<19} | "
            f"{game.get('mode', 'Unknown'):<17} | "
            f'{board:<5} | '
            f"{game.get('difficulty', 'Unknown'):<12} | "
            f"{game.get('result', 'Unknown'):<12} | "
            f"{game.get('duration', '0:00')}"
        )


def get_player_move(board):
    size = len(board)
    try:
        move = input(f'Enter your move as row,col (0-{size - 1}): ')
        row, col = map(int, move.strip().split(','))
    except ValueError:
        print(f'Invalid input. Please enter as row,col with numbers from 0 to {size - 1}.')
        pause()
        return None

    if row not in range(size) or col not in range(size):
        print(f'Row and column must be between 0 and {size - 1}.')
        pause()
        return None

    if board[row][col] != EMPTY:
        print('Cell already taken. Try again.')
        pause()
        return None

    return row, col


def find_winning_move(board, player):
    for row, col in get_available_moves(board):
        board[row][col] = player
        player_wins = check_win(board, player)
        board[row][col] = EMPTY
        if player_wins:
            return row, col
    return None


def choose_center_or_random_move(board):
    moves = get_available_moves(board)
    if not moves:
        return None

    size = len(board)
    centers = []
    if size % 2 == 1:
        center = size // 2
        centers.append((center, center))
    else:
        first_center = size // 2 - 1
        second_center = size // 2
        centers.extend([
            (first_center, first_center),
            (first_center, second_center),
            (second_center, first_center),
            (second_center, second_center),
        ])

    open_centers = [move for move in centers if move in moves]
    if open_centers:
        return random.choice(open_centers)
    return random.choice(moves)


def get_tactical_move(board, machine_player, human_player):
    winning_move = find_winning_move(board, machine_player)
    if winning_move:
        return winning_move

    blocking_move = find_winning_move(board, human_player)
    if blocking_move:
        return blocking_move

    return None


def get_intermediate_move(board, machine_player, human_player):
    tactical_move = get_tactical_move(board, machine_player, human_player)
    if tactical_move:
        return tactical_move

    return choose_center_or_random_move(board)


def board_key(board):
    return tuple(tuple(row) for row in board)


def minimax(board, machine_player, human_player, is_maximizing, depth=0, cache=None):
    if cache is None:
        cache = {}

    cache_key = (board_key(board), is_maximizing)
    if cache_key in cache:
        return cache[cache_key]

    if check_win(board, machine_player):
        return 10 - depth
    if check_win(board, human_player):
        return depth - 10
    if check_draw(board):
        return 0

    if is_maximizing:
        best_score = -sys.maxsize
        for row, col in get_available_moves(board):
            board[row][col] = machine_player
            score = minimax(board, machine_player, human_player, False, depth + 1, cache)
            board[row][col] = EMPTY
            best_score = max(best_score, score)
        cache[cache_key] = best_score
        return best_score

    best_score = sys.maxsize
    for row, col in get_available_moves(board):
        board[row][col] = human_player
        score = minimax(board, machine_player, human_player, True, depth + 1, cache)
        board[row][col] = EMPTY
        best_score = min(best_score, score)
    cache[cache_key] = best_score
    return best_score


def get_minimax_move(board, machine_player, human_player):
    if len(get_available_moves(board)) == 9:
        return 1, 1

    best_score = -sys.maxsize
    best_moves = []
    cache = {}

    for row, col in get_available_moves(board):
        board[row][col] = machine_player
        score = minimax(board, machine_player, human_player, False, cache=cache)
        board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    if not best_moves:
        return None
    return random.choice(best_moves)


def evaluate_line(line, machine_player, human_player):
    machine_count = line.count(machine_player)
    human_count = line.count(human_player)

    if machine_count and human_count:
        return 0
    if machine_count:
        return 10 ** machine_count
    if human_count:
        return -(12 ** human_count)
    return 1


def evaluate_board(board, machine_player, human_player):
    if check_win(board, machine_player):
        return 100000
    if check_win(board, human_player):
        return -100000

    score = sum(evaluate_line(line, machine_player, human_player) for line in get_lines(board))
    size = len(board)
    center = (size - 1) / 2

    for row in range(size):
        for col in range(size):
            distance_from_center = abs(row - center) + abs(col - center)
            center_bonus = size - int(distance_from_center)
            if board[row][col] == machine_player:
                score += center_bonus
            elif board[row][col] == human_player:
                score -= center_bonus

    return score


def get_strategic_move(board, machine_player, human_player):
    tactical_move = get_tactical_move(board, machine_player, human_player)
    if tactical_move:
        return tactical_move

    best_score = -sys.maxsize
    best_moves = []

    for row, col in get_available_moves(board):
        board[row][col] = machine_player
        score = evaluate_board(board, machine_player, human_player)

        human_responses = get_available_moves(board)
        if human_responses:
            worst_response_score = sys.maxsize
            for human_row, human_col in human_responses:
                board[human_row][human_col] = human_player
                response_score = evaluate_board(board, machine_player, human_player)
                board[human_row][human_col] = EMPTY
                worst_response_score = min(worst_response_score, response_score)
            score = worst_response_score

        board[row][col] = EMPTY

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    if not best_moves:
        return None
    return random.choice(best_moves)


def get_machine_move(board, machine_player, human_player, difficulty):
    moves = get_available_moves(board)
    if not moves:
        return None

    if difficulty == 'Easy':
        return random.choice(moves)
    if difficulty == 'Intermediate':
        return get_intermediate_move(board, machine_player, human_player)
    if len(board) == 3:
        return get_minimax_move(board, machine_player, human_player)
    return get_strategic_move(board, machine_player, human_player)


def get_result_label(settings, current_player):
    if settings['mode'] == 'Player vs Machine' and current_player == 'O':
        return 'Machine'
    return f'Player {current_player}'


def show_game_screen(board, settings, started_at, history):
    clear_screen()
    print_score_card(settings, time.time() - started_at, history)
    print()
    print_board(board)
    print()


def record_game(history, settings, result, duration_seconds, moves_played):
    history.append({
        'played_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'mode': settings['mode'],
        'board_size': settings['board_size'],
        'difficulty': settings['difficulty'],
        'result': result,
        'duration_seconds': int(duration_seconds),
        'duration': format_duration(duration_seconds),
        'moves': moves_played,
    })
    save_history(history)


def play_game(history):
    settings = choose_game_settings()
    size = settings['board_size']
    board = [[EMPTY for _ in range(size)] for _ in range(size)]
    current_player = 'X'
    machine_player = 'O'
    human_player = 'X'
    started_at = time.time()
    moves_played = 0

    while True:
        show_game_screen(board, settings, started_at, history)

        if settings['mode'] == 'Player vs Machine' and current_player == machine_player:
            print("Machine's turn.")
            machine_move = get_machine_move(board, machine_player, human_player, settings['difficulty'])
            if machine_move is None:
                result = 'Draw'
                break
            row, col = machine_move
            time.sleep(0.4)
        else:
            print(f"Player {current_player}'s turn.")
            player_move = get_player_move(board)
            if player_move is None:
                continue
            row, col = player_move

        board[row][col] = current_player
        moves_played += 1

        if check_win(board, current_player):
            result = get_result_label(settings, current_player)
            break

        if check_draw(board):
            result = 'Draw'
            break

        current_player = 'O' if current_player == 'X' else 'X'

    duration_seconds = time.time() - started_at
    record_game(history, settings, result, duration_seconds, moves_played)

    clear_screen()
    print_board(board)
    print()
    if result == 'Draw':
        print("It's a draw!")
    else:
        print(f'{result} wins!')
    print()
    print_score_card(settings, duration_seconds, history[:-1])
    print(f'Moves played: {moves_played}')
    print()
    print_history(history, limit=5)
    print()
    pause()


def show_history_screen(history):
    clear_screen()
    print_history(history)
    print()
    pause()


def tic_tac_toe():
    history = load_history()

    while True:
        action = choose_from_menu(
            'Tic Tac Toe',
            {
                '1': 'Start New Game',
                '2': 'View Game History',
                '3': 'Exit',
            },
            'Choose an option',
        )

        if action == '1':
            play_game(history)
        elif action == '2':
            show_history_screen(history)
        else:
            break


if __name__ == '__main__':
    tic_tac_toe()
