"""
🎬 영상 에디터 — Streamlit 버전
================================
실행: streamlit run app.py
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import time, math, random, io, os, tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ──────────────────────────────────────────────────────────
#  페이지 기본 설정 (맨 처음에 와야 함)
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎬 영상 에디터",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────
#  CSS 스타일 (다크 테마)
# ──────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 전체 배경 */
.stApp { background-color: #07070f; color: #e4e4f4; }
section[data-testid="stSidebar"] { background-color: #0f0f1c; }
section[data-testid="stSidebar"] * { color: #e4e4f4 !important; }

/* 제목 */
h1 { color: #f0a840 !important; font-family: 'Arial Black', sans-serif; }
h2, h3 { color: #f0a840 !important; }

/* 버튼 */
.stButton > button {
    background: linear-gradient(135deg, #f0a840, #ff7b54) !important;
    color: #000 !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 20px !important;
    padding: 8px 20px !important;
}
.stButton > button:hover { opacity: 0.88; }

/* 다운로드 버튼 */
.stDownloadButton > button {
    background: linear-gradient(135deg, #44d9a0, #00b087) !important;
    color: #000 !important;
    font-weight: 700 !important;
    border-radius: 20px !important;
}

/* 입력창 */
.stTextInput > div > div > input {
    background-color: #171727 !important;
    color: #e4e4f4 !important;
    border: 1px solid #252540 !important;
}

/* 슬라이더 */
.stSlider { color: #f0a840 !important; }

/* 구분선 */
hr { border-color: #252540 !important; }

/* 미디어 컨테이너 */
.preview-box {
    background: #040408;
    border-radius: 12px;
    padding: 20px;
    display: flex;
    justify-content: center;
    align-items: center;
}

/* 상태 배지 */
.rec-badge {
    background: rgba(232,68,90,.15);
    border: 1px solid #e8445a;
    color: #e8445a;
    border-radius: 20px;
    padding: 4px 12px;
    font-weight: 700;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────
#  상수
# ──────────────────────────────────────────────────────────
CW, CH      = 360, 640    # 캔버스 크기 (9:16)
FPS         = 24          # 내보내기 FPS
SLIDE_SEC   = 5           # 슬라이드 간격(초)
MAX_IMG     = 10
MAX_VID     = 5
EXPORT_SEC  = 30          # 내보내기 최대 길이

# 애니메이션 목록
ANIMS = [
    ("없음",     "none"),   ("⭐ 별빛",   "stars"),
    ("🌧 소나기","hrain"),  ("🌂 이슬비","drizzle"),
    ("❄ 눈송이", "snow"),   ("🌸 벚꽃",  "sakura"),
    ("🌼 작은꽃","flower"), ("☀ 햇빛",   "sun"),
    ("🍂 낙엽",  "leaf"),   ("🍃 작은낙엽","sleaf"),
    ("💨 수증기","steam"),  ("🌫 김서림","fog2"),
    ("🌁 안개",  "fog"),
]
ANIM_COUNTS = {
    "none":0,"stars":120,"hrain":180,"drizzle":100,"snow":90,
    "sakura":70,"flower":90,"sun":8,"leaf":35,"sleaf":50,
    "steam":28,"fog2":45,"fog":6,
}

# ──────────────────────────────────────────────────────────
#  세션 상태 초기화
# ──────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "mode":       "images",
        "cur_idx":    0,
        "playing":    False,
        "slide_start":time.time(),
        "t1": "", "t2": "", "t3": "",
        "txt_color":  "#ffffff",
        "txt_size":   38,
        "trans":      "fade",
        "mus_vol":    0.7,
        "nar_vol":    1.0,
        "anim":       "none",
        "anim_str":   1.0,
        "particles":  [],
        "last_ts":    time.time(),
        # 업로드된 파일 (PIL Image 리스트 등)
        "img_list":   [],   # PIL Image
        "vid_paths":  [],   # 임시 파일 경로
        "mus_path":   None,
        "nar_path":   None,
        # 전환 효과
        "tr_active":  False,
        "tr_prog":    0.0,
        "tr_prev":    0,
        "tr_start":   0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()
S = st.session_state   # 편의상 짧게


# ──────────────────────────────────────────────────────────
#  파티클 클래스
# ──────────────────────────────────────────────────────────
class Particle:
    def __init__(self, t: str):
        self.type  = t
        self.alive = True
        r = random.random
        if t == "stars":
            self.x=r()*CW; self.y=r()*CH; self.rad=r()*2.2+.4
            self.a=r(); self.da=(r()*.015+.004)*(1 if r()>.5 else -1)
            self.col=random.choice(["#ffffff","#fff8cc","#ccddff","#ffe0a0"])
        elif t in ("hrain","drizzle"):
            self.x=r()*(CW+200)-100; self.y=r()*CH
            self.vx=-2.5 if t=="hrain" else -.8
            self.vy=r()*10+14 if t=="hrain" else r()*5+5
            self.ln=r()*18+10 if t=="hrain" else r()*8+4
            self.a=.55 if t=="hrain" else .3
        elif t == "snow":
            self.x=r()*CW; self.y=r()*CH; self.rad=r()*9+2
            self.vx=(r()-.5)*1.5; self.vy=r()*1.5+.5
            self.a=r()*.5+.4; self.wob=r()*math.pi*2; self.ws=r()*.04
        elif t in ("sakura","flower"):
            self.x=r()*(CW+120); self.y=r()*CH; self.rad=r()*12+5
            self.vx=(r()-.5)*2-.8; self.vy=r()*2+.6
            self.rot=r()*math.pi*2; self.rs=(r()-.5)*.1
            self.a=r()*.5+.45; self.wob=r()*math.pi*2; self.ws=r()*.03
            self.col=random.choice(
                ["#ffb7c5","#ffccda","#ff8fab"] if t=="sakura"
                else ["#ff6b9d","#ffbe0b","#ff006e","#06d6a0","#3a86ff"])
        elif t == "sun":
            self.angle=r()*math.pi; self.length=r()*350+250
            self.width=r()*120+40; self.a=r()*.07+.02; self.da=(r()-.5)*.0008
        elif t in ("leaf","sleaf"):
            sm=(t=="sleaf"); self.x=r()*(CW+100); self.y=r()*CH
            self.w=r()*14+5 if sm else r()*30+14; self.h=self.w*(r()*.35+.55)
            self.vx=(r()-.5)*2-.8; self.vy=r()*2+.7
            self.rot=r()*math.pi*2; self.rs=(r()-.5)*.05
            self.a=r()*.5+.45; self.wob=r()*math.pi*2; self.ws=r()*.03
            self.col=random.choice(["#cc4400","#ff6600","#cc8800","#883300","#ff9900"])
        elif t == "steam":
            self.x=r()*CW; self.y=r()*CH; self.rad=r()*18+8
            self.vx=(r()-.5)*.7; self.vy=-(r()*1.2+.4); self.a=r()*.25+.08
        elif t in ("fog2","fog"):
            self.x=r()*CW; self.y=r()*CH; self.rad=r()*4+.5
            self.a=r()*.35+.1; self.vx=(r()-.5)*.3; self.vy=r()*.4+.05
            self.w=r()*500+250; self.h=r()*100+50

    def update(self):
        t=self.type; r=random.random
        if t=="stars":
            self.a+=self.da
            if self.a>1: self.a,self.da=1.,-abs(self.da)
            if self.a<0: self.a,self.da=0., abs(self.da)
        elif t in ("hrain","drizzle"):
            self.x+=self.vx; self.y+=self.vy
            if self.y>CH+20: self.alive=False
        elif t=="snow":
            self.wob+=self.ws; self.x+=self.vx+math.sin(self.wob)*.6; self.y+=self.vy
            if self.y>CH+20: self.alive=False
        elif t in ("sakura","flower"):
            self.wob+=self.ws; self.x+=self.vx+math.sin(self.wob)*.6
            self.y+=self.vy; self.rot+=self.rs
            if self.y>CH+20 or self.x<-60 or self.x>CW+60: self.alive=False
        elif t=="sun":
            self.angle+=self.da; self.a+=(r()-.5)*.005
            self.a=max(.01,min(.12,self.a))
        elif t in ("leaf","sleaf"):
            self.wob+=self.ws; self.x+=self.vx+math.sin(self.wob)*1.2
            self.y+=self.vy; self.rot+=self.rs
            if self.y>CH+30 or self.x<-60 or self.x>CW+60: self.alive=False
        elif t=="steam":
            self.x+=self.vx; self.y+=self.vy; self.rad+=.25; self.a-=.003
            if self.a<=0 or self.y<-60: self.alive=False
        elif t in ("fog2","fog"):
            self.x+=self.vx; self.y+=self.vy
            if self.y>CH+50: self.alive=False


# ──────────────────────────────────────────────────────────
#  파티클 업데이트 & 이미지에 그리기
# ──────────────────────────────────────────────────────────
def update_particles():
    """세션 파티클 리스트 업데이트 및 보충"""
    anim = S.anim
    if anim == "none":
        S.particles = []
        return
    target = int(ANIM_COUNTS.get(anim, 80) * S.anim_str)
    alive = [p for p in S.particles if p.alive]
    for p in alive: p.update()
    while len(alive) < target:
        alive.append(Particle(anim))
    S.particles = alive


def draw_particles(base: Image.Image) -> Image.Image:
    """파티클을 PIL 이미지에 그립니다"""
    if not S.particles:
        return base
    overlay = Image.new("RGBA", (CW, CH), (0,0,0,0))
    od = ImageDraw.Draw(overlay)

    def hex2rgba(hx, a):
        h=hx.lstrip("#")
        return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16), int(a*255))

    for p in S.particles:
        ai = max(0, min(1, p.a))
        if ai < 0.02: continue
        t = p.type

        if t == "stars":
            r=max(1,int(p.rad)); c=hex2rgba(p.col,ai)
            od.ellipse([(p.x-r,p.y-r),(p.x+r,p.y+r)], fill=c)

        elif t in ("hrain","drizzle"):
            c=(180,210,255,int(.85*255)); lw=2 if t=="hrain" else 1
            od.line([(p.x,p.y),(p.x+p.vx*3,p.y+p.ln)], fill=c, width=lw)

        elif t == "snow":
            c=(220,240,255,int(.9*255)); r=max(1,int(p.rad))
            for i in range(6):
                ang=i/6*math.pi*2
                od.line([(int(p.x),int(p.y)),
                         (int(p.x+math.cos(ang)*r),int(p.y+math.sin(ang)*r))],
                        fill=c, width=1)

        elif t in ("sakura","flower"):
            c=hex2rgba(p.col,ai); r=max(2,int(p.rad))
            od.ellipse([(int(p.x-r),int(p.y-r)),(int(p.x+r),int(p.y+r))], fill=c)

        elif t == "sun":
            c=(255,220,80,max(1,int(p.a*180)))
            cx=CW//2; cy=-60
            hw=int(p.width*.4)
            pts=[(cx-hw,cy),(cx+hw,cy),
                 (int(cx+p.width*.6),int(cy+p.length)),
                 (int(cx-p.width*.6),int(cy+p.length))]
            ang=p.angle
            rpts=[(int(cx+(px-cx)*math.cos(ang)-(py-cy)*math.sin(ang)),
                   int(cy+(px-cx)*math.sin(ang)+(py-cy)*math.cos(ang)))
                  for px,py in pts]
            od.polygon(rpts, fill=c)

        elif t in ("leaf","sleaf"):
            c=hex2rgba(p.col,ai)
            hw=max(2,int(p.w*.5)); hh=max(1,int(p.h*.5))
            od.ellipse([(int(p.x-hw),int(p.y-hh)),(int(p.x+hw),int(p.y+hh))], fill=c)

        elif t == "steam":
            r=max(1,int(p.rad))
            c=(255,255,255,max(1,int(p.a*180)))
            od.ellipse([(int(p.x-r),int(p.y-r)),(int(p.x+r),int(p.y+r))], fill=c)

        elif t in ("fog2","fog"):
            r=max(1,int(p.rad*(40 if t=="fog" else 1)))
            c=(200,220,240,max(1,int(p.a*140)))
            od.ellipse([(int(p.x-r),int(p.y-r)),(int(p.x+r),int(p.y+r))], fill=c)

    if S.anim in ("fog","fog2","steam"):
        overlay=overlay.filter(ImageFilter.GaussianBlur(radius=6))
    elif S.anim in ("snow","sakura","flower"):
        overlay=overlay.filter(ImageFilter.GaussianBlur(radius=1))

    base.paste(overlay, (0,0), overlay)
    return base


# ──────────────────────────────────────────────────────────
#  텍스트 그리기
# ──────────────────────────────────────────────────────────
def draw_texts(img: Image.Image) -> Image.Image:
    draw = ImageDraw.Draw(img, "RGBA")
    sz = S.txt_size
    col_hex = S.txt_color.lstrip("#")
    cr,cg,cb = int(col_hex[0:2],16),int(col_hex[2:4],16),int(col_hex[4:6],16)

    # 폰트 로드 시도 (서버에서도 동작하는 폰트 탐색)
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/AppleGothic.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
    ]
    fnt_big = fnt_med = fnt_sm = ImageFont.load_default()
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                fnt_big = ImageFont.truetype(fp, sz)
                fnt_med = ImageFont.truetype(fp, int(sz*.78))
                fnt_sm  = ImageFont.truetype(fp, int(sz*.75))
                break
            except: pass

    def shadow_text(text, x, y, fnt, col):
        for dx,dy in [(-2,2),(2,2),(0,3)]:
            draw.text((x+dx,y+dy), text, font=fnt, fill=(0,0,0,200), anchor="mm")
        draw.text((x,y), text, font=fnt, fill=(*col,255), anchor="mm")

    y1 = sz + 30
    if S.t1:
        shadow_text(S.t1, CW//2, y1, fnt_big, (cr,cg,cb))
    if S.t2:
        y2 = y1 + int(sz*1.4) if S.t1 else y1
        shadow_text(S.t2, CW//2, y2, fnt_med, (cr,cg,cb))
    if S.t3:
        shadow_text(S.t3, CW//2, CH - 55, fnt_sm, (cr,cg,cb))
    return img


# ──────────────────────────────────────────────────────────
#  배경 이미지 붙이기 (9:16 커버)
# ──────────────────────────────────────────────────────────
def fit_image(pil_img: Image.Image) -> Image.Image:
    sc = max(CW/pil_img.width, CH/pil_img.height)
    nw,nh = int(pil_img.width*sc), int(pil_img.height*sc)
    return pil_img.resize((nw,nh), Image.LANCZOS)

def paste_img(base, imgs, idx, alpha=1.0):
    if idx<0 or idx>=len(imgs): return
    fitted = fit_image(imgs[idx].convert("RGB"))
    ox,oy = (CW-fitted.width)//2, (CH-fitted.height)//2
    if alpha >= 1.0:
        base.paste(fitted,(ox,oy))
    else:
        overlay=Image.new("RGBA",base.size,(0,0,0,0))
        tmp=fitted.convert("RGBA")
        r,g,b,a=tmp.split()
        a=a.point(lambda v:int(v*alpha))
        tmp=Image.merge("RGBA",(r,g,b,a))
        overlay.paste(tmp,(ox,oy),tmp)
        base.paste(overlay,(0,0),overlay)


# ──────────────────────────────────────────────────────────
#  한 프레임 렌더링
# ──────────────────────────────────────────────────────────
def render_frame(imgs=None, vid_frame=None, slide_prog=0.0) -> Image.Image:
    """현재 상태를 PIL Image 한 장으로 렌더링"""
    # 기본 배경
    img = Image.new("RGB",(CW,CH),"#07070f")
    draw = ImageDraw.Draw(img)
    for y in range(CH):
        v = y/CH
        r=int(6+7*v); g=int(6-1*v); b=int(15+22*v)
        draw.line([(0,y),(CW,y)],fill=(r,g,b))

    if imgs is None: imgs = S.img_list

    # 미디어 배경
    if S.mode == "images" and imgs:
        tr  = S.tr_active
        prg = min(1.0, S.tr_prog)
        prev= S.tr_prev
        idx = S.cur_idx
        trans=S.trans

        if tr and prg < 1.0:
            if trans=="fade":
                paste_img(img,imgs,prev,1.0-prg)
                paste_img(img,imgs,idx,prg)
            elif trans=="slide":
                off=int((1-prg)*CW)
                tmp=img.copy(); paste_img(tmp,imgs,prev,1.0)
                img.paste(tmp.crop((0,0,CW,CH)),(-off,0))
                paste_img(img,imgs,idx,1.0)
            elif trans=="zoom":
                paste_img(img,imgs,prev,1.0-prg)
                sc=.85+prg*.15
                if idx<len(imgs):
                    fi=fit_image(imgs[idx].convert("RGB"))
                    nw,nh=int(fi.width*sc),int(fi.height*sc)
                    fi2=fi.resize((nw,nh),Image.LANCZOS)
                    ox,oy=(CW-nw)//2,(CH-nh)//2
                    overlay=Image.new("RGBA",img.size,(0,0,0,0))
                    r2,g2,b2,a2=fi2.convert("RGBA").split()
                    a2=a2.point(lambda v:int(v*prg))
                    overlay.paste(Image.merge("RGBA",(r2,g2,b2,a2)),(ox,oy),
                                  Image.merge("RGBA",(r2,g2,b2,a2)))
                    img.paste(overlay,(0,0),overlay)
        else:
            paste_img(img,imgs,idx,1.0)

        # 전환 완료 처리
        if tr and prg>=1.0:
            S.tr_active=False

    elif S.mode=="videos" and vid_frame is not None:
        import cv2
        frame_rgb=cv2.cvtColor(vid_frame,cv2.COLOR_BGR2RGB)
        vf=Image.fromarray(frame_rgb)
        sc=max(CW/vf.width,CH/vf.height)
        nw,nh=int(vf.width*sc),int(vf.height*sc)
        vf=vf.resize((nw,nh),Image.LANCZOS)
        img.paste(vf,((CW-nw)//2,(CH-nh)//2))

    elif not imgs and S.mode=="images":
        # 빈 화면 안내
        draw = ImageDraw.Draw(img)
        draw.text((CW//2,CH//2-40),"🎬",(255,255,255,120),anchor="mm")
        draw.text((CW//2,CH//2+10),"이미지를 업로드해주세요",(180,180,200,180),anchor="mm")

    # 파티클
    update_particles()
    img = draw_particles(img)

    # 텍스트
    img = draw_texts(img)

    # 진행 바
    if slide_prog > 0 and S.mode=="images" and len(imgs)>1:
        draw2=ImageDraw.Draw(img)
        draw2.rectangle([(0,CH-6),(CW,CH)],fill=(255,255,255,30))
        bw=int(CW*slide_prog)
        if bw>0:
            draw2.rectangle([(0,CH-6),(bw,CH)],fill=(240,168,64,210))

    # 슬라이드 인디케이터 점
    if S.mode=="images" and len(imgs)>1:
        draw3=ImageDraw.Draw(img,"RGBA")
        total=len(imgs); gap=14; dot_r=4
        sx=(CW-total*gap)//2+gap//2
        for i in range(total):
            r=dot_r+2 if i==S.cur_idx else dot_r
            c=(240,168,64,220) if i==S.cur_idx else (255,255,255,80)
            draw3.ellipse([(sx+i*gap-r,CH-22-r),(sx+i*gap+r,CH-22+r)],fill=c)

    return img


# ──────────────────────────────────────────────────────────
#  동영상 내보내기 (MP4 생성)
# ──────────────────────────────────────────────────────────
def generate_video() -> bytes | None:
    """
    현재 설정으로 최대 30초 분량의 MP4를 생성해 bytes로 반환합니다.
    이미지 모드: 슬라이드쇼 / 동영상 모드: 영상 합치기
    """
    import imageio
    frames = []
    total_frames = EXPORT_SEC * FPS
    imgs = S.img_list

    progress_bar = st.progress(0, text="🎬 영상 생성 중...")

    if S.mode == "images":
        # ── 이미지 슬라이드쇼 렌더링 ──
        frames_per_slide = SLIDE_SEC * FPS
        tr_frames = int(0.7 * FPS)  # 전환 효과 프레임 수

        slide_order = list(range(len(imgs))) if imgs else [0]
        frame_count = 0

        for loop in range(100):  # 충분히 반복
            for si, img_idx in enumerate(slide_order):
                S.cur_idx = img_idx
                S.tr_active = False
                # 슬라이드 표시 구간
                for f in range(frames_per_slide):
                    prog = f / frames_per_slide
                    frame_img = render_frame(imgs, slide_prog=prog)
                    frames.append(np.array(frame_img))
                    frame_count += 1
                    progress_bar.progress(
                        min(1.0, frame_count/total_frames),
                        text=f"🎬 렌더링 중... {frame_count}/{total_frames} 프레임")
                    if frame_count >= total_frames:
                        break

                # 전환 효과
                if frame_count < total_frames and len(imgs)>1:
                    next_idx = (si+1) % len(imgs)
                    S.tr_prev = img_idx
                    S.cur_idx = next_idx
                    S.tr_active = True
                    for f in range(tr_frames):
                        S.tr_prog = f / tr_frames
                        frame_img = render_frame(imgs, slide_prog=1.0)
                        frames.append(np.array(frame_img))
                        frame_count += 1
                        if frame_count >= total_frames: break
                    S.tr_active = False

                if frame_count >= total_frames:
                    break
            if frame_count >= total_frames:
                break

    elif S.mode == "videos" and S.vid_paths:
        import cv2
        frame_count = 0
        for vid_path in S.vid_paths:
            cap = cv2.VideoCapture(vid_path)
            while True:
                ret, vframe = cap.read()
                if not ret: break
                frame_img = render_frame(vid_frame=vframe)
                frames.append(np.array(frame_img))
                frame_count += 1
                progress_bar.progress(
                    min(1.0, frame_count/total_frames),
                    text=f"🎬 렌더링 중... {frame_count}/{total_frames} 프레임")
                if frame_count >= total_frames: break
            cap.release()
            if frame_count >= total_frames: break
    else:
        # 빈 영상
        for i in range(FPS * 3):
            frames.append(np.array(render_frame()))

    if not frames:
        progress_bar.empty()
        return None

    # MP4 파일로 저장
    progress_bar.progress(0.95, text="💾 MP4 파일 변환 중...")
    buf = io.BytesIO()
    try:
        writer = imageio.get_writer(buf, format="mp4", fps=FPS,
                                    codec="libx264", quality=7,
                                    macro_block_size=8,
                                    output_params=["-pix_fmt","yuv420p"])
        for f in frames:
            writer.append_data(f)
        writer.close()
    except Exception as e:
        st.error(f"영상 생성 오류: {e}")
        progress_bar.empty()
        return None

    progress_bar.progress(1.0, text="✅ 완료!")
    time.sleep(0.5)
    progress_bar.empty()
    return buf.getvalue()


# ──────────────────────────────────────────────────────────
#  자동 새로고침 (재생 중일 때)
# ──────────────────────────────────────────────────────────
if S.playing:
    st_autorefresh(interval=300, key="play_refresh")  # 300ms마다 새로고침

    # 슬라이드 타이머
    now = time.time()
    elapsed = now - S.slide_start
    if S.mode == "images" and len(S.img_list) > 1:
        if elapsed >= SLIDE_SEC:
            prev_idx = S.cur_idx
            S.cur_idx = (S.cur_idx + 1) % len(S.img_list)
            S.tr_prev = prev_idx
            S.tr_active = True
            S.tr_prog = 0.0
            S.tr_start = now
            S.slide_start = now

    # 전환 진행
    if S.tr_active:
        tr_elapsed = now - S.tr_start
        S.tr_prog = min(1.0, tr_elapsed / 0.7)
        if S.tr_prog >= 1.0:
            S.tr_active = False


# ──────────────────────────────────────────────────────────
#  사이드바 UI
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 영상 에디터")
    st.markdown("---")

    # ── 모드 선택 ──
    st.markdown("### 📌 재생 모드")
    mode_choice = st.radio("", ["🖼️ 이미지 슬라이드", "🎬 동영상 재생"],
                           horizontal=True, label_visibility="collapsed")
    S.mode = "images" if "이미지" in mode_choice else "videos"

    st.markdown("---")

    # ── 문구 설정 ──
    with st.expander("📝 문구 설정", expanded=True):
        S.t1 = st.text_input("🔝 상단 퍼스트", value=S.t1, placeholder="상단 첫째 줄")
        S.t2 = st.text_input("🔝 상단 세컨드", value=S.t2, placeholder="상단 둘째 줄")
        S.t3 = st.text_input("🔻 하단 서드",   value=S.t3, placeholder="하단 문구")

        col1,col2 = st.columns(2)
        with col1:
            S.txt_color = st.color_picker("글자 색상", S.txt_color)
        with col2:
            S.txt_size = st.slider("글자 크기", 18, 70, S.txt_size)

    # ── 이미지 업로드 ──
    with st.expander("🖼️ 이미지 업로드 (최대 10장)", expanded=True):
        uploaded_imgs = st.file_uploader(
            "이미지 파일 선택 (9:16 비율 권장)",
            type=["jpg","jpeg","png","bmp","webp","gif"],
            accept_multiple_files=True,
            key="img_uploader"
        )
        if uploaded_imgs:
            new_imgs = []
            for f in uploaded_imgs[:MAX_IMG]:
                try:
                    new_imgs.append(Image.open(f).convert("RGB"))
                except: pass
            if new_imgs:
                S.img_list = new_imgs
                S.cur_idx = min(S.cur_idx, len(S.img_list)-1)

        st.caption(f"현재 {len(S.img_list)}장 / 최대 {MAX_IMG}장")

        if S.img_list:
            # 썸네일 미리보기
            cols = st.columns(min(5, len(S.img_list)))
            for i, (col, img) in enumerate(zip(cols, S.img_list)):
                thumb = img.copy()
                thumb.thumbnail((60,60))
                with col:
                    st.image(thumb, use_container_width=True,
                             caption=f"{'▶' if i==S.cur_idx else str(i+1)}")

        st.markdown("**슬라이드 전환 효과**")
        S.trans = st.radio("", ["fade","slide","zoom"],
                           format_func=lambda x:{"fade":"🌫 페이드","slide":"➡ 슬라이드","zoom":"🔍 줌"}[x],
                           horizontal=True, label_visibility="collapsed",
                           index=["fade","slide","zoom"].index(S.trans))

    # ── 동영상 업로드 ──
    with st.expander("🎬 동영상 업로드 (최대 5개)", expanded=False):
        uploaded_vids = st.file_uploader(
            "동영상 파일 선택 (9:16 비율 권장)",
            type=["mp4","mov","avi","mkv","webm"],
            accept_multiple_files=True,
            key="vid_uploader"
        )
        if uploaded_vids:
            # 임시 파일로 저장
            new_paths = []
            for f in uploaded_vids[:MAX_VID]:
                tmp = tempfile.NamedTemporaryFile(
                    delete=False, suffix=Path(f.name).suffix)
                tmp.write(f.read()); tmp.close()
                new_paths.append(tmp.name)
            if new_paths:
                S.vid_paths = new_paths
        st.caption(f"현재 {len(S.vid_paths)}개 / 최대 {MAX_VID}개")

    # ── 오디오 ──
    with st.expander("🎵 오디오 (내보내기에 포함)", expanded=False):
        st.markdown("**🎶 배경 음악**")
        mus_file = st.file_uploader("음악 파일", type=["mp3","wav","ogg","m4a"],
                                     key="mus_uploader")
        if mus_file:
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=Path(mus_file.name).suffix)
            tmp.write(mus_file.read()); tmp.close()
            S.mus_path=tmp.name
            st.caption(f"✅ {mus_file.name}")
        S.mus_vol = st.slider("음악 볼륨", 0.0, 1.0, S.mus_vol, 0.05)

        st.markdown("**🎙️ 나레이션**")
        nar_file = st.file_uploader("나레이션 파일", type=["mp3","wav","ogg","m4a"],
                                     key="nar_uploader")
        if nar_file:
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=Path(nar_file.name).suffix)
            tmp.write(nar_file.read()); tmp.close()
            S.nar_path=tmp.name
            st.caption(f"✅ {nar_file.name}")
        S.nar_vol = st.slider("나레이션 볼륨", 0.0, 1.0, S.nar_vol, 0.05)

    # ── 애니메이션 ──
    with st.expander("✨ 애니메이션 효과", expanded=True):
        anim_labels = [f"{lbl}" for lbl,_ in ANIMS]
        anim_ids    = [aid for _,aid in ANIMS]
        cur_ai      = anim_ids.index(S.anim) if S.anim in anim_ids else 0

        selected_ai = st.selectbox("효과 선택", anim_labels, index=cur_ai)
        new_anim    = anim_ids[anim_labels.index(selected_ai)]
        if new_anim != S.anim:
            S.anim = new_anim
            target = int(ANIM_COUNTS.get(new_anim,80))
            S.particles = [Particle(new_anim) for _ in range(target)] if new_anim!="none" else []

        S.anim_str = st.slider("효과 강도", 0.3, 2.0, S.anim_str, 0.1)


# ──────────────────────────────────────────────────────────
#  메인 영역
# ──────────────────────────────────────────────────────────
st.markdown("# 🎬 영상 에디터")

main_col, ctrl_col = st.columns([2, 1])

with main_col:
    # 현재 프레임 렌더링
    slide_prog = 0.0
    if S.playing and S.mode=="images" and len(S.img_list)>1:
        elapsed = time.time() - S.slide_start
        slide_prog = min(1.0, elapsed / SLIDE_SEC)

    current_frame = render_frame(S.img_list, slide_prog=slide_prog)

    # 미리보기 이미지 표시 (중앙 정렬)
    c1,c2,c3 = st.columns([1,2,1])
    with c2:
        st.image(current_frame, caption="📺 미리보기 (9:16)", use_container_width=True)

with ctrl_col:
    st.markdown("### ⏯ 재생 제어")

    # ── 재생/정지 ──
    if S.playing:
        if st.button("⏸ 일시정지", use_container_width=True):
            S.playing = False
            st.rerun()
    else:
        if st.button("▶ 재생", use_container_width=True):
            S.playing = True
            S.slide_start = time.time()
            st.rerun()

    # ── 이전/다음 ──
    p1, p2 = st.columns(2)
    with p1:
        if st.button("◀ 이전", use_container_width=True):
            arr = S.img_list if S.mode=="images" else S.vid_paths
            if arr:
                prev = S.cur_idx
                S.cur_idx = (S.cur_idx-1) % len(arr)
                S.tr_prev=prev; S.tr_active=True
                S.tr_prog=0.; S.tr_start=time.time()
            st.rerun()
    with p2:
        if st.button("다음 ▶", use_container_width=True):
            arr = S.img_list if S.mode=="images" else S.vid_paths
            if arr:
                prev = S.cur_idx
                S.cur_idx = (S.cur_idx+1) % len(arr)
                S.tr_prev=prev; S.tr_active=True
                S.tr_prog=0.; S.tr_start=time.time()
            st.rerun()

    st.markdown("---")
    st.markdown("### ℹ️ 현재 상태")
    arr = S.img_list if S.mode=="images" else S.vid_paths
    st.info(
        f"**모드**: {'이미지 슬라이드' if S.mode=='images' else '동영상'}\n\n"
        f"**{'이미지' if S.mode=='images' else '동영상'}**: "
        f"{S.cur_idx+1} / {len(arr) if arr else 0}\n\n"
        f"**애니메이션**: {dict(ANIMS).get(S.anim,'없음') if S.anim!='none' else '없음'}\n\n"
        f"**재생**: {'▶ 재생 중' if S.playing else '⏸ 정지'}"
    )

    st.markdown("---")
    st.markdown("### 📤 동영상 내보내기")
    st.caption(f"최대 {EXPORT_SEC}초 MP4로 저장")

    if st.button("🎬 MP4 생성 시작", use_container_width=True, type="primary"):
        video_bytes = generate_video()
        if video_bytes:
            fname = f"영상_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
            st.download_button(
                label="⬇ MP4 다운로드",
                data=video_bytes,
                file_name=fname,
                mime="video/mp4",
                use_container_width=True
            )
            st.success(f"✅ 완료! {len(video_bytes)/1024/1024:.1f}MB")

st.markdown("---")
st.caption("🎬 영상 에디터 v1.0 | 이미지·동영상·오디오·애니메이션 통합 편집기")
