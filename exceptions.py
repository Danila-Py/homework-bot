class EnviromentTokenError(Exception):
    """Отсутствие обязательных переменных окружения во время запуска бота."""


class GetAPIAnswerException(Exception):
    """Ошибка доступа к API."""


class CheckResponseException(Exception):
    """Ответ API не соответствует документации."""


class CheckHomeworkError(Exception):
    """Ошибки при извелечении информации о домашней работе."""


class RequestError(Exception):
    """Возникает при недоступности ендпоинта."""
