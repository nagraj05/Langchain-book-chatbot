from __future__ import annotations

import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "media"
OUT.mkdir(exist_ok=True)

W = H = 1080
FPS = 30
DURATION = 15

BG = "#090B0E"
PANEL = "#111418"
PANEL_2 = "#171B20"
TEXT = "#F4F1EA"
MUTED = "#99A1AA"
ACCENT = "#F2A65A"
ACCENT_2 = "#FFB76E"
GREEN = "#70D49B"
BLUE = "#82B9F4"


def font(size: int, bold: bool = False, serif: bool = False):
    if serif:
        path = Path("C:/Windows/Fonts/georgiab.ttf" if bold else "C:/Windows/Fonts/georgia.ttf")
    else:
        path = Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf")
    return ImageFont.truetype(str(path), size)


F_18 = font(18)
F_22 = font(22)
F_24B = font(24, True)
F_28 = font(28)
F_30B = font(30, True)
F_34B = font(34, True)
F_42B = font(42, True)
F_54B = font(54, True)
F_70B = font(70, True)
F_84B = font(84, True)
F_44S = font(44, True, True)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def ease(v):
    v = clamp(v)
    return 1 - (1 - v) ** 3


def smooth(v):
    v = clamp(v)
    return v * v * (3 - 2 * v)


def window(t, start, end, fade=0.45):
    return smooth((t - start) / fade) * smooth((end - t) / fade)


def mix(a, b, t):
    return a + (b - a) * t


def rgba(hex_color, alpha=255):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) + (int(alpha),)


def text(draw, xy, value, fnt, fill=TEXT, anchor="la", alpha=255):
    draw.text(xy, value, font=fnt, fill=rgba(fill, alpha), anchor=anchor)


def overlay(base, layer):
    base.alpha_composite(layer)


def glow_circle(base, center, radius, color, alpha=70):
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    x, y = center
    d.ellipse((x-radius, y-radius, x+radius, y+radius), fill=rgba(color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.55))
    overlay(base, layer)


def logo(draw, x, y, size, alpha=255):
    draw.rounded_rectangle((x, y, x+size, y+size), radius=size*0.22, fill=rgba(PANEL, alpha))
    p = [(x+size*.17, y+size*.28), (x+size*.5, y+size*.38), (x+size*.5, y+size*.79), (x+size*.17, y+size*.7)]
    q = [(x+size*.83, y+size*.28), (x+size*.5, y+size*.38), (x+size*.5, y+size*.79), (x+size*.83, y+size*.7)]
    draw.polygon(p, fill=rgba(ACCENT, alpha))
    draw.polygon(q, fill=rgba(ACCENT_2, alpha))
    draw.line((x+size*.5, y+size*.38, x+size*.5, y+size*.79), fill=rgba(PANEL, alpha), width=max(2, int(size*.045)))


def book(layer, x, y, w, h, color, title, subtitle="", angle=0, alpha=255):
    pad = 26
    b = Image.new("RGBA", (int(w+pad*2), int(h+pad*2)))
    d = ImageDraw.Draw(b)
    d.rounded_rectangle((pad+8, pad+10, pad+w+8, pad+h+12), radius=18, fill=(0, 0, 0, int(alpha*.32)))
    d.rounded_rectangle((pad, pad, pad+w, pad+h), radius=16, fill=rgba(color, alpha))
    d.rectangle((pad+18, pad, pad+25, pad+h), fill=(255, 255, 255, int(alpha*.16)))
    d.line((pad+w-12, pad+18, pad+w-12, pad+h-18), fill=(0, 0, 0, int(alpha*.18)), width=3)
    title_font = F_30B if len(title) < 15 else F_24B
    title_color = "#101318" if color in (ACCENT, ACCENT_2, "#E6C56E") else TEXT
    d.multiline_text((pad+42, pad+h*.25), title, font=title_font, fill=rgba(title_color, alpha), spacing=6)
    if subtitle:
        d.text((pad+42, pad+h-55), subtitle.upper(), font=F_18, fill=rgba(title_color, int(alpha*.72)))
    if angle:
        b = b.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    layer.alpha_composite(b, (int(x-b.width/2), int(y-b.height/2)))


