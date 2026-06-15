from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import redis


# -----------------------------
# Data structures
# -----------------------------


@dataclass
class StepComment:
    """Feedback from a supervisor/evaluator for one step."""

    step_id: str
    comments: List[str]
    score: float
    generated_checks: Optional[Any] = None
    context: Optional[str] = None


@dataclass
class MemoryRecord:
    """Canonical memory item stored in Redis."""

    memory_id: str
    text: str
    category: str
    importance: int = 5
    hits: int = 1
    last_seen: str = field(default_factory=lambda: _dt.date.today().isoformat())
    success_after_use: int = 0
    source: str = "evaluator"
    examples: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _dt.datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: _dt.datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            memory_id=data["memory_id"],
            text=data["text"],
            category=data.get("category", "misc"),
            importance=int(data.get("importance", 5)),
            hits=int(data.get("hits", 1)),
            last_seen=data.get("last_seen", _dt.date.today().isoformat()),
            success_after_use=int(data.get("success_after_use", 0)),
            source=data.get("source", "evaluator"),
            examples=list(data.get("examples", []) or []),
            created_at=data.get("created_at", _dt.datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", _dt.datetime.utcnow().isoformat()),
        )


@dataclass
class ConsolidatedMemoryUpdate:
    """Result of consolidation for a batch of comments."""

    new_items: List[MemoryRecord] = field(default_factory=list)
    updated_items: List[MemoryRecord] = field(default_factory=list)
    ignored_comments: List[str] = field(default_factory=list)


# -----------------------------
# Utility functions
# -----------------------------


_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_\-]{2,}")
_WS_RE = re.compile(r"\s+")


DEFAULT_CATEGORY_RULES: List[Tuple[str, Sequence[str]]] = [
    ("duplication", ["дубли", "duplicate", "повтор", "same check", "same state", "repeated"]),
    ("missing_negative", ["negative", "негатив", "invalid", "невалид", "ошибк", "failure", "not handled"]),
    ("missing_assertion", ["assert", "провер", "expected", "ожид", "verify", "validate"]),
    ("coverage_gap", ["coverage", "покрыт", "branch", "ветк", "path", "route"]),
    ("ordering", ["order", "sequence", "последоват", "step", "sequence"]),
    ("state_leak", ["state", "состояни", "leak", "shared", "persist", "reset"]),
    ("data_dependency", ["depends", "dependency", "завис", "previous", "prior", "раньше"]),
    ("flaky", ["flaky", "unstable", "нестаб", "random", "intermittent"]),
    ("overgeneralized", ["too broad", "overgeneral", "general", "слишком общ", "vague", "неяс"]),
    ("wrong_target", ["wrong endpoint", "не тот endpoint", "wrong step", "incorrect", "mismatch"]),
]


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "is", "are",
    "be", "this", "that", "it", "as", "at", "by", "from", "за", "на", "и", "в", "к",
    "по", "для", "что", "это", "как", "не", "ни", "то", "the", "step", "шаг",
}


def _today_iso() -> str:
    return _dt.date.today().isoformat()


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().isoformat()


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def normalize_text(text: str) -> str:
    text = text.strip()
    text = _WS_RE.sub(" ", text)
    return text


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


