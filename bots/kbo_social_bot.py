import os
import sys
import json
import datetime
import argparse
import requests
import pandas as pd
from kbo_match_simulator import KBOChainSimulator
from kbo_card_generator import generate_matchup_card

# .env 환경변수 로딩 지원 (dotenv가 설치되어 있지 않을 경우의 폴백)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv가 없으면 os.environ을 직접 활용하도록 무시
    pass

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

def get_today_games():
    """오늘 날짜에 예정된 KBO 경기 일정 가져오기 (daily_kbo_updater.py의 네이버 API 로직 활용)"""
    today_str = datetime.datetime.now().strftime("%Y%m%d")
    year = today_str[:4]
    month = today_str[4:6]
    
    url = f"https://sports.news.naver.com/kbaseball/schedule/index?category=kbo&year={year}&month={month}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 네이버 API에서 오늘 날짜의 경기 추출
            # 구조: data['dailyScheduleList'] 리스트
            schedules = data.get("dailyScheduleList", [])
            today_games = []
            for s in schedules:
                game_date = s.get("today", "").replace("-", "")
                if game_date == today_str:
                    # KBO 1군 경기만 필터링 (구분: 클래식 리그 등 제외)
                    # s['classicAd'] 가 False 이고 s['state'] 가 'BEFORE' or 'RUNNING' or 'END'
                    for match in s.get("scheduleList", []):
                        # 1군 정규시즌 경기 판단
                        if match.get("leagueName", "KBO") == "KBO":
                            today_games.append({
                                "gameId": match.get("gameId"),
                                "home": match.get("homeTeamName"),
                                "away": match.get("awayTeamName"),
                                "state": match.get("state", "BEFORE"),
                                "time": match.get("startTime", "18:30")
                            })
            return today_games
    except Exception as e:
        print(f"⚠️ 오늘 경기 일정 수집 중 오류 발생: {e}")
    return []

