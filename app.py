import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import plotly.graph_objects as go

st.set_page_config(page_title="トラさん流 株式分析", page_icon="📈", layout="wide")

st.markdown("""<style>
/* 全体背景を明るく */
.stApp { background-color: #F0F4F8; }
.block-container { padding-top: 1.5rem; }
/* カード */
.mcard {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    margin-bottom: 4px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.10);
    border: 1px solid #E2E8F0;
}
.mcard-lbl { font-size: 11px; color: #64748B; margin-bottom: 4px; }
.mcard-val { font-size: 24px; font-weight: 700; color: #1E293B; }
.mcard-up  { font-size: 12px; color: #16A34A; margin-top: 2px; font-weight:600; }
.mcard-dn  { font-size: 12px; color: #DC2626; margin-top: 2px; font-weight:600; }
/* 判定バッジ */
.badge-buy   { display:inline-block; background:#DCFCE7; color:#15803D;
               padding:5px 16px; border-radius:20px; font-weight:700; font-size:13px; }
.badge-watch { display:inline-block; background:#FEF9C3; color:#A16207;
               padding:5px 16px; border-radius:20px; font-weight:700; font-size:13px; }
.badge-weak  { display:inline-block; background:#FFEDD5; color:#C2410C;
               padding:5px 16px; border-radius:20px; font-weight:700; font-size:13px; }
.badge-avoid { display:inline-block; background:#FEE2E2; color:#B91C1C;
               padding:5px 16px; border-radius:20px; font-weight:700; font-size:13px; }
/* スコアカード */
.score-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.10);
    border: 1px solid #E2E8F0;
    margin-bottom: 4px;
}
/* バー */
.sbar-bg { background:#E2E8F0; border-radius:4px; height:8px; margin-top:4px; }
.sbar    { height:8px; border-radius:4px; }
</style>""", unsafe_allow_html=True)

