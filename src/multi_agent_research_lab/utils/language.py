"""Small language helpers for prompt conditioning."""

from __future__ import annotations

_VIETNAMESE_MARKERS = set(
    "ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"
)


def response_language_instruction(query: str) -> str:
    """Return a concise instruction to answer in the user's query language."""
    lowered = query.lower()
    if any(char in _VIETNAMESE_MARKERS for char in lowered) or any(
        token in lowered.split()
        for token in ("hãy", "là", "và", "của", "cho", "tôi", "như", "nào", "viết")
    ):
        return (
            "Language requirement: The user query is Vietnamese. Produce all substantive "
            "agent outputs in Vietnamese, including headings, analysis, final answer, "
            "critique, and references labels. Keep source titles/URLs unchanged."
        )
    return (
        "Language requirement: Match the language of the user's query in all substantive "
        "agent outputs. Keep source titles/URLs unchanged."
    )
