# KBO PTS 야구 데이터 수집 및 정제 파이프라인 (KBO PTS Baseball Data Pipeline)

네이버 스포츠 경기 상세 릴레이 및 3D PTS(Pitch Tracking System) 투구 추적 데이터를 일괄 수집(Collect)하고, 정제 및 결합(Transform)하여 투구 단위 및 선수별 시즌 요약 정형 데이터셋(Tabular Data)을 구축하는 KBO 전용 데이터 엔지니어링 파이프라인입니다.

---

## 🏛️ 파이프라인 아키텍처 및 구성 파일

본 프로젝트는 수집(Extract), 변환(Transform), 적재(Load)의 ETL 단계를 유기적으로 수행합니다.

### 1. [naver_kbo_crawler.py](file:///Users/ryuhwanjin/Desktop/Project/인생/naver_kbo_crawler.py) (수집)
- 2017~2025시즌 KBO 정규시즌 및 포스트시즌 경기 일정을 조회하여 릴레이 JSON 원본 데이터를 다운로드합니다. (시범경기 자동 배제)
- 수집된 원본 파일은 `kbo_data/{year}/{month}/{day}/`와 같은 **일별 폴더 트리 구조**로 체계적으로 분류 적재됩니다.
- 중복 파일 스킵 기능과 IP 차단 방지용 안전 대기 시간(`delay`)이 내장되어 있습니다.

### 2. [naver_kbo_pipeline.py](file:///Users/ryuhwanjin/Desktop/Project/인생/naver_kbo_pipeline.py) (변환: 투구 단위 조인)
- 적재된 일별 폴더 트리 내의 모든 JSON 파일을 스캔하여 문자중계 텍스트와 3D PTS 투구 궤적 좌표를 병합합니다.
- 등가속도 운동 방정식을 이용해 홈플레이트를 통과하는 3차원 높이 변수 **`plate_z` (ft)**를 미적분 역학 공식을 통해 직접 계산하여 추가 적재합니다.
- 최종 정제된 1구 단위 투구 데이터는 [kbo_pitch_dataset.csv](file:///Users/ryuhwanjin/Desktop/Project/인생/kbo_data/kbo_pitch_dataset.csv) 파일로 저장됩니다.

### 3. [naver_kbo_summary.py](file:///Users/ryuhwanjin/Desktop/Project/인생/naver_kbo_summary.py) (변환: 선수별 요약 집계)
- 모든 경기 라인업의 당일 최종 성적을 기반으로 선수별 누적 비율 지표를 집계합니다.
- **타자**: 타석(`PA`), 타수(`AB`), 안타(`H`), 홈런(`HR`), 볼넷(`BB`), 사구(`HBP`), 삼진(`SO`)을 누계하고 타율(`AVG`), 출루율(`OBP`), 장타율(`SLG`), `OPS`를 자동으로 연산합니다.
  - *과거 데이터 중 일부 타석(pa)이 누락되는 데이터 유실 오류를 `PA = max(PA, AB + BB + HBP)` 경계 공식으로 자동 클리닝합니다.*
- **투수**: 실수형 이닝(`IP_float`), 자책점(`ER`), 피안타(`H`), 탈삼진(`SO`) 등을 집계하여 평균자책점(`ERA`)과 `WHIP`를 KBO 공식 기록법 규격에 맞게 계산합니다.
- 결과는 [kbo_batter_summary.csv](file:///Users/ryuhwanjin/Desktop/Project/인생/kbo_data/kbo_batter_summary.csv) 및 [kbo_pitcher_summary.csv](file:///Users/ryuhwanjin/Desktop/Project/인생/kbo_data/kbo_pitcher_summary.csv) 파일로 내보내집니다.

---

## 🛠️ 설치 및 실행 방법

### 1. 개발 환경 설정
본 프로젝트는 파이썬 가상환경 사용을 권장합니다.

```bash
# 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 필수 패키지(pandas, numpy, requests 등) 설치
pip install -r requirements.txt
```

### 2. 실행 프로세스 (ETL 순서)

#### Step 1: Raw Data 수집 (Extract)
```bash
# 2017~2024시즌 전체 KBO 경기 데이터 일괄 수집
python naver_kbo_crawler.py --years 2017,2018,2019,2020,2021,2022,2023,2024 --delay 1.5
```

#### Step 2: 투구 단위 및 선수별 정형 데이터 정제 (Transform & Load)
```bash
# 1구 단위 투구 궤적 데이터셋(CSV) 생성
python naver_kbo_pipeline.py

# 타자/투수 시즌 요약 데이터셋(CSV) 생성
python naver_kbo_summary.py
```
