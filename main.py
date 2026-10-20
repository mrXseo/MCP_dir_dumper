# dumper/main.py
import argparse
import sys
from pathlib import Path

# Добавляем корень dumper в sys.path для импорта пакета project
HERE = Path(__file__).resolve().parent
# if str(HERE) not in sys.path:
#    sys.path.insert(0, str(HERE))

from project.plugin_host import PluginHost


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dumper — генератор структурированных дампов"
    )
    parser.add_argument(
        "config",
        nargs="?",
        default=str(HERE / "configs" / ".dump.json"),
        help="Путь к JSON-конфигу",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод процесса работы",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Конфиг не найден: {config_path}")
        sys.exit(1)

    print(f"Загружаю конфиг: {config_path}")
    host = PluginHost(str(config_path), verbose=args.verbose)
    host.run()


if __name__ == "__main__":
    main()