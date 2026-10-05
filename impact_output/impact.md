# Sublist3r 분석 보고서

- 입력: `https://github.com/aboul3la/Sublist3r.git`
- Python 파일: 4개 / 코드: 1,310줄
- 클래스: 16개 / 함수·메서드: 99개
- 호출 해석: 87건 / 미해결: 427건
- Git 이력: 사용 가능

## 진입점과 읽기 시작점

|파일|종류|위치|호출|
|---|---|---:|---|
|subbrute/subbrute.py|__main__ guard|553|getattr, os.path.dirname, multiprocessing.freeze_support, os.path.dirname, os.path.realpath, optparse.OptionParser, parser.add_option, os.path.join, parser.add_option, os.path.join, parser.add_option, parser.add_option, parser.add_option, parser.add_option, parser.add_option, parser.add_option, parser.add_option, parser.add_option, parser.parse_args, parser.error, len, extract_subdomains, sys.exit, print, check_open, open, error, open, error, str.upper, str, target.strip, print, print_target|
|sublist3r.py|__main__ guard|1005|interactive|

## 변경 영향 파일

|파일|테스트|근거|함수 후보|
|---|---|---|---|
|subbrute/subbrute.py|False|changed, historical_cochange: sublist3r.py|<module>, check_open, error, extract_hosts, extract_subdomains, killproc, lookup.__init__, lookup.check, lookup.get_ns, lookup.get_ns_blocking, lookup.run, print_target, run, signal_init, trace, verify_nameservers.__init__, verify_nameservers.add_nameserver, verify_nameservers.end, verify_nameservers.find_wildcards, verify_nameservers.run, verify_nameservers.verify|
|sublist3r.py|False|changed, imports_affected_file: subbrute/subbrute.py, historical_cochange: subbrute/subbrute.py|<module>, AskEnum.__init__, AskEnum.extract_domains, AskEnum.generate_query, AskEnum.get_page, BaiduEnum.__init__, BaiduEnum.check_response_errors, BaiduEnum.extract_domains, BaiduEnum.findsubs, BaiduEnum.generate_query, BaiduEnum.should_sleep, BingEnum.__init__, BingEnum.extract_domains, BingEnum.generate_query, CrtSearch.__init__, CrtSearch.enumerate, CrtSearch.extract_domains, CrtSearch.req, DNSdumpster.__init__, DNSdumpster.check_host, DNSdumpster.enumerate, DNSdumpster.extract_domains, DNSdumpster.get_csrftoken, DNSdumpster.req, GoogleEnum.__init__, GoogleEnum.check_response_errors, GoogleEnum.extract_domains, GoogleEnum.generate_query, GoogleEnum.should_sleep, NetcraftEnum.__init__, NetcraftEnum.create_cookies, NetcraftEnum.enumerate, NetcraftEnum.extract_domains, NetcraftEnum.get_cookies, NetcraftEnum.get_next, NetcraftEnum.req, NetcraftEnum.should_sleep, PassiveDNS.__init__, PassiveDNS.enumerate, PassiveDNS.extract_domains, PassiveDNS.req, ThreatCrowd.__init__, ThreatCrowd.enumerate, ThreatCrowd.extract_domains, ThreatCrowd.req, Virustotal.__init__, Virustotal.enumerate, Virustotal.extract_domains, Virustotal.send_req, YahooEnum.__init__, YahooEnum.extract_domains, YahooEnum.generate_query, YahooEnum.get_page, YahooEnum.should_sleep, banner, enumratorBase.__init__, enumratorBase.check_max_pages, enumratorBase.check_max_subdomains, enumratorBase.check_response_errors, enumratorBase.enumerate, enumratorBase.extract_domains, enumratorBase.generate_query, enumratorBase.get_page, enumratorBase.get_response, enumratorBase.print_, enumratorBase.print_banner, enumratorBase.send_req, enumratorBase.should_sleep, enumratorBaseThreaded.__init__, enumratorBaseThreaded.run, interactive, main, no_color, parse_args, parser_error, portscan.__init__, portscan.port_scan, portscan.run, subdomain_sorting_key, write_file|

## 함수 영향 전파

|거리|영향 함수|경유 대상|신뢰도|
|---:|---|---|---|
|1|subbrute/subbrute.py::<module>|subbrute/subbrute.py::print_target|static|
|1|sublist3r.py::main|subbrute/subbrute.py::print_target|static|
|2|sublist3r.py::interactive|sublist3r.py::main|static|
|3|sublist3r.py::<module>|sublist3r.py::interactive|static|

## 테스트 후보

정적으로 연결된 테스트 후보가 없습니다.

## 공개 API

공개 심볼 99개, 문서화된 공개 심볼 7개입니다.

|심각도|심볼|변화|설명|
|---|---|---|---|
|review|sublist3r.py::enumratorBaseThreaded.__init__|signature_changed|매개변수 또는 반환 타입 주석이 변경되었습니다.|

## 미해결 호출 분류

- 동적 객체·속성: 215건
- 외부 라이브러리: 105건
- Python 내장 함수: 99건
- 정의 미확인 이름: 8건

## 분석 한계

- 동적 import, fixture 주입, monkeypatch, 콜백과 런타임 디스패치를 놓칠 수 있습니다.
- Git 동시 수정은 코드 의존성이 아니라 경험적 상관관계입니다.
- 낮은 신뢰도의 이름 기반 호출 추정은 직접 검토해야 합니다.
- 테스트 미검출은 테스트 영향이 없다는 뜻이 아닙니다.
