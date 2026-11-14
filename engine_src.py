# Chess engine for make.fun tiny-chess-01.
# Adapted from sunfish by Thomas Ahle (GPL-3.0-only): the design follows
# sunfish (piece-square-table evaluation, negamax search) in original code,
# with an original make.fun env-HTTP driver. License: GPL-3.0-only.
import json, os, urllib.request

BUDGET = 75000
INF = 1000000
MATE = 100000

# Piece-square tables, value included, from White's side, rank 8 first.
MG = {
'P': (100,100,100,100,100,100,100,100, 150,150,150,150,150,150,150,150,
      110,110,120,130,130,120,110,110, 105,105,110,125,125,110,105,105,
      100,100,100,120,120,100,100,100, 105,95,90,100,100,90,95,105,
      105,110,110,80,80,110,110,105, 100,100,100,100,100,100,100,100),
'N': (270,280,290,290,290,290,280,270, 280,300,320,320,320,320,300,280,
      290,320,330,335,335,330,320,290, 290,325,335,340,340,335,325,290,
      290,320,335,340,340,335,320,290, 290,325,330,335,335,330,325,290,
      280,300,320,325,325,320,300,280, 270,280,290,290,290,290,280,270),
'B': (310,320,320,320,320,320,320,310, 320,330,330,330,330,330,330,320,
      320,330,335,340,340,335,330,320, 320,335,335,340,340,335,335,320,
      320,330,340,340,340,340,330,320, 320,340,340,340,340,340,340,320,
      320,335,330,330,330,330,335,320, 310,320,320,320,320,320,320,310),
'R': (500,500,500,500,500,500,500,500, 505,510,510,510,510,510,510,505,
      495,500,500,500,500,500,500,495, 495,500,500,500,500,500,500,495,
      495,500,500,500,500,500,500,495, 495,500,500,500,500,500,500,495,
      495,500,500,500,500,500,500,495, 500,500,500,505,505,500,500,500),
'Q': (880,890,890,895,895,890,890,880, 890,900,900,900,900,900,900,890,
      890,900,905,905,905,905,900,890, 895,900,905,905,905,905,900,895,
      900,900,905,905,905,905,900,895, 890,905,905,905,905,905,900,890,
      890,900,905,900,900,900,900,890, 880,890,890,895,895,890,890,880),
'K': (-30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
      -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
      -20,-30,-30,-40,-40,-30,-30,-20, -10,-20,-20,-20,-20,-20,-20,-10,
      20,20,0,0,0,0,20,20, 20,30,10,0,0,10,30,20),
}
EG = dict(MG)
EG['K'] = (-50,-40,-30,-20,-20,-30,-40,-50, -30,-20,0,0,0,0,-20,-30,
           -30,0,10,15,15,10,0,-30, -30,5,15,20,20,15,5,-30,
           -30,0,15,20,20,15,0,-30, -30,5,10,15,15,10,5,-30,
           -30,0,5,10,10,5,0,-30, -50,-30,-30,-40,-40,-30,-30,-50)
PH = {'P': 0, 'N': 1, 'B': 1, 'R': 2, 'Q': 4, 'K': 0}
VV = {'P': 100, 'N': 300, 'B': 320, 'R': 500, 'Q': 900, 'K': 0}
KNO = ((1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1))
KGO = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
DIAG = ((1, 1), (1, -1), (-1, 1), (-1, -1))
STRA = ((1, 0), (-1, 0), (0, 1), (0, -1))
ROOKHOME = {56: 'Q', 63: 'K', 0: 'q', 7: 'k'}
CASTROOK = {62: (63, 61), 58: (56, 59), 6: (7, 5), 2: (0, 3)}

B = ['.'] * 64
TURN = True
CAST = ''
EP = -1
SM = 0
SE = 0
PHASE = 0
WK = 60
BK = 4
nodes = 0


class TO(Exception):
    pass


def contrib(p, s):
    i = s if p.isupper() else s ^ 56
    u = p.upper()
    if p.isupper():
        return MG[u][i], EG[u][i]
    return -MG[u][i], -EG[u][i]


