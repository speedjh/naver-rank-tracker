# Pull Request: naver-rank-tracker v12

## 📋 PR 제목
`feat: Place 캠페인 자동화 완성 - 명소 자동추출 + 순위확인 다중방법 + Excel 비상용`

---

## 🎯 변경 범위
| 파일 | 변경 내용 | 라인 수 |
|------|-----------|--------|
| `app.py` | 새 API 3개 추가, 순위확인 재작성, 파일명 수정 | 1,467줄 |
| `templates/automation.html` | 명소 자동추출 UI, minkukss URL 교체 | 1,534줄 |

---

## 🔬 테스트 결과 (25개 이상)

### Round 1 — 초기 네트워크 테스트 (8/10 PASS)
| # | 테스트 | 결과 | 원인 |
|---|--------|------|------|
| T01 | 네이버 모바일 접근 | ✅ PASS | - |
| T02 | 플레이스 구좌 확인 | ✅ PASS | - |
| T03 | m.map ID 추출 | ✅ PASS | 75개 ID |
| T04 | 타겟 ID 순위 (m.map) | ✅ PASS | 10위 |
| T05 | 업체명 Apollo 추출 | ✅ PASS | 트라가 삼성점 |
| T06 | 좌표 추출 | ✅ PASS | x=127.055598 |
| **T07** | TripSummary 명소 | **❌ FAIL** | Apollo State에 TripSummary 없음 |
| T08 | GraphQL getTrips | ✅ PASS | 30개 명소 |
| T09 | 15번째 명소 | ✅ PASS | 맘스터치 서울시청점 |
| **T10** | m.search businessId JSON | **❌ FAIL** | businessId 키 없음 |

### 오류 수정 과정
1. **T07 오류**: `pcmap around?tab=spot` 페이지에는 TripSummary가 없음 확인
   - **원인**: 해당 탭은 초기 로드에 트립 데이터를 포함하지 않음
   - **해결**: GraphQL getTrips를 방법1(최우선)로 변경, Apollo는 방법2로 격하
   
2. **T10 오류**: m.search에 `"businessId"` JSON 키 없음
   - **원인**: 네이버 모바일 검색은 JSON 포함 없이 URL 패턴만 사용
   - **해결**: `place.naver.com/[cat]/ID` URL 패턴으로 변경

### Round 2 — 전체 테스트 (19/19 PASS)
| # | 테스트 | 결과 |
|---|--------|------|
| T01 | 네이버 모바일 접근 | ✅ |
| T02 | 플레이스 구좌 확인 | ✅ |
| T03 | m.map ID 추출 | ✅ |
| T04 | 타겟 ID 순위 (10위 확인) | ✅ |
| T05 | 업체명 추출 (Apollo) | ✅ |
| T06 | 좌표 추출 | ✅ |
| T07 | GraphQL getTrips | ✅ |
| T08 | 15번째 명소 | ✅ |
| T09 | m.search URL 패턴 | ✅ |
| T10 | 플레이스 구좌 없는 키워드 | ✅ |
| T15 | URL 정규식 | ✅ |
| T18 | 초성 추출 로직 | ✅ |
| T19 | 업체명 블러 | ✅ |
| T20 | 한글 파일명 인코딩 | ✅ |
| T23 | 엑셀 파일명 변경 | ✅ |
| T24 | minkukss 제거 | ✅ |
| T25 | UI 함수 존재 | ✅ |
| T_SYNTAX | app.py 문법 | ✅ |
| T_NEW_API | fetch-place-spots 라우트 | ✅ |

### Round 3 — 추가 테스트 (14/15 PASS)
| # | 테스트 | 결과 | 비고 |
|---|--------|------|------|
| T11 | API 라우트 5개 존재 | ✅ | |
| T12 | 엑셀 파일명 형식 | ✅ | 플레이스/쇼핑 분리 |
| T13 | UTF-8 Content-Disposition | ✅ | 2개 헤더 |
| T14 | 자동추출 UI | ✅ | |
| T15 | 도담산삼 URL 정확성 | ✅ | |
| **T16** | 초성 추출 (기대값 오류) | **❌** | 로직은 정확, 테스트 케이스 버그 |
| T17 | 라우트 수 23개 | ✅ | |
| T18 | MERGE_COLS 정의 | ✅ | |
| T19 | Place 상태변수 | ✅ | |
| T20 | 산삼 키워드 순위 | ✅ | |
| T21 | URL 패턴 다양성 | ✅ | restaurant×102, place×9 |
| T22 | 좌표 재추출 | ✅ | |
| T23 | GraphQL 30개 명소 | ✅ | |
| T24 | 15번째 공백제거 | ✅ | |
| T25 | 전체 순위 확인 통합 | ✅ | 10위 이내 |

### Round 4 — T16 재확인 (2/2 PASS)
- T16 테스트 케이스 기대값 오류였음 (ㅌ=터, ㅊ=치 구분 미숙)
- 실제 로직: `맘스터치서울시청점` → `ㅁㅅㅌㅊㅅㅇㅅㅊㅈ` ✅ 정확

---

## 📝 커밋 메시지 (세분화)

### Commit 1: `fix(excel): rename template to "엑셀 다운로드 ( 비상용 )"`
```
fix(excel): rename template files to standard format

- place excel: "[엑셀 다운로드 ( 비상용 ) - 플레이스.xlsx]"  
- shopping excel: "엑셀 다운로드 ( 비상용 ) - 쇼핑.xlsx"
- Both use UTF-8 Content-Disposition encoding
```

