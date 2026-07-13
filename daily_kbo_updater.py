import os
import sys
import json
import time
import argparse
import requests
import subprocess
from datetime import datetime, timedelta

# KBO 일정 API Endpoint로부터 경기 정보를 가져오는 함수
def get_kbo_games_status(date_str):
    url = f"https://api-gw.sports.naver.com/schedule/games?upperCategoryId=kbaseball&fromDate={date_str}&toDate={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://sports.news.naver.com/kbaseball/schedule/index"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        games = data.get("result", {}).get("games", [])
        
        finished_games = []
        for g in games:
            # 1군 KBO 경기이면서 종료된(FINISHED) 경기만 필터링
            if g.get("categoryId") == "kbo" and g.get("homeTeamName") and g.get("awayTeamName"):
                # state가 FINISHED 또는 경기 종료 상태인 경우
                if g.get("state") == "FINISHED":
                    finished_games.append({
                        "gameId": g["gameId"],
                        "date": date_str
                    })
        return finished_games
    except Exception as e:
        print(f"⚠️ {date_str} 경기 일정을 조회하는 중 에러 발생: {e}")
        return []

# 문자중계 릴레이 데이터를 다운로드하고 모든 이닝을 병합하여 저장하는 함수
def download_game_relay(game_id, output_dir="kbo_data"):
    if len(game_id) >= 8 and game_id[0:8].isdigit():
        year = game_id[0:4]
        month = game_id[4:6]
        day = game_id[6:8]
    else:
        year, month, day = "Unknown", "Unknown", "Unknown"
        
    game_dir = os.path.join(output_dir, year, month, day)
    os.makedirs(game_dir, exist_ok=True)
    target_path = os.path.join(game_dir, f"{game_id}.json")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://sports.news.naver.com/"
    }
    
    # 1. 경기 기본 정보 로드 (릴레이의 기본 뼈대 데이터)
    base_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}/relay"
    try:
        response = requests.get(base_url, headers=headers, timeout=5)
        response.raise_for_status()
        base_data = response.json()
    except Exception as e:
        print(f"❌ [{game_id}] 릴레이 기본 데이터 다운로드 실패: {e}")
        return False
        
    # 2. 각 이닝별(1이닝~연장) 문자 중계 상세 데이터 수집 및 병합
    relay_data = base_data.get("result", {}).get("textRelayData", {})
    if not relay_data:
        print(f"⚠️ [{game_id}] textRelayData가 존재하지 않아 스킵합니다.")
        return False
        
    # 총 이닝 수 구하기 (일반적으로 9이닝, 연장 시 12이닝 등)
    inn_count = relay_data.get("inn", 9)
    if inn_count < 1:
        inn_count = 9
        
    merged_relays = []
    
    # 각 이닝별 문자중계 API 호출 및 병합
    for inn in range(1, inn_count + 1):
        for half in ["top", "bottom"]:
            inn_url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}/relay/texts?inning={inn}&inningHalf={half}"
            try:
                # 네이버 서버의 과부하 및 차단을 방지하기 위한 50ms 미세 딜레이
                time.sleep(0.05)
                res = requests.get(inn_url, headers=headers, timeout=5)
                res.raise_for_status()
                res_data = res.json()
                
                texts = res_data.get("result", {}).get("textRelays", [])
                if texts:
                    merged_relays.extend(texts)
            except Exception as e:
                # 콜드게임이나 강우 종료 등으로 연장/일부 이닝이 없는 경우는 패스
                continue
                
    # 시간 역순으로 정렬된 데이터를 정방향 순서로 재정렬
    merged_relays.reverse()
    
    # 최종 병합된 리스트를 JSON 구조에 재적재
    base_data["result"]["textRelayData"]["textRelays"] = merged_relays
    
    # 파일에 JSON 저장
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(base_data, f, indent=4, ensure_ascii=False)
        
    print(f"💾 [{game_id}] 릴레이 데이터 병합 저장 완료 -> {target_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="KBO 2026시즌 매일 진행 중인 데이터를 증분 수집하고 세이버메트릭스 파이프라인을 갱신합니다.")
    parser.add_argument('--days', type=int, default=3, help="최근 며칠 동안의 경기를 검사할지 범위 설정 (기본값: 3)")
    parser.add_argument('--output-dir', type=str, default="kbo_data", help="데이터가 저장될 디렉토리 (기본값: kbo_data)")
    args = parser.parse_args()
    
    print(f"=== KBO 2026 데일리 증분 업데이트 시작 (최근 {args.days}일 검사) ===")
    
    today = datetime.now()
    dates_to_check = []
    for i in range(args.days + 1):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        dates_to_check.append(date_str)
        
    # 중복 및 날짜 정렬
    dates_to_check = sorted(list(set(dates_to_check)))
    
    new_downloads = 0
    
    for date_str in dates_to_check:
        print(f"📅 {date_str} 경기 확인 중...")
        finished_games = get_kbo_games_status(date_str)
        
        for g in finished_games:
            game_id = g["gameId"]
            year = game_id[0:4]
            month = game_id[4:6]
            day = game_id[6:8]
            
            target_path = os.path.join(args.output_dir, year, month, day, f"{game_id}.json")
            
            # 로컬에 파일이 없는 경우에만 새로 다운로드
            if not os.path.exists(target_path):
                print(f"🆕 새 경기 감지: {game_id} ({date_str})")
                success = download_game_relay(game_id, args.output_dir)
                if success:
                    new_downloads += 1
                time.sleep(0.5)  # 과도한 요청 방지
                
    print(f"\n📥 업데이트 완료: 총 {new_downloads}개의 새로운 경기를 다운로드 받았습니다.")
    
    if new_downloads > 0:
        print("\n⚙️ 신규 데이터가 감지되어 2026시즌 세이버메트릭스 정밀 보정 파이프라인을 기동합니다...")
        pipeline_script = "/Users/ryuhwanjin/.gemini/antigravity/brain/440e699a-7148-44ae-9962-d03e7ca8ed5f/scratch/run_final_pipeline_all_years.py"
        try:
            # 2026 정밀 파이프라인 동기식 실행
            result = subprocess.run([sys.executable, pipeline_script], check=True, text=True, capture_output=True)
            print("✅ 2026시즌 세이버메트릭스 및 정합성 0오차 보정 갱신이 완료되었습니다!")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"❌ 파이프라인 갱신 실패 (exit_code: {e.returncode})")
            print(e.stdout)
            print(e.stderr)
    else:
        print("☕ 업데이트된 신규 경기가 없어 파이프라인 갱신을 건너뜁니다.")

if __name__ == "__main__":
    main()
