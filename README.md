# tiny-chess-01 entry: sunfish fork with a make.fun driver

A fork of **sunfish** by Thomas Ahle and contributors — specifically
`nnue_4k/pst_entry.py` at commit
e396948acbd80cdcbad3dccfb07e878fba9df8f4 of
https://github.com/thomasahle/sunfish — licensed **GPL-3.0-only**
(see LICENSE). The house baseline of this competition is that same
engine; this entry keeps its search core (MTD-bi with quiescence,
null-move pruning, internal iterative deepening, late-move reduction,
transposition tables) and its piece-square evaluation unchanged.

What this entry changes, all in the driver layer:

- the UCI loop and wall-clock time management are replaced by an
  original driver for the make.fun env (POST /game, POST /move at
  MAKEFUN_ENV_URL), the way the kit's starter does it;
- move choice uses a **fixed node budget** — no clock anywhere — so a
  trial replays move for move;
- the rendered search move is checked against the env's legal_moves,
  with a first-legal-capture fallback;
- the piece-square tables ride in the source as a packed int8/base85
  blob (the values are upstream's, verbatim).

## Layout

- `main.py` — the entry: an lzma payload plus a decompress-and-exec
  stub. It is all the sandbox runs.
- `engine.py` — the readable source main.py is packed from (kept in
  the repository history; the submitted tree omits it for size).
- `build.py` — the packer: AST-minifies engine.py (comments dropped,
  identifiers renamed), lzma-compresses, base85-encodes. The build is
  verified behaviour-preserving against upstream on test positions
  (identical moves and node counts).

To audit main.py:

```python
import lzma, base64
src = lzma.decompress(base64.b85decode(<the b85 literal in main.py>))
```
