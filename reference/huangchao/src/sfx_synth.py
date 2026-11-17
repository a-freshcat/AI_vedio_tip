"""程序化古战场音效合成库（纯 numpy/scipy，无外部素材、无版权问题）。

所有函数返回 float64 数组：单声道 shape=(n,)，立体声 shape=(2, n)，采样率 SR=48000。
每个函数都接收 numpy Generator，固定种子即可保证每次渲染完全一致。
"""
import numpy as np
from scipy import signal

SR = 48000


# ----------------------------------------------------------------------------- 基础工具
def _t(dur):
    return np.arange(int(round(dur * SR))) / SR


def filt(x, kind, f, order=2):
    nyq = SR / 2.0
    if kind == "band":
        wn = [max(f[0], 15.0) / nyq, min(f[1], nyq * 0.97) / nyq]
        btype = "bandpass"
    else:
        wn = min(max(f, 15.0), nyq * 0.97) / nyq
        btype = {"low": "lowpass", "high": "highpass"}[kind]
    sos = signal.butter(order, wn, btype=btype, output="sos")
    return signal.sosfilt(sos, x, axis=-1)


def norm(x, peak=1.0):
    m = float(np.max(np.abs(x))) if x.size else 0.0
    return x * (peak / m) if m > 1e-12 else x


def colored_noise(n, rng, power=1.0):
    """power=0 白噪, 1 粉噪, 2 褐噪。"""
    X = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n)
    f[0] = f[1] if n > 1 else 1.0
    X /= f ** (power / 2.0)
    return norm(np.fft.irfft(X, n))


def smooth_random(n, rng, rate_hz=0.5):
    """缓变随机包络 (0..1)。"""
    x = colored_noise(n, rng, 0.0)
    x = filt(x, "low", rate_hz, order=2)
    x = norm(x)
    return 0.5 + 0.5 * x


def pan_stereo(mono, pan):
    """等功率声像，pan ∈ [-1, 1]。"""
    a = (pan + 1.0) * np.pi / 4.0
    return np.vstack([mono * np.cos(a), mono * np.sin(a)])


def place(buf, sig, t0, gain=1.0, pan=0.0):
    """把单声道/立体声片段混入立体声总线 buf (2, N)。"""
    if sig.ndim == 1:
        sig = pan_stereo(sig, pan)
    i0 = int(round(t0 * SR))
    if i0 >= buf.shape[1]:
        return
    s0 = 0
    if i0 < 0:
        s0 = -i0
        i0 = 0
    n = min(sig.shape[1] - s0, buf.shape[1] - i0)
    if n > 0:
        buf[:, i0:i0 + n] += gain * sig[:, s0:s0 + n]


def reverb(x, rng, rt60=1.4, wet=0.25, predelay=0.018, tone=5000.0):
    """指数衰减的去相关噪声脉冲响应卷积混响（立体声输入）。"""
    n_ir = int(rt60 * SR)
    t = np.arange(n_ir) / SR
    decay = np.exp(-6.9 * t / rt60)
    pre = int(predelay * SR)
    out = np.zeros_like(x)
    for ch in range(2):
        ir = rng.standard_normal(n_ir) * decay
        ir = filt(ir, "low", tone, order=1)
        ir = np.concatenate([np.zeros(pre), ir])
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-12
        out[ch] = signal.fftconvolve(x[ch], ir)[: x.shape[1]]
    return x * (1.0 - wet) + out * wet * 1.6


def distance(x, amount):
    """amount 0=近 1=远：压高频、降电平。支持随时间变化的 amount 数组。"""
    far = filt(x, "low", 900.0, order=2)
    a = np.asarray(amount)
    return (x * (1.0 - a) + far * a) * (1.0 - 0.55 * a)


def fade(x, fin=0.0, fout=0.0):
    n = x.shape[-1]
    env = np.ones(n)
    ni, no = int(fin * SR), int(fout * SR)
    if ni > 0:
        env[:ni] = np.linspace(0, 1, ni) ** 1.5
    if no > 0:
        env[-no:] *= np.linspace(1, 0, no) ** 1.5
    return x * env


