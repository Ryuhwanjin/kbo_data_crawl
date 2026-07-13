import os
import re
import datetime
import argparse
import requests
from bs4 import BeautifulSoup

# .env 환경변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# MLB 관련 해외 야구 차단용 블랙리스트 키워드 패턴
MLB_BLACKLIST_PATTERN = r"오타니|다저스|샌프란|샌디에고|파드리스|블루제이스|에인절스|메츠|컵스|카디널스|화이트삭스|필리스|브레이브스|마린스|내셔널스|브루어스|로키스|디백스|매리너스|레인저스|애스트로스|양키스|레드삭스|이정후|김하성|배지환|고우석|최지만|mlb|m.l.b.|메이저리그|해외야구|메이저|해외파|월드시리즈|포스트시즌\(mlb\)|자이언츠\(mlb\)"

def is_kbo_only(title, summary=""):
    """제목과 요약에서 메이저리그 관련 키워드를 검출하여 KBO 순수 기사인지 판별"""
    text = (title + " " + summary).lower()
    return not re.search(MLB_BLACKLIST_PATTERN, text)

def calculate_importance(title, summary=""):
    """기사 헤드라인 및 요약 키워드를 정밀 판독하여 중요도 별점(1~5개) 부여"""
    text = (title + " " + summary).lower()
    
    # 5성 (★★★★★): 메가톤급 특보
    if re.search(r"단독|속보|부상|방출|fa|계약|트레이드|징계|은퇴|수술|음주|쇼크|영입", text):
        return "★★★★★"
    # 4성 (★★★★☆): 주요 전술/인터뷰/대회 기록
    elif re.search(r"공식발표|엔트리|말소|감독|위닝|스윕|완봉|완투|연승|1군|콜업|올스타|mvp", text):
        return "★★★★☆"
    # 2성 (★★☆☆☆): 가벼운 일상 및 팬 포토
    elif re.search(r"미담|팬|사인|행사|일상|사진|포토|아내|기부|사인회", text):
        return "★★☆☆☆"
    # 3성 (★★★☆☆): 일반 야구 분석 및 통상 기사 (디폴트)
    return "★★★☆☆"

def clean_summary(summary):
    """뉴스 기사 요약문을 깔끔하게 최대 2줄(100자)로 다듬어 리턴"""
    if not summary:
        return "본문 요약이 없습니다. 링크를 통해 상세 뉴스를 확인하세요."
    # 태그 및 줄바꿈 제거
    clean = re.sub(r"<[^>]*>", "", summary)
    clean = clean.replace("\n", " ").replace("\r", " ").strip()
    # 100자 제한 및 말줄임표
    if len(clean) > 100:
        return clean[:97] + "..."
    return clean

def scrape_kbo_official():
    """KBO 공식 홈페이지 보도자료 게시판 크롤링"""
    url = "https://www.koreabaseball.com/News/Press/List.aspx"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    press_list = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.find("table", class_="tbl")
            if table:
                rows = table.find("tbody").find_all("tr")
                for r in rows:
                    cols = r.find_all("td")
                    if len(cols) >= 3:
                        title_td = cols[1]
                        a_tag = title_td.find("a")
                        title = title_td.text.strip()
                        link = "https://www.koreabaseball.com" + a_tag["href"] if a_tag else url
                        reg_date = cols[2].text.strip()
                        
                        # KBO 뉴스 필터링 및 중요도/요약 가공
                        if is_kbo_only(title):
                            summary = "KBO 공식 보도자료 및 일일 주요 발표 공지입니다."
                            press_list.append({
                                "title": title,
                                "link": link,
                                "date": reg_date,
                                "office": "KBO 공식",
                                "summary": summary,
                                "importance": calculate_importance(title, summary),
                                "source": "KBO 공식"
                            })
    except Exception as e:
        print(f"⚠️ KBO 공식 보도자료 수집 중 오류 발생: {e}")
        
    return press_list[:15] # 15개 확보

