#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
샘플 로고 이미지 생성 스크립트
PIL(Pillow) 라이브러리를 사용하여 간단한 로고 이미지를 생성합니다.
"""

import os

try:
    from PIL import Image, ImageDraw, ImageFont
    
    def create_sample_logo():
        """샘플 로고 이미지 생성"""
        
        # 이미지 크기 설정
        width, height = 300, 100
        
        # 새 이미지 생성 (흰색 배경)
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        
        # 폰트 설정 (기본 폰트 사용)
        try:
            # Windows 기본 폰트
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            try:
                # macOS 기본 폰트
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
            except:
                try:
                    # Linux 기본 폰트
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
                except:
                    # 기본 폰트 사용
                    font = ImageFont.load_default()
        
        # 텍스트 설정
        text = "인적성평가시스템"
        text_color = (102, 126, 234)  # 파란색 계열
        
        # 텍스트 크기 계산
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # 텍스트 중앙 정렬
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # 텍스트 그리기
        draw.text((x, y), text, fill=text_color, font=font)
        
        # 테두리 추가
        draw.rectangle([0, 0, width-1, height-1], outline=text_color, width=2)
        
        # BASE_DIR: 현재 파일이 위치한 디렉토리의 절대경로
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        STATIC_IMAGES_FOLDER = os.path.join(BASE_DIR, 'static', 'images')
        os.makedirs(STATIC_IMAGES_FOLDER, exist_ok=True)  # 폴더가 없으면 생성
        
        # 파일 저장
        logo_path = os.path.join(STATIC_IMAGES_FOLDER, 'sample_logo.png')
        image.save(logo_path, 'PNG')
        
        print(f"샘플 로고가 생성되었습니다: {logo_path}")
        print("이제 관리자 페이지에서 '회사 정보 수정' 버튼을 클릭하여 로고를 설정할 수 있습니다.")
        
        return logo_path
        
    if __name__ == "__main__":
        create_sample_logo()
        
except ImportError:
    print("PIL(Pillow) 라이브러리가 설치되지 않았습니다.")
    print("다음 명령어로 설치하세요:")
    print("pip install Pillow")
    
    # 대안: 간단한 텍스트 파일 생성
    print("\n대안으로 텍스트 기반 로고 파일을 생성합니다...")
    
    try:
        # BASE_DIR: 현재 파일이 위치한 디렉토리의 절대경로
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        STATIC_IMAGES_FOLDER = os.path.join(BASE_DIR, 'static', 'images')
        os.makedirs(STATIC_IMAGES_FOLDER, exist_ok=True)
        
        # SVG 로고 생성
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="300" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect width="300" height="100" fill="white" stroke="#667eea" stroke-width="2"/>
  <text x="150" y="60" font-family="Arial, sans-serif" font-size="20" fill="#667eea" text-anchor="middle">인적성평가시스템</text>
</svg>'''
        
        with open(os.path.join(STATIC_IMAGES_FOLDER, 'sample_logo.svg'), 'w', encoding='utf-8') as f:
            f.write(svg_content)
        
        print(f"SVG 샘플 로고가 생성되었습니다: {os.path.join(STATIC_IMAGES_FOLDER, 'sample_logo.svg')}")
        
    except Exception as e:
        print(f"SVG 로고 생성 중 오류: {e}") 