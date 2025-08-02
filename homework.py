import logging
from logging import StreamHandler
import os
import sys
import time

import requests
from telebot import TeleBot, apihelper
from dotenv import load_dotenv

from exceptions import (
    EnviromentTokenError,
    GetAPIAnswerException,
    CheckHomeworkError,
    CheckResponseException,
    RequestError
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    missing_variables = [
        var for var in variables
        if variables.get(var) is None
    ]
    return missing_variables


def send_message(bot, message):
    """Отправляет сообщение через Бота Telegram."""
    logger.debug(
        'Запуск функции send_message, начало отправки сообщения.'
    )
    try:
        logger.debug(f'Отправка: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except (
            apihelper.ApiException,
            requests.exceptions.RequestException
    ) as exc:
        logger.error(f'Ошибка отправки: {exc}', exc_info=True)
    else:
        logger.info(f'Бот успешно отправил сообщение: {message}')


def get_api_answer(current_timestamp):
    """Запрос к ENDPOINT API-Яндекс.Практикум.Домашка."""
    logger.debug(
        f'Запуск функции get_api_answer. Запроса к API {ENDPOINT}, '
        f'передан параметр from_date: {current_timestamp}.'
    )
    error_message = (
        f'Ошибка при запросе к основному API: {ENDPOINT}. '
        f'Передан параметр from_date: {current_timestamp}.'
    )
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': current_timestamp}
        )
    except requests.RequestException:
        raise RequestError(error_message)
    if response.status_code == requests.codes.ok:
        return response.json()
    raise GetAPIAnswerException(error_message)


def check_response(response):
    """Проверяет корректность ответа API и возвращает список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    check_list_homeworks = response.get('homeworks')
    api_keys = ['homeworks', 'current_date']
    for key in api_keys:
        if key not in response:
            raise CheckResponseException(
                f'Ответ API не содержит ожидаемые ключи: {api_keys}'
            )
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ homeworks в ответе')
    if not isinstance(check_list_homeworks, list):
        raise TypeError(
            'В ответе API под ключом "homeworks" получен не тип "list", '
            f'а: {type(check_list_homeworks).__name__}'
        )
    return check_list_homeworks


def parse_status(homework):
    """Извлекает из информации о конкретном ДЗ его статус."""
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name недоступен')
    if 'status' not in homework:
        raise KeyError('Ключ status недоступен')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        raise CheckHomeworkError(
            f'Некорректный статус работы: {homework_status}'
        )

    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logger.info('Вы запустили Бота')
    missing_variables = check_tokens()
    if missing_variables:
        error_message = (
            f'Отсутствуют переменные окружения: {missing_variables}. '
            'Программа принудительно остановлена.'
        )
        logger.critical(error_message, exc_info=True)
        raise EnviromentTokenError(error_message)

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_message = None
    processed_homeworks = set()

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                send_message(bot, "Новых статусов пока нет")
                logger.info("Новых статусов пока нет")
            else:
                for homework in homeworks:
                    if homework['homework_name'] not in processed_homeworks:
                        status_message = parse_status(homework)
                        success = send_message(bot, status_message)
                        if success:
                            processed_homeworks.add(homework['homework_name'])
                            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error_message, exc_info=True)
            if message != error_message:
                error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
