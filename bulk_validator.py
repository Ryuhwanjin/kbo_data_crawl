import pandas as pd
import time
import argparse
import os
import logging
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def run_bulk_validator(year):
    log_file = f'validation_errors_{year}.log'
    logging.basicConfig(filename=log_file, level=logging.INFO, 
                        format='%(asctime)s - %(message)s', filemode='w')
    
    # 1. 파일 로드
    parsed_file = f"kbo_batter_saber_{year}.csv"
    master_file = "unique_players.csv"
    
    if not os.path.exists(parsed_file) or not os.path.exists(master_file):
        logging.error("필수 CSV 파일이 없습니다. kbo_sabermetrics.py 또는 extract_unique_players.py 를 실행하세요.")
        print("에러: 필수 CSV 없음. 로그 확인.")
        return
        
    df_parsed = pd.read_csv(parsed_file)
    df_master = pd.read_csv(master_file)
    
    # pcode가 매핑된 타자들만 (파서 데이터에 존재하는 선수만)
    df_valid = pd.merge(df_parsed, df_master, on='Player', how='inner')
    df_valid = df_valid.drop_duplicates(subset=['pcode'])
    df_valid = df_valid[df_valid['pcode'].notna() & (df_valid['pcode'] != 'Unknown')]
    
    total_players = len(df_valid)
    logging.info(f"[{year}년] 총 {total_players}명 대량 교차 검증 시작")
    print(f"[{year}년] 총 {total_players}명 검증 시작. (로그는 {log_file} 참조)")
    
    driver = init_driver()
    error_count = 0
    
    # 메모리 누수 방지용 카운터
    req_count = 0
    current_idx = 0
    
    for _, row in df_valid.iterrows():
        req_count += 1
        current_idx += 1
        
        if req_count % 50 == 0:
            driver.quit()
            time.sleep(2)
            driver = init_driver()
            
        pcode = str(int(row['pcode'])) if isinstance(row['pcode'], float) else str(row['pcode'])
        player = row['Player']
        
        progress_str = f"[{current_idx}/{total_players}] ({current_idx/total_players*100:.1f}%)"
        
        url = f"https://m.sports.naver.com/player/index?playerId={pcode}&category=kbo&tab=record"
        try:
            driver.get(url)
            time.sleep(2.5) # 페이지 로딩 딜레이
        except Exception as e:
            logging.error(f"[{player}] 브라우저 접속 에러: {e}")
            print(f"⚠️ {progress_str} [{player}] 브라우저 로딩 에러 건너뜀")
            continue
            
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        target_tr = None
        headers = []
        tables = soup.find_all('table')
        for table in tables:
            spans = table.find_all('span', class_='text')
            for span in spans:
                if str(year) in span.text:
                    target_tr = span.find_parent('tr')
                    break
            if target_tr:
                thead = table.find('thead')
                if thead:
                    headers = [th.text.strip() for th in thead.find_all('th')]
                break
                
        if not target_tr or not headers:
            logging.info(f"[{player}] {year}년 네이버 기록 없음 (출전기록 누락 등)")
            print(f"⏩ {progress_str} [{player}] {year}년 네이버 공식 기록이 없어 패스")
            continue
            
        tds = [td.text.strip() for td in target_tr.find_all('td')]
        if len(headers) - len(tds) == 1:
            headers = headers[1:]
            
        naver_stats = dict(zip(headers, tds))
        for k, v in naver_stats.items():
            try: naver_stats[k] = int(v)
            except: pass
                
        # 파서 스탯
        p_PA = int(row['PA'])
        p_AB = int(row['AB'])
        p_H = int(row['1B']) + int(row['2B']) + int(row['3B']) + int(row['HR'])
        p_2B = int(row['2B'])
        p_3B = int(row['3B'])
        p_HR = int(row['HR'])
        p_BB = int(row['BB'])
        p_SO = int(row['SO'])
        
        errors = []
        def check_diff(stat_name, parser_val, naver_key):
            if naver_key in naver_stats:
                diff = naver_stats[naver_key] - parser_val
                if diff != 0:
                    sign = "+" if diff > 0 else ""
                    errors.append(f"{stat_name} {sign}{diff}")
        
        check_diff('AB', p_AB, '타수')
        check_diff('H', p_H, '안타')
        check_diff('2B', p_2B, '2루타')
        check_diff('3B', p_3B, '3루타')
        check_diff('HR', p_HR, '홈런')
        check_diff('BB', p_BB, '볼넷')
        check_diff('SO', p_SO, '삼진')
        
        if errors:
            logging.warning(f"[{player}] 오차 발생: " + ", ".join(errors))
            print(f"❌ {progress_str} [{player}] 오차 발생! (상세 로깅됨)")
            error_count += 1
        else:
            print(f"✅ {progress_str} [{player}] 완벽 일치")
            
    driver.quit()
    logging.info(f"검증 완료. 총 {total_players}명 중 {error_count}명 오차 발생.")
    print(f"검증 완료. 총 {total_players}명 중 {error_count}명 오차 발생. 상세 내역은 {log_file} 확인.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="대량 교차 검증 봇")
    parser.add_argument('--year', type=int, required=True, help="검증할 연도")
    args = parser.parse_args()
    
    run_bulk_validator(args.year)
