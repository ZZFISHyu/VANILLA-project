import streamlit as st
import pandas as pd
import datetime
import re
from dateutil.parser import parse as date_parse
import requests

# ============= 配置区 =============
API_KEY = "1b3b5fbb-fd2a-4376-8b32-c16a0f91c2ca"  # 替换为你的 CoinMarketCap API Key
CMC_LIMIT = 5000               # 一次获取多少个“最新上架”的币（可适当调大）
NEW_COIN_MAX_HOURS = 4320     # 180天 (4320小时)
MIN_MARKET_CAP = 300_000
MIN_VOLUME = 30_000
MIN_LIQUIDITY = 10_000
HIGHLIGHT_72H_HOURS = 72      # 72小时内红色高亮
CSV_FILENAME = "filtered_crypto_data.csv"


# ============= 样式美化区 =============
CUSTOM_CSS = """
<style>
/* 整体背景：渐变 */
.stApp {
    background: linear-gradient(to right, #d4d4d4, #eeeeee);
}

/* 修改表格字体大小及配色 */
table td, table th {
    font-size: 14px;
}

/* 让顶部的主标题带有大字间距、居中 */
h1, h2, h3 {
    text-align: center;
    letter-spacing: 1.5px;
}

/* 提示条圆角，在中间对齐 */
.element-container .stAlert {
    border-radius: 8px;
    margin-left: auto;
    margin-right: auto;
    width: 60%;
}

/* 侧边栏，放置头像时的居中设置 */
[data-testid="stSidebar"] > div:first-child {
    align-items: center;
    text-align: center;
    padding: 1rem;
}
</style>
"""

def add_custom_css():
    """将自定义CSS插入到Streamlit页面。"""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============= 函数定义区 =============