def envelope_points(n, pts):
    """pts = [(sec, gain), ...] 线性插值成包络。"""
    t = np.arange(n) / SR
    xs, ys = zip(*pts)
    return np.interp(t, xs, ys)


# ----------------------------------------------------------------------------- 打击/金属
def war_drum(rng, f0=58.0, dur=1.3, bright=1.0):
    """战鼓：音高下滑的鼓腔 + 鼓皮噪声 + 鼓槌击点。"""
    t = _t(dur)
    f0 = f0 * rng.uniform(0.95, 1.05)
    f = f0 * (1.0 + 0.55 * np.exp(-t / 0.035))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.38)
    f2 = 1.59 * f0 * (1.0 + 0.4 * np.exp(-t / 0.03))
    body += 0.35 * np.sin(2 * np.pi * np.cumsum(f2) / SR) * np.exp(-t / 0.16)
    skin = filt(rng.standard_normal(t.size), "low", 900 * bright) * np.exp(-t / 0.06)
    click = filt(rng.standard_normal(t.size), "band", (1500, 5000)) * np.exp(-t / 0.004)
    return norm(body + 0.45 * skin + 0.25 * bright * click)


def gong_clang(rng, base=520.0, dur=1.8):
    """鸣金用的铜钲/锣：非谐分音、微下滑音高、金属击点。"""
    t = _t(dur)
    ratios = [1.0, 1.53, 2.09, 2.71, 3.29, 4.12, 5.04, 6.3]
    amps = [1.0, 0.75, 0.6, 0.45, 0.33, 0.24, 0.15, 0.08]
    y = np.zeros(t.size)
    glide = 1.0 - 0.025 * (1 - np.exp(-t / 0.4))
    for r, a in zip(ratios, amps):
        fr = base * r * rng.uniform(0.99, 1.01) * glide
        dec = rng.uniform(0.5, 1.1) / (r ** 0.35)
        y += a * np.sin(2 * np.pi * np.cumsum(fr) / SR + rng.uniform(0, 6.28)) * np.exp(-t / dec)
    hit = filt(rng.standard_normal(t.size), "high", 2500) * np.exp(-t / 0.006)
    return norm(y + 0.5 * hit)


def bronze_bell(rng, base=98.0, dur=7.0):
    """大钟（编钟/朝钟）：带拍频的成对分音，长衰减。"""
    t = _t(dur)
    ratios = [0.5, 1.0, 1.183, 1.506, 2.0, 2.514, 2.662, 3.011, 4.166, 5.433]
    amps = [0.55, 1.0, 0.8, 0.6, 0.5, 0.35, 0.3, 0.22, 0.13, 0.07]
    decs = [7.5, 6.0, 5.0, 4.0, 3.4, 2.8, 2.4, 2.0, 1.4, 0.9]
    y = np.zeros(t.size)
    for r, a, d in zip(ratios, amps, decs):
        f = base * r
        beat = rng.uniform(0.3, 1.2)
        ph = rng.uniform(0, 6.28)
        y += a * 0.5 * (np.sin(2 * np.pi * f * t + ph) + np.sin(2 * np.pi * (f + beat) * t + ph)) * np.exp(-t / d)
    strike = filt(rng.standard_normal(t.size), "low", 700) * np.exp(-t / 0.03)
    return norm(y * (1 - np.exp(-t / 0.004)) + 0.35 * strike)


