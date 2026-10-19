import os
import re
from pathlib import Path
from typing import TextIO, List, Optional, Dict, Union, Pattern

from ..blank_plugin import DumperPlugin


class FileContentsPlugin(DumperPlugin):
    """
    Плагин для генерации раздела "Файлы" в дампе.

    Рекурсивно обходит целевую директорию и записывает содержимое
    текстовых файлов в виде блоков с настраиваемыми заголовками и подвалами.
    Поддерживает фильтрацию по регулярным выражениям (regex).
    """

    host_key: str = "file_contents"
    name: str = "File Contents"

    def __init__(self, config: Optional[dict] = None, **kwargs) -> None:
        super().__init__(config=config, **kwargs)

    def configure(self, **kwargs) -> None:
        """
        Извлекает и компилирует настройки из self.config.
        BREAKING CHANGE: Фильтрация теперь осуществляется исключительно через regex.
        """
        raw_included = self.config.get("included", [r".*"])
        raw_excluded = self.config.get("excluded", [])

        # Fail-fast валидация: ловим ошибки синтаксиса regex сразу при старте, 
        # а не на середине обхода тысяч файлов.
        try:
            self._compiled_included: List[Pattern] = [re.compile(p) for p in raw_included]
            self._compiled_excluded: List[Pattern] = [re.compile(p) for p in raw_excluded]
        except re.error as e:
            raise ValueError(f"Invalid regex pattern in plugin '{self.host_key}': {e}")

        self.block_header: str = self.config.get(
            "block_header_template", "===== Файл: {relative_path} ====="
        )
        self.block_footer: str = self.config.get(
            "block_footer_template", "===== Конец: {relative_path} ====="
        )
        self.max_rows: Union[Dict[str, int], int] = self.config.get("max_rows", -1)
        self.strategy: Optional[str] = self.config.get("strategy", None)

    def execute(self, target_directory: str, output: TextIO) -> None:
        """Записывает в output раздел с содержимым файлов."""
        output.write("===== ФАЙЛЫ =====\n")
        self._process_dir(target_directory, target_directory, output)

    def _process_dir(self, base_dir: str, current_dir: str, output: TextIO) -> None:
        """Рекурсивный обход директорий с фильтрацией."""
        try:
            entries = sorted(os.listdir(current_dir))
        except PermissionError:
            return
        
        for entry in entries:
            full_path = os.path.join(current_dir, entry)
            if os.path.isdir(full_path):
                # Если директория исключена, мы не заходим в неё вообще (экономия I/O)
                if not self._is_excluded_name(entry):
                    self._process_dir(base_dir, full_path, output)
            elif os.path.isfile(full_path):
                if self._should_include_file(entry):
                    self._dump_file(base_dir, full_path, output)

    def _should_include_file(self, filename: str) -> bool:
        """
        Проверяет, проходит ли файл через фильтры.
        Приоритет: exclude (denylist) всегда сильнее include (allowlist).
        """
        # 1. Проверка на исключение
        if self._matches(filename, self._compiled_excluded):
            return False
        
        # 2. Проверка на включение
        # Если список включений пуст, файл отвергается (защитный механизм).
        # По умолчанию там [r".*"], что разрешает всё, не попавшее в exclude.
        if not self._compiled_included:
            return False
            
        return self._matches(filename, self._compiled_included)

    def _is_excluded_name(self, name: str) -> bool:
        """Проверяет, исключено ли имя директории."""
        return self._matches(name, self._compiled_excluded)

    @staticmethod
    def _matches(value: str, patterns: List[Pattern]) -> bool:
        """Поиск совпадений по предкомпилированным регулярным выражениям."""
        return any(pattern.search(value) for pattern in patterns)

    def _dump_file(self, base_dir: str, file_path: str, output: TextIO) -> None:
        """Читает файл и записывает его содержимое в блоке."""
        rel_path = os.path.relpath(file_path, base_dir)
        extension = Path(rel_path).suffix
        
        max_rows = -1
        if isinstance(self.max_rows, dict):
            max_rows = self.max_rows.get(extension, -1)
        elif isinstance(self.max_rows, int):
            max_rows = self.max_rows
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_content = f.readlines()
                
                if max_rows < 0 or len(full_content) <= max_rows:
                    content = "".join(full_content)
                else:
                    content = "".join(full_content[:max_rows])
                    content += f"\n~~~DUMPER-COMMENT~~~[{len(full_content) - max_rows} lines are hidden]\n"
        except (UnicodeDecodeError, PermissionError, OSError):
            # Не текстовый файл или ошибка доступа – пропускаем без шума
            return

        header = self.block_header.format(relative_path=rel_path)
        footer = self.block_footer.format(relative_path=rel_path)
        
        output.write(f"{header}\n")
        output.write(content)
        if not content.endswith('\n'):
            output.write('\n')
        output.write(f"{footer}\n\n")