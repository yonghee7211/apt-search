import streamlit as st
import requests
import pandas as pd
import xml.etree.ElementTree as ET

# 웹페이지 넓게 쓰기 세팅
st.set_page_config(layout="wide")
st.title("전국 아파트 실거래가 정밀 조회 (동별 필터링) 🏠")
st.write("법정동코드 CSV 데이터를 활용하여 전국의 모든 읍/면/동 실거래가를 조회합니다.")

# 직접 제공해주신 인증키
API_KEY = "cb76cc0d703ce4fd87a3359499af7aa653f7698a0db899daa0d7e68882fa5e2a"

# [핵심] 대용량 CSV 파일을 빠르게 읽고 전처리하는 함수 (기억하기 기능 적용)
@st.cache_data
def load_and_process_bjd():
    try:
        # 파일 읽기
        df = pd.read_csv("법정동코드.csv", encoding="cp949")
    except UnicodeDecodeError:
        df = pd.read_csv("법정동코드.csv", encoding="utf-8-sig")
        
    # 현재 존재하는 지역만 남기기
    df = df[df["폐지여부"] == "존재"]
    
    # 법정동 코드를 10자리 문자열로 맞추기
    df["법정동코드"] = df["법정동코드"].astype(str).str.zfill(10)
    
    # 시도, 시군구, 읍면동 분리하는 함수
    def split_bjd_name(name):
        parts = str(name).split()
        sido = parts[0] if len(parts) > 0 else ""
        
        if len(parts) == 2:
            sigungu = parts[1]
            dong = ""
        elif len(parts) == 3:
            sigungu = parts[1]
            dong = parts[2]
        elif len(parts) >= 4:
            sigungu = " ".join(parts[1:-1])
            dong = parts[-1]
        else:
            sigungu, dong = "", ""
        return [sido, sigungu, dong]
    
    # 버전에 관계없이 무조건 작동하도록 한 줄씩 따로 담기
    parsed_data = df["법정동명"].apply(split_bjd_name).tolist()
    df["시도"] = [x[0] for x in parsed_data]
    df["시군구"] = [x[1] for x in parsed_data]
    df["읍면동"] = [x[2] for x in parsed_data]
    
    # 동 정보가 없는 시군구 자체 행은 제외
    df = df[df["읍면동"] != ""]
    return df

# 데이터 로드하기
with st.spinner("전국 법정동 데이터를 구성하는 중입니다... (최초 1회만 실행)"):
    bjd_data = load_and_process_bjd()

# --- 화면에 선택 상자 배치 ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    sido_list = sorted(bjd_data["시도"].unique())
    selected_sido = st.selectbox("1️⃣ 시/도 선택", sido_list)

with col2:
    sigungu_filtered = bjd_data[bjd_data["시도"] == selected_sido]
    sigungu_list = sorted(sigungu_filtered["시군구"].unique())
    selected_sigungu = st.selectbox("2️⃣ 시/군/구 선택", sigungu_list)

with col3:
    dong_filtered = sigungu_filtered[sigungu_filtered["시군구"] == selected_sigungu]
    dong_list = sorted(dong_filtered["읍면동"].unique())
    selected_dong = st.selectbox("3️⃣ 읍/면/동 선택", dong_list)
    
    # 선택된 동이 꼬이거나 비어있을 때를 대비한 안전장치 추가
    lawd_cd = ""
    if selected_dong:
        target_matches = dong_filtered[dong_filtered["읍면동"] == selected_dong]
        if not target_matches.empty:
            target_row = target_matches.iloc[0]
            lawd_cd = target_row["법정동코드"][:5]

with col4:
    deal_ymd = st.text_input("4️⃣ 조회연월 (6자리)", "202605")

st.markdown("---")

# --- 데이터 조회 및 필터링 동작 ---
if st.button("실거래가 데이터 조회하기", type="primary"):
    
    # 안전장치 확인: 지역 코드가 제대로 잡히지 않았다면 조회를 멈춤
    if not lawd_cd:
        st.error("지역 선택이 진행 중이거나 올바르지 않습니다. 지역을 다시 선택해 주세요.")
    else:
        st.info(f"🛰️ {selected_sido} {selected_sigungu} {selected_dong} 데이터를 분석 중입니다...")
        
        # ⚠️ 잘려나갔던 주소를 완벽하게 복구했습니다!
        url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
        
        params = {
            'serviceKey': API_KEY,
            'pageNo': '1',
            'numOfRows': '2000', 
            'LAWD_CD': lawd_cd,
            'DEAL_YMD': deal_ymd
        }
        
        try:
            response = requests.get(url, params=params, verify=False)
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = root.findall('.//item')
                
                if len(items) > 0:
                    raw_data = []
                    for item in items:
                        apt_name = item.find('aptNm').text if item.find('aptNm') is not None else ""
                        price = item.find('dealAmount').text if item.find('dealAmount') is not None else ""
                        area = item.find('excluUseAr').text if item.find('excluUseAr') is not None else ""
                        floor = item.find('floor').text if item.find('floor') is not None else ""
                        dong = item.find('umdNm').text if item.find('umdNm') is not None else ""
                        day = item.find('dealDay').text if item.find('dealDay') is not None else ""
                        
                        raw_data.append({
                            "법정동": dong.strip(),
                            "아파트명": apt_name.strip(),
                            "전용면적(㎡)": area.strip(),
                            "층": floor.strip(),
                            "계약일": f"{day.strip()}일",
                            "거래금액(만원)": price.strip()
                        })
                    
                    df_all = pd.DataFrame(raw_data)
                    df_filtered = df_all[df_all["법정동"] == selected_dong]
                    
                    if not df_filtered.empty:
                        st.dataframe(df_filtered, use_container_width=True)
                        st.success(f"🎯 [{selected_dong}] 지역 총 {len(df_filtered)}건의 실거래 내역을 찾았습니다!")
                    else:
                        st.warning(f"⚠️ {selected_sigungu} 전체에는 거래가 있으나, 선택하신 [{selected_dong}]에는 해당 월의 매매 거래가 없습니다.")
                else:
                    st.warning("이 지역 및 연월에는 아파트 매매 거래 데이터가 존재하지 않습니다.")
            else:
                st.error(f"서버 접속 실패 (코드: {response.status_code})")
                
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")