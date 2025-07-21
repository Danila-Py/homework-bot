from http import HTTPStatus
import logging
from logging import StreamHandler
import os
import sys
import time

import requests
from telebot import TeleBot
from dotenv import load_dotenv

from exceptions import (
    EnviromentTokenError,
    GetAPIAnswerException,
    CheckHomeworkError,
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
    if missing_variables:
        error_message = (
            f'Отсутствуют переменные окружения: {missing_variables}. '
            'Программа принудительно остановлена.')
        logger.critical(error_message, exc_info=True)
        raise EnviromentTokenError(error_message)


def send_message(bot, message):
    """Отправляет сообщение через Бота Telegram."""
    logger.debug(
        'Запуск функции send_message, начало отправки сообщения.'
    )
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: {message}')
    except TeleBot:
        logger.error('Сбой отправки сообщения.')


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
        raise ConnectionError(error_message)
    else:
        if response.status_code != HTTPStatus.OK:
            raise GetAPIAnswerException(error_message)
        logger.info(
            f'Запрос к API {ENDPOINT} успешно отправлен. '
            f'Передан параметр from_date: {current_timestamp}'
        )
        return response.json()


def check_response(response):
    """Проверяет корректность ответа API и возвращает список домашних работ."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    check_list_homeworks = response.get('homeworks')
    if check_list_homeworks is None:
        raise KeyError('Ключ "homeworks" не доступен')
    if not isinstance(check_list_homeworks, list):
        raise TypeError('Ответ API по ключу "homeworks" не список')
    if len(check_list_homeworks) >= 0:
        return check_list_homeworks
    else:
        logger.debug('В текущей проверке новые статусы ДЗ отсутсвуют')


def parse_status(homework):
    """Извлекает из информации о конкретном ДЗ его статус."""
    if 'homework_name' not in homework:
        message = 'Ключ homework_name недоступен'
        logger.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'Ключ status недоступен'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        message = (
            f'Передан неизвестный статус домашней работы "{homework_status}"'
        )
        logger.error(message)
        raise CheckHomeworkError(message)


def main():
    """Основная логика работы бота."""
    logger.info('Вы запустили Бота')
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if not response.get('homeworks'):
                logger.debug(
                    f'Запрос к API {ENDPOINT} вернул пустой список homeworks, '
                    'статус работ не изменился.'
                )
            else:
                message = parse_status(response.get('homeworks')[0])
                send_message(bot, message)
                error_message = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error_message, exc_info=True)
            if error_message != message:
                error_message = message
                send_message(bot, error_message)
        else:
            timestamp = response.get('current_date')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