def sword_clash(rng):
    """刀剑格击：高频金属模态 + 击点噪声。"""
    t = _t(0.55)
    s = rng.uniform(0.85, 1.18)
    y = np.zeros(t.size)
    for f, a, d in [(1850, 1.0, 0.22), (2730, 0.8, 0.17), (3990, 0.6, 0.12),
                    (5620, 0.42, 0.08), (7480, 0.3, 0.05), (9300, 0.18, 0.03)]:
        y += a * rng.uniform(0.4, 1.0) * np.sin(2 * np.pi * f * s * rng.uniform(0.97, 1.03) * t
                                                 + rng.uniform(0, 6.28)) * np.exp(-t / (d * rng.uniform(0.6, 1.4)))
    click = filt(rng.standard_normal(t.size), "high", 1800) * np.exp(-t / 0.0045)
    return norm(0.65 * y + 0.9 * click)


def shield_thud(rng):
    """盾牌/甲胄/肉搏闷击。"""
    t = _t(0.3)
    f = rng.uniform(90, 150)
    y = filt(rng.standard_normal(t.size), "low", rng.uniform(350, 700)) * np.exp(-t / 0.045)
    y += 0.8 * np.sin(2 * np.pi * f * t) * np.exp(-t / 0.07)
    wood = filt(rng.standard_normal(t.size), "band", (600, 1600)) * np.exp(-t / 0.02)
    return norm(y + 0.4 * wood)


def blade_cleave(rng):
    """利刃劈砍命中：短促挥刀风声 + 锐利破甲金属声 + 重砍闷响。"""
    t = _t(0.42)
    noise = rng.standard_normal(t.size)
    swish = filt(noise, "band", (900, 3200)) * np.exp(-((t - 0.045) / 0.024) ** 2)
    edge = np.zeros(t.size)
    s = rng.uniform(0.92, 1.12)
    t_hit = np.maximum(0.0, t - 0.055)
    mask = (t >= 0.055).astype(float)
    for f, a, d in [(1650, 1.0, 0.14), (2880, 0.85, 0.11), (4520, 0.55, 0.07), (7100, 0.35, 0.04)]:
        edge += a * np.sin(2 * np.pi * f * s * t_hit + rng.uniform(0, 6.28)) * np.exp(-t_hit / d) * mask
    crunch = filt(rng.standard_normal(t.size), "band", (220, 1800)) * np.exp(-t_hit / 0.032) * mask
    return norm(0.7 * swish + 0.8 * edge + 0.9 * crunch)


def body_fall(rng):
    """中刀倒地：身躯砸地低频闷响 + 甲胄/兵刃散落轻撞。"""
    t = _t(0.55)
    f = rng.uniform(55, 82) * (1.0 + 0.35 * np.exp(-t / 0.025))
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.085)
    dirt = filt(rng.standard_normal(t.size), "low", 480) * np.exp(-t / 0.065)
    rattle = np.zeros(t.size)
    for dt in [0.05, 0.12, 0.21]:
        tt = np.maximum(0.0, t - dt)
        m = (t >= dt).astype(float)
        rattle += m * filt(rng.standard_normal(t.size), "band", (1400, 4800)) * np.exp(-tt / 0.022) * 0.4
    return norm(0.85 * thump + 0.65 * dirt + rattle)


def timber_crash(rng):
    """帅旗折断倾倒：木杆脆裂 + 砸地重响 + 旗面呼啦。"""
    t = _t(0.95)
    snap = filt(rng.standard_normal(t.size), "band", (650, 3400)) * np.exp(-t / 0.014)
    snap += 0.6 * np.sin(2 * np.pi * 420 * t) * np.exp(-t / 0.025)
    t2 = np.maximum(0.0, t - 0.36)
    m2 = (t >= 0.36).astype(float)
    f_low = 64.0 * (1.0 + 0.3 * np.exp(-t2 / 0.03))
    fall = m2 * (np.sin(2 * np.pi * np.cumsum(f_low) / SR) * np.exp(-t2 / 0.14)
                 + 0.7 * filt(rng.standard_normal(t.size), "low", 420) * np.exp(-t2 / 0.09))
    flap = m2 * filt(rng.standard_normal(t.size), "band", (160, 750)) * np.exp(-t2 / 0.18) * 0.5
    return norm(0.9 * snap + 1.0 * fall + flap)


