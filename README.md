# 인적성 평가시스템

## 📋 프로젝트 개요

**통합 온라인 인적성 평가시스템**은 기술 역량과 문제 해결력을 통합적으로 평가하는 온라인 시스템입니다. 지원자 등록부터 평가, 채점, 결과 분석까지 전체 프로세스를 자동화하여 효율적인 인재 선발을 지원합니다.

### 🎯 주요 특징

- **통합 평가 시스템**: 기술 지식 + 문제 해결력 통합 평가
- **자동화된 프로세스**: 등록부터 결과까지 전 과정 자동화
- **부서별 맞춤 평가**: 부서별 문제 할당 및 관리
- **AI 기반 면접 지원**: 맞춤형 면접 질문 자동 생성
- **실시간 검증**: 지원자 등록 시 실시간 이름 검증
- **유연한 출제 설정**: 카테고리별 랜덤 출제 개수 설정 (0개 가능)

## 🏗️ 시스템 아키텍처

### 기술 스택
- **Backend**: Python (Flask)
- **Frontend**: HTML, CSS, JavaScript (Bootstrap, FontAwesome)
- **Database**: JSON 파일 기반
- **AI Integration**: OpenAI GPT API

### 프로젝트 구조
```
인적성평가시스템/
├── app.py                          # 메인 Flask 애플리케이션
├── models.py                       # 데이터 모델 및 관리자
├── templates/                      # HTML 템플릿
│   ├── base.html                   # 기본 레이아웃
│   ├── index.html                  # 메인 페이지
│   ├── register.html               # 지원자 등록
│   ├── test_start.html             # 평가 시작
│   ├── technical_test.html         # 기술 평가
│   ├── result.html                 # 결과 페이지
│   ├── admin.html                  # 관리자 대시보드
│   ├── admin_answer_detail.html    # 답안 상세 조회
│   ├── question_manage.html        # 문제 관리
│   ├── question_edit.html          # 문제 편집
│   └── candidate_question_match.html # 지원자-문제 매칭
├── data/                           # JSON 데이터 파일
│   ├── candidates.json             # 지원자 데이터
│   ├── questions.json              # 문제 데이터
│   ├── results.json                # 평가 결과
│   ├── departments.json            # 부서 데이터
│   └── random_config.json          # 랜덤 출제 설정
├── static/                         # 정적 파일 (CSS, JS, 이미지)
├── requirements.txt                # Python 의존성
└── README.md                       # 프로젝트 문서
```

## 🚀 주요 기능

### 1. 지원자 관리
- **사전 등록 시스템**: 관리자가 지원자 이름을 사전 등록
- **실시간 검증**: 이름 입력 시 즉시 사전 등록 여부 확인
- **접속 제한**: 지원자별 접속 가능 날짜 설정
- **부서 자동 할당**: 기본 부서(dept_1) 자동 할당

### 2. 평가 시스템
- **통합 평가**: 기술 지식 + 문제 해결력 통합 평가
- **타이머 기능**: 설정된 시간 내 문제 풀이
- **자동 채점**: 객관식/주관식 자동 채점
- **결과 분석**: 점수 계산 및 순위 산정

### 3. 문제 관리
- **카테고리별 관리**: Java, Database, 문제해결
- **유형별 분류**: 객관식/주관식 문제
- **난이도 설정**: 초급/중급 난이도
- **부서별 할당**: 부서별 문제 할당 및 공유

### 4. 랜덤 출제 시스템
- **카테고리별 설정**: Java, Database, 문제해결 각각 설정
- **유연한 개수 조정**: 0개부터 원하는 개수까지 설정 가능
- **부서별 적용**: 부서별로 다른 출제 설정 가능

### 5. AI 기반 면접 지원
- **맞춤형 질문 생성**: 지원자 정보 기반 면접 질문 자동 생성
- **OpenAI 연동**: GPT API를 활용한 질문 생성
- **API Key 관리**: 관리자 화면에서 API Key 설정

