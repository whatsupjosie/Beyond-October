"""vp.py <image> [n_vps] -> vanishing points of the receding horizontal lines (RANSAC over Hough segments)."""
import sys, math, random
import cv2, numpy as np

def segments(path, minfrac=25):
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE); H, W = g.shape
    g = cv2.GaussianBlur(g, (3, 3), 0)
    e = cv2.Canny(g, 40, 120)
    ls = cv2.HoughLinesP(e, 1, np.pi / 720, threshold=60, minLineLength=max(40, W // minfrac), maxLineGap=6)
    out = []
    if ls is None: return out, W, H
    for x1, y1, x2, y2 in np.asarray(ls).reshape(-1, 4):
        a = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
        a = a - 180 if a > 90 else a            # -90..90
        if 2.5 <= abs(a) <= 55:                 # receding horizontals only (not verticals, not dead level)
            out.append((x1, y1, x2, y2, math.hypot(x2 - x1, y2 - y1)))
    return out, W, H

def intersect(s, t):
    x1, y1, x2, y2, _ = s; x3, y3, x4, y4, _ = t
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9: return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / d
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / d
    return px, py

def consistent(s, vp, tol_deg=1.2):
    x1, y1, x2, y2, _ = s; mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    a1 = math.atan2(y2 - y1, x2 - x1); a2 = math.atan2(vp[1] - my, vp[0] - mx)
    d = abs((a1 - a2 + math.pi / 2) % math.pi - math.pi / 2)
    return math.degrees(d) < tol_deg

def find(path, n=3, iters=6000, seed=1, minfrac=25):
    segs, W, H = segments(path, minfrac); rnd = random.Random(seed); found = []
    pool = list(segs)
    for _ in range(n):
        if len(pool) < 6: break
        best = (0, None)
        for _ in range(iters):
            s, t = rnd.sample(pool, 2)
            vp = intersect(s, t)
            if vp is None or abs(vp[0]) > 6 * W or abs(vp[1]) > 3 * H: continue
            score = sum(u[4] for u in pool if consistent(u, vp))
            if score > best[0]: best = (score, vp)
        if best[1] is None: break
        sc, vp = best
        inl = [u for u in pool if consistent(u, vp)]
        # refine: weighted least squares intersection of inlier lines
        A, b = [], []
        for x1, y1, x2, y2, L in inl:
            nx, ny = -(y2 - y1), (x2 - x1); nn = math.hypot(nx, ny); nx, ny = nx / nn, ny / nn
            A.append([nx * L, ny * L]); b.append((nx * x1 + ny * y1) * L)
        sol = np.linalg.lstsq(np.array(A), np.array(b), rcond=None)[0]
        found.append(dict(vp=(round(float(sol[0])), round(float(sol[1]))), length=round(sc), n=len(inl)))
        pool = [u for u in pool if not consistent(u, vp)]
    return found, W, H, len(segs)

if __name__ == '__main__':
    f, W, H, n = find(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3, minfrac=int(sys.argv[3]) if len(sys.argv) > 3 else 25)
    print(sys.argv[1].split('/')[-1], '%dx%d' % (W, H), 'segments', n)
    for v in f: print('  VP', v['vp'], 'inlier length', v['length'], 'segments', v['n'])