def pill(draw, x, y, label, color, alpha=255):
    box = draw.textbbox((0, 0), label, font=F_22)
    tw = box[2] - box[0]
    draw.rounded_rectangle((x, y, x+tw+38, y+46), radius=23, fill=rgba(color, int(alpha*.12)), outline=rgba(color, int(alpha*.45)), width=2)
    draw.ellipse((x+14, y+18, x+22, y+26), fill=rgba(color, alpha))
    text(draw, (x+29, y+23), label, F_22, color, "lm", alpha)
    return tw + 38


def scene_books(base, t):
    a = int(255 * window(t, 0, 4.05, .5))
    if not a:
        return
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    intro = ease((t-.15)/.8)
    text(d, (76, 82 + (1-intro)*24), "YOUR BOOKS. ONE CONVERSATION.", F_22, ACCENT, alpha=int(a*intro))
    text(d, (76, 126 + (1-intro)*30), "Your library has", F_70B, TEXT, alpha=int(a*intro))
    text(d, (76, 205 + (1-intro)*30), "answers.", F_70B, ACCENT, alpha=int(a*intro))
    specs = [
        ("#3A5974", "THE\nODYSSEY", "HOMER", -8, 230, 650),
        ("#A04444", "HOMER", "EPIC POETRY", -2, 435, 660),
        ("#524070", "DARK\nMATTER", "BLAKE CROUCH", 4, 645, 645),
        ("#E6C56E", "PROJECT\nHAIL MARY", "ANDY WEIR", 9, 855, 660),
    ]
    for i, (c, title_, sub, angle, x, y) in enumerate(specs):
        p = ease((t-(.55+i*.16))/.75)
        yy = y + (1-p)*290 + math.sin(t*1.15+i)*5
        book(layer, x, yy, 188, 350, c, title_, sub, angle*(.65+.35*p), int(a*p))
    text(d, (540, 956), "PDF  •  EPUB  •  TXT  •  MD", F_22, MUTED, "ma", a)
    overlay(base, layer)


def app_shell(layer, x, y, w, h, alpha=255):
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((x+12, y+18, x+w+12, y+h+18), radius=34, fill=(0, 0, 0, int(alpha*.35)))
    d.rounded_rectangle((x, y, x+w, y+h), radius=32, fill=rgba(PANEL, alpha), outline=rgba("#333A43", alpha), width=2)
    d.line((x, y+86, x+w, y+86), fill=rgba("#2A3037", alpha), width=2)
    logo(d, x+26, y+19, 48, alpha)
    text(d, (x+88, y+43), "BOOKBot", F_24B, TEXT, "lm", alpha)
    d.rounded_rectangle((x+w-152, y+23, x+w-24, y+65), radius=12, fill=rgba(ACCENT, alpha))
    text(d, (x+w-88, y+44), "+ Add book", F_18, PANEL, "mm", alpha)


