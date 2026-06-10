def format_memories(memories: list, sort_by_kind: bool = True) -> list[str]:
        memories = [i.value for i in memories]
        if sort_by_kind:
            memories = sorted(memories, key=lambda x: (x["kind"], x["timestamp"]))

        importance_str = [
            f"{m['importance']:.2f}" if m["importance"] != -1 else "N/A"
            for m in memories
        ]

        memories_str = [
            f"""timestamp: {m['timestamp']}; kind: {m['kind']}; importance: {i}; content: {m['content']}"""
            for m, i in zip(memories, importance_str)
        ]

        return memories_str