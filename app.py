import streamlit as st
import yfinance as yf
from pycoingecko import CoinGeckoAPI
import pandas as pd
import google.generativeai as genai
from datetime import datetime, timedelta

st.set_page_config(page_title="MSTR Robo-Advisor", layout="wide")
st.title("📊 MicroStrategy (MSTR) Robo-Advisor")
st.write("監測 MSTR 淨資產價值 (NAV) 溢價與比特幣關聯性")

# --- 初始化 Session State (記憶使用者的 API Key) ---
if 'user_api_key' not in st.session_state:
    st.session_state['user_api_key'] = ''

# --- 側邊欄設定區 ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 使用 st.form 建立表單，這樣就會有專屬的按鈕，且支援鍵盤 Enter 送出
    with st.form(key='api_key_form'):
        input_key = st.text_input(
            "輸入 Gemini API Key", 
            value=st.session_state['user_api_key'], 
            type="password", 
            help="若要使用 AI 分析功能請輸入此 Key"
        )
        # 實體的「登錄」按鈕
        submit_button = st.form_submit_button(label='登錄 / Enter')
        
    # 當按下按鈕或按 Enter 時，將輸入的 Key 存入記憶中
    if submit_button:
        st.session_state['user_api_key'] = input_key
        
    # 顯示狀態提示
    if st.session_state['user_api_key']:
        st.success("✅ API Key 已登錄！")
    else:
        st.warning("👈 請在此輸入 API Key 以解鎖 AI 洞察功能")
    
    st.markdown("[點此免費申請 Gemini API Key](https://aistudio.google.com/)")

# --- 時間範圍選擇 UI ---
timeframe_map = {
    "1 個月": 30,
    "6 個月": 180,
    "1 年": 365
}
selected_timeframe = st.radio("選擇時間範圍：", list(timeframe_map.keys()), horizontal=True)
days_to_fetch = timeframe_map[selected_timeframe]

# --- 資料收集函數 ---
@st.cache_data(ttl=3600)
def fetch_data(days):
    cg = CoinGeckoAPI()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    mstr = yf.Ticker("MSTR").history(start=start_date, end=end_date)
    df_mstr = mstr[['Close']].reset_index()
    df_mstr['Date'] = df_mstr['Date'].dt.tz_localize(None).dt.normalize()
    
    btc_data = cg.get_coin_market_chart_by_id(id='bitcoin', vs_currency='usd', days=days)
    df_btc = pd.DataFrame(btc_data['prices'], columns=['Timestamp', 'BTC_Price'])
    df_btc['Date'] = pd.to_datetime(df_btc['Timestamp'], unit='ms').dt.normalize()
    df_btc = df_btc.groupby('Date').last().reset_index()

    holdings = 766970  
    shares_outstanding = 277620000 

    df = pd.merge(df_mstr, df_btc, on='Date', how='left')
    df['NAV'] = (holdings * df['BTC_Price']) / shares_outstanding
    df['Premium_Pct'] = ((df['Close'] - df['NAV']) / df['NAV']) * 100
    
    return df.dropna()

# --- 執行與顯示 ---
try:
    data = fetch_data(days_to_fetch)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"MSTR Premium to NAV ({selected_timeframe}) 趨勢圖")
        # 改用更穩定的繪圖語法，明確指定 X 與 Y 軸，解決圖表空白問題
        st.line_chart(data, x='Date', y='Premium_Pct')
        
        st.subheader("數據預覽")
        st.dataframe(data.tail(10))

    with col2:
        st.subheader("🤖 AI 投資洞察")
        if st.button("產生 AI 分析報告"):
            
            # 從 session_state 讀取剛剛登錄的 Key
            current_key = st.session_state['user_api_key']
            
            if not current_key:
                st.error("❌ 請先在左側邊欄輸入你的 Gemini API Key 並按下登錄！")
            else:
                try:
                    genai.configure(api_key=current_key)
                    # ★ 已經修正回你成功執行過的模型名稱
                    model = genai.GenerativeModel('gemini-flash-latest')
                    
                    recent_data = data.tail(5).to_string()
                    prompt = f"你是一個專業的加密貨幣分析師。以下是 MSTR 過去五天的數據：\n{recent_data}\n請根據溢價(Premium_Pct)趨勢，提供繁體中文的簡短市場總結與警示。"
                    
                    with st.spinner('AI 思考中...'):
                        response = model.generate_content(prompt)
                        st.info(response.text)
                except Exception as e:
                    st.error(f"❌ AI 分析失敗：請確認 API Key 是否正確且有效。\n錯誤訊息：{e}")

except Exception as e:
    st.error(f"資料抓取失敗: {e}")