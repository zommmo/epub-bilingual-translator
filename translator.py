import asyncio
import json
import re
from typing import Dict, List, Tuple

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

import config
from translation_types import TranslationOptions


class TranslationError(Exception):
    """自定义异常用于触发重试"""


THINKING_PROVIDER_HINTS = ("qwen", "dashscope", "aliyun", "aliyuncs", "tongyi")


def should_send_thinking_control(base_url: str, model: str, thinking_enabled: bool) -> bool:
    if thinking_enabled:
        return True
    haystack = f"{base_url} {model}".lower()
    return any(hint in haystack for hint in THINKING_PROVIDER_HINTS)


def build_chat_payload(
    model: str,
    temperature: float,
    messages: list[dict],
    base_url: str = "",
    thinking_enabled: bool = config.DEFAULT_THINKING_ENABLED,
) -> dict:
    payload = {
        "model": model,
        "temperature": float(temperature),
        "messages": messages,
    }
    if should_send_thinking_control(base_url, model, thinking_enabled):
        payload["enable_thinking"] = bool(thinking_enabled)
    return payload


async def _call_model(client: httpx.AsyncClient, payload: dict) -> str:
    # 结构化 JSON 响应能保证段落不乱序，可精确按 id 对齐
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(TranslationError),
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(config.MAX_RETRIES),
    ):
        with attempt:
            try:
                resp = await client.post(
                    "/chat/completions",
                    json=payload,
                    timeout=config.DEFAULT_TIMEOUT,
                )
                if resp.status_code != 200:
                    body_snippet = resp.text[:200]
                    if resp.status_code in {429, 500, 502, 503, 504}:
                        raise TranslationError(
                            f"server busy: {resp.status_code}; body_snippet={body_snippet}"
                        )
                    raise TranslationError(
                        f"bad status: {resp.status_code}; body_snippet={body_snippet}"
                    )
                try:
                    data = resp.json()
                except Exception as exc:
                    raise TranslationError(f"json decode failed: {exc}")

                try:
                    return data["choices"][0]["message"]["content"]
                except Exception as exc:
                    raise TranslationError(f"parse response failed: {exc}")
            except httpx.HTTPError as exc:
                raise TranslationError(f"http error: {exc}")
            except TranslationError:
                raise
            except Exception as exc:
                raise TranslationError(f"unexpected error: {exc}")
    raise TranslationError("exceeded retries")