def set_fen(fen):
    global B, TURN, CAST, EP, SM, SE, PHASE, WK, BK
    parts = fen.split()
    B = ['.'] * 64
    i = 0
    for ch in parts[0]:
        if ch == '/':
            continue
        if ch.isdigit():
            i += int(ch)
        else:
            B[i] = ch
            i += 1
    TURN = parts[1] == 'w'
    CAST = '' if parts[2] == '-' else parts[2]
    if parts[3] == '-':
        EP = -1
    else:
        EP = (8 - int(parts[3][1])) * 8 + (ord(parts[3][0]) - 97)
    SM = 0
    SE = 0
    PHASE = 0
    for s in range(64):
        p = B[s]
        if p == '.':
            continue
        a, b = contrib(p, s)
        SM += a
        SE += b
        PHASE += PH[p.upper()]
        if p == 'K':
            WK = s
        elif p == 'k':
            BK = s


def attacked(s, byw):
    f = s & 7
    r = s >> 3
    if byw:
        if r < 7:
            if f > 0 and B[s + 7] == 'P':
                return True
            if f < 7 and B[s + 9] == 'P':
                return True
    else:
        if r > 0:
            if f > 0 and B[s - 9] == 'p':
                return True
            if f < 7 and B[s - 7] == 'p':
                return True
    n = 'N' if byw else 'n'
    for df, dr in KNO:
        nf, nr = f + df, r + dr
        if 0 <= nf < 8 and 0 <= nr < 8 and B[nr * 8 + nf] == n:
            return True
    k = 'K' if byw else 'k'
    for df, dr in KGO:
        nf, nr = f + df, r + dr
        if 0 <= nf < 8 and 0 <= nr < 8 and B[nr * 8 + nf] == k:
            return True
    bp = 'B' if byw else 'b'
    qp = 'Q' if byw else 'q'
    for df, dr in DIAG:
        nf, nr = f + df, r + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            q = B[nr * 8 + nf]
            if q != '.':
                if q == bp or q == qp:
                    return True
                break
            nf += df
            nr += dr
    rp = 'R' if byw else 'r'
    for df, dr in STRA:
        nf, nr = f + df, r + dr
        while 0 <= nf < 8 and 0 <= nr < 8:
            q = B[nr * 8 + nf]
            if q != '.':
                if q == rp or q == qp:
                    return True
                break
            nf += df
            nr += dr
    return False


def gen(cap=False):
    ms = []
    w = TURN
    for s in range(64):
        p = B[s]
        if p == '.' or p.isupper() != w:
            continue
        f = s & 7
        r = s >> 3
        u = p.upper()
        if u == 'P':
            d = -8 if w else 8
            start = 6 if w else 1
            last = 1 if w else 6
            t = s + d
            if B[t] == '.':
                if r == last:
                    for pr in (4, 3, 2, 1):
                        ms.append(s | t << 6 | pr << 12)
                elif not cap:
                    ms.append(s | t << 6)
                    if r == start and B[s + 2 * d] == '.':
                        ms.append(s | (s + 2 * d) << 6)
            for df in (-1, 1):
                if 0 <= f + df < 8:
                    t = s + d + df
                    q = B[t]
                    if (q != '.' and q.isupper() != w) or t == EP:
                        if r == last:
                            for pr in (4, 3, 2, 1):
                                ms.append(s | t << 6 | pr << 12)
                        else:
                            ms.append(s | t << 6)
        elif u == 'N' or u == 'K':
            for df, dr in (KNO if u == 'N' else KGO):
                nf, nr = f + df, r + dr
                if 0 <= nf < 8 and 0 <= nr < 8:
                    t = nr * 8 + nf
                    q = B[t]
                    if q == '.':
                        if not cap:
                            ms.append(s | t << 6)
                    elif q.isupper() != w:
                        ms.append(s | t << 6)
            if u == 'K' and not cap:
                if w and s == 60:
                    if ('K' in CAST and B[61] == '.' and B[62] == '.'
                            and not attacked(60, False) and not attacked(61, False)
                            and not attacked(62, False)):
                        ms.append(60 | 62 << 6)
                    if ('Q' in CAST and B[59] == '.' and B[58] == '.' and B[57] == '.'
                            and not attacked(60, False) and not attacked(59, False)
                            and not attacked(58, False)):
                        ms.append(60 | 58 << 6)
                elif not w and s == 4:
                    if ('k' in CAST and B[5] == '.' and B[6] == '.'
                            and not attacked(4, True) and not attacked(5, True)
                            and not attacked(6, True)):
                        ms.append(4 | 6 << 6)
                    if ('q' in CAST and B[3] == '.' and B[2] == '.' and B[1] == '.'
                            and not attacked(4, True) and not attacked(3, True)
                            and not attacked(2, True)):
                        ms.append(4 | 2 << 6)
        else:
            dirs = DIAG if u == 'B' else (STRA if u == 'R' else DIAG + STRA)
            for df, dr in dirs:
                nf, nr = f + df, r + dr
                while 0 <= nf < 8 and 0 <= nr < 8:
                    t = nr * 8 + nf
                    q = B[t]
                    if q == '.':
                        if not cap:
                            ms.append(s | t << 6)
                    else:
                        if q.isupper() != w:
                            ms.append(s | t << 6)
                        break
                    nf += df
                    nr += dr
    return ms


