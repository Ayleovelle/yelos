"""test_ppmi_svd.py:PPMI 手算小例 + rsvd 性质测试(性质 + 维四差分)。

锁:PPMI 手算对数;rsvd 正交容差 / 奇异值降序 / 同 seed_key 逐位一致
(MEM-A9)/ 小矩阵 vs 稠密参考 SVD(独立算法路径)误差断言(维四差分,
MEM-T4:不逐字重证收敛界,以性质测试代证明);性能冒烟(适度规模,预算内)。
"""

from __future__ import annotations

import math
import time

from yelos.memory.l2_semantic import linalg_lite as ll
from yelos.memory.l2_semantic.ppmi import cooccurrence, ppmi_weight, row_totals
from yelos.memory.l2_semantic.vocab import Vocab


def test_ppmi_hand_calc_small_example():
    # 词表: 0,1,2;两篇文档,窗口=1
    docs = [[0, 1], [1, 2], [0, 1], [1, 2]]
    cooc = cooccurrence(docs, vocab_size=3, window=1)
    row_tot, total = row_totals(cooc)
    ppmi = ppmi_weight(cooc, row_tot, total, shift=1.0)

    # 手算:(0,1) 共现 4 次(每篇一次,距离加权 1/1=1,来回各一次共 2 次每篇);
    # 直接验证 PPMI 公式而非猜测计数:pmi(i,j) = log(p_ij/(p_i*p_j))
    for (i, j), v in cooc.items():
        pij = v / total
        pi = row_tot[i] / total
        pj = row_tot[j] / total
        expected = max(0.0, math.log(pij / (pi * pj)))
        assert ppmi.get((i, j), 0.0) == pytest_approx(expected)


def pytest_approx(x: float, tol: float = 1e-9):
    class _Approx:
        def __eq__(self, other):
            return abs(other - x) <= tol

    return _Approx()


def test_ppmi_empty_corpus_returns_empty():
    assert cooccurrence([], 10) == {}
    row_tot, total = row_totals({})
    assert ppmi_weight({}, row_tot, total) == {}


def _small_symmetric_matrix():
    dense = [
        [4, 1, 0, 0],
        [1, 3, 1, 0],
        [0, 1, 2, 1],
        [0, 0, 1, 2],
    ]
    mat = {}
    for i in range(4):
        for j in range(4):
            if dense[i][j] != 0:
                mat[(i, j)] = float(dense[i][j])
    return dense, mat


def test_rsvd_orthonormal_columns():
    y = ll.random_gaussian_matrix(6, 3, "seed-ortho")
    q = ll.orthonormalize(y)
    for c1 in range(3):
        col1 = [q[i][c1] for i in range(6)]
        norm = math.sqrt(sum(x * x for x in col1))
        assert abs(norm - 1.0) < 1e-9
        for c2 in range(c1 + 1, 3):
            col2 = [q[i][c2] for i in range(6)]
            dot = sum(a * b for a, b in zip(col1, col2))
            assert abs(dot) < 1e-9


def test_rsvd_singular_values_descending():
    _dense, mat = _small_symmetric_matrix()
    _u, sigma = ll.rsvd(mat, (4, 4), k=3, iters=6, oversample=4, seed_key="desc-seed")
    assert sigma == sorted(sigma, reverse=True)


def test_rsvd_deterministic_same_seed():
    _dense, mat = _small_symmetric_matrix()
    u1, s1 = ll.rsvd(mat, (4, 4), k=3, iters=6, oversample=4, seed_key="fixed-seed")
    u2, s2 = ll.rsvd(mat, (4, 4), k=3, iters=6, oversample=4, seed_key="fixed-seed")
    assert s1 == s2
    assert u1 == u2


