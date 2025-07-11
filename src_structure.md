# 소스코드 디렉토리 구조 (Source Code Directory Structure)

## 📁 프로젝트 전체 구조

```
assessmentSystem/
├── docs/                                    # 문서 디렉토리
│   ├── 인적성평가시스템_요건정의서.md        # 시스템 요건정의서
│   └── ...
├── aptitude_system/                        # 메인 소스코드 디렉토리 (src/)
│   ├── app.py                              # 메인 Flask 애플리케이션
│   ├── models.py                           # 데이터 모델 및 관리자
│   ├── check_time.py                       # 시간 체크 유틸리티
│   ├── create_sample_logo.py               # 샘플 로고 생성 스크립트
│   ├── config.json                         # 설정 파일
│   ├── requirements.txt                    # Python 의존성 목록
│   ├── README.md                           # 프로젝트 설명서
│   ├── data/                               # 데이터 파일 디렉토리
│   ├── static/                             # 정적 파일 디렉토리
│   └── templates/                          # HTML 템플릿 디렉토리
├── static/                                 # 루트 정적 파일
├── requirements.txt                        # 루트 의존성 파일
└── README.md                               # 프로젝트 메인 문서
```

---

## 🐍 Python 소스코드 파일

### 1. `app.py` - 메인 애플리케이션
**위치**: `aptitude_system/app.py`  
**역할**: Flask 웹 애플리케이션의 메인 진입점

#### 주요 기능
- **라우트 정의**: 모든 웹 페이지 및 API 엔드포인트
- **요청 처리**: 사용자 요청 처리 및 응답 생성
- **세션 관리**: 사용자 세션 및 상태 관리
- **오류 처리**: 예외 상황 처리 및 로깅

#### 주요 라우트
```python
# 사용자 화면
@app.route('/')                    # 메인 페이지
@app.route('/register')            # 지원자 등록
@app.route('/test/start')          # 평가 시작
@app.route('/test/technical')      # 기술 평가
@app.route('/result')              # 결과 페이지

# 관리자 화면
@app.route('/admin')               # 관리자 대시보드
@app.route('/admin/questions')     # 문제 관리
@app.route('/admin/answer/<id>')   # 답안 상세 조회

# API 엔드포인트
@app.route('/api/check_name')      # 실시간 이름 검증
@app.route('/api/submit_answers')  # 답안 제출
@app.route('/api/candidate/<id>/generate_questions')  # AI 질문 생성
```

### 2. `models.py` - 데이터 모델 및 관리자
**위치**: `aptitude_system/models.py`  
**역할**: 데이터 모델 정의 및 데이터 관리 기능

#### 주요 클래스
```python
class DataManager:
    """데이터 관리 클래스"""
    - load_candidates()      # 지원자 데이터 로드
    - save_candidates()      # 지원자 데이터 저장
    - load_questions()       # 문제 데이터 로드
    - save_questions()       # 문제 데이터 저장
    - load_results()         # 결과 데이터 로드
    - save_results()         # 결과 데이터 저장
    - load_departments()     # 부서 데이터 로드
    - save_departments()     # 부서 데이터 저장

class Candidate:
    """지원자 모델"""
    - id, name, email, phone
    - created_at, access_date
    - test_duration, department_id
    - selected_questions

class Question:
    """문제 모델"""
    - id, category, type, difficulty
    - question, options, correct_answer
    - keywords, points, department_ids

class TestResult:
    """평가 결과 모델"""
    - candidate_id, test_date
    - answers, scores, total_score, rank
```

### 3. `check_time.py` - 시간 체크 유틸리티
**위치**: `aptitude_system/check_time.py`  
**역할**: 시간 관련 유틸리티 함수

#### 주요 기능
```python
def is_valid_access_date(access_date):
    """접속 가능 날짜 체크"""
    
def format_time_remaining(seconds):
    """남은 시간 포맷팅"""
    
def get_current_time():
    """현재 시간 조회"""
```

### 4. `create_sample_logo.py` - 샘플 로고 생성
**위치**: `aptitude_system/create_sample_logo.py`  
**역할**: 샘플 로고 이미지 생성 스크립트

#### 주요 기능
```python
def create_sample_logo():
    """SVG 형식의 샘플 로고 생성"""
    
def save_logo_with_timestamp():
    """타임스탬프가 포함된 로고 파일 저장"""
```

### 5. `config.json` - 설정 파일
**위치**: `aptitude_system/config.json`  
**역할**: 애플리케이션 설정 정보

#### 주요 설정
```json
{
  "OPENAI_API_KEY": "your-api-key-here",
  "DEFAULT_TEST_DURATION": 10,
  "DEFAULT_DEPARTMENT": "dept_1",
  "MAX_QUESTIONS_PER_CATEGORY": 10
}
```

---

## 📁 데이터 디렉토리 (`data/`)

### 1. `candidates.json` - 지원자 데이터
**위치**: `aptitude_system/data/candidates.json`  
**역할**: 등록된 지원자 정보 저장

