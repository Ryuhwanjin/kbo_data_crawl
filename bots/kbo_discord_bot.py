import os
import sys

# 프로젝트 루트 경로를 sys.path에 추가하여 서브패키지 모듈 탐색이 가능하게 함
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import datetime
import re
import asyncio
import collections
import urllib.request
import json

# 1. 라이브러리 검사
try:
    import discord
    from discord.ext import tasks
    import yt_dlp
except ImportError:
    print("\n⚠️ [Error] 필요한 라이브러리가 설치되지 않았습니다. pip install discord.py PyNaCl yt-dlp로 설치해 주세요.\n")
    sys.exit(1)

# .env 환경변수 로딩 (루트 디렉토리의 .env 파일을 가리킴)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(ROOT_DIR, '.env'))
except ImportError:
    pass

# 📦 사용자 지정 플레이리스트 영속 스토리지 설정
PLAYLIST_FILE = os.path.join(ROOT_DIR, "saber_data", "user_playlists.json")

def load_user_playlist():
    if not os.path.exists(PLAYLIST_FILE):
        return []
    try:
        with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ 플레이리스트 로드 실패: {e}")
        return []

def save_user_playlist(playlist_data):
    try:
        os.makedirs(os.path.dirname(PLAYLIST_FILE), exist_ok=True)
        with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
            json.dump(playlist_data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"⚠️ 플레이리스트 저장 실패: {e}")
        return False

def clean_youtube_url(url):
    """더 이상 믹스 URL을 자르지 않고 통과시킵니다 (playlist_items에서 20곡 컷 처리)."""
    return url

from utils import kbo_idea_memo
from crawlers import kbo_news_scraper

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# 인텐트 세팅
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)

# 🎵 macOS 오디오 스트리밍을 위한 libopus 수동 로딩 설정
if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus('/opt/homebrew/lib/libopus.dylib')
        print("🟢 [Audio Engine] libopus 동적 라이브러리 로드 성공!")
    except Exception as e:
        print(f"⚠️ [Audio Engine] libopus 로드 실패: {e}. 음악 재생 기능이 제한될 수 있습니다.")

# 구단명 한글/영문 매칭 키워드 맵 (채널 분류용 정규식 패턴)
TEAM_KEYWORDS = {
    'kia-타이거즈': r'kia|기아|타이거즈|네일|김도영|양현종',
    '삼성-라이온즈': r'삼성|라이온즈|원태인|구자욱|코너',
    'lg-트윈스': r'lg|엘지|트윈스|홍창기|염경엽|손주영',
    '두산-베어스': r'두산|베어스|양의지|김택연',
    'ssg-랜더스': r'ssg|쓱|랜더스|최정|김광현',
    '롯데-자이언츠': r'롯데|자이언츠|황성빈|윤동희',
    '한화-이글스': r'한화|이글스|류현진|노시환',
    'kt-위즈': r'kt|케이티|위즈|강백호|고영표',
    '키움-히어로즈': r'키움|히어로즈|송성문|후라도',
    'nc-다이노스': r'nc|엔씨|다이노스|박건우|데이비슨'
}

# 🎵 유튜브 재생 및 스트리밍 오디오 셋업
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        url = clean_youtube_url(url)
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if not data:
            raise RuntimeError("유튜브 오디오 데이터(None)를 불러오는데 실패했습니다.")
            
        if 'entries' in data:
            entries = [e for e in data['entries'] if e is not None]
            if not entries:
                raise RuntimeError("플레이리스트 내에 재생 가능한 곡이 없습니다.")
            data = entries[0]

        filename = data.get('url') or data.get('webpage_url')
        if not filename:
            raise RuntimeError("유튜브 오디오 스트림 URL을 획득하지 못했습니다.")
            
        return cls(discord.FFmpegPCMAudio(filename, executable='/opt/homebrew/bin/ffmpeg', **ffmpeg_options), data=data)

music_queues = collections.defaultdict(list)

def play_next_song(guild_id, voice_client, channel_to_notify):
    if music_queues[guild_id]:
        next_song = music_queues[guild_id].pop(0)
        
        async def async_play():
            try:
                if not next_song.get('source'):
                    source = await YTDLSource.from_url(next_song['url'], loop=client.loop, stream=True)
                    next_song['source'] = source
                
                def after_playing(error):
                    if error:
                        print(f"❌ 재생 중 오류 발생: {error}")
                    client.loop.call_soon_threadsafe(play_next_song, guild_id, voice_client, channel_to_notify)
                
                voice_client.play(next_song['source'], after=after_playing)
                
                embed = discord.Embed(
                    title="🎵 지금 재생 중",
                    description=f"[{next_song['title']}]({next_song['url']})",
                    color=0x10B981
                )
                await channel_to_notify.send(embed=embed)
            except Exception as e:
                await channel_to_notify.send(f"❌ '{next_song['title']}' 재생 실패: {e}")
                play_next_song(guild_id, voice_client, channel_to_notify)
                
        client.loop.create_task(async_play())
    else:
        client.loop.create_task(channel_to_notify.send("📭 모든 대기곡 재생이 끝났습니다."))

# ---------------------------------------------------------------------------
# 💾 중복 전송 방지 로컬 JSON 캐시 관리 (posted_links.json)
# ---------------------------------------------------------------------------
CACHE_DIR = "saber_data"
CACHE_FILE = os.path.join(CACHE_DIR, "posted_links.json")