def hoof_strike(rng, ice=False):
    t = _t(0.16)
    lp = rng.uniform(900, 1700) * (2.2 if ice else 1.0)
    y = filt(rng.standard_normal(t.size), "low", lp) * np.exp(-t / 0.016)
    f = rng.uniform(70, 110) * (1 + np.exp(-t / 0.01))
    y += 0.7 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035)
    if ice:
        y += 0.35 * np.sin(2 * np.pi * rng.uniform(2200, 3600) * t) * np.exp(-t / 0.03)
    return norm(y)


def footstep(rng, armor=True):
    t = _t(0.2)
    y = filt(rng.standard_normal(t.size), "band", (150, 1900)) * np.exp(-t / 0.028)
    y += 0.5 * np.sin(2 * np.pi * rng.uniform(70, 100) * t) * np.exp(-t / 0.03)
    if armor and rng.random() < 0.6:
        j = np.zeros(t.size)
        for f in rng.uniform(3200, 8500, 4):
            j += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / rng.uniform(0.02, 0.06))
        dly = int(rng.uniform(0.005, 0.03) * SR)
        y[dly:] += 0.25 * j[: t.size - dly]
    return norm(y)


# ----------------------------------------------------------------------------- 管乐/人声
def war_horn(rng, f0=110.0, dur=2.6, n_players=3):
    """号角：滑音起奏的锯齿波 + 共鸣峰 + 气息噪声，多人齐吹略失谐。"""
    t = _t(dur)
    y = np.zeros(t.size)
    for _ in range(n_players):
        fb = f0 * rng.uniform(0.985, 1.015)
        ff = fb * (0.86 + 0.14 * (1 - np.exp(-t / 0.18)))
        ff *= 1 + 0.006 * np.sin(2 * np.pi * rng.uniform(4.5, 6) * t)
        ph = 2 * np.pi * np.cumsum(ff) / SR
        y += signal.sawtooth(ph + rng.uniform(0, 6.28))
    y = filt(y, "low", 2400, order=2) + 0.9 * filt(y, "band", (350, 1300))
    breath = filt(rng.standard_normal(t.size), "band", (500, 3000)) * 0.06
    env = np.minimum(1, t / 0.28) * np.minimum(1, (dur - t) / 0.7).clip(0)
    return norm((y + breath) * env)


VOWELS = {"a": (800, 1200, 2500), "o": (520, 860, 2400), "e": (560, 1700, 2450), "u": (380, 800, 2300)}


def shout(rng, dur, f0, vowel="a", contour="fall"):
    """单个士兵的喊声（"杀！" / "啊——"），源-滤波器共振峰模型。"""
    t = _t(dur)
    u = t / dur
    if contour == "fall":
        cont = 1.15 - 0.3 * u
    elif contour == "rise":          # 惊叫：上扬后抖动
        cont = 0.95 + 0.45 * np.sin(np.pi * np.minimum(u * 1.4, 1.0))
    else:
        cont = np.ones_like(u)
    jitter = 1 + 0.02 * filt(rng.standard_normal(t.size), "low", 8)
    fr = f0 * cont * jitter * (1 + 0.012 * np.sin(2 * np.pi * rng.uniform(4, 7) * t))
    src = signal.sawtooth(2 * np.pi * np.cumsum(fr) / SR, 0.92)
    src = src + 0.18 * rng.standard_normal(t.size)            # 嘶哑气声
    F = VOWELS[vowel]
    y = (filt(src, "band", (F[0] - 110, F[0] + 110)) * 1.0
         + filt(src, "band", (F[1] - 140, F[1] + 140)) * 0.6
         + filt(src, "band", (F[2] - 200, F[2] + 200)) * 0.25)
    att = min(0.05, dur * 0.2)
    env = np.minimum(1, t / att) * np.clip((dur - t) / (dur * 0.45), 0, 1) ** 0.8
    return norm(y * env)


