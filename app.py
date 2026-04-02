"""
🎬 영상 에디터 — Streamlit 버전 v2.0
"""

import streamlit as st
import time, math, random, io, os, tempfile, urllib.request
from pathlib import Path

# ── 한글 폰트 자동 다운로드 ──
FONT_PATH = "/tmp/NanumGothicBold.ttf"
FONT_URL  = "https://github.com/googlefonts/nanum/raw/main/src/NanumGothic/NanumGothicBold.ttf"

@st.cache_resource
def get_font(size):
    if os.path.exists(FONT_PATH):
        try: return ImageFont.truetype(FONT_PATH, size)
        except: pass
    for fp in [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]:
        if os.path.exists(fp):
            try: return ImageFont.truetype(fp, size)
            except: pass
    try:
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        return ImageFont.truetype(FONT_PATH, size)
    except:
        return ImageFont.load_default()

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── 페이지 설정 ──────────────────────────────────────────
st.set_page_config(
    page_title="🎬 영상 에디터",
    page_icon="🎬",
    layout="wide",
)

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
.stApp { background-color: #07070f; color: #e4e4f4; }
section[data-testid="stSidebar"] { background-color: #0f0f1c; }
h1, h2, h3 { color: #f0a840 !important; }
.stButton > button {
    background: linear-gradient(135deg,#f0a840,#ff7b54) !important;
    color:#000 !important; font-weight:700 !important;
    border:none !important; border-radius:20px !important;
}
.stDownloadButton > button {
    background: linear-gradient(135deg,#44d9a0,#00b087) !important;
    color:#000 !important; font-weight:700 !important;
    border-radius:20px !important;
}
</style>
""", unsafe_allow_html=True)

# ── 상수 ─────────────────────────────────────────────────
CW, CH      = 360, 640
FPS         = 20
SLIDE_SEC   = 5
MAX_IMG     = 10
MAX_VID     = 5
EXPORT_SEC  = 30

ANIMS = [
    ("없음","none"),       ("⭐ 별빛","stars"),
    ("🌧 소나기","hrain"), ("🌂 이슬비","drizzle"),
    ("❄ 눈송이","snow"),  ("🌸 벚꽃","sakura"),
    ("🌼 작은꽃","flower"),("☀ 햇빛","sun"),
    ("🍂 낙엽","leaf"),    ("🍃 작은낙엽","sleaf"),
    ("💨 수증기","steam"), ("🌫 김서림","fog2"),
    ("🌁 안개","fog"),
]
ANIM_COUNTS = {
    "none":0,"stars":80,"hrain":120,"drizzle":70,"snow":60,
    "sakura":50,"flower":60,"sun":6,"leaf":25,"sleaf":35,
    "steam":20,"fog2":30,"fog":5,
}

# ── 세션 초기화 ───────────────────────────────────────────
def init():
    defs = {
        "mode":"images", "cur_idx":0,
        "t1":"","t2":"","t3":"",
        "txt_color":"#ffffff","txt_size":38,
        "trans":"fade",
        "anim":"none","anim_str":1.0,
        "particles":[],
        "img_list":[],
        "vid_paths":[],
        "mus_path":None,
        "nar_path":None,
    }
    for k,v in defs.items():
        if k not in st.session_state:
            st.session_state[k]=v

init()
S = st.session_state

# ── 파티클 클래스 ─────────────────────────────────────────
class P:
    def __init__(self, t):
        self.t=t; self.alive=True; r=random.random
        if t=="stars":
            self.x=r()*CW;self.y=r()*CH;self.rad=r()*2+.5
            self.a=r();self.da=(r()*.012+.003)*(1 if r()>.5 else -1)
            self.col=random.choice(["#ffffff","#fff8cc","#ffe0a0"])
        elif t in("hrain","drizzle"):
            self.x=r()*(CW+100);self.y=r()*CH
            self.vx=-2 if t=="hrain" else -.6
            self.vy=r()*10+12 if t=="hrain" else r()*4+4
            self.ln=r()*15+8 if t=="hrain" else r()*7+3
            self.a=.5 if t=="hrain" else .28
        elif t=="snow":
            self.x=r()*CW;self.y=r()*CH;self.rad=r()*8+2
            self.vx=(r()-.5)*1.2;self.vy=r()*1.2+.4
            self.a=r()*.5+.4;self.wob=r()*math.pi*2;self.ws=r()*.03
        elif t in("sakura","flower"):
            self.x=r()*CW;self.y=r()*CH;self.rad=r()*10+4
            self.vx=(r()-.5)*1.5-.5;self.vy=r()*1.5+.5
            self.a=r()*.5+.4;self.wob=r()*math.pi*2;self.ws=r()*.03
            self.col=random.choice(
                ["#ffb7c5","#ff8fab","#ffc8d5"] if t=="sakura"
                else ["#ff6b9d","#ffbe0b","#06d6a0","#3a86ff"])
        elif t=="sun":
            self.angle=r()*math.pi;self.length=r()*300+200
            self.width=r()*100+40;self.a=r()*.06+.02;self.da=(r()-.5)*.001
        elif t in("leaf","sleaf"):
            self.x=r()*CW;self.y=r()*CH
            self.w=(r()*12+4) if t=="sleaf" else (r()*25+12)
            self.h=self.w*(r()*.3+.5)
            self.vx=(r()-.5)*1.5-.5;self.vy=r()*1.5+.5
            self.a=r()*.5+.4;self.wob=r()*math.pi*2;self.ws=r()*.03
            self.col=random.choice(["#cc4400","#ff6600","#cc8800","#ff9900"])
        elif t=="steam":
            self.x=r()*CW;self.y=r()*CH;self.rad=r()*15+6
            self.vx=(r()-.5)*.5;self.vy=-(r()*1+.3);self.a=r()*.2+.07
        elif t in("fog2","fog"):
            self.x=r()*CW;self.y=r()*CH;self.rad=r()*30+10
            self.a=r()*.25+.08;self.vx=(r()-.5)*.2;self.vy=r()*.3+.04

    def update(self):
        t=self.t
        if t=="stars":
            self.a+=self.da
            if self.a>1:self.a,self.da=1.,-abs(self.da)
            if self.a<0:self.a,self.da=0.,abs(self.da)
        elif t in("hrain","drizzle"):
            self.x+=self.vx;self.y+=self.vy
            if self.y>CH+20:self.alive=False
        elif t=="snow":
            self.wob+=self.ws;self.x+=self.vx+math.sin(self.wob)*.5;self.y+=self.vy
            if self.y>CH+20:self.alive=False
        elif t in("sakura","flower"):
            self.wob+=self.ws;self.x+=self.vx+math.sin(self.wob)*.5;self.y+=self.vy
            if self.y>CH+20 or self.x<-50 or self.x>CW+50:self.alive=False
        elif t=="sun":
            self.angle+=self.da;self.a+=(random.random()-.5)*.004
            self.a=max(.01,min(.1,self.a))
        elif t in("leaf","sleaf"):
            self.wob+=self.ws;self.x+=self.vx+math.sin(self.wob);self.y+=self.vy
            if self.y>CH+30 or self.x<-50 or self.x>CW+50:self.alive=False
        elif t=="steam":
            self.x+=self.vx;self.y+=self.vy;self.rad+=.2;self.a-=.003
            if self.a<=0 or self.y<-50:self.alive=False
        elif t in("fog2","fog"):
            self.x+=self.vx;self.y+=self.vy
            if self.y>CH+50:self.alive=False

def update_particles():
    anim=S.anim
    if anim=="none":S.particles=[];return
    target=int(ANIM_COUNTS.get(anim,60)*S.anim_str)
    alive=[p for p in S.particles if p.alive]
    for p in alive:p.update()
    while len(alive)<target:alive.append(P(anim))
    S.particles=alive

def draw_particles(base):
    if not S.particles:return base
    ov=Image.new("RGBA",(CW,CH),(0,0,0,0))
    od=ImageDraw.Draw(ov)
    def h2c(hx,a):
        h=hx.lstrip("#")
        return(int(h[0:2],16),int(h[2:4],16),int(h[4:6],16),int(a*255))
    for p in S.particles:
        ai=max(0,min(1,p.a));t=p.t
        if ai<.02:continue
        if t=="stars":
            r=max(1,int(p.rad));c=h2c(p.col,ai)
            od.ellipse([(p.x-r,p.y-r),(p.x+r,p.y+r)],fill=c)
        elif t in("hrain","drizzle"):
            c=(180,210,255,int(.8*255))
            od.line([(p.x,p.y),(p.x+p.vx*2,p.y+p.ln)],fill=c,width=2 if t=="hrain" else 1)
        elif t=="snow":
            c=(220,240,255,int(.85*255));r=max(1,int(p.rad))
            for i in range(6):
                a2=i/6*math.pi*2
                od.line([(int(p.x),int(p.y)),(int(p.x+math.cos(a2)*r),int(p.y+math.sin(a2)*r))],fill=c,width=1)
        elif t in("sakura","flower"):
            c=h2c(p.col,ai);r=max(2,int(p.rad))
            od.ellipse([(int(p.x-r),int(p.y-r)),(int(p.x+r),int(p.y+r))],fill=c)
        elif t=="sun":
            c=(255,220,80,max(1,int(p.a*160)))
            cx=CW//2;cy=-60;hw=int(p.width*.4)
            pts=[(cx-hw,cy),(cx+hw,cy),(int(cx+p.width*.6),int(cy+p.length)),(int(cx-p.width*.6),int(cy+p.length))]
            ang=p.angle
            rpts=[(int(cx+(px-cx)*math.cos(ang)-(py-cy)*math.sin(ang)),
                   int(cy+(px-cx)*math.sin(ang)+(py-cy)*math.cos(ang))) for px,py in pts]
            od.polygon(rpts,fill=c)
        elif t in("leaf","sleaf"):
            c=h2c(p.col,ai);hw=max(2,int(p.w*.5));hh=max(1,int(p.h*.5))
            od.ellipse([(int(p.x-hw),int(p.y-hh)),(int(p.x+hw),int(p.y+hh))],fill=c)
        elif t in("steam","fog2","fog"):
            r=max(1,int(p.rad));c=(200,220,240,max(1,int(p.a*140)))
            od.ellipse([(int(p.x-r),int(p.y-r)),(int(p.x+r),int(p.y+r))],fill=c)
    if S.anim in("fog","fog2","steam"):
        ov=ov.filter(ImageFilter.GaussianBlur(radius=5))
    base.paste(ov,(0,0),ov)
    return base

def fit_img(im):
    sc=max(CW/im.width,CH/im.height)
    return im.resize((int(im.width*sc),int(im.height*sc)),Image.LANCZOS)

def paste_alpha(base,im,alpha):
    fitted=fit_img(im.convert("RGB"))
    ox,oy=(CW-fitted.width)//2,(CH-fitted.height)//2
    if alpha>=1.:base.paste(fitted,(ox,oy));return
    ov=Image.new("RGBA",base.size,(0,0,0,0))
    tmp=fitted.convert("RGBA")
    r2,g2,b2,a2=tmp.split()
    a2=a2.point(lambda v:int(v*alpha))
    ov.paste(Image.merge("RGBA",(r2,g2,b2,a2)),(ox,oy),Image.merge("RGBA",(r2,g2,b2,a2)))
    base.paste(ov,(0,0),ov)

def draw_texts(img):
    draw=ImageDraw.Draw(img,"RGBA")
    sz=S.txt_size
    hx=S.txt_color.lstrip("#")
    cr,cg,cb=int(hx[0:2],16),int(hx[2:4],16),int(hx[4:6],16)
    # get_font()이 한글폰트를 자동 다운로드합니다
    fnt  = get_font(sz)
    fnt2 = get_font(int(sz*.78))
    fnt3 = get_font(int(sz*.75))
    def st2(text,x,y,f,col):
        for dx,dy in[(-2,2),(2,2),(0,3)]:
            draw.text((x+dx,y+dy),text,font=f,fill=(0,0,0,190),anchor="mm")
        draw.text((x,y),text,font=f,fill=(*col,255),anchor="mm")
    if S.t1:st2(S.t1,CW//2,sz+30,fnt,(cr,cg,cb))
    if S.t2:
        y2=sz*2+50 if S.t1 else sz+30
        st2(S.t2,CW//2,y2,fnt2,(cr,cg,cb))
    if S.t3:st2(S.t3,CW//2,CH-55,fnt3,(cr,cg,cb))
    return img

def render_frame(slide_prog=0.0, tr_prog=1.0, tr_prev=0):
    img=Image.new("RGB",(CW,CH),"#07070f")
    draw=ImageDraw.Draw(img)
    for y in range(0,CH,2):
        v=y/CH
        draw.rectangle([(0,y),(CW,y+2)],fill=(int(6+7*v),5,int(15+22*v)))
    imgs=S.img_list
    if S.mode=="images" and imgs:
        idx=S.cur_idx
        if tr_prog<1. and tr_prev!=idx:
            if S.trans=="fade":
                paste_alpha(img,imgs[tr_prev],1.-tr_prog)
                paste_alpha(img,imgs[idx],tr_prog)
            elif S.trans=="slide":
                off=int((1-tr_prog)*CW)
                fp=fit_img(imgs[tr_prev].convert("RGB"))
                img.paste(fp,((CW-fp.width)//2-off,(CH-fp.height)//2))
                fn2=fit_img(imgs[idx].convert("RGB"))
                img.paste(fn2,((CW-fn2.width)//2+CW-off,(CH-fn2.height)//2))
            else:
                paste_alpha(img,imgs[tr_prev],1.-tr_prog)
                paste_alpha(img,imgs[idx],tr_prog)
        else:
            paste_alpha(img,imgs[idx],1.)
    elif S.mode=="videos" and S.vid_paths:
        try:
            import cv2
            cap=cv2.VideoCapture(S.vid_paths[S.cur_idx])
            ret,frame=cap.read();cap.release()
            if ret:
                frame_rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                vf=Image.fromarray(frame_rgb)
                sc=max(CW/vf.width,CH/vf.height)
                vf=vf.resize((int(vf.width*sc),int(vf.height*sc)),Image.LANCZOS)
                img.paste(vf,((CW-vf.width)//2,(CH-vf.height)//2))
        except:
            ImageDraw.Draw(img).text((CW//2,CH//2),"🎬 동영상",(200,200,200),anchor="mm")
    else:
        d=ImageDraw.Draw(img)
        d.text((CW//2,CH//2-20),"🎬",(100,100,120),anchor="mm")
        d.text((CW//2,CH//2+20),"이미지를 업로드해주세요",(100,100,120),anchor="mm")

    update_particles()
    img=draw_particles(img)
    img=draw_texts(img)

    if S.mode=="images" and len(imgs)>1:
        d=ImageDraw.Draw(img,"RGBA")
        total=len(imgs);gap=14;r=4
        sx=(CW-total*gap)//2+gap//2
        for i in range(total):
            rv=r+2 if i==S.cur_idx else r
            c=(240,168,64,220) if i==S.cur_idx else (255,255,255,70)
            d.ellipse([(sx+i*gap-rv,CH-22-rv),(sx+i*gap+rv,CH-22+rv)],fill=c)
    return img

def generate_mp4():
    try:
        import imageio
        imageio.plugins.ffmpeg.download()
    except:
        pass
    try:
        import imageio
    except:
        st.error("imageio 라이브러리 오류");return None

    frames=[];total=EXPORT_SEC*FPS;imgs=S.img_list
    bar=st.progress(0,"🎬 영상 생성 중...")

    if S.mode=="images" and imgs:
        spf=SLIDE_SEC*FPS;cnt=0
        for loop in range(999):
            for si in range(len(imgs)):
                S.cur_idx=si
                for f in range(spf):
                    frames.append(np.array(render_frame(slide_prog=f/spf)))
                    cnt+=1
                    bar.progress(min(1.,cnt/total),f"🎬 {cnt}/{total}")
                    if cnt>=total:break
                if cnt<total and len(imgs)>1:
                    ni=(si+1)%len(imgs);prev=si
                    for f in range(int(.4*FPS)):
                        S.cur_idx=ni
                        frames.append(np.array(render_frame(tr_prog=f/(int(.4*FPS)),tr_prev=prev)))
                        cnt+=1
                        if cnt>=total:break
                if cnt>=total:break
            if cnt>=total:break
    else:
        for i in range(FPS*5):frames.append(np.array(render_frame()))

    bar.progress(.95,"💾 MP4 변환 중...")
    buf=io.BytesIO()
    try:
        writer=imageio.get_writer(buf,format="mp4",fps=FPS,
                                   codec="libx264",quality=6,
                                   macro_block_size=8,
                                   output_params=["-pix_fmt","yuv420p"])
        for f in frames:writer.append_data(f)
        writer.close()
    except Exception as e:
        st.error(f"변환 오류: {e}");bar.empty();return None

    bar.progress(1.,"✅ 완료!");time.sleep(.4);bar.empty()

    # ── 오디오 합치기 ──────────────────────────
    video_bytes = buf.getvalue()
    mus = S.get("mus_path")
    nar = S.get("nar_path")
    if mus or nar:
        try:
            from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
            # 영상을 임시파일로 저장
            tmp_v = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp_v.write(video_bytes); tmp_v.close()
            clip = VideoFileClip(tmp_v.name)

            audio_clips = []
            if mus and os.path.exists(mus):
                m_clip = AudioFileClip(mus).volumex(S.get("mus_vol",0.7))
                # 영상 길이에 맞게 자르거나 반복
                if m_clip.duration < clip.duration:
                    from moviepy.editor import concatenate_audioclips
                    loops = int(clip.duration // m_clip.duration) + 1
                    m_clip = concatenate_audioclips([m_clip]*loops)
                audio_clips.append(m_clip.subclip(0, clip.duration))
            if nar and os.path.exists(nar):
                n_clip = AudioFileClip(nar).volumex(S.get("nar_vol",1.0))
                audio_clips.append(n_clip.subclip(0, min(n_clip.duration, clip.duration)))

            if audio_clips:
                final_audio = CompositeAudioClip(audio_clips)
                clip = clip.set_audio(final_audio)

            tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp_out.close()
            clip.write_videofile(tmp_out.name, fps=FPS, logger=None,
                                 codec="libx264", audio_codec="aac",
                                 temp_audiofile="/tmp/tmp_audio.m4a")
            with open(tmp_out.name, "rb") as fout:
                video_bytes = fout.read()
            clip.close()
            os.unlink(tmp_v.name); os.unlink(tmp_out.name)
        except Exception as e:
            st.warning(f"⚠ 오디오 합치기 실패 (영상만 저장): {e}")

    return video_bytes

# ────────────────────────────────────────────────────────
#  사이드바
# ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 영상 에디터")
    st.divider()
    st.markdown("### 📌 재생 모드")
    mc=st.radio("",["🖼️ 이미지 슬라이드","🎬 동영상 재생"],
                horizontal=True,label_visibility="collapsed")
    S.mode="images" if "이미지" in mc else "videos"
    st.divider()

    with st.expander("📝 문구 설정",expanded=True):
        S.t1=st.text_input("🔝 상단 퍼스트",value=S.t1,placeholder="상단 첫째 줄")
        S.t2=st.text_input("🔝 상단 세컨드",value=S.t2,placeholder="상단 둘째 줄")
        S.t3=st.text_input("🔻 하단 서드",value=S.t3,placeholder="하단 문구")
        c1,c2=st.columns(2)
        with c1:S.txt_color=st.color_picker("글자색",S.txt_color)
        with c2:S.txt_size=st.slider("크기",16,70,S.txt_size)

    with st.expander("🖼️ 이미지 (최대 10장)",expanded=True):
        up=st.file_uploader("이미지 선택",
                            type=["jpg","jpeg","png","bmp","webp"],
                            accept_multiple_files=True,key="iup")
        if up:
            S.img_list=[Image.open(f).convert("RGB") for f in up[:MAX_IMG]]
            S.cur_idx=min(S.cur_idx,max(0,len(S.img_list)-1))
        st.caption(f"{len(S.img_list)}장 / 최대 {MAX_IMG}장")
        if S.img_list:
            cols=st.columns(min(5,len(S.img_list)))
            for i,(col,im) in enumerate(zip(cols,S.img_list)):
                t2=im.copy();t2.thumbnail((55,55))
                with col:st.image(t2,use_container_width=True,caption="▶" if i==S.cur_idx else str(i+1))
            S.cur_idx=st.slider("현재 이미지",0,max(0,len(S.img_list)-1),S.cur_idx)
        st.markdown("**전환 효과**")
        S.trans=st.radio("",["fade","slide","zoom"],
                         format_func=lambda x:{"fade":"🌫 페이드","slide":"➡ 슬라이드","zoom":"🔍 줌"}[x],
                         horizontal=True,label_visibility="collapsed",
                         index=["fade","slide","zoom"].index(S.trans))

    with st.expander("🎬 동영상 (최대 5개)",expanded=False):
        vup=st.file_uploader("동영상 선택",
                             type=["mp4","mov","avi","mkv","webm"],
                             accept_multiple_files=True,key="vup")
        if vup:
            new_paths=[]
            for f in vup[:MAX_VID]:
                tmp=tempfile.NamedTemporaryFile(delete=False,suffix=Path(f.name).suffix)
                tmp.write(f.read());tmp.close()
                new_paths.append(tmp.name)
            S.vid_paths=new_paths
        st.caption(f"{len(S.vid_paths)}개 / 최대 {MAX_VID}개")

    with st.expander("🎵 오디오",expanded=False):
        st.caption("💡 업로드하면 MP4에 자동으로 합쳐집니다")
        mf=st.file_uploader("🎶 배경 음악",type=["mp3","wav","ogg","m4a"],key="mup")
        if mf:
            st.audio(mf)
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=Path(mf.name).suffix)
            tmp.write(mf.read()); tmp.close()
            S.mus_path=tmp.name
        S.mus_vol=st.slider("음악 볼륨",0.0,1.0,
                            S.get("mus_vol",0.7),0.05,key="mvol")
        nf=st.file_uploader("🎙️ 나레이션",type=["mp3","wav","ogg","m4a"],key="nup")
        if nf:
            st.audio(nf)
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=Path(nf.name).suffix)
            tmp.write(nf.read()); tmp.close()
            S.nar_path=tmp.name
        S.nar_vol=st.slider("나레이션 볼륨",0.0,1.0,
                            S.get("nar_vol",1.0),0.05,key="nvol")

    with st.expander("✨ 애니메이션 효과",expanded=True):
        al=[l for l,_ in ANIMS];ai2=[a for _,a in ANIMS]
        ci=ai2.index(S.anim) if S.anim in ai2 else 0
        sel=st.selectbox("효과 선택",al,index=ci)
        na=ai2[al.index(sel)]
        if na!=S.anim:
            S.anim=na
            S.particles=[P(na) for _ in range(int(ANIM_COUNTS.get(na,60)))] if na!="none" else []
        S.anim_str=st.slider("효과 강도",0.3,2.0,S.anim_str,.1)

# ────────────────────────────────────────────────────────
#  메인 화면
# ────────────────────────────────────────────────────────
st.markdown("# 🎬 영상 에디터")
left,right=st.columns([2,1])

with left:
    frame=render_frame()
    c1,c2,c3=st.columns([1,2,1])
    with c2:
        st.image(frame,caption="📺 미리보기 (9:16)",use_container_width=True)
    b1,b2,b3=st.columns(3)
    with b1:
        if st.button("◀ 이전",use_container_width=True):
            arr=S.img_list if S.mode=="images" else S.vid_paths
            if arr:S.cur_idx=(S.cur_idx-1)%len(arr)
            st.rerun()
    with b2:
        if st.button("🔄 새로고침",use_container_width=True):st.rerun()
    with b3:
        if st.button("다음 ▶",use_container_width=True):
            arr=S.img_list if S.mode=="images" else S.vid_paths
            if arr:S.cur_idx=(S.cur_idx+1)%len(arr)
            st.rerun()

with right:
    arr=S.img_list if S.mode=="images" else S.vid_paths
    st.markdown("### ℹ️ 상태")
    st.info(
        f"**모드**: {'이미지' if S.mode=='images' else '동영상'}\n\n"
        f"**현재**: {S.cur_idx+1} / {len(arr) if arr else 0}\n\n"
        f"**효과**: {dict(ANIMS).get(S.anim,'없음')}"
    )
    st.divider()
    st.markdown("### 📤 MP4 내보내기")
    st.caption(f"최대 {EXPORT_SEC}초 분량")
    if st.button("🎬 MP4 생성 시작",use_container_width=True,type="primary"):
        vb=generate_mp4()
        if vb:
            fn=f"영상_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
            st.download_button("⬇ MP4 다운로드",vb,fn,"video/mp4",use_container_width=True)
            st.success(f"✅ {len(vb)/1024/1024:.1f}MB")

st.divider()
st.caption("🎬 영상 에디터 v2.0 | AI닷 (AI DOT)")
