import json
import os
import time

import config
from database import bulk_get, make_cache_key, make_prompt_hash, set_many
from epub_processor import extract_blocks, inject_translations
from translator import translate_batches
from translation_types import TranslateFunc, TranslationOptions


def empty_job_state() -> dict:
    return {
        "status": "idle",
        "pending_blocks": [],
        "total_blocks": 0,
        "processed_blocks": 0,
        "hit_count": 0,
        "failures": [],
        "start_time": None,
        "last_update_time": None,
        "results_map": {},
        "epub_bytes": None,
        "output_name": None,
        "params_json": None,
        "model": None,
        "temperature": None,
        "batch_size": None,
        "concurrency": None,
        "base_url": None,
        "miss_count": 0,
        "output_bytes": None,
        "custom_prompt": "",
        "glossary": "",
        "recent_context": [],
        "thinking_enabled": config.DEFAULT_THINKING_ENABLED,
        "prompt_hash": "",
        "target_language": config.DEFAULT_TARGET_LANGUAGE,
        "translation_profile": config.DEFAULT_TRANSLATION_PROFILE,
        "style_preset": config.DEFAULT_STYLE_PRESET,
        "last_window_size": 0,
        "last_batch_seconds": 0.0,
        "avg_batch_seconds": 0.0,
        "batches_completed": 0,
    }


