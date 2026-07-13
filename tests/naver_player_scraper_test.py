import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def test_naver_player_page():
    # 75847 최정
    url = "https://m.sports.naver.com/player/index?playerId=75847&category=kbo&tab=record"
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.get(url)
    time.sleep(5)  # 렌더링 대기
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # 테이블이나 2017 텍스트 검색
    if '2017' in driver.page_source:
        print("✅ 2017년 기록이 페이지에 렌더링되었습니다!")
        # 보통 타자 기록은 테이블 형태나 리스트 형태로 있음
        # 네이버 모바일 페이지의 테이블 클래스나 div 찾기
        tables = soup.find_all('table')
        print(f"발견된 테이블 수: {len(tables)}")
        for i, table in enumerate(tables):
            if '2017' in table.text:
                print(f"--- 2017년 기록이 있는 {i}번째 테이블의 일부 HTML ---")
                print(str(table)[:500])
                break
    else:
        print("❌ 2017년 기록을 찾지 못했습니다.")
        
    driver.quit()

if __name__ == "__main__":
    test_naver_player_page()