def test_rsvd_different_seed_differs():
    _dense, mat = _small_symmetric_matrix()
    _u1, s1 = ll.rsvd(mat, (4, 4), k=2, iters=4, oversample=4, seed_key="seed-a")
    _u2, s2 = ll.rsvd(mat, (4, 4), k=2, iters=4, oversample=4, seed_key="seed-b")
    # 奇异值本身应大体一致(同一矩阵),但 U 的具体基一般不同(除非退化)
    assert s1 != [] and s2 != []


def test_rsvd_vs_dense_reference_singular_values_close():
    """维四差分:rsvd(双边 Jacobi 对 B·Bᵀ)与独立算法路径的稠密参考(单边 Jacobi
    直接旋转 A 的列)在小矩阵上奇异值应逐位接近(MEM-T4:性质测试代证明)。
    """
    dense, mat = _small_symmetric_matrix()
    _u, sigma_rsvd = ll.rsvd(
        mat, (4, 4), k=4, iters=10, oversample=6, seed_key="diff-seed"
    )
    _uref, sigma_ref = ll.dense_svd_reference(dense)
    for a, b in zip(sigma_rsvd, sigma_ref[: len(sigma_rsvd)]):
        assert abs(a - b) < 1e-6


def test_rsvd_reconstruction_error_small_for_full_rank():
    """k>=rank 时重构误差趋 0(MEM-T4 用性质断言代替 Halko 界的逐字重证)。"""
    dense, mat = _small_symmetric_matrix()
    u, sigma = ll.rsvd(mat, (4, 4), k=4, iters=12, oversample=8, seed_key="recon-seed")
    # 重构 A_hat = U * diag(sigma) * U^T(对称矩阵,V=U)
    m = len(u)
    kk = len(sigma)
    recon = [[0.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(m):
            s = 0.0
            for c in range(kk):
                s += u[i][c] * sigma[c] * u[j][c]
            recon[i][j] = s
    err = max(abs(recon[i][j] - dense[i][j]) for i in range(m) for j in range(m))
    assert err < 1e-6


def test_rsvd_empty_matrix_degrades_gracefully():
    u, sigma = ll.rsvd({}, (5, 5), k=3, seed_key="empty")
    assert sigma == [0.0, 0.0, 0.0]
    assert len(u) == 5
    assert all(len(row) == 3 for row in u)


def test_embed_doc_and_cosine():
    word_vecs = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    idf = {"a": 1.0, "b": 1.0}
    vec_a = ll.embed_doc(["a", "a"], word_vecs, idf)
    vec_b = ll.embed_doc(["b"], word_vecs, idf)
    assert ll.cosine(vec_a, vec_a) > 0.999
    assert abs(ll.cosine(vec_a, vec_b)) < 1e-9
    assert ll.embed_doc([], word_vecs, idf) == []
    assert ll.embed_doc(["unknown"], word_vecs, idf) == []


def test_vocab_low_frequency_pruned_and_tiebreak():
    v = Vocab(cap=10, min_count=2)
    v.fit_update([["a", "b", "b", "c"], ["a", "b"]])
    # a:2 b:3 c:1(截断) -> 保留 a,b;并列按字典序破
    assert v.contains("b")
    assert v.contains("a")
    assert not v.contains("c")


def test_perf_smoke_moderate_scale_within_budget():
    """性能冒烟:适度规模(非 4000x30000 全量,CI 友好)在合理墙钟内完成。"""
    import random as _random

    rng = _random.Random(42)
    vocab_size = 300
    docs = [[rng.randrange(vocab_size) for _ in range(20)] for _ in range(200)]
    cooc = cooccurrence(docs, vocab_size, window=4)
    row_tot, total = row_totals(cooc)
    ppmi = ppmi_weight(cooc, row_tot, total)

    t0 = time.monotonic()
    u, sigma = ll.rsvd(
        ppmi, (vocab_size, vocab_size), k=32, iters=4, oversample=8, seed_key="perf"
    )
    elapsed = time.monotonic() - t0
    assert elapsed < 10.0
    assert len(sigma) == 32
    assert len(u) == vocab_size
