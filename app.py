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

# [핵심] 대용량 CSV 파일을 깨짐 없이 안전하게 읽어오는 함수
@st.cache_data
def load_and_process_bjd():
    df = None
    # 에러를 엄격하게 잡아내는 utf-8 규격들을 먼저 시도합니다.
    encodings = ["utf-8", "utf-8-sig", "cp949", "euc-kr"]
    
    for enc in encodings:
        try:
            test_df = pd.read_csv("법정동코드.csv", encoding=enc)
            # 글자가 깨지지 않고 정상적으로 '법정동코드' 컬럼이 읽혔는지 검사
            if "법정동코드" in test_df.columns:
                df = test_df
                break
        except:
            continue
            
    # 파일 읽기에 완전히 실패했거나 컬럼명이 다를 때의 예외 처리
    if df is None:
        st.error("🚨 '법정동코드.csv' 파일을 읽지 못했거나 한글 인코딩이 맞지 않습니다. 파일 상태를 확인해 주세요.")
        return pd.DataFrame(columns=["시도", "시군구", "읍면동", "법정동코드"])
        
    # '폐지여부' 컬럼이 존재하는 경우에만 '존재'하는 지역 필터링 (컬럼명 불일치 방지)
    if "폐지여부" in df.columns:
        df = df[df["폐지여부"] == "존재"]
    
    # 법정동 코드를 10자리 문자열로 안전하게 맞추기
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
    
    # 안전하게 한 줄씩 분리하여 새 컬럼 생성
    parsed_data = df["법정동명"].apply(split_bjd_name).tolist()
    df["시도"] = [x[0] for x in parsed_data]
    df["시군구"] = [x[1] for x in parsed_data]
    df["읍면동"] = [x[2] for x in parsed_data]
    
    # 구 단위 자체 행을 제외하고 실제 '동' 정보가 있는 행만 추출
    df = df[df["읍면동"] != ""]
    return df

# 데이터 로드하기
with st.spinner("전국 법정동 데이터를 분석하고 있습니다... 잠시만 기다려주세요."):
    bjd_data = load_and_process_bjd()

# 만약 데이터가 비어있다면 화면 비활성화 및 경고창 안내
if bjd_data.empty:
    st.warning("⚠️ 법정동 데이터를 불러오지 못했습니다. CSV 파일의 컬럼명(법정동코드, 법정동명, 폐지여부)을 확인해 주세요.")
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
        dong_list = sorted(dong_filtered["읍면동"].unique())
        selected_dong = st.selectbox("3️⃣ 읍/면/동 선택", dong_list)
        
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
        if not lawd_cd:
            st.error("지역 선택이 진행 중이거나 올바르지 않습니다. 지역을 다시 선택해 주세요.")
        else:
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