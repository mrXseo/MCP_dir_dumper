# project/plugins/directory_structure_plugin.py
import os
from typing import TextIO, List, Optional

from ..blank_plugin import DumperPlugin


class DirectoryStructurePlugin(DumperPlugin):
    """
    Плагин для генерации раздела "Структура директории" в дампе.

    Рекурсивно обходит целевую директорию и строит текстовое дерево.
    Поддерживает фильтрацию по именам папок/файлов (чёрный список).
    В будущем — стратегии комментирования узлов.
    """

    host_key: str = "directory_structure"
    name: str = "Directory Structure"

    def __init__(self, config: Optional[dict] = None, **kwargs) -> None:
        super().__init__(config=config, **kwargs)

    def configure(self, **kwargs) -> None:
        """Извлекает настройки из self.config и kwargs."""
        self.include_extensions: List[str] = self.config.get("include_extensions", ["*"])
        self.exclude_names: List[str] = self.config.get("exclude_names", [])
        self.exclude_extensions: List[str] = self.config.get("exclude_extensions", [])
        self.include_names: List[str] = self.config.get("include_names", ["*"])
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

        # Фильтруем по именам
        entries = [e for e in entries if self._should_include_name(e)]
        if not entries:
            return

        for i, entry in enumerate(entries):
            full_path = os.path.join(path, entry)
            is_last = (i == len(entries) - 1)
            is_dir = os.path.isdir(full_path)

            # Выбираем соединитель
            connector = "`*--" if is_last else "|*--"
            connector += ", " if is_dir else "- "
            output.write(f".    {prefix}{connector}{entry}{'/' if is_dir else ''}\n")

            if is_dir:
                # Добавляем отступ для следующего уровня
                extension = "    " if is_last else "|   "
                self._walk(full_path, output, prefix + extension)

    def _should_include_name(self, name: str) -> bool:
        """Проверяет, проходит ли имя через фильтры include/exclude."""
        # Исключённые имена
        if self._matches(name, self.exclude_names):
            return False
        # Если include_names заданы явно (не ["*"]), проверяем вхождение
        if self.include_names and self.include_names != ["*"]:
            return self._matches(name, self.include_names)
        return True

    @staticmethod
    def _matches(name: str, patterns: List[str]) -> bool:
        """Точное совпадение или символ '*' (глобальное разрешение)."""
        return "*" in patterns or name in patterns