```json
[
  {
    "id": "candidate_001",
    "name": "홍길동",
    "email": "hong@example.com",
    "phone": "010-1234-5678",
    "created_at": "2024-12-19 10:00:00",
    "access_date": "2024-12-20",
    "test_duration": 10,
    "department_id": "dept_1",
    "selected_questions": ["q001", "q002", "q003"]
  }
]
```

### 2. `questions.json` - 문제 데이터
**위치**: `aptitude_system/data/questions.json`  
**역할**: 평가 문제 정보 저장

```json
[
  {
    "id": "q001",
    "category": "Java",
    "type": "객관식",
    "difficulty": "초급",
    "question": "Java에서 상속을 나타내는 키워드는?",
    "options": ["extends", "implements", "inherits", "super"],
    "correct_answer": "extends",
    "points": 5,
    "department_ids": ["dept_1", "dept_2"]
  }
]
```

### 3. `results.json` - 평가 결과 데이터
**위치**: `aptitude_system/data/results.json`  
**역할**: 평가 결과 및 답안 저장

```json
[
  {
    "candidate_id": "candidate_001",
    "test_date": "2024-12-19 14:30:00",
    "answers": {
      "q001": "extends",
      "q002": "데이터베이스 정규화는...",
      "q003": "A"
    },
    "scores": {
      "technical": 85,
      "problem_solving": 90
    },
    "total_score": 175,
    "rank": 1
  }
]
```

### 4. `departments.json` - 부서 데이터
**위치**: `aptitude_system/data/departments.json`  
**역할**: 부서 정보 및 문제 할당 관리

```json
[
  {
    "id": "dept_1",
    "name": "개발팀",
    "description": "소프트웨어 개발 담당",
    "question_ids": ["q001", "q002", "q003"]
  }
]
```

### 5. `random_config.json` - 랜덤 출제 설정
**위치**: `aptitude_system/data/random_config.json`  
**역할**: 카테고리별 랜덤 출제 개수 설정

```json
{
  "java_mc_count": 2,
  "java_sub_count": 1,
  "db_mc_count": 3,
  "db_sub_count": 1,
  "ps_mc_count": 2
}
```

---

## 🎨 정적 파일 디렉토리 (`static/`)

### 1. CSS 파일
**위치**: `aptitude_system/static/css/`  
**역할**: 스타일시트 파일

- **Bootstrap**: 기본 UI 프레임워크
- **FontAwesome**: 아이콘 라이브러리
- **Custom CSS**: 프로젝트별 커스텀 스타일

### 2. JavaScript 파일
**위치**: `aptitude_system/static/js/`  
**역할**: 클라이언트 사이드 스크립트

#### 주요 기능
- **실시간 이름 검증**: AJAX를 통한 실시간 검증
- **타이머 기능**: 평가 시간 관리
- **동적 폼 제어**: 조건부 필드 활성화
- **모달 관리**: 팝업 창 제어
- **데이터 필터링**: 부서별 문제 필터링

### 3. 이미지 파일
**위치**: `aptitude_system/static/images/`  
**역할**: 로고 및 이미지 파일

- **로고 파일**: 회사 로고 및 브랜드 이미지
- **UI 이미지**: 인터페이스 요소 이미지
- **샘플 이미지**: 개발용 샘플 이미지

---

## 📄 템플릿 디렉토리 (`templates/`)

### 1. `base.html` - 기본 레이아웃
**위치**: `aptitude_system/templates/base.html`  
**역할**: 모든 페이지의 기본 HTML 구조

#### 주요 구성
- **메타 태그**: SEO 및 뷰포트 설정
- **CSS/JS 로드**: Bootstrap, FontAwesome, 커스텀 스타일
- **네비게이션**: 공통 네비게이션 바
- **푸터**: 공통 푸터 정보
- **블록 영역**: {% block content %} 템플릿 상속

### 2. 사용자 화면 템플릿

#### `index.html` - 메인 페이지
**역할**: 시스템 소개 및 시작 페이지
- **시스템 소개**: 주요 기능 및 특징 설명
- **시작 버튼**: 지원자 등록 페이지로 이동
- **관리자 링크**: 관리자 페이지 접근

#### `register.html` - 지원자 등록
**역할**: 지원자 정보 입력 및 검증
- **실시간 검증**: 이름 입력 시 즉시 검증
- **동적 폼**: 유효한 이름 입력 시 다른 필드 활성화
- **접속 제한**: 날짜 및 시간 설정

#### `test_start.html` - 평가 시작
**역할**: 평가 안내 및 시작
- **평가 안내**: 규칙 및 주의사항
- **시간 설정**: 타이머 초기화
- **문제 로드**: 선택된 문제 정보 표시

#### `technical_test.html` - 기술 평가
**역할**: 실제 문제 풀이 화면
- **타이머**: 실시간 남은 시간 표시
- **문제 표시**: 객관식/주관식 문제 렌더링
- **답안 입력**: 다양한 입력 방식 지원
- **자동 제출**: 시간 종료 시 자동 제출

