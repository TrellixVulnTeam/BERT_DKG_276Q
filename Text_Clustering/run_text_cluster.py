from __future__ import print_function

from sklearn.datasets import fetch_20newsgroups
from sklearn import metrics

from sklearn.cluster import MiniBatchKMeans
import os
import logging
from optparse import OptionParser
import sys
from time import time
from doc_embed import *
import numpy as np
from collections import Counter
import random

# Display progress logs on stdout
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

# parse commandline arguments
op = OptionParser()
op.add_option("--embed_type", dest="embed_type", default="get_bert2vec_embed")
op.add_option("--run_num", dest="run_num", type=int, default=10)
op.add_option("--cluster_num", dest="cluster_num", type=int, default=4)
op.add_option("--doc_path", dest="doc_path", default="ai")
print(__doc__)
op.print_help()


def is_interactive():
    return not hasattr(sys.modules['__main__'], '__file__')


# work-around for Jupyter notebook and IPython console
argv = [] if is_interactive() else sys.argv[1:]
(opts, args) = op.parse_args(argv)
if len(args) > 0:
    op.error("this script takes no arguments.")
    sys.exit(1)


# #############################################################################
# Load some categories from the training set
def load_20news_data():
    categories = [
        'alt.atheism',
        'talk.religion.misc',
        'comp.graphics',
        'sci.space',
    ]
    # Uncomment the following to do the analysis on all the categories
    # categories = None

    print("Loading 20 newsgroups dataset for categories:")
    print(categories)

    dataset = fetch_20newsgroups(subset='all', categories=categories,
                                 shuffle=True, random_state=42)

    print("%d documents" % len(dataset.data))
    print("%d categories" % len(dataset.target_names))
    print()
    return dataset


class Mydataset(object):
    def __init__(self, data, entities=None):
        self.data = data
        self.entities = entities


def load_ai_data():
    docs = []
    with open("data/ai_data_sents3000.txt", encoding="utf8") as f:
        doc = []
        for line in f.readlines():
            if line == "\n":
                docs.append(" ".join(doc))
                doc = []
            else:
                doc.append(line.strip())
    print("%d docs" % len(docs))

    docs_entities = []
    path = "NER_projects/pt_bert_ner/no_X_version/output_predict_doc_reg/prediction_entities.txt"
    if os.path.exists(path):
        with open(path, encoding="utf8") as f:
            for line in f.readlines():
                doc_entities = {"FIELD": set(), "TEC": set(), "MISC": set()}
                parts = line.strip("\n").split(", ")
                doc_entities['FIELD'] = set(parts[0].split("\t")) if parts[0].split("\t") != [""] else set()
                doc_entities['TEC'] = set(parts[1].split("\t")) if parts[1].split("\t") != [""] else set()
                doc_entities['MISC'] = set(parts[2].split("\t")) if parts[2].split("\t") != [""] else set()

                docs_entities.append(doc_entities)

    dataset = Mydataset(docs, docs_entities)
    print("%d docs_entities" % len(docs_entities))
    return dataset