def scene_chat(base, t):
    a = int(255 * window(t, 3.35, 10.7, .55))
    if not a:
        return
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    p = ease((t-3.45)/.8)
    x, y, w, h = 74, int(mix(1040, 126, p)), 932, 812
    app_shell(layer, x, y, w, h, a)
    # Scope selector
    d.rounded_rectangle((x+310, y+24, x+625, y+65), radius=12, fill=rgba(PANEL_2, a), outline=rgba("#353C45", a))
    text(d, (x+332, y+44), "▣  All books  4", F_18, MUTED, "lm", a)
    # User question types on
    qstart = 4.35
    question = "What makes survival possible?"
    chars = int(len(question) * clamp((t-qstart)/1.0))
    qa = int(a*smooth((t-4.05)/.35))
    d.rounded_rectangle((x+224, y+140, x+w-48, y+217), radius=19, fill=rgba("#20252B", qa))
    text(d, (x+250, y+178), question[:chars], F_28, TEXT, "lm", qa)
    if chars < len(question) and chars > 0:
        cx = x+250+d.textlength(question[:chars], font=F_28)+3
        d.rectangle((cx, y+158, cx+2, y+197), fill=rgba(ACCENT, qa))
    # Assistant response
    ra = int(a*smooth((t-5.55)/.55))
    logo(d, x+48, y+282, 46, ra)
    text(d, (x+112, y+299), "BOOKBot", F_24B, TEXT, "lm", ra)
    lines = [
        ("Survival becomes possible through a mix of", MUTED),
        ("resourcefulness, trust, and the courage to adapt.", TEXT),
        ("Across these stories, knowledge matters most when", MUTED),
        ("it becomes action.", TEXT),
    ]
    for i, (line, c) in enumerate(lines):
        lp = smooth((t-(5.8+i*.14))/.45)
        text(d, (x+112, y+352+i*45), line, F_28, c, alpha=int(ra*lp))
    # Citation cards rise in
    for i, (title_, detail, c) in enumerate([
        ("Project Hail Mary", "Chapter 12", ACCENT),
        ("The Odyssey", "Book IX", BLUE),
        ("Dark Matter", "Chapter 8", "#B39DDB"),
    ]):
        cp = ease((t-(6.65+i*.18))/.55)
        cy = y+598 + (1-cp)*34
        cx = x+112+i*248
        d.rounded_rectangle((cx, cy, cx+226, cy+108), radius=15, fill=rgba(PANEL_2, int(ra*cp)), outline=rgba(c, int(ra*cp*.55)), width=2)
        d.rectangle((cx, cy+18, cx+5, cy+90), fill=rgba(c, int(ra*cp)))
        text(d, (cx+22, cy+31), title_, F_18, TEXT, alpha=int(ra*cp))
        text(d, (cx+22, cy+70), detail, F_18, MUTED, alpha=int(ra*cp))
        text(d, (cx+188, cy+72), f"[{i+1}]", F_18, c, alpha=int(ra*cp))
    # Composer
    d.rounded_rectangle((x+48, y+h-86, x+w-48, y+h-28), radius=18, fill=rgba("#1B2026", a), outline=rgba("#38404A", a))
    text(d, (x+72, y+h-57), "Ask your library anything…", F_22, MUTED, "lm", a)
    d.ellipse((x+w-98, y+h-76, x+w-58, y+h-36), fill=rgba(ACCENT, a))
    text(d, (x+w-78, y+h-56), "↑", F_24B, PANEL, "mm", a)
    overlay(base, layer)


def scene_values(base, t):
    a = int(255 * window(t, 9.55, 12.75, .5))
    if not a:
        return
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    p = ease((t-9.65)/.65)
    text(d, (540, 210+(1-p)*30), "BUILT FOR YOUR PRIVATE LIBRARY", F_22, ACCENT, "ma", int(a*p))
    text(d, (540, 275+(1-p)*30), "Grounded answers.", F_70B, TEXT, "ma", int(a*p))
    text(d, (540, 358+(1-p)*30), "No cloud required.", F_70B, ACCENT, "ma", int(a*p))
    labels = [("⌂", "Local by default", GREEN), ("✓", "Source citations", BLUE), ("⌁", "Multi-book chat", ACCENT)]
    total = 0
    widths = []
    for _, label, _ in labels:
        widths.append(ImageDraw.Draw(Image.new("RGB", (1,1))).textlength(label, font=F_22)+88)
    total = sum(widths)+30*2
    cursor = (W-total)/2
    for i, ((icon, label, color), pw) in enumerate(zip(labels, widths)):
        pp = ease((t-(10.25+i*.16))/.55)
        yy = 520+(1-pp)*30
        d.rounded_rectangle((cursor, yy, cursor+pw, yy+74), radius=22, fill=rgba(PANEL_2, int(a*pp)), outline=rgba(color, int(a*pp*.48)), width=2)
        text(d, (cursor+26, yy+37), icon, F_30B, color, "lm", int(a*pp))
        text(d, (cursor+65, yy+37), label, F_22, TEXT, "lm", int(a*pp))
        cursor += pw+30
    # local pipeline
    yy = 720
    items = [("BOOKS", ACCENT), ("EMBED", BLUE), ("RETRIEVE", "#B39DDB"), ("ANSWER", GREEN)]
    for i, (label, color) in enumerate(items):
        pp = ease((t-(10.55+i*.12))/.5)
        cx = 150+i*260
        d.ellipse((cx-34, yy-34, cx+34, yy+34), fill=rgba(color, int(a*pp*.18)), outline=rgba(color, int(a*pp)), width=3)
        text(d, (cx, yy), str(i+1), F_24B, color, "mm", int(a*pp))
        text(d, (cx, yy+78), label, F_18, MUTED, "ma", int(a*pp))
        if i < len(items)-1:
            linep = clamp((t-(10.75+i*.12))/.55)
            d.line((cx+45, yy, cx+45+170*linep, yy), fill=rgba("#39414A", int(a*pp)), width=3)
    overlay(base, layer)