#### `result.html` - 결과 페이지
**역할**: 평가 결과 및 순위 표시
- **점수 표시**: 카테고리별 및 총점
- **순위 정보**: 전체 지원자 중 순위
- **답안 확인**: 개별 문제 답안 확인
- **통계 정보**: 평균점수, 분포 등

### 3. 관리자 화면 템플릿

#### `admin.html` - 관리자 대시보드
**역할**: 관리자 메인 화면
- **통계 대시보드**: 지원자 수, 평가 현황
- **지원자 관리**: 등록, 수정, 삭제
- **부서 관리**: 부서 추가/삭제
- **랜덤 설정**: 출제 개수 설정
- **AI 설정**: OpenAI API Key 설정

#### `admin_answer_detail.html` - 답안 상세 조회
**역할**: 개별 지원자 답안 상세 조회
- **지원자 정보**: 기본 정보 표시
- **답안 상세**: 문제별 답안 및 정답 비교
- **점수 분석**: 카테고리별 점수 분석
- **통계 정보**: 전체 대비 성적 분석

#### `question_manage.html` - 문제 관리
**역할**: 문제 목록 및 기본 관리
- **문제 목록**: 모든 문제 표시
- **검색/필터**: 카테고리, 유형별 필터링
- **CRUD 작업**: 생성, 수정, 삭제
- **부서 할당**: 문제별 부서 할당 관리

#### `question_edit.html` - 문제 편집
**역할**: 개별 문제 편집 화면
- **문제 정보**: 제목, 내용, 카테고리
- **선택지 관리**: 객관식 선택지 추가/삭제
- **정답 설정**: 정답 및 키워드 설정
- **배점 설정**: 문제별 배점 설정

#### `candidate_question_match.html` - 지원자-문제 매칭
**역할**: 지원자별 문제 할당
- **지원자 목록**: 등록된 지원자 표시
- **문제 할당**: 개별 문제 선택/해제
- **부서 필터**: 부서별 문제 필터링
- **AI 질문 생성**: 맞춤형 면접 질문 생성

---

## 📦 의존성 파일

### 1. `requirements.txt` - Python 의존성
**위치**: `aptitude_system/requirements.txt`  
**역할**: 필요한 Python 패키지 목록

```
Flask==2.3.3
openai==0.28.1
python-dotenv==1.0.0
Werkzeug==2.3.7
```

### 2. 루트 `requirements.txt`
**위치**: `assessmentSystem/requirements.txt`  
**역할**: 프로젝트 전체 의존성 관리

---

## 🔧 설정 및 환경 파일

### 1. 환경 변수 설정
**위치**: `.env` (생성 필요)  
**역할**: 환경별 설정 관리

```env
FLASK_ENV=development
FLASK_DEBUG=True
OPENAI_API_KEY=your-api-key-here
SECRET_KEY=your-secret-key-here
```

### 2. 로그 설정
**위치**: `logs/` (생성 필요)  
**역할**: 애플리케이션 로그 저장

---

## 📊 파일 크기 및 복잡도 분석

### Python 파일별 라인 수
- `app.py`: ~800 라인 (메인 애플리케이션)
- `models.py`: ~300 라인 (데이터 모델)
- `check_time.py`: ~50 라인 (유틸리티)
- `create_sample_logo.py`: ~30 라인 (스크립트)

### 템플릿 파일별 복잡도
- `base.html`: 높음 (기본 레이아웃)
- `admin.html`: 높음 (관리자 대시보드)
- `technical_test.html`: 중간 (평가 화면)
- `candidate_question_match.html`: 중간 (매칭 화면)

### 데이터 파일별 크기
- `questions.json`: ~50KB (문제 데이터)
- `candidates.json`: ~10KB (지원자 데이터)
- `results.json`: ~20KB (결과 데이터)
- `departments.json`: ~5KB (부서 데이터)

---

## 🚀 배포 및 실행 구조

### 개발 환경
```
python app.py
```

### 프로덕션 환경
```
gunicorn app:app
```

### Docker 환경 (선택사항)
```
docker build -t assessment-system .
docker run -p 5000:5000 assessment-system
```

---

## 📈 확장성 고려사항

### 현재 구조의 장점
- **모듈화**: 기능별 파일 분리
- **확장성**: 새로운 기능 추가 용이
- **유지보수성**: 명확한 파일 구조
- **테스트 용이성**: 단위 테스트 작성 가능

### 개선 가능 영역
- **데이터베이스**: JSON → PostgreSQL 마이그레이션
- **캐싱**: Redis 도입
- **로깅**: 구조화된 로깅 시스템
- **테스트**: 단위/통합 테스트 추가

---

**소스코드 디렉토리 구조** - 프로젝트의 모든 소스코드 파일과 디렉토리의 상세한 설명 