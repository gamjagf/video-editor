# 🎬 영상 에디터

이미지·동영상·오디오·애니메이션 효과를 합쳐서 **MP4 동영상으로 내보낼 수 있는** Streamlit 웹 앱입니다.

---

## ✨ 주요 기능

| 기능 | 내용 |
|---|---|
| **문구 입력** | 상단 퍼스트/세컨드 + 하단 서드 텍스트, 색상·크기 조절 |
| **이미지 슬라이드** | 최대 10장, 5초 간격 자동 재생, 페이드/슬라이드/줌 전환 |
| **동영상 재생** | 최대 5개 순서대로 연속 재생 |
| **오디오** | 배경 음악 + 나레이션 별도 업로드, 볼륨 조절 |
| **애니메이션** | 12가지 파티클 효과 (별빛, 소나기, 눈송이, 벚꽃 등) |
| **MP4 내보내기** | 최대 30초, 다운로드 버튼으로 즉시 저장 |

---

## 🚀 로컬 실행 방법

### 1단계 — 저장소 클론
```bash
git clone https://github.com/your-username/video-editor.git
cd video-editor
```

### 2단계 — 라이브러리 설치
```bash
pip install -r requirements.txt
```

> **ffmpeg 필요**: 동영상 내보내기를 위해 ffmpeg가 설치되어 있어야 합니다.
> - Windows: https://ffmpeg.org/download.html
> - Mac: `brew install ffmpeg`
> - Linux: `sudo apt install ffmpeg`

### 3단계 — 실행
```bash
streamlit run app.py
```

브라우저에서 자동으로 `http://localhost:8501` 이 열립니다.

---

## ☁️ Streamlit Cloud 배포 방법

### 1. GitHub에 올리기
```bash
git init
git add .
git commit -m "첫 커밋: 영상 에디터"
git branch -M main
git remote add origin https://github.com/your-username/video-editor.git
git push -u origin main
```

### 2. Streamlit Cloud에서 배포
1. [share.streamlit.io](https://share.streamlit.io) 접속
2. **GitHub 계정으로 로그인**
3. **"New app"** 클릭
4. 저장소·브랜치·파일 선택:
   - Repository: `your-username/video-editor`
   - Branch: `main`
   - Main file path: `app.py`
5. **"Deploy!"** 클릭 → 자동 배포 완료!

> `packages.txt` 파일 덕분에 ffmpeg가 서버에 자동 설치됩니다.

---

## 📁 파일 구조

```
video-editor/
│
├── app.py              ← 메인 Streamlit 앱
├── requirements.txt    ← Python 라이브러리 목록
├── packages.txt        ← 시스템 패키지 목록 (ffmpeg 등)
├── .gitignore          ← Git 제외 파일 목록
└── README.md           ← 이 파일
```

---

## 🎬 사용 방법

1. **왼쪽 사이드바**에서 이미지/동영상/오디오를 업로드
2. 문구, 색상, 애니메이션 효과 설정
3. **▶ 재생** 버튼으로 미리보기 확인
4. **🎬 MP4 생성 시작** 버튼 클릭
5. **⬇ MP4 다운로드** 버튼으로 저장

---

## 🛠 기술 스택

- **Frontend/서버**: Streamlit
- **이미지 처리**: Pillow (PIL)
- **동영상 처리**: OpenCV, imageio
- **애니메이션**: 커스텀 파티클 시스템 (순수 Python)

---

Made with ❤️ by AI닷 (AI DOT)
