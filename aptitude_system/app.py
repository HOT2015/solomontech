from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from models import Candidate, Question, TestResult, DataManager, Department
import os
from datetime import datetime, timedelta, timezone
import uuid
from werkzeug.utils import secure_filename
import tempfile
import requests
import json

# transformers 라이브러리 조건부 import (선택적 기능)
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("transformers 라이브러리가 설치되지 않았습니다. AI 기능이 비활성화됩니다.")

app = Flask(__name__)
app.secret_key = '인적성평가시스템_시크릿키_2024'  # 세션 관리를 위한 시크릿 키

# 파일 업로드 관련 설정 (현재 사용되지 않지만 향후 확장을 위해 유지)
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

# 관리자 인증 관련 상수
ADMIN_SESSION_KEY = 'admin_authenticated'
ADMIN_SESSION_TIMEOUT = 600 * 600  # 10시간(초)

# 관리자 암호 생성 함수
def get_admin_password():
    today = datetime.now().strftime('%Y%m%d')
    return f"{today}1"

# 관리자 인증 필요 데코레이터
from functools import wraps

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get(ADMIN_SESSION_KEY):
            # 세션 만료 체크
            auth_time_raw = session.get('admin_auth_time')
            auth_time = None
            if isinstance(auth_time_raw, str):
                try:
                    auth_time = datetime.fromisoformat(auth_time_raw)
                except Exception:
                    auth_time = None
            elif isinstance(auth_time_raw, datetime):
                auth_time = auth_time_raw
            now = datetime.now(timezone.utc).astimezone()  # 항상 aware datetime
            if auth_time and (now - auth_time).total_seconds() < ADMIN_SESSION_TIMEOUT:
                return f(*args, **kwargs)
            session.pop(ADMIN_SESSION_KEY, None)
            session.pop('admin_auth_time', None)
        return redirect(url_for('admin_login', next=request.path))
    return decorated_function

# 관리자 암호 입력 페이지
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == get_admin_password():
            session[ADMIN_SESSION_KEY] = True
            session['admin_auth_time'] = datetime.now(timezone.utc).astimezone().isoformat()
            next_url = request.args.get('next') or url_for('admin')
            return redirect(next_url)
        else:
            error = '잘못된 암호입니다.'
    return render_template('admin_login.html', error=error)

# 회사 정보 설정 (이미지 파일과 함께 사용)
app.config['COMPANY_NAME'] = '솔로몬텍 인적성 평가시스템'  # 회사명 (로고 이미지 파일명으로 변경 가능)
app.config['COMPANY_DESCRIPTION'] = '기술 역량과 문제 해결력을 통합적으로 평가하는 온라인 시스템'  # 회사 설명
app.config['COMPANY_LOGO'] = None  # 로고 이미지 파일명 (예: 'logo.png', 'company_logo.jpg' 등)

# BASE_DIR: app.py가 위치한 디렉토리의 절대경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 데이터 매니저 초기화
data_manager = DataManager()

# 랜덤 설정 파일 경로
RANDOM_CONFIG_FILE = os.path.join(BASE_DIR, 'data', 'random_config.json')

# OpenAI API Key 로드 함수
import configparser

