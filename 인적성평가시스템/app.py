from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from models import Candidate, Question, TestResult, DataManager, Department
import os
from datetime import datetime, timedelta
import uuid
import pandas as pd
from docx import Document
from werkzeug.utils import secure_filename
import tempfile
import requests
import json
import openai
from transformers import pipeline

app = Flask(__name__)
app.secret_key = '인적성평가시스템_시크릿키_2024'  # 세션 관리를 위한 시크릿 키

# 회사 정보 설정 (이미지 파일과 함께 사용)
app.config['COMPANY_NAME'] = '인적성 평가시스템'  # 회사명 (로고 이미지 파일명으로 변경 가능)
app.config['COMPANY_DESCRIPTION'] = '기술 역량과 문제 해결력을 통합적으로 평가하는 온라인 시스템'  # 회사 설명
app.config['COMPANY_LOGO'] = None  # 로고 이미지 파일명 (예: 'logo.png', 'company_logo.jpg' 등)

# BASE_DIR: app.py가 위치한 디렉토리의 절대경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 데이터 매니저 초기화
data_manager = DataManager()

# 파일 업로드 관련 설정
ALLOWED_EXTENSIONS = {'xlsx', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

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
    default = {"java_count": 10, "db_count": 3}
    try:
        with open(RANDOM_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_random_config(config):
    """랜덤 출제 개수 설정 저장"""
    with open(RANDOM_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        department_id = request.form.get('department_id')
        if not department_id:
            departments = data_manager.load_departments()
            return render_template('register.html', error='부서를 반드시 선택해야 합니다.', departments=departments)
        if name and email and phone:
            candidates = data_manager.get_all_candidates()
            matched = None
            for candidate in candidates:
                if candidate.name == name:
                    matched = candidate
                    break
            if not matched:
                departments = data_manager.load_departments()
                return render_template('register.html', error="사전에 등록된 이름이 아닙니다. 관리자에게 문의하세요.", departments=departments)
            today = datetime.now().strftime('%Y-%m-%d')
            if not hasattr(matched, 'access_date') or not matched.access_date:
                departments = data_manager.load_departments()
                return render_template('register.html', error="접속 가능 날짜가 설정되지 않았습니다. 관리자에게 문의하세요.", departments=departments)
            if matched.access_date != today:
                departments = data_manager.load_departments()
                return render_template('register.html', error=f"오늘({today})은 접속 가능 날짜가 아닙니다. (응시 가능일: {matched.access_date})", departments=departments)
            # 부서 미지정 지원자라면 기본 부서 할당
            if not matched.department_id:
                matched.department_id = department_id or 'dept_1'
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
            departments = data_manager.load_departments()
            return render_template('register.html', error="이름, 이메일, 핸드폰번호를 모두 입력해주세요.", departments=departments)
    departments = data_manager.load_departments()
    return render_template('register.html', departments=departments)

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
        department_questions = [q for q in all_questions if q.department_id == candidate.department_id]
        java_objective = [q for q in department_questions if q.category == 'Java' and q.type == '객관식']
        db_objective = [q for q in department_questions if q.category == 'Database' and q.type == '객관식']
        # 출제 개수 설정값 적용
        random_config = load_random_config()
        java_count = random_config.get('java_count', 10)
        db_count = random_config.get('db_count', 3)
        import random
        selected_java = random.sample(java_objective, min(len(java_objective), java_count))
        selected_db = random.sample(db_objective, min(len(db_objective), db_count))
        selected_ids = [q.id for q in selected_java] + [q.id for q in selected_db]
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
def admin():
    """관리자 페이지 - 대시보드"""
    candidates = data_manager.get_all_candidates()
    results = data_manager.get_all_results()
    departments = data_manager.load_departments()
    questions = data_manager.load_questions()
    # 부서 미지정 문제 목록
    unassigned_questions = [q for q in questions if not q.department_id]
    
    # 날짜 포맷 변경 (ISO -> YYYY-MM-DD HH:MM:SS) 및 None 체크
    for c in candidates:
        if c.created_at:
            try:
                c.created_at_formatted = datetime.fromisoformat(c.created_at).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                c.created_at_formatted = "N/A"
        else:
            c.created_at_formatted = "N/A"

    # 대시보드 데이터 계산
    total_candidates = len(candidates)
    
    # 지원자별 결과 매핑
    candidate_results = {}
    for result in results:
        candidate = data_manager.get_candidate(result.candidate_id)
        if candidate:
            candidate_results[result.candidate_id] = {
                'candidate': candidate,
                'result': result
            }
    
    return render_template('admin.html', candidates=candidates, candidate_results=candidate_results, departments=departments, unassigned_questions=unassigned_questions, questions=[q.to_dict() for q in questions])

@app.route('/admin/candidate/delete/<candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    """지원자 삭제"""
    data_manager.delete_candidate(candidate_id)
    data_manager.delete_result(candidate_id)
    return jsonify(success=True, message="지원자가 삭제되었습니다.")

@app.route('/admin/questions')
def question_manage():
    """문제 관리 페이지"""
    questions = data_manager.load_questions()
    departments = data_manager.load_departments()
    return render_template('question_manage.html', technical_questions=questions, departments=departments)

@app.route('/admin/questions/add', methods=['POST'])
def add_question():
    try:
        data = request.get_json()
        if data['category'] in ['Java', 'Database']:
            existing_questions = data_manager._load_json(data_manager.questions_file)["technical_questions"]
            new_id = f"tech_{len(existing_questions) + 1}"
            question_data = {
                'id': new_id,
                'category': data['category'],
                'type': data['type'],
                'difficulty': data['difficulty'],
                'question': data['question'],
                'points': int(data['points'])
            }
            if data['type'] == '객관식':
                question_data['options'] = data['options']
                question_data['correct_answer'] = data['correct_answer']
            else:
                question_data['keywords'] = data['keywords']
                question_data['correct_answer'] = data['correct_answer']
            questions_data = data_manager._load_json(data_manager.questions_file)
            questions_data["technical_questions"].append(question_data)
            data_manager._save_json(data_manager.questions_file, questions_data)
            return jsonify({'success': True, 'message': '문제가 추가되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '카테고리는 Java 또는 Database만 허용됩니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions/edit/<question_id>', methods=['PUT'])
def edit_question(question_id):
    try:
        data = request.get_json()
        questions_data = data_manager._load_json(data_manager.questions_file)
        for question in questions_data["technical_questions"]:
            if question['id'] == question_id:
                question.update({
                    'category': data['category'],
                    'type': data['type'],
                    'difficulty': data['difficulty'],
                    'question': data['question'],
                    'points': int(data['points'])
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
        for i, question in enumerate(questions_data["technical_questions"]):
            if question['id'] == question_id:
                del questions_data["technical_questions"][i]
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
    for question in questions_data["problem_solving_questions"]:
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
    questions = data_manager.load_questions()
    return jsonify([{
        'id': q.id,
        'category': q.category,
        'type': q.type,
        'difficulty': q.difficulty,
        'question': q.question,
        'options': q.options,
        'points': q.points
    } for q in questions])

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
    # 지원자에게 출제된 문제만 불러오기
    all_questions = data_manager.load_questions()
    selected_ids = getattr(candidate, 'selected_questions', [])
    selected_questions = [q for q in all_questions if q.id in selected_ids]
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
        # data_manager.update_candidate 호출 시 'test_deadline' 없음
        updated_candidate = data_manager.update_candidate(
            candidate_id, 
            name, 
            access_date, 
            int(test_duration),
            department_id
        )
        if updated_candidate:
            return jsonify(success=True, message="지원자 정보가 수정되었습니다.", candidate=updated_candidate.to_dict())
        else:
            return jsonify(success=False, message="지원자를 찾을 수 없습니다.")
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
    
    # 부서 이름을 id에 매핑시켜두면 템플릿에서 사용하기 편리함
    department_map = {d.id: d.name for d in all_departments}

    return render_template('candidate_question_match.html',
                           candidates=all_candidates,
                           questions=all_questions,
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
                q.department_id = department.id
        data_manager.save_all_questions(questions)
    return jsonify(success=True, message="부서가 추가되었습니다.", department=department.to_dict())

@app.route('/admin/departments/assign_questions', methods=['POST'])
def assign_questions_to_department():
    """특정 부서에 문제를 할당하는 API"""
    data = request.get_json() if request.is_json else request.form
    department_id = data.get('department_id')
    question_ids = data.get('question_ids')
    if not department_id or not question_ids:
        return jsonify(success=False, message="부서와 문제를 모두 선택해야 합니다."), 400
    if isinstance(question_ids, str):
        question_ids = [question_ids]
    questions = data_manager.load_questions()
    for q in questions:
        if q.id in question_ids:
            q.department_id = department_id
        elif q.department_id == department_id and q.id not in question_ids:
            q.department_id = None  # 할당 해제
    data_manager.save_all_questions(questions)
    return jsonify(success=True, message="문제가 성공적으로 할당되었습니다.")

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
                q.department_id = None
                found = True
                break
        if found:
            data_manager.save_all_questions(questions)
            return jsonify({'success': True, 'message': '문제의 부서 할당이 해제되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '문제를 찾을 수 없습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/candidate/<candidate_id>/questions/randomize', methods=['POST'])
def randomize_candidate_questions(candidate_id):
    """지원자별 문제 세트를 JAVA 객관식 10, DB 객관식 3개로 다시 랜덤 할당하는 API"""
    candidate = data_manager.get_candidate(candidate_id)
    if not candidate:
        return jsonify(success=False, message="지원자를 찾을 수 없습니다."), 404
    all_questions = data_manager.load_questions()
    # 지원자 부서에 해당하는 문제만 필터링
    department_questions = [q for q in all_questions if q.department_id == candidate.department_id]
    java_objective = [q for q in department_questions if q.category == 'Java' and q.type == '객관식']
    db_objective = [q for q in department_questions if q.category == 'Database' and q.type == '객관식']
    import random
    selected_java = random.sample(java_objective, min(len(java_objective), 10))
    selected_db = random.sample(db_objective, min(len(db_objective), 3))
    selected_ids = [q.id for q in selected_java] + [q.id for q in selected_db]
    candidate.selected_questions = selected_ids
    data_manager.update_candidate(candidate)
    return jsonify(success=True, selected_questions=selected_ids)

@app.route('/api/random_config', methods=['GET'])
def get_random_config():
    return jsonify(load_random_config())

@app.route('/api/random_config', methods=['POST'])
def set_random_config():
    data = request.get_json()
    java_count = int(data.get('java_count', 10))
    db_count = int(data.get('db_count', 3))
    config = {"java_count": java_count, "db_count": db_count}
    save_random_config(config)
    return jsonify(success=True, config=config)

# 로컬 LLM 파이프라인(최초 1회만 로드)
local_llm = None

def get_local_llm():
    global local_llm
    if local_llm is None:
        # 한글 특화 모델, 최초 실행 시 다운로드(수 분 소요)
        local_llm = pipeline("text-generation", model="beomi/KoAlpaca-Polyglot-5.8B", device_map="auto")
    return local_llm

def generate_questions_with_local_llm(prompt):
    llm = get_local_llm()
    # max_new_tokens, temperature 등은 필요에 따라 조정
    result = llm(prompt, max_new_tokens=256, do_sample=True, temperature=0.7)
    # 결과에서 질문 부분만 추출
    return result[0]['generated_text']

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

if __name__ == '__main__':
    # 개발 서버 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 