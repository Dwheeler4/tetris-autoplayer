# Tetris Autoplayer

An AI move-selection policy for a Tetris engine supplied as UCL coursework.
**Only `player.py` is my work** — the game engine, wire protocol and
visualisers (`board.py`, `server.py`, `client.py`, `adversary.py`,
`cmdline.py`, `visual*.py`, …) were provided by the course.

The engine is a Tetris variant with two extra actions beyond the usual
moves/rotations: a limited number of **bombs** (clear a region) and
**discards** (skip the current piece).

## The player (`player.py`)

For each falling piece it:

1. **Enumerates every placement** — all four rotations × every horizontal
   offset — by cloning the board and simulating the rotate/shift/drop, then
   de-duplicating by the resulting locked cells.
2. **Scores each resulting board** with a hand-designed evaluation:
   - stack height and bumpiness (sum of adjacent column-height differences)
   - holes (covered empty cells)
   - **well shaping** for Tetris setups: rewards a single deep well,
     penalises having more than one, extra bonus for a well on an edge column
   - per-line-clear-count terms tuned to **prefer clearing four rows at once**
     and avoid burning singles/doubles/triples
3. **Looks one move ahead** — a 2-ply beam search: keep the best 10 first
   moves, expand each, score `immediate + 0.6 * best_reply`.
4. **Uses the special actions on thresholds** — bomb once the stack rises
   within a few rows of the top; discard an S/Z piece while a Tetris well is
   open and the board is still low (S/Z pieces wreck a flat stack).

The evaluation weights were tuned by hill-climbing self-play.

## Running it

```
python cmdline.py     # curses UI, autoplay
python server.py       # wire-protocol mode, driven by an external adversary
```

## Results

Headless self-play against `RandomAdversary`, 400-piece limit per game, seeds 1–8:

| metric | value |
|---|---|
| median score | ~31,800 |
| mean score | ~28,800 (one early top-out drags this down) |
| games that reached the 400-piece limit without topping out | 6 / 8 |

Small sample (8 seeds); the ~2 s/move pure-Python placement search makes large
runs slow.

## Limitations / notes

- The evaluation includes a non-linear "danger" height term, but at the tuned
  `danger_threshold` it never activates — the linear height penalty alone was
  what the hill-climber settled on.
- Lookahead is 2-ply and uncached; deeper search would help, but the
  pure-Python placement enumeration is the bottleneck.
- The bomb/discard policies are hand-tuned thresholds, separate from the
  optimised weight set.
- Weight tuning was single-start hill-climbing (no restarts/population), so it
  can settle in a local optimum.
