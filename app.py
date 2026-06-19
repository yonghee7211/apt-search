import streamlit as st
import requests
import pandas as pd
import xml.etree.ElementTree as ET

# 웹페이지 넓게 쓰기 세팅
st.set_page_config(layout="wide")
st.title("전국 아파트 실거래가 정밀 조회 (동별 필터링) 🏠")
st.write("법정동코드 CSV 데이터를 활용하여 전국의 모든 읍/면/동 실거래가를 조회합니다.")

API_KEY = "cb76cc0d703ce4fd87a3359499af7aa653f7698a0db899daa0d7e68882fa5e2a"

# 데이터 전처리 함수
@st.cache_data
def load_and_process_bjd():
    try:
        df = pd.read_csv("법정동코드.csv", encoding="cp949", dtype=str)
    except:
        df = pd.read_csv("법정동코드.csv", encoding="utf-8", dtype=str)
        
    if "폐지여부" in df.columns:
        df = df[df["폐지여부"].str.lower().isin(["존재", "exst"])]
        
    df["법정동코드"] = df["법정동코드"].astype(str).str.zfill(10)
    
    def split_bjd_name(name):
        parts = str(name).split()
        sido = parts[0] if len(parts) > 0 else ""
        if len(parts) == 2:
            sigungu, dong = parts[1], ""
        elif len(parts) == 3:
            sigungu, dong = parts[1], parts[2]
        elif len(parts) >= 4:
            sigungu = " ".join(parts[1:-1])
            dong = parts[-1]
        else:
            sigungu, dong = "", ""
        return [sido, sigungu, dong]
        
    parsed_data = df["법정동명"].apply(split_bjd_name).tolist()
    df["시도"] = [x[0] for x in parsed_data]
    df["시군구"] = [x[1] for x in parsed_data]
    df["읍면동"] = [x[2] for x in parsed_data]
    
    df = df[df["읍면동"] != ""]
    return df

# 데이터 로드
with st.spinner("전국 법정동 데이터를 분석하고 있습니다... 잠시만 기다려주세요."):
    bjd_data = load_and_process_bjd()

if bjd_data.empty:
    st.error("🚨 데이터를 불러오지 못했습니다. 파일 이름을 다시 한번 확인해 주세요.")
else:
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
        
        # 🚀 핵심: 동 목록 맨 앞에 '전체' 옵션을 추가합니다.
        dong_list = ["전체"] + sorted(dong_filtered["읍면동"].unique())
        selected_dong = st.selectbox("3️⃣ 읍/면/동 선택", dong_list)
        
        lawd_cd = ""
        if selected_dong:
            if selected_dong == "전체":
                # '전체'를 선택한 경우, 해당 구의 아무 동이나 하나 잡아서 앞 5자리 코드(구 코드)를 가져옵니다.
                if not dong_filtered.empty:
                    lawd_cd = dong_filtered.iloc[0]["법정동코드"][:5]
            else:
                target_matches = dong_filtered[dong_filtered["읍면동"] == selected_dong]
                if not target_matches.empty:
                    target_row = target_matches.iloc[0]
                    lawd_cd = target_row["법정동코드"][:5]

    with col4:
        deal_ymd = st.text_input("4️⃣ 조회연월 (6자리)", "202605")

    st.markdown("---")

    # --- 데이터 조회 및 필터링 동작 ---
    if st.button("실거래가 데이터 조회하기", type="primary"):
        if not lawd_cd:
            st.error("지역을 정확히 선택해 주세요.")
        else:
            # 상태 표시 문구도 '전체'일 때 자연스럽게 나오도록 수정
            display_name = selected_sigungu if selected_dong == "전체" else selected_dong
            st.info(f"🛰️ {selected_sido} {selected_sigungu} {selected_dong} 데이터를 분석 중입니다...")
            
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
                        
                        # 🚀 핵심: '전체'를 선택했으면 솎아내지 않고 전부 다 보여줍니다.
                        if selected_dong == "전체":
                            df_filtered = df_all
                        else:
                            df_filtered = df_all[df_all["법정동"] == selected_dong]
                        
                        if not df_filtered.empty:
                            st.dataframe(df_filtered, use_container_width=True)
                            
                            if selected_dong == "전체":
                                st.success(f"🎯 [{selected_sigungu} 전체] 지역 총 {len(df_filtered)}건의 실거래 내역을 찾았습니다!")
                            else:
                                st.success(f"🎯 [{selected_dong}] 지역 총 {len(df_filtered)}건의 실거래 내역을 찾았습니다!")
                        else:
                            st.warning(f"⚠️ 선택하신 [{display_name}] 지역에는 해당 월의 매매 거래가 없습니다.")
                    else:
                        st.warning("이 지역 및 연월에는 아파트 매매 거래 데이터가 존재하지 않습니다.")
                else:
                    st.error(f"서버 접속 실패 (코드: {response.status_code})")
                    
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")