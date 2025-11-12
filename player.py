from board import Direction, Rotation, Action, Shape
from random import Random
import time

# === GLOBAL CONFIG (modified dynamically by optimizer) ===
USE_LOOKAHEAD = True

# Default weight values (get overridden by optimizer)
DEFAULT_WEIGHTS = {
    "height_weight": 23.5,
    "hole_weight": 120,
    "bump_weight": 7.7,
    "lines_weight": 2.0,
    "potential_weight": 8.6,
    "lookahead_weight": 0.45,

    # New heuristic weights
    "well_weight": 2.5,
    "transition_weight": 0.2,
    "hole_depth_weight": 0.5,
}


# === HELPER FUNCTIONS ===
def max_height(test_board):
    min_y = min((y for (_, y) in test_board.cells), default=test_board.height)
    return test_board.height - min_y


def build_tetris(board, move, block_type, lines_cleared_count):
    score = 0
    width = board.width
    height = board.height

    col_heights = []
    for x in range(width):
        top_y = min((y for (cx, y) in board.cells if cx == x), default=height)
        col_heights.append(height - top_y)

    right_col = width - 1
    neighbor_height = col_heights[right_col - 1] if width >= 2 else 0
    well_depth = max(0, neighbor_height - col_heights[right_col])

    if lines_cleared_count == 4:
        score += 80
    if well_depth >= 4:
        score += 6
    elif well_depth >= 2:
        score += 3
    if block_type.shape != Shape.I and well_depth < 2:
        score -= 8

    return score


def bumpiness(test_board):
    total = 0
    for x in range(test_board.width - 1):
        thisheight = min((y for (cx, y) in test_board.cells if cx == x), default=test_board.height)
        nextheight = min((y for (cx, y) in test_board.cells if cx == x + 1), default=test_board.height)
        total += abs(thisheight - nextheight)
    return total


def holes(test_board):
    hole_count = 0
    column_heights = {}
    for x in range(test_board.width):
        column_heights[x] = min((y for cx, y in test_board.cells if cx == x), default=test_board.height)
    for x in range(test_board.width):
        for y in range(column_heights[x], test_board.height):
            if (x, y) not in test_board.cells:
                hole_count += 1
    return hole_count


# === NEW HEURISTICS ===
def right_well_score(board):
    width, height = board.width, board.height
    col_heights = [
        height - min((y for (cx, y) in board.cells if cx == x), default=height)
        for x in range(width)
    ]
    right_well_depth = max(0, max(col_heights[:-1]) - col_heights[-1])
    blocked = any((width - 1, y) in board.cells for y in range(height - right_well_depth, height))
    if blocked:
        return -5 * right_well_depth
    return +2 * right_well_depth


def row_col_transitions(board):
    grid = [[(x, y) in board.cells for x in range(board.width)] for y in range(board.height)]
    row_trans = sum(sum(grid[y][x] != grid[y][x + 1] for x in range(board.width - 1)) for y in range(board.height))
    col_trans = sum(sum(grid[y][x] != grid[y + 1][x] for y in range(board.height - 1)) for x in range(board.width))
    return row_trans + col_trans


def hole_depth_penalty(board):
    height = board.height
    total = 0
    for x in range(board.width):
        col = sorted([y for (cx, y) in board.cells if cx == x])
        if not col:
            continue
        top_y = col[0]
        for y in range(top_y, height):
            if (x, y) not in board.cells:
                total += (height - y)
    return total


def score_to_lines(score):
    score_map = {0: 0, 25: 1, 100: 2, 400: 3, 1600: 4}
    return score_map.get(score, 0)


def generate_moves(board, block):
    moves = []
    for rotation in range(4):
        start_board = board.clone()
        rotation_landed = False
        for _ in range(rotation):
            start_board.rotate(Rotation.Clockwise)
            if start_board.falling is None:
                rotation_landed = True
                break
        if rotation_landed or start_board.falling is None:
            continue

        block_width = max(x for x, y in start_board.falling.cells) - min(x for x, y in start_board.falling.cells) + 1
        max_x = board.width - block_width

        for target_x in range(max_x + 1):
            test_board = start_board.clone()
            shift = target_x - test_board.falling.left

            actions = []
            if shift > 0:
                actions = [Direction.Right] * shift
            elif shift < 0:
                actions = [Direction.Left] * abs(shift)

            path_blocked = False
            for action in actions:
                if test_board.falling is None:
                    path_blocked = True
                    break
                old_x = test_board.falling.left
                test_board.move(action)
                if test_board.falling is None or test_board.falling.left == old_x:
                    path_blocked = True
                    break

            if path_blocked or test_board.falling is None:
                continue

            test_board.move(Direction.Drop)
            moves.append({
                "rotation": rotation,
                "x_moves": shift,
                "board": test_board,
                "landing_column": target_x,
                "block_width": block_width,
            })
    return moves


