import re
import tiktoken

_enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    """Accurately count tokens using tiktoken (cl100k_base)."""
    return len(_enc.encode(text, disallowed_special=()))

def group_blocks(content: str) -> list[str]:
    lines = [L.strip() for L in content.split("\n") if L.strip()]
    blocks = []
    current_block = []
    
    for line in lines:
        is_table_row = line.startswith('|') and line.endswith('|')
        if is_table_row:
            current_block.append(line)
        else:
            if current_block:
                blocks.append("\n".join(current_block))
                current_block = []
            blocks.append(line)
            
    if current_block:
        blocks.append("\n".join(current_block))
        
    return blocks


def chunk_section(
    content: str,
    header: str,
    section_title: str = "",
    max_tokens: int = 2500,
) -> list[str]:
    """Single unified chunking strategy: one chunk per section, split only if > max_tokens.
    Tables are kept in their entirety unless they exceed the limit."""
    prefix = f"Section: {section_title}\n\n" if section_title else ""
    full_header = f"{header}\n\n{prefix}" if prefix else header + "\n\n"
    header_tokens = count_tokens(full_header)
    content_tokens = count_tokens(content)

    if content_tokens + header_tokens <= max_tokens:
        return [f"{full_header}{content}"] if content.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    max_body_tokens = max_tokens - header_tokens

    blocks = group_blocks(content)

    for block in blocks:
        block_tokens = count_tokens(block)
        
        if block_tokens > max_body_tokens:
            if current:
                chunks.append(f"{full_header}" + "\n".join(current))
                current = []
                current_tokens = 0
                
            block_enc = _enc.encode(block, disallowed_special=())
            for i in range(0, len(block_enc), max_body_tokens):
                hard_chunk = _enc.decode(block_enc[i:i + max_body_tokens])
                chunks.append(f"{full_header}{hard_chunk}")
            continue

        if current_tokens + block_tokens > max_body_tokens and current:
            chunks.append(f"{full_header}" + "\n".join(current))
            current = []
            current_tokens = 0
            
        current.append(block)
        current_tokens += block_tokens
    
    if current:
        chunks.append(f"{full_header}" + "\n".join(current))
    
    return chunks


# ---------------------------------------------------------------------------
# Small-chunk safety net
# ---------------------------------------------------------------------------

MIN_CHUNK_TOKENS = 100


def merge_small_chunks(
    chunks: list[tuple[str, str]],
    max_tokens: int = 2500,
) -> list[tuple[str, str]]:
    """Merge any chunk below MIN_CHUNK_TOKENS into its predecessor.

    Walk the flat ``(content, section)`` list produced by the pipeline and
    try to append any short chunk to the previous one.  When that is not
    possible (no predecessor yet, or merger would exceed ``max_tokens``), the
    short chunk is held *pending* and prepended to the **next** chunk.  Any
    chunk that is still too small after all merges (e.g. a lone
    "Not applicable." at the very end of a filing) is silently discarded.
    """
    if not chunks:
        return []

    result: list[tuple[str, str]] = []
    pending: tuple[str, str] | None = None  # short chunk waiting to merge forward

    for content, section in chunks:
        # Prepend any pending short chunk from the previous iteration
        if pending is not None:
            combined = pending[0] + "\n" + content
            if count_tokens(combined) <= max_tokens:
                content = combined
                # Keep the pending section label if the current one is empty
                section = pending[1] if pending[1] else section
            # If it doesn't fit, silently discard the pending chunk
            pending = None

        tok = count_tokens(content)

        if tok < MIN_CHUNK_TOKENS:
            # Try to merge backward into the last result chunk
            if result:
                prev_content, prev_section = result[-1]
                merged = prev_content + "\n" + content
                if count_tokens(merged) <= max_tokens:
                    result[-1] = (merged, prev_section)
                    continue
            # Can't merge backward — hold it and try to merge forward
            pending = (content, section)
            continue

        result.append((content, section))

    # Any remaining pending chunk that meets the minimum threshold is kept
    if pending is not None and count_tokens(pending[0]) >= MIN_CHUNK_TOKENS:
        result.append(pending)
    # Otherwise it is discarded (truly too small to be useful)

    return result
