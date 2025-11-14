from board import Direction, Rotation, Action
from random import Random
import math

BEAM_WIDTH = 20
USE_LOOKAHEAD = True

OPTIMAL_WEIGHTS = {
    "height_base": -5.0,
    "height_danger": -100.0,
    "danger_threshold": 0.65,
    "bumpiness": -7.0,
    "holes": -50.0,
    "well_depth": 20.0,
    "well_penalty": -15.0,
    "clear_1": -8.0,
    "clear_2": -3.0,
    "clear_3": 3.0,
    "clear_4": 50.0,
    "bomb_threshold": 0.7,
}

def get_column_heights(board):
    heights = []
    for x in range(board.width):
        ys = [y for cx, y in board.cells if cx == x]
        heights.append(board.height - min(ys) if ys else 0)
    return heights

def count_holes(board):
    total = 0
    for x in range(board.width):
        ys = sorted([y for cx, y in board.cells if cx == x])
        if not ys:
            continue
        top = ys[0]
        for y in range(top + 1, board.height):
            if (x, y) not in board.cells:
                total += 1
    return total

def evaluate_well_right(col_heights, width, target_depth, weights):
    well_x = width - 1
    well_h = col_heights[well_x]
    others = [h for i, h in enumerate(col_heights) if i != well_x]
    if not others:
        return 0.0
    avg = sum(others) / len(others)
    depth = avg - well_h
    penalty = abs(depth - target_depth)
    return max(0, depth), penalty

def map_line_clear(points):
    if points >= 1600:
        return 4
    if points >= 400:
        return 3
    if points >= 100:
        return 2
    if points >= 25:
        return 1
    return 0

def evaluate(board, lines, w):
    if not board.alive:
        return -1e6
    col = get_column_heights(board)
    if not col:
        return w.get(f"clear_{lines}", 0.0)
    max_h = max(col)
    h_ratio = max_h / board.height
    if h_ratio <= w["danger_threshold"]:
        h_penalty = w["height_base"] * max_h
    else:
        d = (h_ratio - w["danger_threshold"]) / (1 - w["danger_threshold"])
        expv = math.exp(4 * d)
        h_penalty = w["height_base"] * max_h + w["height_danger"] * expv
    bumps = sum(abs(col[i] - col[i + 1]) for i in range(len(col) - 1))
    holes = count_holes(board)
    well_depth, well_penalty = evaluate_well_right(col, board.width, 4, w)
    clear_score = w.get(f"clear_{lines}", 0.0)
    score = 0
    score += h_penalty
    score += w["bumpiness"] * bumps
    score += w["holes"] * holes
    score += w["well_depth"] * well_depth
    score += w["well_penalty"] * well_penalty
    score += clear_score
    return score

def try_sequence(board, rotations, dx):
    sim = board.clone()
    for _ in range(rotations):
        if sim.falling is None:
            return False, None
        test = sim.clone()
        before = frozenset(test.falling.cells)
        test.rotate(Rotation.Clockwise)
        if test.falling is None or frozenset(test.falling.cells) == before:
            return False, None
        landed = sim.rotate(Rotation.Clockwise)
        if landed or sim.falling is None:
            return False, None
    if sim.falling is None:
        return False, None
    if dx != 0:
        direction = Direction.Right if dx > 0 else Direction.Left
        for _ in range(abs(dx)):
            test = sim.clone()
            before = test.falling.left
            test.move(direction)
            if test.falling is None or test.falling.left == before:
                return False, None
            landed = sim.move(direction)
            if landed or sim.falling is None:
                return False, None
    return True, sim

def generate_moves(board):
    if board.falling is None:
        return []
    moves = []
    seen = set()
    for rot in range(4):
        for dx in range(-board.width, board.width + 1):
            ok, sim = try_sequence(board, rot, dx)
            if not ok or sim is None or sim.falling is None:
                continue
            state = (frozenset(sim.falling.cells), sim.falling.left, sim.falling.top)
            if state in seen:
                continue
            seen.add(state)
            old = sim.score
            sim.score = 0
            sim.move(Direction.Drop)
            gained = sim.score
            sim.score = old + gained
            lines = map_line_clear(gained)
            actions = [Rotation.Clockwise] * rot
            if dx > 0:
                actions += [Direction.Right] * dx
            elif dx < 0:
                actions += [Direction.Left] * (-dx)
            actions.append(Direction.Drop)
            moves.append({
                "board": sim,
                "lines": lines,
                "actions": actions
            })
    return moves

def beam_search_2ply(board, w, discount=0.6):
    moves1 = generate_moves(board)
    if not moves1:
        return None, -1e9
    for m in moves1:
        m["immediate"] = evaluate(m["board"], m["lines"], w)
    moves1.sort(key=lambda m: m["immediate"], reverse=True)
    moves1 = moves1[:BEAM_WIDTH]
    best_move = None
    best_score = -1e9
    for m1 in moves1:
        moves2 = generate_moves(m1["board"])
        if not moves2:
            best_next = -8000
        else:
            best_next = max(evaluate(m2["board"], m2["lines"], w) for m2 in moves2)
        total = m1["immediate"] + discount * best_next
        if total > best_score:
            best_score = total
            best_move = m1
    return best_move, best_score

class Player:
    def __init__(self, weights=None, lookahead_enabled=True):
        global USE_LOOKAHEAD
        USE_LOOKAHEAD = lookahead_enabled
        self.weights = weights or OPTIMAL_WEIGHTS.copy()

    def choose_action(self, board):
        if board.cells and board.bombs_remaining > 0:
            highest = min(y for _, y in board.cells)
            ratio = 1 - (highest / board.height)
            if ratio >= self.weights["bomb_threshold"]:
                return [Action.Bomb]
        if USE_LOOKAHEAD:
            move, _ = beam_search_2ply(board, self.weights)
        else:
            moves = generate_moves(board)
            if not moves:
                return [Direction.Drop]
            for m in moves:
                m["score"] = evaluate(m["board"], m["lines"], self.weights)
            move = max(moves, key=lambda x: x["score"])
        if move is None:
            return [Direction.Drop]
        return move["actions"]

class RandomPlayer:
    def __init__(self, seed=None):
        self.random = Random(seed)
    def choose_action(self, board):
        if self.random.random() > 0.97:
            return self.random.choice([Action.Bomb, Action.Discard])
        return self.random.choice([
            Direction.Left, Direction.Right, Direction.Down,
            Rotation.Clockwise, Rotation.Anticlockwise
        ])

SelectedPlayer = Player