### 6. 관리자 기능
- **대시보드**: 지원자 통계, 평가 현황, 점수 분포
- **부서 관리**: 부서 추가/삭제, 문제 할당
- **결과 분석**: 개별 답안 상세 조회, 통계 분석

## 🤖 AI 활용 내역

### 1. AI 기반 면접 질문 생성

#### 구현 방식
- **API 연동**: OpenAI GPT-3.5/4 API 활용
- **프롬프트 엔지니어링**: 지원자 정보를 바탕으로 맞춤형 질문 생성
- **결과 활용**: 생성된 질문을 면접관이 복사/활용

#### 기술적 세부사항
```python
# OpenAI API 연동
def generate_candidate_questions(candidate_id):
    candidate = data_manager.get_candidate(candidate_id)
    resume_text = f"이름: {candidate.name}\n"
    # 지원자 정보 수집
    
    prompt = f"다음 지원자 정보를 참고해서 면접관이 활용할 수 있는 맞춤형 면접 질문 3~5개를 한글로 생성해줘.\n{resume_text}"
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response['choices'][0]['message']['content']
```

#### 사용 시나리오
1. 관리자가 지원자-문제 매칭 화면에서 지원자 선택
2. "AI 맞춤질문 생성" 버튼 클릭
3. OpenAI API 호출하여 지원자 정보 기반 질문 생성
4. 생성된 질문을 면접관이 복사하여 활용

### 2. AI 활용의 장점

#### 효율성 향상
- **시간 절약**: 면접 질문 준비 시간 단축
- **일관성**: 모든 지원자에게 동일한 기준의 질문 생성
- **맞춤성**: 지원자별 특성에 맞는 질문 생성

#### 품질 향상
- **다양성**: AI가 다양한 관점의 질문 생성
- **적절성**: 지원자 수준에 맞는 질문 난이도 조절
- **완성도**: 문법적으로 완성된 질문 생성

### 3. 향후 AI 활용 계획

#### 단기 계획 (1-3개월)
- **채점 알고리즘 개선**: 주관식 답안 AI 채점 정확도 향상
- **문제 난이도 자동 평가**: AI를 활용한 문제 난이도 자동 측정
- **답안 분석**: 지원자 답안 패턴 분석 및 인사이트 제공

#### 중기 계획 (3-6개월)
- **면접 시뮬레이션**: AI 기반 가상 면접관 기능
- **성과 예측**: 지원자 평가 결과 기반 업무 성과 예측
- **개인화된 피드백**: AI가 생성하는 맞춤형 피드백 제공

#### 장기 계획 (6개월 이상)
- **다국어 지원**: AI 번역을 활용한 다국어 평가 시스템
- **음성 인식**: 음성 기반 면접 질문 및 답변 처리
- **감정 분석**: 면접 과정에서의 지원자 감정 상태 분석

## 📊 데이터 모델

### 지원자 (Candidate)
```json
{
  "id": "고유ID",
  "name": "이름",
  "email": "이메일",
  "phone": "핸드폰번호",
  "created_at": "등록일시",
  "access_date": "접속 가능 날짜",
  "test_duration": "문제풀이 시간(분)",
  "department_id": "부서 ID",
  "selected_questions": ["선택된 문제 ID 목록"]
}
```

### 문제 (Question)
```json
{
  "id": "문제ID",
  "category": "카테고리(Java/Database/문제해결)",
  "type": "유형(객관식/주관식)",
  "difficulty": "난이도(초급/중급)",
  "question": "문제내용",
  "options": ["선택지"],
  "correct_answer": "정답",
  "keywords": ["키워드 (주관식용)"],
  "points": "배점",
  "department_ids": ["할당된 부서 ID 목록"]
}
```

### 평가 결과 (TestResult)
```json
{
  "candidate_id": "지원자ID",
  "test_date": "평가일시",
  "answers": {"문제ID": "답안"},
  "scores": {
    "technical": "기술점수",
    "problem_solving": "문제해결점수"
  },
  "total_score": "총점",
  "rank": "순위"
}
```

## 🛠️ 설치 및 실행

### 1. 환경 요구사항
- Python 3.7 이상
- pip (Python 패키지 관리자)

