# QA Workbench Web

기존 QA Workbench v5.30 구조화 버전을 바탕으로 만든 Streamlit 웹 버전입니다.

## 포함 기능
- 대시보드
- 검사관리
  - 체크시트 이미지 업로드
  - Tesseract OCR 자동 인식
  - 측정값 수동 수정
  - 기준값 비교 및 자동 합·불 판정
  - 불합격 시 불량관리 자동 연계
- 불량관리 / 원본 검사이력 추적
- 일정·할일 / 시간 알림
- 납품일정 / 납기 긴급도 색상
- ERP/BOM
  - 품목·현재고·안전재고
  - BOM
  - 생산계획
  - 30일 예상 자재소요 / 부족·여유 판정

## 로컬 실행
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Community Cloud 배포
1. 이 폴더의 파일 전체를 GitHub 저장소에 업로드합니다.
2. https://share.streamlit.io 에 GitHub 계정으로 로그인합니다.
3. Create app → 저장소 선택
4. Main file path: `streamlit_app.py`
5. Deploy
6. 생성된 `https://...streamlit.app` 링크를 공유하면 됩니다.

## 중요
- 기존 macOS Apple Vision OCR은 Streamlit 서버가 Linux이므로 사용할 수 없습니다.
  웹 버전은 Tesseract OCR을 사용하고, OCR 오인식 값은 직접 수정할 수 있습니다.
- Streamlit Community Cloud의 로컬 SQLite 파일은 앱 재시작/재배포 시 영구 보존을 보장하지 않습니다.
  과제 발표/시연에는 충분하지만, 실제 팀 공용 운영에는 Supabase/PostgreSQL 같은 외부 DB 연결을 권장합니다.
- 시간 알림은 브라우저 페이지가 열려 있거나 새로고침될 때 확인되는 방식입니다.
  브라우저가 완전히 닫힌 상태의 푸시 알림은 별도 알림 서비스가 필요합니다.