def generate_lookahead_moves(test_board, next_block):
    lookahead_moves = []
    initial_simulation_board = test_board.clone()
    if initial_simulation_board.falling is not None:
        initial_simulation_board.falling = None
    initial_simulation_board.falling = next_block.clone()
    initial_simulation_board.falling.initialize(initial_simulation_board)

    for rotation in range(4):
        sim_board = initial_simulation_board.clone()
        rotation_landed = False
        for _ in range(rotation):
            sim_board.rotate(Rotation.Clockwise)
            if sim_board.falling is None:
                rotation_landed = True
                break
        if rotation_landed or sim_board.falling is None:
            continue

        block_width = max(x for x, y in sim_board.falling.cells) - min(x for x, y in sim_board.falling.cells) + 1
        max_x = sim_board.width - block_width

        for target_x in range(max_x + 1):
            final_board = sim_board.clone()
            shift = target_x - final_board.falling.left

            actions = []
            if shift > 0:
                actions = [Direction.Right] * shift
            elif shift < 0:
                actions = [Direction.Left] * abs(shift)

            path_blocked = False
            for action in actions:
                if final_board.falling is None:
                    path_blocked = True
                    break
                old_x = final_board.falling.left
                final_board.move(action)
                if final_board.falling is None or final_board.falling.left == old_x:
                    path_blocked = True
                    break

            if path_blocked or final_board.falling is None:
                continue

            final_board.move(Direction.Drop)
            lookahead_moves.append({
                "rotation": rotation,
                "x_moves": shift,
                "board": final_board,
                "landing_column": target_x,
                "block_width": block_width,
            })
    return lookahead_moves


def lookahead_score(lookahead_moves, weights):
    for move in lookahead_moves:
        test_board = move["board"]
        if not test_board.alive:
            move["score"] = -10**6
            continue

        linescore = test_board.clean() / 100
        height = max_height(test_board)
        bumps = bumpiness(test_board)
        hole_count = holes(test_board)

        move["score"] = (
            weights["lines_weight"] * linescore
            - weights["height_weight"] * height
            - weights["hole_weight"] * hole_count
            - weights["bump_weight"] * bumps
        )
    return lookahead_moves


def score_moves(board, block, moves, weights):
    next_block = board.next
    for move in moves:
        test_board = move["board"]
        if not test_board.alive:
            move["score"] = -10**6
            continue

        clean_score = test_board.clean()
        lines_cleared_count = score_to_lines(clean_score)
        linescore = clean_score / 100.0

        height = max_height(test_board)
        bumps = bumpiness(test_board)
        hole_count = holes(test_board)
        potential = build_tetris(test_board, move, block, lines_cleared_count)

        # === New Heuristic Components ===
        well_score = right_well_score(test_board)
        transitions = row_col_transitions(test_board)
        hole_depth = hole_depth_penalty(test_board)

        score_current = (
            weights["lines_weight"] * linescore
            - weights["height_weight"] * height
            - weights["hole_weight"] * hole_count
            - weights["bump_weight"] * bumps
            + weights["potential_weight"] * potential
            + weights["well_weight"] * well_score
            - weights["transition_weight"] * transitions
            - weights["hole_depth_weight"] * hole_depth
        )

        if USE_LOOKAHEAD and next_block is not None:
            lookahead_moves = generate_lookahead_moves(test_board, next_block)
            scored_future_moves = lookahead_score(lookahead_moves, weights)
            if scored_future_moves:
                max_future_score = max(m["score"] for m in scored_future_moves)
            else:
                max_future_score = -10**6
            final_score = score_current + (weights["lookahead_weight"] * max_future_score)
        else:
            final_score = score_current

        move["score"] = final_score
    return moves


# === PLAYER CLASS ===
class Player:
    def __init__(self, weights=None, lookahead_enabled=True):
        global USE_LOOKAHEAD
        USE_LOOKAHEAD = lookahead_enabled
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def choose_action(self, board):
        if board.falling is None:
            return None

        if max_height(board) > board.height - 5 and board.bombs_remaining > 0:
            return [Action.Bomb]

        moves = generate_moves(board, board.falling)
        if not moves:
            if board.discards_remaining > 0:
                return [Action.Discard]
            else:
                return None

        scored_moves = score_moves(board, board.falling, moves, self.weights)

        if scored_moves and max(m["score"] for m in scored_moves) < -1000 and board.discards_remaining > 0:
            return [Action.Discard]

        best_move = max(scored_moves, key=lambda m: m["score"])
        if best_move["score"] < -10000 and board.bombs_remaining > 0:
            return [Action.Bomb]

        actions = []
        for _ in range(best_move["rotation"]):
            actions.append(Rotation.Clockwise)
        x_moves = best_move["x_moves"]
        if x_moves > 0:
            actions += [Direction.Right] * x_moves
        elif x_moves < 0:
            actions += [Direction.Left] * abs(x_moves)
        actions.append(Direction.Drop)
        return actions


# === OPTIONAL RANDOM PLAYER (unchanged) ===
class RandomPlayer(Player):
    def __init__(self, seed=None):
        self.random = Random(seed)

    def print_board(self, board):
        print("--------")
        for y in range(24):
            s = ""
            for x in range(10):
                s += "#" if (x, y) in board.cells else "."
            print(s, y)

    def choose_action(self, board):
        self.print_board(board)
        time.sleep(0.5)
        if self.random.random() > 0.97:
            return self.random.choice([Action.Discard, Action.Bomb])
        else:
            return self.random.choice([
                Direction.Left,
                Direction.Right,
                Direction.Down,
                Rotation.Anticlockwise,
                Rotation.Clockwise,
            ])


SelectedPlayer = Player












