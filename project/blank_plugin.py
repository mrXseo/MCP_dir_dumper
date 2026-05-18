# project/blank_plugin.py
from abc import ABC, abstractmethod
from typing import TextIO, Optional


class DumperPlugin(ABC):
    """
    Базовый класс-контракт для всех плагинов дампера.

    Каждый плагин отвечает за отдельный раздел итогового дампа.
    Плагин обязан определить свойства:
      - host_key: уникальный строковый ключ для привязки к JSON-конфигу
      - name: человекочитаемое имя (для логов и отладки)
    """

    @property
    @abstractmethod
    def host_key(self) -> str:
        """
        Уникальный ключ плагина.
        Используется как идентификатор в конфигурационном файле (словарь 'plugins').
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Человекочитаемое имя плагина.
        Выводится в логах, не влияет на логику работы.
        """
        ...

    def __init__(self, config: Optional[dict] = None, **kwargs) -> None:
        """
        Инициализация плагина.

        :param config: Словарь с настройками плагина, полученный из JSON-конфига.
                       Содержит все параметры, переданные для данного host_key, кроме служебного 'enabled'.
        :param kwargs: Дополнительные именованные параметры, которые могут быть проброшены хостом
                       или использованы в цепочке super().__init__.
        """
        self.config: dict = config or {}
        # Позволяем наследникам обработать оставшиеся kwargs
        self.configure(**kwargs)

    def configure(self, **kwargs) -> None:
        """
        Переопределяемый метод для обработки дополнительных параметров.

        Вызывается в конце __init__. По умолчанию не делает ничего.
        Наследники могут извлекать специфичные для себя параметры из kwargs и self.config.
        """
        pass

    @abstractmethod
    def execute(self, target_directory: str, output: TextIO) -> None:
        """
        Выполняет генерацию своего раздела дампа.

        :param target_directory: Абсолютный или относительный путь к целевой директории,
                                 которую необходимо обработать.
        :param output: Поток для записи текстового дампа.
                       Плагин владеет потоком монопольно во время вызова.
        """
        ...