def scene_end(base, t):
    a = int(255*smooth((t-12.15)/.55))
    if not a:
        return
    layer = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(layer)
    p = ease((t-12.2)/.8)
    size = 126
    logo(d, W/2-size/2, 178+(1-p)*28, size, int(a*p))
    text(d, (540, 358+(1-p)*24), "Meet BOOKBot", F_84B, TEXT, "ma", int(a*p))
    text(d, (540, 462+(1-p)*24), "Ask your books anything.", F_42B, ACCENT, "ma", int(a*p))
    text(d, (540, 528), "Private, grounded, and completely local.", F_28, MUTED, "ma", a)
    # CTA
    cp = ease((t-13.0)/.6)
    d.rounded_rectangle((330, 650+(1-cp)*20, 750, 730+(1-cp)*20), radius=24, fill=rgba(ACCENT, int(a*cp)))
    text(d, (540, 690+(1-cp)*20), "CHAT WITH YOUR LIBRARY  →", F_24B, PANEL, "mm", int(a*cp))
    text(d, (540, 845), "Your library.  Your machine.  Your answers.", F_22, TEXT, "ma", int(a*cp*.9))
    text(d, (540, 916), "Built with LangChain  •  Ollama  •  Qdrant", F_18, MUTED, "ma", int(a*cp*.8))
    overlay(base, layer)


def render_frame(t):
    base = Image.new("RGBA", (W, H), rgba(BG))
    # Ambient light and a subtle editorial grid.
    glow_circle(base, (180+80*math.sin(t*.28), 170), 250, ACCENT, 26)
    glow_circle(base, (920, 800+70*math.cos(t*.22)), 300, BLUE, 15)
    grid = Image.new("RGBA", (W, H))
    gd = ImageDraw.Draw(grid)
    for x in range(0, W, 54):
        gd.line((x, 0, x, H), fill=(255, 255, 255, 5))
    for y in range(0, H, 54):
        gd.line((0, y, W, y), fill=(255, 255, 255, 5))
    overlay(base, grid)
    scene_books(base, t)
    scene_chat(base, t)
    scene_values(base, t)
    scene_end(base, t)
    return base.convert("RGB")


def main():
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = OUT / "bookbot_linkedin.mp4"
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for i in range(FPS * DURATION):
        frame = render_frame(i / FPS)
        proc.stdin.write(frame.tobytes())
        if i in (0, 150, 300, 449):
            print(f"Rendered frame {i+1}/{FPS*DURATION}")
    proc.stdin.close()
    if proc.wait() != 0:
        raise SystemExit("ffmpeg encoding failed")
    render_frame(13.6).save(OUT / "bookbot_linkedin_poster.png", quality=95)
    print(mp4)


if __name__ == "__main__":
    main()
