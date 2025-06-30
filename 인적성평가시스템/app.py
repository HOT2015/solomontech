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

app = Flask(__name__)
app.secret_key = '인적성평가시스템_시크릿키_2024'  # 세션 관리를 위한 시크릿 키

# 회사 정보 설정 (이미지 파일과 함께 사용)
app.config['COMPANY_NAME'] = '인적성 평가시스템'  # 회사명 (로고 이미지 파일명으로 변경 가능)
app.config['COMPANY_DESCRIPTION'] = '기술 역량과 문제 해결력을 통합적으로 평가하는 온라인 시스템'  # 회사 설명
app.config['COMPANY_LOGO'] = None  # 로고 이미지 파일명 (예: 'logo.png', 'company_logo.jpg' 등)

# 데이터 매니저 초기화
data_manager = DataManager()

# 파일 업로드 관련 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 업로드 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

RANDOM_CONFIG_FILE = os.path.join('data', 'random_config.json')

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

def parse_excel_file(file_path):
    """엑셀 파일에서 문제 데이터 파싱"""
    try:
        df = pd.read_excel(file_path, sheet_name=0)
        questions = []
        
        for index, row in df.iterrows():
            # 빈 행 건너뛰기
            if pd.isna(row.iloc[0]) or str(row.iloc[0]).strip() == '':
                continue
                
            question_data = {
                'id': str(uuid.uuid4()),
                'category': str(row.iloc[0]).strip(),
                'type': str(row.iloc[1]).strip(),
                'difficulty': str(row.iloc[2]).strip(),
                'question': str(row.iloc[3]).strip(),
                'points': int(row.iloc[4]) if not pd.isna(row.iloc[4]) else 10
            }
            
            # Java, Database 카테고리 외에는 건너뛰기
            if question_data['category'] not in ['Java', 'Database']:
                continue
            
            # 객관식인 경우
            if question_data['type'] == '객관식':
                options = []
                for i in range(5, 9):  # 5-8번째 열이 선택지
                    if not pd.isna(row.iloc[i]) and str(row.iloc[i]).strip() != '':
                        options.append(str(row.iloc[i]).strip())
                question_data['options'] = options
                question_data['correct_answer'] = str(row.iloc[9]).strip() if not pd.isna(row.iloc[9]) else ''
            
            # 주관식인 경우
            elif question_data['type'] == '주관식':
                keywords = str(row.iloc[5]).strip() if not pd.isna(row.iloc[5]) else ''
                question_data['keywords'] = [kw.strip() for kw in keywords.split(',') if kw.strip()] if keywords else []
                question_data['correct_answer'] = str(row.iloc[6]).strip() if not pd.isna(row.iloc[6]) else ''
            
            questions.append(question_data)
        
        return questions
    except Exception as e:
        raise Exception(f"엑셀 파일 파싱 오류: {str(e)}")

def parse_word_file(file_path):
    """워드 파일에서 문제 데이터 파싱"""
    try:
        doc = Document(file_path)
        questions = []
        current_question = None
        
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            
            # 문제 시작 확인 (Java, Database 카테고리만 허용)
            if any(keyword in text for keyword in ['Java', 'Database', '객관식', '주관식', '초급', '중급']):
                if current_question:
                    # 이전 문제 저장 전 유효성 검사
                    if current_question.get('category') in ['Java', 'Database']:
                        questions.append(current_question)
                
                # 새로운 문제 시작
                parts = text.split('|')
                if len(parts) >= 4:
                    current_question = {
                        'id': str(uuid.uuid4()),
                        'category': parts[0].strip(),
                        'type': parts[1].strip(),
                        'difficulty': parts[2].strip(),
                        'question': parts[3].strip(),
                        'points': 10  # 기본값
                    }
                    
                    if current_question['type'] == '객관식':
                        current_question['options'] = []
                    elif current_question['type'] == '주관식':
                        current_question['keywords'] = []
            
            # 문제 내용 추가
            elif current_question and not current_question.get('question_content'):
                current_question['question_content'] = text
            
            # 객관식 선택지 추가
            elif current_question and current_question['type'] == '객관식' and text.startswith(('1.', '2.', '3.', '4.')):
                option = text[2:].strip()
                if option:
                    current_question['options'].append(option)
            
            # 정답 추가
            elif current_question and text.startswith('정답:'):
                current_question['correct_answer'] = text[3:].strip()
            
            # 주관식 키워드 추가
            elif current_question and current_question['type'] == '주관식' and text.startswith('키워드:'):
                keywords = text[4:].strip()
                current_question['keywords'] = [kw.strip() for kw in keywords.split(',') if kw.strip()]
        
        # 마지막 문제 추가
        if current_question:
            questions.append(current_question)
        
        return questions
    except Exception as e:
        raise Exception(f"워드 파일 파싱 오류: {str(e)}")

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

