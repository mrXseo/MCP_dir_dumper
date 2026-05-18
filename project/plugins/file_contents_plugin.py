# project/plugins/file_contents_plugin.py
import os
from typing import TextIO, List, Optional

from ..blank_plugin import DumperPlugin


class FileContentsPlugin(DumperPlugin):
    """
    Плагин для генерации раздела "Файлы" в дампе.

    Рекурсивно обходит целевую директорию и записывает содержимое
    текстовых файлов в виде блоков с настраиваемыми заголовками и подвалами.
    Поддерживает фильтрацию по именам и расширениям.
    В будущем — применение стратегий постобработки содержимого.
    """

    host_key: str = "file_contents"
    name: str = "File Contents"

    def __init__(self, config: Optional[dict] = None, **kwargs) -> None:
        super().__init__(config=config, **kwargs)

    def configure(self, **kwargs) -> None:
        """Извлекает настройки из self.config."""
        self.include_extensions: List[str] = self.config.get("include_extensions", ["*"])
        self.exclude_extensions: List[str] = self.config.get("exclude_extensions", [])
        self.include_names: List[str] = self.config.get("include_names", ["*"])
        self.exclude_names: List[str] = self.config.get("exclude_names", [])
        self.block_header: str = self.config.get(
            "block_header_template", "===== Файл: {relative_path} ====="
        )
        self.block_footer: str = self.config.get(
            "block_footer_template", "===== Конец: {relative_path} ====="
        )
        # Задел для будущей стратегии постобработки содержимого
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
                if not self._is_excluded_name(entry):
                    self._process_dir(base_dir, full_path, output)
            elif os.path.isfile(full_path):
                if self._should_include(entry):
                    self._dump_file(base_dir, full_path, output)

    def _should_include(self, filename: str) -> bool:
        """Проверяет, проходит ли файл через фильтры имён и расширений."""
        # Проверка имени
        if self._matches(filename, self.exclude_names):
            return False
        if self.include_names != ["*"] and not self._matches(filename, self.include_names):
            return False
        # Проверка расширения
        ext = os.path.splitext(filename)[1].lower()
        if self._matches(ext, self.exclude_extensions):
            return False
        if self.include_extensions != ["*"] and not self._matches(ext, self.include_extensions):
            return False
        return True

    def _is_excluded_name(self, name: str) -> bool:
        """Проверяет, исключено ли имя директории."""
        return self._matches(name, self.exclude_names)

    @staticmethod
    def _matches(value: str, patterns: List[str]) -> bool:
        """Точное совпадение со значением или наличие '*' в списке шаблонов."""
        return "*" in patterns or value in patterns

    def _dump_file(self, base_dir: str, file_path: str, output: TextIO) -> None:
        """Читает файл и записывает его содержимое в блоке."""
        rel_path = os.path.relpath(file_path, base_dir)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, PermissionError, OSError):
            # Не текстовый файл или ошибка доступа – пропускаем
            return

        # Здесь в будущем можно применить стратегию постобработки
        # if self.strategy:
        #     content = self._apply_strategy(content, self.strategy)

        header = self.block_header.format(relative_path=rel_path)
        footer = self.block_footer.format(relative_path=rel_path)
        output.write(f"{header}\n")
        output.write(content)
        if not content.endswith('\n'):
            output.write('\n')
        output.write(f"{footer}\n\n")