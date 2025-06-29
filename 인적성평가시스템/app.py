from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from models import Candidate, Question, TestResult, DataManager
import os
from datetime import datetime, timedelta
import uuid
import pandas as pd
from docx import Document
from werkzeug.utils import secure_filename
import tempfile
import requests

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
            
            # 문제 시작 확인 (카테고리, 유형, 난이도가 포함된 행)
            if any(keyword in text for keyword in ['Java', 'Database', '문제해결', '객관식', '주관식', '초급', '중급']):
                if current_question:
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
    
    # 평가완료시간 체크 - 마감 날짜가 지났는지 확인
    if data_manager.is_test_deadline_passed(session['candidate_id']):
        # 마감 날짜만 안내
        deadline_info = f" (마감일: {candidate.test_deadline[:10]})" if candidate.test_deadline else ""
        return render_template('test_start.html', 
                             candidate=candidate, 
                             error=f"평가 완료일이 지났습니다. 관리자에게 문의하세요.{deadline_info}")
    
    # 이미 평가를 완료했는지 확인
    existing_result = data_manager.get_result(session['candidate_id'])
    if existing_result:
        return redirect(url_for('result'))
    
    return render_template('test_start.html', candidate=candidate)

@app.route('/test/technical')
def technical_test():
    """기술 평가 페이지"""
    if 'candidate_id' not in session:
        return redirect(url_for('register'))
    
    # 지원자 정보 가져오기
    candidate = data_manager.get_candidate(session['candidate_id'])
    if not candidate:
        return redirect(url_for('register'))
    
    # 평가 시작 시 세션 초기화
    session['current_step'] = 'technical'
    session.pop('technical_answers', None)  # 이전 답안 초기화
    
    # 세션에 문제풀이 시간 저장
    session['test_duration'] = candidate.test_duration
    
    # 지원자별 출제 문제 로드
    all_questions = data_manager.get_candidate_questions(session['candidate_id'])
    technical_questions = [q for q in all_questions if q.category in ['Java', 'Database']]
    
    # 지원자 정보와 문제를 템플릿에 전달
    return render_template('technical_test.html', 
                         candidate=candidate, 
                         questions=technical_questions)

@app.route('/test/problem_solving')
def problem_solving_test():
    """문제해결력 평가 페이지"""
    if 'candidate_id' not in session:
        return redirect(url_for('register'))
    
    # 1단계에서 넘어온 경우에만 접근 허용
    if session.get('current_step') != 'problem_solving':
        return redirect(url_for('technical_test'))
    
    # 지원자 정보 가져오기
    candidate = data_manager.get_candidate(session['candidate_id'])
    if not candidate:
        return redirect(url_for('register'))
    
    # 세션에 문제풀이 시간 저장
    session['test_duration'] = candidate.test_duration
    
    # 지원자별 출제 문제 로드
    all_questions = data_manager.get_candidate_questions(session['candidate_id'])
    problem_solving_questions = [q for q in all_questions if q.category == '문제해결']
    
    # 지원자 정보와 문제를 템플릿에 전달
    return render_template('problem_solving_test.html', 
                         candidate=candidate, 
                         questions=problem_solving_questions)

@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    """답안 제출 및 채점"""
    if 'candidate_id' not in session:
        return jsonify({'error': '세션이 만료되었습니다.'}), 400
    
    candidate_id = session['candidate_id']
    current_step = request.form.get('current_step', 'technical')  # 현재 단계 확인
    
    # 답안 수집
    answers = {}
    for key, value in request.form.items():
        if key.startswith('question_'):
            question_id = key.replace('question_', '')
            answers[question_id] = value
    
    # 현재 단계에 따라 처리
    if current_step == 'technical':
        # 1단계(기술 평가) 완료 - 임시 저장 후 2단계로 이동
        session['technical_answers'] = answers
        session['current_step'] = 'problem_solving'
        return redirect(url_for('problem_solving_test'))
    
    elif current_step == 'problem_solving':
        # 2단계(문제해결력 평가) 완료 - 전체 평가 결과 생성
        technical_answers = session.get('technical_answers', {})
        
        # 전체 답안 합치기
        all_answers = {**technical_answers, **answers}
        
        # 평가 결과 생성
        result = TestResult(candidate_id)
        for question_id, answer in all_answers.items():
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
    
    else:
        # 잘못된 단계 정보
        return jsonify({'error': '잘못된 평가 단계입니다.'}), 400

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
    """관리자 페이지 - 지원자 목록 및 결과 조회"""
    candidates = data_manager.get_all_candidates()
    results = data_manager.get_all_results()
    
    # 지원자별 결과 매핑
    candidate_results = {}
    for result in results:
        candidate = data_manager.get_candidate(result.candidate_id)
        if candidate:
            candidate_results[result.candidate_id] = {
                'candidate': candidate,
                'result': result
            }
    
    return render_template('admin.html', candidates=candidates, candidate_results=candidate_results)