### 2. 설치 과정
```bash
# 1. 프로젝트 클론
git clone [repository-url]
cd assessmentSystem/인적성평가시스템

# 2. 의존성 설치
pip install -r requirements.txt

# 3. OpenAI API Key 설정 (선택사항)
# config.json 파일에 API Key 추가
{
  "OPENAI_API_KEY": "your-api-key-here"
}
```

### 3. 실행
```bash
python app.py
```

### 4. 접속
- **메인 페이지**: http://localhost:5000
- **관리자 페이지**: http://localhost:5000/admin
- **문제 관리**: http://localhost:5000/admin/questions

## 📱 주요 화면

### 사용자 화면
- **메인 페이지**: 시스템 소개 및 시작
- **지원자 등록**: 이름, 이메일, 핸드폰번호 입력
- **평가 시작**: 평가 안내 및 시작
- **기술 평가**: 문제 풀이 및 타이머
- **결과 페이지**: 평가 결과 및 순위

### 관리자 화면
- **관리자 대시보드**: 통계 및 현황
- **지원자 관리**: 등록, 수정, 삭제
- **문제 관리**: 생성, 수정, 삭제
- **부서 관리**: 부서 추가/삭제, 문제 할당
- **결과 분석**: 개별 답안 조회, 통계 분석

## 🔧 API 엔드포인트

### 지원자 관리
- `GET /` - 메인 페이지
- `POST /register` - 지원자 등록
- `POST /api/check_name` - 실시간 이름 검증
- `GET /test/start` - 평가 시작
- `GET /test/technical` - 기술 평가
- `POST /submit_answers` - 답안 제출

### 관리자 기능
- `GET /admin` - 관리자 대시보드
- `POST /admin/candidate/add` - 지원자 추가
- `PUT /admin/candidate/edit/<id>` - 지원자 정보 수정
- `DELETE /admin/candidate/delete/<id>` - 지원자 삭제
- `GET /admin/answer/<id>` - 답안 상세 조회

### AI 기능
- `POST /api/candidate/<id>/generate_questions` - AI 맞춤질문 생성
- `POST /admin/openai_key` - OpenAI API Key 설정

## 📈 성능 지표

### 정량적 지표
- 평가 완료율: 80% 이상
- 시스템 안정성: 95% 이상
- 실시간 검증 응답률: 99% 이상
- AI 질문 생성 성공률: 90% 이상

### 정성적 지표
- 사용자 친화적 인터페이스
- 실시간 피드백 제공
- 안정적인 데이터 처리
- 확장 가능한 코드 구조

## 🔮 향후 발전 방향

### 기술적 개선
- **마이크로서비스 아키텍처**: 모듈화 및 확장성 향상
- **데이터베이스 마이그레이션**: JSON → PostgreSQL/REDIS
- **실시간 통신**: WebSocket을 활용한 실시간 업데이트
- **모바일 앱**: React Native 기반 모바일 애플리케이션

### AI 기능 확장
- **다중 AI 모델 지원**: OpenAI 외 Claude, Gemini 등
- **로컬 AI 모델**: 오프라인 환경에서도 AI 기능 사용
- **AI 채점 고도화**: 주관식 답안 정확도 향상
- **감정 분석**: 면접 과정에서의 지원자 상태 분석

### 비즈니스 확장
- **다국어 지원**: 글로벌 기업 대상 서비스
- **SaaS 플랫폼**: 클라우드 기반 서비스 제공
- **API 서비스**: 외부 시스템 연동 API 제공
- **데이터 분석**: 빅데이터 기반 인사이트 제공

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 👥 기여자

- **개발팀**: 시스템 설계 및 구현
- **AI 팀**: AI 기능 개발 및 최적화
- **QA 팀**: 테스트 및 품질 보증

## 📞 문의

프로젝트 관련 문의사항이 있으시면 이슈를 생성해 주시기 바랍니다.

---

**인적성 평가시스템** - 효율적이고 정확한 인재 선발을 위한 AI 기반 평가 플랫폼 