import abc
import functools
import os
import time

import bpemb
import corenlp
import torch
#import torchtext

from utils.linking_utils import corenlp


class Embedder(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def tokenize(self, sentence):
        '''Given a string, return a list of tokens suitable for lookup.'''
        pass

    @abc.abstractmethod
    def untokenize(self, tokens):
        '''Undo tokenize.'''
        pass

    @abc.abstractmethod
    def lookup(self, token):
        '''Given a token, return a vector embedding if token is in vocabulary.
        If token is not in the vocabulary, then return None.'''
        pass

    @abc.abstractmethod
    def contains(self, token):
        pass

    @abc.abstractmethod
    def to(self, device):
        '''Transfer the pretrained embeddings to the given device.'''
        pass


class GloVe(Embedder):


    def __init__(self, kind, lemmatize=False):
        # 不再调用 torchtext.vocab.GloVe
        self.dim = 300
        self.lemmatize = lemmatize
        self.corenlp_annotators = ['tokenize', 'ssplit']
        if lemmatize:
            self.corenlp_annotators.append('lemma')
        
        # 建立一个空的或简单的映射，避免 WinError 127
        self.stoi = {} 
        self.vectors = torch.zeros((1, self.dim)) 
        print("Warning: GloVe is initialized with empty vectors to bypass torchtext error.")


    # def __init__(self, kind, lemmatize=False):
    #     cache = os.path.join(os.environ.get('CACHE_DIR', os.getcwd()), 'vector_cache')
    #     self.glove = torchtext.vocab.GloVe(name=kind, cache=cache)
    #     self.dim = self.glove.dim
    #     self.vectors = self.glove.vectors
    #     self.lemmatize = lemmatize
    #     self.corenlp_annotators = ['tokenize', 'ssplit']
    #     if lemmatize:
    #         self.corenlp_annotators.append('lemma')

    @functools.lru_cache(maxsize=1024)
    def tokenize(self, text):
        ann = corenlp.annotate(text, self.corenlp_annotators)
        if self.lemmatize:
            return [tok.lemma.lower() for sent in ann.sentence for tok in sent.token]
        else:
            return [tok.word.lower() for sent in ann.sentence for tok in sent.token]

    @functools.lru_cache(maxsize=1024)
    def tokenize_for_copying(self, text):
        ann = corenlp.annotate(text, self.corenlp_annotators)
        text_for_copying = [tok.originalText.lower() for sent in ann.sentence for tok in sent.token]
        if self.lemmatize:
            text = [tok.lemma.lower() for sent in ann.sentence for tok in sent.token]
        else:
            text = [tok.word.lower() for sent in ann.sentence for tok in sent.token]
        return text, text_for_copying

    def untokenize(self, tokens):
        return ' '.join(tokens)

    # def lookup(self, token):
    #     i = self.glove.stoi.get(token)
    #     if i is None:
    #         return None
    #     return self.vectors[i]

    # def contains(self, token):
    #     return token in self.glove.stoi
    
    def lookup(self, token):
    # 保持返回类型一致：None 或 torch.Tensor
        if token in self.stoi:
            return self.vectors[self.stoi[token]]
        return None

    def contains(self, token):
        # 返回类型严格保持为 bool
        return token in self.stoi

    def to(self, device):
        self.vectors = self.vectors.to(device)