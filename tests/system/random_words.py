#!/usr/bin/env python
import string
import random
import json
import sys

DICT_FILE = '/etc/dictionaries-common/words'

def get_words():
    words = []
    try:
        with open(DICT_FILE, 'r') as f:
            words.extend(f.read().split('\n'))
    except IOError:
        try:
            with open('LICENSE', 'r') as f:
                words.extend(f.read().translate(string.maketrans("",""),
                                                string.punctuation).split())
        except IOError:
            print json.dumps({'error': "couldn't open dictionary file",
                              'filename': DICT_FILE})
        sys.exit(1)
    return words


def random_words(count=int(random.uniform(1,500)), sig='me'):
    words = get_words()
    random_word_list = []

    if sig:
        word_index = int(random.uniform(1, len(words)))
        random_word = words[word_index]

        salutation = ['Hey', 'Hi', 'Ahoy', 'Yo'][int(random.uniform(0,3))]
        random_word_list.append("{} {},\n\n".format(salutation, random_word))


    just_entered = False
    for i in range(count):
        word_index = int(random.uniform(1, len(words)))
        random_word = words[word_index]

        if i > 0 and not just_entered:
            random_word = ' ' + random_word

        just_entered = False

        if int(random.uniform(1,15)) == 1:
            random_word += ('.')

            if int(random.uniform(1,3)) == 1 and sig:
                random_word += ('\n')
                just_entered = True

            if int(random.uniform(1,3)) == 1 and sig:
                random_word += ('\n')
                just_entered = True

        random_word_list.append(random_word)

    text = ''.join(random_word_list) + '.'
    if sig:
        if int(random.uniform(1,2)) == 1:
            salutation = ['Cheers', 'Adios', 'Ciao', 'Bye'][int(random.uniform(0,3))]
            punct = ['.', ',', '!', ''][int(random.uniform(0,3))]
            text += "\n\n{}{}\n".format(salutation, punct)
        else:
            text += '\n\n'

        punct = ['-', '- ', '--', '-- '][int(random.uniform(0,3))]
        text += '{}{}'.format(punct, sig)

    return text


if __name__ == '__main__':
    print random_words()
