# project/plugin_host.py
import json
import importlib
import inspect
import sys
from pathlib import Path
from typing import Dict, Type

from .blank_plugin import DumperPlugin


class PluginHost:
    """Загружает плагины по JSON-конфигу и запускает их для создания дампа."""

    # Ключи в конфигурационном файле
    CONF_TARGET: str = "target_directory"
    CONF_OUTPUT: str = "output_file"
    CONF_PLUGINS: str = "plugins"

    def __init__(self, config_path: str, verbose: bool = False) -> None:
        self.verbose = verbose
        with open(config_path, 'r', encoding='utf-8') as f:
            self.raw_config = json.load(f)
        self.target_directory: str = self.raw_config[self.CONF_TARGET]
        self.output_file: str = self.raw_config[self.CONF_OUTPUT]
        self.plugins_config: Dict[str, dict] = self.raw_config.get(self.CONF_PLUGINS, {})
        self._log(f"Конфиг загружен: цель='{self.target_directory}', вывод='{self.output_file}'")
        self._log(f"Плагины в конфиге: {list(self.plugins_config.keys())}")

    def _log(self, message: str) -> None:
        """Логирование только при verbose=True."""
        if self.verbose:
            print(f"[Host] {message}")

    def _error(self, message: str) -> None:
        """Сообщения об ошибках выводятся всегда."""
        print(f"[Host ERROR] {message}", file=sys.stderr)

    def _discover_plugin_classes(self) -> Dict[str, Type[DumperPlugin]]:
        """Импортирует модули из project/plugins и возвращает {host_key: класс}."""
        plugin_classes: Dict[str, Type[DumperPlugin]] = {}
        plugins_dir = Path(__file__).parent / "plugins"
        self._log(f"Сканирую папку плагинов: {plugins_dir}")
        if not plugins_dir.exists():
            self._error(f"Папка плагинов не найдена: {plugins_dir}")
            return plugin_classes

        for module_file in plugins_dir.glob("*.py"):
            if module_file.name.startswith("_") or module_file.name == "__init__.py":
                continue
            module_name = f"project.plugins.{module_file.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception as e:
                self._error(f"Не удалось импортировать {module_name}: {e}")
                continue
            self._log(f"Импортирован модуль: {module_name}")
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, DumperPlugin)
                    and obj is not DumperPlugin
                    and obj.__module__ == module.__name__
                ):
                    plugin_key = getattr(obj, 'host_key', None)
                    if not plugin_key:
                        self._error(f"Класс {obj.__name__} не имеет host_key, пропущен")
                        continue
                    plugin_classes[plugin_key] = obj
                    self._log(f"Найден плагин: {plugin_key} -> {obj.__name__}")
        return plugin_classes

    def run(self) -> None:
        """Главный метод: выполняет все включенные плагины и записывает дамп."""
        output_path = Path(self.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        available = self._discover_plugin_classes()
        self._log(f"Доступные плагины: {list(available.keys())}")

        if not available:
            self._error("Плагины не найдены. Аварийное завершение.")
            return

        with open(output_path, 'w', encoding='utf-8') as out:
            for host_key, pconf in self.plugins_config.items():
                if not pconf.get("enabled", False):
                    self._log(f"Плагин '{host_key}' отключен, пропускаю")
                    continue
                if host_key not in available:
                    self._error(f"Плагин '{host_key}' из конфига не найден, пропускаю")
                    continue

                plugin_cls = available[host_key]
                # Убираем 'enabled' из конфига, остальное передаётся плагину
                plugin_config = {k: v for k, v in pconf.items() if k != "enabled"}
                try:
                    plugin = plugin_cls(config=plugin_config)
                except Exception as e:
                    self._error(f"Ошибка при создании плагина '{host_key}': {e}")
                    continue

                self._log(f"Запускаю плагин: {plugin.name} (key={host_key})")
                try:
                    plugin.execute(self.target_directory, out)
                except Exception as e:
                    self._error(f"Плагин '{host_key}' завершился с ошибкой: {e}")
                    continue
                out.write("\n")  # разделитель между разделами плагинов

        print(f"Дамп сохранён в {self.output_file}")