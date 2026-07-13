"""linalg_lite.py 在架构中的位置。

自著数值内核(纯 stdlib,裁决 M3):randomized 截断 SVD——全平台唯一把
PPMI 稀疏矩阵压成 k 维语义向量的地方。零 numpy、零第三方 NLP/线性代数库。

确定性(MEM-A9):全部伪随机来自 blake2b(seed_key|counter) 派生的哈希族,
同 seed_key → 逐位同输出(容差 1e-9)。

管线:Ω(哈希高斯)→ Y=AΩ → 功率迭代 (A·Aᵀ)^q·Y(每步 Gram-Schmidt 正交化)
→ Q → B=QᵀA → B 的小型 SVD(对 B·Bᵀ 做双边 Jacobi 特征分解,自著)。

本文件另附 `dense_svd_reference`:与 rsvd 内部路径**独立的**单边 Jacobi
(直接旋转列)算法,仅供 test_ppmi_svd 做维四差分测试用,不参与任何运行时
决策(MEM-T4:rsvd 收敛界不逐字重证,以性质测试代证明)。
"""

from __future__ import annotations

import hashlib
import math

SparseMat = dict[tuple[int, int], float]
Dense = list[list[float]]

# --- 确定性伪随机(哈希族,MEM-A9)---------------------------------------


def _hash_floats(seed_key: str, counter: int, count: int) -> list[float]:
    """blake2b(seed_key|counter) 派生 count 个 [0,1) 均匀伪随机数。"""
    out: list[float] = []
    c = counter
    while len(out) < count:
        h = hashlib.blake2b(f"{seed_key}|{c}".encode("utf-8"), digest_size=32).digest()
        for i in range(0, len(h) - 7, 8):
            if len(out) >= count:
                break
            chunk = int.from_bytes(h[i : i + 8], "big")
            out.append(chunk / float(1 << 64))
        c += 1
    return out[:count]


def _gaussian(seed_key: str, counter: int, count: int) -> list[float]:
    """Box-Muller:均匀对 → 标准高斯,确定性。"""
    need_pairs = (count + 1) // 2
    u = _hash_floats(seed_key, counter, need_pairs * 2)
    out: list[float] = []
    for i in range(need_pairs):
        u1 = min(max(u[2 * i], 1e-12), 1.0 - 1e-12)
        u2 = u[2 * i + 1]
        r = math.sqrt(-2.0 * math.log(u1))
        theta = 2.0 * math.pi * u2
        out.append(r * math.cos(theta))
        out.append(r * math.sin(theta))
    return out[:count]


def random_gaussian_matrix(n_rows: int, n_cols: int, seed_key: str) -> Dense:
    if n_rows <= 0 or n_cols <= 0:
        return []
    flat = _gaussian(seed_key, 0, n_rows * n_cols)
    return [flat[i * n_cols : (i + 1) * n_cols] for i in range(n_rows)]


# --- 稀疏 × 稠密 --------------------------------------------------------


def sparse_matmul_dense(mat: SparseMat, shape: tuple[int, int], dense: Dense) -> Dense:
    """A(sparse, m x n) @ dense(n x r) -> (m x r)。"""
    m, _n = shape
    r = len(dense[0]) if dense else 0
    out: Dense = [[0.0] * r for _ in range(m)]
    for (i, j), v in mat.items():
        if j >= len(dense):
            continue
        row = dense[j]
        out_row = out[i]
        for c in range(r):
            out_row[c] += v * row[c]
    return out


def sparse_T_matmul_dense(
    mat: SparseMat, shape: tuple[int, int], dense: Dense
) -> Dense:
    """Aᵀ(sparse, m x n 视角) @ dense(m x r) -> (n x r)。"""
    _m, n = shape
    r = len(dense[0]) if dense else 0
    out: Dense = [[0.0] * r for _ in range(n)]
    for (i, j), v in mat.items():
        if i >= len(dense):
            continue
        row = dense[i]
        out_row = out[j]
        for c in range(r):
            out_row[c] += v * row[c]
    return out


