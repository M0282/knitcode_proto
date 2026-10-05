# Python Repository Analyzer v0.6

Python 저장소의 AST 구조, Git 동시 수정 이력, import 관계, 함수 호출 관계, 테스트 후보와 공개 API 변화를 결합해 변경 영향을 추정합니다. v0.6은 분석 범위와 진입점부터 파일별 선언·docstring·인코딩, 전체 내부 import·호출 관계, 미해결 호출 사유, API 시그니처와 호환성 변화까지 하나의 검색 가능한 HTML에 표시합니다.

결과는 Wix 교육 템플릿의 밝고 대담한 인상을 참고한 단독 HTML과 Markdown·JSON으로 저장합니다. Python 3.10 이상과 Git이 필요하며 필수 외부 Python 패키지는 없습니다. 상세 생성 과정은 `REPORT_GENERATION.md`에 정리되어 있습니다.

## 빠른 실행 — Sublist3r

PowerShell에서 이 프로젝트 폴더로 이동한 뒤 GitHub 주소만 전달하면 자동으로 임시 clone하고 분석합니다. 저장소 주소뿐 아니라 Issues·PR 하위 주소도 인식합니다.

```powershell
py impact_cli.py --repo-url https://github.com/aboul3la/Sublist3r/issues `
  --changed subbrute/subbrute.py `
  --changed-symbol "subbrute/subbrute.py::print_target" `
  --base HEAD~1 `
  --output impact_output
start impact_output\report.html
```

이미 clone한 저장소가 있다면 기존처럼 로컬 경로를 사용할 수 있습니다.

```powershell
py impact_cli.py target_repo --changed subbrute/subbrute.py --output impact_output
```

최근 커밋의 변경 파일을 분석하려면 다음 명령을 사용합니다.

```powershell
py impact_cli.py target_repo --base HEAD~1 --output impact_output_recent
```

특정 함수만 변경했다고 가정하려면 파일과 함수 ID를 함께 지정합니다. `--changed-symbol`은 여러 번 사용할 수 있습니다.

```powershell
py impact_cli.py demo_fixture --changed app/models.py `
  --changed-symbol "app/models.py::User.__init__" `
  --output impact_output_symbol
```

## 결과 파일

- `report.html`: 외부 서버나 CDN 없이 바로 여는 상세 반응형 보고서
- `analysis.json`: AST, Git, 영향, API, 진입점과 읽기 안내를 묶은 전체 스키마 0.6 원자료
- `report.md`: 핵심 결과를 공유하기 위한 한국어 Markdown 보고서
- `impact.json`, `impact.md`: 기존 사용자와의 호환성을 위한 동일 내용 별칭
- `call_graph.json`: 함수·메서드·생성자 호출 그래프와 전체 미해결 호출
- `api_surface.json`: 공개/비공개 심볼, 시그니처, 문서화 여부와 기준 리비전 대비 API 변화
- `manifest.json`: 분석 snapshot 해시와 각 산출물의 SHA-256·크기

근거 유형은 다음과 같습니다.

| 근거 | 의미 |
|---|---|
| `changed` | 사용자가 변경 대상으로 지정한 파일 |
| `imports_affected_file` | 변경 파일을 직접 또는 간접 import하는 파일 |
| `calls_changed_function` | 변경된 함수·메서드·클래스를 호출하는 함수 |
| `historical_cochange` | Git 커밋에서 여러 번 함께 수정된 파일 |

함수 호출 간 거리는 `1`이면 직접 호출, `2` 이상이면 다른 함수를 거친 간접 호출입니다. `confidence=static`은 import나 같은 파일 정의로 연결한 경우이고, `inferred_instance`는 `obj = Class()`를 바탕으로 `obj.method()`를 연결한 경우입니다. `unique_name_heuristic`은 저장소에 같은 이름의 정의가 하나뿐이라는 규칙으로 연결한 낮은 신뢰도의 후보입니다.

## v0.6에서 추가된 기능

- GitHub 저장소·Issues·PR URL을 저장소 주소로 정규화하고 실제 저장소명을 보고서에 표시
- 분석 범위, Git 이력 상태, 진입점 후보와 호출 그래프 기반 권장 읽기 순서
- 분석한 Python 파일 트리와 제외 디렉터리 규칙
- 모든 내부 import 관계와 해석된 내부 함수 호출 관계를 HTML에서 검색
- 미해결 호출을 내장 함수·외부 라이브러리·동적 속성·정의 미확인으로 분류하고 전체 상세 표시
- 공개 API 전체 목록, 시그니처·상속·docstring, 문서화율과 기준 리비전 대비 변화
- 파일별 클래스·함수·중첩 함수, 위치, 시그니처, docstring, import와 파싱 상태
- 소스 인코딩 감지, 대체 디코딩과 분석 중 파일 변경 진단
- 전체 분석 데이터와 HTML이 동일한 결과 객체에서 생성되도록 표현 계층 분리
- `analysis.json`과 산출물 무결성 확인용 `manifest.json`

