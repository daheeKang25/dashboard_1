import streamlit as st
import pandas as pd
import time
import numpy as np
import plotly.graph_objects as go

# 1. 페이지 설정 (이모지 제거, 와이드 레이아웃 유지)
st.set_page_config(page_title="연료전지 예지보전 시스템", layout="wide")

# CSS를 통한 산업용 UI 커스텀 (여백 최소화, 카드형 디자인)
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    .sensor-box {
        background-color: #303030FF; border: 1px solid #333; 
        border-radius: 4px; padding: 10px; margin-bottom: 10px;
    }
    .sensor-title { font-size: 16px; color: #FFFFFF; margin-bottom: 2px; }
    .sensor-value { font-size: 20px; font-weight: 600; color: #00E676; }
    .log-box {
        background-color: #1A1A1A; border-left: 3px solid #FF1744;
        padding: 8px; margin-bottom: 5px; font-size: 13px; color: #FF8A80;
    }
    h1, h2, h3 { color: #E0E0E0; }
    </style>
""", unsafe_allow_html=True)

# 2. 데이터 로드 함수
@st.cache_data
def load_data(scenario):
    if scenario == "정상 운전 (FC1)":
        return pd.read_csv('./data/FC1_Cleaned_1Hz.csv')
    else:
        return pd.read_csv('./data/FC2_Cleaned_1Hz.csv')

# 3. 세션 상태 초기화 (알람 로그 배열 추가)
if 'current_index' not in st.session_state: st.session_state.current_index = 0
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'scenario' not in st.session_state: st.session_state.scenario = "정상 운전 (FC1)"
if 'alarm_log' not in st.session_state: st.session_state.alarm_log = []

# 4. 사이드바 (통신 제어부 최소화)
with st.sidebar:
    st.title("데이터 전송 제어부")
    selected_scenario = st.selectbox("시나리오 선택", ["정상 운전 (FC1)", "가속 열화 (FC2)"], 
                                     index=0 if st.session_state.scenario == "정상 운전 (FC1)" else 1)
    
    if selected_scenario != st.session_state.scenario:
        st.session_state.scenario = selected_scenario
        st.session_state.current_index = 0
        st.session_state.is_running = False
        st.session_state.alarm_log = []

    df = load_data(st.session_state.scenario)
    total_rows = len(df)

    col1, col2 = st.columns(2)
    if col1.button("▶ 전송 시작"): st.session_state.is_running = True
    if col2.button("⏸ 전송 정지"): st.session_state.is_running = False
    
    st.markdown("---")
    
    status_html = "<span style='color:#00FF00;'>연결됨 (송신 중)</span>" if st.session_state.is_running else "<span style='color:#FFA500;'>대기 (송신 중지)</span>"
    st.markdown(f"**통신 상태:** {status_html}", unsafe_allow_html=True)
    st.write(f"**전송 건수:** {st.session_state.current_index} / {total_rows}")
    
    st.session_state.current_index = st.slider("시점 이동 (Time Index)", 0, total_rows - 1, st.session_state.current_index)

# 5. 메인 레이아웃 분할 (비율 2:6:2)
st.title("수소발전소 연료전지(PEMFC) 실시간 모니터링")

if st.session_state.current_index < total_rows:
    latest_row = df.iloc[st.session_state.current_index]
    
    # 상태 판정 로직 (현재 시나리오의 첫 행 기준으로 다시 고정)
    utot_ref = df.iloc[0]['Utot']
    
    current_utot = latest_row['Utot']
    voltage_drop_ratio = (utot_ref - current_utot) / utot_ref
    
    cell_voltages = [latest_row['U1'], latest_row['U2'], latest_row['U3'], latest_row['U4'], latest_row['U5']]
    cell_std = np.std(cell_voltages)
    
    is_anomaly = False
    if voltage_drop_ratio > 0.0040:  # 하락률 임계값 설정
        is_anomaly = True
        msg = f"스택 전압 강하 ({voltage_drop_ratio*100:.1f}%)"
        if msg not in [log.split("] ")[-1] for log in st.session_state.alarm_log]:
            st.session_state.alarm_log.insert(0, f"[{latest_row['Time']:.1f}h] {msg}")
            
    if cell_std > 0.05:
        is_anomaly = True
        msg = f"셀 전압 불균형 (표준편차: {cell_std:.3f})"
        if msg not in [log.split("] ")[-1] for log in st.session_state.alarm_log]:
            st.session_state.alarm_log.insert(0, f"[{latest_row['Time']:.1f}h] {msg}")
    
    # 알람 로그 최대 10개 유지
    st.session_state.alarm_log = st.session_state.alarm_log[:10]

    # --- 3단 그리드 구성 ---
    col_kpi, col_charts, col_bop = st.columns([2, 6, 2])
    
    # 좌측: 핵심 KPI (HTML/CSS 카드 렌더링)
    with col_kpi:
        st.subheader("운전 지표")
        def metric_card(title, value, unit="", color="#00E676"):
            st.markdown(f"""
            <div class="sensor-box">
                <div class="sensor-title">{title}</div>
                <div class="sensor-value" style="color:{color};">{value} {unit}</div>
            </div>
            """, unsafe_allow_html=True)
            
        metric_card("노화 진행 시간 (Time)", f"{latest_row['Time']:.1f}", "h")
        metric_card("스택 총 전압 (Utot)", f"{latest_row['Utot']:.3f}", "V")
        
        # 임계값 접근 시 색상 변화 로직 추가
        drop_color = "#FF1744" if voltage_drop_ratio > 0.10 else ("#FFA500" if voltage_drop_ratio > 0.05 else "#00E676")
        metric_card("전압 강하율 (Drop)", f"{voltage_drop_ratio*100:.2f}", "%", color=drop_color)
        
        std_color = "#FF1744" if cell_std > 0.05 else ("#FFA500" if cell_std > 0.03 else "#00E676")
        metric_card("셀 전압 편차 (Std)", f"{cell_std:.4f}", "V", color=std_color)
        
        # 시스템 상태 표시등
        st.markdown("<br>", unsafe_allow_html=True)
        if is_anomaly:
            st.markdown("### 설비 상태: <span style='color:#FF1744;'>이상 발생 (FAULT)</span>", unsafe_allow_html=True)
        else:
            st.markdown("### 설비 상태: <span style='color:#00E676;'>정상 운전 (NORMAL)</span>", unsafe_allow_html=True)

    # 중앙: Plotly를 활용한 실시간 차트
    with col_charts:
        window_size = 60 # 60초(1분) 간격 차트
        start_idx = max(0, st.session_state.current_index - window_size)
        chart_data = df.iloc[start_idx : st.session_state.current_index + 1]
        
        # 1. 셀 전압 차트 (Plotly)
        fig_cell = go.Figure()
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        for idx, col in enumerate(['U1', 'U2', 'U3', 'U4', 'U5']):
            fig_cell.add_trace(go.Scatter(x=chart_data['Time'], y=chart_data[col], mode='lines', name=col, line=dict(width=2, color=colors[idx])))
        
        fig_cell.update_layout(
            title="개별 셀 전압 실시간 추세",
            template="plotly_dark", height=250, margin=dict(l=10, r=10, t=30, b=10),
            xaxis_title="시간 (h)", yaxis_title="전압 (V)"
        )
        st.plotly_chart(fig_cell, use_container_width=True)
        
        # 2. Utot 장기 열화 차트 (이상 발생 시 빨간색으로 변경)
        utot_line_color = '#FF1744' if is_anomaly else '#00E676'
        
        fig_utot = go.Figure()
        fig_utot.add_trace(go.Scatter(
            x=df.iloc[:st.session_state.current_index + 1]['Time'], 
            y=df.iloc[:st.session_state.current_index + 1]['Utot'], 
            mode='lines', 
            line=dict(color=utot_line_color, width=2)
        ))
        
        fig_utot.update_layout(
            title="스택 총 전압 (Utot) 장기 열화 추세",
            template="plotly_dark", height=250, margin=dict(l=10, r=10, t=30, b=10),
            xaxis_title="시간 (h)", yaxis_title="전압 (V)"
        )
        st.plotly_chart(fig_utot, use_container_width=True)

    # 우측: BOP 환경 센서 및 알람 로그 (탭 제거 후 리스트형 배치)
    with col_bop:
        st.subheader("환경 센서 상세 (BOP)")
        
        # HTML을 이용해 작고 컴팩트하게 센서 배치
        bop_html = f"""
        <div style="font-size: 13px;">
            <b style="color:#E0E0E0;">온도 (°C)</b><br>
            수소 유입: {latest_row['TinH2']:.1f} / 유출: {latest_row['ToutH2']:.1f}<br>
            공기 유입: {latest_row['TinAIR']:.1f} / 유출: {latest_row['ToutAIR']:.1f}<hr style="margin:5px 0; border-color:#333;">
            <b style="color:#E0E0E0;">압력 (mbara)</b><br>
            수소 유입: {latest_row.get('PinH2', 0):.0f} / 유출: {latest_row.get('PoutH2', 0):.0f}<br>
            공기 유입: {latest_row.get('PinAIR', 0):.0f} / 유출: {latest_row.get('PoutAIR', 0):.0f}<hr style="margin:5px 0; border-color:#333;">
            <b style="color:#E0E0E0;">유량 (l/mn)</b><br>
            수소 유입: {latest_row.get('DinH2', 0):.1f}<br>
            공기 유입: {latest_row.get('DinAIR', 0):.1f}<br>
            냉각수 배출: {latest_row.get('DWAT', 0):.1f}
        </div>
        """
        st.markdown(bop_html, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.subheader("알람 발생 이력")
        if st.session_state.alarm_log:
            for log in st.session_state.alarm_log:
                st.markdown(f'<div class="log-box">{log}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#888; font-size:12px;">현재 발생한 알람이 없습니다.</div>', unsafe_allow_html=True)

# 6. 실시간 업데이트 루프 (Data Pump)
if st.session_state.is_running:
    if st.session_state.current_index < total_rows - 1:
        time.sleep(1)
        st.session_state.current_index += 1
        st.rerun()
    else:
        st.session_state.is_running = False
        st.sidebar.warning("데이터 재생이 완료되었습니다.")
        st.rerun()
