# Python Repository Analyzer v0.3

기존 v0.2.1 구조 분석 기능을 유지하면서 변경 이력, 테스트 연결, 영향 후보 분석 및 제한된 자동 수정 루프를 추가했습니다. Python 3.10 이상과 Git이 필요합니다. 추가 Python 패키지는 없습니다.

## 1. 변경 영향 분석 (PowerShell)

전체 이력이 있는 로컬 저장소를 사용하세요. 기존 main.py의 clone은 이력 분석에 충분하지 않을 수 있습니다. 원격 저장소는 먼저 직접 clone합니다.

```powershell
git clone https://github.com/dbader/schedule.git target_repo
py impact_cli.py target_repo --changed schedule/__init__.py --output impact_output
# 특정 커밋 이후 HEAD까지의 변경 파일을 자동 선택
py impact_cli.py target_repo --base HEAD~1 --output impact_output
```

`--changed`는 저장소 루트 기준 경로입니다. `--base`는 커밋된 HEAD와 비교하며 미커밋 변경은 포함하지 않습니다. 기본 최대 500개의 비병합 커밋을 분석하며 `--commits 1000`처럼 조절할 수 있습니다. Python 파일 30개를 초과하는 대규모 커밋은 통계 왜곡을 줄이기 위해 제외합니다. 삭제 파일도 기록하지만 이름 변경의 이력 통합은 지원하지 않습니다.

- impact.json: 기존 구조, import 연결, 동시 수정 횟수/Jaccard, 변경 영향 후보, 테스트 후보 및 근거
- impact.md: 간단한 표 보고서
- Git이 없으면 구조 분석만 진행하고 이력 없음 표시
- 얕은 clone이면 shallow 표시; 전체 이력이 필요하면 `git fetch --unshallow`

영향 분석은 변경 파일을 import하는 파일을 역방향으로 추적합니다. 직접/간접 import로 연결되는 테스트를 후보로 제시합니다. 두 번 이상 함께 수정된 파일은 별도의 상관관계 근거로 추가합니다. 역사적 상관관계를 구조적 의존성으로 취급하지 않습니다.

**함수 수준 전파를 입증한 것은 아닙니다.** 영향 후보 파일의 함수 목록을 제공합니다. 동적 import, pytest fixture/conftest, monkeypatch, 객체 메서드 dispatch, 외부 의존성은 누락될 수 있습니다. 테스트 미검출은 영향 없음의 증거가 아닙니다. src 레이아웃과 상대 import를 일부 지원하지만 모든 프로젝트의 실행 경로 설정을 재현하지는 않습니다.

## 2. 자동 수정 → 빌드/테스트 → 재수정

`agent.py`는 원본을 별도의 새 폴더에 복사하고 어댑터를 실행합니다. 어댑터는 stdin의 작업·Python 소스·직전 실패 로그를 받아 stdout으로 JSON 전체 파일 교체안을 반환합니다. 사용자 지정 검사 명령들을 실행하고 실패하면 다음 시도로 전달합니다. 기본 3회, 최대 10회이며 명령별 제한시간이 있습니다. 원본에 자동 병합하거나 push하지 않습니다. 결과와 시도별 로그는 작업 폴더의 agent_log.json에 저장됩니다.

### 실제 AI 연결

`examples/chat_adapter.py`는 chat-completions 호환 HTTP 응답 형식(`choices[0].message.content`)을 사용하는 선택형 어댑터입니다. 본인이 사용하는 서비스의 전체 endpoint URL, 모델명, 키를 설정하세요. 모델 호출 비용은 해당 서비스에 따릅니다. **실제 외부 모델 호출은 이 배포본 검증에서 수행하지 않았습니다.** 공급자별 응답 형식이 다르면 어댑터를 변경해야 합니다.

```powershell
$env:AGENT_CHAT_URL = '서비스의 전체 chat completions URL'
$env:AGENT_CHAT_MODEL = '모델명'
$env:AGENT_CHAT_KEY = '본인 API 키'
# 아래 예시는 PowerShell 인자 인용 문제를 피하려고 Python 실행 래퍼를 사용합니다.
py run_agent.py --repo target_repo --work repaired_repo --task '오류 설명과 원하는 동작' --adapter examples/chat_adapter.py
```

래퍼의 기본 검사는 `python -m compileall -q .`와 `python -m unittest discover`입니다. pytest 저장소라면 `--pytest`를 추가하고 현재 Python 환경에 프로젝트 의존성과 pytest를 설치하세요. compileall은 빌드 대용 구문 검사이며 프로젝트별 실제 빌드가 필요하면 `agent.py --checks`에 argv 배열로 설정하세요. 테스트 없는 프로젝트에서 unittest 성공은 검증 근거가 부족하므로 프로젝트의 실제 검사를 지정해야 합니다.

어댑터는 Python 소스와 실패 로그를 외부 모델로 전송합니다. 민감 소스에 적용하기 전 범위를 확인하세요. `.env`, `.git`, 가상환경은 복사 대상에서 제외하지만 소스 안의 비밀까지 탐지하지는 않습니다. 작업 복사본은 보안 샌드박스가 아닙니다. 검사 대상 코드는 로컬 권한으로 실행되므로 신뢰하는 저장소에서 사용하세요. 큰 저장소에서는 입력량을 줄이는 별도 어댑터가 필요할 수 있습니다.

### 모델 없이 재현 검증

```powershell
py -m unittest discover -s tests -v
py impact_cli.py demo_fixture --changed app/services/user_service.py --output impact_output
```

3개 테스트로 Git 동시 수정과 테스트까지의 간접 import 전파, 경로 이탈 거부, 첫 검사 실패 → 로그 피드백 → 두 번째 수정 성공 및 원본 보존을 확인했습니다. 테스트의 수정기는 결정적 mock이며 AI 성능 평가가 아닙니다. `examples/demo_adapter.py` 역시 calc.py 덧셈 버그만 교체하는 프로토콜 예제입니다.
