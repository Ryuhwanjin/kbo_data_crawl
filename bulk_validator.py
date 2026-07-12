import pandas as pd
import time
import argparse
import os
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import UnexpectedAlertPresentException

def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def naver_ip_to_outs(ip_str):
    ip_str = ip_str.strip()
    if not ip_str:
        return 0
    try:
        if ' ' in ip_str:
            parts = ip_str.split(' ')
            integer_part = int(parts[0])
            fraction_part = parts[1]
            if fraction_part == '1/3':
                outs = integer_part * 3 + 1
            elif fraction_part == '2/3':
                outs = integer_part * 3 + 2
            else:
                outs = integer_part * 3
        elif '/' in ip_str:
            if ip_str == '1/3':
                outs = 1
            elif ip_str == '2/3':
                outs = 2
            else:
                outs = 0
        else:
            if '.' in ip_str:
                parts = ip_str.split('.')
                integer_part = int(parts[0])
                fraction_part = int(parts[1])
                outs = integer_part * 3 + fraction_part
            else:
                outs = int(ip_str) * 3
        return outs
    except:
        return 0

def run_bulk_validator(year, player_type="batter"):
    log_file = f'validation_errors_{player_type}_{year}.log'
    # Configure logging dynamically
    logger = logging.getLogger(player_type)
    logger.setLevel(logging.INFO)
    # Clear existing handlers to avoid mixing logs
    if logger.handlers:
        logger.handlers.clear()
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger.addHandler(fh)
    
    parsed_file = f"kbo_{player_type}_saber_{year}.csv"
    
    if not os.path.exists(parsed_file):
        logger.error(f"필수 CSV 파일이 없습니다. kbo_sabermetrics.py --year {year} 를 먼저 실행하세요.")
        print(f"에러: 필수 CSV({parsed_file}) 없음. 로그 확인.")
        return
        
    df_valid = pd.read_csv(parsed_file)
    
    if 'pcode' not in df_valid.columns:
        print("에러: 파서 데이터에 pcode 컬럼이 없습니다.")
        return
        
    df_valid = df_valid[df_valid['pcode'].notna() & (df_valid['pcode'] != 'Unknown')]
    df_valid = df_valid.drop_duplicates(subset=['pcode'])
    
    total_players = len(df_valid)
    type_kor = "타자" if player_type == "batter" else "투수"
    logger.info(f"[{year}년] [{type_kor}] 총 {total_players}명 대량 교차 검증 시작")
    print(f"[{year}년] [{type_kor}] 총 {total_players}명 검증 시작. (로그는 {log_file} 참조)")
    
    driver = init_driver()
    error_count = 0
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
        
        progress_str = f"[{current_idx}/{total_players}] ({(current_idx/total_players*100):.1f}%)"
        
        url = f"https://m.sports.naver.com/player/index?playerId={pcode}&category=kbo&tab=record"
        try:
            driver.get(url)
            time.sleep(2.5)
        except Exception as e:
            logger.error(f"[{player}] 브라우저 접속 에러: {e}")
            print(f"⚠️ {progress_str} [{player}] 브라우저 로딩 에러 건너뜀")
            continue
            
        try:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
        except UnexpectedAlertPresentException:
            try:
                alert = driver.switch_to.alert
                alert_text = alert.text
                alert.accept()
            except:
                alert_text = "알 수 없는 팝업"
            logger.info(f"[{player}] 네이버 팝업 발생: {alert_text}")
            print(f"⏩ {progress_str} [{player}] 네이버 미등록 선수로 스킵")
            continue
        
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
            logger.info(f"[{player}] {year}년 네이버 기록 없음 (출전기록 누락 등)")
            print(f"⏩ {progress_str} [{player}] {year}년 네이버 공식 기록이 없어 패스")
            continue
            
        tds = [td.text.strip() for td in target_tr.find_all('td')]
        if len(headers) - len(tds) == 1:
            headers = headers[1:]
            
        naver_stats = dict(zip(headers, tds))
        for k, v in naver_stats.items():
            try: naver_stats[k] = int(v)
            except: pass
                
        errors = []
        def check_diff(stat_name, parser_val, naver_key):
            if naver_key in naver_stats:
                diff = naver_stats[naver_key] - parser_val
                if diff != 0:
                    sign = "+" if diff > 0 else ""
                    errors.append(f"{stat_name} {sign}{diff}")
                    
        if player_type == "batter":
            p_AB = int(row['AB'])
            p_H = int(row['1B']) + int(row['2B']) + int(row['3B']) + int(row['HR'])
            p_2B = int(row['2B'])
            p_3B = int(row['3B'])
            p_HR = int(row['HR'])
            p_BB = int(row['BB'])
            p_SO = int(row['SO'])
            
            check_diff('AB', p_AB, '타수')
            check_diff('H', p_H, '안타')
            check_diff('2B', p_2B, '2루타')
            check_diff('3B', p_3B, '3루타')
            check_diff('HR', p_HR, '홈런')
            check_diff('BB', p_BB, '볼넷')
            check_diff('SO', p_SO, '삼진')
        else: # pitcher
            p_Outs = int(row['Outs'])
            p_H = int(row['H'])
            p_HR = int(row['HR'])
            p_BB = int(row['BB'])
            p_HBP = int(row['HBP'])
            p_SO = int(row['SO'])
            
            if '이닝' in naver_stats:
                n_outs = naver_ip_to_outs(str(naver_stats['이닝']))
                diff_outs = n_outs - p_Outs
                if diff_outs != 0:
                    sign = "+" if diff_outs > 0 else ""
                    integer_diff = diff_outs // 3
                    fraction_diff = diff_outs % 3
                    if diff_outs < 0:
                        abs_diff = abs(diff_outs)
                        integer_diff = -(abs_diff // 3)
                        fraction_diff = -(abs_diff % 3)
                    diff_ip_str = f"{integer_diff}.0" if fraction_diff == 0 else f"{integer_diff}.{abs(fraction_diff)}"
                    errors.append(f"IP {sign}{diff_ip_str}")
            
            h_key = '피안타' if '피안타' in naver_stats else ('안타' if '안타' in naver_stats else None)
            if h_key: check_diff('H', p_H, h_key)
            
            hr_key = '피홈런' if '피홈런' in naver_stats else ('홈런' if '홈런' in naver_stats else None)
            if hr_key: check_diff('HR', p_HR, hr_key)
            
            check_diff('BB', p_BB, '볼넷')
            check_diff('HBP', p_HBP, '사구')
            
            so_key = '탈삼진' if '탈삼진' in naver_stats else ('삼진' if '삼진' in naver_stats else None)
            if so_key: check_diff('SO', p_SO, so_key)
        
        if errors:
            logger.warning(f"[{player}] 오차 발생: " + ", ".join(errors))
            print(f"❌ {progress_str} [{player}] 오차 발생! (상세 로깅됨)")
            error_count += 1
        else:
            print(f"✅ {progress_str} [{player}] 완벽 일치")
            
    driver.quit()
    logger.info(f"[{type_kor}] 검증 완료. 총 {total_players}명 중 {error_count}명 오차 발생.")
    print(f"[{type_kor}] 검증 완료. 총 {total_players}명 중 {error_count}명 오차 발생. 상세 내역은 {log_file} 확인.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="대량 교차 검증 봇")
    parser.add_argument('--year', type=int, required=True, help="검증할 연도")
    args = parser.parse_args()
    
    run_bulk_validator(args.year, "batter")
    run_bulk_validator(args.year, "pitcher")
