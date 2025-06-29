import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class Candidate:
    """지원자 정보를 관리하는 클래스"""
    
    def __init__(self, name: str, email: str = '', phone: str = '', created_at: str = None, test_deadline: str = None, access_date: str = None, test_duration: int = 10):
        self.id = str(uuid.uuid4())  # 고유 ID 생성
        self.name = name
        self.email = email or ''
        self.phone = phone or ''
        self.created_at = created_at or datetime.now().isoformat()
        self.test_deadline = test_deadline
        self.access_date = access_date  # YYYY-MM-DD
        self.test_duration = test_duration  # 분 단위, 기본 10분
    
    def to_dict(self) -> Dict:
        """지원자 정보를 딕셔너리로 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at,
            "test_deadline": self.test_deadline,
            "access_date": self.access_date,
            "test_duration": self.test_duration
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Candidate':
        """딕셔너리에서 지원자 객체 생성"""
        candidate = cls(
            data["name"],
            data.get("email", ""),
            data.get("phone", ""),
            data.get("created_at"),
            data.get("test_deadline"),
            data.get("access_date"),
            data.get("test_duration", 10)
        )
        # id 필드를 명시적으로 설정 (JSON에서 로드할 때 필요)
        candidate.id = data["id"]
        return candidate

class Question:
    """문제 정보를 관리하는 클래스"""
    
    def __init__(self, question_data: Dict):
        self.id = question_data["id"]
        self.category = question_data["category"]
        self.type = question_data["type"]
        self.difficulty = question_data["difficulty"]
        self.question = question_data["question"]
        self.options = question_data.get("options", [])
        self.correct_answer = question_data["correct_answer"]
        self.keywords = question_data.get("keywords", [])
        self.points = question_data["points"]
    
    def is_correct(self, answer: str) -> bool:
        """답안이 정답인지 확인"""
        if self.type == "객관식":
            return answer == self.correct_answer
        elif self.type == "주관식":
            # 키워드 매칭 기반 채점
            answer_lower = answer.lower()
            correct_keywords = [kw.lower() for kw in self.keywords]
            matched_keywords = sum(1 for kw in correct_keywords if kw in answer_lower)
            return matched_keywords >= len(correct_keywords) * 0.6  # 60% 이상 매칭 시 정답
        return False

class TestResult:
    """평가 결과를 관리하는 클래스"""
    
    def __init__(self, candidate_id: str):
        self.candidate_id = candidate_id
        self.test_date = datetime.now().isoformat()
        self.answers = {}  # 문제ID: 답안
        self.scores = {
            "technical": 0,
            "problem_solving": 0
        }
        self.total_score = 0
        self.rank = 0
    
    def add_answer(self, question_id: str, answer: str):
        """답안 추가"""
        self.answers[question_id] = answer
    
    def calculate_score(self, questions: List[Question]):
        """점수 계산"""
        technical_score = 0
        problem_solving_score = 0
        
        for question in questions:
            if question.id in self.answers:
                answer = self.answers[question.id]
                if question.is_correct(answer):
                    if question.category in ["Java", "Database"]:
                        technical_score += question.points
                    elif question.category == "문제해결":
                        problem_solving_score += question.points
        
        self.scores["technical"] = technical_score
        self.scores["problem_solving"] = problem_solving_score
        self.total_score = technical_score + problem_solving_score
    
    def to_dict(self) -> Dict:
        """결과를 딕셔너리로 변환"""
        return {
            "candidate_id": self.candidate_id,
            "test_date": self.test_date,
            "answers": self.answers,
            "scores": self.scores,
            "total_score": self.total_score,
            "rank": self.rank
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TestResult':
        """딕셔너리에서 결과 객체 생성"""
        result = cls(data["candidate_id"])
        result.test_date = data["test_date"]
        result.answers = data["answers"]
        result.scores = data["scores"]
        result.total_score = data["total_score"]
        result.rank = data["rank"]
        return result

class DataManager:
    """데이터 관리를 담당하는 클래스"""
    
    def __init__(self):
        self.candidates_file = "data/candidates.json"
        self.results_file = "data/results.json"
        self.questions_file = "data/questions.json"
        self._ensure_data_files()
    
    def _ensure_data_files(self):
        """데이터 파일들이 존재하는지 확인하고 없으면 생성"""
        import os
        
        # data 디렉토리 생성
        os.makedirs("data", exist_ok=True)
        
        # 후보자 파일 초기화
        if not os.path.exists(self.candidates_file):
            self._save_json(self.candidates_file, [])
        
        # 결과 파일 초기화
        if not os.path.exists(self.results_file):
            self._save_json(self.results_file, [])
    
    def _load_json(self, filename: str) -> List[Dict]:
        """JSON 파일 로드"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return []
    
    def _save_json(self, filename: str, data: List[Dict]):
        """JSON 파일 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def save_candidate(self, candidate: Candidate):
        """지원자 정보 저장"""
        candidates = self._load_json(self.candidates_file)
        candidates.append(candidate.to_dict())
        self._save_json(self.candidates_file, candidates)
    
    def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        """지원자 정보 조회"""
        candidates = self._load_json(self.candidates_file)
        for candidate_data in candidates:
            if candidate_data["id"] == candidate_id:
                return Candidate.from_dict(candidate_data)
        return None
    
    def get_all_candidates(self) -> List[Candidate]:
        """모든 지원자 정보 조회"""
        candidates = self._load_json(self.candidates_file)
        return [Candidate.from_dict(data) for data in candidates]
    
    def save_result(self, result: TestResult):
        """평가 결과 저장"""
        results = self._load_json(self.results_file)
        results.append(result.to_dict())
        self._save_json(self.results_file, results)
    
    def get_result(self, candidate_id: str) -> Optional[TestResult]:
        """평가 결과 조회"""
        results = self._load_json(self.results_file)
        for result_data in results:
            if result_data["candidate_id"] == candidate_id:
                return TestResult.from_dict(result_data)
        return None
    
    def get_all_results(self) -> List[TestResult]:
        """모든 평가 결과 조회"""
        results = self._load_json(self.results_file)
        return [TestResult.from_dict(data) for data in results]
    
    def load_questions(self) -> List[Question]:
        """문제 데이터 로드"""
        questions_data = self._load_json(self.questions_file)
        questions = []
        
        # 기술 문제 로드
        for tech_q in questions_data.get("technical_questions", []):
            questions.append(Question(tech_q))
        
        # 문제해결력 문제 로드
        for ps_q in questions_data.get("problem_solving_questions", []):
            questions.append(Question(ps_q))
        
        return questions
    
    def calculate_ranks(self):
        """순위 계산 및 업데이트"""
        results = self.get_all_results()
        
        # 총점 기준으로 정렬
        results.sort(key=lambda x: x.total_score, reverse=True)
        
        # 순위 부여
        for i, result in enumerate(results):
            result.rank = i + 1
        
        # 업데이트된 결과 저장
        updated_results = [result.to_dict() for result in results]
        self._save_json(self.results_file, updated_results)
    
    def delete_candidate(self, candidate_id: str):
        """지원자 삭제"""
        candidates = self._load_json(self.candidates_file)
        candidates = [c for c in candidates if c["id"] != candidate_id]
        self._save_json(self.candidates_file, candidates)
    
    def delete_result(self, candidate_id: str):
        """평가 결과 삭제"""
        results = self._load_json(self.results_file)
        results = [r for r in results if r["candidate_id"] != candidate_id]
        self._save_json(self.results_file, results)
    
    def set_candidate_deadline(self, candidate_id: str, deadline: str):
        """지원자 평가완료시간 설정"""
        candidates = self._load_json(self.candidates_file)
        for candidate in candidates:
            if candidate["id"] == candidate_id:
                candidate["test_deadline"] = deadline
                break
        self._save_json(self.candidates_file, candidates)
    
    def update_candidate(self, candidate_id: str, name: str, access_date: str, test_duration: int):
        """지원자 정보 수정"""
        candidates = self._load_json(self.candidates_file)
        for candidate in candidates:
            if candidate["id"] == candidate_id:
                candidate["name"] = name
                candidate["access_date"] = access_date
                candidate["test_duration"] = test_duration
                break
        self._save_json(self.candidates_file, candidates)
    
    def update_candidate_contact_info(self, candidate_id: str, email: str, phone: str):
        """지원자 연락처 정보 업데이트 (이메일, 핸드폰번호)"""
        candidates = self._load_json(self.candidates_file)
        for candidate in candidates:
            if candidate["id"] == candidate_id:
                candidate["email"] = email
                candidate["phone"] = phone
                break
        self._save_json(self.candidates_file, candidates)
    
    def is_test_deadline_passed(self, candidate_id: str) -> bool:
        """평가완료시간이 지났는지 확인 (일자만 비교)"""
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            return True  # 지원자를 찾을 수 없으면 True 반환 (접근 차단)
        
        # test_deadline이 설정되지 않은 경우 False 반환 (평가 가능)
        if not candidate.test_deadline:
            return False
        
        try:
            # 마감 날짜(YYYY-MM-DD)만 추출
            deadline_date = candidate.test_deadline[:10]
            current_date = datetime.now().strftime('%Y-%m-%d')
            # 현재 날짜가 마감 날짜를 초과했는지 확인
            return current_date > deadline_date
        except (ValueError, TypeError):
            # 날짜 형식이 잘못된 경우 False 반환 (평가 가능)
            return False 