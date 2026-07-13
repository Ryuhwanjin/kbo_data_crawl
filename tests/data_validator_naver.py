import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os

def validate_top_10_batters(year):
    print("==================================================")
    print(f"[{year}] 네이버 선수별 모바일 페이지 다이렉트 교차 검증 시작 (상위 3명)")
    print("==================================================")
    
    # 1. 파싱된 데이터 로드 (PA 기준 정렬)
    parsed_file = f"kbo_batter_saber_{year}.csv"
    if not os.path.exists(parsed_file):
        print(f"{parsed_file} 파일이 없습니다. kbo_sabermetrics.py 를 먼저 실행하세요.")
        return
        
    df_parsed = pd.read_csv(parsed_file)
    # pcode가 있는 선수들만
    df_parsed = df_parsed[df_parsed['pcode'].notna()]
    df_parsed = df_parsed[df_parsed['pcode'] != 'Unknown']
    
    top_10 = df_parsed.sort_values(by='PA', ascending=False).head(3)
    
    # 2. 크롬 드라이버 셋업
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"크롬 드라이버 에러: {e}")
        return
        
    # 비교할 스탯 리스트: (파서 컬럼명, 네이버 컬럼명)
    # 네이버 모바일 타자 기록 테이블 헤더 순서 (일반적):
    # 시즌 | 타율 | 경기수 | 타석 | 타수 | 득점 | 안타 | 2루타 | 3루타 | 홈런 | 타점 | 도루 | 볼넷 | 사구 | 삼진 | 장타율 | 출루율
    # 우리는 th 텍스트를 보고 매핑할 것이다.
    
    for idx, row in top_10.iterrows():
        pcode = str(int(row['pcode'])) if isinstance(row['pcode'], float) else str(row['pcode'])
        player = row['Player']
        
        print(f"👉 {player} (ID: {pcode}) 검증 중...")
        url = f"https://m.sports.naver.com/player/index?playerId={pcode}&category=kbo&tab=record"
        driver.get(url)
        time.sleep(2.5) # 페이지 렌더링 딜레이
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 2017년 기록 <tr> 찾기
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
            print(f"   ❌ {year}년 테이블을 찾지 못했습니다.")
            continue
            
        tds = [td.text.strip() for td in target_tr.find_all('td')]
        
        # 네이버 모바일 기록표는 '시즌'이 th에 있지만 td 배열에는 제외되는 경우가 많음 (밀림 현상)
        # 만약 len(headers) - len(tds) == 1 이면 headers[1:] 사용
        if len(headers) - len(tds) == 1:
            headers = headers[1:]
            
        naver_stats = dict(zip(headers, tds))
        
        # 숫자 변환
        for k, v in naver_stats.items():
            try:
                naver_stats[k] = int(v)
            except:
                pass
                
        # 파서 데이터 재조합
        p_PA = int(row['PA'])
        p_AB = int(row['AB'])
        p_H = int(row['1B']) + int(row['2B']) + int(row['3B']) + int(row['HR'])
        p_2B = int(row['2B'])
        p_3B = int(row['3B'])
        p_HR = int(row['HR'])
        p_BB = int(row['BB'])
        p_HBP = int(row['HBP'])
        p_SO = int(row['SO'])
        
        errors = []
        def check_diff(stat_name, parser_val, naver_key):
            if naver_key in naver_stats:
                diff = naver_stats[naver_key] - parser_val
                if diff != 0:
                    sign = "+" if diff > 0 else ""
                    errors.append(f"{stat_name} {sign}{diff}")
        
        # 모바일 기본 기록표에는 보통 타석, 사구가 없으므로 존재하는 컬럼만 검증
        check_diff('AB', p_AB, '타수')
        check_diff('H', p_H, '안타')
        check_diff('2B', p_2B, '2루타')
        check_diff('3B', p_3B, '3루타')
        check_diff('HR', p_HR, '홈런')
        check_diff('BB', p_BB, '볼넷')
        check_diff('SO', p_SO, '삼진')
        
        if errors:
            print(f"   ⚠️ 오차 발견: " + ", ".join(errors))
        else:
            print(f"   ✅ 완벽 일치! (PA: {p_PA})")
            
    driver.quit()
    print("==================================================")
    print("검증 완료")

if __name__ == "__main__":
    validate_top_10_batters(2017)
