# 인적성 평가 시스템 - 요건정의서 v2.2

## 1. 프로젝트 개요

### 1.1 프로젝트명
온라인 인적성 평가 시스템

### 1.2 프로젝트 목적
- 지원자의 기술 역량과 문제 해결력을 통합적으로 평가
- 온라인 환경에서 효율적이고 공정한 평가 진행
- 평가 결과의 체계적 관리 및 분석

### 1.3 주요 기능
- 지원자 등록 및 관리
- 기술 문제 평가 (Java, Database)
- 문제해결력 평가
- 실시간 채점 및 결과 분석
- 관리자 기능 (문제 관리, 결과 조회)
- 엑셀/워드 파일 업로드를 통한 문제 일괄 등록
- 회사 로고/정보 관리
- 카테고리별 문제 선택 및 랜덤 문제 생성
- 지원자 정보 수정 시 문제 재설정

## 2. 시스템 요구사항

### 2.1 기술 스택
- **Backend**: Python Flask
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Database**: JSON 파일 기반 (SQLite 대체)
- **File Processing**: Excel(.xlsx), Word(.docx) 파일 업로드 지원

### 2.2 필수 패키지
```
Flask==2.3.3
Flask-SQLAlchemy==3.0.5
Werkzeug==2.3.7
Jinja2==3.1.2
openpyxl==3.1.2
python-docx==0.8.11
pandas==2.0.3
requests==2.31.0
```

## 3. 기능 요구사항

### 3.1 지원자 기능

#### 3.1.1 지원자 등록
- **기능**: 이름, 이메일, 핸드폰번호 입력
- **검증**: 사전 등록된 이름과 일치 여부 확인
- **접속 제한**: 지정된 날짜에만 접속 가능

#### 3.1.2 평가 진행
- **평가 유형**: 기술 문제 + 문제해결력 문제
- **시간 제한**: 설정된 시간 내 완료
- **문제 유형**: 객관식, 주관식 지원
- **실시간 저장**: 답안 자동 저장

#### 3.1.3 결과 확인
- **채점 결과**: 즉시 확인 가능
- **점수 분석**: 기술/문제해결력 영역별 점수
- **순위 정보**: 전체 지원자 중 순위

### 3.2 관리자 기능

#### 3.2.1 지원자 관리
- **지원자 등록**: 이름, 접속 가능 날짜, 평가 완료일 설정
- **지원자 수정**: 기존 지원자 정보 변경 및 문제 재설정
- **지원자 삭제**: 지원자 정보 및 결과 삭제
- **연락처 관리**: 이메일, 핸드폰번호 업데이트

#### 3.2.2 문제 관리
- **문제 추가**: 수동 입력 또는 파일 업로드
- **문제 수정**: 기존 문제 내용 변경
- **문제 삭제**: 불필요한 문제 제거
- **문제 분류**: 카테고리, 유형, 난이도별 관리
- **카테고리별 문제 선택 및 랜덤 문제 생성**

#### 3.2.3 파일 업로드 기능
- **Excel 파일**: .xlsx 형식 지원
- **Word 파일**: .docx 형식 지원
- **자동 파싱**: 파일 내용을 문제 데이터로 변환
- **중복 처리**: 기존 문제와 중복 시 처리 옵션

#### 3.2.4 결과 관리
- **결과 조회**: 전체 지원자 평가 결과
- **상세 분석**: 개별 지원자 답안 및 채점 결과
- **순위 계산**: 총점 기준 자동 순위 부여

#### 3.2.5 시스템 설정
- **회사 정보**: 회사명, 설명, 로고 설정
- **평가 설정**: 기본 평가 시간, 문제 배점 등

## 4. 데이터 모델

### 4.1 지원자 (Candidate)
```json
{
  "id": "고유 ID",
  "name": "지원자명",
  "email": "이메일",
  "phone": "핸드폰번호",
  "created_at": "등록일시",
  "access_date": "접속 가능 날짜",
  "test_deadline": "평가 완료일",
  "test_duration": "평가 시간(분)",
  "selected_questions": ["선택된 문제 ID 목록"]
}
```

