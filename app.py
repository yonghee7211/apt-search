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
    
    # 🚀 [에러 해결 부분] 최신 판다스 버전에 맞춰 안전하게 3개의 컬럼으로 분리하여 할당
    parsed_data = df["법정동명"].apply(split_bjd_name).tolist()
    df[["시도", "시군구", "읍면동"]] = pd.DataFrame(parsed_data, index=df.index)
    
    # 동 정보가 없는 시군구 자체 행은 제외
    df = df[df["읍면동"] != ""]
    return df