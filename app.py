import asyncio
import hashlib
import json
import time

import streamlit as st

import config
from database import bulk_get, init_db, make_cache_key, set_many
from epub_processor import extract_blocks
from translator import translate_batches


# 页面标题
st.title("EPUB 行间双语翻译器")

# 初始化缓存数据库
init_db(config.DB_PATH)

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

    阶段进度：MVP-3
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


st.subheader("缓存自检")
if st.button("缓存自检"):
    demo_text = "This is a cache smoke test."
    text_hash = hashlib.sha256(demo_text.encode("utf-8")).hexdigest()
    params_json = json.dumps(
        {
            "temperature": float(temperature),
            "batch_size": int(batch_size),
            "concurrency": int(concurrency),
        },
        sort_keys=True,
    )
    # 缓存键包含模型/提示版本/参数，防止不同配置的翻译结果混用
    cache_key = make_cache_key(text_hash, model, config.PROMPT_VERSION, params_json)
    now_ts = int(time.time())

    set_many(
        config.DB_PATH,
        [
            {
                "cache_key": cache_key,
                "text_hash": text_hash,
                "model": model,
                "prompt_version": config.PROMPT_VERSION,
                "params_json": params_json,
                "translation": "这是缓存写入示例",
                "created_at": now_ts,
            }
        ],
    )

    result = bulk_get(config.DB_PATH, [cache_key, "non-existent-key"])
    st.success("缓存写入并读取成功")
    st.json(result)


st.subheader("翻译 EPUB（MVP-4）")
max_blocks = st.number_input(
    "max_blocks（0 表示不限制）",
    min_value=0,
    value=50,
    step=1,
)
if st.button("开始翻译（MVP-4）"):
    if not uploaded_file:
        st.warning("请先上传 EPUB 文件。")
    elif not api_key:
        st.warning("请先填写 API Key。")
    else:
        start_ts = time.time()
        epub_bytes = uploaded_file.getvalue()
        blocks = extract_blocks(epub_bytes)
        if max_blocks > 0:
            blocks = blocks[: int(max_blocks)]

        if not blocks:
            st.warning("未解析到可翻译的 blocks。")
        else:
            params = {"temperature": float(temperature)}
            # params_json 必须稳定序列化，否则同一参数顺序或空白不同会导致缓存键不一致、命中失效
            params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))

            for block in blocks:
                # 缓存键必须包含 model/prompt_version/params_json，避免不同模型或提示参数共享同一缓存
                block["cache_key"] = make_cache_key(
                    block["text_hash"], model, config.PROMPT_VERSION, params_json
                )

            cache_hits = bulk_get(config.DB_PATH, [b["cache_key"] for b in blocks])
            results = {}
            missing_blocks = []
            cache_hit_count = 0
            for block in blocks:
                cached_translation = cache_hits.get(block["cache_key"])
                if cached_translation is not None:
                    results[block["block_id"]] = cached_translation
                    cache_hit_count += 1
                else:
                    missing_blocks.append(block)

            failures = []
            miss_count = len(missing_blocks)
            if missing_blocks:
                fresh_results, failures = asyncio.run(
                    translate_batches(
                        missing_blocks,
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                        temperature=float(temperature),
                        batch_size=int(batch_size),
                        concurrency=int(concurrency),
                    )
                )
                results.update(fresh_results)

                now_ts = int(time.time())
                rows = []
                for block in missing_blocks:
                    translation = fresh_results.get(block["block_id"])
                    if translation is None:
                        continue
                    rows.append(
                        {
                            "cache_key": block["cache_key"],
                            "text_hash": block["text_hash"],
                            "model": model,
                            "prompt_version": config.PROMPT_VERSION,
                            "params_json": params_json,
                            "translation": translation,
                            "created_at": now_ts,
                        }
                    )
                set_many(config.DB_PATH, rows)

            elapsed = time.time() - start_ts
            st.success("翻译完成")
            st.write(f"本次处理 blocks 数：{len(blocks)}")
            st.write(f"缓存命中数：{cache_hit_count}")
            st.write(f"未命中数（请求翻译数）：{miss_count}")
            st.write(f"失败数：{len(failures)}")
            st.write(f"耗时：{elapsed:.2f} 秒")

            if failures:
                st.write("失败详情（block_id / 原文前 50 字 / 错误原因）：")
                st.table(
                    [
                        {
                            "block_id": f["id"],
                            "text_snippet": f.get("text_snippet", ""),
                            "reason": f.get("reason", ""),
                        }
                        for f in failures
                    ]
                )


st.subheader("翻译自测（MVP-3）")
if st.button("翻译自测（MVP-3）"):
    if not api_key:
        st.warning("请先填写 API Key。")
    else:
        # 构造三条示例段落，用固定 block_id 和 text_hash 便于验证
        demo_blocks = [
            {
                "block_id": "sample::p::0",
                "text": "This is the first sample paragraph for translation.",
            },
            {
                "block_id": "sample::p::1",
                "text": "Here is the second sentence to check batching behavior.",
            },
            {
                "block_id": "sample::p::2",
                "text": "Finally, this third piece ensures ordering is preserved.",
            },
        ]
        for blk in demo_blocks:
            blk["text_hash"] = hashlib.sha256(blk["text"].encode("utf-8")).hexdigest()

        # 结构化 JSON 输出让模型按 id 返回，可保证多段翻译不乱序
        results, failures = asyncio.run(
            translate_batches(
                demo_blocks,
                api_key=api_key,
                base_url=base_url,
                model=model,
                temperature=float(temperature),
                batch_size=int(batch_size),
                concurrency=int(concurrency),
            )
        )
        st.success("翻译完成")
        st.write("成功映射：")
        st.json(results)
        st.write("失败记录：")
        st.json(failures)
