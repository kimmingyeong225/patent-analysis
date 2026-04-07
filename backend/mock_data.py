# mock_data.py
# 역할: 백엔드 완성 전 프론트엔드 개발용 Mock 데이터

MOCK_SEARCH_RESPONSE = {
    "query": "자가 충전형 스마트 워치 스트랩",
    "cached": False,
    "results": [
        {
            "rank": 1,
            "similarity_score": 0.91,
            "공개등록공보": {
                "patent_id": "KR1020230012345",
                "application_number": "10-2022-0098765",
                "title": "태양광 패널 내장형 스마트워치 스트랩 및 그 제조방법",
                "applicant": "삼성전자주식회사",
                "inventor": "홍길동, 김철수",
                "application_date": "2022-08-03",
                "publication_date": "2023-02-14",
                "registration_date": None,
                "abstract": "본 발명은 스마트워치 스트랩 내부에 유연성 태양광 패널을 내장하여 착용 중 자가 충전이 가능하도록 하는 기술에 관한 것이다.",
                "claims": [
                    "청구항 1: 유연성 태양광 패널을 포함하는 스마트워치 스트랩",
                    "청구항 2: 제1항에 있어서, 상기 패널이 실리콘 소재로 밀봉된 스트랩"
                ],
                "doc_type": "공개"
            },
            "인용문헌": {
                "cited_by_count": 3,
                "citing_count": 5,
                "cited_patents": ["KR1020190045678", "US10236701B2", "JP2021032156A"]
            },
            "법적상태": {
                "status": "심사중",
                "status_code": "R0040",
                "last_event": "출원심사청구",
                "last_event_date": "2022-09-01",
                "is_alive": True
            },
            "분류코드": {
                "ipc": [
                    {"code": "H02J 7/35", "desc": "태양광 에너지를 이용한 충전 장치"},
                    {"code": "G04G 17/00", "desc": "전자 시계의 전원 공급 장치"}
                ],
                "cpc": [
                    {"code": "H02J 7/35", "desc": "태양광 충전"},
                    {"code": "A44C 5/14", "desc": "시계줄"}
                ]
            }
        },
        {
            "rank": 2,
            "similarity_score": 0.75,
            "공개등록공보": {
                "patent_id": "KR1020210056789",
                "application_number": "10-2020-0112233",
                "title": "압전 소자를 이용한 운동에너지 수확 웨어러블 장치",
                "applicant": "엘지전자주식회사",
                "inventor": "이영희",
                "application_date": "2020-09-15",
                "publication_date": "2021-05-20",
                "registration_date": "2022-03-11",
                "abstract": "착용자의 움직임에서 발생하는 운동 에너지를 압전 소자로 변환하여 배터리를 충전하는 웨어러블 기기.",
                "claims": [
                    "청구항 1: 압전 소자를 포함하는 웨어러블 충전 장치",
                    "청구항 2: 에너지 변환 효율을 높이기 위한 공진 구조"
                ],
                "doc_type": "등록"
            },
            "인용문헌": {
                "cited_by_count": 8,
                "citing_count": 2,
                "cited_patents": ["KR1020180033445", "US9831723B2"]
            },
            "법적상태": {
                "status": "등록",
                "status_code": "R0060",
                "last_event": "등록결정",
                "last_event_date": "2022-03-11",
                "is_alive": True
            },
            "분류코드": {
                "ipc": [
                    {"code": "H02N 2/18", "desc": "압전 효과를 이용한 전기 기계 변환"},
                    {"code": "H04R 17/00", "desc": "압전형 트랜스듀서"}
                ],
                "cpc": [
                    {"code": "H02N 2/181", "desc": "압전 에너지 하베스팅"}
                ]
            }
        },
        {
            "rank": 3,
            "similarity_score": 0.68,
            "공개등록공보": {
                "patent_id": "KR1020220087654",
                "application_number": "10-2021-0145678",
                "title": "체온 차이를 이용한 열전 발전 스마트밴드",
                "applicant": "카이스트",
                "inventor": "박민준, 최수진",
                "application_date": "2021-11-10",
                "publication_date": "2022-06-20",
                "registration_date": "2023-01-05",
                "abstract": "착용자의 체온과 외부 온도의 차이를 열전 발전 소자로 변환하여 전력을 생산하는 밴드.",
                "claims": [
                    "청구항 1: 열전 발전 소자를 내장한 스마트밴드",
                    "청구항 2: 효율적인 열 전달을 위한 방열 구조"
                ],
                "doc_type": "등록"
            },
            "인용문헌": {
                "cited_by_count": 1,
                "citing_count": 0,
                "cited_patents": ["KR1020170011223"]
            },
            "법적상태": {
                "status": "등록",
                "status_code": "R0060",
                "last_event": "등록결정",
                "last_event_date": "2023-01-05",
                "is_alive": True
            },
            "분류코드": {
                "ipc": [
                    {"code": "H10N 10/00", "desc": "열전 소자"},
                    {"code": "A61B 5/00", "desc": "인체 측정 웨어러블"}
                ],
                "cpc": [
                    {"code": "H02S 10/30", "desc": "열전 시스템과 결합된 전력 생산"}
                ]
            }
        }
    ]
}
