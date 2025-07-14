import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os

# BASE_DIR: models.py가 아닌 app.py 기준의 절대경로를 사용
try:
    from app import BASE_DIR
except ImportError:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Candidate:
    """지원자 정보를 관리하는 클래스"""
    
    def __init__(self, name: str, email: str = '', phone: str = '', created_at: str = None, access_date: str = None, test_duration: int = 10, selected_questions: List[str] = None, department_id: str = None):
        self.id = str(uuid.uuid4())  # 고유 ID 생성
        self.name = name
        self.email = email or ''
        self.phone = phone or ''
        self.created_at = created_at or datetime.now().isoformat()
        self.access_date = access_date  # YYYY-MM-DD
        self.test_duration = test_duration  # 분 단위, 기본 10분
        self.selected_questions = selected_questions or []  # 출제할 문제 ID 목록
        self.department_id = department_id # 부서 ID 추가
    
    def to_dict(self) -> Dict:
        """지원자 정보를 딕셔너리로 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "created_at": self.created_at,
            "access_date": self.access_date,
            "test_duration": self.test_duration,
            "selected_questions": self.selected_questions,
            "department_id": self.department_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Candidate':
        """딕셔너리에서 지원자 객체 생성"""
        candidate = cls(
            data["name"],
            data.get("email", ""),
            data.get("phone", ""),
            data.get("created_at"),
            data.get("access_date"),
            data.get("test_duration", 10),
            data.get("selected_questions", []),
            data.get("department_id")
        )
        # id 필드를 명시적으로 설정 (JSON에서 로드할 때 필요)
        candidate.id = data["id"]
        return candidate

class Department:
    """부서 정보를 관리하는 클래스"""
    def __init__(self, name: str):
        self.id = "dept_" + str(uuid.uuid4())
        self.name = name

    def to_dict(self) -> Dict:
        return {"id": self.id, "name": self.name}

    @classmethod
    def from_dict(cls, data: Dict) -> 'Department':
        dept = cls(data["name"])
        dept.id = data["id"]
        return dept

class Question:
    """문제 정보를 관리하는 클래스"""
    
    def __init__(self, id, category, type, difficulty, question, options=None, correct_answer=None, keywords=None, points=1, department_ids=None):
        self.id = id
        self.category = category
        self.type = type
        self.difficulty = difficulty
        self.question = question
        self.options = options or []
        self.correct_answer = correct_answer
        self.keywords = keywords or []
        self.points = points
        # department_ids가 None이거나 단일 문자열이면 리스트로 변환
        if department_ids is None:
            self.department_ids = []
        elif isinstance(department_ids, str):
            self.department_ids = [department_ids]
        else:
            self.department_ids = list(department_ids)
    
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

    def to_dict(self) -> Dict:
        """문제 정보를 딕셔너리로 변환"""
        data = {
            "id": self.id,
            "category": self.category,
            "type": self.type,
            "difficulty": self.difficulty,
            "question": self.question,
            "points": self.points,
            "department_ids": self.department_ids,
        }
        if self.type == "객관식":
            data["options"] = self.options
            data["correct_answer"] = self.correct_answer
        elif self.type == "주관식":
            data["keywords"] = self.keywords
            data["correct_answer"] = self.correct_answer
        return data

    @staticmethod
    def from_dict(q):
        # dict에서 Question 객체 생성 (department_ids 보정)
        return Question(
            id=q.get('id'),
            category=q.get('category'),
            type=q.get('type'),
            difficulty=q.get('difficulty'),
            question=q.get('question'),
            options=q.get('options'),
            correct_answer=q.get('correct_answer'),
            keywords=q.get('keywords'),
            points=q.get('points'),
            department_ids=q.get('department_ids')
        )

class TestResult:
    """평가 결과를 관리하는 클래스"""
    
    def __init__(self, candidate_id: str):
        self.candidate_id = candidate_id
        self.test_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.answers = {}  # 문제ID: 답안
        self.scores = {
            "technical": 0,
            "problem_solving": 0  # 문제해결력 점수 추가
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
        # 기존 데이터에 problem_solving 키가 없는 경우 추가
        if "problem_solving" not in result.scores:
            result.scores["problem_solving"] = 0
        result.total_score = data["total_score"]
        result.rank = data["rank"]
        return result

class DataManager:
    """데이터 관리를 담당하는 클래스"""
    
    def __init__(self):
        # 항상 app.py 기준의 절대경로로 data 폴더 지정
        self.data_folder = os.path.join(BASE_DIR, "data")
        self.candidates_file = os.path.join(self.data_folder, "candidates.json")
        self.results_file = os.path.join(self.data_folder, "results.json")
        self.questions_file = os.path.join(self.data_folder, "questions.json")
        self.departments_file = os.path.join(self.data_folder, "departments.json")
        # 디버깅용 경로 출력
        print("[DataManager 경로 확인]")
        print(f"BASE_DIR: {BASE_DIR}")
        print(f"data_folder: {self.data_folder}")
        print(f"candidates_file: {self.candidates_file}")
        print(f"results_file: {self.results_file}")
        print(f"questions_file: {self.questions_file}")
        print(f"departments_file: {self.departments_file}")
        self._ensure_data_files()
    
    def _ensure_data_files(self):
        """데이터 파일들이 존재하는지 확인하고 없으면 생성"""
        os.makedirs(self.data_folder, exist_ok=True)
        if not os.path.exists(self.candidates_file):
            self._save_json(self.candidates_file, [])
        if not os.path.exists(self.questions_file):
            self._save_json(self.questions_file, {"technical_questions": []})
        if not os.path.exists(self.results_file):
            self._save_json(self.results_file, [])
        if not os.path.exists(self.departments_file):
            self._save_json(self.departments_file, {"departments": []})
    
    def _load_json(self, filename: str):
        """JSON 파일 로드"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            if filename == self.departments_file:
                return {"departments": []}
            if filename == self.questions_file:
                return {"technical_questions": []}
            return []
    
    def _save_json(self, filename: str, data):
        """JSON 파일 저장"""
        dir_name = os.path.dirname(filename)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
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
        """모든 결과 정보 조회"""
        results = self._load_json(self.results_file)
        return [TestResult.from_dict(data) for data in results]
    
    def load_questions(self) -> List[Question]:
        """문제 데이터 로드 (기술 문제 + 문제해결 문제)"""
        try:
            with open(self.questions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 기술 문제와 문제해결 문제 모두 로드
            technical_questions_data = data.get("technical_questions", [])
            problem_solving_questions_data = data.get("problem_solving_questions", [])
            
            all_questions_data = technical_questions_data + problem_solving_questions_data
            
            return [Question.from_dict(q) for q in all_questions_data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
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
    
    def update_candidate(self, updated_candidate: Candidate):
        """지원자 정보 수정 (수정된 Candidate 객체를 통째로 받아 처리)"""
        candidates = self._load_json(self.candidates_file)
        # 해당 id를 가진 지원자 데이터를 찾아 교체
        for i, candidate in enumerate(candidates):
            if candidate["id"] == updated_candidate.id:
                candidates[i] = updated_candidate.to_dict()
                break
        self._save_json(self.candidates_file, candidates)
        return updated_candidate
    
    def update_candidate_contact_info(self, candidate_id: str, email: str, phone: str):
        """지원자 연락처 정보 업데이트 (이메일, 핸드폰번호)"""
        candidates = self._load_json(self.candidates_file)
        for candidate in candidates:
            if candidate["id"] == candidate_id:
                candidate["email"] = email
                candidate["phone"] = phone
                break
        self._save_json(self.candidates_file, candidates)
    
    def get_candidate_questions(self, candidate_id: str) -> List[Question]:
        """지원자에게 할당된 문제 목록을 반환"""
        candidate = self.get_candidate(candidate_id)
        if not candidate:
            return []
        
        all_questions = self.load_questions()
        
        # 선택된 문제가 있으면 해당 문제들만 반환
        if candidate.selected_questions:
            selected_questions = []
            for question in all_questions:
                if question.id in candidate.selected_questions:
                    selected_questions.append(question)
            return selected_questions
        
        # 선택된 문제가 없으면 전체 문제 반환
        return all_questions
    
    def set_candidate_questions(self, candidate_id: str, question_ids: List[str]):
        """지원자 출제 문제 설정"""
        candidates = self._load_json(self.candidates_file)
        for candidate in candidates:
            if candidate["id"] == candidate_id:
                candidate["selected_questions"] = question_ids
                break
        self._save_json(self.candidates_file, candidates)
    
    def get_random_questions(self, count: int = 10, category: str = None) -> List[str]:
        """지정된 카테고리 또는 전체에서 랜덤으로 문제 ID 목록 반환"""
        import random
        
        all_questions = self.load_questions()
        
        if category:
            filtered_questions = [q for q in all_questions if q.category == category]
        else:
            filtered_questions = all_questions
            
        if len(filtered_questions) < count:
            count = len(filtered_questions)
            
        return [q.id for q in random.sample(filtered_questions, count)]
    
    def get_questions_by_category(self, category: str) -> List[Question]:
        """카테고리별 문제 조회"""
        all_questions = self.load_questions()
        return [q for q in all_questions if q.category == category]

    # 부서 관리 메서드
    def load_departments(self) -> List[Department]:
        data = self._load_json(self.departments_file)
        return [Department.from_dict(d) for d in data.get("departments", [])]

    def save_department(self, department: Department):
        data = self._load_json(self.departments_file)
        data["departments"].append(department.to_dict())
        self._save_json(self.departments_file, data)

    def delete_department(self, department_id: str):
        data = self._load_json(self.departments_file)
        data["departments"] = [d for d in data["departments"] if d["id"] != department_id]
        self._save_json(self.departments_file, data)
        # 연관된 문제들의 department_ids에서 해당 부서 제거
        questions = self.load_questions()
        for q in questions:
            if department_id in q.department_ids:
                q.department_ids.remove(department_id)
        self.save_all_questions(questions)

    def save_all_questions(self, questions: List[Question]):
        """모든 문제 정보를 파일에 저장 (기술 문제 + 문제해결 문제)"""
        # 기존 데이터 로드
        try:
            with open(self.questions_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = {"technical_questions": [], "problem_solving_questions": []}
        
        # 카테고리별로 분류
        technical_questions = [q.to_dict() for q in questions if q.category in ["Java", "Database"]]
        problem_solving_questions = [q.to_dict() for q in questions if q.category == "문제해결"]
        
        question_data = {
            "technical_questions": technical_questions,
            "problem_solving_questions": problem_solving_questions
        }
        self._save_json(self.questions_file, question_data) 