def make(m):
    global TURN, CAST, EP, SM, SE, PHASE, WK, BK
    frm = m & 63
    to = (m >> 6) & 63
    pr = (m >> 12) & 7
    p = B[frm]
    w = p.isupper()
    cap = B[to]
    undo = (m, p, cap, CAST, EP, SM, SE, PHASE, WK, BK)
    a, b = contrib(p, frm)
    SM -= a
    SE -= b
    if cap != '.':
        a, b = contrib(cap, to)
        SM -= a
        SE -= b
        PHASE -= PH[cap.upper()]
    epsq = -1
    if p.upper() == 'P' and to == EP and cap == '.' and (frm & 7) != (to & 7):
        epsq = to + 8 if w else to - 8
        cp = B[epsq]
        a, b = contrib(cp, epsq)
        SM -= a
        SE -= b
        B[epsq] = '.'
    if pr:
        np = 'NBRQ'[pr - 1]
        if not w:
            np = np.lower()
    else:
        np = p
    B[to] = np
    B[frm] = '.'
    a, b = contrib(np, to)
    SM += a
    SE += b
    if pr:
        PHASE += PH[np.upper()]
    if p.upper() == 'K' and abs(to - frm) == 2:
        rf, rt = CASTROOK[to]
        rp = B[rf]
        a, b = contrib(rp, rf)
        SM -= a
        SE -= b
        B[rt] = rp
        B[rf] = '.'
        a, b = contrib(rp, rt)
        SM += a
        SE += b
    if p == 'K':
        WK = to
    elif p == 'k':
        BK = to
    rem = ''
    if p == 'K':
        rem = 'KQ'
    elif p == 'k':
        rem = 'kq'
    for sq in (frm, to):
        if sq in ROOKHOME:
            rem += ROOKHOME[sq]
    if rem:
        CAST = ''.join(ch for ch in CAST if ch not in rem)
    if p.upper() == 'P' and abs(to - frm) == 16:
        EP = (frm + to) // 2
    else:
        EP = -1
    TURN = not TURN
    return undo


def unmake(undo):
    global TURN, CAST, EP, SM, SE, PHASE, WK, BK
    m, p, cap, CAST, EP, SM, SE, PHASE, WK, BK = undo
    frm = m & 63
    to = (m >> 6) & 63
    TURN = not TURN
    if p.upper() == 'K' and abs(to - frm) == 2:
        rf, rt = CASTROOK[to]
        B[rf] = B[rt]
        B[rt] = '.'
    B[frm] = p
    B[to] = cap
    if p.upper() == 'P' and to == EP and cap == '.' and (frm & 7) != (to & 7):
        epsq = to + 8 if p.isupper() else to - 8
        B[epsq] = 'p' if p.isupper() else 'P'
        B[to] = '.'


def legal_moves():
    w = TURN
    out = []
    for m in gen():
        undo = make(m)
        if not attacked(WK if w else BK, not w):
            out.append(m)
        unmake(undo)
    return out