@app.route('/admin/questions/upload', methods=['POST'])
def upload_questions():
    """파일로 문제 업로드"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다.'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'message': '파일이 선택되지 않았습니다.'})
        
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': '지원하지 않는 파일 형식입니다. (.xlsx, .docx만 지원)'})
        
        # 파일 크기 확인
        file.seek(0, 2)  # 파일 끝으로 이동
        file_size = file.tell()
        file.seek(0)  # 파일 시작으로 이동
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'success': False, 'message': '파일 크기가 너무 큽니다. (최대 10MB)'})
        
        # 파일 저장
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # 파일 파싱
        if filename.endswith('.xlsx'):
            questions = parse_excel_file(file_path)
        elif filename.endswith('.docx'):
            questions = parse_word_file(file_path)
        else:
            return jsonify({'success': False, 'message': '지원하지 않는 파일 형식입니다.'})
        
        # 임시 파일 삭제
        os.remove(file_path)
        
        if not questions:
            return jsonify({'success': False, 'message': '파일에서 문제를 찾을 수 없습니다.'})
        
        # 검증만 수행하는 경우
        if request.form.get('validate_only'):
            return jsonify({
                'success': True,
                'message': '파일 검증 완료',
                'total_questions': len(questions),
                'added_questions': 0,
                'updated_questions': 0,
                'skipped_questions': len(questions),
                'errors': []
            })
        
        # 기존 문제 로드
        questions_data = data_manager._load_json(data_manager.questions_file)
        technical_questions = questions_data.get("technical_questions", [])
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        overwrite = request.form.get('overwrite') == 'on'
        
        for question in questions:
            try:
                # 문제 유효성 검사
                if not all(key in question for key in ['category', 'type', 'difficulty', 'question']):
                    errors.append(f"문제 {question.get('question', 'Unknown')[:30]}...: 필수 필드가 누락되었습니다.")
                    skipped_count += 1
                    continue
                
                # 기존 문제와 중복 확인
                existing_question = None
                target_list = None
                
                if question['category'] in ['Java', 'Database']:
                    for i, q in enumerate(technical_questions):
                        if q['question'] == question['question']:
                            existing_question = q
                            target_list = technical_questions
                            target_index = i
                            break
                
                if existing_question:
                    if overwrite:
                        # 기존 문제 업데이트
                        existing_question.update(question)
                        updated_count += 1
                    else:
                        # 건너뛰기
                        skipped_count += 1
                        continue
                else:
                    # 새 문제 추가
                    if question['category'] in ['Java', 'Database']:
                        technical_questions.append(question)
                    added_count += 1
                
            except Exception as e:
                errors.append(f"문제 처리 중 오류: {str(e)}")
                skipped_count += 1
        
        # 파일 저장
        questions_data["technical_questions"] = technical_questions
        data_manager._save_json(data_manager.questions_file, questions_data)
        
        return jsonify({
            'success': True,
            'message': '파일 업로드가 완료되었습니다.',
            'total_questions': len(questions),
            'added_questions': added_count,
            'updated_questions': updated_count,
            'skipped_questions': skipped_count,
            'errors': errors
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'업로드 중 오류가 발생했습니다: {str(e)}'})

@app.route('/download_sample_excel')
def download_sample_excel():
    """엑셀 샘플 파일 다운로드"""
    try:
        # 샘플 데이터 생성
        sample_data = [
            ['카테고리', '유형', '난이도', '문제', '배점', '선택지1', '선택지2', '선택지3', '선택지4', '정답', '키워드'],
            ['Java', '객관식', '초급', 'Java에서 변수를 선언하는 키워드는?', 10, 'var', 'let', 'const', 'variable', 'var', ''],
            ['Database', '객관식', '초급', 'SQL에서 데이터를 조회하는 명령어는?', 10, 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'SELECT', ''],
            ['문제해결', '객관식', '초급', '배열에서 최대값을 찾는 알고리즘의 시간복잡도는?', 10, 'O(1)', 'O(n)', 'O(n²)', 'O(log n)', 'O(n)', ''],
            ['Java', '주관식', '중급', '1부터 10까지 출력하는 for문을 작성하세요.', 15, '', '', '', '', 'for(int i=1; i<=10; i++)', 'for, int, i, 1, 10, ++'],
            ['Database', '주관식', '중급', '사용자 테이블에서 이름이 "김"으로 시작하는 사용자를 조회하는 SQL을 작성하세요.', 15, '', '', '', '', 'SELECT * FROM users WHERE name LIKE "김%"', 'SELECT, FROM, WHERE, LIKE, 김%']
        ]
        
        # DataFrame 생성
        df = pd.DataFrame(sample_data[1:], columns=sample_data[0])
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            df.to_excel(tmp.name, index=False)
            
            # 파일 읽기
            with open(tmp.name, 'rb') as f:
                file_content = f.read()
            
            # 임시 파일 삭제
            os.unlink(tmp.name)
        
        from flask import send_file
        from io import BytesIO
        
        return send_file(
            BytesIO(file_content),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='문제_업로드_샘플.xlsx'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download_sample_word')
def download_sample_word():
    """워드 샘플 파일 다운로드"""
    try:
        # 워드 문서 생성
        doc = Document()
        
        # 제목 추가
        title = doc.add_heading('문제 업로드 샘플', 0)
        
        # 설명 추가
        doc.add_paragraph('아래 형식에 맞춰 문제를 작성하세요.')
        doc.add_paragraph('각 문제는 "카테고리|유형|난이도|문제" 형식으로 시작합니다.')
        doc.add_paragraph('')
        
        # 샘플 문제들 추가
        sample_questions = [
            'Java|객관식|초급|Java에서 변수를 선언하는 키워드는?',
            '1. var',
            '2. let', 
            '3. const',
            '4. variable',
            '정답: var',
            '',
            'Database|객관식|초급|SQL에서 데이터를 조회하는 명령어는?',
            '1. SELECT',
            '2. INSERT',
            '3. UPDATE', 
            '4. DELETE',
            '정답: SELECT',
            '',
            'Java|주관식|중급|1부터 10까지 출력하는 for문을 작성하세요.',
            '키워드: for, int, i, 1, 10, ++',
            '정답: for(int i=1; i<=10; i++)',
            '',
            'Database|주관식|중급|사용자 테이블에서 이름이 "김"으로 시작하는 사용자를 조회하는 SQL을 작성하세요.',
            '키워드: SELECT, FROM, WHERE, LIKE, 김%',
            '정답: SELECT * FROM users WHERE name LIKE "김%"'
        ]
        
        for line in sample_questions:
            if line.strip():
                doc.add_paragraph(line)
            else:
                doc.add_paragraph()
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            doc.save(tmp.name)
            
            # 파일 읽기
            with open(tmp.name, 'rb') as f:
                file_content = f.read()
            
            # 임시 파일 삭제
            os.unlink(tmp.name)
        
        from flask import send_file
        from io import BytesIO
        
        return send_file(
            BytesIO(file_content),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name='문제_업로드_샘플.docx'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/company/settings', methods=['POST'])
def update_company_settings():
    """회사 정보 설정 업데이트"""
    try:
        # 회사명과 설명 업데이트
        company_name = request.form.get('company_name', '').strip()
        company_description = request.form.get('company_description', '').strip()
        
        if company_name:
            app.config['COMPANY_NAME'] = company_name
        if company_description:
            app.config['COMPANY_DESCRIPTION'] = company_description
        
        # 로고 제거 요청 처리
        if request.form.get('remove_logo') == 'true':
            app.config['COMPANY_LOGO'] = None
            return jsonify({'success': True, 'message': '회사 정보가 업데이트되었습니다.'})
        
        # 로고 파일 업로드 처리
        logo_file = request.files.get('logo_file')
        if logo_file and logo_file.filename:
            # 파일 확장자 검사
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
            file_extension = logo_file.filename.rsplit('.', 1)[1].lower() if '.' in logo_file.filename else ''
            
            if file_extension not in allowed_extensions:
                return jsonify({'success': False, 'message': '지원하지 않는 이미지 형식입니다. PNG, JPG, JPEG, GIF, SVG만 지원됩니다.'})
            
            # 파일 크기 검사 (2MB 제한)
            logo_file.seek(0, 2)  # 파일 끝으로 이동
            file_size = logo_file.tell()
            logo_file.seek(0)  # 파일 시작으로 이동
            
            if file_size > 2 * 1024 * 1024:  # 2MB
                return jsonify({'success': False, 'message': '파일 크기가 2MB를 초과합니다.'})
            
            # 안전한 파일명 생성
            filename = secure_filename(logo_file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"logo_{timestamp}_{filename}"
            
            # static/images 폴더에 저장
            logo_path = os.path.join('static', 'images', new_filename)
            logo_file.save(logo_path)
            
            # 기존 로고 파일 삭제 (있는 경우)
            if app.config.get('COMPANY_LOGO'):
                old_logo_path = os.path.join('static', 'images', app.config['COMPANY_LOGO'])
                if os.path.exists(old_logo_path):
                    try:
                        os.remove(old_logo_path)
                    except:
                        pass  # 삭제 실패해도 계속 진행
            
            # 새 로고 파일명 설정
            app.config['COMPANY_LOGO'] = new_filename
        
        return jsonify({'success': True, 'message': '회사 정보가 업데이트되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'설정 업데이트 중 오류가 발생했습니다: {str(e)}'})

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

if __name__ == '__main__':
    # 개발 서버 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 