def extract_json_array(text: str) -> list:
    # 模型偶尔会输出 Markdown 包装或夹带说明，先容错提取 JSON 避免解析失败
    raw_text = text
    cleaned = text.strip()
    if "```" in cleaned:
        lines = []
        for line in cleaned.splitlines():
            if line.strip().startswith("```"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    candidate = cleaned
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except Exception as exc:
        snippet = raw_text[:200]
        raise TranslationError(
            f"response json parse failed: {exc}; 原始返回片段前 200 字符: {snippet}"
        )

    if not isinstance(parsed, list):
        raise TranslationError("response is not a list")
    return parsed


def _chunk_list(items: List[dict], size: int) -> List[List[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _resolve_style_prompt(style_preset: str, custom_prompt: str) -> str:
    preset = config.STYLE_PRESETS.get((style_preset or "").strip(), "")
    custom = (custom_prompt or "").strip()
    if preset and custom:
        return f"{preset}\nAdditional instruction: {custom}"
    return preset or custom


def _build_context_excerpt(context: list[dict] | None, profile: str) -> str:
    if not context:
        return ""
    limit = 2 if profile == "fast" else 5
    excerpt_lines = ["<context>", "Use this previous context only for continuity, pronoun resolution, tone, and terminology. Do not translate this section."]
    for ctx in context[-limit:]:
        excerpt_lines.append(f"Source: {ctx['original']}")
        excerpt_lines.append(f"Target: {ctx['translation']}")
    excerpt_lines.append("</context>")
    return "\n".join(excerpt_lines)


def _validate_translation_items(parsed: list, batch: List[dict]) -> Dict[str, str]:
    translations: Dict[str, str] = {}
    for item in parsed:
        if not isinstance(item, dict) or "id" not in item or "translation" not in item:
            raise TranslationError("response item missing fields")
        translations[str(item["id"])] = str(item["translation"])

    input_ids = {b["block_id"] for b in batch}
    received_ids = set(translations)
    if received_ids != input_ids:
        missing = sorted(input_ids - received_ids)
        extra = sorted(received_ids - input_ids)
        details = []
        if missing:
            details.append(f"missing ids: {len(missing)}")
        if extra:
            details.append(f"extra ids: {len(extra)}")
        raise TranslationError("response ids mismatch input" + (f" ({', '.join(details)})" if details else ""))
    return translations


def sample_blocks_for_glossary(blocks: List[dict], max_chars: int = 18000) -> List[str]:
    if not blocks or max_chars <= 0:
        return []

    total_chars = sum(len(block.get("text", "")) for block in blocks)
    if total_chars <= max_chars:
        return [block["text"] for block in blocks if block.get("text")]

    sample_points = [0, len(blocks) // 3, (len(blocks) * 2) // 3]
    per_section = max(1, max_chars // len(sample_points))
    seen_ids = set()
    samples: List[str] = []
    remaining_budget = max_chars

    for start_index in sample_points:
        section_chars = 0
        for block in blocks[start_index:]:
            if remaining_budget <= 0 or section_chars >= per_section:
                break
            block_id = block.get("block_id")
            if block_id in seen_ids:
                continue
            text = (block.get("text") or "").strip()
            if not text:
                continue
            samples.append(text)
            seen_ids.add(block_id)
            section_chars += len(text)
            remaining_budget -= len(text)

    return samples


async def _run_refinement_pass(
    client: httpx.AsyncClient,
    parsed: list[dict],
    source_text_by_id: dict[str, str],
    target_language: str,
    glossary: str,
    style_instruction: str,
    model: str,
    temperature: float,
    base_url: str,
    thinking_enabled: bool,
) -> list[dict]:
    payload_items = []
    for item in parsed:
        item_id = item["id"]
        payload_items.append(
            {
                "id": item_id,
                "source": source_text_by_id.get(item_id, ""),
                "draft": item["translation"],
            }
        )
    user_lines = [
        "Polish the draft translations for natural target-language prose.",
        "Keep source meaning, names, facts, paragraph boundaries, and ids unchanged.",
        "Improve rhythm, word choice, dialogue flow, and idiomatic phrasing.",
        "Return the same JSON array schema with id and translation only.",
    ]
    if glossary.strip():
        user_lines.extend(["<glossary>", glossary.strip(), "</glossary>"])
    if style_instruction.strip():
        user_lines.extend(["<style>", style_instruction.strip(), "</style>"])
    user_lines.append(f"<drafts_json>{json.dumps(payload_items, ensure_ascii=False)}</drafts_json>")
    messages = [
        {"role": "system", "content": config.build_system_prompt(target_language, "refine")},
        {"role": "user", "content": "\n".join(user_lines)},
    ]
    payload = build_chat_payload(
        model=model,
        temperature=min(max(float(temperature), 0.2), 1.0),
        messages=messages,
        base_url=base_url,
        thinking_enabled=thinking_enabled,
    )
    refined_content = await _call_model(client, payload)
    return extract_json_array(refined_content)


def estimate_token_count(text: str, model: str = "") -> int:
    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text or ""))
    except Exception:
        return max(1, len(text or "") // 4)


def _split_piece_by_estimate(piece: str, max_tokens: int, model: str) -> List[str]:
    pending = piece.strip()
    chunks = []
    while pending and estimate_token_count(pending, model) > max_tokens:
        low = 1
        high = len(pending)
        best = 1
        while low <= high:
            mid = (low + high) // 2
            if estimate_token_count(pending[:mid], model) <= max_tokens:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        boundary = best
        prefix = pending[:best]
        matches = list(re.finditer(r"[\s,.;:!?，。；：！？、]", prefix))
        if matches and matches[-1].end() >= max(1, best // 2):
            boundary = matches[-1].end()

        chunk = pending[:boundary].strip()
        if not chunk:
            chunk = pending[:best].strip() or pending[:1]
            boundary = len(chunk)
        chunks.append(chunk)
        pending = pending[boundary:].strip()

    if pending:
        chunks.append(pending)
    return chunks


def split_text_for_translation(
    text: str,
    max_tokens: int = config.MAX_BLOCK_TOKENS,
    model: str = "",
) -> List[str]:
    normalized = (text or "").strip()
    if not normalized:
        return [""]
    if max_tokens <= 0 or estimate_token_count(normalized, model) <= max_tokens:
        return [normalized]

    sentences = [
        item.strip()
        for item in re.split(r"(?<=[.!?。！？；;])\s+|\n+", normalized)
        if item.strip()
    ] or [normalized]

    chunks = []
    current = ""
    for sentence in sentences:
        if estimate_token_count(sentence, model) > max_tokens:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_piece_by_estimate(sentence, max_tokens, model))
            continue

        candidate = f"{current} {sentence}".strip()
        if current and estimate_token_count(candidate, model) > max_tokens:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def _build_translation_units(blocks: List[dict], model: str) -> tuple[List[dict], Dict[str, List[dict]]]:
    units = []
    units_by_parent: Dict[str, List[dict]] = {}
    for block in blocks:
        parent_id = block["block_id"]
        chunks = split_text_for_translation(block.get("text", ""), config.MAX_BLOCK_TOKENS, model)
        units_by_parent[parent_id] = []
        for index, chunk in enumerate(chunks):
            unit = dict(block)
            unit["parent_block_id"] = parent_id
            unit["chunk_index"] = index
            unit["chunk_count"] = len(chunks)
            unit["text"] = chunk
            if len(chunks) > 1:
                unit["block_id"] = f"{parent_id}::part::{index}"
            units.append(unit)
            units_by_parent[parent_id].append(unit)
    return units, units_by_parent


async def translate_batches(
    blocks: List[dict],
    options: TranslationOptions,
) -> Tuple[Dict[str, str], List[dict]]:
    """
    批量翻译：返回成功映射与失败列表。
    返回 mapping: id -> translation
    failures: {id, reason, text_snippet}
    custom_prompt: 仅作为风格说明，系统提示保持固定以保证 JSON 解析稳定。
    target_language: 目标语言名称，例如 Chinese、English、Japanese。
    """

    if not blocks:
        return {}, []

    api_key = options.api_key
    base_url = options.base_url
    model = options.model
    temperature = options.temperature
    batch_size = options.batch_size
    concurrency = options.concurrency
    custom_prompt = options.custom_prompt
    target_language = options.target_language
    glossary = options.glossary
    context = options.context
    thinking_enabled = options.thinking_enabled
    translation_profile = options.translation_profile
    style_preset = options.style_preset

    headers = {"Authorization": f"Bearer {api_key}"}
    # 使用 semaphore 控制并发，避免过高并发触发限流
    semaphore = asyncio.Semaphore(concurrency)
    units, units_by_parent = _build_translation_units(blocks, model)
    unit_results: Dict[str, str] = {}
    unit_failures: List[dict] = []

    async def request_batch(batch: List[dict]) -> Dict[str, str]:
        user_payload = [{"id": b["block_id"], "text": b["text"]} for b in batch]
        user_content_parts = [
            "Translate the passages in <passages_json> into natural target-language prose.",
            "Return only a JSON array. Each item must contain exactly the original id and its translation.",
        ]
        glossary_prompt = (glossary or "").strip()
        if glossary_prompt:
            user_content_parts.extend(["<glossary>", glossary_prompt, "</glossary>"])
        style_prompt = _resolve_style_prompt(style_preset, custom_prompt)
        if style_prompt:
            user_content_parts.extend(["<style>", style_prompt, "</style>"])
        context_excerpt = _build_context_excerpt(context, translation_profile)
        if context_excerpt:
            user_content_parts.append(context_excerpt)
        user_content_parts.extend(
            [
                "<translation_rules>",
                "- Translate meaning, tone, and narrative function, not source-language word order.",
                "- Make dialogue sound native, character-appropriate, and speakable.",
                "- Preserve paragraph boundaries; do not merge, split, summarize, or annotate passages.",
                "- Keep numbers, names, invented terms, formatting-sensitive punctuation, and repeated phrases consistent.",
                "- If literal wording sounds unnatural, choose an idiomatic equivalent that preserves intent.",
                "- Do not explain, summarize, censor, add notes, or wrap output in Markdown.",
                "</translation_rules>",
            ]
        )
        messages = [
            {
                "role": "system",
                "content": config.build_system_prompt(target_language, translation_profile),
            },
                {
                    "role": "user",
                    "content": "\n".join(user_content_parts)
                    + f"\n<passages_json>{json.dumps(user_payload, ensure_ascii=False)}</passages_json>",
                },
            ]
        payload = build_chat_payload(
            model=model,
            temperature=temperature,
            messages=messages,
            base_url=base_url,
            thinking_enabled=thinking_enabled,
        )
        content = await _call_model(client, payload)
        parsed = extract_json_array(content)
        if translation_profile == "refine":
            parsed = await _run_refinement_pass(
                client,
                parsed,
                {b["block_id"]: b["text"] for b in batch},
                target_language,
                glossary_prompt,
                style_prompt,
                model,
                temperature,
                base_url,
                thinking_enabled,
            )
        return _validate_translation_items(parsed, batch)

    async def request_with_fallback(batch: List[dict]) -> None:
        try:
            unit_results.update(await request_batch(batch))
            return
        except Exception as exc:
            if len(batch) <= 1:
                for b in batch:
                    unit_failures.append(
                        {
                            "id": b["block_id"],
                            "reason": str(exc),
                            "text_snippet": b.get("text", "")[:50],
                        }
                    )
                return

        midpoint = max(1, len(batch) // 2)
        await request_with_fallback(batch[:midpoint])
        await request_with_fallback(batch[midpoint:])

    async def handle_batch(batch: List[dict]):
        async with semaphore:
            await request_with_fallback(batch)

    batches = _chunk_list(units, batch_size)
    async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
        await asyncio.gather(*(handle_batch(batch) for batch in batches))

    failures_by_unit = {failure["id"]: failure for failure in unit_failures}
    results: Dict[str, str] = {}
    failures: List[dict] = []
    for block in blocks:
        parent_id = block["block_id"]
        parent_units = units_by_parent.get(parent_id, [])
        unit_ids = [unit["block_id"] for unit in parent_units]
        failed = [failures_by_unit[unit_id] for unit_id in unit_ids if unit_id in failures_by_unit]
        missing = [unit_id for unit_id in unit_ids if unit_id not in unit_results and unit_id not in failures_by_unit]
        if failed or missing:
            reasons = [failure.get("reason", "") for failure in failed]
            if missing:
                reasons.append(f"missing translated chunks: {len(missing)}")
            failures.append(
                {
                    "id": parent_id,
                    "reason": "; ".join(reason for reason in reasons if reason),
                    "text_snippet": block.get("text", "")[:50],
                }
            )
            continue
        results[parent_id] = "\n".join(unit_results[unit_id] for unit_id in unit_ids)

    return results, failures


async def generate_glossary(
    blocks: List[dict],
    api_key: str,
    base_url: str,
    model: str,
    target_language: str,
    thinking_enabled: bool = config.DEFAULT_THINKING_ENABLED,
) -> str:
    text_samples = sample_blocks_for_glossary(blocks)
    if not text_samples:
        return ""
    
    sample_text = "\n\n".join(text_samples)
    
    system_prompt = (
        f"You are a translation assistant. Extract main character names, locations, and unique proper nouns from the text. "
        f"Provide their translation in {target_language}. "
        "Return ONLY a valid JSON dictionary where keys are original names and values are translations. "
        "Do not output markdown code blocks or any explanations, just the JSON object."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Text:\n{sample_text}"}
    ]
    
    payload = build_chat_payload(
        model=model,
        temperature=0.3,
        messages=messages,
        base_url=base_url,
        thinking_enabled=thinking_enabled,
    )
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=120.0) as client:
        try:
            content = await _call_model(client, payload)
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(json)?|```$", "", content).strip()
            data = json.loads(content)
            if isinstance(data, dict):
                return "\n".join([f"{k}={v}" for k, v in data.items() if isinstance(k, str) and isinstance(v, str)])
            return ""
        except Exception as e:
            raise TranslationError(f"Glossary extraction failed: {str(e)}")