def get_openai_api_key():
    # 환경변수 우선, 없으면 config.json에서 로드
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        return api_key
    config_path = os.path.join(BASE_DIR, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('OPENAI_API_KEY')
    return None

def load_random_config():
    """랜덤 출제 개수 설정 로드"""
    # 새로운 카테고리별 기본값 설정 (0개로 초기화)
    default = {
        "java_mc_count": 0,
        "java_sub_count": 0,
        "db_mc_count": 0,
        "db_sub_count": 0,
        "ps_mc_count": 0
    }
    try:
        with open(RANDOM_CONFIG_FILE, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
            print(f"로드된 설정: {loaded_config}")
            return loaded_config
    except Exception as e:
        print(f"설정 파일 로드 실패, 기본값 사용: {e}")
        return default

def save_random_config(config):
    """랜덤 출제 개수 설정 저장"""
    # data 디렉토리가 없으면 생성
    data_dir = os.path.dirname(RANDOM_CONFIG_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    print(f"저장할 설정: {config}")
    with open(RANDOM_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"설정이 {RANDOM_CONFIG_FILE}에 저장되었습니다.")

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

@app.route('/')
def index():
    """메인 페이지 - 지원자 등록 또는 평가 시작"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """지원자 등록 페이지"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        if name and email and phone:
            candidates = data_manager.get_all_candidates()
            matched = None
            for candidate in candidates:
                if candidate.name == name:
                    matched = candidate
                    break
            if not matched:
                return render_template('register.html', error="사전에 등록된 이름이 아닙니다. 관리자에게 문의하세요.")
            today = datetime.now().strftime('%Y-%m-%d')
            if not hasattr(matched, 'access_date') or not matched.access_date:
                return render_template('register.html', error="접속 가능 날짜가 설정되지 않았습니다. 관리자에게 문의하세요.")
            if matched.access_date != today:
                return render_template('register.html', error=f"오늘({today})은 접속 가능 날짜가 아닙니다. (응시 가능일: {matched.access_date})")
            # 부서 미지정 지원자라면 기본 부서 할당
            if not matched.department_id:
                matched.department_id = 'dept_1'
                data_manager.update_candidate(matched)
            # 세션에 지원자 정보 저장
            session['candidate_id'] = matched.id
            session['candidate_name'] = matched.name
            session['candidate_email'] = email
            session['candidate_phone'] = phone
            # 지원자 데이터에 이메일과 핸드폰번호 업데이트
            data_manager.update_candidate_contact_info(matched.id, email, phone)
            return redirect(url_for('test_start'))
        else:
            return render_template('register.html', error="이름, 이메일, 핸드폰번호를 모두 입력해주세요.")
    return render_template('register.html')

@app.route('/test/start')
def test_start():
    """평가 시작 페이지"""
    if 'candidate_id' not in session:
        return redirect(url_for('register'))
    
    candidate = data_manager.get_candidate(session['candidate_id'])
    if not candidate:
        return redirect(url_for('register'))
    
    # 이미 평가를 완료했는지 확인
    existing_result = data_manager.get_result(session['candidate_id'])
    if existing_result:
        return redirect(url_for('result'))
    
    # -------------------------------------------------------------
    # 시험 출제 로직: 부서별 랜덤 문제 자동 할당
    # -------------------------------------------------------------
    # 지원자에게 할당된 문제가 없는 경우에만 새로 할당
    if not candidate.selected_questions:
        all_questions = data_manager.load_questions()
        department_questions = [q for q in all_questions if candidate.department_id in q.department_ids]
        
        # 카테고리별 문제 분류
        java_mc = [q for q in department_questions if q.category == 'Java' and q.type == '객관식']
        java_sub = [q for q in department_questions if q.category == 'Java' and q.type == '주관식']
        db_mc = [q for q in department_questions if q.category == 'Database' and q.type == '객관식']
        db_sub = [q for q in department_questions if q.category == 'Database' and q.type == '주관식']
        ps_mc = [q for q in department_questions if q.category == '문제해결' and q.type == '객관식']
        
        # 출제 개수 설정값 적용 (기본값 0으로 설정)
        random_config = load_random_config()
        java_mc_count = random_config.get('java_mc_count', 0)
        java_sub_count = random_config.get('java_sub_count', 0)
        db_mc_count = random_config.get('db_mc_count', 0)
        db_sub_count = random_config.get('db_sub_count', 0)
        ps_mc_count = random_config.get('ps_mc_count', 0)
        
        import random
        selected_java_mc = random.sample(java_mc, min(len(java_mc), java_mc_count))
        selected_java_sub = random.sample(java_sub, min(len(java_sub), java_sub_count))
        selected_db_mc = random.sample(db_mc, min(len(db_mc), db_mc_count))
        selected_db_sub = random.sample(db_sub, min(len(db_sub), db_sub_count))
        selected_ps_mc = random.sample(ps_mc, min(len(ps_mc), ps_mc_count))
        
        selected_ids = ([q.id for q in selected_java_mc] + [q.id for q in selected_java_sub] + 
                       [q.id for q in selected_db_mc] + [q.id for q in selected_db_sub] + 
                       [q.id for q in selected_ps_mc])
        candidate.selected_questions = selected_ids
        data_manager.update_candidate(candidate)

    # 평가 시간 및 기타 정보 설정
    session['test_duration'] = candidate.test_duration
    session.pop('technical_answers', None)
    
    # 모든 문제는 technical_test에서 처리
    return redirect(url_for('technical_test'))

@app.route('/test/technical')
def technical_test():
    """기술 평가 페이지"""
    if 'candidate_id' not in session:
        return redirect(url_for('register'))
    
    # 지원자 정보 가져오기
    candidate = data_manager.get_candidate(session['candidate_id'])
    if not candidate:
        return redirect(url_for('register'))
    
    # 선택된 문제 또는 전체 문제를 가져옴
    questions = data_manager.get_candidate_questions(session['candidate_id'])
    
    return render_template('technical_test.html', questions=questions, time_limit=candidate.test_duration * 60, candidate=candidate)

@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    """답안 제출 및 채점 (1단계 기술평가만 존재)"""
    if 'candidate_id' not in session:
        return jsonify({'error': '세션이 만료되었습니다.'}), 400
    candidate_id = session['candidate_id']
    # 답안 수집
    answers = {}
    for key, value in request.form.items():
        if key.startswith('question_'):
            question_id = key.replace('question_', '')
            answers[question_id] = value
    # 평가 결과 생성
    result = TestResult(candidate_id)
    for question_id, answer in answers.items():
        result.add_answer(question_id, answer)
    # 모든 문제 로드하여 점수 계산
    all_questions = data_manager.load_questions()
    result.calculate_score(all_questions)
    # 결과 저장
    data_manager.save_result(result)
    # 순위 계산
    data_manager.calculate_ranks()
    # 세션 정리
    session.pop('technical_answers', None)
    session.pop('current_step', None)
    return redirect(url_for('result'))

@app.route('/result')
def result():
    """평가 결과 페이지"""
    if 'candidate_id' not in session:
        return redirect(url_for('register'))
    
    candidate_id = session['candidate_id']
    candidate = data_manager.get_candidate(candidate_id)
    result = data_manager.get_result(candidate_id)
    
    if not candidate or not result:
        return redirect(url_for('register'))
    
    # 전체 결과에서 순위 정보 업데이트
    all_results = data_manager.get_all_results()
    all_results.sort(key=lambda x: x.total_score, reverse=True)
    
    for i, r in enumerate(all_results):
        if r.candidate_id == candidate_id:
            result.rank = i + 1
            break
    
    return render_template('result.html', candidate=candidate, result=result)

@app.route('/admin')
@admin_login_required
def admin():
    """관리자 페이지 - 대시보드"""
    candidates = data_manager.get_all_candidates()
    results = data_manager.get_all_results()
    departments = data_manager.load_departments()
    departments_dict = [dept.to_dict() for dept in departments]
    
    # 모든 문제 로드 (기술 문제 + 문제해결 문제)
    all_questions = []
    
    # 기술 문제 로드
    technical_questions = data_manager.load_questions()
    for q in technical_questions:
        all_questions.append(q.to_dict())
    
    # 문제해결 문제 로드
    questions_data = data_manager._load_json(data_manager.questions_file)
    problem_solving_questions = questions_data.get("problem_solving_questions", [])
    for q in problem_solving_questions:
        all_questions.append(q)
    
    unassigned_questions = [q for q in all_questions if not q.get('department_ids') or len(q.get('department_ids', [])) == 0]
    
    for c in candidates:
        if c.created_at:
            try:
                c.created_at_formatted = datetime.fromisoformat(c.created_at).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                c.created_at_formatted = "N/A"
        else:
            c.created_at_formatted = "N/A"
    total_candidates = len(candidates)
    candidate_results = {}
    for result in results:
        candidate = data_manager.get_candidate(result.candidate_id)
        if candidate:
            candidate_results[result.candidate_id] = {
                'candidate': candidate,
                'result': result
            }
    # candidates를 dict 리스트로 변환
    candidates_dict = [c.to_dict() for c in candidates]
    # created_at_formatted도 dict에 추가
    for i, c in enumerate(candidates):
        candidates_dict[i]['created_at_formatted'] = c.created_at_formatted
    return render_template('admin.html', candidates=candidates_dict, candidate_results=candidate_results, departments=departments_dict, unassigned_questions=unassigned_questions, questions=all_questions)

@app.route('/admin/candidate/delete/<candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    """지원자 삭제"""
    data_manager.delete_candidate(candidate_id)
    data_manager.delete_result(candidate_id)
    return jsonify(success=True, message="지원자가 삭제되었습니다.")

@app.route('/admin/questions')
def question_manage():
    """문제 관리 페이지"""
    technical_questions = data_manager.load_questions()
    # 문제해결 문제도 로드
    questions_data = data_manager._load_json(data_manager.questions_file)
    problem_solving_questions = questions_data.get("problem_solving_questions", [])
    departments = data_manager.load_departments()
    
    # 부서별 문제 통계 계산
    department_stats = {}
    unassigned_count = 0
    
    # 기술 문제 통계 계산
    for question in technical_questions:
        department_ids = getattr(question, 'department_ids', [])
        if not department_ids:
            unassigned_count += 1
        else:
            for dept_id in department_ids:
                if dept_id not in department_stats:
                    department_stats[dept_id] = 0
                department_stats[dept_id] += 1
    
    # 문제해결 문제 통계 계산 (문제해결 문제는 딕셔너리 형태)
    for question in problem_solving_questions:
        department_ids = question.get('department_ids', [])
        if not department_ids:
            unassigned_count += 1
        else:
            for dept_id in department_ids:
                if dept_id not in department_stats:
                    department_stats[dept_id] = 0
                department_stats[dept_id] += 1
    
    # 부서 이름과 함께 통계 정보 생성
    department_info = []
    for dept in departments:
        count = department_stats.get(dept.id, 0)
        department_info.append({
            'id': dept.id,
            'name': dept.name,
            'count': count
        })
    
    return render_template('question_manage.html', 
                         technical_questions=technical_questions, 
                         problem_solving_questions=problem_solving_questions,
                         departments=departments,
                         department_info=department_info,
                         unassigned_count=unassigned_count)

@app.route('/admin/questions/add', methods=['POST'])
def add_question():
    try:
        data = request.get_json()
        
        # 카테고리별로 다른 처리
        if data['category'] in ['Java', 'Database']:
            # 기술 문제 처리
            questions_data = data_manager._load_json(data_manager.questions_file)
            existing_questions = questions_data["technical_questions"]
            new_id = f"tech_{len(existing_questions) + 1}"
            question_data = {
                'id': new_id,
                'category': data['category'],
                'type': data['type'],
                'difficulty': data['difficulty'],
                'question': data['question'],
                'points': int(data['points']),
                # 부서 ID를 리스트로 저장 (없으면 빈 리스트)
                'department_ids': [data.get('department_id', 'dept_1')] if data.get('department_id') else []
            }
            if data['type'] == '객관식':
                question_data['options'] = data['options']
                question_data['correct_answer'] = data['correct_answer']
            else:
                question_data['keywords'] = data['keywords']
                question_data['correct_answer'] = data['correct_answer']
            
            questions_data["technical_questions"].append(question_data)
            data_manager._save_json(data_manager.questions_file, questions_data)
            
        elif data['category'] == '문제해결':
            # 문제해결 문제 처리
            questions_data = data_manager._load_json(data_manager.questions_file)
            # problem_solving_questions 키가 없으면 생성
            if "problem_solving_questions" not in questions_data:
                questions_data["problem_solving_questions"] = []
            
            existing_questions = questions_data["problem_solving_questions"]
            new_id = f"ps_{len(existing_questions) + 1}"
            question_data = {
                'id': new_id,
                'category': data['category'],
                'type': data['type'],
                'difficulty': data['difficulty'],
                'question': data['question'],
                'points': int(data['points']),
                # 부서 ID를 리스트로 저장 (없으면 빈 리스트)
                'department_ids': [data.get('department_id', 'dept_1')] if data.get('department_id') else []
            }
            if data['type'] == '객관식':
                question_data['options'] = data['options']
                question_data['correct_answer'] = data['correct_answer']
            else:
                question_data['keywords'] = data['keywords']
                question_data['correct_answer'] = data['correct_answer']
            
            questions_data["problem_solving_questions"].append(question_data)
            data_manager._save_json(data_manager.questions_file, questions_data)
            
        else:
            return jsonify({'success': False, 'message': '지원하지 않는 카테고리입니다. Java, Database, 문제해결 중 선택해주세요.'})
        
        return jsonify({'success': True, 'message': '문제가 추가되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions/edit/<question_id>', methods=['PUT'])
def edit_question(question_id):
    try:
        data = request.get_json()
        questions_data = data_manager._load_json(data_manager.questions_file)
        
        # 기술 문제에서 찾기
        for question in questions_data["technical_questions"]:
            if question['id'] == question_id:
                question.update({
                    'category': data['category'],
                    'type': data['type'],
                    'difficulty': data['difficulty'],
                    'question': data['question'],
                    'points': int(data['points']),
                    # 부서 ID를 리스트로 저장 (없으면 빈 리스트)
                    'department_ids': [data.get('department_id', 'dept_1')] if data.get('department_id') else []
                })
                if data['type'] == '객관식':
                    question['options'] = data['options']
                    question['correct_answer'] = data['correct_answer']
                else:
                    question['keywords'] = data['keywords']
                    question['correct_answer'] = data['correct_answer']
                data_manager._save_json(data_manager.questions_file, questions_data)
                return jsonify({'success': True, 'message': '문제가 수정되었습니다.'})
        
        # 문제해결 문제에서 찾기
        problem_solving_questions = questions_data.get("problem_solving_questions", [])
        for question in problem_solving_questions:
            if question['id'] == question_id:
                question.update({
                    'category': data['category'],
                    'type': data['type'],
                    'difficulty': data['difficulty'],
                    'question': data['question'],
                    'points': int(data['points']),
                    # 부서 ID를 리스트로 저장 (없으면 빈 리스트)
                    'department_ids': [data.get('department_id', 'dept_1')] if data.get('department_id') else []
                })
                if data['type'] == '객관식':
                    question['options'] = data['options']
                    question['correct_answer'] = data['correct_answer']
                else:
                    question['keywords'] = data['keywords']
                    question['correct_answer'] = data['correct_answer']
                data_manager._save_json(data_manager.questions_file, questions_data)
                return jsonify({'success': True, 'message': '문제가 수정되었습니다.'})
        
        return jsonify({'success': False, 'message': '문제를 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions/delete/<question_id>', methods=['DELETE'])
def delete_question(question_id):
    try:
        questions_data = data_manager._load_json(data_manager.questions_file)
        
        # 기술 문제에서 찾기
        for i, question in enumerate(questions_data["technical_questions"]):
            if question['id'] == question_id:
                del questions_data["technical_questions"][i]
                data_manager._save_json(data_manager.questions_file, questions_data)
                return jsonify({'success': True, 'message': '문제가 삭제되었습니다.'})
        
        # 문제해결 문제에서 찾기
        problem_solving_questions = questions_data.get("problem_solving_questions", [])
        for i, question in enumerate(problem_solving_questions):
            if question['id'] == question_id:
                del questions_data["problem_solving_questions"][i]
                data_manager._save_json(data_manager.questions_file, questions_data)
                return jsonify({'success': True, 'message': '문제가 삭제되었습니다.'})
        
        return jsonify({'success': False, 'message': '문제를 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions/edit/<question_id>', methods=['GET'])
def edit_question_page(question_id):
    """문제 편집 페이지"""
    questions_data = data_manager._load_json(data_manager.questions_file)
    
    # 기술 문제에서 찾기
    for question in questions_data["technical_questions"]:
        if question['id'] == question_id:
            return render_template('question_edit.html', question=question)
    
    # 문제해결 문제에서 찾기
    problem_solving_questions = questions_data.get("problem_solving_questions", [])
    for question in problem_solving_questions:
        if question['id'] == question_id:
            return render_template('question_edit.html', question=question)
    
    return redirect(url_for('question_manage'))

@app.route('/logout')
def logout():
    """로그아웃 - 세션 클리어"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/questions')
def api_questions():
    """문제 데이터 API"""
    all_questions = []
    
    # 기술 문제 로드
    technical_questions = data_manager.load_questions()
    for q in technical_questions:
        all_questions.append({
            'id': q.id,
            'category': q.category,
            'type': q.type,
            'difficulty': q.difficulty,
            'question': q.question,
            'options': q.options,
            'correct_answer': q.correct_answer,
            'keywords': q.keywords,
            'points': q.points,
            # department_ids를 항상 문자열 배열로 변환
            'department_ids': [str(did) for did in getattr(q, 'department_ids', [])]
        })
    
    # 문제해결 문제 로드
    questions_data = data_manager._load_json(data_manager.questions_file)
    problem_solving_questions = questions_data.get("problem_solving_questions", [])
    for q in problem_solving_questions:
        all_questions.append({
            'id': q['id'],
            'category': q['category'],
            'type': q['type'],
            'difficulty': q['difficulty'],
            'question': q['question'],
            'options': q.get('options', []),
            'correct_answer': q['correct_answer'],
            'keywords': q.get('keywords', []),
            'points': q['points'],
            # department_ids를 항상 문자열 배열로 변환
            'department_ids': [str(did) for did in q.get('department_ids', [])]
        })
    
    return jsonify(all_questions)

@app.route('/api/departments')
def api_departments():
    """부서 목록 API"""
    departments = data_manager.load_departments()
    return jsonify([{'id': dept.id, 'name': dept.name} for dept in departments])

@app.route('/api/candidates')
def api_candidates():
    """지원자 목록 API"""
    candidates = data_manager.get_all_candidates()
    return jsonify([c.to_dict() for c in candidates])

@app.route('/api/results')
def api_results():
    """평가 결과 목록 API"""
    results = data_manager.get_all_results()
    return jsonify([r.to_dict() for r in results])

@app.route('/api/random_questions', methods=['GET'])
def api_random_questions_get():
    """카테고리별로 랜덤 문제를 가져오는 API"""
    category = request.args.get('category')
    count = request.args.get('count', default=5, type=int)

    # 'Java', 'Database' 카테고리가 아니면 전체에서 랜덤 선택
    if category not in ['Java', 'Database']:
        category = None

    question_ids = data_manager.get_random_questions(count=count, category=category)
    questions = data_manager.load_questions()
    
    # ID에 해당하는 문제 객체를 찾아 반환
    selected_questions = [q for q in questions if q.id in question_ids]
    
    return jsonify([q.to_dict() for q in selected_questions])

@app.route('/api/candidate/<candidate_id>/questions')
def api_candidate_questions(candidate_id):
    """지원자별 선택된 문제 조회 API"""
    try:
        candidate = data_manager.get_candidate(candidate_id)
        if not candidate:
            return jsonify({
                'success': False,
                'message': '지원자를 찾을 수 없습니다.'
            }), 404
        
        selected_questions = getattr(candidate, 'selected_questions', [])
        
        return jsonify({
            'success': True,
            'selected_questions': selected_questions,
            'total_count': len(selected_questions)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'지원자 문제 조회 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/admin/answer/<candidate_id>')
def admin_answer_detail(candidate_id):
    """관리자용 지원자 답안 상세 페이지"""
    candidate = data_manager.get_candidate(candidate_id)
    result = data_manager.get_result(candidate_id)
    if not candidate or not result:
        return redirect(url_for('admin'))
    
    # 모든 문제 로드 (기술 + 문제해결)
    all_questions = data_manager.load_questions()
    
    # 지원자에게 출제된 문제가 있으면 해당 문제만, 없으면 모든 문제 사용
    selected_ids = getattr(candidate, 'selected_questions', [])
    if selected_ids:
        selected_questions = [q for q in all_questions if q.id in selected_ids]
    else:
        # 선택된 문제가 없으면 모든 문제 사용
        selected_questions = all_questions
    
    # 답변 매핑 - 출제된 문제에 대해서만 처리
    answers = []
    for question in selected_questions:
        answer = result.answers.get(question.id, '')
        if answer:
            answers.append({
                'question': question,
                'answer': answer,
                'is_correct': question.is_correct(answer),
                'answered': True
            })
        else:
            answers.append({
                'question': question,
                'answer': '',
                'is_correct': False,
                'answered': False
            })
    
    return render_template('admin_answer_detail.html', candidate=candidate, result=result, answers=answers)

@app.route('/admin/candidate/add', methods=['POST'])
def add_candidate():
    """관리자가 지원자 사전 등록"""
    data = request.get_json()
    name = data.get('name')
    access_date = data.get('access_date')
    test_duration = data.get('test_duration', 10)
    
    if not name or not access_date:
        return jsonify(success=False, message="이름과 접속 가능 날짜를 모두 입력해야 합니다.")
    
    # Candidate 생성 시 'test_deadline' 인자 없음
    candidate = Candidate(name=name, access_date=access_date, test_duration=int(test_duration))
    data_manager.save_candidate(candidate)
    
    return jsonify(success=True, message="지원자가 등록되었습니다.", candidate=candidate.to_dict())

@app.route('/api/check_name', methods=['POST'])
def check_name():
    """이름 검증 API - 사전 등록된 이름인지 확인"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'valid': False, 'message': '이름을 입력해주세요.'})
        
        # 모든 지원자 목록에서 이름 확인
        candidates = data_manager.get_all_candidates()
        matched_candidate = None
        
        for candidate in candidates:
            if candidate.name == name:
                matched_candidate = candidate
                break
        
        if matched_candidate:
            # 접속 가능 날짜 확인
            today = datetime.now().strftime('%Y-%m-%d')
            if not matched_candidate.access_date:
                return jsonify({
                    'valid': False, 
                    'message': '접속 가능 날짜가 설정되지 않았습니다. 관리자에게 문의하세요.'
                })
            
            if matched_candidate.access_date != today:
                return jsonify({
                    'valid': False, 
                    'message': f'오늘({today})은 접속 가능 날짜가 아닙니다. (응시 가능일: {matched_candidate.access_date})'
                })
            
            return jsonify({
                'valid': True, 
                'message': '사전 등록된 이름입니다. 다음 정보를 입력해주세요.',
                'access_date': matched_candidate.access_date
            })
        else:
            return jsonify({
                'valid': False, 
                'message': '사전에 등록된 이름이 아닙니다. 관리자에게 문의하세요.'
            })
            
    except Exception as e:
        return jsonify({'valid': False, 'message': f'검증 중 오류가 발생했습니다: {str(e)}'})

@app.route('/admin/candidate/edit/<candidate_id>', methods=['PUT'])
def edit_candidate(candidate_id):
    """지원자 정보 수정"""
    data = request.get_json() if request.is_json else request.form
    name = data.get('name')
    access_date = data.get('access_date')
    test_duration = data.get('test_duration')
    department_id = data.get('department_id')

    if not name or not access_date or not test_duration or not department_id:
        return jsonify(success=False, message="모든 필드를 입력해야 합니다.")
    try:
        # 기존 지원자 정보 불러오기
        candidate = data_manager.get_candidate(candidate_id)
        if not candidate:
            return jsonify(success=False, message="지원자를 찾을 수 없습니다.")
        # 입력값으로 갱신
        candidate.name = name
        candidate.access_date = access_date
        candidate.test_duration = int(test_duration)
        candidate.department_id = department_id
        # 저장
        updated_candidate = data_manager.update_candidate(candidate)
        return jsonify(success=True, message="지원자 정보가 수정되었습니다.", candidate=updated_candidate.to_dict())
    except (ValueError, TypeError):
        return jsonify(success=False, message="잘못된 데이터 형식입니다.")

# ===============================================
# 지원자-문제 매칭 페이지 라우트
# ===============================================
@app.route('/admin/match')
def candidate_question_match():
    """지원자와 문제를 수동으로 매칭하는 페이지"""
    all_candidates = data_manager.get_all_candidates()
    all_questions = data_manager.load_questions()
    all_departments = data_manager.load_departments()
    all_results = data_manager.get_all_results()
    
    # 평가완료된 지원자 ID 목록 생성
    completed_candidate_ids = {result.candidate_id for result in all_results}
    
    # 평가 미완료 지원자만 필터링
    incomplete_candidates = [c for c in all_candidates if c.id not in completed_candidate_ids]
    
    # 부서 이름을 id에 매핑시켜두면 템플릿에서 사용하기 편리함
    department_map = {d.id: d.name for d in all_departments}

    return render_template('candidate_question_match.html',
                           candidates=incomplete_candidates,
                           questions=[q.to_dict() for q in all_questions],
                           departments=all_departments,
                           department_map=department_map)

@app.route('/api/candidate/<candidate_id>/questions/update', methods=['POST'])
def update_candidate_questions(candidate_id):
    """API: 특정 지원자에게 할당된 문제 목록을 업데이트"""
    data = request.get_json()
    question_ids = data.get('question_ids', [])
    
    candidate = data_manager.get_candidate(candidate_id)
    if not candidate:
        return jsonify(success=False, message="지원자를 찾을 수 없습니다."), 404
        
    candidate.selected_questions = question_ids
    data_manager.update_candidate(candidate)
    
    return jsonify(success=True, message="문제가 성공적으로 할당되었습니다.")

@app.route('/admin/departments/add', methods=['POST'])
def add_department():
    """새 부서 추가 API (문제 할당 포함)"""
    data = request.get_json() if request.is_json else request.form
    name = data.get('name', '').strip()
    assign_questions = data.getlist('assign_questions') if not request.is_json else data.get('assign_questions', [])
    if not name:
        return jsonify(success=False, message="부서명을 입력해주세요."), 400
    departments = data_manager.load_departments()
    if any(d.name == name for d in departments):
        return jsonify(success=False, message="이미 존재하는 부서명입니다."), 409
    department = Department(name)
    data_manager.save_department(department)
    # 선택된 문제들 부서 할당
    if assign_questions:
        questions = data_manager.load_questions()
        for q in questions:
            if q.id in assign_questions:
                if department.id not in q.department_ids:
                    q.department_ids.append(department.id)
        data_manager.save_all_questions(questions)
    return jsonify(success=True, message="부서가 추가되었습니다.", department=department.to_dict())

@app.route('/admin/departments/assign_questions', methods=['POST'])
def assign_questions_to_department():
    """특정 부서에 문제를 할당/해제하는 API (여러 부서 할당 가능)"""
    data = request.get_json() if request.is_json else request.form
    department_id = data.get('department_id')
    question_ids = data.get('question_ids', [])
    filter_conditions = data.get('filter_conditions', {})  # 필터 조건 추가
    
    if not department_id:
        return jsonify(success=False, message="부서를 선택해야 합니다."), 400
    
    # question_ids가 문자열인 경우 리스트로 변환
    if isinstance(question_ids, str):
        question_ids = [question_ids]
    
    questions = data_manager.load_questions()
    
    # 필터 조건에 맞는 문제들만 처리
    filtered_questions = []
    for q in questions:
        # 부서 필터 로직
        dept_match = True
        if filter_conditions.get('department') == 'unassigned':
            # 미지정 필터: 미지정 문제만
            dept_match = (not q.department_ids or len(q.department_ids) == 0)
        elif filter_conditions.get('department') == 'current':
            # 현재 부서 필터: 해당 부서 문제만
            dept_match = (q.department_ids and department_id in q.department_ids)
        elif filter_conditions.get('department') and filter_conditions.get('department') not in ['all', 'current', 'unassigned']:
            # 특정 부서 필터: 해당 부서 문제만
            dept_match = (q.department_ids and filter_conditions.get('department') in q.department_ids)
        
        # 카테고리 필터
        category_match = not filter_conditions.get('category') or q.category == filter_conditions.get('category')
        
        # 유형 필터
        type_match = not filter_conditions.get('type') or q.type == filter_conditions.get('type')
        
        if dept_match and category_match and type_match:
            filtered_questions.append(q)
    
    # 디버깅 로그
    print(f"부서 ID: {department_id}")
    print(f"선택된 문제 수: {len(question_ids)}")
    print(f"필터 조건: {filter_conditions}")
    print(f"필터링된 문제 수: {len(filtered_questions)}")
    print(f"필터링된 문제 ID들: {[q.id for q in filtered_questions]}")
    
    # 필터링된 문제들만 처리
    for q in filtered_questions:
        # 현재 부서에 할당할 문제들
        if q.id in question_ids:
            # 해당 부서가 이미 할당되어 있지 않으면 추가
            if department_id not in q.department_ids:
                q.department_ids.append(department_id)
                print(f"문제 {q.id}를 부서 {department_id}에 할당")
        # 현재 부서에서 해제할 문제들 (question_ids에 없는 문제들)
        elif department_id in q.department_ids and q.id not in question_ids:
            # 해당 부서에서 제거
            q.department_ids.remove(department_id)
            print(f"문제 {q.id}를 부서 {department_id}에서 해제")
    
    data_manager.save_all_questions(questions)
    return jsonify(success=True, message="문제 할당이 성공적으로 업데이트되었습니다.")

@app.route('/admin/departments/delete/<department_id>', methods=['DELETE'])
def delete_department_route(department_id):
    """부서 삭제 API"""
    try:
        data_manager.delete_department(department_id)
        return jsonify(success=True, message="부서가 삭제되었습니다.")
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500

@app.route('/admin/questions/unassign/<question_id>', methods=['PUT'])
def unassign_question_department(question_id):
    """문제의 부서 할당만 해제하는 API"""
    try:
        questions = data_manager.load_questions()
        found = False
        for q in questions:
            if q.id == question_id:
                q.department_ids = []
                found = True
                break
        if found:
            data_manager.save_all_questions(questions)
            return jsonify({'success': True, 'message': '문제의 부서 할당이 해제되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '문제를 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})



@app.route('/api/random_config', methods=['GET'])
def get_random_config():
    config = load_random_config()
    print(f"API 호출 - 반환할 설정: {config}")  # 디버깅 로그
    response = jsonify(config)
    # 완전한 캐시 방지 헤더 추가
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    response.headers['ETag'] = str(hash(str(config)))  # 고유 ETag 추가
    return response

@app.route('/api/random_config', methods=['POST'])
def set_random_config():
    try:
        data = request.get_json()
        if not data:
            return jsonify(success=False, message="데이터가 전송되지 않았습니다."), 400
        
        # 새로운 카테고리별 설정값 가져오기 (기본값 0, 안전한 변환)
        java_mc_count = safe_int(data.get('java_mc_count'))
        java_sub_count = safe_int(data.get('java_sub_count'))
        db_mc_count = safe_int(data.get('db_mc_count'))
        db_sub_count = safe_int(data.get('db_sub_count'))
        ps_mc_count = safe_int(data.get('ps_mc_count'))
        
        # 디버깅 로그 추가
        print(f"받은 데이터: {data}")
        print(f"변환된 값들: java_mc={java_mc_count}, java_sub={java_sub_count}, db_mc={db_mc_count}, db_sub={db_sub_count}, ps_mc={ps_mc_count}")
        
        # 유효성 검사 (0도 가능하도록 수정)
        if (java_mc_count < 0 or java_sub_count < 0 or db_mc_count < 0 or 
            db_sub_count < 0 or ps_mc_count < 0):
            return jsonify(success=False, message="출제 개수는 0 이상이어야 합니다."), 400
        
        config = {
            "java_mc_count": java_mc_count,
            "java_sub_count": java_sub_count,
            "db_mc_count": db_mc_count,
            "db_sub_count": db_sub_count,
            "ps_mc_count": ps_mc_count
        }
        save_random_config(config)
        return jsonify(success=True, config=config, message="랜덤 출제 설정이 저장되었습니다.")
    except ValueError as e:
        return jsonify(success=False, message="잘못된 숫자 형식입니다."), 400
    except Exception as e:
        return jsonify(success=False, message=f"저장 중 오류가 발생했습니다: {str(e)}"), 500

# 로컬 LLM 파이프라인(최초 1회만 로드) - 조건부 처리
local_llm = None

def get_local_llm():
    global local_llm
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("transformers 라이브러리가 설치되지 않았습니다.")
    if local_llm is None:
        # 한글 특화 모델, 최초 실행 시 다운로드(수 분 소요)
        local_llm = pipeline("text-generation", model="beomi/KoAlpaca-Polyglot-5.8B", device_map="auto")
    return local_llm

def generate_questions_with_local_llm(prompt):
    if not TRANSFORMERS_AVAILABLE:
        return "AI 기능을 사용하려면 transformers 라이브러리를 설치해주세요."
    try:
        llm = get_local_llm()
        # max_new_tokens, temperature 등은 필요에 따라 조정
        result = llm(prompt, max_new_tokens=256, do_sample=True, temperature=0.7)
        # 결과에서 질문 부분만 추출
        return result[0]['generated_text']
    except Exception as e:
        return f"AI 질문 생성 중 오류가 발생했습니다: {str(e)}"

@app.route('/api/candidate/<candidate_id>/generate_questions', methods=['POST'])
def generate_candidate_questions(candidate_id):
    """
    지원자 정보를 바탕으로 AI(로컬 LLM 또는 OpenAI 등)로 맞춤형 면접 질문을 생성하는 엔드포인트
    """
    # config.json에서 AI_PROVIDER 확인
    config_path = os.path.join(BASE_DIR, 'config.json')
    provider = 'openai'
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                config = json.load(f)
                provider = config.get('AI_PROVIDER', 'openai')
            except Exception:
                provider = 'openai'
    candidate = data_manager.get_candidate(candidate_id)
    if not candidate:
        return jsonify({'success': False, 'message': '지원자 정보를 찾을 수 없습니다.'}), 404
    # 지원자 정보 요약 (이름, 경력, 자기소개 등)
    resume_text = f"이름: {candidate.name}\n"
    if hasattr(candidate, 'experience'):
        resume_text += f"경력: {candidate.experience}\n"
    if hasattr(candidate, 'self_intro'):
        resume_text += f"자기소개: {candidate.self_intro}\n"
    prompt = f"다음 지원자 정보를 참고해서 면접관이 활용할 수 있는 맞춤형 면접 질문 3~5개를 한글로 생성해줘.\n{resume_text}"
    try:
        if provider == 'local':
            questions = generate_questions_with_local_llm(prompt)
            return jsonify({'success': True, 'questions': questions})
        else:
            # 기존 OpenAI 연동 코드(백업)
            api_key = get_openai_api_key()
            if not api_key:
                return jsonify({'success': False, 'message': 'OpenAI API Key가 설정되어 있지 않습니다.'}), 400
            import openai
            openai.api_key = api_key
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            questions = response['choices'][0]['message']['content']
            return jsonify({'success': True, 'questions': questions})
    except Exception as e:
        return jsonify({'success': False, 'message': f'질문 생성 실패: {str(e)}'}), 500

@app.route('/admin/openai_key', methods=['POST'])
def set_openai_api_key():
    """
    관리자 화면에서 OpenAI API Key를 저장하는 엔드포인트
    """
    data = request.get_json()
    api_key = data.get('openai_api_key')
    if not api_key:
        return jsonify({'success': False, 'message': 'API Key가 비어 있습니다.'}), 400
    config_path = os.path.join(BASE_DIR, 'config.json')
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                config = json.load(f)
            except Exception:
                config = {}
    config['OPENAI_API_KEY'] = api_key
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': f'저장 실패: {str(e)}'}), 500

# 기존 문제 데이터 마이그레이션 스크립트 (단발성 실행)
def migrate_questions_department_ids():
    """
    기존 questions.json 파일에서 department_id(단수)를 department_ids(복수, 리스트)로 변환
    """
    import os
    questions_file = os.path.join(BASE_DIR, 'data', 'questions.json')
    if not os.path.exists(questions_file):
        print('questions.json 파일이 존재하지 않습니다.')
        return
    with open(questions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    changed = False
    for section in ['technical_questions', 'problem_solving_questions']:
        if section in data:
            for q in data[section]:
                if 'department_id' in q:
                    dept_id = q['department_id']
                    if dept_id:
                        q['department_ids'] = [dept_id]
                    else:
                        q['department_ids'] = []
                    del q['department_id']
                    changed = True
                elif 'department_ids' not in q:
                    q['department_ids'] = []
                    changed = True
    if changed:
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print('questions.json 파일이 마이그레이션되었습니다.')
    else:
        print('변경사항 없음. 이미 최신 구조입니다.')

@app.route('/api/ping')
def api_ping():
    """
    클라이언트에서 서버 연결 유지를 위해 주기적으로 호출하는 핑 엔드포인트
    """
    return 'pong', 200

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    migrate_questions_department_ids()  # 서버 실행 전 1회 마이그레이션
    app.run(host="0.0.0.0", port=port, debug=True)  # 디버그 모드 활성화 