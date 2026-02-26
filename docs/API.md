# Naver Rank Tracker — API 문서

> **프로젝트**: `speedjh/naver-rank-tracker`  
> **서버**: Flask (Python)  
> **Base URL**: `https://naver-rank-tracker-ql90.onrender.com`  
> **최종 업데이트**: 2026-02-26  

---

## 목차

| # | 엔드포인트 | 설명 |
|---|-----------|------|
| 1 | [`POST /api/check-rank`](#1-post-apicheck-rank) | 네이버 쇼핑 순위 체크 |
| 2 | [`POST /api/check-place-rank`](#2-post-apicheck-place-rank) | 네이버 플레이스 순위 체크 |
| 3 | [`GET /api/fetch-store-name`](#3-get-apifetch-store-name) | 스마트스토어 업체명 조회 |
| 4 | [`GET /api/fetch-place-name`](#4-get-apifetch-place-name) | 플레이스 업체명 조회 |
| 5 | [`GET /api/fetch-place-spots`](#5-get-apifetch-place-spots) | 플레이스 명소 목록 조회 |
| 6 | [`POST /api/automation/excel-export`](#6-post-apiautomationexcel-export) | 새 엑셀 파일 생성 (쇼핑/플레이스) |
| 7 | [`POST /api/automation/place-excel-fill`](#7-post-apiautomationplace-excel-fill) | 플레이스 템플릿 엑셀 채우기 |
| 8 | [`POST /api/automation/excel-fill`](#8-post-apiautomationexcel-fill) | 쇼핑 템플릿 엑셀 채우기 |

---

## 공통 컬럼 구조 (v15)

> 쇼핑/플레이스 모두 동일한 A~O 15컬럼 구조를 사용합니다.

| 열 | 인덱스(0-based) | 내용 | 비고 |
|----|----------------|------|------|
| A | 0 | 구분 (일반 / 플레이스) | 5행 병합 |
| B | 1 | 유형 (WEB / APP) | - |
| C | 2 | 시작일 | 5행 병합 |
| D | 3 | 종료일 | 5행 병합 |
| E | 4 | 총예산 (120% 상향) | 5행 병합, **수식 보존** |
| F | 5 | 총예산 수식 | 5행 병합, **수식 보존** |
| G | 6 | 일예산 수식 | 5행 병합, **수식 보존** |
| H | 7 | 포인트 (10) | 5행 병합, **수식 보존 — 절대 덮어쓰지 않음** |
| I | 8 | 검색어 (키워드) | 행별 독립값 |
| J | 9 | 미션내용 | 행별 독립값 |
| K | 10 | 정답 (명소명 / PID 앞 5자리) | 행별 독립값 |
| L | 11 | 힌트 URL | 행별 독립값 |
| M | 12 | 업체명 | 행별 독립값 |
| N | 13 | 일유입목표 | 5행 병합 |
| O | 14 | 글자수 수식 | 5행 병합, **수식 보존** |

> ⚠️ **H열(인덱스 7)은 수식(`=IF(H2=10, N*55, N*40)`)이 들어있어 어떠한 경우에도 값을 쓰지 않습니다.**  
> `FORMULA_OFFSETS = {4, 5, 6, 7, 14}` 로 보호됩니다.

---

## 1. `POST /api/check-rank`

### 설명
네이버 쇼핑 Open API를 통해 특정 상품(PID)의 키워드별 순위를 조회합니다.  
검색 결과 상위 **30개** 중 PID가 포함된 인덱스를 반환합니다.

### 요청

```
POST /api/check-rank
Content-Type: application/json
```

```json
{
  "jobs": [
    {
      "pid": "상품PID (문자열)",
      "url": "상품URL (선택)",
      "keywords": ["키워드1", "키워드2"]
    }
  ]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `jobs` | array | ✅ | 순위 조회 작업 배열 |
| `jobs[].pid` | string | ✅ | 네이버 쇼핑 상품 PID |
| `jobs[].keywords` | array | ✅ | 순위를 확인할 키워드 목록 |
| `jobs[].url` | string | ❌ | 상품 URL (응답 에코용) |

### 응답

```json
{
  "ok": true,
  "results": [
    {
      "pid": "123456789",
      "url": "https://...",
      "keywords": [
        { "keyword": "키워드1", "rank": 3 },
        { "keyword": "키워드2", "rank": 0 }
      ]
    }
  ]
}
```

| 필드 | 설명 |
|------|------|
| `rank` | 1~30 : 해당 순위 / `0` : 30위 이내 없음 / `null` : API 오류 |

### 내부 로직

```
Naver Shopping API (sort=sim, display=30)
  → items 순회
  → productId 또는 link의 /products/{id} 에서 PID 매칭
  → 매칭된 인덱스 + 1 = rank
```

### 새 플랫폼 적용 예시

> 쿠팡, 11번가 등 다른 쇼핑 플랫폼에 적용 시:
> - `get_rank()` 함수 내 API URL만 교체
> - PID 추출 정규식을 해당 플랫폼 URL 패턴으로 변경
> - 나머지 `jobs` 구조는 동일하게 재사용 가능

---

## 2. `POST /api/check-place-rank`

### 설명
네이버 지도/플레이스 영역에서 특정 업체의 키워드별 순위와 구좌(섹션) 노출 여부를 확인합니다.  
총 **3가지 방법**을 순차적으로 시도합니다.

### 요청

```
POST /api/check-place-rank
Content-Type: application/json
```

```json
{
  "keywords": ["키워드1", "키워드2"],
  "url": "https://m.place.naver.com/restaurant/1326727196/home"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `keywords` | array | ✅ | 순위를 확인할 키워드 목록 |
| `url` | string | ✅ | 네이버 플레이스 URL |

### 응답

```json
{
  "ok": true,
  "rank_blocked": false,
  "results": [
    {
      "keyword": "강남 맛집",
      "has_section": true,
      "rank": 7,
      "message": "7위",
      "method": "mmap"
    }
  ]
}
```

| 필드 | 설명 |
|------|------|
| `has_section` | 플레이스 구좌(섹션) 노출 여부 |
| `rank` | 1~30: 순위 / `0`: 미노출 / `null`: 확인 불가 |
| `rank_blocked` | 순위 체크가 차단된 경우 `true` |
| `method` | 성공한 방법: `mmap`, `msearch`, `local-api` |

### 내부 로직 (3단계 폴백)

```
Step 1: m.map.naver.com 검색 크롤링
  → 검색 결과 HTML에서 place_id 추출 → 순위 계산

Step 2: m.search.naver.com 모바일 검색 크롤링
  → 플레이스 섹션 존재 여부 + 업체 순위 추출

Step 3: 네이버 로컬 API (v1/search/local.json)
  → 최대 5페이지 × 5개 = 25개 결과 순회
  → mapx/mapy 좌표 또는 업체명으로 매칭
```

### 새 플랫폼 적용 예시

> 카카오맵, 구글맵 등 적용 시:
> - `check_rank_for_keyword()` 함수를 복사하여 내부 크롤링 URL/파싱 로직만 변경
> - `has_section`, `rank`, `method` 반환 구조는 동일하게 유지
> - `rank_blocked` 감지 조건을 해당 플랫폼 특성에 맞게 조정

---

## 3. `GET /api/fetch-store-name`

### 설명
스마트스토어 slug와 상품 PID를 기반으로 업체명(mallName)을 조회합니다.

### 요청

```
GET /api/fetch-store-name?slug=mystore&pid=123456789&keyword=검색어
```

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `slug` | string | ✅ | 스마트스토어 URL slug |
| `pid` | string | ✅ | 상품 PID |
| `keyword` | string | ❌ | PID 매칭에 사용할 검색어 |

### 응답

```json
{
  "ok": true,
  "name": "가게이름",
  "slug": "mystore",
  "source": "api-kw"
}
```

| `source` 값 | 설명 |
|------------|------|
| `api-kw` | 쇼핑 API keyword+PID 매칭 성공 |
| `api-slug` | 쇼핑 API slug+PID 매칭 성공 |
| `crawl` | 스마트스토어 og:title 크롤링 |
| `crawl-title` | title 태그 크롤링 |
| `slug` | 모든 방법 실패, slug 그대로 반환 |

### 내부 로직

```
1순위: Shopping API (keyword + PID 매칭) → mallName
2순위: Shopping API (slug + PID 매칭) → mallName
3순위: smartstore.naver.com/{slug} 크롤링 → og:title or <title>
폴백: slug를 name으로 그대로 반환
```

---

## 4. `GET /api/fetch-place-name`

### 설명
네이버 플레이스 URL에서 업체명을 추출합니다.

### 요청

```
GET /api/fetch-place-name?url=https://m.place.naver.com/restaurant/1326727196/home
```

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `url` | string | ✅ | 네이버 플레이스 전체 URL |

### 응답

```json
{
  "ok": true,
  "name": "홍길동 음식점",
  "pid": "1326727196",
  "source": "apollo"
}
```

| `source` 값 | 설명 |
|------------|------|
| `apollo` | Apollo State JSON에서 추출 |
| `og` | og:title 메타태그에서 추출 |
| `title` | `<title>` 태그에서 추출 |

### 지원 플레이스 카테고리

`restaurant`, `cafe`, `hospital`, `beauty`, `hairshop`, `store`, `place`

---

## 5. `GET /api/fetch-place-spots`

### 설명
특정 플레이스의 '가볼만한곳(명소)' 목록을 자동 추출합니다.  
미션 자동화에서 **K열(정답) 후보 생성**에 사용됩니다.

### 요청

```
GET /api/fetch-place-spots?url=https://m.place.naver.com/restaurant/1326727196/home&nth=15
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| `url` | string | ✅ | - | 네이버 플레이스 URL |
| `nth` | int | ❌ | 15 | 선택할 명소 순번 (1-based) |

### 응답

```json
{
  "ok": true,
  "spots": ["명소1", "명소2", "..."],
  "count": 20,
  "nth": 15,
  "spot_nth": "명소15",
  "spot_nth_clean": "명소15",
  "method": "graphql"
}
```

| 필드 | 설명 |
|------|------|
| `spots` | 전체 명소 이름 배열 |
| `count` | 총 명소 개수 |
| `spot_nth` | `nth`번째 명소 (원문) |
| `spot_nth_clean` | 정제된 명소명 |
| `method` | 성공한 방법 |

### 내부 로직 (3단계 폴백)

```
Step 1: GraphQL getTrips (pcmap-api.place.naver.com)
  → 가장 안정적, 구조화된 데이터 반환

Step 2: Apollo State ROOT_QUERY 파싱 (PC map 캐시)
  → HTML 내 JSON 스크립트 파싱

Step 3: m.place around HTML 스크립트 파싱
  → 주변 장소 HTML 직접 파싱
```

---

## 6. `POST /api/automation/excel-export`

### 설명
캠페인 데이터를 **새 .xlsx 파일**로 생성하여 다운로드합니다.  
쇼핑 및 플레이스 캠페인 모두 지원합니다.

### 요청

```
POST /api/automation/excel-export
Content-Type: application/json
```

```json
{
  "type": "place",
  "campaigns": [
    {
      "rows": [
        ["일반", "APP", "2025-01-01", "2025-01-31", "", "", "", "", "키워드1", "미션내용1", "정답", "힌트URL", "업체명", 50, ""],
        ["__merge__", "APP", "__merge__", "__merge__", "__merge__", "__merge__", "__merge__", "__merge__", "키워드2", "미션내용2", "정답", "힌트URL", "업체명", "__merge__", "__merge__"],
        ...
      ]
    }
  ]
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `type` | string | ❌ | `"shop"` 또는 `"place"` (기본: `"shop"`) |
| `campaigns` | array | ✅ | 캠페인 배열 |
| `campaigns[].rows` | array | ✅ | 각 캠페인의 행 데이터 (15컬럼 × 5행) |

### 행 구조 규칙

- 각 캠페인은 **5개 행** (키워드 5개)으로 구성
- `__merge__`는 병합 셀 자리 표시자 (백엔드에서 빈 문자열 처리)
- **H열(인덱스 7)은 항상 `''` 또는 `'__merge__'` — 수식 보존**

### 응답

```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename=campaign.xlsx
```

xlsx 바이너리 파일 반환

### 병합 열 목록

`A(1), C(3), D(4), E(5), F(6), G(7), H(8), N(14), O(15)` — 각 캠페인 5행씩 병합

---

## 7. `POST /api/automation/place-excel-fill`

### 설명
업로드된 **기존 엑셀 템플릿**에 플레이스 미션 데이터를 채워넣습니다.  
수식과 서식이 보존된 상태로 데이터만 삽입됩니다.

### 요청

```
POST /api/automation/place-excel-fill
Content-Type: multipart/form-data
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `file` | file | ✅ | 기존 XLSX 템플릿 파일 |
| `payload` | string | ✅ | JSON 문자열 (캠페인 데이터) |
| `start_row` | int | ❌ | 데이터 시작 행 번호 (기본: 3) |
| `start_col` | int | ❌ | 데이터 시작 열 번호 (기본: 1) |

`payload` JSON 구조:

```json
{
  "campaigns": [
    {
      "rows": [ [...15개 값...], [...], [...], [...], [...] ]
    }
  ]
}
```

### 응답

xlsx 바이너리 파일 반환

### 수식 보존 규칙

```
FORMULA_OFFSETS = {4, 5, 6, 7, 14}
  → 인덱스 4(E), 5(F), 6(G), 7(H), 14(O) 열은 쓰기 건너뜀
  → 템플릿의 기존 수식이 그대로 유지됨
```

> ⚠️ **H열(인덱스 7)은 FORMULA_OFFSETS에 포함되어 템플릿 수식이 절대 덮어써지지 않습니다.**

---

## 8. `POST /api/automation/excel-fill`

### 설명
업로드된 **기존 엑셀 템플릿**에 쇼핑 캠페인 데이터를 삽입합니다.  
플레이스 버전(`place-excel-fill`)과 동일한 구조이나 쇼핑 전용 컬럼 처리가 포함됩니다.

### 요청

```
POST /api/automation/excel-fill
Content-Type: multipart/form-data
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `file` | file | ✅ | 기존 XLSX 템플릿 파일 |
| `payload` | string | ✅ | JSON 문자열 (캠페인 데이터) |
| `start_row` | int | ❌ | 데이터 시작 행 번호 (기본: 3) |
| `start_col` | int | ❌ | 데이터 시작 열 번호 (기본: 1) |

### 응답

xlsx 바이너리 파일 반환

### 수식 보존 규칙

```
FORMULA_OFFSETS = {4, 5, 6, 7, 14}
  → 쇼핑 캠페인도 동일하게 H열 수식 보존
```

---

## 오류 응답 공통 형식

```json
{
  "ok": false,
  "error": "오류 메시지"
}
```

| HTTP 코드 | 상황 |
|----------|------|
| `400` | 필수 파라미터 누락 |
| `404` | 리소스 없음 |
| `409` | 이미 처리 중 |
| `500` | 서버 내부 오류 |

---

## 새 플랫폼 개발 가이드

새로운 쇼핑/지도 플랫폼 순위 체커를 추가할 때 참고하세요.

### 쇼핑 순위 체커 추가 (예: 쿠팡)

```python
# app.py에 추가
@app.route("/api/check-coupang-rank", methods=["POST"])
def api_check_coupang_rank():
    """쿠팡 키워드별 순위 확인 — /api/check-rank 구조 참조"""
    data = request.get_json(force=True)
    jobs = data.get("jobs", [])  # [{pid, url, keywords:[]}]

    def get_coupang_rank(pid, keyword):
        # 1. 쿠팡 검색 API 또는 크롤링
        # 2. PID 매칭 → rank 반환
        pass

    results = []
    for job in jobs:
        pid = str(job.get("pid", ""))
        kws = job.get("keywords", [])
        kw_results = [{"keyword": kw, "rank": get_coupang_rank(pid, kw)} for kw in kws]
        results.append({"pid": pid, "url": job.get("url",""), "keywords": kw_results})

    return jsonify({"ok": True, "results": results})
```

**요청 시 참조 표현**: `"쿠팡 순위 체크 추가 — /api/check-rank 구조 따라서"`

### 지도 플랫폼 순위 체커 추가 (예: 카카오맵)

```python
@app.route("/api/check-kakaomap-rank", methods=["POST"])
def api_check_kakaomap_rank():
    """카카오맵 키워드별 플레이스 순위 확인 — /api/check-place-rank 구조 참조"""
    data = request.get_json(force=True)
    keywords = data.get("keywords", [])
    url = data.get("url", "")  # 카카오맵 장소 URL

    # 카카오 place_id 추출
    # 키워드 검색 크롤링
    # has_section, rank 반환

    return jsonify({
        "ok": True,
        "results": [
            {"keyword": kw, "has_section": True, "rank": 1, "message": "1위", "method": "kakao"}
            for kw in keywords
        ]
    })
```

**요청 시 참조 표현**: `"카카오맵 플레이스 순위 체크 추가 — /api/check-place-rank 구조 따라서"`

---

## 다음에 요청할 때 이렇게 말하면 됩니다

| 하고 싶은 작업 | 요청 표현 |
|--------------|-----------|
| 쿠팡 순위 체크 추가 | "쿠팡 순위 체크 API 추가해줘 — `/api/check-rank` 구조 참조" |
| 카카오맵 순위 체크 추가 | "카카오맵 플레이스 순위 체크 추가 — `/api/check-place-rank` 폴백 3단계 구조 참조" |
| 새 엑셀 열 추가 | "v15 컬럼 구조에 P열 추가 — FORMULA_OFFSETS, MERGE_COLS 포함해서" |
| 미션 템플릿 변수 추가 | "미션 템플릿에 `{new_var}` 추가 — `generatePlaceAll()` 치환 로직 참조" |
| 자동화 페이지 버튼 추가 | "플레이스 시트 생성 버튼 옆에 '초기화' 버튼 추가 — `generatePlaceAll()` 참조" |

---

*Generated from commit [`c5511884`](https://github.com/speedjh/naver-rank-tracker/commit/c5511884f0dc00e460a0a224a3c1476858629d88) · 2026-02-26*
