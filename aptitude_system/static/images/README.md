# 이미지 파일 사용 가이드

이 폴더에는 웹사이트에서 사용할 이미지 파일들을 저장합니다.

## 지원하는 이미지 형식
- PNG (.png)
- JPG/JPEG (.jpg, .jpeg)
- GIF (.gif)
- SVG (.svg)

## 권장 이미지 파일명
- `logo.png` - 회사 로고
- `favicon.ico` - 브라우저 탭 아이콘
- `banner.jpg` - 메인 배너 이미지
- `background.jpg` - 배경 이미지

## HTML에서 이미지 사용법
```html
<!-- 로고 이미지 -->
<img src="{{ url_for('static', filename='images/logo.png') }}" alt="회사 로고">

<!-- CSS에서 배경 이미지 -->
<style>
.header {
    background-image: url("{{ url_for('static', filename='images/banner.jpg') }}");
}
</style>
```

## 이미지 최적화 권장사항
- 로고: PNG 형식 권장 (투명 배경 지원)
- 사진: JPG 형식 권장 (파일 크기 최적화)
- 아이콘: SVG 형식 권장 (확대/축소 시 품질 유지)
- 파일 크기: 웹 최적화를 위해 1MB 이하 권장 