## HTML 보고서 구성

1. 저장소와 변경 영향 핵심 지표
2. 분석 범위와 프로젝트 규모
3. 진입점 후보와 권장 읽기 순서
4. Python 파일 트리와 제외 규칙
5. 변경 영향 파일과 근거
6. 연결된 테스트 후보
7. 함수 단위 역방향 영향 전파
8. 전체 내부 import·호출 관계
9. 미해결 호출 사유별 통계와 전체 상세
10. 공개 API·시그니처·docstring과 API 호환성 변화
11. 파일별 선언·docstring·import·파싱 상태
12. Git 동시 수정 이력, 구문·읽기 진단과 분석 한계

각 상세 표는 브라우저에서 검색할 수 있으며 저장소에서 읽은 문자열은 HTML 이스케이프합니다. CSS와 JavaScript는 파일 내부에 포함되므로 별도 서버나 CDN이 필요하지 않습니다.

## v0.5에서 추가된 기능

- Griffe에서 착안한 정적 API surface: 함수 매개변수·기본값·타입 주석, 반환 타입, 공개 여부, docstring, 클래스 상속 수집
- `--base` 기준 공개 심볼 삭제, 시그니처 변경, 상속 변경을 API 호환성 위험 후보로 분류
- 분석 엔진 결과와 표현 계층을 분리한 `report.html` 자동 생성
- 영향 파일 검색, 위험도 배지, 함수 전파 거리, API 변화, Git 동시 수정과 진단을 한 페이지에 구성
- 저장소에서 읽은 문자열을 HTML 이스케이프하고 외부 리소스를 사용하지 않는 단독 보고서

## v0.4에서 추가된 기능

- 조원 프로토타입의 함수·메서드 Call Graph 개념 통합
- 일반 함수, 클래스 생성자, `self.method()`, import alias, `instance.method()` 해석
- 역방향 호출 그래프를 이용한 함수 단위 영향 전파
- 호출 관계를 따라 테스트 함수까지 단계별 추적
- 호출 근거별 신뢰도와 미해석 호출 통계 제공
- 오래된 정규표현식의 `SyntaxWarning`을 화면에 반복 출력하지 않고 JSON에 수집
- 구문 오류가 있는 파일이 있어도 나머지 파일 분석 지속

대형 대화형 그래프는 기본 화면에 넣지 않았습니다. 복잡한 force graph보다 표와 거리 기반 전파 목록이 변경 판단에 더 직접적이며, `call_graph.json`은 별도 시각화 연결을 위해 그대로 제공합니다.

## 검증

```powershell
py -m unittest discover -s tests -v
py impact_cli.py demo_fixture --changed app/models.py --output impact_output_demo
```

테스트는 GitHub URL 정규화, Git 동시 수정 집계, 간접 import 전파, 함수 호출을 통한 테스트 도달, 클래스 인스턴스 메서드 해석, API 호환성 비교, HTML 이스케이프, 경로 이탈 차단, 자동 수정 재시도와 원본 보존을 확인합니다.

## 자동 수정 → 검사 → 재수정

v0.3의 자동 수정 루프도 유지합니다. 실제 AI 서비스 연결 정보는 `README_v03.md`에 있으며 다음 형태로 실행합니다.

```powershell
py run_agent.py --repo target_repo --work repaired_repo `
  --task "수정할 내용" --adapter examples/chat_adapter.py
```

원본 저장소는 수정하지 않고 새 작업 폴더에서 최대 지정 횟수만큼 수정과 검사를 반복합니다.

## 분석 한계

정적 분석이므로 동적 import, pytest fixture 주입, monkeypatch, 콜백, 데코레이터 내부 호출, 다형성에 의해 실행 중 결정되는 메서드는 놓칠 수 있습니다. Git 동시 수정은 경험적 상관관계이며 코드 의존성을 뜻하지 않습니다. 낮은 신뢰도의 `unique_name_heuristic` 결과는 직접 검토해야 합니다.
