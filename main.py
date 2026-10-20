# dumper/main.py
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

HERE = Path(__file__).resolve().parent

from project.plugin_host import PluginHost

LOCAL_CONFIG_NAME = ".dir_dumper.conf.json"
BUILTIN_CONFIG = HERE / "configs" / ".dump.json"
DUMP_FILE_NAME = ".dump.txt"
GITIGNORE_MARKER = "# auto-insert @ dir-dumper"
GITIGNORE_BLOCK = f"""{GITIGNORE_MARKER}
/.dump.txt
/.dir_dumper.conf.json
"""


def fail(message: str, code: int = 1) -> None:
    print(f"Ошибка: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path) -> Dict[str, Any]:
    """Читает JSON с понятными ошибками вместо traceback."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        fail(f"Не удалось прочитать {path}: {e}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        fail(f"Некорректный JSON в {path}: {e}")

    if not isinstance(data, dict):
        fail(f"Конфиг {path} должен содержать JSON-объект, а не {type(data).__name__}")

    return data


def resolve_config(target: Path, explicit: Optional[str], verbose: bool) -> Path:
    """
    Явный --config -> локальный .dir_dumper.conf.json -> встроенный конфиг.
    Найдённый, но битый конфиг НЕ подменяется встроенным: fail-fast.
    """
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            fail(f"Указанный конфиг не найден: {path}")
        label = "явный (--config)"
    else:
        local = target / LOCAL_CONFIG_NAME
        if local.is_file():
            path, label = local, "локальный"
        elif BUILTIN_CONFIG.is_file():
            path, label = BUILTIN_CONFIG, "встроенный (fallback)"
        else:
            fail(
                f"Не найден ни локальный конфиг {local}, "
                f"ни встроенный {BUILTIN_CONFIG}.\n"
                f"Создайте локальный: python main.py \"{target}\" --build"
            )

    # Валидируем сразу, чтобы не падать внутри PluginHost на середине работы.
    load_json(path)

    if verbose:
        print(f"Источник конфига: {label}")
    return path


def update_gitignore(target: Path, verbose: bool) -> None:
    """
    Идемпотентно добавляет блок с маркером в .gitignore целевой директории.
    Если маркер уже есть — ничего не делает.
    """
    gitignore_path = target / ".gitignore"

    # Читаем существующий .gitignore (если есть)
    existing_content = ""
    if gitignore_path.is_file():
        try:
            existing_content = gitignore_path.read_text(encoding="utf-8")
        except OSError as e:
            fail(f"Не удалось прочитать {gitignore_path}: {e}")

    # Проверяем идемпотентность: если маркер уже есть, выходим
    if GITIGNORE_MARKER in existing_content:
        if verbose:
            print(f"Блок уже присутствует в {gitignore_path}, пропускаем")
        return

    # Формируем новое содержимое
    new_content = existing_content
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += GITIGNORE_BLOCK

    # Атомарная запись
    tmp = gitignore_path.with_name(gitignore_path.name + ".tmp")
    try:
        tmp.write_text(new_content, encoding="utf-8")
        tmp.replace(gitignore_path)
    except OSError as e:
        fail(f"Не удалось записать {gitignore_path}: {e}")
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)

    if verbose:
        print(f"Добавлен блок в {gitignore_path}")
    else:
        print(f"Обновлён .gitignore: {gitignore_path}")


def build_config(
    target: Path, source: Path, force: bool, gitignore: bool, verbose: bool
) -> Path:
    """Копирует шаблон в целевую директорию как .dir_dumper.conf.json."""
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        fail(f"Не удалось создать директорию {target}: {e}")

    dest = target / LOCAL_CONFIG_NAME

    # --config может указывать уже на сам локальный конфиг.
    if source.resolve() == dest.resolve():
        print(f"Локальный конфиг уже на месте: {dest}")
    else:
        if dest.exists() and not force:
            fail(
                f"Файл уже существует: {dest}\n"
                f"Используйте --force для перезаписи.",
                code=2,
            )

        config = load_json(source)

        # Привязываем к реальному месту создания: запуск с любого cwd
        # должен дампить именно эту директорию в её же .dump.txt.
        config["target_directory"] = str(target.resolve())
        config["output_file"] = str((target / DUMP_FILE_NAME).resolve())

        # Атомарная запись: не портим существующий конфиг при сбое.
        tmp = dest.with_name(dest.name + ".tmp")
        try:
            tmp.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            tmp.replace(dest)
        except OSError as e:
            fail(f"Не удалось записать {dest}: {e}")
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        if verbose:
            print(f"Шаблон: {source}")

        print(f"Создан локальный конфиг: {dest}")
        print(f"Целевая директория: {config['target_directory']}")
        print(f"Файл дампа: {config['output_file']}")

    # Обновляем .gitignore, если запрошено
    if gitignore:
        update_gitignore(target, verbose)

    return dest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dumper — генератор структурированных дампов",
        epilog=(
            "Поиск конфига: --config -> <target>/.dir_dumper.conf.json "
            "-> configs/.dump.json (внутри инструмента).\n"
            "Примеры:\n"
            "  python main.py\n"
            "  python main.py ./my_project\n"
            "  python main.py ./my_project --build\n"
            "  python main.py ./my_project --build --gitignore\n"
            "  python main.py --config ./custom.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Целевая директория для поиска конфига и --build (по умолчанию: текущая)",
    )
    parser.add_argument(
        "-c", "--config",
        metavar="PATH",
        help="Явный путь к JSON-конфигу; с --build используется как источник шаблона",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Создать .dir_dumper.conf.json в целевой директории и выйти",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="С --build: перезаписать существующий локальный конфиг",
    )
    parser.add_argument(
        "--gitignore",
        action="store_true",
        help="С --build: идемпотентно добавить /.dump.txt и /.dir_dumper.conf.json в .gitignore",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Подробный вывод процесса работы",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if (args.force or args.gitignore) and not args.build:
        fail("--force и --gitignore имеют смысл только вместе с --build", code=2)

    target = Path(args.target).expanduser().resolve()

    if args.build:
        source = (
            Path(args.config).expanduser().resolve()
            if args.config
            else BUILTIN_CONFIG
        )
        if not source.is_file():
            fail(f"Шаблон конфига не найден: {source}")

        build_config(
            target, source, force=args.force, gitignore=args.gitignore, verbose=args.verbose
        )
        print(f"\nЗапуск дампа: python main.py \"{target}\"")
        return

    config_path = resolve_config(target, args.config, args.verbose)

    print(f"Загружаю конфиг: {config_path}")
    host = PluginHost(str(config_path), verbose=args.verbose)
    host.run()


if __name__ == "__main__":
    main()