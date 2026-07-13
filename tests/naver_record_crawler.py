import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def crawl_naver_official_stats(year):
    """
    네이버 스포츠 KBO 기록실을 헤드리스 브라우저로 띄워서 
    해당 연도 공식 타자 클래식 스탯을 긁어옵니다.
    """
    print(f"[{year}] 공식 KBO 타자 기록 크롤링 시작... (Source: 네이버 스포츠)")
    
    url = f"https://sports.news.naver.com/kbaseball/record/index?category=kbo&year={year}&type=batter"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"크롬 드라이버 로드 에러 (크롬 브라우저가 설치되어 있어야 합니다): {e}")
        return None
        
    try:
        driver.get(url)
        # 네이버 기록실 테이블이 로드될 때까지 최대 10초 대기
        # 네이버 기록실은 <div class="tbl_box"> 또는 <table id="regularTeamRecordList_table"> 구조를 가짐. 
        # 타자 기록은 보통 id="regularBatterRecordList_table" 이거나 tbl_box 안에 있음.
        time.sleep(3) # 추가 안전 대기
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 테이블 파싱
        # 네이버 타자 기록 테이블을 찾음
        dfs = pd.read_html(driver.page_source)
        
        target_df = None
        for df in dfs:
            if '선수' in df.columns or '선수명' in df.columns or '타율' in df.columns or 'H' in df.columns:
                target_df = df
                break
                
        if target_df is None:
            print("데이터를 찾을 수 없습니다. (테이블 파싱 실패)")
            driver.quit()
            return None
            
        # 컬럼 매핑 (네이버 기록실 컬럼명 기준)
        # 네이버: 순위, 선수명, 팀명, 타율, G, PA, AB, R, H, 2B, 3B, HR, TB, RBI, SAC, SF
        rename_dict = {
            '선수': 'Player',
            '선수명': 'Player',
            'PA': 'PA_official',
            'AB': 'AB_official',
            'H': 'H_official',
            '2B': '2B_official',
            '3B': '3B_official',
            'HR': 'HR_official',
            'BB': 'BB_official',
            'HBP': 'HBP_official',
            'SO': 'SO_official',
            '사구': 'HBP_official',
            '볼넷': 'BB_official',
            '삼진': 'SO_official'
        }
        
        target_df = target_df.rename(columns=rename_dict)
        
        # 규정타석 이상 선수들(또는 상위 100위까지의 페이징이 있다면 추가 처리 필요. 일단 첫 페이지 긁음)
        valid_cols = ['Player'] + [c for c in rename_dict.values() if c in target_df.columns and c != 'Player']
        target_df = target_df[valid_cols]
        
        out_file = f"official_batter_{year}.csv"
        target_df.to_csv(out_file, index=False, encoding='utf-8-sig')
        print(f"[{year}] 네이버 스포츠 공식 데이터 {len(target_df)}명 크롤링 완료 -> {out_file}")
        
        driver.quit()
        return target_df
            
    except Exception as e:
        print(f"크롤링 에러 발생: {e}")
        driver.quit()
        return None

if __name__ == "__main__":
    crawl_naver_official_stats(2017)