def crowd(rng, dur, n_shouts, f0_range=(105, 195), vowels="aoe", shout_len=(0.35, 1.1),
          contour="fall", murmur=0.35, spread=0.85):
    """群体喊杀/惊叫：大量个体喊声随机分布 + 宽带人声底噪。返回立体声。"""
    n = int(round(dur * SR))
    buf = np.zeros((2, n))
    for _ in range(n_shouts):
        ln = rng.uniform(*shout_len)
        st = rng.uniform(-0.2, max(0.05, dur - ln * 0.6))
        s = shout(rng, ln, rng.uniform(*f0_range), rng.choice(list(vowels)), contour)
        g = rng.uniform(0.25, 1.0)
        far = rng.uniform(0, 0.7)
        s = s * (1 - far) + filt(s, "low", 1100) * far
        place(buf, s, st, g * (1 - 0.5 * far), rng.uniform(-spread, spread))
    if murmur > 0:
        for ch in range(2):
            m = filt(colored_noise(n, rng, 1.0), "band", (220, 1800))
            m *= 0.4 + 0.6 * smooth_random(n, rng, 3.0)
            buf[ch] += murmur * norm(m) * 0.5
    return buf


# ----------------------------------------------------------------------------- 群体/复合事件
def melee_bed(rng, dur, rate=9.0, thud_ratio=0.45):
    """白刃混战：随机格击与闷击，前后远近交错。返回立体声。"""
    n = int(round(dur * SR))
    buf = np.zeros((2, n))
    k = rng.poisson(rate * dur)
    for st in np.sort(rng.uniform(0, dur, k)):
        s = shield_thud(rng) if rng.random() < thud_ratio else sword_clash(rng)
        far = rng.uniform(0, 0.8)
        s = s * (1 - far) + filt(s, "low", 1500) * far
        place(buf, s, st, rng.uniform(0.25, 0.9) * (1 - 0.6 * far), rng.uniform(-0.9, 0.9))
    return buf


def gallop(rng, dur, n_horses=10, ice=False, rumble=0.5, period=(0.34, 0.44)):
    """骑兵奔驰：每匹马三连蹄声 + 地面低频轰鸣。返回立体声。"""
    n = int(round(dur * SR))
    buf = np.zeros((2, n))
    for _ in range(n_horses):
        p = rng.uniform(*period)
        tt = rng.uniform(-p, 0)
        pan = rng.uniform(-0.85, 0.85)
        g = rng.uniform(0.35, 1.0)
        while tt < dur:
            for off in (0.0, 0.065, 0.13):
                ts = tt + off + rng.normal(0, 0.006)
                if 0 <= ts < dur:
                    place(buf, hoof_strike(rng, ice), ts, g * rng.uniform(0.6, 1.0), pan)
            tt += p * rng.uniform(0.96, 1.04)
    if rumble > 0:
        for ch in range(2):
            r = filt(colored_noise(n, rng, 2.0), "low", 140)
            buf[ch] += rumble * norm(r) * 0.6
    return buf


def arrow_whoosh(rng):
    """箭矢破空：带通噪声的中心频率由高到低扫过（多普勒感）。"""
    dur = rng.uniform(0.35, 0.6)
    t = _t(dur)
    noise = rng.standard_normal(t.size)
    centers = [5200, 3600, 2500, 1700]
    bands = [filt(noise, "band", (c * 0.75, c * 1.3)) for c in centers]
    pos = np.clip(t / dur, 0, 1) * (len(centers) - 1)
    y = np.zeros(t.size)
    for i, b in enumerate(bands):
        y += b * np.clip(1 - np.abs(pos - i), 0, 1)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1) ** 0.7) ** 2
    return norm(y * env)


def bow_twang(rng):
    t = _t(0.35)
    f = rng.uniform(160, 260)
    y = sum((1.0 / k) * np.sin(2 * np.pi * f * k * t) * np.exp(-t / (0.12 / k ** 0.6)) for k in range(1, 7))
    return norm(y + 0.3 * filt(rng.standard_normal(t.size), "high", 3000) * np.exp(-t / 0.003))