def clean_number(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned_str = re.sub(r"[^0-9.]", "", str(value))
    return float(cleaned_str) if cleaned_str else 0.0

def fetch_coinmarketcap_data(limit=CMC_LIMIT):
    """获取最新上架的加密货币列表"""
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": API_KEY
    }
    params = {
        "start": "1",
        "limit": str(limit),
        "convert": "USD"
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            st.error(f"[Error] Request failed with status code {resp.status_code}.")
            st.write("Response text:", resp.text)
            return None
        return resp.json()
    except Exception as e:
        st.error(f"[Error] Exception when requesting CoinMarketCap API: {e}")
        return None

def fetch_coin_info(coin_ids):
    """获取多个币的详细信息(社交媒体、合约地址等)"""
    url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/info"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": API_KEY
    }
    params = {
        "id": coin_ids
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            st.error(f"[Error] Info request failed with status code {resp.status_code}.")
            st.write("Response text:", resp.text)
            return {}
        data = resp.json().get("data", {})
        return data
    except Exception as e:
        st.error(f"[Error] Exception when requesting Coin Info: {e}")
        return {}

def filter_new_coins(data):
    """先按上架时间/市值/交易量筛选，返回符合条件的币列表"""
    if not data or "data" not in data:
        return []

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    filtered_list = []

    for coin in data["data"]:
        coin_id = coin.get("id")
        name = coin.get("name", "N/A")
        symbol = coin.get("symbol", "N/A")
        date_str = coin.get("date_added", "")
        if not date_str or not coin_id:
            continue

        # 计算上架后经过的小时数
        try:
            added_time = date_parse(date_str)
        except:
            continue
        hours_since_added = (now_utc - added_time).total_seconds() / 3600.0
        if hours_since_added > NEW_COIN_MAX_HOURS:
            continue

        quote_usd = coin.get("quote", {}).get("USD", {})
        market_cap = clean_number(quote_usd.get("market_cap", 0))
        volume_24h = clean_number(quote_usd.get("volume_24h", 0))
        liquidity = volume_24h

        if (market_cap > MIN_MARKET_CAP and volume_24h > MIN_VOLUME and liquidity > MIN_LIQUIDITY):
            filtered_list.append({
                "ID": coin_id,
                "Name": name,
                "Symbol": symbol,
                "Date Added": date_str,
                "HoursSinceAdded": round(hours_since_added, 1),
                "Market Cap": market_cap,
                "24h Volume": volume_24h,
                "Liquidity(approx)": liquidity
            })
    return filtered_list

def get_social_links(coin_info):
    """提取推特、Reddit、Facebook、Telegram，如果没有则用 'N'"""
    urls = coin_info.get("urls", {})
    twitter = urls.get("twitter", ["N"])[0] if urls.get("twitter") else "N"
    reddit = urls.get("reddit", ["N"])[0] if urls.get("reddit") else "N"
    facebook = urls.get("facebook", ["N"])[0] if urls.get("facebook") else "N"
    telegram = urls.get("telegram", ["N"])[0] if urls.get("telegram") else "N"
    return twitter, reddit, facebook, telegram

def get_contract_address(coin_info):
    """提取合约地址，没有则返回 'N'"""
    try:
        c_arr = coin_info.get("contract_address", [])
        if c_arr and len(c_arr) > 0:
            return c_arr[0].get("contract_address", "N")
        else:
            return "N"
    except:
        return "N"

def classify_potential(market_cap, volume_24h):
    """
    评级规则(仅示例)：
    S: 市值>500M 且交易量>100M
    A: 市值>100M 或交易量>50M
    B: 市值>10M  或交易量>5M
    C: 市值>1M   或交易量>1M
    D: 其他
    """
    if market_cap > 500_000_000 and volume_24h > 100_000_000:
        return "S"
    elif market_cap > 100_000_000 or volume_24h > 50_000_000:
        return "A"
    elif market_cap > 10_000_000 or volume_24h > 5_000_000:
        return "B"
    elif market_cap > 1_000_000 or volume_24h > 1_000_000:
        return "C"
    else:
        return "D"

def main():
    st.set_page_config(page_title="Crypto Newcomers - by FISH", layout="wide")
    add_custom_css()

    # 侧边栏
    st.sidebar.image("avatar.jpg", caption="制作者: FISH", width=140)
    st.sidebar.markdown("---")
    st.sidebar.title("Crypto Newcomers")
    st.sidebar.markdown("**用途**: 快速筛选市值、交易量都不错的**新上架**币种")

    # 主体区域
    st.title("新上架加密货币筛选器")
    st.markdown("### 由 **FISH** 倾情打造，助你快速发现新币！")

    st.info("点击下方按钮，从 CoinMarketCap 拉取最新数据，然后筛选出符合条件的新币。")

    with st.expander("查看筛选标准"):
        st.markdown(f"""
        **基本筛选** (先剔除无价值项目):
        - 上架时间：**{NEW_COIN_MAX_HOURS} 小时** (约半年内)
        - 市值 > **{MIN_MARKET_CAP:,}**
        - 24小时交易量 > **{MIN_VOLUME:,}**
        - 流动性(近似 24h 交易量) > **{MIN_LIQUIDITY:,}**
        - 上架 **{HIGHLIGHT_72H_HOURS} 小时**内的新币，会用**红色**高亮

        ---
        **潜力等级** (二次划分):
        - S: 市值>500M 且 交易量>100M
        - A: 市值>100M 或 交易量>50M
        - B: 市值>10M  或 交易量>5M
        - C: 市值>1M   或 交易量>1M
        - D: 其他
        """)

    if st.button("获取并筛选新币"):
        with st.spinner("正在从 CoinMarketCap 获取数据..."):
            data = fetch_coinmarketcap_data()

        if not data:
            st.error("[Error] 无法获取数据，请检查 API Key 或网络。")
            return

        st.success("数据获取成功！开始筛选...")
        coins = filter_new_coins(data)
        if not coins:
            st.warning("没有符合条件的币。")
            return

        st.success(f"共筛选出 {len(coins)} 个币。")

        # 排序(小时数升序：越新越前)
        coins.sort(key=lambda c: c["HoursSinceAdded"])

        # 补充社交媒体、合约信息
        id_str = ",".join(str(c["ID"]) for c in coins)
        coin_info_data = {}
        if id_str:
            with st.spinner("正在获取社交媒体和合约信息..."):
                coin_info_data = fetch_coin_info(id_str)

        # 赋值到 coins + 分级
        for c in coins:
            c_id = str(c["ID"])
            if c_id in coin_info_data:
                info = coin_info_data[c_id]
                tw, rd, fb, tg = get_social_links(info)
                contract = get_contract_address(info)
                c["Twitter"] = tw
                c["Reddit"] = rd
                c["Facebook"] = fb
                c["Telegram"] = tg
                c["Contract"] = contract
            else:
                c["Twitter"] = "N"
                c["Reddit"] = "N"
                c["Facebook"] = "N"
                c["Telegram"] = "N"
                c["Contract"] = "N"

            # 潜力等级
            c["Potential Level"] = classify_potential(c["Market Cap"], c["24h Volume"])

        # 转成 DataFrame（全部结果）
        df = pd.DataFrame(coins)
        
        # 用户可选是否保存
        if st.checkbox("保存筛选结果到 CSV 文件"):
            df.to_csv(CSV_FILENAME, index=False, encoding="utf-8")
            st.info(f"结果已保存到 {CSV_FILENAME}")

        # ---- 显示“全部结果” ----
        st.subheader("全部筛选结果")
        # 给 HoursSinceAdded 加高亮
        styled_df_all = df.style.applymap(
            lambda x: "color: red; font-weight:bold;" if isinstance(x, float) and x <= HIGHLIGHT_72H_HOURS else "",
            subset=["HoursSinceAdded"]
        )
        st.dataframe(styled_df_all, use_container_width=True)

        st.markdown("---")
        st.subheader("按潜力等级分类")

        # 分组展示：S, A, B, C, D
        ratings = ["S","A","B","C","D"]
        for rating in ratings:
            sub_coins = [c for c in coins if c["Potential Level"] == rating]
            if len(sub_coins) == 0:
                continue  # 没有该评级的币则跳过

            st.markdown(f"### 潜力等级: {rating} (共 {len(sub_coins)} 个)")
            sub_df = pd.DataFrame(sub_coins)
            # 同样加 HoursSinceAdded 高亮
            styled_sub_df = sub_df.style.applymap(
                lambda x: "color: red; font-weight:bold;" if isinstance(x, float) and x <= HIGHLIGHT_72H_HOURS else "",
                subset=["HoursSinceAdded"]
            )
            st.dataframe(styled_sub_df, use_container_width=True)

        st.markdown("---")
        st.subheader("详细列表 (全部)")
        # 不再限制前10，直接逐个打印
        for i, coin in enumerate(coins, start=1):
            color_style = "red" if coin["HoursSinceAdded"] <= HIGHLIGHT_72H_HOURS else "black"
            st.markdown(
                f"""
                <p style="color:{color_style}; font-weight:bold; margin-left:20px;">
                {i}. {coin['Name']} ({coin['Symbol']})  
                - Market Cap: {coin['Market Cap']:,}  
                - 24h Volume: {coin['24h Volume']:,}  
                - Hours Since Added: {coin['HoursSinceAdded']}  
                - Potential Level: <b>{coin['Potential Level']}</b>  
                - Twitter: {coin['Twitter']}  
                - Reddit: {coin['Reddit']}  
                - Facebook: {coin['Facebook']}  
                - Telegram: {coin['Telegram']}  
                - Contract: {coin['Contract']}
                </p>
                """,
                unsafe_allow_html=True
            )

    st.markdown("---")
    st.markdown("<div style='text-align:center;'>Made with ❤️ by <b>FISH</b></div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