def evaluate():
    v = SM * PHASE + SE * (24 - PHASE)
    v = v // 24 if v >= 0 else -((-v) // 24)
    return v if TURN else -v


def order_key(m):
    frm = m & 63
    to = (m >> 6) & 63
    pr = (m >> 12) & 7
    sc = 0
    q = B[to]
    if q != '.':
        sc = 1000000 + VV[q.upper()] * 10 - VV[B[frm].upper()] // 10
    elif B[frm].upper() == 'P' and to == EP:
        sc = 1000000 + 990
    if pr:
        sc += 900000 + pr * 1000
    return sc


def ordered(ms, first=-1):
    return sorted(ms, key=lambda m: (m == first, order_key(m)), reverse=True)


def qs(alpha, beta, ply):
    global nodes
    nodes += 1
    if nodes > BUDGET:
        raise TO()
    if ply >= 48:
        return evaluate()
    w = TURN
    if attacked(WK if w else BK, not w):
        best = -INF
        any = False
        for m in ordered(gen()):
            undo = make(m)
            if attacked(WK if w else BK, not w):
                unmake(undo)
                continue
            any = True
            sc = -qs(-beta, -alpha, ply + 1)
            unmake(undo)
            if sc > best:
                best = sc
            if sc > alpha:
                alpha = sc
            if alpha >= beta:
                break
        if not any:
            return -MATE + ply
        return best
    stand = evaluate()
    if stand >= beta:
        return beta
    if stand > alpha:
        alpha = stand
    for m in ordered(gen(True)):
        undo = make(m)
        if attacked(WK if w else BK, not w):
            unmake(undo)
            continue
        sc = -qs(-beta, -alpha, ply + 1)
        unmake(undo)
        if sc >= beta:
            return beta
        if sc > alpha:
            alpha = sc
    return alpha


def search(d, alpha, beta, ply):
    global nodes
    nodes += 1
    if nodes > BUDGET:
        raise TO()
    if d <= 0:
        return qs(alpha, beta, ply)
    w = TURN
    if attacked(WK if w else BK, not w):
        d += 1
    best = -INF
    any = False
    for m in ordered(gen()):
        undo = make(m)
        if attacked(WK if w else BK, not w):
            unmake(undo)
            continue
        any = True
        sc = -search(d - 1, -beta, -alpha, ply + 1)
        unmake(undo)
        if sc > best:
            best = sc
        if sc > alpha:
            alpha = sc
        if alpha >= beta:
            break
    if not any:
        if attacked(WK if w else BK, not w):
            return -MATE + ply
        return 0
    return best


def pick():
    global nodes
    nodes = 0
    ms = legal_moves()
    best = ms[0]
    d = 1
    while d <= 80:
        try:
            cur = best
            a = -INF
            first = True
            for m in ordered(ms, best):
                undo = make(m)
                if first:
                    sc = -search(d - 1, -INF, INF, 1)
                    first = False
                else:
                    sc = -search(d - 1, -INF, -a, 1)
                unmake(undo)
                if sc > a:
                    a = sc
                    cur = m
            best = cur
        except TO:
            break
        d += 1
    return best


def uci(m):
    frm = m & 63
    to = (m >> 6) & 63
    pr = (m >> 12) & 7
    s = 'abcdefgh'[frm & 7] + str(8 - (frm >> 3)) + 'abcdefgh'[to & 7] + str(8 - (to >> 3))
    if pr:
        s += 'nbrq'[pr - 1]
    return s


def choose(fen, legal):
    set_fen(fen)
    m = pick()
    u = uci(m)
    if u in legal:
        return u
    want = set(legal)
    for m in ordered(legal_moves()):
        u = uci(m)
        if u in want:
            return u
    return legal[0]


def post(path, body):
    req = urllib.request.Request(
        URL + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req) as res:
        return json.load(res)


if os.environ.get("MAKEFUN_ENV_URL"):
    URL = os.environ["MAKEFUN_ENV_URL"]
    while True:
        g = post("/game", {})
        if g["status"] == "done":
            break
        while g["status"] == "your_move":
            g = post("/move", {"game": g["game"], "move": choose(g["fen"], g["legal_moves"])})
