import streamlit as st
import requests
import pandas as pd
import xml.etree.ElementTree as ET

# 1. 지역 선택을 위한 딕셔너리 구성 (주요 시/도 및 시/군/구)
REGIONS = {
    "서울특별시": {
        "영등포구": "11560", "강남구": "11680", "서초구": "11650", "송파구": "11710", "용산구": "11170", 
        "마포구": "11440", "성동구": "11200", "광진구": "11215", "동대문구": "11230", "중랑구": "11260", 
        "성북구": "11290", "강북구": "11305", "도봉구": "11320", "노원구": "11350", "은평구": "11380", 
        "서대문구": "11410", "양천구": "11470", "강서구": "11500", "구로구": "11530", "금천구": "11545", 
        "동작구": "11590", "관악구": "11620", "강동구": "11740", "종로구": "11110", "중구": "11140"
    },
    "대구광역시": {
        "중구": "27110", "동구": "27140", "서구": "27170", "남구": "27200", "북구": "27230",
        "수성구": "27260", "달서구": "27290", "달성군": "27710", "군위군": "27720"
    },
    "부산광역시": {
        "해운대구": "26350", "수영구": "26500", "동래구": "26260", "연제구": "26470", "남구": "26290",
        "진구": "26230", "북구": "26320", "사하구": "26380", "금정구": "26410", "강서구": "26440",
        "기장군": "26710", "동구": "26170", "서구": "26140", "사상구": "26530", "영도구": "26200", "중구": "26110"
    },
    "인천광역시": {
        "연수구": "28185", "서구": "28260", "남동구": "28200", "부평구": "28237", "계양구": "28245",
        "미추홀구": "28177", "동구": "28140", "중구": "28110", "강화군": "28710", "옹진군": "28720"
    },
    "경기도(일부)": {
        "성남분당구": "41135", "수원영통구": "41117", "안양동안구": "41173", "과천시": "41290",
        "광명시": "41210", "하남시": "41450", "용인수지구": "41465", "고양일산동구": "41285",
        "김포시": "41570", "화성시": "41590", "부천시": "41190", "평택시": "41220", "시흥시": "41390"
    }
}

# 2. 웹페이지 기본 설정
st.set_page_config(layout="wide")
st.title("전국 아파트 실거래가 조회 🏠")
st.write("지역을 선택하고 원하는 달의 거래 내역을 확인해 보세요.")

# 3. 직접 제공해주신 인증키 적용
API_KEY = "cb76cc0d703ce4fd87a3359499af7aa653f7698a0db899daa0d7e68882fa5e2a"

# 4. 화면을 3칸으로 나누어 입력 위젯 배치
col1, col2, col3 = st.columns(3)

with col1:
    sido = st.selectbox("1️⃣ 시/도 선택", list(REGIONS.keys()))
with col2:
    sigungu = st.selectbox("2️⃣ 시/군/구 선택", list(REGIONS[sido].keys()))
    lawd_cd = REGIONS[sido][sigungu]
with col3:
    deal_ymd = st.text_input("3️⃣ 조회연월 (예: 202605)", "202605")

st.markdown("---")

# 5. 조회 버튼 눌렀을 때의 동작
if st.button("데이터 조회하기", type="primary"):
    st.info(f"{sido} {sigungu} 데이터를 불러오는 중입니다. 잠시만 기다려주세요...")
    
    url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
    
    params = {
        'serviceKey': API_KEY,
        'pageNo': '1',
        'numOfRows': '100',
        'LAWD_CD': lawd_cd,
        'DEAL_YMD': deal_ymd
    }
    
    try:
        response = requests.get(url, params=params, verify=False) 
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # [수정됨] 데이터(item)가 있는지 가장 먼저 확인하도록 변경
            items = root.findall('.//item')
            
            if len(items) > 0:
                data = []
                for item in items:
                    apt_name = item.find('aptNm').text if item.find('aptNm') is not None else ""
                    price = item.find('dealAmount').text if item.find('dealAmount') is not None else ""
                    area = item.find('excluUseAr').text if item.find('excluUseAr') is not None else ""
                    floor = item.find('floor').text if item.find('floor') is not None else ""
                    dong = item.find('umdNm').text if item.find('umdNm') is not None else ""
                    day = item.find('dealDay').text if item.find('dealDay') is not None else ""
                    
                    data.append({
                        "법정동": dong,
                        "아파트명": apt_name,
                        "전용면적(㎡)": area,
                        "층": floor,
                        "계약일": f"{day}일",
                        "거래금액(만원)": price.strip()
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
                st.success(f"성공적으로 {len(data)}건의 데이터를 가져왔습니다!")
                
            else:
                # 데이터가 없는 경우 (API는 정상 작동했지만 해당 달에 거래가 0건일 때)
                result_msg = root.find('.//resultMsg')
                msg = result_msg.text.strip().lower() if result_msg is not None else ""
                
                if msg in ['ok', 'normal service.', '정상']:
                    st.warning("해당 조건(지역/연월)에 아파트 매매 거래 데이터가 아직 없거나 등록되지 않았습니다.")
                else:
                    st.error(f"서버 응답 오류 (사유: {msg})")
                    
        else:
            st.error(f"서버 접속 오류가 발생했습니다. (상태 코드: {response.status_code})")
            
    except Exception as e:
        st.error(f"실행 중 문제가 발생했습니다: {e}")