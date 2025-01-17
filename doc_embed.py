# -*- coding:utf8 -*-

# sklearn的TF-IDF模型
def get_tfidf_embed(dataset, hook):
    from sklearn.feature_extraction.text import TfidfVectorizer
    import sklearn.preprocessing as preprocessing
    vectorizer = TfidfVectorizer(max_df=1000, max_features=30000,
                                 min_df=2, stop_words='english',
                                 use_idf=True)
    X = vectorizer.fit_transform(dataset.data)
    X = preprocessing.normalize(X)
    hook(dataset, X.toarray())
    return X


# gensim的TF-IDF模型
def get_tfidf_embed2(dataset, hook):
    import gensim
    from gensim.models.tfidfmodel import TfidfModel
    from gensim.corpora import Dictionary
    import sklearn.preprocessing as preprocessing
    docs = [gensim.utils.simple_preprocess(doc) for i, doc in enumerate(dataset.data)]
    dictionary = Dictionary(docs)
    corpus = [dictionary.doc2bow(text) for text in docs]
    tfidfModel = TfidfModel(corpus=corpus, dictionary=dictionary)

    X = tfidfModel[corpus]
    X = preprocessing.normalize(X)
    hook(dataset, X)
    return X


# gensim的LDA模型
def get_lda_embed(dataset, hook):
    import gensim
    from gensim.corpora.dictionary import Dictionary
    import sklearn.preprocessing as preprocessing
    import numpy as np
    docs = [gensim.utils.simple_preprocess(doc) for i, doc in enumerate(dataset.data)]
    dictionary = Dictionary(docs)
    dictionary.filter_extremes(no_below=2, no_above=0.8)
    corpus = [dictionary.doc2bow(text) for text in docs]
    tfidf = gensim.models.TfidfModel(corpus)
    corpus_tfidf = tfidf[corpus]
    lda = gensim.models.ldamodel.LdaModel(corpus=corpus_tfidf, num_topics=100)
    topics = lda.get_topics()
    X = []
    for doc in corpus:
        topic_probs = lda.get_document_topics(doc, per_word_topics=True)
        np.array(sorted(topic_probs[2],key=lambda x:x[1][1]))
        X.append(np.sum([topics[pair[0]]*pair[1] for pair in topic_probs], axis=0))
    X = preprocessing.normalize(X)
    hook(dataset,X)
    return X


# sklearn 的 LDA模型
def get_lda_embed2(dataset, hook):
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    import sklearn.preprocessing as preprocessing
    cntVector = CountVectorizer(max_df=1000, min_df=2, stop_words='english',max_features=30000)
    cntTf = cntVector.fit_transform(dataset.data)
    lda = LatentDirichletAllocation(n_components=200, max_iter=10)
    docres = lda.fit_transform(cntTf)
    X = preprocessing.normalize(docres)
    hook(dataset, X)
    return X


# gensim 的doc2vec模型
def get_doc2vec_embed(dataset, hook):
    import gensim
    from gensim.models.doc2vec import Doc2Vec, TaggedDocument
    import sklearn.preprocessing as preprocessing
    docs = [TaggedDocument(gensim.utils.simple_preprocess(doc), [i]) for i, doc in enumerate(dataset.data)]
    doc2vec_dbow = Doc2Vec(dm=0, vector_size=256, min_count=2, max_count=1000)
    doc2vec_dm = Doc2Vec(dm=1, vector_size=256, min_count=2, max_count=1000)
    doc2vec_dbow.build_vocab(docs)
    doc2vec_dm.build_vocab(docs)
    doc2vec_dbow.train(docs, total_examples=doc2vec_dbow.corpus_count, epochs=10)
    doc2vec_dm.train(docs, total_examples=doc2vec_dm.corpus_count, epochs=10)

    X = [doc2vec_dbow.infer_vector(doc.words) + doc2vec_dm.infer_vector(doc.words) for doc in docs]
    X = preprocessing.normalize(X)
    hook(dataset, X)
    return X


# 用训练好的BERT模型的最后一层求和作为序列向量，直接用官方的预训练模型效果较差。
def get_bert_embed(data):
    import torch
    import gensim
    from pytorch_pretrained_bert import BertModel, BertTokenizer
    docs = [gensim.utils.simple_preprocess(doc) for i, doc in enumerate(data)]
    device = torch.device("cuda", torch.cuda.current_device()) if torch.cuda.is_available() else torch.device("cpu")
    model = BertModel.from_pretrained('bert-base-uncased')  # 可以指定由专门预料上训练的模型路径
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased', do_lower_case=True)
    model.to(device)
    model.eval()
    X = []
    for i,doc in enumerate(docs):
        print("converting %d"%i)
        doc_tok = ['[CLS]']
        for word in doc:
            toks = tokenizer.tokenize(word)
            doc_tok.extend(toks)
        doc_tok = doc_tok[:511]+['[SEP]']
        doc_ids = tokenizer.convert_tokens_to_ids(doc_tok)
        tokens_tensor = torch.tensor([doc_ids]).to(device)
        with torch.no_grad():
            encoded_layers, pooled_output = model(tokens_tensor, output_all_encoded_layers=False)
        X.append(encoded_layers.sum(1).tolist()[0])
    return X


# 采用MD2vec模型，参数由 Args 类控制
def get_MD2vec_embed(dataset, hook):
    import sklearn.preprocessing as preprocessing
    from MD2vec.run_lm_finetuning import main
    X = main(dataset, Args(), hook)
    X = preprocessing.normalize(X)
    hook(dataset, X)
    return X

class Args(object):
    def __init__(self, train_file="./data/20newsgroup.txt", vocab="./MD2vec/vocab.txt",
                 bert_config="./MD2vec/bert_config.json", vocab_size=28000):
        self.train_file = train_file
        self.vocab = vocab
        self.bert_config = bert_config
        self.max_seq_length = 512
        self.do_train = True
        self.train_batch_size = 32
        self.learning_rate = 3e-4
        self.num_train_epochs = 10.0
        self.warmup_proportion = 0.1
        self.no_cuda = False
        self.do_lower_case = True
        self.local_rank = -1
        self.seed = 42
        self.gradient_accumulation_steps = 1
        self.fp16 = False
        self.loss_scale = 0
        self.vocab_size = vocab_size
        self.mask_prob = 1  # mask的比例
        self.all_mask = True  # 调试模式下，每个mask比例都会跑一遍
        self.weighted = False  # 是否采用实体词信息计算 weighted loss
        self.weight = 1.  # 如果采用weighted loss，设定的实体词权重
        self.output_dir = "./output_dir"
