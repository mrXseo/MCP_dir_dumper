import os
import re
from typing import TextIO, List, Optional, Pattern

from ..blank_plugin import DumperPlugin


class DirectoryStructurePlugin(DumperPlugin):
    """
    Плагин для генерации раздела "Структура директории" в дампе.

    Рекурсивно обходит целевую директорию и строит текстовое дерево.
    Поддерживает фильтрацию по регулярным выражениям (regex).
    """

    host_key: str = "directory_structure"
    name: str = "Directory Structure"

    def __init__(self, config: Optional[dict] = None, **kwargs) -> None:
        super().__init__(config=config, **kwargs)

    def configure(self, **kwargs) -> None:
        """
        Извлекает и компилирует настройки из self.config.
        BREAKING CHANGE: Фильтрация теперь осуществляется исключительно через regex.
        """
        raw_included = self.config.get("included", [r".*"])
        raw_excluded = self.config.get("excluded", [])

        # Fail-fast валидация: ловим ошибки синтаксиса regex сразу при старте.
        try:
            self._compiled_included: List[Pattern] = [re.compile(p) for p in raw_included]
            self._compiled_excluded: List[Pattern] = [re.compile(p) for p in raw_excluded]
        except re.error as e:
            raise ValueError(f"Invalid regex pattern in plugin '{self.host_key}': {e}")

        # Поле для будущей стратегии комментирования узлов
        self.strategy: Optional[str] = self.config.get("strategy", None)

    def execute(self, target_directory: str, output: TextIO) -> None:
        output.write("===== СТРУКТУРА ДИРЕКТОРИИ =====\n")
        # Выводим корневую папку
        root_name = os.path.basename(target_directory) or target_directory
        output.write(f". >> {root_name}/\n")
        self._walk(target_directory, output, prefix="")

    def _walk(self, path: str, output: TextIO, prefix: str) -> None:
        """Рекурсивно выводит дерево с правильными префиксами."""
        try:
            entries = sorted(os.listdir(path))
        except PermissionError:
            return

        # Фильтруем элементы через единый метод проверки
        entries = [e for e in entries if self._should_include(e)]
        if not entries:
            return

        for i, entry in enumerate(entries):
            full_path = os.path.join(path, entry)
            is_last = (i == len(entries) - 1)
            is_dir = os.path.isdir(full_path)

            # Выбираем соединитель для ASCII-дерева
            connector = "`*--" if is_last else "|*--"
            connector += ", " if is_dir else "- "
            output.write(f".    {prefix}{connector}{entry}{'/' if is_dir else ''}\n")

            if is_dir:
                # Добавляем отступ для следующего уровня
                extension = "    " if is_last else "|   "
                self._walk(full_path, output, prefix + extension)

    def _should_include(self, name: str) -> bool:
        """
        Проверяет, проходит ли элемент (файл или директория) через фильтры.
        Приоритет: exclude (denylist) всегда сильнее include (allowlist).
        """
        # 1. Проверка на исключение
        if self._matches(name, self._compiled_excluded):
            return False
        
        # 2. Проверка на включение
        # Если список включений пуст, элемент отвергается (защитный механизм).
        # По умолчанию там [r".*"], что разрешает всё, не попавшее в exclude.
        if not self._compiled_included:
            return False
            
        return self._matches(name, self._compiled_included)

    @staticmethod
    def _matches(value: str, patterns: List[Pattern]) -> bool:
        """Поиск совпадений по предкомпилированным регулярным выражениям."""
        return any(pattern.search(value) for pattern in patterns)