def run_simulation_and_post(home_team, away_team, test_mode=False):
    """특정 매치업에 대해 시뮬레이션을 가동하고 디스코드에 포스팅"""
    print(f"🔮 [KBO Social Bot] {away_team} vs {home_team} 시뮬레이션 분석 가동...")
    
    # 1. 몬테카를로 시뮬레이터 인스턴스 생성 및 라인업 로드
    # 2026시즌 기본 적용
    sim = KBOChainSimulator(year=2026)
    sim.load_data()
    
    # 라인업 선출
    away_lineup, away_pitcher = sim.get_best_lineup(away_team)
    home_lineup, home_pitcher = sim.get_best_lineup(home_team)
    
    if len(away_lineup) < 9 or len(home_lineup) < 9:
        print(f"⚠️ [Error] {away_team} 또는 {home_team}의 로스터가 충분치 않아 가상 라인업으로 대체합니다.")
        # 만약 데이터가 부족하면 2025시즌 데이터로 폴백 시도
        sim = KBOChainSimulator(year=2025)
        sim.load_data()
        away_lineup, away_pitcher = sim.get_best_lineup(away_team)
        home_lineup, home_pitcher = sim.get_best_lineup(home_team)
        
    # 2,000회 몬테카를로 경기 시뮬레이션 기동
    sim_runs = 2000
    away_wins, home_wins, draws, away_runs, home_runs = sim.run_monte_carlo(
        away_team, home_team, away_lineup, away_pitcher, home_lineup, home_pitcher, simulations=sim_runs
    )
    
    away_pct = (away_wins / sim_runs) * 100.0
    home_pct = (home_wins / sim_runs) * 100.0
    draw_pct = (draws / sim_runs) * 100.0
    
    avg_away_score = sum(away_runs) / sim_runs
    avg_home_score = sum(home_runs) / sim_runs
    
    # 2. Pillow 기반 카드뉴스 생성
    output_filename = f"saber_data/kbo_predict_{away_team}_{home_team}.png"
    generate_matchup_card(
        home_team=home_team,
        away_team=away_team,
        year=2026 if not test_mode else 2025,
        home_win_pct=home_pct,
        away_win_pct=away_pct,
        output_path=output_filename
    )
    
    # 3. 디스코드 송출 포맷팅
    embed_color = 0x0062B2 if home_team == '삼성' else 0xC70930 if home_team == 'KIA' else 0x1E293B
    
    payload = {
        "username": "KBO 데이터 시뮬레이터",
        "avatar_url": "https://raw.githubusercontent.com/naver/kbo-assets/main/emblems/KBO.png",
        "embeds": [
            {
                "title": f"⚔️ 오늘의 매치업 분석: {away_team} vs {home_team}",
                "description": f"KBO 2026 정규시즌 데이터를 기반으로 한 2,000회 몬테카를로 승패 예측 보고서입니다.",
                "color": embed_color,
                "fields": [
                    {
                        "name": f"🏃 {away_team} 예측 승률",
                        "value": f"**`{away_pct:.1f}%`** ({away_wins}승)",
                        "inline": True
                    },
                    {
                        "name": f"⚾ {home_team} 예측 승률",
                        "value": f"**`{home_pct:.1f}%`** ({home_wins}승)",
                        "inline": True
                    },
                    {
                        "name": "🤝 무승부 확률",
                        "value": f"`{draw_pct:.1f}%` ({draws}무)",
                        "inline": True
                    },
                    {
                        "name": "📈 평균 예상 스코어",
                        "value": f"🏟️ **{away_team} {avg_away_score:.1f}점** vs **{home_team} {avg_home_score:.1f}점**",
                        "inline": False
                    },
                    {
                        "name": "👤 예상 선발 투수 매치업",
                        "value": f"• {away_team}: **{away_pitcher['Player']}** (FIP: {away_pitcher['FIP']:.2f}, WAR: {away_pitcher['WAR']:.2f})\n• {home_team}: **{home_pitcher['Player']}** (FIP: {home_pitcher['FIP']:.2f}, WAR: {home_pitcher['WAR']:.2f})",
                        "inline": False
                    }
                ],
                "image": {
                    "url": f"attachment://kbo_predict_{away_team}_{home_team}.png"
                },
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }
    
    # 4. 디스코드 전송
    if not DISCORD_WEBHOOK_URL:
        print("\n📢 [Dry-Run 모드] DISCORD_WEBHOOK_URL이 설정되지 않아 로컬 터미널에 메시지를 출력합니다:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
        
    try:
        with open(output_filename, "rb") as f:
            files = {
                "file": (f"kbo_predict_{away_team}_{home_team}.png", f, "image/png")
            }
            # payload를 'payload_json' 파라미터로 실어서 파일과 함께 전송해야 디스코드에서 이미지 첨부가 매칭됩니다.
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=15
            )
            
            if response.status_code in [200, 204]:
                print(f"✅ 디스코드 웹훅 송출 완료: {away_team} vs {home_team}")
            else:
                print(f"❌ 디스코드 웹훅 전송 실패 (상태 코드: {response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ 디스코드 웹훅 전송 중 오류 발생: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="가상의 KIA vs 삼성 테스트 매치업 시뮬레이션 송출")
    parser.add_argument("--home", type=str, default=None, help="테스트 홈 팀")
    parser.add_argument("--away", type=str, default=None, help="테스트 원정 팀")
    args = parser.parse_args()
    
    # 디스코드 연동 테스트 모드
    if args.test or (args.home and args.away):
        home = args.home or "삼성"
        away = args.away or "KIA"
        run_simulation_and_post(home, away, test_mode=True)
        return
        
    # 데일리 자동화 모드: 당일 실제 일정 조회
    print("📅 [KBO Social Bot] 오늘의 KBO 경기 일정을 조회합니다...")
    games = get_today_games()
    
    if not games:
        print("📭 오늘 예정된 KBO 1군 경기가 없거나 일정을 불러오지 못했습니다.")
        return
        
    print(f"🔥 오늘 총 {len(games)}개의 경기가 예정되어 있습니다.")
    for game in games:
        print(f"👉 매치업 감지: {game['away']} (원정) vs {game['home']} (홈) [{game['time']}]")
        run_simulation_and_post(game['home'], game['away'])

if __name__ == "__main__":
    main()
