from board import Direction, Rotation, Action
from random import Random
import time



height_weight = 10
hole_weight = 15
bump_weight = 2
lines_weight = 3
lookahead_weight= 0.7

bomb_limit = 1000
discard_limit= 800
# --- Heuristics ---

def max_height(test_board):
    min_y = min((y for (_, y) in test_board.cells), default=0)
    height = test_board.height - min_y
    return height

def holes(test_board):
    # This function is required for the scoring logic to run, 
    # even if it returns 0. For actual AI performance, it must be implemented.
    return 0

def bumpiness(test_board):
    total = 0
    for x in range(test_board.width - 1):
        thisheight = max((y for (cx, y) in test_board.cells if cx == x), default=test_board.height)
        nextheight = max((y for (cx, y) in test_board.cells if cx == x + 1), default=test_board.height)
        difference = abs(thisheight - nextheight)
        total += difference
    return total

def holes(test_board):
    hole_count = 0
    column_heights = {}
    for x in range(test_board.width):
        column_heights[x] = min((y for cx, y in test_board.cells if cx == x), default=test_board.height)
    for x in range(test_board.width):
        for y in range(column_heights[x], test_board.height):
            if (x, y) not in test_board.cells:
                hole_count +=1
    return hole_count
                

# --- Move Generation ---

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
            
        if rotation_landed:
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
                "board": test_board
            })
                
    return moves

def generate_lookahead_moves(test_board, next_block):
    lookahead_moves = []
    
    initial_simulation_board = test_board.clone()
    
    if initial_simulation_board.falling is not None:
         initial_simulation_board.falling = None 
         
    # FIXED: Use 'next_block' parameter and clone it
    initial_simulation_board.falling = next_block.clone() 

    for rotation in range(4):
        sim_board = initial_simulation_board.clone()
        
        rotation_landed = False
        
        for _ in range(rotation):
            sim_board.rotate(Rotation.Clockwise)
            
            if sim_board.falling is None:
                rotation_landed = True
                break
            
        if rotation_landed:
            continue
            
        if sim_board.falling is None:
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
                "board": final_board
            })
                
    return lookahead_moves

# --- Scoring Functions ---

def lookahead_score(lookahead_moves):
    for move in lookahead_moves:
        test_board = move["board"]
        
        lines_cleared_count = test_board.clean() 
        
        # Calculate Linescore (1=25, 2=100, 3=400, 4=1600)
        if lines_cleared_count == 4: linescore = 1600
        elif lines_cleared_count == 3: linescore = 400
        elif lines_cleared_count == 2: linescore = 100
        elif lines_cleared_count == 1: linescore = 25
        else: linescore = 0
            
        height = max_height(test_board)
        bumps = bumpiness(test_board)
        hole_count = holes(test_board)

        # Apply Heuristic: This is the future score
        move["score"] = lines_weight*linescore - (height_weight* height) - (hole_weight * hole_count) - (bump_weight * bumps)
    
    # FIXED: The function correctly returns the list of scored moves
    return lookahead_moves 


def score_moves(board, block, moves):
    LOOKAHEAD_WEIGHT = 0.5
    next_block = board.next

    for move in moves:
        test_board = move["board"]
        
        # --- A. Immediate Score (0-ply) ---
        lines_cleared_count = test_board.clean() 
        
        # Calculate IMMEDIATE linescore
        if lines_cleared_count == 4: linescore = 1600
        elif lines_cleared_count == 3: linescore = 400
        elif lines_cleared_count == 2: linescore = 100 # Adjusted from 25
        elif lines_cleared_count == 1: linescore = 25 # Adjusted from 0
        else: linescore = 0
            
        height = max_height(test_board)
        bumps = bumpiness(test_board)
        hole_count = holes(test_board)
        
        # Calculate the base score
        score_current = lines_weight*linescore - (height_weight * height) - (hole_weight * hole_count) - (bump_weight * bumps)

        # --- B. Lookahead Integration (1-ply) ---
        if next_block is not None:
            
            lookahead_moves = generate_lookahead_moves(test_board, next_block)
            scored_future_moves = lookahead_score(lookahead_moves)
            
            # FIXED: Max logic to find the best future score (Maximax)
            if scored_future_moves:
                max_future_score = max(m["score"] for m in scored_future_moves)
            else:
                max_future_score = -50000 
                
            # Combine scores
            final_score = score_current + (lookahead_weight * max_future_score)
        
        else:
            final_score = score_current

        move["score"] = final_score
        
    return moves


# --- Player Class ---

class Player:
    def choose_action(self, board):
        if board.falling is None:
            return None

        moves = generate_moves(board, board.falling)
        scored_moves = score_moves(board, board.falling, moves)
        
        if not scored_moves:
             return None
             
        # FIXED: Ensures 'scored_moves' contains dictionaries before finding max
        # You may want to keep the debug check from our previous step temporarily 
        # to ensure no strings sneak into this list, but without comments/extraneous checks:
        
        best_move = max(scored_moves, key=lambda m: m["score"])
        
        actions = []

        # Note: Bomb logic relies on accurately scored moves
        
        if all(move["score"] < -discard_limit for move in scored_moves) and board.discards_remaining > 0:
            return Action.Discard
        
        elif all(move["score"] < -bomb_limit for move in scored_moves) and board.bombs_remaining > 0:
            return Action.Bomb

        for _ in range(best_move["rotation"]):
            actions.append(Rotation.Clockwise)

        x_moves = best_move["x_moves"]
        if x_moves > 0:
            for _ in range(x_moves):
                actions.append(Direction.Right)
        elif x_moves < 0:
            for _ in range(abs(x_moves)):
                actions.append(Direction.Left)

        actions.append(Direction.Drop)
        
        return actions


class RandomPlayer(Player):
    def __init__(self, seed=None):
        self.random = Random(seed)

    def print_board(self, board):
        print("--------")
        for y in range(24):
            s = ""
            for x in range(10):
                if (x,y) in board.cells:
                    s += "#"
                else:
                    s += "."
            print(s, y)
            
    def choose_action(self, board):
        self.print_board(board)
        time.sleep(0.5)
        if self.random.random() > 0.97:
            # 3% chance we'll discard or drop a bomb
            return self.random.choice([
                Action.Discard,
                Action.Bomb,
            ])
        else:
            # 97% chance we'll make a normal move
            return self.random.choice([
                Direction.Left,
                Direction.Right,
                Direction.Down,
                Rotation.Anticlockwise,
                Rotation.Clockwise,
            ])


SelectedPlayer = Player
