from typing import Any, List, Mapping, Sequence

from tabulate import tabulate


def to_markdown_table(rows: Sequence[Mapping[str, Any]], headers: Sequence[str]) -> str:
    normalized: List[List[Any]] = [
        [row.get(col, "") for col in headers] for row in rows
    ]
    return tabulate(normalized, headers=headers, tablefmt="github")
