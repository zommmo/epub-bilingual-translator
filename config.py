# 默认配置，占位值，后续可按需替换
BASE_URL = "https://api.example.com/v1"
MODEL = "your-model-name"
TEMPERATURE = 0.7
BATCH_SIZE = 4
CONCURRENCY = 4
DEFAULT_TARGET_LANGUAGE = "Chinese"
DEFAULT_THINKING_ENABLED = False
TARGET_LANGUAGES = ["Chinese", "English", "Japanese", "Korean", "French", "German", "Spanish"]
MAX_BLOCK_TOKENS = 900
TRANSLATION_PROFILES = ["fast", "balanced", "refine"]
DEFAULT_TRANSLATION_PROFILE = "balanced"
STYLE_PRESETS = {
    "auto": "",
    "literary": (
        "Write in polished literary prose. Preserve imagery, rhythm, subtext, emotional distance, and narrative voice. "
        "Prefer idiomatic phrasing over literal syntax, and let dialogue sound like something a native speaker would actually say."
    ),
    "faithful": (
        "Stay close to the source meaning, sequence of ideas, and level of detail while still writing idiomatic target-language prose. "
        "Do not embellish, simplify, or interpret beyond the source."
    ),
    "webnovel": (
        "Use vivid, highly readable genre-fiction prose. Keep dialogue punchy, scene movement clear, and emotional beats immediate. "
        "Avoid stiff literary over-polish when a direct, energetic line reads better."
    ),
    "nonfiction": (
        "Use precise, clear, low-ornament prose suitable for nonfiction. Prioritize terminology, logical flow, and readability. "
        "Keep metaphors and technical terms accurate rather than decorative."
    ),
}
DEFAULT_STYLE_PRESET = "literary"

# 翻译提示与容错设置
PROMPT_VERSION = "v2"


def build_system_prompt(
    target_language: str = DEFAULT_TARGET_LANGUAGE,
    profile: str = DEFAULT_TRANSLATION_PROFILE,
) -> str:
    language = (target_language or DEFAULT_TARGET_LANGUAGE).strip()
    mode = (profile or DEFAULT_TRANSLATION_PROFILE).strip().lower()
    quality_rule = {
        "fast": (
            "Produce a fluent first-pass translation that is accurate, readable, and terminology-consistent. "
            "Do not overwork the prose; prioritize speed and reliability."
        ),
        "balanced": (
            "Produce publishable, natural prose that preserves tone, pacing, implication, and authorial intent. "
            "Revise sentence structure when the source syntax would sound translated."
        ),
        "refine": (
            "Produce a polished editorial translation with strong sentence flow, voice consistency, and literary texture. "
            "Prefer the best native target-language reading experience over source-language word order."
        ),
    }.get(mode, "Prioritize natural, publishable prose while preserving tone, pacing, and intent.")
    return (
        "You are a senior book translator and bilingual copy editor. You only output strict JSON. "
        "Task: translate each source passage into the target language for an interleaved bilingual EPUB. "
        'Required output format: [{"id":"...","translation":"..."}]. '
        "Return one object for every input id, exactly once, and preserve the original ids unchanged. "
        f"Translations must be written in {language}. "
        f"{quality_rule} "
        "Preserve meaning, plot facts, speaker intent, register, imagery, pacing, paragraph boundaries, and dialogue energy. "
        "Use native target-language phrasing: restructure sentences, resolve pronouns, and adjust word order when needed for fluency. "
        "Keep names, places, factions, invented terms, honorifics, measurements, and repeated phrases consistent with the glossary and context. "
        "If a phrase is ambiguous, choose the translation that best fits the local context instead of explaining the ambiguity. "
        "Do not summarize, add commentary, censor, moralize, omit difficult content, or leave untranslated fragments unless the source itself is untranslated. "
        "Do not output Markdown, code fences, notes, headings, or any text outside the JSON array. "
        "Output must start with [ and end with ], with no extra characters."
    )


SYSTEM_PROMPT = build_system_prompt(DEFAULT_TARGET_LANGUAGE, DEFAULT_TRANSLATION_PROFILE)
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 5

DB_PATH = "translations.sqlite3"