def build_params_json(
    temperature: float,
    target_language: str = config.DEFAULT_TARGET_LANGUAGE,
    thinking_enabled: bool = config.DEFAULT_THINKING_ENABLED,
    translation_profile: str = config.DEFAULT_TRANSLATION_PROFILE,
    style_preset: str = config.DEFAULT_STYLE_PRESET,
) -> str:
    # 稳定序列化，避免同一参数因空白或顺序不同导致缓存 key 变化。
    return json.dumps(
        {
            "target_language": target_language or config.DEFAULT_TARGET_LANGUAGE,
            "thinking_enabled": bool(thinking_enabled),
            "temperature": float(temperature),
            "translation_profile": translation_profile or config.DEFAULT_TRANSLATION_PROFILE,
            "style_preset": style_preset or config.DEFAULT_STYLE_PRESET,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def apply_cache_keys(
    blocks: list[dict],
    model: str,
    params_json: str,
    custom_prompt: str,
    glossary: str,
) -> tuple[list[dict], str]:
    prompt_hash = make_prompt_hash(custom_prompt, glossary)
    keyed_blocks = []
    for block in blocks:
        keyed = dict(block)
        keyed["cache_key"] = make_cache_key(
            keyed["text_hash"],
            model,
            config.PROMPT_VERSION,
            params_json,
            prompt_hash,
        )
        keyed_blocks.append(keyed)
    return keyed_blocks, prompt_hash


def create_job_from_blocks(
    blocks: list[dict],
    epub_bytes: bytes,
    input_name: str,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
    base_url: str,
    custom_prompt: str,
    glossary: str,
    db_path: str,
    target_language: str = config.DEFAULT_TARGET_LANGUAGE,
    thinking_enabled: bool = config.DEFAULT_THINKING_ENABLED,
    translation_profile: str = config.DEFAULT_TRANSLATION_PROFILE,
    style_preset: str = config.DEFAULT_STYLE_PRESET,
    now: float | None = None,
) -> dict:
    start_ts = time.time() if now is None else now
    params_json = build_params_json(
        temperature,
        target_language,
        thinking_enabled,
        translation_profile,
        style_preset,
    )
    keyed_blocks, prompt_hash = apply_cache_keys(blocks, model, params_json, custom_prompt, glossary)

    cache_hits = bulk_get(db_path, [block["cache_key"] for block in keyed_blocks])
    results_map = {}
    pending_blocks = []
    cache_hit_count = 0
    for block in keyed_blocks:
        cached_translation = cache_hits.get(block["cache_key"])
        if cached_translation is not None:
            results_map[block["block_id"]] = cached_translation
            cache_hit_count += 1
        else:
            pending_blocks.append(block)

    base_name, _ = os.path.splitext(input_name)
    output_name = f"{base_name}_bilingual.epub"

    return {
        "status": "running" if pending_blocks else "done",
        "pending_blocks": pending_blocks,
        "total_blocks": len(keyed_blocks),
        "processed_blocks": cache_hit_count,
        "hit_count": cache_hit_count,
        "failures": [],
        "start_time": start_ts,
        "last_update_time": start_ts,
        "results_map": results_map,
        "epub_bytes": epub_bytes,
        "output_name": output_name,
        "params_json": params_json,
        "model": model,
        "temperature": float(temperature),
        "batch_size": int(batch_size),
        "concurrency": int(concurrency),
        "base_url": base_url,
        "miss_count": len(pending_blocks),
        "output_bytes": None,
        "custom_prompt": custom_prompt,
        "glossary": glossary,
        "recent_context": [],
        "thinking_enabled": bool(thinking_enabled),
        "prompt_hash": prompt_hash,
        "target_language": target_language or config.DEFAULT_TARGET_LANGUAGE,
        "translation_profile": translation_profile or config.DEFAULT_TRANSLATION_PROFILE,
        "style_preset": style_preset or config.DEFAULT_STYLE_PRESET,
        "last_window_size": 0,
        "last_batch_seconds": 0.0,
        "avg_batch_seconds": 0.0,
        "batches_completed": 0,
    }


def create_translation_job(
    epub_bytes: bytes,
    input_name: str,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
    base_url: str,
    custom_prompt: str,
    glossary: str,
    max_blocks: int,
    db_path: str,
    target_language: str = config.DEFAULT_TARGET_LANGUAGE,
    thinking_enabled: bool = config.DEFAULT_THINKING_ENABLED,
    translation_profile: str = config.DEFAULT_TRANSLATION_PROFILE,
    style_preset: str = config.DEFAULT_STYLE_PRESET,
) -> dict:
    blocks = extract_blocks(epub_bytes)
    if max_blocks > 0:
        blocks = blocks[:max_blocks]
    if not blocks:
        job = empty_job_state()
        job["status"] = "empty"
        job["epub_bytes"] = epub_bytes
        return job
    return create_job_from_blocks(
        blocks,
        epub_bytes,
        input_name,
        model,
        temperature,
        batch_size,
        concurrency,
        base_url,
        custom_prompt,
        glossary,
        db_path,
        target_language,
        thinking_enabled,
        translation_profile,
        style_preset,
    )


def _attach_failed_blocks(failures: list[dict], batch: list[dict]) -> list[dict]:
    blocks_by_id = {block["block_id"]: block for block in batch}
    enriched = []
    for failure in failures:
        item = dict(failure)
        block = blocks_by_id.get(item.get("id"))
        if block is not None:
            item["block"] = dict(block)
        enriched.append(item)
    return enriched


def prepare_retry_failed_blocks(job: dict) -> int:
    retry_blocks = []
    seen_ids = set()
    for failure in job.get("failures") or []:
        block = failure.get("block")
        if not block:
            continue
        block_id = block.get("block_id")
        if block_id in seen_ids:
            continue
        retry_blocks.append(dict(block))
        seen_ids.add(block_id)

    if not retry_blocks:
        return 0

    job["pending_blocks"] = retry_blocks
    job["failures"] = []
    job["processed_blocks"] = max(int(job.get("total_blocks") or 0) - len(retry_blocks), 0)
    job["last_update_time"] = time.time()
    job["output_bytes"] = None
    job["status"] = "running"
    return len(retry_blocks)


async def process_next_batch(
    job: dict,
    api_key: str,
    db_path: str,
    translate_func: TranslateFunc = translate_batches,
) -> dict:
    if job.get("status") != "running":
        return job
    if not job.get("pending_blocks"):
        job["status"] = "done"
        return job

    batch_size = int(job.get("batch_size") or 1)
    temperature = float(job.get("temperature") or 0)
    concurrency = int(job.get("concurrency") or 1)
    model = job.get("model") or config.MODEL
    base_url = job.get("base_url") or config.BASE_URL
    remaining = len(job["pending_blocks"])
    profile = job.get("translation_profile") or config.DEFAULT_TRANSLATION_PROFILE
    if profile == "fast":
        window_size = min(remaining, max(batch_size * max(concurrency, 1) * 2, batch_size))
    elif profile == "refine":
        window_size = min(remaining, max(batch_size, batch_size * max(concurrency, 1) // 2))
    else:
        window_size = min(remaining, max(batch_size * max(concurrency, 1), batch_size))
    batch = job["pending_blocks"][:window_size]
    started_at = time.time()

    options = TranslationOptions(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        batch_size=batch_size,
        concurrency=concurrency,
        custom_prompt=job.get("custom_prompt") or "",
        target_language=job.get("target_language") or config.DEFAULT_TARGET_LANGUAGE,
        glossary=job.get("glossary") or "",
        context=job.get("recent_context") or [],
        thinking_enabled=bool(job.get("thinking_enabled", config.DEFAULT_THINKING_ENABLED)),
        translation_profile=profile,
        style_preset=job.get("style_preset") or config.DEFAULT_STYLE_PRESET,
    )
    fresh_results, batch_failures = await translate_func(
        batch,
        options,
    )
    job["results_map"].update(fresh_results)
    job["failures"].extend(_attach_failed_blocks(batch_failures, batch))

    # Update sliding window context
    if fresh_results:
        recent = job.get("recent_context") or []
        for block in batch:
            if block["block_id"] in fresh_results:
                recent.append({
                    "original": block["text"],
                    "translation": fresh_results[block["block_id"]]
                })
        job["recent_context"] = recent[-5:]  # Keep last 5

    now_ts = int(time.time())
    rows = []
    for block in batch:
        translation = fresh_results.get(block["block_id"])
        if translation is None:
            continue
        rows.append(
            {
                "cache_key": block["cache_key"],
                "text_hash": block["text_hash"],
                "model": model,
                "prompt_version": config.PROMPT_VERSION,
                "params_json": job.get("params_json"),
                "translation": translation,
                "created_at": now_ts,
            }
        )
    set_many(db_path, rows)

    job["processed_blocks"] += len(batch)
    elapsed = time.time() - started_at
    completed_batches = int(job.get("batches_completed") or 0) + 1
    previous_avg = float(job.get("avg_batch_seconds") or 0.0)
    job["last_window_size"] = len(batch)
    job["last_batch_seconds"] = elapsed
    job["avg_batch_seconds"] = (
        elapsed if completed_batches == 1 else ((previous_avg * (completed_batches - 1)) + elapsed) / completed_batches
    )
    job["batches_completed"] = completed_batches
    job["last_update_time"] = time.time()
    job["pending_blocks"] = job["pending_blocks"][len(batch) :]
    if not job["pending_blocks"]:
        job["status"] = "done"
    return job


def ensure_output(job: dict, output_dir: str = "output") -> bytes | None:
    if job.get("output_bytes") is not None:
        return job["output_bytes"]
    if not job.get("epub_bytes"):
        return None

    output_bytes = inject_translations(job["epub_bytes"], job.get("results_map") or {})
    os.makedirs(output_dir, exist_ok=True)
    output_name = job.get("output_name") or "bilingual.epub"
    output_path = os.path.join(output_dir, output_name)
    with open(output_path, "wb") as file:
        file.write(output_bytes)
    job["output_bytes"] = output_bytes
    return output_bytes


def job_counts(job: dict) -> dict:
    total_count = job.get("total_blocks", 0)
    cache_hit_count = job.get("hit_count", 0)
    miss_count = job.get("miss_count")
    if miss_count is None:
        miss_count = max(total_count - cache_hit_count, 0)
    translated_count = len(job.get("results_map") or {})
    processed_count = int(job.get("processed_blocks") or 0)
    pending_count = len(job.get("pending_blocks") or [])
    elapsed_seconds = 0.0
    if job.get("start_time"):
        elapsed_seconds = max(0.0, time.time() - float(job["start_time"]))
    blocks_per_minute = (processed_count / elapsed_seconds * 60.0) if elapsed_seconds > 0 and processed_count else 0.0
    eta_seconds = (pending_count / blocks_per_minute * 60.0) if blocks_per_minute > 0 and pending_count else 0.0
    return {
        "total": total_count,
        "cache_hits": cache_hit_count,
        "misses": miss_count,
        "translated": translated_count,
        "placeholders": max(total_count - translated_count, 0),
        "failures": len(job.get("failures") or []),
        "blocks_per_minute": round(blocks_per_minute, 1),
        "eta_seconds": int(eta_seconds),
        "elapsed_seconds": int(elapsed_seconds),
    }
