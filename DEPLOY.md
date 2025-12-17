# 홈서버 배포 가이드

PM2 기반 환경에서 Lavalink v4 음악 봇 배포 방법

---

## 1. 사전 준비

### Discord Bot Token 발급

1. [Discord Developer Portal](https://discord.com/developers/applications) 접속
2. `New Application` 클릭 → 이름 입력
3. 좌측 `Bot` 메뉴 → `Add Bot`
4. `TOKEN` 복사 (나중에 `.env`에 입력)
5. **Privileged Gateway Intents** 활성화:
   - `MESSAGE CONTENT INTENT` ✅
   - `SERVER MEMBERS INTENT` ✅
   - `PRESENCE INTENT` ✅

### 봇 서버 초대

1. 좌측 `OAuth2` → `URL Generator`
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions: `Administrator` (또는 필요한 권한만)
4. 생성된 URL로 접속하여 서버에 봇 초대

---

## 2. 서버 접속

```bash
ssh s980903@192.168.0.103
# 비밀번호: qkrtjdgh0903
```

---

## 3. Java 17 설치 (Lavalink 필수)

```bash
# Java 설치
sudo apt update
sudo apt install openjdk-17-jre-headless -y

# 설치 확인
java -version
# openjdk version "17.x.x" 출력되면 성공
```

---

## 4. Lavalink 설치

```bash
# Lavalink 폴더 생성
mkdir -p ~/lavalink && cd ~/lavalink

# Lavalink.jar 다운로드
wget https://github.com/lavalink-devs/Lavalink/releases/download/4.0.8/Lavalink.jar

# application.yml 복사 (Git에서 가져온 후)
# 또는 직접 생성
nano application.yml
# (lavalink_bot/lavalink/application.yml 내용 붙여넣기)
```

---

## 5. Python 봇 설치

```bash
# 봇 폴더 생성
mkdir -p ~/discord-bot && cd ~/discord-bot

# 코드 클론 (GitHub에 올린 경우)
git clone https://github.com/YOUR_USERNAME/lavalink_bot.git
cd lavalink_bot

# 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

---

## 6. 환경 설정

```bash
# .env 파일 생성
cd ~/discord-bot/lavalink_bot
nano .env
```

```env
# .env 내용
DISCORD_TOKEN=여기에_봇_토큰_붙여넣기
LAVALINK_URI=http://localhost:2333
LAVALINK_PASSWORD=youshallnotpass
```

---

## 7. PM2로 실행

### Lavalink 실행

```bash
cd ~/lavalink
pm2 start java --name lavalink -- -jar Lavalink.jar

# 로그 확인 (OAuth 인증 URL 확인용)
pm2 log lavalink
```

### OAuth 인증 (중요!)

1. `pm2 log lavalink` 실행
2. 로그에서 Google OAuth URL 찾기
3. 해당 URL을 브라우저에서 열기
4. Google 계정으로 로그인 (봇 전용 계정 권장)
5. 로그에 "OAuth token saved" 메시지 확인

### Python 봇 실행

```bash
cd ~/discord-bot/lavalink_bot
pm2 start venv/bin/python --name music-bot -- bot.py

# 저장 (재부팅 시 자동 실행)
pm2 save
```

---

## 8. 상태 확인

```bash
pm2 list

# 예상 출력:
# ┌────┬────────────┬─────────┬─────────┬──────────┐
# │ id │ name       │ status  │ cpu     │ memory   │
# ├────┼────────────┼─────────┼─────────┼──────────┤
# │ 0  │ lavalink   │ online  │ 2%      │ 200MB    │
# │ 1  │ music-bot  │ online  │ 1%      │ 80MB     │
# └────┴────────────┴─────────┴─────────┴──────────┘
```

---

## 9. 자주 사용하는 명령어

### PM2 관리

```bash
# 로그 확인
pm2 log lavalink
pm2 log music-bot

# 재시작
pm2 restart all
pm2 restart music-bot
pm2 restart lavalink

# 중지
pm2 stop all

# 모니터링
pm2 monit
```

### 코드 업데이트

```bash
cd ~/discord-bot/lavalink_bot
git pull
source venv/bin/activate
pip install -r requirements.txt
pm2 restart music-bot
```

---

## 10. 단축키 설정 (선택)

```bash
nano ~/.bashrc
```

```bash
# 맨 아래에 추가
alias gomusic='cd ~/discord-bot/lavalink_bot'
alias golava='cd ~/lavalink'
alias musiclog='pm2 log music-bot'
alias lavalog='pm2 log lavalink'
alias restartmusic='pm2 restart lavalink && pm2 restart music-bot'
alias updatemusic='cd ~/discord-bot/lavalink_bot && git pull && pm2 restart music-bot'
```

```bash
source ~/.bashrc
```

---

## 11. 트러블슈팅

### 429 에러 발생 시

1. OAuth 인증 확인
```bash
pm2 log lavalink | grep -i oauth
```

2. 인증 만료 시 재인증
```bash
pm2 restart lavalink
# 로그에서 새 OAuth URL 확인 후 재인증
```

### 봇이 연결 안 될 때

1. Lavalink가 먼저 실행 중인지 확인
```bash
pm2 list
curl http://localhost:2333/version
```

2. 포트 확인
```bash
netstat -tlnp | grep 2333
```

### 음악이 안 나올 때

1. 봇이 음성 채널에 있는지 확인
2. 볼륨 확인 (`/볼륨 50`)
3. 로그 확인
```bash
pm2 log music-bot --lines 50
```

---

## 12. 사용 가능한 명령어

| 명령어 | 설명 |
|-------|------|
| `/재생 <검색어>` | 음악 재생 (YouTube, Spotify URL 가능) |
| `/스킵` | 다음 곡으로 넘기기 |
| `/일시정지` | 일시정지/재개 토글 |
| `/멈춰` | 정지 및 퇴장 |
| `/대기열` | 대기열 확인 |
| `/현재곡` | 현재 재생 곡 정보 |
| `/반복 <모드>` | 반복 모드 설정 |
| `/볼륨 <0-100>` | 볼륨 조절 |
| `/셔플` | 대기열 셔플 |
| `/삭제 <번호>` | 대기열에서 곡 삭제 |
| `/탐색 <초>` | 특정 위치로 이동 |
