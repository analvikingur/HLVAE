import collections
import os
import re
import numpy as np
from six.moves import cPickle
from utils.functions import *


class BatchLoader:
    def __init__(self, data_path_prefix='../'):
        """
        :param data_path_prefix: string prefix to path of data folder
        """

        assert isinstance(data_path_prefix, str), \
            'Invalid data_path_prefix type. Required {}, but {} found'.format(str, type(data_path_prefix))

        data_path = data_path_prefix + 'data/'

        self.ann_path = data_path + 'ann.txt'
        assert os.path.exists(self.ann_path), 'Annotations file not found'

        self.images_path = data_path + "images/"
        assert os.path.exists(self.ann_path), 'Images file not found'

        '''
        go_token (or stop_token) uses to mark start (or end) of the sequence while decoding
        pad_token uses to fill tensor to fixed-size length
        '''
        self.go_token = '>'
        self.stop_token = '<'
        self.word_level_pad_token = '|'
        self.character_level_pad_token = ''

        tensors_path = data_path + 'preprocessed_data/'
        self.idx_files = [tensors_path + 'words_vocab.pkl',
                          tensors_path + 'characters_vocab.pkl']
        self.tensor_files = [tensors_path + 'train_tensor.npy', tensors_path + 'valid_tensor.npy']

        idx_files_exist = fold(f_and, [os.path.exists(file) for file in self.idx_files], True)
        tensor_files_exist = fold(f_and, [os.path.exists(file) for file in self.tensor_files], True)

        if idx_files_exist and tensor_files_exist:
            self.load_preprocessed_data()
            print('preprocessed data have loaded')
        else:
            self.preprocess_data()
            print('data have preprocessed')

        # this index is uses to iterate over all annotations to train word embeddings
        self.word_embedding_index = 0

    def build_character_vocab(self, data):
        """
        :param data: whole data string
        :return: chars_vocab_size - size of unique characters in corpus
                 idx_to_char - array of shape [chars_vocab_size] containing ordered list of inique characters
                 char_to_idx - dictionary of shape [chars_vocab_size]
                        such that idx_to_char[char_to_idx[some_char]] = some_char
                        where some_char is such that idx_to_char contains it
        """

        # unique characters with blind symbol
        chars = list(set(data)) + [self.character_level_pad_token,
                                   self.word_level_pad_token,
                                   self.go_token,
                                   self.stop_token]
        chars_vocab_size = len(chars)

        # mappings itself
        idx_to_char = chars
        char_to_idx = {x: i for i, x in enumerate(idx_to_char)}

        return chars_vocab_size, idx_to_char, char_to_idx

    def build_word_vocab(self, sentences):
        """
        :param sentences: array of words
        :return: words_vocab_size – size of unique words in corpus
                 idx_to_word – array of shape [words_vocab_size] containing ordered list of inique words
                 word_to_idx – dictionary of shape [words_vocab_size]
                        such that idx_to_word[word_to_idx[some_word]] = some_word
                        where some_word is such that idx_to_word contains it
        """

        # Build vocabulary
        word_counts = collections.Counter(sentences)

        # Mapping from index to word
        idx_to_word = [x[0] for x in word_counts.most_common()]
        idx_to_word = list(sorted(idx_to_word)) + [self.word_level_pad_token, self.go_token, self.stop_token]

        words_vocab_size = len(idx_to_word)

        # Mapping from word to index
        word_to_idx = {x: i for i, x in enumerate(idx_to_word)}

        return words_vocab_size, idx_to_word, word_to_idx

    def preprocess_data(self):
        """
        performs data preprocessing
        """

        # be aware that ann.txt should't contain empty string in the end of file
        with open(self.ann_path, "r") as f:
            annotations = f.read()

        annotations = np.array(annotations.split('\n'))
        annotations = np.array([annotation.split('\t') for annotation in annotations])
        annotations = np.array([[element[:-2] for element in line] for line in annotations])

        self.num_annotations = len(annotations)

        merged_annotations = " ".join(annotations[:, 1])
        self.chars_vocab_size, self.idx_to_char, self.char_to_idx = self.build_character_vocab(merged_annotations)
        merged_word_annotations = merged_annotations.split()
        self.words_vocab_size, self.idx_to_word, self.word_to_idx = self.build_word_vocab(merged_word_annotations)
        del merged_annotations
        del merged_word_annotations

        # for now annotations is array of maps {'image':path_to_image, 'ann': array of words}
        annotations = np.array([{'image': row[0], 'ann': row[1].split()}
                                for row in annotations])

        self.max_word_len = np.amax([len(word) for word in self.idx_to_word])
        self.max_seq_len = np.amax([len(line['ann']) for line in annotations])

        np.random.shuffle(annotations)
        test_train_annotations = [annotations[:500], annotations[500:]]
        [self.test, self.train] = [[{'image': row['image'],
                                     'word_ann': [self.word_to_idx[word] for word in row['ann']],
                                     'character_ann': [self.encode_characters(word) for word in row['ann']]}
                                    for row in target]
                                   for target in test_train_annotations]

        self.embeddings_learning_data = [[self.word_to_idx[word] for word in row['ann']] for row in annotations]

        np.save(self.tensor_files[0], self.train)
        np.save(self.tensor_files[1], self.test)

        with open(self.idx_files[0], 'wb') as f:
            cPickle.dump(self.idx_to_word, f)

        with open(self.idx_files[1], 'wb') as f:
            cPickle.dump(self.idx_to_char, f)

    def load_preprocessed_data(self):

        [self.idx_to_word, self.idx_to_char] = [cPickle.load(open(file, "rb")) for file in self.idx_files]
        [self.words_vocab_size, self.chars_vocab_size] = [len(idx) for idx in [self.idx_to_word, self.idx_to_char]]
        [self.word_to_idx, self.char_to_idx] = [dict(zip(idx, range(len(idx)))) for idx in
                                                [self.idx_to_word, self.idx_to_char]]
        self.max_word_len = np.amax([len(word) for word in self.idx_to_word])

        [self.train, self.test] = [np.load(path) for path in self.tensor_files]
        self.num_annotations = len(self.test) + len(self.train)
        self.max_seq_len = np.amax([len(row['word_ann']) for target in [self.train, self.test] for row in target])

        self.embeddings_learning_data = [row['word_ann'] for target in [self.train, self.test] for row in target]

    def next_embedding_seq(self, num_batches):
        """
        :return: pair of input and output for word embeddings learning for approproate indexes with aware of batches 
        """

        batches = [self.embeddings_learning_data[i % self.num_annotations]
                   for i in np.arange(self.word_embedding_index, self.word_embedding_index + num_batches)]

        self.word_embedding_index = (self.word_embedding_index + num_batches) % self.num_annotations

        result = [self._embedding_seq(batch) for batch in batches]
        result = np.concatenate(result, 1)

        [input, target] = result
        return input, target

    def _embedding_seq(self, seq):
        """
        :return: input and output for word embeddings learning,
                 where input = [b, b, c, c, d, d, e, e]
                 and output  = [a, c, b, d, d, e, d, g]
                 for seq [a, b, c, d, e, g] at index i
        """

        # input, target
        result = [[], []]
        seq_len = len(seq)

        for i in range(seq_len - 2):
            result[0].append(seq[i + 1])
            result[0].append(seq[i + 1])
            result[1].append(seq[i])
            result[1].append(seq[i + 2])

        return np.array(result)

    def encode_word(self, idx):
        result = np.zeros(self.words_vocab_size)
        result[idx] = 1
        return result

    def decode_word(self, word_idx):
        word = self.idx_to_word[word_idx]
        return word

    def sample_word_from_distribution(self, distribution):
        ix = np.random.choice(range(self.words_vocab_size), p=distribution.ravel())
        x = np.zeros((self.words_vocab_size, 1))
        x[ix] = 1
        return self.idx_to_word[np.argmax(x)]

    def encode_characters(self, characters):
        word_len = len(characters)
        to_add = self.max_word_len - word_len
        characters_idx = [self.char_to_idx[i] for i in characters] + \
                         to_add * [self.char_to_idx[self.character_level_pad_token]]
        return characters_idx

    def decode_characters(self, characters_idx):
        characters = [self.idx_to_char[i] for i in characters_idx]
        return ''.join(characters)
