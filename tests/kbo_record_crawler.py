import pandas as pd
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def crawl_kbo_official_stats_selenium(year):
    """
    KBO 공식 홈페이지에서 셀레니움을 통해 
    공식 타자 기록과 KBO 선수 고유 ID(pcode)를 긁어옵니다.
    """
    print(f"[{year}] KBO 공식 타자 기록 크롤링 (Selenium 가동 중...)")
    
    url = "https://www.koreabaseball.com/Record/Player/HitterBasic/Basic1.aspx"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"크롬 드라이버 에러: {e}")
        return None
        
    driver.get(url)
    time.sleep(2)
    
    all_data = []
    
    try:
        # 연도 선택
        season_select = Select(driver.find_element(By.ID, "cphContents_cphContents_cphContents_ddlSeason_ddlSeason"))
        season_select.select_by_value(str(year))
        time.sleep(2)
        
        # 규정타석을 채운 상위 선수들(보통 1~3페이지 정도) 파싱
        # (테스트용으로 1페이지만 먼저 수집. 전체 수집은 로직 확장 필요)
        for page_idx in range(1, 4):
            print(f"... {page_idx}페이지 크롤링 중")
            
            # 페이지 로딩 대기
            time.sleep(1)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            table = soup.find('table', {'class': 'tData'})
            if not table:
                break
                
            tbody = table.find('tbody')
            rows = tbody.find_all('tr')
            
            for row in rows:
                cols = row.find_all('td')
                if not cols or len(cols) < 15:
                    continue
                    
                # 선수 링크에서 KBO ID 추출 (예: playerId=76232)
                a_tag = cols[1].find('a')
                pcode = "Unknown"
                player_name = "Unknown"
                
                if a_tag:
                    player_name = a_tag.text.strip()
                    href = a_tag.get('href', '')
                    m = re.search(r'playerId=(\d+)', href)
                    if m:
                        pcode = m.group(1)
                else:
                    player_name = cols[1].text.strip()
                    
                # 컬럼 순서 (KBO 표 1 기준):
                # 순위, 선수명, 팀명, AVG, G, PA, AB, R, H, 2B, 3B, HR, TB, RBI, SAC, SF
                # 0    1       2     3    4  5   6   7  8  9   10  11  12  13   14   15
                try:
                    data_dict = {
                        'pcode': pcode,
                        'Player': player_name,
                        'PA_official': int(cols[5].text.strip()),
                        'AB_official': int(cols[6].text.strip()),
                        'H_official': int(cols[8].text.strip()),
                        '2B_official': int(cols[9].text.strip()),
                        '3B_official': int(cols[10].text.strip()),
                        'HR_official': int(cols[11].text.strip())
                    }
                    all_data.append(data_dict)
                except ValueError:
                    pass
            
            # 다음 페이지 클릭
            try:
                # KBO 페이징 구조: id="cphContents_cphContents_cphContents_ucPager_btnNo2"
                next_page_id = f"cphContents_cphContents_cphContents_ucPager_btnNo{page_idx + 1}"
                if page_idx == 5:
                    next_page_id = "cphContents_cphContents_cphContents_ucPager_btnNext"
                    
                next_btn = driver.find_element(By.ID, next_page_id)
                next_btn.click()
            except:
                break # 다음 페이지가 없으면 종료
                
        df = pd.DataFrame(all_data)
        out_file = f"kbo_official_batter_{year}.csv"
        df.to_csv(out_file, index=False, encoding='utf-8-sig')
        print(f"[{year}] KBO 공식 데이터 {len(df)}명 크롤링 완료 (pcode 포함) -> {out_file}")
        
    except Exception as e:
        print(f"크롤링 진행 중 에러: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    crawl_kbo_official_stats_selenium(2017)