@app.route('/admin/candidate/delete/<candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    """지원자 삭제"""
    try:
        print(f"삭제 요청 받음: candidate_id = {candidate_id}")  # 디버깅 로그
        
        # 지원자 존재 여부 확인
        candidate = data_manager.get_candidate(candidate_id)
        if not candidate:
            print(f"지원자를 찾을 수 없음: {candidate_id}")  # 디버깅 로그
            return jsonify({'success': False, 'message': '지원자를 찾을 수 없습니다.'})
        
        print(f"지원자 발견: {candidate.name}")  # 디버깅 로그
        
        # 지원자 삭제
        data_manager.delete_candidate(candidate_id)
        print(f"지원자 삭제 완료: {candidate_id}")  # 디버깅 로그
        
        # 관련 결과도 삭제
        data_manager.delete_result(candidate_id)
        print(f"평가 결과 삭제 완료: {candidate_id}")  # 디버깅 로그
        
        return jsonify({'success': True, 'message': '지원자가 삭제되었습니다.'})
    except Exception as e:
        print(f"삭제 중 오류 발생: {str(e)}")  # 디버깅 로그
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/candidate/deadline/<candidate_id>', methods=['PUT'])
def set_candidate_deadline(candidate_id):
    """지원자 평가 완료시간 설정"""
    try:
        data = request.get_json()
        deadline = data.get('deadline')
        
        if deadline:
            data_manager.set_candidate_deadline(candidate_id, deadline)
            return jsonify({'success': True, 'message': '평가 완료시간이 설정되었습니다.'})
        else:
            return jsonify({'success': False, 'message': '완료시간을 입력해주세요.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions')
def question_manage():
    """문제 관리 페이지"""
    questions_data = data_manager._load_json(data_manager.questions_file)
    technical_questions = questions_data.get("technical_questions", [])
    problem_solving_questions = questions_data.get("problem_solving_questions", [])
    
    return render_template('question_manage.html', 
                         technical_questions=technical_questions,
                         problem_solving_questions=problem_solving_questions)

@app.route('/admin/questions/add', methods=['POST'])
def add_question():
    """문제 추가"""
    try:
        data = request.get_json()
        # 새 문제 ID 생성
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
            # 기술 문제에 추가
            questions_data = data_manager._load_json(data_manager.questions_file)
            questions_data["technical_questions"].append(question_data)
        else:  # 문제해결
            existing_questions = data_manager._load_json(data_manager.questions_file)["problem_solving_questions"]
            new_id = f"ps_{len(existing_questions) + 1}"
            question_data = {
                'id': new_id,
                'category': data['category'],
                'type': data['type'],
                'difficulty': data['difficulty'],
                'question': data['question'],
                'points': int(data['points']),
                'options': data.get('options', []),
                'correct_answer': data['correct_answer']
            }
            if data['type'] == '주관식':
                question_data['keywords'] = data['keywords']
            # 문제해결 문제에 추가
            questions_data = data_manager._load_json(data_manager.questions_file)
            questions_data["problem_solving_questions"].append(question_data)
        data_manager._save_json(data_manager.questions_file, questions_data)
        return jsonify({'success': True, 'message': '문제가 추가되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions/edit/<question_id>', methods=['PUT'])
def edit_question(question_id):
    """문제 수정"""
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
        
        # 문제해결 문제에서 찾기
        for question in questions_data["problem_solving_questions"]:
            if question['id'] == question_id:
                question.update({
                    'category': data['category'],
                    'type': data['type'],
                    'difficulty': data['difficulty'],
                    'question': data['question'],
                    'points': int(data['points']),
                    'options': data['options'],
                    'correct_answer': data['correct_answer']
                })
                
                data_manager._save_json(data_manager.questions_file, questions_data)
                return jsonify({'success': True, 'message': '문제가 수정되었습니다.'})
        
        return jsonify({'success': False, 'message': '문제를 찾을 수 없습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/questions/delete/<question_id>', methods=['DELETE'])
def delete_question(question_id):
    """문제 삭제"""
    try:
        questions_data = data_manager._load_json(data_manager.questions_file)
        
        # 기술 문제에서 삭제
        for i, question in enumerate(questions_data["technical_questions"]):
            if question['id'] == question_id:
                del questions_data["technical_questions"][i]
                data_manager._save_json(data_manager.questions_file, questions_data)
                return jsonify({'success': True, 'message': '문제가 삭제되었습니다.'})
        
        # 문제해결 문제에서 삭제
        for i, question in enumerate(questions_data["problem_solving_questions"]):
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
    """카테고리별 랜덤 문제 선택 API (GET)"""
    try:
        java_count = int(request.args.get('java', 0))
        database_count = int(request.args.get('database', 0))
        problem_solving_count = int(request.args.get('problem_solving', 0))
        selected_questions = []
        # Java 문제 랜덤 선택
        if java_count > 0:
            java_questions = data_manager.get_questions_by_category('Java')
            if java_questions:
                import random
                selected_java = random.sample(java_questions, min(java_count, len(java_questions)))
                selected_questions.extend([q.id for q in selected_java])
        # Database 문제 랜덤 선택
        if database_count > 0:
            database_questions = data_manager.get_questions_by_category('Database')
            if database_questions:
                import random
                selected_database = random.sample(database_questions, min(database_count, len(database_questions)))
                selected_questions.extend([q.id for q in selected_database])
        # 문제해결 문제 랜덤 선택
        if problem_solving_count > 0:
            problem_solving_questions = data_manager.get_questions_by_category('문제해결')
            if problem_solving_questions:
                import random
                selected_problem_solving = random.sample(problem_solving_questions, min(problem_solving_count, len(problem_solving_questions)))
                selected_questions.extend([q.id for q in selected_problem_solving])
        return jsonify({
            'success': True,
            'selected_questions': selected_questions,
            'total_count': len(selected_questions)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'랜덤 문제 선택 중 오류가 발생했습니다: {str(e)}'
        }), 500

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
    
    # 모든 문제 불러오기
    all_questions = data_manager.load_questions()
    
    # 답변 매핑 - 모든 문제에 대해 처리
    answers = []
    for question in all_questions:
        answer = result.answers.get(question.id, '')  # 답변하지 않은 경우 빈 문자열
        if answer:  # 답변한 경우
            answers.append({
                'question': question,
                'answer': answer,
                'is_correct': question.is_correct(answer),
                'answered': True
            })
        else:  # 답변하지 않은 경우
            answers.append({
                'question': question,
                'answer': '',
                'is_correct': False,
                'answered': False
            })
    
    return render_template('admin_answer_detail.html', candidate=candidate, result=result, answers=answers)

@app.route('/admin/candidate/add', methods=['POST'])
def add_candidate():
    data = request.get_json()
    name = data.get('name')
    access_date = data.get('access_date')
    test_duration = int(data.get('test_duration', 10))
    selected_questions = data.get('selected_questions', [])  # 출제할 문제 ID 목록
    
    if not name or not access_date:
        return {'success': False, 'message': '이름, 접속 가능 날짜는 필수입니다.'}
    
    for c in data_manager.get_all_candidates():
        if c.name == name:
            return {'success': False, 'message': '이미 등록된 이름입니다.'}
    
    candidate = Candidate(name=name, access_date=access_date, test_duration=test_duration, selected_questions=selected_questions)
    data_manager.save_candidate(candidate)
    return {'success': True, 'message': '지원자가 등록되었습니다.'}

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
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        access_date = data.get('access_date')
        test_duration = int(data.get('test_duration', 10))
        selected_questions = data.get('selected_questions', [])  # 출제할 문제 ID 목록
        
        if not name or not access_date:
            return jsonify({'success': False, 'message': '이름과 접속 가능 날짜는 필수입니다.'})
        
        # 지원자 존재 여부 확인
        candidate = data_manager.get_candidate(candidate_id)
        if not candidate:
            return jsonify({'success': False, 'message': '지원자를 찾을 수 없습니다.'})
        
        # 이름 중복 확인 (자신을 제외하고)
        candidates = data_manager.get_all_candidates()
        for c in candidates:
            if c.id != candidate_id and c.name == name:
                return jsonify({'success': False, 'message': '이미 등록된 이름입니다.'})
        
        # 지원자 정보 수정
        data_manager.update_candidate(candidate_id, name, access_date, test_duration)
        
        # 선택된 문제 설정
        data_manager.set_candidate_questions(candidate_id, selected_questions)
        
        return jsonify({'success': True, 'message': '지원자 정보가 수정되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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
        problem_solving_questions = questions_data.get("problem_solving_questions", [])
        
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
                elif question['category'] == '문제해결':
                    for i, q in enumerate(problem_solving_questions):
                        if q['question'] == question['question']:
                            existing_question = q
                            target_list = problem_solving_questions
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
                    elif question['category'] == '문제해결':
                        problem_solving_questions.append(question)
                    added_count += 1
                
            except Exception as e:
                errors.append(f"문제 처리 중 오류: {str(e)}")
                skipped_count += 1
        
        # 파일 저장
        questions_data["technical_questions"] = technical_questions
        questions_data["problem_solving_questions"] = problem_solving_questions
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

if __name__ == '__main__':
    # 개발 서버 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 