SITES = {
    "マクロ経済": [
        ("FRED（金利・CPI）", "https://fred.stlouisfed.org/"),
        ("CME FedWatch", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
        ("CNN Fear & Greed", "https://edition.cnn.com/markets/fear-and-greed"),
    ],
    "バリュエーション": [
        ("投資の森（バフェット指数）", "https://nikkeiyosoku.com/buffett_us/"),
        ("Multpl シラーPER", "https://www.multpl.com/shiller-pe"),
        ("Multpl S&P500 PER", "https://www.multpl.com/s-p-500-pe-ratio"),
    ],
    "株価・チャート": [
        ("TradingView", "https://jp.tradingview.com/"),
        ("Yahoo Finance", "https://finance.yahoo.com/"),
        ("Finviz セクターマップ", "https://finviz.com/map.ashx"),
    ],
    "バフェット動向": [
        ("SEC EDGAR 13F", "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001067983&type=13F"),
        ("Berkshire 株主レター", "https://www.berkshirehathaway.com/letters/letters.html"),
        ("Macrotrends", "https://www.macrotrends.net/"),
    ],
    "日本・新NISA": [
        ("金融庁", "https://www.fsa.go.jp/policy/nisa2/"),
        ("日経新聞", "https://www.nikkei.com/"),
        ("楽天証券 トウシル", "https://media.rakuten-sec.net/"),
    ],
}

@st.cache_data(ttl=1800)
def fetch_market():
    tgts = {"S&P500":"^GSPC","VIX":"^VIX","米10年債":"^TNX","米2年債":"^IRX","ドル円":"JPY=X"}
    out = {}
    for name, tk in tgts.items():
        try:
            h = yf.Ticker(tk).history(period="5d")
            if h.empty: continue
            v = round(h["Close"].iloc[-1], 3)
            c = round((v - h["Close"].iloc[-2]) / h["Close"].iloc[-2] * 100, 2) if len(h) >= 2 else 0.0
            out[name] = {"v": v, "c": c}
        except:
            out[name] = {"v": None, "c": 0.0}
    return out

@st.cache_data(ttl=3600)
def fetch_valu():
    r = {"buffett": 100.0, "cape": 37.0, "per": 28.4}
    try:
        res = requests.get("https://nikkeiyosoku.com/buffett_us/", timeout=8,
                           headers={"User-Agent": "Mozilla/5.0"})
        m = re.findall(r"バフェット指数[^\d]*(\d+\.?\d*)\s*%",
                       BeautifulSoup(res.text, "html.parser").get_text())
        if m: r["buffett"] = float(m[0])
    except: pass
    return r

def kind_of(tk):
    if tk.startswith("^"): return "インデックス"
    try:
        q = yf.Ticker(tk).info.get("quoteType", "").upper()
        return "ETF" if q == "ETF" else "個別株"
    except: return "個別株"

def sc_macro(vix, b10, b2):
    vs = max(0, min(100, (40-vix)/20*100))
    bs = max(0, min(100, (6.0-b10)/3.0*100))
    ys = 100 if b10-b2 > 0.5 else (50 if b10 > b2 else 0)
    return round(vs*0.4 + bs*0.4 + ys*0.2, 1)

def sc_valu(buf, cape, per):
    a = max(0, min(100, (150-buf)/70*100))
    b = max(0, min(100, (40-cape)/25*100))
    c = max(0, min(100, (35-per)/20*100))
    return round(a*0.5 + b*0.3 + c*0.2, 1)

def sc_tech(tk):
    try:
        h = yf.Ticker(tk).history(period="6mo")
        if h.empty or len(h) < 14: return 50.0, {}
        cl = h["Close"]
        ma50  = cl.rolling(min(50,  len(cl))).mean().iloc[-1]
        ma200 = cl.rolling(min(200, len(cl))).mean().iloc[-1]
        last  = cl.iloc[-1]
        ms = 70 if last > ma50  else 30
        gs = 80 if ma50 > ma200 else 20
        dlt  = cl.diff()
        gain = dlt.clip(lower=0).rolling(14).mean().iloc[-1]
        loss = (-dlt.clip(upper=0)).rolling(14).mean().iloc[-1]
        rsi  = round(100-(100/(1+gain/loss)), 1) if loss != 0 else 50
        rs   = 85 if rsi < 30 else (25 if rsi > 70 else 60)
        return round(ms*0.4+gs*0.3+rs*0.3, 1), {
            "RSI": rsi, "MA50": round(ma50,2),
            "MA200": round(ma200,2), "終値": round(last,2)}
    except: return 50.0, {}

def sc_fund(tk):
    try:
        info = yf.Ticker(tk).info
        roe  = (info.get("returnOnEquity", 0) or 0) * 100
        per  = info.get("trailingPE", 20) or 20
        rg   = (info.get("revenueGrowth", 0) or 0) * 100
        dy   = (info.get("dividendYield", 0) or 0) * 100
        t = round(
            max(0,min(100,roe/30*100))*0.35 +
            max(0,min(100,(35-per)/20*100))*0.30 +
            max(0,min(100,rg/20*100))*0.25 +
            max(0,min(100,dy/5*100))*0.10, 1)
        return t, {"ROE(%)":round(roe,1),"PER":round(per,1),
                   "売上成長(%)":round(rg,1),"配当(%)":round(dy,2)}
    except: return 50.0, {}

def do_analyze(tk, ms, vs, wm, wv, wt, wf):
    kind = kind_of(tk)
    tech, td = sc_tech(tk)
    if kind == "個別株":
        fund, fd = sc_fund(tk)
        total = round(ms*wm + vs*wv + tech*wt + fund*wf, 1)
    else:
        fund, fd = None, {}
        total = round(ms*(wm+wf) + vs*wv + tech*wt, 1)
    if   total >= 70: jdg, badge = "★ 買い候補",   "buy"
    elif total >= 50: jdg, badge = "△ 様子見",     "watch"
    elif total >= 35: jdg, badge = "▼ 弱い様子見", "weak"
    else:             jdg, badge = "✕ 見送り",     "avoid"
    return {"tk":tk,"kind":kind,"ms":ms,"vs":vs,"tech":tech,"fund":fund,
            "total":total,"jdg":jdg,"badge":badge,"td":td,"fd":fd}

def mc(lbl, val, chg=None):
    if chg is None: d = ""
    elif chg >= 0:  d = '<div class="mcard-up">&#9650; {:.2f}%</div>'.format(abs(chg))
    else:           d = '<div class="mcard-dn">&#9660; {:.2f}%</div>'.format(abs(chg))
    return '<div class="mcard"><div class="mcard-lbl">{}</div><div class="mcard-val">{}</div>{}</div>'.format(lbl, val, d)

def sb(score, color="#2563EB"):
    p = max(0, min(100, score))
    return '<div class="sbar-bg"><div class="sbar" style="width:{}%;background:{};"></div></div>'.format(p, color)

# サイドバー
with st.sidebar:
    st.markdown("## ⚙️ 設定")
    tk_input = st.text_area("分析銘柄（改行区切り）",
                            value="^GSPC\nVOO\nAAPL\nNVDA", height=120)
    tickers = [t.strip().upper() for t in tk_input.splitlines() if t.strip()]
    st.divider()
    st.markdown("### ⚖️ 重み調整（個別株）")
    st.caption("合計を100にしてください")
    wm = st.number_input("マクロ(%)",           0, 100, 25, 5)
    wv = st.number_input("バリュエーション(%)", 0, 100, 15, 5)
    wt = st.number_input("テクニカル(%)",       0, 100, 10, 5)
    wf = st.number_input("ファンダ(%)",         0, 100, 50, 5)
    tw = wm+wv+wt+wf
    if tw != 100: st.warning("合計: {}%".format(tw))
    else:         st.success("合計: {}% ✓".format(tw))
    st.divider()
    run = st.button("🔍 分析実行", use_container_width=True, type="primary")

# メイン
st.markdown("# 📈 トラさん流 株式分析ダッシュボード")
st.caption("更新: {}　　データ: yfinance / 投資の森".format(
    datetime.now().strftime("%Y-%m-%d %H:%M")))

tab1, tab2, tab3 = st.tabs(["📊 市場概況", "🔬 銘柄分析", "🌐 参照サイト"])

# ── TAB1 ──────────────────────────────────────────────────
with tab1:
    with st.spinner("データ取得中..."):
        mkt = fetch_market()
        vd  = fetch_valu()

    vix  = mkt.get("VIX",     {}).get("v", 20)  or 20
    b10  = mkt.get("米10年債", {}).get("v", 4.5) or 4.5
    b2   = mkt.get("米2年債",  {}).get("v", 4.0) or 4.0
    buf  = vd.get("buffett", 100.0)
    cape = vd.get("cape",    37.0)
    per  = vd.get("per",     28.4)
    ms   = sc_macro(vix, b10, b2)
    vs   = sc_valu(buf, cape, per)

    st.markdown("#### マクロ指標")
    cols = st.columns(4)
    for col, (lbl, key) in zip(cols, [
        ("S&P500","S&P500"),("VIX","VIX"),("米10年債利回り","米10年債"),("ドル円","ドル円")]):
        d = mkt.get(key, {}); v = d.get("v"); c = d.get("c", 0)
        col.markdown(mc(lbl, "{:,.3g}".format(v) if v else "—", chg=c),
                     unsafe_allow_html=True)

    st.divider()
    st.markdown("#### バリュエーション & スコア")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(mc("バフェット指数",    "{:.0f}%".format(buf)),  unsafe_allow_html=True)
    c2.markdown(mc("シラーPER(CAPE)",  "{:.1f}".format(cape)),   unsafe_allow_html=True)
    c3.markdown(mc("S&P500 PER",       "{:.1f}".format(per)),    unsafe_allow_html=True)
    c4.markdown(mc("マクロスコア",     "{:.1f}".format(ms)),     unsafe_allow_html=True)
    c5.markdown(mc("バリュエーション", "{:.1f}".format(vs)),     unsafe_allow_html=True)

    st.divider()
    st.markdown("#### スコア内訳")
    cl, cr = st.columns(2)
    with cl:
        st.markdown("**マクロ内訳**")
        for lbl, val, color in [
            ("VIX ({})".format(vix),   max(0,min(100,(40-vix)/20*100)),  "#2563EB"),
            ("金利 ({}%)".format(b10), max(0,min(100,(6-b10)/3*100)),    "#2563EB"),
            ("イールド差",              100 if b10-b2>0.5 else 50,         "#2563EB"),
        ]:
            st.markdown(
                '<div style="font-size:12px;color:#475569;margin-top:8px;">'
                '{} — {:.0f}点</div>'.format(lbl, val) + sb(val, "#2563EB"),
                unsafe_allow_html=True)
    with cr:
        st.markdown("**バリュエーション内訳**")
        bs = max(0,min(100,(150-buf)/70*100))
        cs = max(0,min(100,(40-cape)/25*100))
        ps = max(0,min(100,(35-per)/20*100))
        for lbl, val, color in [
            ("バフェット ({:.0f}%)".format(buf), bs, "#7C3AED"),
            ("CAPE ({:.1f})".format(cape),        cs, "#7C3AED"),
            ("PER ({:.1f})".format(per),           ps, "#7C3AED"),
        ]:
            st.markdown(
                '<div style="font-size:12px;color:#475569;margin-top:8px;">'
                '{} — {:.0f}点</div>'.format(lbl, val) + sb(val, "#7C3AED"),
                unsafe_allow_html=True)

    st.divider()
    st.markdown("#### スコアゲージ")

    def gauge(title, value, color):
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=value,
            title={"text": title, "font": {"size": 13, "color": "#1E293B"}},
            number={"font": {"color": "#1E293B"}},
            gauge={
                "axis": {"range": [0,100], "tickcolor": "#64748B"},
                "bar":  {"color": color},
                "bgcolor": "#F8FAFC",
                "steps": [
                    {"range": [0,  35], "color": "#FEE2E2"},
                    {"range": [35, 50], "color": "#FFEDD5"},
                    {"range": [50, 70], "color": "#FEF9C3"},
                    {"range": [70,100], "color": "#DCFCE7"},
                ],
                "threshold": {"line": {"color": "#1E293B","width": 2},
                              "thickness": 0.75, "value": 70},
            }))
        fig.update_layout(
            height=200, margin=dict(t=40,b=10,l=20,r=20),
            paper_bgcolor="rgba(0,0,0,0)", font_color="#1E293B")
        return fig

    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(gauge("マクロスコア", ms, "#2563EB"), use_container_width=True)
    with g2:
        st.plotly_chart(gauge("バリュエーションスコア", vs, "#7C3AED"), use_container_width=True)

