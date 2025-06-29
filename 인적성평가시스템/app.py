from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from models import Candidate, Question, TestResult, DataManager
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = '인적성평가시스템_시크릿키_2024'  # 세션 관리를 위한 시크릿 키

# 데이터 매니저 초기화
data_manager = DataManager()

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
    
    # 기술 문제 로드
    questions_data = data_manager._load_json(data_manager.questions_file)
    technical_questions = questions_data.get("technical_questions", [])
    
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
    
    # 문제해결력 문제 로드
    questions_data = data_manager._load_json(data_manager.questions_file)
    problem_solving_questions = questions_data.get("problem_solving_questions", [])
    
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
                'options': data['options'],
                'correct_answer': data['correct_answer']
            }
            
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
    if not name or not access_date:
        return {'success': False, 'message': '이름, 접속 가능 날짜는 필수입니다.'}
    for c in data_manager.get_all_candidates():
        if c.name == name:
            return {'success': False, 'message': '이미 등록된 이름입니다.'}
    candidate = Candidate(name=name, access_date=access_date, test_duration=test_duration)
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
        
        return jsonify({'success': True, 'message': '지원자 정보가 수정되었습니다.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    # 개발 서버 실행
    app.run(debug=True, host='0.0.0.0', port=5000) 