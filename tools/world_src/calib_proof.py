import sys, json
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))           # tools/world_src
_os.chdir(_os.path.dirname(_os.path.dirname(_HERE)))           # run from the repo root whatever the cwd
sys.path.insert(0, '.'); sys.path.insert(0, _HERE)
from PIL import Image, ImageDraw, ImageFont
from human import draw_human
from calib_data import CAL, ppi, PROOF_AT
from modules import pubcast_world as W, pubcast_world_placement as P
S = _os.environ.get('WORLD_PROOF_DIR', _os.path.join(_HERE, 'proof_sheets')); _os.makedirs(S, exist_ok=True)
F = lambda n, b=False: ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if b else ''), n)
data = P.load()
CH = [("Purfluous 6'2\"", 74, (190, 120, 255), 'm'), ("RePete 5'10\"", 70, (90, 170, 255), 'm'), ("Pete 5'8\"", 68, (80, 230, 190), 'f')]
IMG = {P.view_key(r.room_id, v.view_id): v.image for r in W.WORLD.values() for v in r.views}

def wrap(d, text, font, width):
    out, line = [], ''
    for w in text.split():
        t = (line + ' ' + w).strip()
        if d.textlength(t, font=font) > width and line: out.append(line); line = w
        else: line = t
    if line: out.append(line)
    return out

def render(key, rows=None, xs=None):
    c = CAL[key]; v = data['views'][key]
    im = Image.open('static/world/rooms/' + IMG[key]).convert('RGBA'); w, h = im.size
    floors = [[tuple(p) for p in z['points']] for z in v['zones'] if z['kind'] in ('floor', 'ramp', 'stairs')]
    ys = [p[1] for f in floors for p in f]; y0, y1 = min(ys), max(ys)
    rows = rows or [y0 + (y1 - y0) * f for f in (0.12, 0.45, 0.85)]
    d = ImageDraw.Draw(im)
    if c['kind'] == 'camera':
        for x in range(0, w, 18): d.line([(x, c['h']), (x + 9, c['h'])], fill=(255, 235, 0, 255), width=2)
    for i, (name, inch, col, sx) in enumerate(CH):
        y = rows[i]
        xsr = [x for x in range(0, w, 6) if any(P.point_in_polygon((x, y), f) for f in floors)]
        if not xsr: continue
        x = xs[i] if xs else xsr[0] + (xsr[-1] - xsr[0]) * (0.18, 0.5, 0.82)[i]
        p = ppi(key, y); hp = inch * p
        draw_human(im, x, y, hp, col, sx)
        d.text((x - 50, y + 6), "%s %.0f px" % (name, hp), font=F(15, True), fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    if c['kind'] == 'camera':
        pass
        d.text((8, c['h'] + 4), "horizon row %d" % c['h'], font=F(15, True), fill=(255, 235, 0, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    if c.get('alt'):
        a = c['alt']; (ay0, ap0), (ay1, ap1) = a['samples']
        aq = lambda yy: ap0 + (yy - ay0) * (ap1 - ap0) / (ay1 - ay0)
        yy = a['row']; x0, x1 = a['xs']
        hp = 68 * ppi(key, yy); draw_human(im, x0, yy, hp, CH[2][2], 'f')
        d.text((x0 - 50, yy + 6), "proposed %.0f px" % hp, font=F(15, True), fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        ha = 68 * aq(yy); draw_human(im, x1, yy, ha, (170, 170, 170), 'f')
        d.text((x1 + a.get('lab_dx', -10), yy + 24), "grey: %s %.0f px" % (a['label'], ha), font=F(15, True), fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    # caption strip under the picture
    fb = F(16, True); ft = F(14)
    lines = [("%s   [%s confidence]   %s" % (key, c['conf'].upper(), ("horizon row %d, eye height %d in" % (c['h'], c['E'])) if c['kind'] == 'camera' else "two samples, no camera fitted"), fb, (255, 235, 150))]
    for t in wrap(d, c['why'], ft, w - 24): lines.append((t, ft, (255, 255, 255)))
    lines.append(("Measured: " + "; ".join(c['refs']), ft, (190, 220, 255)))
    ext = []
    for t, f, col in lines:
        for u in wrap(d, t, f, w - 24): ext.append((u, f, col))
    strip = Image.new('RGBA', (w, 14 + 22 * len(ext)), (14, 14, 22, 255)); sd = ImageDraw.Draw(strip)
    for i, (t, f, col) in enumerate(ext): sd.text((12, 8 + 22 * i), t, font=f, fill=col + (255,))
    out = Image.new('RGB', (w, h + strip.height)); out.paste(im.convert('RGB'), (0, 0)); out.paste(strip.convert('RGB'), (0, h))
    name = key.replace('/', '__')
    out.save('%s/CAL_%s.jpg' % (S, name), quality=88); print(name, out.size, [round(r) for r in rows])

if __name__ == '__main__':
    for k in sys.argv[1:]:
        r, x = PROOF_AT.get(k, (None, None)); render(k, rows=r, xs=x)