# ── TAB2 ──────────────────────────────────────────────────
with tab2:
    if not run:
        st.info("サイドバーの「分析実行」ボタンを押してください")
    elif tw != 100:
        st.error("重みの合計が100になっていません")
    else:
        results = []
        prog = st.progress(0, text="分析中...")
        for i, tk in enumerate(tickers):
            prog.progress((i+1)/len(tickers), text="分析中: {}".format(tk))
            results.append(do_analyze(tk, ms, vs, wm/100, wv/100, wt/100, wf/100))
        prog.empty()

        st.markdown("#### 総合判定")
        for col, r in zip(st.columns(len(results)), results):
            col.markdown(
                '<div class="score-card">'
                '<div style="font-size:17px;font-weight:700;color:#1E293B;margin-bottom:4px;">{}</div>'
                '<div style="font-size:11px;color:#64748B;margin-bottom:10px;">{}</div>'
                '<div style="font-size:36px;font-weight:700;color:#1E293B;margin-bottom:8px;">{}</div>'
                '<span class="badge-{}">{}</span>'
                '</div>'.format(r["tk"], r["kind"], r["total"], r["badge"], r["jdg"]),
                unsafe_allow_html=True)

        st.divider()
        st.markdown("#### スコア比較（レーダーチャート）")
        cats   = ["マクロ","バリュエーション","テクニカル","ファンダ"]
        colors = ["#2563EB","#7C3AED","#EA580C","#059669","#D97706","#DC2626"]
        fig_r  = go.Figure()
        for r, color in zip(results, colors):
            vals = [r["ms"],r["vs"],r["tech"],r["fund"] if r["fund"] else r["ms"]]
            fig_r.add_trace(go.Scatterpolar(
                r=vals+[vals[0]], theta=cats+[cats[0]],
                fill="toself", name=r["tk"], line_color=color, opacity=0.7))
        fig_r.update_layout(
            polar=dict(
                bgcolor="#F8FAFC",
                radialaxis=dict(range=[0,100], gridcolor="#CBD5E1",
                                tickfont=dict(color="#475569")),
                angularaxis=dict(gridcolor="#CBD5E1",
                                 tickfont=dict(color="#1E293B"))),
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(font=dict(color="#1E293B")),
            height=380, margin=dict(t=20,b=20))
        st.plotly_chart(fig_r, use_container_width=True)

        st.markdown("#### テクニカル詳細")
        st.dataframe(pd.DataFrame([{
            "ティッカー":      r["tk"],
            "終値":           r["td"].get("終値","—"),
            "50日MA":         r["td"].get("MA50","—"),
            "200日MA":        r["td"].get("MA200","—"),
            "RSI(14)":        r["td"].get("RSI","—"),
            "テクニカルスコア": r["tech"],
        } for r in results]), use_container_width=True, hide_index=True)

        fund_rs = [r for r in results if r["fd"]]
        if fund_rs:
            st.markdown("#### ファンダメンタルズ詳細（個別株）")
            st.dataframe(pd.DataFrame([{
                "ティッカー":    r["tk"],
                "ROE(%)":       r["fd"].get("ROE(%)","—"),
                "PER":          r["fd"].get("PER","—"),
                "売上成長(%)":   r["fd"].get("売上成長(%)","—"),
                "配当(%)":      r["fd"].get("配当(%)","—"),
                "ファンダスコア": r["fund"],
            } for r in fund_rs]), use_container_width=True, hide_index=True)

# ── TAB3 ──────────────────────────────────────────────────
with tab3:
    st.markdown("#### 🌐 トラさん参照サイト一覧")
    st.caption("ボタンをクリックすると各サイトが新しいタブで開きます")
    for cat, sites in SITES.items():
        st.markdown("**{}**".format(cat))
        cols = st.columns(len(sites))
        for col, (name, url) in zip(cols, sites):
            col.link_button("↗ {}".format(name), url, use_container_width=True)
        st.markdown("")
    st.divider()
    st.markdown("#### 📌 手動確認メモ")
    st.text_area("気になった数値や所感をメモ",
                 placeholder="例: バフェット指数100%到達。CAPE37と高止まり...",
                 height=100)