def canonicalize_comment(text: str) -> str:
    """Reduce a raw comment to a compact canonical form.

    Conservative on purpose: it keeps the meaning but removes details that
    often create duplicate memories.
    """
    text = normalize_text(text)
    text = text.lower()

    replacements = [
        (r"\bshould\b", "need to"),
        (r"\bmust\b", "need to"),
        (r"\bneeds to\b", "need to"),
        (r"\bнеобходимо\b", "нужно"),
        (r"\bследует\b", "нужно"),
        (r"\bпроверьте\b", "проверить"),
        (r"\bпроверить\b", "проверка"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    # Remove boilerplate phrases that often appear in evaluator comments.
    boilerplate = [
        r"\bв данном случае\b",
        r"\bна данном шаге\b",
        r"\bв целом\b",
        r"\bскорее всего\b",
        r"\bвозможно\b",
        r"\bit looks like\b",
        r"\bmay be\b",
        r"\bshould probably\b",
    ]
    for pattern in boilerplate:
        text = re.sub(pattern, "", text)

    text = _WS_RE.sub(" ", text).strip(" .,:;\n\t")
    return text


def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    tokens = [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 2]
    counts = Counter(tokens)
    return [w for w, _ in counts.most_common(max_keywords)]


def infer_category(text: str) -> str:
    t = text.lower()
    for category, keywords in DEFAULT_CATEGORY_RULES:
        if any(k in t for k in keywords):
            return category
    return "misc"


def memory_id_from_text(text: str, category: str) -> str:
    digest = hashlib.sha1(f"{category}|{text}".encode("utf-8")).hexdigest()[:10]
    return f"mem_{digest}"


def similarity_score(a: str, b: str) -> float:
    """A lightweight text similarity heuristic without embeddings."""
    ta = set(tokenize(a)) - STOPWORDS
    tb = set(tokenize(b)) - STOPWORDS
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb)
    union = len(ta | tb)
    jaccard = overlap / union

    # Boost exact phrase overlap.
    phrases = [
        "no duplicate",
        "not enough coverage",
        "missing assertion",
        "empty response",
        "negative case",
        "invalid input",
        "state leak",
        "wrong endpoint",
    ]
    phrase_boost = 0.0
    lower_a = a.lower()
    lower_b = b.lower()
    for ph in phrases:
        if ph in lower_a and ph in lower_b:
            phrase_boost += 0.12

    return min(1.0, jaccard + phrase_boost)


# -----------------------------
# Memory node
# -----------------------------


class MemoryNode:
    """Consolidates evaluator comments and stores canonical memories in Redis."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        namespace: str = "agent_memory",
        top_k_default: int = 10,
        max_new_items_per_batch: int = 8,
        min_importance_to_keep: int = 1,
        similarity_threshold: float = 0.55,
        summarizer: Optional[Callable[[List[str], Optional[str]], str]] = None,
    ) -> None:
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self.namespace = namespace
        self.top_k_default = top_k_default
        self.max_new_items_per_batch = max_new_items_per_batch
        self.min_importance_to_keep = min_importance_to_keep
        self.similarity_threshold = similarity_threshold
        self.summarizer = summarizer

        self._mem_key_prefix = f"{self.namespace}:mem:"
        self._rank_key = f"{self.namespace}:rank"
        self._seen_key = f"{self.namespace}:seen"
        self._batch_key_prefix = f"{self.namespace}:batch:"

    # -------------------------
    # Public API
    # -------------------------

    def ingest_evaluator_feedback(
        self,
        evaluator_score: float,
        comments_by_step: Dict[str, List[str]],
        generated_checks_by_step: Optional[Dict[str, Any]] = None,
        process_context: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> ConsolidatedMemoryUpdate:
        """Main entry point.

        Parameters
        ----------
        evaluator_score:
            Global evaluation score (e.g. 0..5).
        comments_by_step:
            Mapping step_id -> list of raw evaluator comments.
        generated_checks_by_step:
            Optional generated checks per step; used only for better normalization.
        process_context:
            Short description of the current process / scenario.
        run_id:
            Optional run identifier for debugging / audit.
        """
        batch_update = ConsolidatedMemoryUpdate()
        now = _utc_now_iso()

        # 1) Flatten comments into normalized candidates.
        candidates: List[Tuple[str, str, str]] = []
        for step_id, raw_comments in comments_by_step.items():
            for raw_comment in raw_comments or []:
                cleaned = canonicalize_comment(raw_comment)
                if not cleaned:
                    batch_update.ignored_comments.append(raw_comment)
                    continue
                category = infer_category(cleaned)
                candidates.append((step_id, cleaned, category))

        if not candidates:
            return batch_update

        # 2) Consolidate candidates into canonical texts.
        grouped: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for step_id, cleaned, category in candidates:
            key = (category, self._coarse_signature(cleaned))
            grouped[key].append(cleaned)

        if self.summarizer is not None:
            summary_input = [f"[{step}] {comment}" for step, comment, _ in candidates]
            summarized_text = self.summarizer(summary_input, process_context)
            if summarized_text:
                summarized_text = canonicalize_comment(summarized_text)
                category = infer_category(summarized_text)
                grouped[(category, self._coarse_signature(summarized_text))].append(summarized_text)

        # 3) Update or create records.
        created = 0
        for (category, _signature), texts in grouped.items():
            canonical_text = self._choose_canonical_text(texts, process_context=process_context)
            if not canonical_text:
                continue

            existing = self._find_best_match(canonical_text, category)
            if existing is None:
                if created >= self.max_new_items_per_batch:
                    continue
                record = MemoryRecord(
                    memory_id=memory_id_from_text(canonical_text, category),
                    text=canonical_text,
                    category=category,
                    importance=self._initial_importance(evaluator_score, canonical_text, category),
                    hits=1,
                    last_seen=_today_iso(),
                    success_after_use=0,
                    source="evaluator",
                    examples=self._collect_examples(texts),
                    created_at=now,
                    updated_at=now,
                )
                self._save_record(record)
                batch_update.new_items.append(record)
                created += 1
                continue

            updated = self._update_existing_record(
                existing,
                canonical_text=canonical_text,
                example_texts=texts,
                evaluator_score=evaluator_score,
                now=now,
                run_id=run_id,
            )
            batch_update.updated_items.append(updated)

        # 4) Apply cleanup policies.
        self._cleanup_low_value_items()
        self._trim_rank_to_keep_top()
        return batch_update

    def get_top_memories(self, k: Optional[int] = None) -> List[MemoryRecord]:
        k = k or self.top_k_default
        ranked = self.redis.zrevrange(self._rank_key, 0, k - 1)
        out: List[MemoryRecord] = []
        for memory_id in ranked:
            raw = self.redis.get(f"{self._mem_key_prefix}{memory_id}")
            if not raw:
                continue
            out.append(MemoryRecord.from_dict(json.loads(raw)))
        return out

    def export_memory(self) -> List[Dict[str, Any]]:
        ids = self.redis.zrevrange(self._rank_key, 0, -1)
        result: List[Dict[str, Any]] = []
        for memory_id in ids:
            raw = self.redis.get(f"{self._mem_key_prefix}{memory_id}")
            if raw:
                result.append(json.loads(raw))
        return result

    def get_memory_prompt_block(self, k: Optional[int] = None) -> str:
        memories = self.get_top_memories(k)
        if not memories:
            return ""
        lines = []
        for idx, mem in enumerate(memories, start=1):
            lines.append(
                f"{idx}. [{mem.category}] {mem.text} "
                f"(importance={mem.importance}, hits={mem.hits}, last_seen={mem.last_seen})"
            )
        return "\n".join(lines)

    # -------------------------
    # Internal consolidation
    # -------------------------

    def _choose_canonical_text(self, texts: List[str], process_context: Optional[str] = None) -> str:
        if not texts:
            return ""
        # Prefer a compact, frequent, and general phrase.
        freqs = Counter(texts)
        ranked = sorted(
            freqs.items(),
            key=lambda kv: (
                -kv[1],
                len(kv[0]),
                -self._generalness_score(kv[0], process_context=process_context),
            ),
        )
        best = ranked[0][0]
        return self._shorten(best)

    def _shorten(self, text: str, max_words: int = 16) -> str:
        words = text.split()
        if len(words) <= max_words:
            return text
        return " ".join(words[:max_words]).rstrip(".,;:")

    def _generalness_score(self, text: str, process_context: Optional[str] = None) -> float:
        # Texts that are less context-specific are preferred as memory items.
        score = 0.0
        if process_context:
            ctx_tokens = set(tokenize(process_context))
            txt_tokens = set(tokenize(text))
            overlap = len(ctx_tokens & txt_tokens)
            score -= overlap
        if any(token.isdigit() for token in tokenize(text)):
            score -= 2.0
        if len(text.split()) <= 8:
            score += 1.0
        return score

    def _coarse_signature(self, text: str) -> str:
        # Build a crude semantic signature from the most informative keywords.
        kws = extract_keywords(text, max_keywords=4)
        return "|".join(sorted(kws))

    def _find_best_match(self, text: str, category: str) -> Optional[MemoryRecord]:
        best: Optional[MemoryRecord] = None
        best_score = 0.0
        for memory_id in self.redis.zrevrange(self._rank_key, 0, -1):
            raw = self.redis.get(f"{self._mem_key_prefix}{memory_id}")
            if not raw:
                continue
            record = MemoryRecord.from_dict(json.loads(raw))
            if record.category != category and record.category != "misc" and category != "misc":
                continue
            score = similarity_score(text, record.text)
            if score > best_score:
                best_score = score
                best = record
        if best is not None and best_score >= self.similarity_threshold:
            return best
        return None

    def _collect_examples(self, texts: List[str], limit: int = 3) -> List[str]:
        out: List[str] = []
        for text in texts:
            cleaned = self._shorten(text, max_words=24)
            if cleaned not in out:
                out.append(cleaned)
            if len(out) >= limit:
                break
        return out

    def _initial_importance(self, evaluator_score: float, text: str, category: str) -> int:
        # Lower supervisor score -> stronger need to remember.
        # Repeated/critical categories get a slightly higher base.
        base = 4
        if evaluator_score < 2:
            base += 3
        elif evaluator_score < 3:
            base += 2
        elif evaluator_score < 4:
            base += 1

        if category in {"missing_negative", "missing_assertion", "coverage_gap", "state_leak", "wrong_target"}:
            base += 1

        if len(extract_keywords(text, 5)) <= 2:
            base -= 1

        return clamp(base, 1, 10)

    # -------------------------
    # Redis operations
    # -------------------------

    def _save_record(self, record: MemoryRecord) -> None:
        record.importance = clamp(record.importance, 1, 10)
        payload = json.dumps(record.to_dict(), ensure_ascii=False)
        mem_key = f"{self._mem_key_prefix}{record.memory_id}"
        self.redis.set(mem_key, payload)
        self.redis.zadd(self._rank_key, {record.memory_id: record.importance})
        self.redis.sadd(self._seen_key, record.memory_id)

    def _update_existing_record(
        self,
        existing: MemoryRecord,
        canonical_text: str,
        example_texts: List[str],
        evaluator_score: float,
        now: str,
        run_id: Optional[str] = None,
    ) -> MemoryRecord:
        existing.hits += 1
        existing.last_seen = _today_iso()
        existing.updated_at = now
        existing.examples = self._merge_examples(existing.examples, example_texts)

        # If the new canonical text is more concise/generic, replace the old one.
        if self._should_replace_text(existing.text, canonical_text):
            existing.text = canonical_text

        delta = 1
        if evaluator_score < 4:
            delta += 1
        if evaluator_score < 3:
            delta += 1
        if existing.category in {"missing_negative", "missing_assertion", "coverage_gap", "state_leak", "wrong_target"}:
            delta += 1

        existing.importance = clamp(existing.importance + delta, 1, 10)

        # Heuristic success signal: if the memory is actively updated after low scores,
        # it is probably useful.
        if evaluator_score < 4:
            existing.success_after_use = clamp(existing.success_after_use + 1, 0, 9999)
        elif evaluator_score >= 4 and existing.success_after_use > 0:
            existing.success_after_use = clamp(existing.success_after_use + 1, 0, 9999)

        self._save_record(existing)
        return existing

    def _should_replace_text(self, old_text: str, new_text: str) -> bool:
        if not old_text:
            return True
        if len(new_text) < len(old_text) and similarity_score(old_text, new_text) >= 0.6:
            return True
        if self._generalness_score(new_text) > self._generalness_score(old_text):
            return True
        return False

    def _merge_examples(self, existing_examples: List[str], new_examples: List[str], limit: int = 5) -> List[str]:
        merged: List[str] = []
        for ex in existing_examples + new_examples:
            ex = normalize_text(ex)
            if ex and ex not in merged:
                merged.append(ex)
            if len(merged) >= limit:
                break
        return merged

    def _cleanup_low_value_items(self) -> None:
        # Remove only the weakest memories to prevent uncontrolled growth.
        ids = self.redis.zrange(self._rank_key, 0, -1)
        for memory_id in ids:
            raw = self.redis.get(f"{self._mem_key_prefix}{memory_id}")
            if not raw:
                self.redis.zrem(self._rank_key, memory_id)
                continue
            record = MemoryRecord.from_dict(json.loads(raw))
            if record.importance < self.min_importance_to_keep:
                self.redis.delete(f"{self._mem_key_prefix}{memory_id}")
                self.redis.zrem(self._rank_key, memory_id)

    def _trim_rank_to_keep_top(self, max_items: int = 1000) -> None:
        # Hard cap for long-running experiments.
        count = self.redis.zcard(self._rank_key)
        if count <= max_items:
            return
        remove_n = count - max_items
        victims = self.redis.zrange(self._rank_key, 0, remove_n - 1)
        for memory_id in victims:
            self.redis.delete(f"{self._mem_key_prefix}{memory_id}")
            self.redis.zrem(self._rank_key, memory_id)

    # -------------------------
    # Convenience methods
    # -------------------------

    def build_prompt_context(self, current_step_comment: str, k: int = 10) -> str:
        """Return a compact memory block to inject into the generator prompt."""
        memories = self.get_top_memories(k)
        if not memories:
            return current_step_comment
        memory_block = self.get_memory_prompt_block(k)
        return (
            f"Current evaluator feedback:\n{current_step_comment}\n\n"
            f"Known recurring mistakes:\n{memory_block}"
        )

    def stats(self) -> Dict[str, Any]:
        return {
            "items": self.redis.zcard(self._rank_key),
            "top_item": (self.redis.zrevrange(self._rank_key, 0, 0) or [None])[0],
            "namespace": self.namespace,
        }


# -----------------------------
# Example usage
# -----------------------------


def _demo() -> None:
    node = MemoryNode()

    feedback = {
        "step_1": [
            "You should not duplicate the same assertion in two places.",
            "Missing check for empty response.",
        ],
        "step_2": [
            "Coverage is too weak here; the invalid input path is not tested.",
            "The step is too generic and should be more specific.",
        ],
    }

    result = node.ingest_evaluator_feedback(
        evaluator_score=3.2,
        comments_by_step=feedback,
        process_context="API test generation for checkout flow",
        run_id="run_001",
    )

    print("new:", [m.to_dict() for m in result.new_items])
    print("updated:", [m.to_dict() for m in result.updated_items])
    print("prompt block:\n", node.get_memory_prompt_block())


if __name__ == "__main__":
    _demo()