def qT_matmul_sparse(q: Dense, mat: SparseMat, shape: tuple[int, int]) -> Dense:
    """Qᵀ(r x m) @ A(sparse, m x n) -> (r x n) 稠密。"""
    _m, n = shape
    r = len(q[0]) if q else 0
    out: Dense = [[0.0] * n for _ in range(r)]
    for (i, j), v in mat.items():
        if i >= len(q):
            continue
        qi = q[i]
        for c in range(r):
            out[c][j] += qi[c] * v
    return out


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: list[float]) -> float:
    return math.sqrt(_dot(a, a))


def orthonormalize(mat: Dense) -> Dense:
    """对 mat(m x r)的列做修正 Gram-Schmidt 正交化,退化列(范数≈0)置零向量。"""
    m = len(mat)
    r = len(mat[0]) if m else 0
    cols = [[mat[i][j] for i in range(m)] for j in range(r)]
    ortho_cols: list[list[float]] = []
    for j in range(r):
        v = cols[j][:]
        for u in ortho_cols:
            coeff = _dot(v, u)
            v = [vi - coeff * ui for vi, ui in zip(v, u)]
        norm = _norm(v)
        if norm < 1e-12:
            ortho_cols.append([0.0] * m)
        else:
            ortho_cols.append([vi / norm for vi in v])
    return [[ortho_cols[j][i] for j in range(r)] for i in range(m)]


def _mat_mat_T(b: Dense) -> Dense:
    """B(r x n) @ Bᵀ -> (r x r) 对称阵。"""
    r = len(b)
    out: Dense = [[0.0] * r for _ in range(r)]
    for a in range(r):
        for c in range(a, r):
            s = _dot(b[a], b[c])
            out[a][c] = s
            out[c][a] = s
    return out


# --- 双边 Jacobi 对称特征分解(rsvd 内部小矩阵求解用,自著)----------------


def jacobi_eigen(
    sym: Dense, *, max_sweeps: int = 60, tol: float = 1e-12
) -> tuple[list[float], list[list[float]]]:
    """对称矩阵的经典 Jacobi 特征值分解;返回(特征值降序, 对应特征向量列表)。

    每个特征向量是长度 n 的 list,eigvecs[idx] 对应 eigvals[idx]。
    """
    n = len(sym)
    if n == 0:
        return [], []
    a = [row[:] for row in sym]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _sweep in range(max_sweeps):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(n) if i != j)
        if off < tol:
            break
        for p in range(n):
            for q in range(p + 1, n):
                apq = a[p][q]
                if abs(apq) < 1e-15:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * apq)
                t_sign = 1.0 if theta >= 0 else -1.0
                t = t_sign / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                app, aqq = a[p][p], a[q][q]
                a[p][p] = c * c * app - 2 * s * c * apq + s * s * aqq
                a[q][q] = s * s * app + 2 * s * c * apq + c * c * aqq
                a[p][q] = 0.0
                a[q][p] = 0.0
                for k in range(n):
                    if k != p and k != q:
                        akp, akq = a[k][p], a[k][q]
                        a[k][p] = c * akp - s * akq
                        a[p][k] = a[k][p]
                        a[k][q] = s * akp + c * akq
                        a[q][k] = a[k][q]
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    eigvals = [a[i][i] for i in range(n)]
    order = sorted(range(n), key=lambda i: -eigvals[i])
    eigvals_sorted = [eigvals[i] for i in order]
    eigvecs_sorted = [[v[k][i] for k in range(n)] for i in order]
    return eigvals_sorted, eigvecs_sorted


# --- randomized 截断 SVD(公开入口)---------------------------------------