def scrape_naver_news():
    """네이버 야구 뉴스 메인 웹 API 호출로 다중 페이지 속보 기사 수집 (3페이지 다중 스캔 + KBO 필터링)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    naver_list = []
    # page=1부터 3까지 순회하여 다량의 뉴스 풀 확보 (최대 240개 수집)
    for page in range(1, 4):
        url = f"https://sports.news.naver.com/kbaseball/news/list?page={page}&pageSize=80"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news_list = data.get("list", [])
                for item in news_list:
                    title = item.get("title", "")
                    sub_content = item.get("subContent", "")
                    
                    # MLB 관련 해외 야구 뉴스 필터링
                    if not is_kbo_only(title, sub_content):
                        continue
                        
                    oid = item.get("oid", "")
                    aid = item.get("aid", "")
                    link = f"https://sports.news.naver.com/kbaseball/news/read?oid={oid}&aid={aid}"
                    office = item.get("officeName", "네이버 스포츠")
                    date_str = item.get("datetime", "")
                    
                    cleaned_sum = clean_summary(sub_content)
                    
                    # 이미 리스트에 담긴 링크인지 중복 검사
                    if not any(x['link'] == link for x in naver_list):
                        naver_list.append({
                            "title": title,
                            "link": link,
                            "date": date_str,
                            "office": office,
                            "summary": cleaned_sum,
                            "importance": calculate_importance(title, sub_content),
                            "source": "네이버"
                        })
        except Exception as e:
            print(f"⚠️ 네이버 야구 뉴스 수집 중 오류 발생 (page {page}): {e}")
            
    return naver_list

def scrape_mlbpark():
    """엠엘비파크 한국야구타운 최신/인기 게시글 크롤링 (KBO 필터링)"""
    url = "https://mlbpark.donga.com/mp/b.php?b=koreabaseball"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    mlb_list = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            titles = soup.find_all("div", class_="title")
            for t in titles:
                a_tag = t.find("a")
                if a_tag and "href" in a_tag.attrs:
                    title_text = a_tag.text.strip()
                    
                    # MLB 관련 해외 야구 글 필터링
                    if not is_kbo_only(title_text):
                        continue
                        
                    link = a_tag["href"]
                    if link.startswith("/mp/"):
                        link = "https://mlbpark.donga.com" + link
                    elif link.startswith("b.php"):
                        link = "https://mlbpark.donga.com/mp/" + link
                        
                    # 중복 적재 방지
                    if not any(item['link'] == link for item in mlb_list):
                        summary_txt = "엠엘비파크 한국야구타운 인기 토픽 토론글입니다."
                        mlb_list.append({
                            "title": title_text,
                            "link": link,
                            "office": "엠엘비파크",
                            "summary": summary_txt,
                            "importance": calculate_importance(title_text, summary_txt),
                            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "source": "엠엘비파크"
                        })
    except Exception as e:
        print(f"⚠️ 엠엘비파크 수집 중 오류 발생: {e}")
        
    return mlb_list[:10] # 최신 10개만 반환

def build_daily_report(kbo_news, naver_news):
    """수집된 다중 뉴스 소스를 병합하여 일일 요약 마크다운 생성"""
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    report_path = f"saber_data/daily_news_{today_str}.md"
    
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# 📰 KBO Daily Issue Report ({today_str})\n\n")
        f.write("본 리포트는 KBO 공식 보도자료 및 네이버 스포츠 주요 뉴스를 실시간 병합/분석한 결과입니다.\n\n")
        
        # 1. KBO 공식 발표 영역
        f.write("## 📢 KBO 리그 공식 공지 & 보도자료\n")
        if kbo_news:
            for item in kbo_news[:5]:
                f.write(f"* **[{item['date']}]** [{item['title']}]({item['link']})\n")
        else:
            f.write("* 오늘 등록된 KBO 공식 공지가 없습니다.\n")
        f.write("\n")
        
        # 2. 실시간 언론 속보 영역
        f.write("## ⚡ 실시간 KBO 핫이슈 & 언론 속보\n")
        if naver_news:
            for item in naver_news[:8]:
                f.write(f"* **[{item['office']}]** [{item['title']}]({item['link']})\n")
                if item['summary']:
                    f.write(f"  - *요약*: {item['summary'][:90]}...\n")
        else:
            f.write("* 수집된 실시간 야구 속보가 없습니다.\n")
            
    print(f"📝 [News Scraper] 일일 뉴스 요약 보고서 작성 완료 ➡️ {report_path}")
    return report_path

def post_to_discord(kbo_news, naver_news):
    """수집된 다중 소스 뉴스를 디스코드 채널로 발송"""
    if not DISCORD_WEBHOOK_URL:
        print("📢 [Dry-Run 모드] DISCORD_WEBHOOK_URL이 없어 디스코드 전송을 생략하고 터미널에 요약 출력합니다.")
        return
        
    # KBO 공식 3개 구성
    kbo_fields = ""
    for item in kbo_news[:3]:
        kbo_fields += f"• **[{item['date']}]** [{item['title']}]({item['link']})\n"
    if not kbo_fields:
        kbo_fields = "• 등록된 신규 공식 공지가 없습니다."
        
    # 네이버 속보 5개 구성
    naver_fields = ""
    for item in naver_news[:5]:
        naver_fields += f"• **[{item['office']}]** [{item['title']}]({item['link']})\n"
    if not naver_fields:
        naver_fields = "• 수집된 실시간 속보가 없습니다."

    payload = {
        "username": "KBO 뉴스 어그리게이터",
        "avatar_url": "https://raw.githubusercontent.com/naver/kbo-assets/main/emblems/KBO.png",
        "embeds": [
            {
                "title": "📰 오늘의 KBO Daily Issue & 뉴스 프리핑",
                "description": f"다중 소스 교차 수집을 통해 구성된 KBO 공식 이슈 및 핫토픽 헤드라인입니다.",
                "color": 0x070A13,
                "fields": [
                    {
                        "name": "📢 KBO 공식 발표 및 공정 보도자료",
                        "value": kbo_fields,
                        "inline": False
                    },
                    {
                        "name": "⚡ 실시간 언론 속보 & 대세 핫이슈",
                        "value": naver_fields,
                        "inline": False
                    }
                ],
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Multi-Source News Aggregator Engine"
                }
            }
        ]
    }
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code in [200, 204]:
            print("✅ [News Scraper] 디스코드 채널로 실시간 KBO 헤드라인 뉴스 포스팅 완료!")
        else:
            print(f"❌ 디스코드 뉴스 전송 실패 (상태 코드: {response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ 디스코드 뉴스 전송 중 에러 발생: {e}")

def main():
    parser = argparse.ArgumentParser(description="KBO 다중 소스 뉴스 스크래퍼 및 디스코드 어시스턴트")
    parser.add_argument("--post", action="store_true", help="수집 결과를 디스코드 채널로 즉시 발송")
    
    args = parser.parse_args()
    
    print("🚀 [News Scraper] KBO 공식 및 네이버 뉴스 크롤링 가동 시작...")
    kbo_news = scrape_kbo_official()
    naver_news = scrape_naver_news()
    
    # 1. 파일 보고서 생성
    build_daily_report(kbo_news, naver_news)
    
    # 2. 디스코드 송출 지시가 있을 경우 실행
    if args.post:
        post_to_discord(kbo_news, naver_news)

if __name__ == "__main__":
    main()
