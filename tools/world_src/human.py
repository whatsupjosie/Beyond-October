"""Anatomically proportioned standing silhouette, drawn from landmark heights as fractions of stature."""
from PIL import Image, ImageDraw, ImageFilter

# fractions of stature measured from the floor (standard anthropometric landmarks)
def landmarks(sex):
    f = sex == 'f'
    return dict(
        head_top=1.0, chin=0.870, neck_base=0.835, shoulder=0.818, armpit=0.735, waist=0.625, navel=0.600,
        hip=0.525, crotch=0.470, knee=0.285, ankle=0.040,
        elbow=0.630, wrist=0.470, fingertip=0.385,
        head_w=0.098 if not f else 0.092, neck_w=0.046 if not f else 0.040,
        shoulder_w=0.258 if not f else 0.228, chest_w=0.205 if not f else 0.185,
        waist_w=0.168 if not f else 0.150, hip_w=0.188 if not f else 0.205,
        thigh_w=0.092 if not f else 0.098, knee_w=0.058, calf_w=0.062, ankle_w=0.036,
        upper_arm_w=0.058 if not f else 0.048, elbow_w=0.044 if not f else 0.038, wrist_w=0.030, hand_w=0.038,
        foot_len=0.150)

def draw_human(base, x, y, height_px, color, sex='m', alpha=235, outline=(255, 255, 255, 230), ss=4):
    """Paint a standing figure with feet centred at (x, y) onto RGBA image `base` (in place)."""
    L = landmarks(sex); H = height_px
    pad = int(H * 0.2)
    w = int(H * 0.5) + 2 * pad; h = int(H) + 2 * pad
    big = Image.new('RGBA', (w * ss, h * ss), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
    cx = w * ss / 2; floor = (pad + H) * ss; S = H * ss
    P = lambda dx, frac: (cx + dx * S, floor - frac * S)
    fill = color + (alpha,)
    def poly(pts): d.polygon(pts, fill=fill)
    # legs (slight stance gap), feet
    gap = 0.012
    for sgn in (-1, 1):
        t = [P(sgn * gap + sgn * L['thigh_w'] / 2 * 0.98, L['crotch'] + 0.03), P(sgn * gap - sgn * 0.0, L['crotch']),
             P(sgn * (gap + 0.004) + sgn * -L['knee_w'] / 2 * 0 , L['knee']),
             P(sgn * (gap + 0.010), L['ankle']), P(sgn * (gap + 0.010) + sgn * L['ankle_w'], L['ankle']),
             P(sgn * (gap + 0.010) + sgn * (L['calf_w'] * 0.95), L['knee'] - 0.10),
             P(sgn * (gap + L['knee_w'] * 0.95), L['knee']), P(sgn * (L['thigh_w'] + gap), L['crotch'] + 0.02)]
        poly(t)
        foot = [P(sgn * (gap + 0.008), L['ankle'] + 0.004), P(sgn * (gap + 0.010 + L['ankle_w']), L['ankle'] + 0.004),
                P(sgn * (gap + 0.010 + L['foot_len'] * 0.55), 0.012), P(sgn * (gap + 0.010 + L['foot_len'] * 0.55), 0.0),
                P(sgn * (gap + 0.004), 0.0)]
        poly(foot)
    # torso
    torso = [P(-L['shoulder_w'] / 2 * 0.86, L['shoulder']), P(-L['neck_w'] / 2, L['neck_base']), P(L['neck_w'] / 2, L['neck_base']),
             P(L['shoulder_w'] / 2 * 0.86, L['shoulder']), P(L['chest_w'] / 2, L['armpit']), P(L['waist_w'] / 2, L['waist']),
             P(L['hip_w'] / 2, L['hip']), P(L['hip_w'] / 2 * 0.95, L['crotch'] - 0.01), P(-L['hip_w'] / 2 * 0.95, L['crotch'] - 0.01),
             P(-L['hip_w'] / 2, L['hip']), P(-L['waist_w'] / 2, L['waist']), P(-L['chest_w'] / 2, L['armpit'])]
    poly(torso)
    # neck and head
    d.rectangle([*P(-L['neck_w'] / 2, L['chin'] + 0.01), *P(L['neck_w'] / 2, L['neck_base'] - 0.004)], fill=fill)
    hh = (L['head_top'] - L['chin'])
    d.ellipse([*P(-L['head_w'] / 2 * 1.0, L['head_top']), *P(L['head_w'] / 2 * 1.0, L['chin'] - 0.004)], fill=fill)
    # arms hanging, hands reach mid-thigh; slightly away from the body
    for sgn in (-1, 1):
        sx = sgn * L['shoulder_w'] / 2 * 0.93
        arm = [P(sx - sgn * 0.004, L['shoulder'] + 0.004), P(sx + sgn * L['upper_arm_w'], L['shoulder'] - 0.012),
               P(sgn * (L['shoulder_w'] / 2 + 0.040) + sgn * L['elbow_w'] / 2, L['elbow']),
               P(sgn * (L['shoulder_w'] / 2 + 0.056) + sgn * L['wrist_w'] / 2, L['wrist']),
               P(sgn * (L['shoulder_w'] / 2 + 0.060) + sgn * L['hand_w'] / 2, L['fingertip'] + 0.01),
               P(sgn * (L['shoulder_w'] / 2 + 0.058) - sgn * L['hand_w'] / 2, L['fingertip']),
               P(sgn * (L['shoulder_w'] / 2 + 0.050) - sgn * L['wrist_w'] / 2 , L['wrist']),
               P(sgn * (L['shoulder_w'] / 2 + 0.030) - sgn * L['elbow_w'] / 2 , L['elbow']),
               P(sx - sgn * L['upper_arm_w'] * 0.35, L['armpit'] + 0.02)]
        poly(arm)
    # one clean outline around the whole silhouette (no seams where limbs overlap the torso)
    from PIL import ImageChops
    a = big.split()[3].point(lambda v: 255 if v > 40 else 0)
    ring = ImageChops.subtract(a.filter(ImageFilter.MaxFilter(ss * 2 + 1)), a)
    edge = Image.new('RGBA', big.size, outline[:3] + (outline[3],)); edge.putalpha(ring)
    big.alpha_composite(edge)
    small = big.resize((w, h), Image.LANCZOS)
    # soft contact shadow
    sh = Image.new('RGBA', base.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    sw = H * 0.17; sd.ellipse([x - sw, y - sw * 0.22, x + sw, y + sw * 0.22], fill=(0, 0, 0, 120))
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(max(1, H * 0.012))))
    base.alpha_composite(small, (int(x - w / 2), int(y - pad - H)))
    return base
