# Indonesia Bridge v0.2 — Big Data Edition

서버형 웹사이트 프로토타입 (Python HTTP API + SQLite + 웹 UI). 실제 공개 URL은 아직 발급하지 않았습니다. 기본값은 로컬 전용입니다. 외부 배포 전 인증/권한/데이터 이용조건 검토가 필요합니다.

## 로컬 실행 (Windows)
1. ZIP 압축 해제 후 폴더에서 PowerShell 실행 (Python 3.10+ 설치 필요).
2. `python -m pip install -r requirements.txt` (Excel 가져오기를 위한 openpyxl).
3. `python server.py` 실행. 최초 실행에 DB 및 가상 데이터 자동 생성.
4. 브라우저에서 `http://127.0.0.1:8000` 열기. PowerShell 창을 종료하면 사이트도 종료.
5. 가져오기 기능을 쓰려면 서버 시작 전에 `$env:IB_ADMIN_TOKEN = '직접 생성한 강력한 비밀값'` 설정. 해당 값은 본인만 관리. 운영 환경에서는 HTTPS 필수.

## 데이터 구성
- demo: 130,560개 가상 월별 행, 2016~2025, 32개 HS4 품목, 인니/한국 각각의 수입 신고국 기준, 상대국 + 15개 지정 비교국 + 세계 합계. 비교국은 실측 순위가 아님. demo 수치는 판매·시장판단 불가.
- kcs: 관세청 API로 적재한 한국 신고국의 월별 수출/수입. 초기 0건. 관세청 한국 수출 FOB를 인도네시아 수입 CIF로 간주하지 않음.
- imported: 별도 사용자 제공 자료. 초기 0건. 출처·허가 미검증; 같은 source/reporter/partner/flow/period/hs/revision 키는 갱신되므로 서로 다른 출처나 방법론을 같은 revision에 혼합하지 말 것. 서버 운영 전에 출처별 데이터셋 관리 확장 필요.
- HS 카탈로그: 데모 32개 + 사용자가 가져온 코드표 검색. 공식 전체 코드표는 미확보. HS 버전별 분리. HS 2/4/6/10단위는 별도로 조회하며 서로 합산하지 않음. 실제 비교 가능한 HS 개정 연계표는 미연동.
- 연간 비교: 12개월 관측이 있는 경우에만 표시. 세계 전체는 WORLD 자료가 있어야 산정. 결측을 0으로 가정하지 않음. 서로 다른 신고국/방향/HS 버전을 자동 결합하지 않음. UI 연도 선택은 2016~2025로 고정.
- 점수: 성장률 0~25% 구간 45점, 절대 로그 규모 log10(USD)/10 (최대 35점), 상대국 비중 여력 20점. 실제 성공 확률 아님.

## 실제 자료 수집
공식 API: https://www.data.go.kr/data/15100475/openapi.do
공공데이터포털에서 활용 신청 후 디코딩 서비스키를 환경변수에 저장. 운영단계 승인은 별도 확인.

PowerShell 예시:
```
$env:KCS_SERVICE_KEY = '본인 발급 디코딩 키'
python collector.py --hs 3304 --partners ID --start 2025 --end 2025 --revision HS2022 --max-calls 1
```
위 예시는 2025년 코드 버전 확인 후 실행. 응답 XML 파서는 fixture 검증 완료, 실제 API 연결은 미검증. 수집기는 연도별 최대 1년 조회, 호출 상한, 중복 키 갱신 지원. 실제 조회 가능 기간/HS 버전/쿼터를 확인하고 범위를 늘릴 것. Windows 작업 스케줄러/cron에서 실행 가능하나 현재 예약되지 않음. 오류 시 중단. 실제 100,000행 목표는 승인 후 수집량 확인으로 진행. 인니 신고국 기반 경쟁국 비교는 허가된 별도 자료 필요. UN Comtrade 이용조건: https://uncomtrade.org/docs/re-dissemination-of-data/ (수집기 미연동).

## 파일 연동
`python data.py import trade.csv` 또는 `.xlsx` / `.json` (rows 배열 또는 배열 자체). 헤더: `reporter,partner,flow,period,hs,revision,name,usd,kg`. reporter KR/ID, partner ISO2 또는 WORLD, flow M/X, period YYYYMM, hs 문자열로 저장, revision 실제 HS 버전, USD 금액, kg 선택. 한 파일 안의 중복 키, 음수, 잘못된 형식은 거부. 0과 미관측을 구분하려면 미관측 행을 생성하지 말 것. xlsx는 첫 시트 사용. 코드표: `python data.py catalog hs.csv` (hs,revision,name). CLI는 관리자 전용. 브라우저 업로드는 50MB 제한 및 관리자 토큰 요구. CSV 다운로드는 선택 연도·신고국·자료·HS 단위·버전 기준 전체 원자료(검색어 필터 미반영), 상세 화면은 HS별 다운로드. 보고서는 현재 검색 결과 인쇄/PDF 저장. CSV 외 Excel/JSON 내보내기는 미구현.

## 기존 기능
`/legacy`에 기존 v0.1 전체 8개 메뉴 보존. 기존 보고서/알림 초안, 수익화 실험실, 고객 등록, 규제·사업 모니터는 기존 가상 데이터와 브라우저 저장소 사용. 새 v0.2 DB와 자동 동기화되지 않음. v0.2 관심 목록도 브라우저별 저장. 회원·결제·실제 이메일·유료 서비스 미연동.

## 배포
Render용 `render.yaml` 제공(배포 미실행). 코드 저장소/호스팅 계정 연결 후, 개발자 프리뷰 배포 및 주소 확인. Render 서비스명 제안: indonesia-bridge (이용 가능 여부 미확인). 개인 도메인 `indonesiabridge.com`은 후보일 뿐이며 보유/가용 여부 확인 및 결제하지 않음. 서버 외부 주소를 만들기 전 접속 제한을 별도로 구성할 것. 현 웹 서버는 개발용이며 공개 상용 운영 전 WSGI/ASGI 서비스, HTTPS, 회원 인증·권한, rate limit, 보안 검토, 운영 DB, 백업, 지속 디스크가 필요. SQLite 파일이 임시 디스크에 있으면 배포 재시작 시 소실 가능. `IB_DB`로 지속 볼륨 경로 지정. 실제 데이터는 허가 없는 공개 금지. 개인정보/결제정보 업로드 금지. 가격/요금제는 별도 확인.

## 검증
`python test_smoke.py` (별도 playwright 및 chromium 필요, 개발 테스트 전용). API HTTP 요청은 실제 로컬 서버 대상. 테스트 환경에서 브라우저 직접 URL 접근이 차단되어 브라우저는 HTML/CSS/JS 주입 + Python HTTP relay 방식으로 검증. SQL 130,560행, 월간 120개월, 32개 HS, 15개 비교국, 파일 적재 3형식, 관리자 토큰, 불완전 연도 제외, HS 검색, 상세, 월간 차트, 관심 저장, 마진, 운영 화면, v0.1 메뉴 표시 테스트 통과. 실제 외부 API, 공개 도메인, 결제, 다운로드/인쇄 및 브라우저 직접 주소 접속은 미검증.