def rsvd(
    mat: SparseMat,
    shape: tuple[int, int],
    k: int,
    *,
    iters: int = 4,
    oversample: int = 8,
    seed_key: str,
) -> tuple[Dense, list[float]]:
    """randomized 截断 SVD;返回 (U_k 即 m x k 左奇异向量, sigma_k 降序)。

    确定性完全由 seed_key 决定(MEM-A9);矩阵/语料太薄(空矩阵、k<=0)时
    返回零填充结果,不 raise(冷启动降级由调用方 §3.2.3 决策表处理)。
    """
    m, n = shape
    kk = max(0, min(k, m, n))
    if kk <= 0 or not mat or m <= 0 or n <= 0:
        z = max(k, 0)
        return [[0.0] * z for _ in range(max(m, 0))], [0.0] * z

    r = max(kk, min(kk + max(0, oversample), n, m))
    omega = random_gaussian_matrix(n, r, seed_key)
    y = sparse_matmul_dense(mat, shape, omega)
    q = orthonormalize(y)
    for _ in range(max(0, iters)):
        z = sparse_T_matmul_dense(mat, shape, q)
        z = orthonormalize(z)
        y = sparse_matmul_dense(mat, shape, z)
        q = orthonormalize(y)

    b = qT_matmul_sparse(q, mat, shape)  # r x n
    bbt = _mat_mat_T(b)  # r x r 对称
    eigvals, eigvecs = jacobi_eigen(bbt)

    sigma = [math.sqrt(max(ev, 0.0)) for ev in eigvals[:kk]]
    u: Dense = [[0.0] * kk for _ in range(m)]
    for idx in range(kk):
        u_b = eigvecs[idx]
        for i in range(m):
            row = q[i]
            s = 0.0
            for c in range(len(u_b)):
                s += row[c] * u_b[c]
            u[i][idx] = s
    return u, sigma


def embed_doc(
    tokens: list[str], word_vecs: dict[str, list[float]], idf: dict[str, float]
) -> list[float]:
    """文向量 = idf 加权词向量均值,L2 归一;无可用词向量返回空表(降级信号)。"""
    dim = 0
    for v in word_vecs.values():
        dim = len(v)
        break
    if dim == 0 or not tokens:
        return []
    acc = [0.0] * dim
    wsum = 0.0
    for t in tokens:
        vec = word_vecs.get(t)
        if vec is None:
            continue
        w = idf.get(t, 1.0)
        for i in range(dim):
            acc[i] += w * vec[i]
        wsum += w
    if wsum <= 0.0:
        return []
    acc = [x / wsum for x in acc]
    norm = math.sqrt(sum(x * x for x in acc))
    if norm < 1e-12:
        return [0.0] * dim
    return [x / norm for x in acc]


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度,任一向量缺失/零向量返回 0.0(不 raise)。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return _dot(a, b) / (na * nb)


# --- 独立算法路径的稠密参考 SVD(仅供差分测试,MEM-T4)----------------------


def dense_svd_reference(
    dense: Dense, *, sweeps: int = 80, tol: float = 1e-14
) -> tuple[Dense, list[float]]:
    """单边 Jacobi(直接旋转 A 的列对),与 rsvd 内部(双边 Jacobi 对 B·Bᵀ 特征
    分解)是不同算法路径,专供 test_ppmi_svd 的维四差分测试使用;不参与任何
    运行时决策。返回 (U 全部列, sigma 降序),U 列数 = min(m, n)。
    """
    m = len(dense)
    n = len(dense[0]) if m else 0
    if m == 0 or n == 0:
        return [], []
    a = [row[:] for row in dense]
    for _sweep in range(sweeps):
        max_off = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                col_i = [a[r][i] for r in range(m)]
                col_j = [a[r][j] for r in range(m)]
                alpha = _dot(col_i, col_i)
                beta = _dot(col_j, col_j)
                gamma = _dot(col_i, col_j)
                max_off = max(max_off, abs(gamma))
                if abs(gamma) < 1e-15:
                    continue
                zeta = (beta - alpha) / (2.0 * gamma)
                t_sign = 1.0 if zeta >= 0 else -1.0
                t = t_sign / (abs(zeta) + math.sqrt(1.0 + zeta * zeta))
                c = 1.0 / math.sqrt(1.0 + t * t)
                s = c * t
                for r in range(m):
                    ci, cj = a[r][i], a[r][j]
                    a[r][i] = c * ci - s * cj
                    a[r][j] = s * ci + c * cj
        if max_off < tol:
            break
    sigma: list[float] = []
    u_cols: list[list[float]] = []
    for j in range(n):
        col = [a[r][j] for r in range(m)]
        norm = math.sqrt(_dot(col, col))
        sigma.append(norm)
        u_cols.append([x / norm for x in col] if norm > 1e-12 else [0.0] * m)
    order = sorted(range(n), key=lambda j: -sigma[j])
    sigma_sorted = [sigma[j] for j in order]
    u = [[u_cols[j][i] for j in order] for i in range(m)]
    return u, sigma_sorted