### Commit 2: `fix(demo): replace minkukss URL with 도담산삼 place URL`
```
fix(demo): replace minkukss smartstore URL with Naver Place URL

- Old: https://smartstore.naver.com/minkukss/products/5835104592
- New: https://m.place.naver.com/restaurant/1326727196/home
- Product name: 도담산삼 장뇌삼 → 도담산삼 (place name)
- Apply to both textarea demo and loadDemoData JS function
```

### Commit 3: `feat(rank): rewrite /api/check-place-rank with multi-method`
```
feat(rank): rewrite place rank check with 3-method fallback

Method priority:
1. m.map.naver.com/search2 (most accurate, /place/{id} URL)
2. m.search.naver.com (URL pattern: place.naver.com/cat/ID)
3. Naver Local Search API (only if API key available)

Bug fix: m.search does NOT contain "businessId" JSON key.
Must use URL pattern (place.naver.com/[category]/[id]) instead.

Returns: {keyword, has_section, rank, message, method}
```

### Commit 4: `feat(spots): add /api/fetch-place-spots endpoint`
```
feat(spots): add new API endpoint for auto-extracting place attractions

GET /api/fetch-place-spots?url=<place_url>&nth=15

Method priority:
1. GraphQL getTrips via pcmap-api.place.naver.com/graphql
   - Most reliable, returns up to 30 spots
   - Includes coordinate params (x, y) for accuracy
2. Apollo ROOT_QUERY trips parsing (cache hit scenario)
3. Apollo around tab TripSummary fallback

Returns: {ok, spots[], count, nth, spot_nth, spot_nth_clean, method}
- spot_nth_clean: whitespace removed (for mission answer)
```

### Commit 5: `feat(ui): add 🤖 spot auto-extract button`
```
feat(ui): add auto-extract spot button to Place campaign tab

- Button: "🤖 자동추출" next to placeSpotAnswer input
- Calls /api/fetch-place-spots with current URL
- Shows all extracted spots with clickable 15th highlight
- Status indicator for extraction method and count
- placeSpotAnswer layout: flex (input + button)
```

---

## 🚀 신규 기능 상세

### 1. `/api/fetch-place-spots` — 명소 자동 추출
```python
GET /api/fetch-place-spots
  ?url=https://m.place.naver.com/restaurant/1326727196/home
  &nth=15

Response:
{
  "ok": true,
  "pid": "1326727196",
  "spots": ["서울도서관 정보서비스과", "하늘광장갤러리", ...],
  "count": 30,
  "nth": 15,
  "spot_nth": "맘스터치 서울시청점",
  "spot_nth_clean": "맘스터치서울시청점",
  "method": "graphql_trips"
}
```

### 2. `/api/check-place-rank` — 순위 확인 (개선)
- **이전**: HTML place_section 파싱만 (순위 제한적)
- **이후**: m.map → m.search → API 3단계 폴백
- 각 결과에 `method` 필드 추가 (어떤 방법으로 찾았는지 표시)

### 3. 🤖 자동추출 버튼 UI
- 15번째 명소 자동 입력
- 모든 명소 목록 클릭하여 선택 가능
- 추출 상태 실시간 표시

---

## 🐛 수정된 버그

| 버그 | 원인 | 수정 방법 |
|------|------|----------|
| m.search businessId 없음 | 네이버 HTML에 JSON 키 미포함 | URL 패턴으로 대체 |
| TripSummary Apollo 없음 | around 탭 초기 로드에 미포함 | GraphQL 우선 방식으로 변경 |
| 엑셀 파일명 한글 미반영 | 이전 SKP 형식 유지 | "비상용" 형식으로 변경 |
| minkukss URL 남아있음 | 데모 데이터 미업데이트 | 플레이스 URL로 전체 교체 |

---

## ✅ 최종 API 목록 (23개 라우트)

| 라우트 | 메서드 | 설명 |
|--------|--------|------|
| `/` | GET | 메인 대시보드 |
| `/automation` | GET | 자동화 탭 |
| `/api/fetch-store-name` | GET | 쇼핑 스토어명 추출 |
| `/api/check-rank` | POST | 쇼핑 순위 확인 |
| `/api/automation/excel-export` | POST | 임시 Excel 생성 |
| `/api/fetch-place-name` | GET | 플레이스 업체명 추출 |
| **`/api/fetch-place-spots`** | GET | **[NEW] 명소 목록 추출** |
| `/api/check-place-rank` | POST | 플레이스 순위 확인 (개선) |
| `/api/automation/place-excel-fill` | POST | 플레이스 Excel 채우기 |
| `/api/automation/excel-fill` | POST | 쇼핑 Excel 채우기 |

---

## 📌 사용 방법

### 명소 자동 추출
1. 플레이스 탭 → 주문 데이터 붙여넣기
2. 행 선택 후 **🤖 자동추출** 버튼 클릭
3. 15번째 명소 자동 입력 (클릭으로 다른 명소 선택 가능)
4. 시트 생성 → Excel 다운로드

### 순위 확인
- **강남맛집** 검색 → 1326727196이 **10위**에서 발견됨
- 방법: `m.map` 방식 (가장 정확)
- 30위 밖이면 "키워드 변경 권장" 경고

---

## ⚠️ 알려진 제한사항
- Naver rate limiting: 연속 요청 시 429 응답 가능 (0.5초 딜레이 권장)
- GraphQL pcmap-api: 세션 없이도 작동하지만 간헐적 429 발생 가능
- 명소 탭이 없는 플레이스는 spots API 실패 (ok: false 반환)
