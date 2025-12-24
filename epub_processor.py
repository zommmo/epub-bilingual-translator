import hashlib
import os
import tempfile
from typing import Iterable

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def _normalize_text(text: str) -> str:
    # 归一化空白，便于稳定哈希与过滤
    return " ".join(text.split()).strip()


def _is_noise(text: str) -> bool:
    if not text:
        return True
    if len(text) < 5:
        return True
    if text.isdigit():
        return True
    # 纯符号文本：没有任何字母或数字
    if not any(char.isalnum() for char in text):
        return True
    return False


def _iter_text_nodes(soup: BeautifulSoup, tags: Iterable[str]):
    for node in soup.find_all(list(tags)):
        yield node.name, node.get_text(" ", strip=True)


def extract_blocks(epub_bytes: bytes) -> list[dict]:
    """
    解析 EPUB 并按文档顺序抽取文本块。
    """
    blocks: list[dict] = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(epub_bytes)
        temp_path = temp_file.name

    try:
        book = epub.read_epub(temp_path)
        # spine 是 EPUB 阅读顺序的目录列表，按此顺序抽取能保持章节顺序一致
        for spine_item in book.spine:
            item_id = spine_item[0] if isinstance(spine_item, (tuple, list)) else spine_item
            item = book.get_item_with_id(item_id)
            # 双保险：类型常量+具体类判断，兼容不同版本的 EbookLib
            if not item or (
                item.get_type() != ebooklib.ITEM_DOCUMENT and not isinstance(item, epub.EpubHtml)
            ):
                continue

            doc_name = item.get_name()
            soup = BeautifulSoup(item.get_content(), "lxml")
            index = 0
            for tag, raw_text in _iter_text_nodes(
                soup, ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]
            ):
                normalized = _normalize_text(raw_text)
                if _is_noise(normalized):
                    continue
                text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                # block_id 用文档名+标签+序号定位唯一块，便于追踪来源
                block_id = f"{doc_name}::{tag}::{index}"
                blocks.append(
                    {
                        "block_id": block_id,
                        "doc_name": doc_name,
                        "tag": tag,
                        "index": index,
                        "text": normalized,
                        # hash 是基于归一化文本的指纹，用于去重或一致性校验
                        "text_hash": text_hash,
                    }
                )
                index += 1
    finally:
        os.remove(temp_path)

    return blocks
