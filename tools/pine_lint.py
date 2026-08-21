#!/usr/bin/env python3
"""Лёгкая статическая проверка Pine-скриптов перед вставкой в TradingView.

Проверяет то, что реально ломает компиляцию в редакторе TradingView:
табуляции, отступы не кратные 4, незакрытые скобки, отсутствие заголовка
версии и объявления indicator(), а также остатки синтаксиса Pine v4.
Полноценная компиляция возможна только в самом TradingView.
"""

from __future__ import annotations

import pathlib
import re
import sys

V4_PATTERNS = {
    r"\bstudy\s*\(": "study() — синтаксис v4, нужен indicator()",
    r"(?<![.\w])security\s*\(": "security() — нужен request.security()",
    r"\biff\s*\(": "iff() удалён, используйте тернарный оператор",
    r"(?<![.\w])crossover\s*\(": "crossover() — нужен ta.crossover()",
    r"(?<![.\w])sma\s*\(": "sma() — нужен ta.sma()",
    r"(?<![.\w])rsi\s*\(": "rsi() — нужен ta.rsi()",
    r"(?<![.\w])tostring\s*\(": "tostring() — нужен str.tostring()",
}

PAIRS = {")": "(", "]": "[", "}": "{"}
OPENERS = set(PAIRS.values())


def strip_code(line: str) -> str:
    """Убирает строковые литералы и комментарии, оставляя структуру кода."""
    out = []
    i = 0
    in_str = False
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def check(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or not lines[0].startswith("//@version="):
        problems.append("строка 1: отсутствует //@version=N")
    if not re.search(r"^indicator\s*\(", text, re.M) and not re.search(
        r"^strategy\s*\(", text, re.M
    ):
        problems.append("нет объявления indicator()/strategy() в глобальной области")

    stack: list[tuple[str, int]] = []
    for num, raw in enumerate(lines, start=1):
        if "\t" in raw:
            problems.append(f"строка {num}: табуляция (Pine требует пробелы)")
        code = strip_code(raw)
        if code.strip():
            indent = len(code) - len(code.lstrip(" "))
            if not stack and indent % 4 != 0:
                problems.append(
                    f"строка {num}: отступ {indent} не кратен 4 — Pine поймёт это как продолжение строки"
                )
        for ch in code:
            if ch in OPENERS:
                stack.append((ch, num))
            elif ch in PAIRS:
                if not stack:
                    problems.append(f"строка {num}: лишняя закрывающая '{ch}'")
                elif stack[-1][0] != PAIRS[ch]:
                    problems.append(
                        f"строка {num}: '{ch}' не соответствует '{stack[-1][0]}' из строки {stack[-1][1]}"
                    )
                    stack.pop()
                else:
                    stack.pop()
        for pattern, message in V4_PATTERNS.items():
            if re.search(pattern, code):
                problems.append(f"строка {num}: {message}")

    for ch, num in stack:
        problems.append(f"строка {num}: не закрыта '{ch}'")

    return problems


def main() -> int:
    targets = [pathlib.Path(a) for a in sys.argv[1:]]
    if not targets:
        targets = sorted(pathlib.Path("pine").glob("*.pine"))
    failed = False
    for path in targets:
        problems = check(path)
        if problems:
            failed = True
            print(f"✗ {path}")
            for problem in problems:
                print(f"    {problem}")
        else:
            print(f"✓ {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