def load_posted_links():
    """이미 송출 완료된 뉴스 링크 세트를 파일에서 로드"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)
    if not os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
        return set()
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data)
    except Exception as e:
        print(f"⚠️ 중복 캐시 로딩 실패: {e}")
        return set()

def save_posted_link(link):
    """새로운 링크를 중복 방지 캐시에 영구 기록"""
    links = load_posted_links()
    if link not in links:
        links.add(link)
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(list(links), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 중복 캐시 저장 실패: {e}")

# 📰 뉴스 라우팅 및 시간 정밀 분석 유틸리티
def route_news_channel(title, summary, channels):
    text_to_scan = (title + " " + summary).lower()
    for chan_name, pattern in TEAM_KEYWORDS.items():
        if re.search(pattern, text_to_scan):
            target_chan = find_channel_by_name(chan_name, channels)
            if target_chan:
                return target_chan
    return find_channel_by_name("kbo", channels)

def find_channel_by_name(name, channels):
    clean_target = name.replace("-", "").replace(" ", "").lower()
    for c in channels:
        if isinstance(c, discord.TextChannel):
            clean_chan = c.name.replace("-", "").replace(" ", "").lower()
            if clean_target in clean_chan or clean_chan in clean_target:
                return c
    return None

def parse_article_datetime(date_str):
    """뉴스 게시 날짜 문자열을 datetime 객체로 변환 (24시간 필터링용)"""
    if not date_str:
        return datetime.datetime.now()
    clean_str = date_str.strip()
    
    # 1) YYYY-MM-DD HH:MM (네이버 및 엠파 표준)
    try:
        return datetime.datetime.strptime(clean_str, "%Y-%m-%d %H:%M")
    except ValueError:
        pass
        
    # 2) YYYY.MM.DD HH:MM (점 구분자 포함 시분 포맷)
    try:
        clean_date = clean_str.replace(".", "-")
        return datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M")
    except ValueError:
        pass
    
    # 3) YYYY.MM.DD 또는 YYYY-MM-DD (KBO 공식 포맷 - 시간 없음)
    try:
        clean_date = clean_str.replace(".", "-")
        return datetime.datetime.strptime(clean_date, "%Y-%m-%d")
    except ValueError:
        pass
        
    # 기본 방어: 파싱 실패 시 현재 시각으로 간주
    return datetime.datetime.now()

async def broadcast_daily_issues(guild):
    """다중 KBO 소스를 수집하여 24시간 시각 필터링 및 중복 차단을 거쳐 최대 5개씩 송출"""
    channels = guild.text_channels
    kbo_channel = find_channel_by_name("kbo", channels)
    
    print(f"📰 [News Router] 서버 '{guild.name}' 내 KBO & Naver & MLBPark 수집 및 24시간/중복 필터 분류...")
    kbo_news = kbo_news_scraper.scrape_kbo_official()
    naver_news = kbo_news_scraper.scrape_naver_news()
    mlb_news = kbo_news_scraper.scrape_mlbpark()
    
    posted_links = load_posted_links()
    now = datetime.datetime.now()
    
    # 10개 구단 및 KBO 채널별 뉴스 바스켓 (Bucket)
    buckets = collections.defaultdict(list)
    stats = collections.defaultdict(int)
    
    # 세 뉴스 소스를 병합하여 단일 기사 리스트 빌드
    all_raw_news = []
    if kbo_news:
        all_raw_news.extend(kbo_news)
    if naver_news:
        all_raw_news.extend(naver_news)
    if mlb_news:
        all_raw_news.extend(mlb_news)
        
    # 기사 정밀 필터링 (중복 체크 & 최근 24시간 이내 기사 판정)
    filtered_news = []
    for item in all_raw_news:
        link = item.get('link', '')
        # 1. 중복 캐시 대조 필터링
        if link in posted_links:
            continue
            
        # 2. scrape 실행 시각 기준 최근 24시간 이내 기사 판정 (Recency Filter)
        pub_time = parse_article_datetime(item.get('date', ''))
        # 시각차가 24시간(86400초)을 초과한 과거 기사만 스킵하고 최신 기사는 보존
        time_diff = now - pub_time
        if time_diff.total_seconds() > 86400:
            continue
            
        filtered_news.append(item)
        
    # 필터 통과한 안전한 최신 기사들을 버킷 분류 적재
    for item in filtered_news:
        dest_chan = route_news_channel(item['title'], item['summary'], channels)
        target = dest_chan if dest_chan else kbo_channel
        if target:
            buckets[target].append(item)

    # 4. 버킷 순회하며 채널별 최대 5개 기사 송출
    posted_kbo = 0
    posted_naver = 0
    posted_mlb = 0
    
    for chan, items in buckets.items():
        # 중요도(별점 개수) 기준 내림차순 정렬
        sorted_items = sorted(items, key=lambda x: len(x.get('importance', '★★★☆☆')), reverse=True)
        
        # 구단별 최대 10개 뉴스 선별 (풍부한 자료 수신용)
        top_items = sorted_items[:10]
        
        for item in top_items:
            # 뉴스 테마별 아이콘 및 분류명 지정
            icon = "📢" if item['source'] == "KBO 공식" else ("⚡" if item['source'] == "네이버" else "🔥")
            tag_name = "공식" if item['source'] == "KBO 공식" else (item.get('office', '속보') if item['source'] == "네이버" else "엠파")
            
            # 중요도 표시 및 타이틀 빌드
            stars = item.get('importance', '★★★☆☆')
            title_text = f"[{stars}] {icon} [{tag_name}] {item['title']}"
            
            # Embed 카드 렌더링
            embed = discord.Embed(
                title=title_text[:256],
                description=item['summary'],
                url=item['link'],
                color=0xEA580C if item['source'] == "엠엘비파크" else (0x070A13 if item['source'] == "KBO 공식" else 0x1E293B),
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text=f"KBO Curation | {item['date']}")
            
            await chan.send(embed=embed)
            stats[chan.name] += 1
            
            # 송출 성공한 링크는 중복 캐시에 기록하여 영구 중복 방지
            save_posted_link(item['link'])
            
            # 전체 통계 카운트 증가
            if item['source'] == "KBO 공식":
                posted_kbo += 1
            elif item['source'] == "네이버":
                posted_naver += 1
            else:
                posted_mlb += 1
                
            # 만약 타겟이 구단 채널이고 kbo 공식 뉴스라면, 기본 KBO 채널에도 아카이빙 전송
            if chan != kbo_channel and item['source'] == "KBO 공식" and kbo_channel:
                await kbo_channel.send(embed=embed)
                stats[kbo_channel.name] += 1

    return {
        "kbo_fetched": len(kbo_news) if kbo_news else 0,
        "naver_fetched": len(naver_news) if naver_news else 0,
        "mlb_fetched": len(mlb_news) if mlb_news else 0,
        "kbo_posted": posted_kbo,
        "naver_posted": posted_naver,
        "mlb_posted": posted_mlb,
        "stats": dict(stats)
    }

# ---------------------------------------------------------------------------
# ⏰ 백그라운드 자동화 스케줄러 (Auto-Scheduler)
# ---------------------------------------------------------------------------
# live game states 캐시용 딕셔너리
game_states_cache = {}

async def fetch_today_games(date_str):
    url = f"https://api-gw.sports.naver.com/schedule/games?upperCategoryId=kbaseball&fromDate={date_str}&toDate={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://sports.news.naver.com/kbaseball/schedule/index"
    }
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("result", {}).get("games", [])
    except Exception as e:
        print(f"⚠️ [Schedule API] 호출 에러: {e}")
    return []

@tasks.loop(minutes=1)
async def auto_news_scraper():
    """매 분마다 현재 시각을 검사하여 지정된 시간(08:30, 18:30)에 뉴스 배포 트리거"""
    now = datetime.datetime.now()
    current_time_str = now.strftime("%H:%M")
    
    if current_time_str in ["08:30", "18:30"]:
        print(f"⏰ [Scheduler] 예약 지정 시각 ({current_time_str}) 도달 ➡️ 무인 배포를 시작합니다.")
        for guild in client.guilds:
            try:
                channels = guild.text_channels
                kbo_chan = find_channel_by_name("kbo", channels)
                if not kbo_chan:
                    print(f"⚠️ [Scheduler] 서버 '{guild.name}' 내에 #kbo 채널이 없습니다. 배포를 생략합니다.")
                    continue
                    
                result = await broadcast_daily_issues(guild)
                
                # 통계 리포트 카드 전송
                embed = discord.Embed(
                    title=f"📅 [정기 브리핑] {current_time_str} 야구 소식 요약",
                    description=f"{now.strftime('%Y년 %m월 %d일')} 아침/저녁 정기 브리핑이 성공적으로 무인 완료되었습니다.",
                    color=0x3B82F6
                )
                embed.add_field(name="KBO 소식", value=f"`{result['kbo_posted']}건` 송출", inline=True)
                embed.add_field(name="Naver 속보", value=f"`{result['naver_posted']}건` 송출", inline=True)
                embed.add_field(name="MLBPark 트렌드", value=f"`{result['mlb_posted']}건` 송출", inline=True)
                
                channels_text = ""
                for ch_name, count in result['stats'].items():
                    channels_text += f"• `#{ch_name}`: **{count}건**\n"
                if not channels_text:
                    channels_text = "• 송출 내역 없음"
                embed.add_field(name="📋 배포 상세 내역", value=channels_text, inline=False)
                
                await kbo_chan.send(embed=embed)
                print(f"✅ [Scheduler] 서버 '{guild.name}' 브리핑 완료!")
            except Exception as e:
                print(f"❌ [Scheduler] 서버 '{guild.name}' 배포 중 오류 발생: {e}")

@tasks.loop(minutes=3)
async def track_live_games():
    """3분마다 오늘 진행 중인 경기 상태를 조회하여, 종료/취소 상태 변화 시 디스코드 알림 발송"""
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # 05:00 ~ 23:59 시간대에만 활성화 (일반적으로 야구 경기 진행 시간대)
    if now.hour < 5 or now.hour > 23:
        return
        
    games = await fetch_today_games(today_str)
    kbo_games = [g for g in games if g.get("categoryId") == "kbo"]
    
    for g in kbo_games:
        game_id = g.get("gameId")
        if not game_id:
            continue
            
        home = g.get("homeTeamName", "홈")
        away = g.get("awayTeamName", "원정")
        home_score = g.get("homeTeamScore", 0)
        away_score = g.get("awayTeamScore", 0)
        status_code = g.get("statusCode", "BEFORE")
        status_info = g.get("statusInfo", "")
        is_cancelled = g.get("cancel", False)
        
        prev = game_states_cache.get(game_id)
        
        # 1. 경기 취소 감지
        if (is_cancelled or status_info == "경기취소") and (not prev or not prev.get("cancelled")):
            game_states_cache[game_id] = {"cancelled": True, "status": "CANCEL"}
            
            for guild in client.guilds:
                kbo_chan = find_channel_by_name("kbo", guild.text_channels)
                if kbo_chan:
                    embed = discord.Embed(
                        title=f"🌧️ [우천 취소 알림] {away} vs {home}",
                        description=f"오늘 예정된 **{away} vs {home}** 경기가 우천 등의 사유로 취소되었습니다.",
                        color=0x9CA3AF,
                        timestamp=datetime.datetime.utcnow()
                    )
                    await kbo_chan.send(embed=embed)
            continue
            
        # 2. 경기 종료 감지
        if status_code == "RESULT" and (not prev or prev.get("status") != "RESULT"):
            game_states_cache[game_id] = {"cancelled": False, "status": "RESULT"}
            
            winner = g.get("winner", "DRAW")
            if winner == "HOME":
                w_text = f"🏆 승리: **{home}**"
            elif winner == "AWAY":
                w_text = f"🏆 승리: **{away}**"
            else:
                w_text = "🤝 무승부"
                
            for guild in client.guilds:
                kbo_chan = find_channel_by_name("kbo", guild.text_channels)
                if kbo_chan:
                    embed = discord.Embed(
                        title=f"🏁 [경기 종료 알림] {away} vs {home}",
                        description=f"**{away} {away_score} : {home_score} {home}**\n\n{w_text}",
                        color=0x10B981,
                        timestamp=datetime.datetime.utcnow()
                    )
                    embed.set_footer(text=f"구장: {g.get('stadium', 'KBO 경기장')} | 종료 정보: {status_info}")
                    await kbo_chan.send(embed=embed)
                    
            # 3. 경기 종료 즉시 daily_kbo_updater를 가동하여 증분 수집 및 파이프라인 갱신 (비동기 subprocess)
            print(f"⚙️ [{game_id}] 경기 종료 감지됨 ➡️ daily_kbo_updater 가동을 시도합니다.")
            import subprocess
            try:
                subprocess.Popen([sys.executable, "utils/daily_kbo_updater.py", "--days", "3"])
            except Exception as e:
                print(f"⚠️ [Scheduler] daily_kbo_updater 가동 실패: {e}")
                
        # 4. 경기 상태 기록 갱신
        if status_code == "RUNNING" and (not prev or prev.get("status") != "RUNNING"):
            game_states_cache[game_id] = {"cancelled": False, "status": "RUNNING"}

# 🤖 디스코드 이벤트 핸들러
@client.event
async def on_ready():
    print("==================================================")
    print(f"🤖 [KBO Discord Bot] 로그인 성공: {client.user.name}")
    print("🟢 디스코드 11개 구단 뉴스 라우팅 및 기획 비서 탑재 완료")
    print("🟢 유튜브 플레이리스트 및 초고속 레이지 로딩 재생 엔진 탑재 완료!")
    
    # 백그라운드 스케줄러 기동 시작!
    if not auto_news_scraper.is_running():
        auto_news_scraper.start()
        print("⏰ 백그라운드 무인 브리핑 스케줄러(08:30 / 18:30) 가동 완료!")
        
    if not track_live_games.is_running():
        track_live_games.start()
        print("⏰ 백그라운드 실시간 경기 모니터링(3분 주기) 가동 완료!")
    print("==================================================")

@client.event
async def on_message(message):
    # 디스코드 게이트웨이 수신 확인용 로그 프린트
    print(f"📥 [Msg Received] {message.author.name} (ID: {message.author.id}): '{message.content}'")
    
    if message.author == client.user:
        return
        
    content = message.content.strip()
    guild_id = message.guild.id if message.guild else None
    
    # 🎵 음악 전용 채널 격리 가드 로직
    music_commands = [
        "!join", "!leave", "!stop", "!play", "!play_saved", "!pls",
        "!skip", "!pause", "!resume", "!queue", "!q", "!remove",
        "!del", "!clear", "!shuffle"
    ]
    is_music_cmd = False
    for cmd in music_commands:
        if content == cmd or content.startswith(cmd + " "):
            is_music_cmd = True
            break
            
    if is_music_cmd:
        channel_name = message.channel.name if hasattr(message.channel, "name") else ""
        if not ("음악" in channel_name or "music" in channel_name):
            await message.channel.send("⚠️ 음악 관련 명령어는 **`#음악`** 채널에서만 사용하실 수 있습니다.")
            return
    
    # 💡 글감 메모 기능
    if content.startswith("!add "):
        idea_text = content[5:].strip()
        if not idea_text:
            await message.channel.send("⚠️ 등록할 내용을 기입하세요.")
            return
        kbo_idea_memo.add_idea(idea_text)
        ideas = kbo_idea_memo.load_ideas()
        new_id = ideas[-1]['id'] if ideas else 1
        
        embed = discord.Embed(
            title="💡 KBO 글감 아이디어 추가 완료",
            description=f"**ID {new_id}**번 아이디어가 메모장 및 `ideas.md`에 실시간 컴파일되어 저장되었습니다.",
            color=0x10B981
        )
        embed.add_field(name="내용", value=f"\"{idea_text}\"", inline=False)
        await message.channel.send(embed=embed)

    elif content in ["!list", "!todo"]:
        ideas = kbo_idea_memo.load_ideas()
        todo_ideas = [i for i in ideas if i.get("status") == "TODO"]
        if not todo_ideas:
            await message.channel.send("📭 대기 중인 TODO 기획이 없습니다.")
            return
            
        embed = discord.Embed(
            title="📋 KBO 대기 중인 TODO 리스트",
            description=f"현재 총 **{len(todo_ideas)}개**의 미완료 글감 아이디어가 남아있습니다.",
            color=0xF59E0B
        )
        list_text = "".join(f"`ID {item['id']}` - **{item['text']}**\n" for item in todo_ideas)
        embed.add_field(name="해야 할 일 / 글감 목록", value=list_text, inline=False)
        await message.channel.send(embed=embed)

    elif content.startswith("!done "):
        id_str = content[6:].strip()
        try:
            idea_id = int(id_str)
        except ValueError:
            await message.channel.send("⚠️ 올바른 메모 ID 번호를 입력하세요.")
            return
        ideas = kbo_idea_memo.load_ideas()
        found = False
        for i in ideas:
            if i.get("id") == idea_id:
                i["status"] = "DONE"
                found = True
                kbo_idea_memo.save_ideas(ideas)
                await message.channel.send(f"✅ **ID {idea_id}**번 아이디어가 완료 처리되고 `ideas.md`가 갱신되었습니다.")
                break
        if not found:
            await message.channel.send("❌ 해당 ID를 찾지 못했습니다.")

    # 📰 자동 채널 셋업 및 뉴스 크롤러 (기존 중복 채널 일괄 Clean 후 Rebuild)
    elif content == "!setup":
        guild = message.guild
        if not guild:
            await message.channel.send("⚠️ 서버에서만 사용할 수 있는 명령어입니다.")
            return
            
        await message.channel.send("🧹 디스코드 KBO 카테고리 및 중복 채널의 일괄 청소(Clean)를 시작합니다...")
        
        categories_to_clean = ["KBO 브리핑 센터", "💡 아이디어 메모장"]
        deleted_channels_count = 0
        
        for cat_name in categories_to_clean:
            matched_categories = [c for c in guild.categories if c.name == cat_name]
            for cat in matched_categories:
                for chan in cat.text_channels:
                    try:
                        await chan.delete()
                        deleted_channels_count += 1
                    except Exception as e:
                        print(f"⚠️ 채널 삭제 에러 ({chan.name}): {e}")
                try:
                    await cat.delete()
                except Exception as e:
                    print(f"⚠️ 카테고리 삭제 에러 ({cat.name}): {e}")
                    
        await message.channel.send(f"✅ 기존 KBO 카테고리 및 채널 `{deleted_channels_count}개` 청소 완료. 신규 셋업을 시작합니다...")

        try:
            # ── KBO 브리핑 센터 카테고리 및 구단 채널 생성
            category_name = "KBO 브리핑 센터"
            category = await guild.create_category(category_name)
            
            channels_to_create = ["kbo", "음악"] + list(TEAM_KEYWORDS.keys())
            created = 0
            for chan_name in channels_to_create:
                await guild.create_text_channel(chan_name, category=category)
                created += 1

            # ── 💡 개인 아이디어 메모장 카테고리 및 채널 생성
            memo_category_name = "💡 아이디어 메모장"
            memo_category = await guild.create_category(memo_category_name)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                message.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            }
            memo_chan = await guild.create_text_channel(
                "아이디어-메모장",
                category=memo_category,
                topic="✏️ 개인 아이디어 & 기획 메모장 | !add / !list / !done / !memo",
                overwrites=overwrites
            )
            created += 1

            # 신규 메모장 채널에 Welcome embed 발송
            welcome_embed = discord.Embed(
                title="✏️ 아이디어 메모장 채널에 오신 것을 환영합니다!",
                description="이곳은 **개인 전용** 아이디어 & 기획 메모 공간입니다.\n자유롭게 떠오르는 생각을 기록해 보세요! 💭",
                color=0x8B5CF6
            )
            welcome_embed.add_field(
                name="📝 사용 가능한 명령어",
                value=(
                    "`!add [내용]` — 새 아이디어 메모 등록\n"
                    "`!list` — 미완료(TODO) 아이디어 전체 조회\n"
                    "`!done [ID]` — 해당 ID 아이디어 완료 처리\n"
                    "`!memo` — 이 채널 도움말 다시 보기"
                ),
                inline=False
            )
            welcome_embed.add_field(
                name="🔒 채널 공개 범위",
                value="이 채널은 **비공개** 설정입니다. 서버의 다른 멤버에게 보이지 않습니다.",
                inline=False
            )
            welcome_embed.set_footer(text="💡 아이디어가 떠오를 때마다 !add 로 바로 기록하세요!")
            await memo_chan.send(embed=welcome_embed)

            await message.channel.send(
                f"🎉 셋업 성공! `{created}개` 채널이 새로 연결되었습니다.\n"
                f"💡 개인 아이디어 메모장: {memo_chan.mention} (비공개 채널)"
            )
        except discord.Forbidden:
            await message.channel.send("❌ 봇의 권한(Manage Channels)이 부족합니다.")
        except Exception as e:
            await message.channel.send(f"❌ 오류 발생: {e}")

    elif content == "!scrape":
        if not message.guild:
            await message.channel.send("⚠️ 서버에서만 실행할 수 있습니다.")
            return
        await message.channel.send("🔄 KBO 뉴스를 긁어와 각 구단 채널로 분기 송출을 시작합니다...")
        try:
            result = await broadcast_daily_issues(message.guild)
            
            # 통계 리포트 카드 빌드
            embed = discord.Embed(
                title="✅ 뉴스 다중 채널 라우팅 배포 완료",
                description="수집 및 채널별 배포가 성공적으로 완료되었습니다.",
                color=0x10B981
            )
            embed.add_field(name="KBO 수집/송출", value=f"`{result['kbo_fetched']}건` / `{result['kbo_posted']}건`", inline=True)
            embed.add_field(name="Naver 수집/송출", value=f"`{result['naver_fetched']}건` / `{result['naver_posted']}건`", inline=True)
            embed.add_field(name="MLBPark 수집/송출", value=f"`{result['mlb_fetched']}건` / `{result['mlb_posted']}건`", inline=True)
            
            channels_text = ""
            if result['stats']:
                for ch_name, count in result['stats'].items():
                    channels_text += f"• `#{ch_name}`: **{count}건** 전송\n"
            else:
                channels_text = "• 송출된 채널이 없습니다. (모든 기사가 중복 캐시에 있거나 24시간이 지났습니다.)"
                
            embed.add_field(name="📋 채널별 배포 상세 내역", value=channels_text, inline=False)
            embed.set_footer(text="실시간 야구 브리핑 서비스 정상 가동 중")
            await message.channel.send(embed=embed)
        except Exception as e:
            await message.channel.send(f"❌ 배포 실패: {e}")

    elif content.startswith("!predict "):
        args = content[9:].strip().split()
        if len(args) < 2:
            await message.channel.send("⚠️ 사용법: `!predict [원정팀] [홈팀]` (예: `!predict KIA 삼성`)")
            return
        away_arg, home_arg = args[0], args[1]
        
        from simulation.kbo_match_simulator import TEAM_NAME_MAP
        away_team = TEAM_NAME_MAP.get(away_arg)
        home_team = TEAM_NAME_MAP.get(home_arg)
        
        if not home_team or not away_team:
            await message.channel.send(f"❌ 올바른 팀 이름을 기입해 주세요. (입력 원정: {away_arg}, 홈: {home_arg})")
            return
            
        await message.channel.send(f"🔮 **{away_team} vs {home_team}** 경기 예측 몬테카를로 시뮬레이션(1,000회) 가동 중...")
        try:
            import subprocess
            cmd = [sys.executable, "simulation/kbo_match_simulator.py", "--away", away_team, "--home", home_team, "--sims", "1000"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=ROOT_DIR
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8')
            
            if proc.returncode != 0:
                await message.channel.send(f"❌ 시뮬레이션 에러: {stderr.decode('utf-8')}")
                return
                
            embed = discord.Embed(
                title=f"🔮 KBO 경기 예측 결과 보고서: {away_team} vs {home_team}",
                color=0x4F46E5,
                timestamp=datetime.datetime.utcnow()
            )
            
            lines = output.split('\n')
            report_lines = []
            capture = False
            for line in lines:
                if "==================================================" in line:
                    if not capture:
                        capture = True
                        continue
                    else:
                        break
                if capture:
                    report_lines.append(line.strip())
                    
            if report_lines:
                embed.description = "\n".join(report_lines)
            else:
                embed.description = f"```text\n{output[-2000:]}\n```"
                
            embed.set_footer(text="몬테카를로 마르코프체인 예측 시뮬레이터 v1.0")
            await message.channel.send(embed=embed)
        except Exception as e:
            await message.channel.send(f"❌ 시뮬레이션 실패: {e}")

    elif content.startswith("!chart "):
        args = content[7:].strip().split()
        if not args:
            await message.channel.send("⚠️ 사용법: `!chart [선수명] [연도]` (예: `!chart 박건우 2024` 또는 `!chart 주현상`)")
            return
        player_name = args[0]
        year = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
        
        await message.channel.send(f"📊 **{player_name}** 선수의 데이터 분석 차트를 생성하고 있습니다. 잠시만 기다려 주세요...")
        
        try:
            import pandas as pd
            import subprocess
            player_type = None
            for y in [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017]:
                bat_csv = os.path.join(ROOT_DIR, "saber_data", f"kbo_batter_saber_{y}.csv")
                pit_csv = os.path.join(ROOT_DIR, "saber_data", f"kbo_pitcher_saber_{y}.csv")
                if os.path.exists(bat_csv):
                    df = pd.read_csv(bat_csv)
                    if player_name in df['Player'].values:
                        player_type = "batter"
                        break
                if os.path.exists(pit_csv):
                    df = pd.read_csv(pit_csv)
                    if player_name in df['Player'].values:
                        player_type = "pitcher"
                        break
                        
            if not player_type:
                player_type = "batter"
                
            cmd = [sys.executable, "visualization/naver_kbo_visualizer.py"]
            if player_type == "batter":
                cmd.extend(["--batter", player_name])
            else:
                cmd.extend(["--pitcher", player_name])
                
            if year:
                cmd.extend(["--year", str(year)])
                
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=ROOT_DIR
            )
            stdout, stderr = await proc.communicate()
            
            suffix = f"_{year}" if year else ""
            chart_type = "spray_chart" if player_type == "batter" else "pitch_chart"
            img_filename = f"{player_name}{suffix}_{chart_type}.png"
            img_path = os.path.join(ROOT_DIR, "kbo_data", img_filename)
            
            if os.path.exists(img_path):
                file = discord.File(img_path, filename=img_filename)
                embed = discord.Embed(
                    title=f"📊 KBO 스탯캐스트 분석: {player_name} " + (f"({year}년)" if year else "(전체 시즌)"),
                    color=0x10B981
                )
                embed.set_image(url=f"attachment://{img_filename}")
                embed.set_footer(text="PTS 스트라이크 존 등고선 및 스프레이 시각화 엔진")
                await message.channel.send(file=file, embed=embed)
                
                os.remove(img_path)
            else:
                err_msg = stderr.decode('utf-8')
                await message.channel.send(f"❌ 차트 생성 실패: 해당 선수의 데이터 표본이 없거나 올바르지 않은 선수명입니다.\n`{err_msg[:200]}`")
        except Exception as e:
            await message.channel.send(f"❌ 에러 발생: {e}")

    elif content == "!today":
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        await message.channel.send(f"📅 **{today_str}** KBO 오늘 일정 및 스코어 상황을 조회하는 중...")
        try:
            games = await fetch_today_games(today_str)
            kbo_games = [g for g in games if g.get("categoryId") == "kbo"]
            if not kbo_games:
                await message.channel.send(f"📅 **{today_str}** 예정된 KBO 경기 일정이 존재하지 않습니다.")
                return
                
            embed = discord.Embed(
                title=f"📅 {today_str} KBO 경기 대진표 & 스코어",
                color=0x3B82F6,
                timestamp=datetime.datetime.utcnow()
            )
            
            schedule_text = ""
            for g in kbo_games:
                time_part = g.get("gameDateTime", "T18:30:00").split("T")[-1][:5]
                status_info = g.get("statusInfo", "")
                is_cancelled = g.get("cancel", False)
                
                home = g.get("homeTeamName", "홈")
                away = g.get("awayTeamName", "원정")
                
                if is_cancelled or status_info == "경기취소":
                    schedule_text += f"• `[{time_part}]` **{away} vs {home}** ➡️ 🌧️ **경기 취소**\n"
                elif g.get("statusCode") == "RESULT":
                    schedule_text += f"• `[{time_part}]` **{away} {g.get('awayTeamScore')} vs {g.get('homeTeamScore')} {home}** ➡️ 🏁 **종료**\n"
                elif g.get("statusCode") == "RUNNING":
                    schedule_text += f"• `[{time_part}]` **{away} {g.get('awayTeamScore')} vs {g.get('homeTeamScore')} {home}** ➡️ ⚡ **경기 중 ({status_info})**\n"
                else:
                    schedule_text += f"• `[{time_part}]` **{away} vs {home}** ➡️ ⏳ **대기 중**\n"
                    
            embed.description = schedule_text
            embed.set_footer(text="실시간 경기 일정 & 스코어 알림 서비스")
            await message.channel.send(embed=embed)
        except Exception as e:
            await message.channel.send(f"❌ 일정 조회 실패: {e}")

    # 🎵 음악 재생 기능
    elif content == "!join":
        if not message.author.voice:
            await message.channel.send("⚠️ 먼저 음성 채널에 들어가 계셔야 봇을 부를 수 있습니다!")
            return
        voice_channel = message.author.voice.channel
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client:
            await voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()
        await message.channel.send(f"🔊 음성 채널 **'{voice_channel.name}'**에 입장했습니다!")

    elif content.startswith("!play "):
        url = content[6:].strip().strip("<>")
        url = clean_youtube_url(url)
        if not url:
            await message.channel.send("⚠️ 재생할 유튜브 주소 또는 검색어를 입력하세요.")
            return
            
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if not voice_client:
            if message.author.voice:
                voice_channel = message.author.voice.channel
                voice_client = await voice_channel.connect()
            else:
                await message.channel.send("⚠️ 봇이 재생할 수 있도록 먼저 음성 채널에 들어가 주세요!")
                return
                
        await message.channel.send("🔍 유튜브 오디오 스트림 분석 및 대기열 빌드 중...")
        
        try:
            loop = client.loop or asyncio.get_event_loop()
            extract_opts = {'extract_flat': True, 'process': False, 'noplaylist': False, 'playlist_items': '1-20'}
            ytdl_flat = yt_dlp.YoutubeDL({**ytdl_format_options, **extract_opts})
            data = await loop.run_in_executor(None, lambda: ytdl_flat.extract_info(url, download=False))
            
            if not data:
                await message.channel.send("❌ 유튜브 정보를 가져오지 못했습니다. 링크를 다시 확인해 주세요.")
                return
                
            if 'entries' in data and len(data.get('entries', [])) > 1:
                entries = list(data['entries'])
                added_songs = []
                for entry in entries:
                    if not entry:
                        continue
                    video_id = entry.get('id') or entry.get('url')
                    video_url = f"https://www.youtube.com/watch?v={video_id}" if not video_id.startswith("http") else video_id
                    title = entry.get('title') or "유튜브 오디오 곡"
                    added_songs.append({
                        'title': title,
                        'url': video_url,
                        'source': None
                    })
                music_queues[guild_id].extend(added_songs)
                await message.channel.send(f"📋 플레이리스트 감지: 총 **`{len(added_songs)}곡`**이 대기열에 고속 적재되었습니다!")
            else:
                full_data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
                if not full_data:
                    await message.channel.send("❌ 음원 메타데이터 추출에 실패했습니다.")
                    return
                if 'entries' in full_data:
                    full_data = full_data['entries'][0]
                video_url = full_data.get('webpage_url') or full_data.get('url') or url
                title = full_data.get('title') or "유튜브 곡"
                
                music_queues[guild_id].append({
                    'title': title,
                    'url': video_url,
                    'source': None
                })
                await message.channel.send(f"📝 대기열 추가: **{title}**")
                
            if not voice_client.is_playing() and not voice_client.is_paused():
                play_next_song(guild_id, voice_client, message.channel)
        except Exception as e:
            await message.channel.send(f"❌ 재생 실패: {e}")

    elif content == "!skip":
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            await message.channel.send("⏭️ 현재 곡을 스킵하고 다음 대기곡으로 넘어갑니다.")
        else:
            await message.channel.send("⚠️ 현재 재생 중인 음악이 없습니다.")

    elif content == "!pause":
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await message.channel.send("⏸️ 음악을 일시정지했습니다.")

    elif content == "!resume":
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await message.channel.send("▶️ 음악 재생을 다시 시작합니다.")

    elif content in ["!leave", "!stop"]:
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client:
            music_queues[guild_id].clear()
            await voice_client.disconnect()
            await message.channel.send("⏹️ 재생을 중단하고 음성 채널에서 나갔습니다.")
        else:
            await message.channel.send("⚠️ 봇이 음성 채널에 연결되어 있지 않습니다.")

    elif content in ["!queue", "!q"]:
        queue = music_queues[guild_id]
        if not queue:
            await message.channel.send("📭 현재 재생 대기열이 비어 있습니다.")
            return
            
        max_display = 15
        queue_text = ""
        for i, song in enumerate(queue[:max_display]):
            next_line = f"`{i+1}.` [{song['title']}]({song['url']})\n"
            # 임베드 버퍼 한계 고려해 글자수 안전 가드
            if len(queue_text) + len(next_line) > 1500:
                queue_text += f"\n*...외 {len(queue) - i}곡이 더 있습니다.*"
                break
            queue_text += next_line
        else:
            if len(queue) > max_display:
                queue_text += f"\n*...외 {len(queue) - max_display}곡이 더 있습니다.*"
                
        embed = discord.Embed(
            title="📋 현재 음악 대기열",
            description=f"총 **{len(queue)}곡**이 대기 중입니다.\n\n{queue_text}",
            color=0x3B82F6
        )
        embed.set_footer(text="!remove [번호] 로 특정 대기곡을 제거할 수 있습니다. | !shuffle 로 순서를 섞을 수 있습니다.")
        await message.channel.send(embed=embed)

    elif content.startswith(("!remove ", "!del ")):
        cmd_len = 8 if content.startswith("!remove ") else 5
        idx_str = content[cmd_len:].strip()
        
        if not idx_str.isdigit():
            await message.channel.send("⚠️ 삭제할 곡의 올바른 번호를 적어주세요. (예: `!remove 3`)")
            return
            
        idx = int(idx_str)
        queue = music_queues[guild_id]
        
        if idx < 1 or idx > len(queue):
            await message.channel.send(f"❌ 올바른 범위 내의 번호를 선택해 주세요. (현재 대기열 범위: 1 ~ {len(queue)})")
            return
            
        removed_song = queue.pop(idx - 1)
        await message.channel.send(f"🗑️ 대기열에서 곡을 삭제했습니다: **{removed_song['title']}**")

    elif content == "!clear":
        queue = music_queues[guild_id]
        if not queue:
            await message.channel.send("⚠️ 비울 대기열이 없습니다.")
            return
            
        count = len(queue)
        queue.clear()
        await message.channel.send(f"🧹 대기열의 모든 곡(**{count}곡**)을 삭제했습니다.")

    elif content == "!shuffle":
        queue = music_queues[guild_id]
        if len(queue) < 2:
            await message.channel.send("⚠️ 섞을 대기곡이 부족합니다. (최소 2곡 이상 필요)")
            return
            
        import random
        random.shuffle(queue)
        await message.channel.send("🔀 대기열 순서를 무작위로 섞었습니다! `!queue` 로 확인해 보세요.")

    elif content.startswith("!save "):
        args = content[6:].strip().split(maxsplit=1)
        if len(args) < 2:
            await message.channel.send("⚠️ 사용법: `!save [곡 별칭] [유튜브 링크]`\n(예: `!save 기아응원가 https://www.youtube.com/watch?v=...`)")
            return
            
        alias, url = args[0].strip(), args[1].strip()
        url = url.strip("<>")
        url = clean_youtube_url(url)
        
        await message.channel.send(f"🔍 유튜브 링크 정보를 분석하고 있습니다: **{alias}**...")
        try:
            loop = client.loop or asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if not info:
                title = alias
            else:
                if 'entries' in info:
                    info = info['entries'][0]
                title = info.get("title") or alias
                
            playlist_data = load_user_playlist()
            playlist_data = [item for item in playlist_data if item["alias"] != alias]
            playlist_data.append({
                "alias": alias,
                "title": title,
                "url": url
            })
            
            if save_user_playlist(playlist_data):
                await message.channel.send(f"💾 보관함에 노래를 성공적으로 저장했습니다!\n• 별칭: **{alias}**\n• 제목: **{title}**")
            else:
                await message.channel.send("❌ 보관함 파일 저장에 실패했습니다.")
        except Exception as e:
            await message.channel.send(f"❌ 유튜브 정보를 분석하지 못했습니다. 링크를 확인해 주세요: {e}")

    elif content in ["!playlist", "!pl"]:
        playlist_data = load_user_playlist()
        if not playlist_data:
            await message.channel.send("📭 나만의 보관함이 비어 있습니다. `!save [별칭] [유튜브주소]` 로 노래를 저장해 보세요!")
            return
            
        pl_text = ""
        for i, item in enumerate(playlist_data):
            next_line = f"`{i+1}.` **{item['alias']}** — [{item['title']}]({item['url']})\n"
            if len(pl_text) + len(next_line) > 1800:
                pl_text += f"\n*...외 {len(playlist_data) - i}곡이 더 있습니다.*"
                break
            pl_text += next_line
            
        embed = discord.Embed(
            title="📂 나만의 노래 보관함",
            description=f"총 **{len(playlist_data)}곡**이 저장되어 있습니다.\n\n{pl_text}",
            color=0x8B5CF6
        )
        embed.set_footer(text="!play_saved [번호/별칭] 으로 재생 목록에 추가하거나, !delete_saved [번호/별칭] 으로 제거합니다.")
        await message.channel.send(embed=embed)

    elif content.startswith(("!play_saved ", "!pls ")):
        cmd_len = 12 if content.startswith("!play_saved ") else 5
        target = content[cmd_len:].strip()
        
        playlist_data = load_user_playlist()
        if not playlist_data:
            await message.channel.send("📭 보관함이 비어 있습니다.")
            return
            
        selected_item = None
        if target.isdigit():
            idx = int(target)
            if 1 <= idx <= len(playlist_data):
                selected_item = playlist_data[idx - 1]
                
        if not selected_item:
            for item in playlist_data:
                if item["alias"] == target:
                    selected_item = item
                    break
                    
        if not selected_item:
            await message.channel.send(f"❌ 보관함에서 **'{target}'** 번호 또는 별칭을 찾을 수 없습니다. `!pl` 로 목록을 확인해 보세요.")
            return
            
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if not voice_client:
            if message.author.voice:
                voice_client = await message.author.voice.channel.connect()
                await message.channel.send(f"🔊 음성 채널 **'{message.author.voice.channel.name}'**에 자동 연결했습니다.")
                if guild_id not in music_queues:
                    music_queues[guild_id] = []
            else:
                await message.channel.send("⚠️ 봇이 오디오를 재생할 수 있게 먼저 음성 채널에 들어가 주시거나 `!join` 을 입력해 주세요.")
                return
                
        music_queues[guild_id].append({
            'title': selected_item['title'],
            'url': selected_item['url'],
            'source': None
        })
        await message.channel.send(f"📝 보관함에서 대기열 추가: **{selected_item['alias']}** ({selected_item['title']})")
        
        if not voice_client.is_playing() and not voice_client.is_paused():
            play_next_song(guild_id, voice_client, message.channel)

    elif content.startswith(("!delete_saved ", "!dels ")):
        cmd_len = 14 if content.startswith("!delete_saved ") else 6
        target = content[cmd_len:].strip()
        
        playlist_data = load_user_playlist()
        if not playlist_data:
            await message.channel.send("📭 보관함이 비어 있어 삭제할 곡이 없습니다.")
            return
            
        removed_item = None
        if target.isdigit():
            idx = int(target)
            if 1 <= idx <= len(playlist_data):
                removed_item = playlist_data.pop(idx - 1)
                
        if not removed_item:
            for i, item in enumerate(playlist_data):
                if item["alias"] == target:
                    removed_item = playlist_data.pop(i)
                    break
                    
        if not removed_item:
            await message.channel.send(f"❌ 보관함에서 **'{target}'**에 해당하는 곡을 찾지 못했습니다.")
            return
            
        if save_user_playlist(playlist_data):
            await message.channel.send(f"🗑️ 보관함에서 곡을 영구 삭제했습니다: **{removed_item['alias']}** ({removed_item['title']})")
        else:
            await message.channel.send("❌ 보관함 파일 업데이트 실패.")

    # 💡 아이디어 메모장 채널 전용 도움말
    elif content == "!memo":
        embed = discord.Embed(
            title="✏️ 아이디어 메모장 도움말",
            description="이 채널은 개인 아이디어 & 기획 메모 전용 공간입니다.",
            color=0x8B5CF6
        )
        embed.add_field(
            name="📝 명령어 목록",
            value=(
                "`!add [내용]` — 새 아이디어 메모 등록\n"
                "`!list` — 미완료(TODO) 아이디어 전체 조회\n"
                "`!done [ID]` — 해당 ID 아이디어 완료 처리\n"
                "`!memo` — 이 도움말 다시 보기"
            ),
            inline=False
        )
        embed.add_field(
            name="💡 팁",
            value=(
                "• 아이디어가 떠오르면 바로 `!add` 로 기록하세요\n"
                "• 완료한 아이디어는 `!done [ID]` 로 처리하면 `ideas.md` 파일에 자동 반영됩니다\n"
                "• `!list` 로 쌓인 아이디어를 주기적으로 확인하세요"
            ),
            inline=False
        )
        embed.set_footer(text="🔒 이 채널은 비공개 채널입니다.")
        await message.channel.send(embed=embed)

    # 도움말
    elif content == "!help":
        embed = discord.Embed(
            title="🤖 KBO 콘텐츠 기획 비서 도움말",
            color=0x6B7280
        )
        embed.add_field(
            name="💡 아이디어 메모장",
            value="• `!add [글감]`: 새 아이디어 등록\n• `!list`: TODO 리스트 조회\n• `!done [ID]`: 아이디어 완료(ideas.md 자동 갱신)\n• `!memo`: 메모장 채널 도움말",
            inline=False
        )
        embed.add_field(
            name="📊 경기 예측 및 시각화 차트",
            value="• `!predict [원정] [홈]`: 양 팀간 1,000회 몬테카를로 경기 시뮬레이션 예측\n• `!chart [선수명] [연도]`: 투수(피칭 히트맵) 또는 타자(안타 스프레이 차트) 생성 및 이미지 전송\n• `!today`: 오늘 진행되는 KBO 경기 일정 및 실시간 스코어/결과 조회",
            inline=False
        )
        embed.add_field(
            name="📰 뉴스 수집 및 스케줄링",
            value="• `!setup`: KBO+10개 구단 채널 + 아이디어 메모장 채널 개설\n• `!scrape`: 실시간 기사 수동 배포 포스팅\n• `⏰ 자동화`: 매일 오전 08:30 / 오후 18:30 전 구단 채널 정기 자동 브리핑 배포\n• `⚡ 실시간 알림`: KBO 경기 시작 전(대진표) / 취소(우천 등) / 종료(최종 스코어) 알림 및 갱신 자동화",
            inline=False
        )
        embed.add_field(
            name="🎵 음악 재생 기능",
            value="• `!join` / `!leave`: 봇 음성 채널 호출 및 퇴장\n• `!play [유튜브 주소/검색]`: 단일곡 및 플레이리스트 고속 적재 재생\n• `!queue` (또는 `!q`): 현재 대기열 목록 조회\n• `!remove [번호]`: 특정 대기곡 제거\n• `!clear` / `!shuffle`: 대기열 전체 비우기 및 섞기\n• `!save [별칭] [링크]`: 유튜브 주소를 나만의 보관함에 별칭으로 저장\n• `!pl` (또는 `!playlist`): 내 노래 보관함 목록 확인\n• `!play_saved` (또는 `!pls`) `[번호/별칭]`: 저장된 곡 재생 대기열 추가\n• `!delete_saved` (또는 `!dels`) `[번호/별칭]`: 보관함 곡 삭제\n• `!skip` / `!pause` / `!resume`: 재생 제어",
            inline=False
        )
        await message.channel.send(embed=embed)

def main():
    if not DISCORD_BOT_TOKEN:
        print("\n⚠️ [Error] DISCORD_BOT_TOKEN이 없습니다.\n")
        sys.exit(1)
    try:
        client.run(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}\n")

if __name__ == "__main__":
    main()
