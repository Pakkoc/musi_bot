// PM2 프로세스 정의 (musi_bot 스택 전용).
// 이 repo의 lavalink와 music-bot만 정의하며, 같은 PM2 데몬에 등록된 다른 봇들은 건드리지 않는다.
//
// 사용법:
//   pm2 start ecosystem.config.js   # 등록 + 기동
//   pm2 restart ecosystem.config.js # 정의 갱신해서 재시작
//   pm2 save                        # 부팅 시 복구되도록 dump.pm2에 영속화
//
// 핵심 설계:
//   - lavalink는 start-lavalink.sh 래퍼로 시작 → JVM 시작 직전에 .env를 source.
//     PM2의 env_file 옵션은 따옴표/특수문자 처리가 불안정해서, bash native source가 더 견고.
//   - music-bot은 Python의 load_dotenv()로 자체 .env 처리. 별도 env 주입 불필요.

const path = require("path");

module.exports = {
  apps: [
    {
      name: "lavalink",
      cwd: path.join(__dirname, "lavalink"),
      script: "start-lavalink.sh",
      interpreter: "bash",
      autorestart: true,
      max_restarts: 10,
      min_uptime: "30s",
      restart_delay: 5000,
    },
    {
      name: "music-bot",
      cwd: __dirname,
      script: "bot.py",
      interpreter: path.join(__dirname, "musi_bot_env/bin/python"),
      autorestart: true,
      max_restarts: 10,
      min_uptime: "30s",
      restart_delay: 5000,
    },
  ],
};
