import streamlit as st

import config
from epub_processor import extract_blocks


# 页面标题
st.title("EPUB 行间双语翻译器")

# 侧边栏配置区域
st.sidebar.header("配置")
api_key = st.sidebar.text_input("API Key", type="password")
base_url = st.sidebar.text_input("Base URL", value="https://api.openai.com/v1")
model = st.sidebar.text_input("Model", value=config.MODEL)
temperature = st.sidebar.number_input(
    "temperature",
    min_value=0.0,
    max_value=2.0,
    value=float(config.TEMPERATURE),
    step=0.1,
)
batch_size = st.sidebar.number_input(
    "batch_size",
    min_value=1,
    value=int(config.BATCH_SIZE),
    step=1,
)
concurrency = st.sidebar.number_input(
    "concurrency",
    min_value=1,
    value=int(config.CONCURRENCY),
    step=1,
)

# 主区域说明
st.markdown(
    """
    这是一个用于 EPUB 行间双语翻译的 Streamlit 空壳页面。

    阶段进度：MVP-1
    """
)

uploaded_file = st.file_uploader("上传 EPUB 文件", type=["epub"])
if st.button("解析预览"):
    if not uploaded_file:
        st.warning("请先上传 EPUB 文件。")
    else:
        epub_bytes = uploaded_file.getvalue()
        blocks = extract_blocks(epub_bytes)
        st.success(f"解析完成，blocks 数量：{len(blocks)}")
        st.subheader("前 8 条预览")
        for block in blocks[:8]:
            preview = block["text"][:80]
            st.write(f"{block['block_id']} | {block['tag']} | {preview}")