def hook(dataset, X):
    if metric:
        labels = dataset.target
        true_k = np.unique(labels).shape[0]
        f = open("result_%s.txt" % opts.embed_type, "a")
        vs = np.array([])
        nmis = np.array([])
        for i in range(opts.run_num):
            # db = DBSCAN(eps=0.3, min_samples=10).fit(X)
            # labels_ = db.labels_
            km = MiniBatchKMeans(n_clusters=true_k, init='k-means++', n_init=1,
                                 init_size=1000, batch_size=1000, verbose=False)
            km.fit(X)
            labels_ = km.labels_

            print("--------------The larger the better (%d)---------------------" % (i + 1), file=f)
            v = metrics.v_measure_score(labels, labels_)
            nmi = metrics.normalized_mutual_info_score(labels, labels_)
            vs = np.append(vs, v)
            nmis = np.append(nmis, nmi)
            print("V-measure: %0.3f" % v, file=f)
            print("Normalized Mutual Information: %0.3f"
                  % nmi, file=f)
            print("\n\n", file=f)
        v_var = vs.var()
        v_mean = vs.mean()
        nmi_var = nmis.var()
        nmi_mean = nmis.mean()
        print("V-measure: var: %0.4f; mean: %0.4f" % (v_var, v_mean), file=f)
        print("Normalized Mutual Information: var: %0.4f; mean: %0.4f" % (nmi_var, nmi_mean), file=f)
        f.close()

        print("V-measure: var: %0.4f; mean: %0.4f" % (v_var, v_mean))
        print("Normalized Mutual Information: var: %0.4f; mean: %0.4f" % (nmi_var, nmi_mean))
    else:
        cluster_num = opts.cluster_num
        km = MiniBatchKMeans(n_clusters=cluster_num, init='k-means++', n_init=1,
                             init_size=1000, batch_size=1000, verbose=False)
        km.fit(X)
        labels = km.labels_
        # labels = np.ones([len(dataset.data)])
        # labels = np.array(list(map(lambda x: random.randint(0, cluster_num - 1), labels)))
        for cluster in range(cluster_num):
            entities = np.array(dataset.entities)[labels == cluster]
            fields = {}  # { lowercase entity: [normal case, nums, id]}
            tecs = {}
            co_occurence = {}  # {(field_id, tec_id):nums}
            for entity in entities:
                f_ids = []
                t_ids = []
                for e in entity["FIELD"]:
                    if e.lower() not in fields:
                        fields[e.lower()] = [e, 1, len(fields) + 1]
                    else:
                        fields[e.lower()][1] += 1
                    f_ids.append(fields[e.lower()][-1])
                for t in entity["TEC"]:
                    if t.lower() not in tecs:
                        tecs[t.lower()] = [t, 1, len(tecs) + 1]
                    else:
                        tecs[t.lower()][1] += 1
                    t_ids.append(tecs[t.lower()][-1])
                for f in f_ids:
                    for t in t_ids:
                        co_occurence.setdefault((f, t), 1)
                        co_occurence[(f, t)] += 1

            co_occurence = dict(sorted(co_occurence.items(), key=lambda x: x[1], reverse=True)[:100])
            used_fields = [i[0] for i in co_occurence.keys()]
            used_tecs = [i[1] for i in co_occurence.keys()]
            with open("cluster_%d.csv" % cluster, "w", encoding="utf8") as f:
                f.write('\n'.join(
                    ["Source,Target,Type,Weight"] + [','.join([str(f), str(t + len(fields)), "Directed", str(n)]) for
                                                     (f, t), n in co_occurence.items()]))
            with open("nodes_%d.csv" % cluster, "w", encoding="utf8") as f:
                f.write('\n'.join(
                    ["Id,Label"] + [','.join([str(id), str(normal)]) for lower, [normal, num, id] in
                                    fields.items() if id in used_fields]))
                f.write('\n'.join(
                    ["Id,Label"] + [','.join([str(id + len(fields)), str(normal)]) for lower, [normal, num, id] in
                                    tecs.items() if id in used_tecs]))

            eages = [(f, t + len(fields), n) for (f, t), n in list(co_occurence.items())[:50]]
            id2label = {id: normal for lower, [normal, num, id] in fields.items()}
            id2label.update({id + len(fields): normal for lower, [normal, num, id] in tecs.items()})

            import networkx as nx
            from matplotlib import pyplot as plt
            plt.switch_backend('agg')
            DG = nx.DiGraph()
            DG.add_weighted_edges_from(eages)

            pos = nx.spring_layout(DG, k=0.15, iterations=100)

            id2labels = {id: id2label[id] for id in pos.keys()}

            d = nx.degree(DG)
            d = [(d[node] + 1) * 50 for node in DG.nodes()]

            nx.draw_networkx_nodes(DG, pos, node_size=d)
            nx.draw_networkx_edges(DG, pos)
            nx.draw_networkx_labels(DG, pos, labels=id2labels)
            plt.axis('off')
            plt.savefig("cluster_%d.png" % cluster)  # save as png
            # plt.show()





def run():
    global metric
    if opts.doc_path == "20newsgroup":
        dataset = load_20news_data()
        metric = True
    else:
        dataset = load_ai_data()
        metric = False
    print("using embedding: %s" % opts.embed_type)
    print("run_num: %d" % opts.run_num)
    # hook(dataset, None)
    eval(opts.embed_type)(dataset, hook)


if __name__ == "__main__":
    run()
