import requests
import json
import os
import time
import argparse
import glob
from datetime import datetime, timedelta

# KBO 연도별 정규시즌 개막일 ~ 한국시리즈 종료일 (시범경기 완전 배제)
KBO_SEASON_DATES = {
    2017: ("2017-03-31", "2017-10-30"),
    2018: ("2018-03-24", "2018-11-12"),
    2019: ("2019-03-23", "2019-10-26"),
    2020: ("2020-05-05", "2020-11-24"),
    2021: ("2021-04-03", "2021-11-18"),
    2022: ("2022-04-02", "2022-11-08"),
    2023: ("2023-04-01", "2023-11-13"),
    2024: ("2024-03-23", "2024-10-28"),
    2025: ("2025-03-22", "2025-10-31"),
    2026: ("2026-03-21", "2026-11-15"), # 2026시즌 임시 기간 설정 (실시간 데이터 수집용)
}

def get_date_range(start_date_str, end_date_str):
    """시작 날짜와 종료 날짜 사이의 모든 날짜 리스트를 반환합니다."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    date_list = []
    current_date = start_date
    while current_date <= end_date:
        date_list.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    return date_list

def get_kbo_game_ids(date_str):
    """지정한 날짜의 KBO 1군 경기 ID 리스트를 가져옵니다."""
    url = f"https://api-gw.sports.naver.com/schedule/games?upperCategoryId=kbaseball&fromDate={date_str}&toDate={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://sports.news.naver.com/kbaseball/schedule/index"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        games = data.get("result", {}).get("games", [])
        kbo_game_ids = [
            g["gameId"] for g in games 
            if g.get("categoryId") == "kbo" and g.get("homeTeamName") and g.get("awayTeamName")
        ]
        return kbo_game_ids
    except Exception as e:
        print(f"⚠️ {date_str} 경기 일정을 가져오는 중 에러 발생: {e}")
        return []

def download_game_relay(game_id, output_dir):
    """특정 경기의 상세 릴레이 JSON 파일을 다운로드하며, 1회부터 마지막 회까지 모든 이닝을 순회하여 병합합니다."""
    if len(game_id) >= 8 and game_id[0:8].isdigit():
        year = game_id[0:4]
        month = game_id[4:6]
        day = game_id[6:8]
    else:
        year, month, day = "Unknown", "Unknown", "Unknown"
        
    game_dir = os.path.join(output_dir, year, month, day)
    os.makedirs(game_dir, exist_ok=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": f"https://sports.news.naver.com/game/{game_id}"
    }
    
    file_path = os.path.join(game_dir, f"kbo_relay_{game_id}.json")
    
    if os.path.exists(file_path):
        return True
        
    all_relays = []
    base_data = None
    
    try:
        # 이닝 1부터 최대 20회까지 순회 (일반적으로 9~12회에서 종료됨)
        for inning in range(1, 21):
            url = f"https://api-gw.sports.naver.com/schedule/games/{game_id}/relay?inning={inning}"
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                break
                
            data = response.json()
            if base_data is None:
                base_data = data
                
            relays = data.get("result", {}).get("textRelayData", {}).get("textRelays", [])
            if not relays:
                break
                
            all_relays.extend(relays)
            time.sleep(0.05) # 네이버 서버 보호를 위한 짧은 딜레이
            
        if not all_relays:
            return False
            
        # 병합된 전체 이닝 이벤트(Relays)를 메타 껍데기(base_data) 안에 끼워넣기
        base_data["result"]["textRelayData"]["textRelays"] = all_relays
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(base_data, f, ensure_ascii=False, indent=4)
        print(f"   -> [SUCCESS] 다운로드 완료: {year}/{month}/{day}/{game_id} (총 {len(all_relays)} 타석/투구 세트 수집)")
        return True
    except Exception as e:
        print(f"   -> [ERROR] 경기 {game_id} 다운로드 실패: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="네이버 KBO PTS 투구 데이터 수집기 (일별 폴더 트리 분류 - 로컬 바이패스 가속 버전)")
    parser.add_argument("--years", type=str, default=None, help="수집할 연도 목록 (예: 2023,2024,2025)")
    parser.add_argument("--start", type=str, default=None, help="시작 날짜 (YYYY-MM-DD, --years 미지정 시 사용)")
    parser.add_argument("--end", type=str, default=None, help="종료 날짜 (YYYY-MM-DD, --years 미지정 시 사용)")
    parser.add_argument("--out", type=str, default="./kbo_data", help="데이터 저장 루트 폴더")
    parser.add_argument("--delay", type=float, default=1.5, help="요청 사이 대기 시간 (초)")
    
    args = parser.parse_args()
    
    tasks = []
    
    if args.years:
        year_list = [int(y.strip()) for y in args.years.split(",") if y.strip().isdigit()]
        for year in year_list:
            if year in KBO_SEASON_DATES:
                start, end = KBO_SEASON_DATES[year]
                tasks.append((year, start, end))
            else:
                print(f"⚠️ {year}년은 정의된 시즌 일정 데이터가 없어 건너뜁니다.")
    else:
        if not args.start or not args.end:
            year = 2024
            start, end = KBO_SEASON_DATES[year]
            tasks.append((year, start, end))
        else:
            tasks.append(("Custom", args.start, args.end))
            
    print("=" * 60)
    print("        네이버 스포츠 KBO PTS 투구 데이터 수집기 (로컬 바이패스 가속 버전)")
    print(f"        저장 루트: {os.path.abspath(args.out)}")
    print(f"        요청 지연 시간: {args.delay}초")
    print("=" * 60)
    
    for task_info in tasks:
        label, start_date, end_date = task_info
            
        print(f"\n🚀 [작업 시작] 대상: {label}시즌 ({start_date} ~ {end_date})")
        
        try:
            dates = get_date_range(start_date, end_date)
        except ValueError:
            print("❌ 날짜 형식이 잘못되었습니다. YYYY-MM-DD 형식인지 확인해주세요.")
            continue
            
        print(f"ℹ️ 총 {len(dates)}일간의 일정을 순회합니다.")
        
        # 로컬 폴더 파일 개수 선 검사 및 일정 조회 API 바이패스
        all_game_ids = []
        skipped_days = 0
        
        for d in dates:
            year_str, month_str, day_str = d.split("-")
            local_day_dir = os.path.join(args.out, year_str, month_str, day_str)
            if os.path.exists(local_day_dir):
                existing_files = glob.glob(os.path.join(local_day_dir, "kbo_relay_*.json"))
                # 보통 월요일(0경기)이거나 우천 취소가 아닌 날은 5경기 수집 시 완료로 간주
                if len(existing_files) >= 5:
                    skipped_days += 1
                    continue
                    
            # 아직 수집 안 되었거나 덜 된 날짜만 API 호출
            game_ids = get_kbo_game_ids(d)
            if game_ids:
                all_game_ids.extend(game_ids)
            time.sleep(0.05) # 선별 조회 지연 시간 최소화 (0.05초)
            
        print("-" * 60)
        print(f"ℹ️ {skipped_days}일의 완성된 일정(로컬 경기 5개 이상)을 네트워크 조회 없이 완벽 바이패스했습니다.")
        print(f"수집 대상 신규 KBO 경기 수: {len(all_game_ids)}개")
        print("-" * 60)
        
        if not all_game_ids:
            print("🎉 추가로 수집할 신규 경기가 없습니다. 다음 작업으로 넘어갑니다.")
            continue
            
        # 각 gameId 별 릴레이 데이터 다운로드
        success_count = 0
        skipped_count = 0
        
        for idx, game_id in enumerate(all_game_ids, 1):
            year = game_id[0:4] if len(game_id) >= 4 else "Unknown"
            month = game_id[4:6] if len(game_id) >= 6 else "Unknown"
            day = game_id[6:8] if len(game_id) >= 8 else "Unknown"
            file_path = os.path.join(args.out, year, month, day, f"kbo_relay_{game_id}.json")
            
            if os.path.exists(file_path):
                skipped_count += 1
                success_count += 1
                continue
                
            print(f"[{idx}/{len(all_game_ids)}] {game_id} 다운로드 시도 중...")
            success = download_game_relay(game_id, args.out)
            if success:
                success_count += 1
            
            if idx < len(all_game_ids):
                time.sleep(args.delay)
                
        print(f"ℹ️ {skipped_count}개의 이미 다운로드된 경기를 자동 스킵(Skip)했습니다.")
        print(f"🎉 [작업 완료] {label}시즌 성공: {success_count}/{len(all_game_ids)}")
        print("-" * 60)
        
    print("\n" + "=" * 60)
    print("        모든 수집 프로세스가 성공적으로 완료되었습니다!")
    print("=" * 60)

if __name__ == "__main__":
    main()
