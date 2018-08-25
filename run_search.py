#!/usr/bin/python3
# -*- coding: utf-8 -*-
from time import sleep
import logging
import string
import random
import argparse
import re
from tabulate import tabulate
from transliterate import translit

from telethon import TelegramClient
from telethon.tl.types import PeerUser, PeerChannel
from telethon.tl.functions.contacts import SearchRequest

api_id = 0
api_hash = 'hash'
re_words = r'([a-z][A-Z]|[A-Z]+[a-z]*|[\da-zа-я]+|[а-я][А-Я]|[А-Я]+[а-я]*)'


# full telegram user name
def get_full_name(user):
    if not user.first_name:
        return user.last_name
    if not user.last_name:
        return user.first_name
    return user.first_name + " " + user.last_name


# telegram user description
def get_user_info_fields(user):
    return [user.id,
            user.username,
            get_full_name(user),
            "BOT" if user.bot else "USER"]


# telegram group description
def get_group_info_fields(group):
    return [group.id,
            group.username,
            group.title,
            "GROUP[{}]".format(group.participants_count)]


def search_accounts(request, client):
    """
    Search accounts in Telegram
    :param request: text request to search
    :param client: telegram client obj
    :return: result obj
    """
    try:
        result = client(SearchRequest(request, 10))
        return result
    except Exception as e:
        logging.warning(e)
        return []


def get_random_dork(max_str_length, max_strs_count):
    """
    Create array of random words
    :param max_str_length: max length of word (2 for ab cd ef / a bc d)
    :param max_strs_count: max word count (3 for ab cd ed / ab cd)
    :return: array of strs
    """
    random_strs_count = random.randint(3, max_strs_count)
    request = []
    for _ in range(random_strs_count):
        random_str_length = random.randint(1, max_str_length)
        random_str = ""
        for __ in range(random_str_length):
            random_str += random.choice(string.ascii_letters + string.digits)
        request.append(random_str)

    return request


def is_weirdness_found(dork_words, found_words):
    """
    Check if search result is weird
    :param dork_words: words used for search
    :param found_words: words found (extracted from accounts data)
    :return: bool
    """
    strange = False
    for dork_word in dork_words:
        exist = False
        for found in found_words:
            if not found:
                continue
            if found.startswith(dork_word):
                exist = True
        if not exist:
            logging.warning("Overlap not found: %s in %s", dork_word, found_words)
            strange = True
    return strange


def custom_transliterate(name):
    """
    based on https://gist.github.com/ledovsky/6398962
    """
    custom_dict = {'а': 'a', 'б': 'b', 'в': ['w', 'v'], 'г': 'g',
                   'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh', 'з': 'z',
                   'и': ['y', 'i'], 'й': 'i', 'к': ['q', 'c', 'k'],
                   'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p',
                   'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f',
                   'х': ['h', 'kh'], 'ц': 'c', 'ч': 'cz', 'ш': 'sh',
                   'щ': 'scz', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e',
                   'ю': 'u', 'я': ['ja', 'ya']}
    deep_trans_arr = []
    for key in custom_dict:
        if key not in name:
            continue
        if isinstance(custom_dict[key], list):
            for repl in custom_dict[key]:
                res = custom_transliterate(name.replace(key, repl))
                deep_trans_arr += res
        else:
            name = name.replace(key, custom_dict[key])

    return deep_trans_arr if deep_trans_arr else [name]


def split_by_words(term):
    """
    Split word by rules to extract term indexed by Telegram
    :param request:
    :return:
    """
    if not term:
        return []
    # make all chars in lower case
    term = term.lower()
    # main rules
    splitted_by_size = re.findall(re_words, term) or [term]
    # separators
    splitted_by_seps = [re.split(r'[_ @,.\-()/№\"]', word) for word in splitted_by_size]
    # convert to simple array
    flat_list = [word for wordlist in splitted_by_seps for word in wordlist]
    # transliteration
    translitted = []
    for word in flat_list:
        try:
            translitted += custom_transliterate(word)
            translitted.append(word)
            translitted.append(translit(word, reversed=True))
        except Exception as e:
            logging.debug("Translit error: %s - %s", str(e), word)
    # unique
    unique_list = list(set(translitted))
    return unique_list


# search wrapper
def random_search(count, client):
    logging.info("Start random search")
    for i in range(count):
        weird_search(client)
        if i < count-1:
            sleep(5)


# main
def weird_search(client, dork=None):
    weirdness_found = False

    if not dork:
        dork_words = get_random_dork(2, 4)
        dork = " ".join(dork_words)
    else:
        dork_words = dork.split()

    logging.info("Dork is: %s\n", dork)
    dork_words = list(set([word.lower() for word in dork_words]))

    result = search_accounts(dork, client)

    exclude_user_ids = [user.user_id for user in result.my_results if isinstance(user, PeerUser)]
    exclude_group_ids = [channel.channel_id for channel in result.my_results if isinstance(channel, PeerChannel)]

    printable_results = []

    for group in result.chats:
        if group.id not in exclude_group_ids:
            words = split_by_words(group.title) + split_by_words(group.username)
            weirdness_found |= is_weirdness_found(dork_words, words)
            printable_results.append(get_group_info_fields(group))
            # hello PCL
            with open("chats.txt", "a") as file:
                file.write('{}\n'.format(group.username))
                file.close()

    for user in result.users:
        if user.id not in exclude_user_ids:
            words = split_by_words(user.last_name) + \
                    split_by_words(user.first_name) + \
                    split_by_words(user.username)
            weirdness_found |= is_weirdness_found(dork_words, words)
            printable_results.append(get_user_info_fields(user))

    if not printable_results:
        print("Sorry, no search results!")
    else:
        print(tabulate(printable_results, ['ID', 'USERNAME', 'FULL NAME', 'TYPE'], tablefmt='orgtbl'))
    print("")

    return weirdness_found


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument("session", help="file with Telegram user session")
    parser.add_argument("--dork", help="custom dork to search", type=str)
    parser.add_argument("--check", help="run weirdness checks", action="store_true")
    parser.add_argument("--random", help="run search by random dorks", action="store_true")
    parser.add_argument("--count", help="attempts to find weirdness (with --random)", type=int, default=100)
    args = parser.parse_args()

    tg_client = TelegramClient(args.session, api_id, api_hash)
    tg_client.start()

    if args.check:
        for weird_dork in ["OG Y RO", "W T l", "7 l PE", "fY k F 4", "q 2p c",
                           "8 qW v", "y i US dE", "sK W C k", "W 3Y V",
                           "G G c 1o", "u t Oq", "P 9 Tt"]:
            assert not weird_search(tg_client, weird_dork)
            sleep(5)

    if args.random:
        random_search(args.count, tg_client)
    elif args.dork:
        weird_search(tg_client, args.dork)
    else:
        random_search(1, tg_client)

    tg_client.disconnect()
