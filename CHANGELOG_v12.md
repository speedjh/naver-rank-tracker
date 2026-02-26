# v12 변경사항 (2026-02-25)

## 신규 기능
- **[새 API]** `GET /api/fetch-place-spots` - 플레이스 명소 자동 추출
  - 방법1: GraphQL getTrips (pcmap-api, 가장 안정적)
  - 방법2: Apollo ROOT_QUERY trips 파싱
  - 방법3: around 탭 Apollo State 파싱
- **[UI]** 명소 자동추출 🤖 버튼 추가 (15번째 명소 자동 입력)
- **[검색]** spot 목록 클릭으로 직접 선택 가능

## 개선
- **[순위확인]** `/api/check-place-rank` 완전 재작성
  - m.map.naver.com/search2 방식(최우선, 더 정확)
  - m.search.naver.com URL 패턴(businessId→place URL 패턴)
  - Naver 로컬 API(API 키 있을 때) 최종 fallback
- **[파일명]** 엑셀 다운로드 파일명 → `엑셀 다운로드 ( 비상용 ) - 플레이스/쇼핑.xlsx`
- **[데모]** minkukss URL → 도담산삼 플레이스 URL로 교체

## 버그 수정
- Content-Disposition UTF-8 인코딩 수정
- m.search businessId JSON 패턴 → place URL 패턴으로 수정
- placeSpotAnswer 입력 flex 레이아웃 개선
