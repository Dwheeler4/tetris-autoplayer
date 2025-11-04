from board import Direction, Rotation, Action
from random import Random
import time



def max_height(test_board):
    min_y = min((y for (_, y) in test_board.cells), default=0)
    height = test_board.height - min_y
    return(height)

def holes(test_board):
    

    return

def bumpiness(test_board):
    total = 0
    for x in range(test_board.width - 1):  # avoid out-of-bounds
        thisheight = max((y for (cx, y) in test_board.cells if cx == x), default=0)
        nextheight = max((y for (cx, y) in test_board.cells if cx == x + 1), default=0)
        difference = abs(thisheight - nextheight)
        total += difference
    return total





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



def score_moves(board, block, moves):
    for move in moves:
        test_board = move["board"]
        
        lines_cleared_count = test_board.clean() 
        
        if lines_cleared_count == 1:
            linescore = 0
        elif lines_cleared_count == 2:
            linescore = 25
        elif lines_cleared_count == 3:
            linescore = 400
        elif lines_cleared_count == 4:
            linescore = 1600
        else:
            linescore = 0
            
        height = max_height(test_board)
        bumps = bumpiness(test_board)

        move["score"] =  - 10*height +100*linescore -0.25*bumps
        

    return moves



class Player:
    def choose_action(self, board):
        if board.falling is None:
            return None

        moves = generate_moves(board, board.falling)
        scored_moves = score_moves(board, board.falling, moves)
        
        if not scored_moves:
             return None
             
        best_move = max(scored_moves, key=lambda m: m["score"])
        

        actions = []

        if all(move["score"] < -100 for move in scored_moves) and board.bombs_remaining > 0:
    #
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
