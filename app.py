"""
🎬 영상 에디터 v3.0 — 완전 재작성
====================================
수정사항:
- 이미지/동영상/오디오 업로드 세션 유지 (1개씩 추가 방식)
- 한글 폰트 자동 다운로드
- 하단 진행바 제거
- MP4 내보내기 + 오디오 합치기
- 모바일 완전 호환
"""

import streamlit as st
import time, math, random, io, os, tempfile, urllib.request
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ══════════════════════════════════════════════════════════
#  1. 페이지 설정 (맨 처음에)
# ══════════════════════════════════════════════════════════
st.set_page_config(
    page_title="🎬 영상 에디터",
    page_icon="🎬",
    layout="wide",
)

st.markdown("""
<style>
.stApp{background:#07070f;color:#e4e4f4}
section[data-testid="stSidebar"]{background:#0f0f1c}
section[data-testid="stSidebar"] label{color:#e4e4f4!important}
h1,h2,h3{color:#f0a840!important}
.stButton>button{
    background:linear-gradient(135deg,#f0a840,#ff7b54)!important;
    color:#000!important;font-weight:700!important;
    border:none!important;border-radius:20px!important;
    padding:6px 16px!important}
.stDownloadButton>button{
    background:linear-gradient(135deg,#44d9a0,#00b087)!important;
    color:#000!important;font-weight:700!important;
    border-radius:20px!important}
.stTextInput input{
    background:#171727!important;color:#e4e4f4!important;
    border:1px solid #252540!important;border-radius:8px!important}
.stSelectbox select,.stRadio label{color:#e4e4f4!important}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
#  2. 상수
# ══════════════════════════════════════════════════════════
CW, CH     = 360, 640   # 캔버스 9:16 비율
FPS        = 20          # 내보내기 FPS
SLIDE_SEC  = 5           # 슬라이드 간격(초)
MAX_IMG    = 10
MAX_VID    = 5
EXPORT_SEC = 30          # 최대 내보내기 시간

ANIMS = [
    ("없음","none"),        ("⭐ 별빛","stars"),
    ("🌧 소나기","hrain"),  ("🌂 이슬비","drizzle"),
    ("❄ 눈송이","snow"),   ("🌸 벚꽃","sakura"),
    ("🌼 작은꽃","flower"), ("☀ 햇빛","sun"),
    ("🍂 낙엽","leaf"),     ("🍃 작은낙엽","sleaf"),
    ("💨 수증기","steam"),  ("🌫 김서림","fog2"),
    ("🌁 안개","fog"),
]
ANIM_N = {
    "none":0,"stars":100,"hrain":150,"drizzle":90,"snow":70,
    "sakura":55,"flower":70,"sun":7,"leaf":30,"sleaf":45,
    "steam":25,"fog2":40,"fog":6,
}

# ══════════════════════════════════════════════════════════
#  3. 한글 폰트 (캐시 → 자동 다운로드)
# ══════════════════════════════════════════════════════════
FONT_PATH = "/tmp/NanumGothicBold.ttf"
FONT_URL  = (
    "https://github.com/googlefonts/nanum/raw/main"
    "/src/NanumGothic/NanumGothicBold.ttf"
)

@st.cache_resource
def get_font(size: int):
    """한글 폰트를 가져옵니다. 없으면 자동 다운로드."""
    # ① 이미 다운로드된 폰트
    if os.path.exists(FONT_PATH):
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except Exception:
            pass
    # ② 시스템 폰트 (Streamlit Cloud 기본 제공)
    for fp in [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    # ③ 인터넷 다운로드
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        pass
    return ImageFont.load_default()

# ══════════════════════════════════════════════════════════
#  4. 세션 상태 초기화
# ══════════════════════════════════════════════════════════
_DEFAULTS = {
    # 모드
    "mode":       "images",
    "cur_idx":    0,
    # 텍스트
    "t1": "", "t2": "", "t3": "",
    "txt_color":  "#ffffff",
    "txt_size":   36,
    # 슬라이드
    "trans":      "fade",
    # 애니메이션
    "anim":       "none",
    "anim_str":   1.0,
    "particles":  [],
    # 이미지 (bytes 리스트로 세션 유지)
    "img_bytes":  [],   # List[bytes]
    "img_list":   [],   # List[PIL.Image]
    # 동영상 (bytes + 임시파일 경로)
    "vid_bytes":  [],   # List[bytes]
    "vid_names":  [],   # List[str]
    "vid_paths":  [],   # List[str] 임시파일
    # 오디오
    "mus_bytes":  None, # bytes
    "mus_name":   "",
    "mus_path":   None, # 임시파일 경로
    "mus_vol":    0.7,
    "nar_bytes":  None,
    "nar_name":   "",
    "nar_path":   None,
    "nar_vol":    1.0,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

S = st.session_state  # 짧은 별칭

# ══════════════════════════════════════════════════════════
#  5. 파티클 시스템
# ══════════════════════════════════════════════════════════
class Particle:
    """애니메이션 파티클 1개"""
    def __init__(self, t: str):
        self.t = t
        self.alive = True
        r = random.random

        if t == "stars":
            self.x=r()*CW; self.y=r()*CH
            self.rad=r()*1.8+0.3
            self.a=r()
            self.da=(r()*.012+.003)*(1 if r()>.5 else -1)
            self.col=random.choice(["#ffffff","#fff8cc","#ffe0a0","#d0eeff"])

        elif t in ("hrain","drizzle"):
            self.x=r()*(CW+100); self.y=r()*CH
            self.vx=-2.5 if t=="hrain" else -0.8
            self.vy=r()*10+12 if t=="hrain" else r()*4+3
            self.ln=r()*14+7 if t=="hrain" else r()*7+3
            self.a=0.5 if t=="hrain" else 0.28

        elif t == "snow":
            self.x=r()*CW; self.y=r()*CH
            self.rad=r()*7+2
            self.vx=(r()-.5)*1.2; self.vy=r()*1.2+.4
            self.a=r()*.5+.4
            self.wob=r()*math.pi*2; self.ws=r()*.03

        elif t in ("sakura","flower"):
            self.x=r()*CW; self.y=r()*CH
            self.rad=r()*9+3
            self.vx=(r()-.5)*1.5-.5; self.vy=r()*1.5+.5
            self.a=r()*.5+.4
            self.wob=r()*math.pi*2; self.ws=r()*.03
            self.col=random.choice(
                ["#ffb7c5","#ff8fab","#ffc8d5","#ffddea"] if t=="sakura"
                else ["#ff6b9d","#ffbe0b","#ff006e","#06d6a0","#3a86ff"])

        elif t == "sun":
            self.angle=r()*math.pi
            self.length=r()*300+200
            self.width=r()*100+40
            self.a=r()*.06+.02
            self.da=(r()-.5)*.001

        elif t in ("leaf","sleaf"):
            self.x=r()*CW; self.y=r()*CH
            self.w=(r()*12+4) if t=="sleaf" else (r()*25+12)
            self.h=self.w*(r()*.3+.5)
            self.vx=(r()-.5)*1.5-.5; self.vy=r()*1.5+.5
            self.a=r()*.5+.4
            self.wob=r()*math.pi*2; self.ws=r()*.03
            self.col=random.choice(
                ["#cc4400","#ff6600","#cc8800","#883300","#ff9900"])

        elif t == "steam":
            self.x=r()*CW; self.y=r()*CH
            self.rad=r()*12+5
            self.vx=(r()-.5)*.5; self.vy=-(r()*.8+.3)
            self.a=r()*.2+.07

        elif t in ("fog2","fog"):
            self.x=r()*CW; self.y=r()*CH
            self.rad=r()*25+8
            self.a=r()*.22+.07
            self.vx=(r()-.5)*.2; self.vy=r()*.3+.04

    def update(self):
        t = self.t
        if t == "stars":
            self.a += self.da
            if self.a > 1: self.a, self.da = 1., -abs(self.da)
            if self.a < 0: self.a, self.da = 0.,  abs(self.da)
        elif t in ("hrain","drizzle"):
            self.x += self.vx; self.y += self.vy
            if self.y > CH+20: self.alive = False
        elif t == "snow":
            self.wob += self.ws
            self.x += self.vx + math.sin(self.wob)*.5
            self.y += self.vy
            if self.y > CH+20: self.alive = False
        elif t in ("sakura","flower"):
            self.wob += self.ws
            self.x += self.vx + math.sin(self.wob)*.5
            self.y += self.vy
            if self.y > CH+20 or self.x < -50 or self.x > CW+50:
                self.alive = False
        elif t == "sun":
            self.angle += self.da
            self.a += (random.random()-.5)*.004
            self.a = max(.01, min(.1, self.a))
        elif t in ("leaf","sleaf"):
            self.wob += self.ws
            self.x += self.vx + math.sin(self.wob)
            self.y += self.vy
            if self.y > CH+30 or self.x < -50 or self.x > CW+50:
                self.alive = False
        elif t == "steam":
            self.x += self.vx; self.y += self.vy
            self.rad += .2; self.a -= .003
            if self.a <= 0 or self.y < -50: self.alive = False
        elif t in ("fog2","fog"):
            self.x += self.vx; self.y += self.vy
            if self.y > CH+50: self.alive = False


def _update_particles():
    """파티클 리스트를 업데이트하고 부족하면 보충"""
    anim = S.anim
    if anim == "none":
        S.particles = []
        return
    target = int(ANIM_N.get(anim, 60) * S.anim_str)
    alive = [p for p in S.particles if p.alive]
    for p in alive:
        p.update()
    while len(alive) < target:
        alive.append(Particle(anim))
    S.particles = alive


def _draw_particles(base: Image.Image) -> Image.Image:
    """파티클을 PIL 이미지에 그립니다"""
    if not S.particles:
        return base

    ov = Image.new("RGBA", (CW, CH), (0,0,0,0))
    od = ImageDraw.Draw(ov)

    def hx(col, a):
        h = col.lstrip("#")
        return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16), int(a*255))

    for p in S.particles:
        ai = max(0., min(1., p.a))
        if ai < .02:
            continue
        t = p.t

        if t == "stars":
            r = max(1, int(p.rad))
            c = hx(p.col, ai)
            od.ellipse([(p.x-r, p.y-r),(p.x+r, p.y+r)], fill=c)

        elif t in ("hrain","drizzle"):
            c = (180,210,255, int(.8*255))
            lw = 2 if t=="hrain" else 1
            od.line([(p.x,p.y),(p.x+p.vx*2,p.y+p.ln)], fill=c, width=lw)

        elif t == "snow":
            c = (220,240,255, int(.85*255))
            r = max(1, int(p.rad))
            for i in range(6):
                ang = i/6*math.pi*2
                od.line([
                    (int(p.x), int(p.y)),
                    (int(p.x+math.cos(ang)*r), int(p.y+math.sin(ang)*r))
                ], fill=c, width=1)

        elif t in ("sakura","flower"):
            c = hx(p.col, ai)
            r = max(2, int(p.rad))
            od.ellipse([
                (int(p.x-r), int(p.y-r)),
                (int(p.x+r), int(p.y+r))
            ], fill=c)

        elif t == "sun":
            c = (255,220,80, max(1,int(p.a*160)))
            cx = CW//2; cy = -60
            hw = int(p.width*.4)
            pts = [
                (cx-hw, cy), (cx+hw, cy),
                (int(cx+p.width*.6), int(cy+p.length)),
                (int(cx-p.width*.6), int(cy+p.length)),
            ]
            ang = p.angle
            rpts = [
                (int(cx+(px-cx)*math.cos(ang)-(py-cy)*math.sin(ang)),
                 int(cy+(px-cx)*math.sin(ang)+(py-cy)*math.cos(ang)))
                for px,py in pts
            ]
            od.polygon(rpts, fill=c)

        elif t in ("leaf","sleaf"):
            c = hx(p.col, ai)
            hw = max(2, int(p.w*.5))
            hh = max(1, int(p.h*.5))
            od.ellipse([
                (int(p.x-hw), int(p.y-hh)),
                (int(p.x+hw), int(p.y+hh))
            ], fill=c)

        elif t in ("steam","fog2","fog"):
            r = max(1, int(p.rad))
            c = (200,220,240, max(1,int(p.a*130)))
            od.ellipse([(int(p.x-r),int(p.y-r)),(int(p.x+r),int(p.y+r))], fill=c)

    # 부드럽게 블러
    if S.anim in ("fog","fog2","steam"):
        ov = ov.filter(ImageFilter.GaussianBlur(radius=5))
    elif S.anim in ("snow",):
        ov = ov.filter(ImageFilter.GaussianBlur(radius=1))

    base.paste(ov, (0,0), ov)
    return base

# ══════════════════════════════════════════════════════════
#  6. 렌더링
# ══════════════════════════════════════════════════════════
def _fit(im: Image.Image) -> Image.Image:
    """9:16 캔버스에 꽉 차도록 리사이즈"""
    sc = max(CW/im.width, CH/im.height)
    return im.resize((int(im.width*sc), int(im.height*sc)), Image.LANCZOS)


def _paste(base: Image.Image, im: Image.Image, alpha: float = 1.0):
    """이미지를 캔버스 중앙에 알파값으로 붙여넣기"""
    fitted = _fit(im.convert("RGB"))
    ox, oy = (CW-fitted.width)//2, (CH-fitted.height)//2
    if alpha >= 1.0:
        base.paste(fitted, (ox, oy))
    else:
        ov = Image.new("RGBA", base.size, (0,0,0,0))
        tmp = fitted.convert("RGBA")
        r2,g2,b2,a2 = tmp.split()
        a2 = a2.point(lambda v: int(v*alpha))
        tmp = Image.merge("RGBA",(r2,g2,b2,a2))
        ov.paste(tmp, (ox,oy), tmp)
        base.paste(ov, (0,0), ov)


def _draw_texts(img: Image.Image) -> Image.Image:
    """문구를 이미지에 그립니다"""
    draw = ImageDraw.Draw(img, "RGBA")
    sz = S.txt_size
    hx = S.txt_color.lstrip("#")
    col = (int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16))

    fnt_big = get_font(sz)
    fnt_mid = get_font(int(sz*.78))
    fnt_sm  = get_font(int(sz*.75))

    def shadow(text, x, y, fnt, c):
        # 그림자 3겹
        for dx,dy in [(-2,2),(2,2),(0,3)]:
            draw.text((x+dx, y+dy), text, font=fnt,
                      fill=(0,0,0,190), anchor="mm")
        draw.text((x, y), text, font=fnt,
                  fill=(*c, 255), anchor="mm")

    # 상단 퍼스트
    if S.t1:
        shadow(S.t1, CW//2, sz+28, fnt_big, col)
    # 상단 세컨드
    if S.t2:
        y2 = sz*2+52 if S.t1 else sz+28
        shadow(S.t2, CW//2, y2, fnt_mid, col)
    # 하단 서드
    if S.t3:
        shadow(S.t3, CW//2, CH-52, fnt_sm, col)

    return img


def render_frame(tr_prog: float = 1.0, tr_prev: int = 0) -> Image.Image:
    """현재 상태를 PIL Image 한 장으로 렌더링"""
    # ── 배경 그라데이션 ──
    img = Image.new("RGB", (CW,CH), "#07070f")
    draw = ImageDraw.Draw(img)
    for y in range(0, CH, 2):
        v = y/CH
        draw.rectangle([(0,y),(CW,y+2)],
                       fill=(int(6+7*v), 5, int(15+22*v)))

    imgs = S.img_list

    # ── 이미지 모드 ──
    if S.mode == "images" and imgs:
        idx = S.cur_idx
        if tr_prog < 1.0 and tr_prev != idx:
            # 전환 효과
            if S.trans == "fade":
                _paste(img, imgs[tr_prev], 1.0-tr_prog)
                _paste(img, imgs[idx], tr_prog)
            elif S.trans == "slide":
                off = int((1-tr_prog)*CW)
                fp = _fit(imgs[tr_prev].convert("RGB"))
                img.paste(fp, ((CW-fp.width)//2 - off, (CH-fp.height)//2))
                fn2 = _fit(imgs[idx].convert("RGB"))
                img.paste(fn2, ((CW-fn2.width)//2 + CW-off, (CH-fn2.height)//2))
            else:  # zoom
                _paste(img, imgs[tr_prev], 1.0-tr_prog)
                _paste(img, imgs[idx], tr_prog)
        else:
            _paste(img, imgs[idx], 1.0)

        # 슬라이드 인디케이터 점
        if len(imgs) > 1:
            d2 = ImageDraw.Draw(img, "RGBA")
            total = len(imgs); gap = 14; r = 4
            sx = (CW - total*gap)//2 + gap//2
            for i in range(total):
                rv = r+2 if i==idx else r
                c = (240,168,64,220) if i==idx else (255,255,255,70)
                d2.ellipse([
                    (sx+i*gap-rv, CH-22-rv),
                    (sx+i*gap+rv, CH-22+rv)
                ], fill=c)

    # ── 동영상 모드 ──
    elif S.mode == "videos" and S.vid_paths:
        try:
            import cv2
            cap = cv2.VideoCapture(S.vid_paths[S.cur_idx])
            ret, frame = cap.read()
            cap.release()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                vf = Image.fromarray(frame_rgb)
                sc = max(CW/vf.width, CH/vf.height)
                vf = vf.resize((int(vf.width*sc),int(vf.height*sc)), Image.LANCZOS)
                img.paste(vf, ((CW-vf.width)//2, (CH-vf.height)//2))
        except Exception:
            pass

    # ── 아무것도 없을 때 안내 ──
    else:
        d2 = ImageDraw.Draw(img)
        d2.text((CW//2, CH//2-24), "🎬", (120,120,140), anchor="mm")
        d2.text((CW//2, CH//2+20), "이미지를 업로드해주세요",
                (100,100,120), anchor="mm")

    # ── 파티클 ──
    _update_particles()
    img = _draw_particles(img)

    # ── 텍스트 ──
    img = _draw_texts(img)

    return img

# ══════════════════════════════════════════════════════════
#  7. MP4 내보내기
# ══════════════════════════════════════════════════════════
def generate_mp4() -> bytes:
    """현재 설정으로 MP4를 생성해 bytes로 반환"""
    try:
        import imageio
    except ImportError:
        st.error("imageio 라이브러리가 없습니다.")
        return b""

    frames = []
    total  = EXPORT_SEC * FPS
    imgs   = S.img_list
    bar    = st.progress(0, "🎬 영상 프레임 생성 중...")

    # ── 이미지 슬라이드 모드 ──
    if S.mode == "images" and imgs:
        spf     = SLIDE_SEC * FPS           # 슬라이드당 프레임 수
        tr_f    = max(1, int(0.4*FPS))      # 전환 프레임 수
        cnt     = 0

        for _ in range(999):                # 30초 채울 때까지 반복
            for si in range(len(imgs)):
                S.cur_idx = si

                # 슬라이드 본체
                for f in range(spf):
                    frames.append(np.array(render_frame()))
                    cnt += 1
                    bar.progress(min(1., cnt/total),
                                 f"🎬 렌더링 {cnt}/{total} 프레임")
                    if cnt >= total:
                        break

                # 전환 효과
                if cnt < total and len(imgs) > 1:
                    ni = (si+1) % len(imgs)
                    prev = si
                    S.cur_idx = ni
                    for f in range(tr_f):
                        tp = f / tr_f
                        frames.append(np.array(render_frame(tr_prog=tp, tr_prev=prev)))
                        cnt += 1
                        if cnt >= total:
                            break

                if cnt >= total:
                    break
            if cnt >= total:
                break

    # ── 동영상 모드 ──
    elif S.mode == "videos" and S.vid_paths:
        try:
            import cv2
            cnt = 0
            for vpath in S.vid_paths:
                cap = cv2.VideoCapture(vpath)
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    vf = Image.fromarray(frame_rgb)
                    sc = max(CW/vf.width, CH/vf.height)
                    vf = vf.resize((int(vf.width*sc),int(vf.height*sc)),
                                   Image.LANCZOS)
                    base = Image.new("RGB",(CW,CH),"#07070f")
                    base.paste(vf, ((CW-vf.width)//2,(CH-vf.height)//2))
                    base = _draw_particles(base)
                    base = _draw_texts(base)
                    frames.append(np.array(base))
                    cnt += 1
                    bar.progress(min(1., cnt/total),
                                 f"🎬 렌더링 {cnt}/{total} 프레임")
                    if cnt >= total:
                        break
                cap.release()
                if cnt >= total:
                    break
        except Exception as e:
            st.error(f"동영상 읽기 오류: {e}")

    # ── 빈 화면 (3초) ──
    else:
        for _ in range(FPS*3):
            frames.append(np.array(render_frame()))

    if not frames:
        bar.empty()
        st.error("렌더링된 프레임이 없습니다.")
        return b""

    # ── 비디오 인코딩 ──
    bar.progress(0.92, "💾 MP4 인코딩 중...")
    buf = io.BytesIO()
    try:
        writer = imageio.get_writer(
            buf, format="mp4", fps=FPS,
            codec="libx264", quality=7,
            macro_block_size=8,
            output_params=["-pix_fmt","yuv420p"],
        )
        for f in frames:
            writer.append_data(f)
        writer.close()
    except Exception as e:
        bar.empty()
        st.error(f"MP4 인코딩 오류: {e}")
        return b""

    video_bytes = buf.getvalue()

    # ── 오디오 합치기 ──
    if S.mus_path or S.nar_path:
        bar.progress(0.96, "🎵 오디오 합치는 중...")
        try:
            from moviepy.editor import (
                VideoFileClip, AudioFileClip,
                CompositeAudioClip, concatenate_audioclips,
            )
            # 영상을 임시 파일에 저장
            tmp_v = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp_v.write(video_bytes); tmp_v.close()

            clip = VideoFileClip(tmp_v.name)
            audio_clips = []

            if S.mus_path and os.path.exists(S.mus_path):
                mc = AudioFileClip(S.mus_path).volumex(S.mus_vol)
                # 영상보다 짧으면 반복
                if mc.duration < clip.duration:
                    loops = int(clip.duration // mc.duration) + 1
                    mc = concatenate_audioclips([mc]*loops)
                audio_clips.append(mc.subclip(0, clip.duration))

            if S.nar_path and os.path.exists(S.nar_path):
                nc = AudioFileClip(S.nar_path).volumex(S.nar_vol)
                dur = min(nc.duration, clip.duration)
                audio_clips.append(nc.subclip(0, dur))

            if audio_clips:
                clip = clip.set_audio(CompositeAudioClip(audio_clips))

            tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp_out.close()
            clip.write_videofile(
                tmp_out.name, fps=FPS, logger=None,
                codec="libx264", audio_codec="aac",
                temp_audiofile="/tmp/_tmp_audio.m4a",
            )
            clip.close()
            with open(tmp_out.name,"rb") as fout:
                video_bytes = fout.read()

            # 임시파일 정리
            for p in [tmp_v.name, tmp_out.name]:
                try: os.unlink(p)
                except: pass

        except Exception as e:
            st.warning(f"⚠ 오디오 합치기 실패 (영상만 저장됩니다): {e}")

    bar.progress(1.0, "✅ 완료!")
    time.sleep(0.4)
    bar.empty()
    return video_bytes

# ══════════════════════════════════════════════════════════
#  8. 사이드바 UI
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🎬 영상 에디터")
    st.divider()

    # ── 재생 모드 ──────────────────────────────────────────
    st.markdown("### 📌 재생 모드")
    mc = st.radio("", ["🖼️ 이미지 슬라이드","🎬 동영상 재생"],
                  horizontal=True, label_visibility="collapsed")
    S.mode = "images" if "이미지" in mc else "videos"
    st.divider()

    # ── 문구 설정 ──────────────────────────────────────────
    with st.expander("📝 문구 설정", expanded=True):
        S.t1 = st.text_input("🔝 상단 퍼스트", value=S.t1,
                             placeholder="상단 첫째 줄")
        S.t2 = st.text_input("🔝 상단 세컨드", value=S.t2,
                             placeholder="상단 둘째 줄")
        S.t3 = st.text_input("🔻 하단 서드",   value=S.t3,
                             placeholder="하단 문구")
        c1, c2 = st.columns(2)
        with c1:
            S.txt_color = st.color_picker("글자 색상", S.txt_color)
        with c2:
            S.txt_size = st.slider("글자 크기", 16, 70, S.txt_size)

    # ── 이미지 업로드 ──────────────────────────────────────
    with st.expander("🖼️ 이미지 (최대 10장)", expanded=True):
        n_img = len(S.img_list)

        if n_img < MAX_IMG:
            up = st.file_uploader(
                f"이미지 추가 ({n_img}/{MAX_IMG}장)",
                type=["jpg","jpeg","png","bmp","webp"],
                accept_multiple_files=False,
                key=f"iup_{n_img}",   # n_img 바뀌면 위젯 초기화 → 연속 업로드 가능
            )
            if up is not None:
                try:
                    b = up.read()
                    pil = Image.open(io.BytesIO(b)).convert("RGB")
                    S.img_bytes.append(b)
                    S.img_list.append(pil)
                    st.rerun()
                except Exception as e:
                    st.error(f"이미지 오류: {e}")
        else:
            st.info(f"최대 {MAX_IMG}장 도달. ✕로 삭제 후 추가하세요.")

        # 썸네일 목록
        if S.img_list:
            st.caption(f"✅ {n_img}장 업로드됨")
            cols = st.columns(min(5, n_img))
            del_i = None
            for i, (col, im) in enumerate(zip(cols, S.img_list)):
                thumb = im.copy(); thumb.thumbnail((60,60))
                with col:
                    st.image(thumb, use_container_width=True,
                             caption="▶" if i==S.cur_idx else str(i+1))
                    if st.button("✕", key=f"di_{i}"):
                        del_i = i
            if del_i is not None:
                S.img_bytes.pop(del_i)
                S.img_list.pop(del_i)
                S.cur_idx = min(S.cur_idx, max(0, len(S.img_list)-1))
                st.rerun()
            if n_img > 1:
                S.cur_idx = st.slider("미리볼 이미지",
                                      0, n_img-1, S.cur_idx, key="imgsl")
            if st.button("🗑 전체 삭제", key="clrim"):
                S.img_bytes=[]; S.img_list=[]; S.cur_idx=0
                st.rerun()
        else:
            st.info("👆 이미지를 한 장씩 추가하세요")

        st.markdown("**전환 효과**")
        S.trans = st.radio(
            "", ["fade","slide","zoom"],
            format_func=lambda x: {
                "fade":"🌫 페이드","slide":"➡ 슬라이드","zoom":"🔍 줌"}[x],
            horizontal=True, label_visibility="collapsed",
            index=["fade","slide","zoom"].index(S.trans),
        )

    # ── 동영상 업로드 ──────────────────────────────────────
    with st.expander("🎬 동영상 (최대 5개)", expanded=False):
        n_vid = len(S.vid_paths)

        if n_vid < MAX_VID:
            vup = st.file_uploader(
                f"동영상 추가 ({n_vid}/{MAX_VID}개)",
                type=["mp4","mov","avi","mkv","webm"],
                accept_multiple_files=False,
                key=f"vup_{n_vid}",
            )
            if vup is not None:
                try:
                    b = vup.read()
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=Path(vup.name).suffix)
                    tmp.write(b); tmp.close()
                    S.vid_bytes.append(b)
                    S.vid_names.append(vup.name)
                    S.vid_paths.append(tmp.name)
                    st.rerun()
                except Exception as e:
                    st.error(f"동영상 오류: {e}")
        else:
            st.info(f"최대 {MAX_VID}개 도달.")

        if S.vid_names:
            st.caption(f"✅ {n_vid}개 업로드됨")
            del_vi = None
            for i, nm in enumerate(S.vid_names):
                c1, c2 = st.columns([5,1])
                with c1:
                    st.caption(f"{'▶ ' if i==S.cur_idx else ''}{i+1}. {nm}")
                with c2:
                    if st.button("✕", key=f"dv_{i}"):
                        del_vi = i
            if del_vi is not None:
                try: os.unlink(S.vid_paths[del_vi])
                except: pass
                S.vid_bytes.pop(del_vi)
                S.vid_names.pop(del_vi)
                S.vid_paths.pop(del_vi)
                S.cur_idx = min(S.cur_idx, max(0, len(S.vid_paths)-1))
                st.rerun()
            if n_vid > 1:
                S.cur_idx = st.slider("현재 동영상",
                                      0, n_vid-1, S.cur_idx, key="vidsl")
            if st.button("🗑 전체 삭제", key="clrvid"):
                for p in S.vid_paths:
                    try: os.unlink(p)
                    except: pass
                S.vid_bytes=[]; S.vid_names=[]; S.vid_paths=[]; S.cur_idx=0
                st.rerun()
        else:
            st.info("👆 동영상을 한 개씩 추가하세요")

    # ── 오디오 ─────────────────────────────────────────────
    with st.expander("🎵 오디오", expanded=False):
        st.caption("업로드하면 MP4에 자동으로 합쳐집니다")

        # 배경 음악
        st.markdown("**🎶 배경 음악**")
        if not S.mus_bytes:
            mf = st.file_uploader(
                "음악 파일 선택",
                type=["mp3","wav","ogg","m4a"],
                accept_multiple_files=False,
                key="mup_0",
            )
            if mf is not None:
                try:
                    b = mf.read()
                    S.mus_bytes = b
                    S.mus_name  = mf.name
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=Path(mf.name).suffix)
                    tmp.write(b); tmp.close()
                    S.mus_path = tmp.name
                    st.rerun()
                except Exception as e:
                    st.error(f"음악 오류: {e}")
        else:
            st.success(f"✅ {S.mus_name}")
            st.audio(io.BytesIO(S.mus_bytes))
            # 임시파일 없으면 복원
            if not S.mus_path or not os.path.exists(S.mus_path):
                tmp = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=Path(S.mus_name).suffix if S.mus_name else ".mp3")
                tmp.write(S.mus_bytes); tmp.close()
                S.mus_path = tmp.name
            if st.button("🗑 음악 삭제", key="delmus"):
                try: os.unlink(S.mus_path)
                except: pass
                S.mus_bytes=None; S.mus_name=""; S.mus_path=None
                st.rerun()
        S.mus_vol = st.slider("음악 볼륨", 0.0, 1.0, S.mus_vol,
                              0.05, key="mvol")

        st.markdown("---")

        # 나레이션
        st.markdown("**🎙️ 나레이션**")
        if not S.nar_bytes:
            nf = st.file_uploader(
                "나레이션 파일 선택",
                type=["mp3","wav","ogg","m4a"],
                accept_multiple_files=False,
                key="nup_0",
            )
            if nf is not None:
                try:
                    b = nf.read()
                    S.nar_bytes = b
                    S.nar_name  = nf.name
                    tmp = tempfile.NamedTemporaryFile(
                        delete=False, suffix=Path(nf.name).suffix)
                    tmp.write(b); tmp.close()
                    S.nar_path = tmp.name
                    st.rerun()
                except Exception as e:
                    st.error(f"나레이션 오류: {e}")
        else:
            st.success(f"✅ {S.nar_name}")
            st.audio(io.BytesIO(S.nar_bytes))
            if not S.nar_path or not os.path.exists(S.nar_path):
                tmp = tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=Path(S.nar_name).suffix if S.nar_name else ".mp3")
                tmp.write(S.nar_bytes); tmp.close()
                S.nar_path = tmp.name
            if st.button("🗑 나레이션 삭제", key="delnar"):
                try: os.unlink(S.nar_path)
                except: pass
                S.nar_bytes=None; S.nar_name=""; S.nar_path=None
                st.rerun()
        S.nar_vol = st.slider("나레이션 볼륨", 0.0, 1.0, S.nar_vol,
                              0.05, key="nvol")

    # ── 애니메이션 효과 ────────────────────────────────────
    with st.expander("✨ 애니메이션 효과", expanded=True):
        a_labels = [l for l,_ in ANIMS]
        a_ids    = [a for _,a in ANIMS]
        cur_ai   = a_ids.index(S.anim) if S.anim in a_ids else 0

        sel = st.selectbox("효과 선택", a_labels, index=cur_ai)
        new_anim = a_ids[a_labels.index(sel)]
        if new_anim != S.anim:
            S.anim = new_anim
            n = int(ANIM_N.get(new_anim, 60))
            S.particles = [Particle(new_anim) for _ in range(n)] \
                          if new_anim != "none" else []

        S.anim_str = st.slider("효과 강도", 0.3, 2.0, S.anim_str, 0.1)

# ══════════════════════════════════════════════════════════
#  9. 메인 화면
# ══════════════════════════════════════════════════════════
st.markdown("# 🎬 영상 에디터")

left, right = st.columns([2, 1])

with left:
    # 미리보기 렌더링
    frame = render_frame()
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image(frame, caption="📺 미리보기 (9:16)",
                 use_container_width=True)

    # 이전 / 새로고침 / 다음
    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("◀ 이전", use_container_width=True):
            arr = S.img_list if S.mode=="images" else S.vid_paths
            if arr:
                S.cur_idx = (S.cur_idx-1) % len(arr)
            st.rerun()
    with b2:
        if st.button("🔄 새로고침", use_container_width=True):
            st.rerun()
    with b3:
        if st.button("다음 ▶", use_container_width=True):
            arr = S.img_list if S.mode=="images" else S.vid_paths
            if arr:
                S.cur_idx = (S.cur_idx+1) % len(arr)
            st.rerun()

with right:
    # 현재 상태
    arr = S.img_list if S.mode=="images" else S.vid_paths
    st.markdown("### ℹ️ 현재 상태")
    st.info(
        f"**모드**: {'이미지 슬라이드' if S.mode=='images' else '동영상'}\n\n"
        f"**{'이미지' if S.mode=='images' else '동영상'}**: "
        f"{S.cur_idx+1} / {len(arr) if arr else 0}\n\n"
        f"**애니메이션**: {dict(ANIMS).get(S.anim,'없음')}\n\n"
        f"**음악**: {'✅ '+S.mus_name if S.mus_name else '없음'}\n\n"
        f"**나레이션**: {'✅ '+S.nar_name if S.nar_name else '없음'}"
    )

    st.divider()

    # MP4 내보내기
    st.markdown("### 📤 MP4 내보내기")
    st.caption(f"최대 {EXPORT_SEC}초 분량 생성")

    if st.button("🎬 MP4 생성 시작", use_container_width=True, type="primary"):
        vb = generate_mp4()
        if vb:
            fname = f"영상_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
            st.download_button(
                label="⬇ MP4 다운로드",
                data=vb,
                file_name=fname,
                mime="video/mp4",
                use_container_width=True,
            )
            sz = len(vb)/1024/1024
            st.success(f"✅ 완료! {sz:.1f}MB")

st.divider()
st.caption("🎬 영상 에디터 v3.0 | AI닷 (AI DOT) | 9:16 비율")