### 4.2 문제 (Question)
```json
{
  "id": "문제 ID",
  "category": "카테고리 (Java/Database/문제해결)",
  "type": "유형 (객관식/주관식)",
  "difficulty": "난이도 (초급/중급)",
  "question": "문제 내용",
  "options": ["선택지1", "선택지2", "선택지3", "선택지4"],
  "correct_answer": "정답",
  "keywords": ["키워드1", "키워드2", "키워드3"],
  "points": "배점"
}
```

### 4.3 평가 결과 (TestResult)
```json
{
  "candidate_id": "지원자 ID",
  "test_date": "평가 일시",
  "answers": {"문제ID": "답안"},
  "scores": {
    "technical": "기술 점수",
    "problem_solving": "문제해결력 점수"
  },
  "total_score": "총점",
  "rank": "순위"
}
```

## 5. API 엔드포인트

### 5.1 지원자 관련
- `GET /` - 메인 페이지
- `GET /register` - 지원자 등록 페이지
- `POST /register` - 지원자 등록 처리
- `GET /test/start` - 평가 시작 페이지
- `GET /test/technical` - 기술 문제 평가
- `GET /test/problem_solving` - 문제해결력 평가
- `POST /submit_answers` - 답안 제출
- `GET /result` - 결과 확인

### 5.2 관리자 관련
- `GET /admin` - 관리자 메인 페이지
- `POST /admin/candidate/add` - 지원자 추가
- `PUT /admin/candidate/edit/<id>` - 지원자 수정
- `DELETE /admin/candidate/delete/<id>` - 지원자 삭제
- `PUT /admin/candidate/deadline/<id>` - 평가 완료일 설정
- `GET /admin/questions` - 문제 관리 페이지
- `POST /admin/questions/add` - 문제 추가
- `PUT /admin/questions/edit/<id>` - 문제 수정
- `DELETE /admin/questions/delete/<id>` - 문제 삭제
- `POST /admin/questions/upload` - 파일 업로드
- `GET /admin/answer/<id>` - 답안 상세 조회

### 5.3 API 엔드포인트
- `GET /api/questions` - 문제 목록
- `GET /api/candidates` - 지원자 목록
- `GET /api/results` - 결과 목록
- `POST /api/check_name` - 이름 중복 확인

## 6. 파일 업로드 형식

### 6.1 Excel 파일 (.xlsx)
첫 번째 시트에 다음 순서로 데이터 입력:
1. 카테고리
2. 유형
3. 난이도
4. 문제
5. 배점
6. 선택지1 (객관식)
7. 선택지2 (객관식)
8. 선택지3 (객관식)
9. 선택지4 (객관식)
10. 정답

### 6.2 Word 파일 (.docx)
각 문제를 다음 형식으로 작성:
```
카테고리|유형|난이도|문제내용
문제 상세 내용
1. 선택지1
2. 선택지2
3. 선택지3
4. 선택지4
정답: 정답내용
```

## 7. 설치 및 실행

### 7.1 환경 설정
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 7.2 실행
```bash
python app.py
```

### 7.3 접속
- 웹 브라우저에서 `http://localhost:5000` 접속
- 관리자 페이지: `http://localhost:5000/admin`

## 8. 보안 및 제약사항

### 8.1 보안
- 세션 기반 인증
- 파일 업로드 크기 제한 (10MB)
- 허용된 파일 형식만 업로드 가능

### 8.2 제약사항
- 동시 접속자 수 제한 없음
- 데이터베이스는 JSON 파일 기반
- 외부 API 의존성 없음

## 9. 향후 개선사항

### 9.1 기능 개선
- 문제 랜덤 출제 기능
- 평가 시간 타이머 기능
- 결과 통계 및 차트 기능
- 이메일 알림 기능

### 9.2 기술 개선
- 데이터베이스 마이그레이션 (SQLite/PostgreSQL)
- RESTful API 표준화
- 프론트엔드 프레임워크 도입 (React/Vue.js)
- Docker 컨테이너화

---

**버전**: 2.2  
**최종 수정일**: 2024년 12월  
**작성자**: 개발팀 