def arrow_volley(rng, n_arrows=26, spread=0.7):
    """一轮齐射：弓弦齐响 → 箭雨破空 → 零星中靶闷响。返回立体声。"""
    dur = 2.0
    buf = np.zeros((2, int(dur * SR)))
    for _ in range(max(6, n_arrows // 3)):
        place(buf, bow_twang(rng), rng.uniform(0, 0.12), rng.uniform(0.15, 0.35), rng.uniform(-0.6, 0.6))
    for _ in range(n_arrows):
        place(buf, arrow_whoosh(rng), rng.uniform(0.1, 0.1 + spread), rng.uniform(0.2, 0.6), rng.uniform(-0.9, 0.9))
    for _ in range(n_arrows // 2):
        place(buf, shield_thud(rng), rng.uniform(0.7, 1.4), rng.uniform(0.1, 0.35), rng.uniform(-0.9, 0.9))
    return buf


def ice_crack(rng):
    """冰面开裂：宽带爆裂 + 频散"啾"声。"""
    t = _t(0.7)
    y = filt(rng.standard_normal(t.size), "high", 900) * np.exp(-t / 0.008)
    for _ in range(rng.integers(2, 5)):
        f_hi, f_lo = rng.uniform(2500, 4500), rng.uniform(250, 500)
        fr = f_lo + (f_hi - f_lo) * np.exp(-t / rng.uniform(0.04, 0.09))
        y += 0.5 * np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / rng.uniform(0.12, 0.25))
    y += 0.6 * filt(rng.standard_normal(t.size), "low", 250) * np.exp(-t / 0.12)
    return norm(y)


def fire(rng, dur, crackle_rate=22.0):
    """城中火起：低沉火焰轰鸣 + 噼啪爆裂。返回立体声。"""
    n = int(round(dur * SR))
    buf = np.zeros((2, n))
    for ch in range(2):
        roar = filt(colored_noise(n, rng, 2.0), "band", (60, 500))
        roar *= 0.5 + 0.5 * smooth_random(n, rng, 2.0)
        buf[ch] += 0.5 * norm(roar)
    for st in rng.uniform(0, dur, rng.poisson(crackle_rate * dur)):
        ln = rng.uniform(0.002, 0.012)
        tt = _t(ln + 0.02)
        c = filt(rng.standard_normal(tt.size), "high", rng.uniform(1500, 4000)) * np.exp(-tt / ln)
        place(buf, norm(c), st, rng.uniform(0.05, 0.4), rng.uniform(-0.8, 0.8))
    return buf


def running_retreat(rng, dur, n_people=22, recede=True):
    """溃兵奔逃：杂乱急促的脚步与甲片碰撞，逐渐远去。返回立体声。"""
    n = int(round(dur * SR))
    buf = np.zeros((2, n))
    for _ in range(n_people):
        rate = rng.uniform(2.7, 3.6)
        tt = rng.uniform(0, 0.4)
        pan = rng.uniform(-0.9, 0.9)
        drift = rng.uniform(-0.3, 0.3)
        g = rng.uniform(0.3, 1.0)
        stumble_at = rng.uniform(0.3, dur) if rng.random() < 0.3 else None
        while tt < dur:
            place(buf, footstep(rng), tt, g * rng.uniform(0.6, 1.0), np.clip(pan + drift * tt / dur, -1, 1))
            step = 1.0 / rate * rng.uniform(0.85, 1.15)
            if stumble_at is not None and abs(tt - stumble_at) < 0.2:
                step *= 1.8           # 踉跄
            tt += step
    if recede:
        amt = np.linspace(0.0, 0.95, n)
        buf = distance(buf, amt)
    return buf


def whoosh(rng, dur=0.7, rising=True):
    """镜头转场的轻扫风声。"""
    t = _t(dur)
    noise = rng.standard_normal(t.size)
    centers = [350, 700, 1300, 2200] if rising else [2200, 1300, 700, 350]
    bands = [filt(noise, "band", (c * 0.7, c * 1.4)) for c in centers]
    pos = (t / dur) * (len(centers) - 1)
    y = sum(b * np.clip(1 - np.abs(pos - i), 0, 1) for i, b in enumerate(bands))
    env = np.sin(np.pi * t / dur) ** 2
    return norm(y * env)


def wind_bed(rng, dur):
    n = int(round(dur * SR))
    out = np.zeros((2, n))
    for ch in range(2):
        w = filt(colored_noise(n, rng, 1.0), "band", (90, 900))
        w *= 0.35 + 0.65 * smooth_random(n, rng, 0.35)
        out[ch] = norm(w)
    return out



# ----------------------------------------------------------------------------- 「大唐衰败」主题乐器
NOTE = {"D3": 146.83, "E3": 164.81, "G3": 196.00, "A3": 220.00, "C4": 261.63,
        "D4": 293.66, "E4": 329.63, "G4": 392.00, "A4": 440.00, "C5": 523.25, "D5": 587.33, "E5": 659.26}


def bianzhong(rng, f, dur=2.2):
    """编钟（盛唐礼乐）：明亮的双音钟体分音。"""
    t = _t(dur)
    y = np.zeros(t.size)
    for r, a, d in [(1.0, 1.0, 1.6), (2.0, 0.35, 0.9), (2.76, 0.4, 0.7), (5.4, 0.18, 0.3), (8.9, 0.08, 0.12)]:
        y += a * np.sin(2 * np.pi * f * r * t + rng.uniform(0, 6.28)) * np.exp(-t / d)
    hit = filt(rng.standard_normal(t.size), "band", (1500, 6000)) * np.exp(-t / 0.004)
    return norm(y * (1 - np.exp(-t / 0.002)) + 0.15 * hit)


def xun(rng, f, dur, slide_from=None):
    """埙：近正弦的浑厚吹奏音、浓重气声、缓慢颤音——苍凉悲怆。"""
    t = _t(dur)
    ff = np.full(t.size, f)
    if slide_from is not None:
        ff = f + (slide_from - f) * np.exp(-t / 0.18)
    vib = 1 + 0.009 * np.sin(2 * np.pi * 4.8 * t) * np.minimum(1, t / 0.6)
    ph = 2 * np.pi * np.cumsum(ff * vib) / SR
    y = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.07 * np.sin(3 * ph)
    breath = filt(rng.standard_normal(t.size), "band", (f * 0.8, f * 3.0)) * 0.22
    env = np.minimum(1, t / 0.22) ** 1.5 * np.clip((dur - t) / 0.5, 0, 1)
    env *= 1 + 0.12 * np.sin(2 * np.pi * 0.7 * t)
    return norm((y + breath) * env)


def guqin(rng, f, dur=3.0, slide_to=None):
    """古琴：拨弦衰减 + 走手音（吟猱下滑）。"""
    t = _t(dur)
    ff = np.full(t.size, f)
    if slide_to is not None:
        ff = f + (slide_to - f) * (1 - np.exp(-np.clip(t - 0.35, 0, None) / 0.25))
    ph = 2 * np.pi * np.cumsum(ff) / SR
    y = sum((1.0 / k ** 1.3) * np.sin(k * ph) * np.exp(-t / (1.6 / k ** 0.7)) for k in range(1, 8))
    pluck = filt(rng.standard_normal(t.size), "band", (800, 4000)) * np.exp(-t / 0.006)
    return norm(y + 0.12 * pluck)


def low_drone(rng, dur, f=55.0):
    """低沉张力铺底（溃败后的压抑感）。"""
    t = _t(dur)
    y = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.5 * t + 1.0)
         + 0.25 * np.sin(2 * np.pi * f * 2.0 * t + 2.0))
    y *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.35 * t)
    return norm(y)
