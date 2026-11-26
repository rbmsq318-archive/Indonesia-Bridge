# Indoneisa Bridge v0.1

사용자 지정 이름을 그대로 사용한 독립 실행형 시장정보·수익화 프로토타입입니다.

## 실행
- `index.html`을 Chrome 또는 Edge에서 열면 됩니다. 설치, 로그인, API 키가 필요 없습니다. 인터넷 없이 기능을 사용 가능합니다(외부 공식 링크 제외).
- 화면에는 2021~2025년, 14개 HS4 품목, 2개 방향의 140개 **가상** 레코드가 포함됩니다. 실제 시장 규모나 규제 변경, 입찰 정보가 아닙니다.
- 메뉴: 시장 개요, 무역 데이터 탐색, 유망 품목 분석, 규제·사업 모니터, 관심 목록·알림, 리포트 센터, 수익화 실험실, 데이터·자동화 관리.
- 관심 품목, 관심 고객(개인정보 없는 시연), 수익 가정, 데이터 및 실행 기록은 브라우저 localStorage에 저장합니다. 파일 주소·브라우저가 바뀌거나 저장소를 지우면 기록이 사라질 수 있습니다. 파일을 외부 공개하지 않았습니다.
- 리포트는 TXT 및 CSV, 브라우저 인쇄 대화상자를 통해 PDF 저장 가능. CSV는 최신 연도 선택 품목 분석 결과입니다.

## Python 로컬 자동 처리
Python 3.9+ (외부 라이브러리 없음). 터미널에서 압축을 푼 폴더로 이동하여 실행:

```sh
python pipeline.py --input sample_data.json --watch watchlist.json --out output
```

생성 파일: `ranked.csv`, `alert_drafts.json`, `report.txt`, `run_log.jsonl`. 알림 초안만 만들며 실제 이메일을 전송하지 않습니다. 동일 명령을 Windows 작업 스케줄러 또는 cron에 등록하면 로컬 처리 작업을 예약할 수 있습니다(자동 예약 자체는 설정하지 않았습니다). 브라우저와 Python 저장소는 자동 동기화되지 않으며 데이터는 파일로 전달해야 합니다.

## 데이터 양식
`sample_data.json`을 참조. dataset_name, source_url, mode, rows 배열. 각 row: direction (`KR_ID` 또는 `ID_KR`), hs(4자리 문자열), name, sector, year, market_usd, bilateral_usd. 한국→인니는 인니 수입국 기준, 반대 방향은 한국 수입국 기준입니다. 시장액은 해당 HS의 전 세계 수입액이며 양국 수입액은 상대국으로부터의 수입액입니다. 동일 방향·HS·연도 중복 불가, 음수 불가, 양국 수입액은 전체 수입액 이하. 동일 방향/HS에서 명칭과 산업은 일관되어야 합니다. 누락된 연도/품목은 0으로 해석하면 안 됩니다. 비교 가능한 동일 연도·품목의 완전한 자료를 권장합니다.

점수: 성장률(45점, 0~25% 구간 선형), 선택 집합 내 로그 시장 규모(35점), 점유율 여력(20점). 데이터가 부족하면 점수 미산정. 규제·관세·수출경쟁력은 반영하지 않습니다. 필터별 점수는 달라질 수 있습니다. Python은 방향별 전체 집합 기준입니다.

## 상용화 전제
- UN Comtrade 공식 API 문서: https://comtrade.un.org/en/api-docs
- 이용조건: https://comtrade.un.org/en/license-agreement
- 재배포 정책: https://uncomtrade.org/docs/re-dissemination-of-data/
- 무료 API가 상업적 재배포 허가를 의미하지 않으므로 이용권한 확인 전 자동 수집을 켜지 않았습니다. 다른 소스도 별도 확인 필요.
- 실제 데이터 수집 어댑터, 서버 DB, 인증 및 권한, 결제·웹훅, 이메일 동의 및 발송, 모니터링, 호스팅은 차기 개발 범위. 수익 시뮬레이터와 잠재고객 등록은 가상 실험입니다. 실제 매출을 보장하지 않습니다.
- 상업화 전 실제 고객 인터뷰, 데이터 라이선스, 결제 비용과 사업자·세무·개인정보 관련 요건을 확인해야 합니다. KOICA 내부자료 및 개인정보를 사용하지 않았습니다.

## 개발 파일
`template.html`은 UI 원본, `build.py`는 가상 데이터 생성 코드. `index.html`은 데이터가 내장된 완성 파일입니다. 수정 후 재빌드 예시:

```sh
python build.py
python -c "from pathlib import Path; Path('index.html').write_text(Path('template.html').read_text(encoding='utf-8').replace('__SAMPLE__',Path('sample_data.json').read_text(encoding='utf-8')),encoding='utf-8')"
```
