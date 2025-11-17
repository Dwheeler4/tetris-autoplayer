from board import Direction, Rotation, Action, Shape
from random import Random
import math

BEAM_WIDTH = 10
USE_LOOKAHEAD = True

DEFAULT_WEIGHTS = {
  "height_base": 3.077084013339751,
  "height_danger": -501.15367427517356,
  "danger_threshold": 4.128936490676556,
  "bumpiness": -12.000750942870829,
  "holes": -100.53876943595337,
  "well_depth": -3.561498010389435,
  "well_penalty": -50.53612768210999,
  "tetris_setup": 20.377539129701354,
  "clear_1": -30.780053176506035,
  "clear_2": -30.358252498280715,
  "clear_3": -80.0686350277031798,
  "clear_4": 17.67222694804013,
  "bomb_threshold": 0.755078808847
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


def analyze_wells(col_heights):
    """
    Returns (wells, best_x, best_depth)
      wells: list[(x, depth)]
      best_x: index of chosen well (prefers deepest; side wells if tie)
      best_depth: its depth
    """
    wells = []
    W = len(col_heights)
    for x in range(W):
        left = col_heights[x - 1] if x > 0 else col_heights[x]
        right = col_heights[x + 1] if x < W - 1 else col_heights[x]
        neigh_min = min(left, right)
        depth = neigh_min - col_heights[x]
        if depth >= 1:
            wells.append((x, depth))

    if not wells:
        return wells, None, 0.0

    wells_sorted = sorted(wells, key=lambda t: t[1], reverse=True)
    best_depth = wells_sorted[0][1]
    candidates = [w for w in wells_sorted if w[1] == best_depth]

    side_candidates = [w for w in candidates if w[0] == 0 or w[0] == W - 1]
    if side_candidates:
        best_x = side_candidates[0][0]
    else:
        best_x = candidates[0][0]

    return wells, best_x, float(best_depth)


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

        danger_factor = (h_ratio - w["danger_threshold"]) / (1.0 - w["danger_threshold"])
        expv = math.exp(4.0 * max(0.0, min(1.0, danger_factor)))
        h_penalty = w["height_base"] * max_h + w["height_danger"] * expv

    bumps = sum(abs(col[i] - col[i + 1]) for i in range(len(col) - 1))
    holes = count_holes(board)


    wells, best_x, best_depth = analyze_wells(col)
    if best_x is None:
        well_score = 0.0
        multi_penalty = 0.0
        setup_bonus = 0.0
    else:

        well_score = w["well_depth"] * best_depth

   
        extra_wells = max(0, len(wells) - 1)
        multi_penalty = w["well_penalty"] * extra_wells


        setup_bonus = 0.0
        if best_depth >= 3:
            setup = best_depth - 2.0  # depth 3 → 1, 4 → 2, etc.

            if best_x == 0 or best_x == len(col) - 1:
                setup *= 1.3
            setup_bonus = w["tetris_setup"] * setup

    clear_score = w.get(f"clear_{lines}", 0.0)

    score = 0.0
    score += h_penalty
    score += w["bumpiness"] * bumps
    score += w["holes"] * holes
    score += well_score
    score += multi_penalty
    score += setup_bonus
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
                "actions": actions,
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
            best_next = -8000.0
        else:
            best_next = max(
                evaluate(m2["board"], m2["lines"], w) for m2 in moves2
            )
        total = m1["immediate"] + discount * best_next
        if total > best_score:
            best_score = total
            best_move = m1

    return best_move, best_score


class Player:
    def __init__(self, weights=None, lookahead_enabled=True):
        global USE_LOOKAHEAD
        USE_LOOKAHEAD = lookahead_enabled
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    def choose_action(self, board):

        if board.cells and board.bombs_remaining > 0:
            highest = min(y for _, y in board.cells)  
            ratio = 1.0 - (highest / board.height)    
            if ratio >= self.weights["bomb_threshold"]:
                return [Action.Bomb]

        col_heights = get_column_heights(board) if board.cells else []

        if (
            board.discards_remaining > 0
            and board.falling is not None
            and col_heights
        ):
            max_h = max(col_heights)
            h_ratio = max_h / board.height
            wells, best_x, best_depth = analyze_wells(col_heights)
            single_good_well = (len(wells) == 1 and best_depth >= 3)


            if (
                h_ratio < 0.6
                and single_good_well
                and board.falling.shape in (Shape.S, Shape.Z)
            ):
                return [Action.Discard]

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
            Direction.Left,
            Direction.Right,
            Direction.Down,
            Rotation.Clockwise,
            Rotation.Anticlockwise,
        ])


SelectedPlayer = Player

























