from __future__ import annotations

from typing import Callable, Generator, Iterator, Optional

from .space_models import Space


# ================================================================
# 遍历
# ================================================================

def walk_dfs(
    root: Space,
    *,
    order: str = "pre",             # "pre" | "post"
    include_root: bool = True,
) -> Generator[Space, None, None]:
    """
    深度优先遍历。

    order="pre"  → 父节点先于子节点 yield（最常用，适合自顶向下计算）
    order="post" → 子节点先于父节点 yield（适合自底向上汇总，如 BOM）

    示例：
        for node in walk_dfs(cabinet_root, order="post"):
            bom_aggregator.collect(node)
    """
    if order == "pre":
        if include_root:
            yield root
        for child in root.children:
            yield from walk_dfs(child, order="pre", include_root=True)
    elif order == "post":
        for child in root.children:
            yield from walk_dfs(child, order="post", include_root=True)
        if include_root:
            yield root
    else:
        raise ValueError(f"order 必须是 'pre' 或 'post'，收到: {order!r}")


def walk_bfs(root: Space) -> Generator[Space, None, None]:
    """
    广度优先遍历（按层展开）。
    适合需要"同层节点一起处理"的场景，如同层隔板均分计算。

    示例：
        layers = list(walk_bfs(root))
    """
    queue: list[Space] = [root]
    while queue:
        node = queue.pop(0)
        yield node
        queue.extend(node.children)


def iter_leaves(root: Space) -> Generator[Space, None, None]:
    """
    只 yield 叶节点（无子节点的 Space）。
    叶节点通常对应最终的柜格/抽屉空间，是板件生成的基本单元。
    """
    for node in walk_dfs(root):
        if node.is_leaf:
            yield node


def iter_ancestors(node: Space, include_self: bool = False) -> Generator[Space, None, None]:
    """
    从当前节点向上遍历祖先链，直到根节点。
    include_self=True 时第一个 yield 是节点本身。

    示例：
        path = list(iter_ancestors(leaf, include_self=True))
        # → [leaf, parent, grandparent, ..., root]
    """
    if include_self:
        yield node
    current = node.parent
    while current is not None:
        yield current
        current = current.parent


# ================================================================
# 查找
# ================================================================

def find_by_id(root: Space, node_id: str) -> Optional[Space]:
    """
    按 UUID 查找节点，找不到返回 None。
    DFS 遍历，找到即停（短路）。
    """
    for node in walk_dfs(root):
        if node.id == node_id:
            return node
    return None


def find_by_name(root: Space, name: str) -> list[Space]:
    """
    按 name 查找所有匹配节点（name 不保证唯一）。
    返回列表，调用方自行处理多结果情况。
    """
    return [node for node in walk_dfs(root) if node.name == name]


def find_first(root: Space, predicate: Callable[[Space], bool]) -> Optional[Space]:
    """
    返回第一个满足 predicate 的节点，找不到返回 None。

    示例：
        node = find_first(root, lambda n: n.height > 800)
    """
    for node in walk_dfs(root):
        if predicate(node):
            return node
    return None


def find_all(root: Space, predicate: Callable[[Space], bool]) -> list[Space]:
    """
    返回所有满足 predicate 的节点列表。

    示例：
        dirty_nodes = find_all(root, lambda n: n.is_dirty)
    """
    return [node for node in walk_dfs(root) if predicate(node)]


def find_dirty(root: Space) -> list[Space]:
    """返回树中所有 dirty_flag != CLEAN 的节点，供 incremental_solver 使用。"""
    return find_all(root, lambda n: n.is_dirty)


# ================================================================
# 路径解析
# ================================================================

def get_path(node: Space) -> list[Space]:
    """
    返回从根节点到当前节点的路径列表（含两端）。

    示例：
        path = get_path(leaf)
        # → [root, level1, level2, leaf]
    """
    path = list(iter_ancestors(node, include_self=True))
    path.reverse()
    return path


def get_path_ids(node: Space) -> list[str]:
    """返回路径上各节点的 id 列表，适合序列化/日志。"""
    return [n.id for n in get_path(node)]


def get_path_names(node: Space) -> str:
    """
    返回路径的可读字符串，用 '/' 分隔，方便调试输出。

    示例：
        get_path_names(leaf)
        # → "整体柜/左柜/下格"
    """
    return "/".join(
        n.name or n.space_type.value
        for n in get_path(node)
    )


def get_siblings(node: Space) -> list[Space]:
    """
    返回同级节点列表（不含自身）。
    父节点为 None 时返回空列表。
    """
    if node.parent is None:
        return []
    return [c for c in node.parent.children if c is not node]


def common_ancestor(a: Space, b: Space) -> Optional[Space]:
    """
    返回两个节点的最近公共祖先（LCA）。
    两节点不在同一棵树时返回 None。

    用途：判断两块板是否属于同一柜格，缝隙规则依赖此关系。
    """
    ancestors_a = {n.id: n for n in iter_ancestors(a, include_self=True)}
    for anc in iter_ancestors(b, include_self=True):
        if anc.id in ancestors_a:
            return anc
    return None


# ================================================================
# 插入 / 删除
# ================================================================

def insert_between(parent: Space, child: Space, new_node: Space) -> None:
    """
    在 parent 和 child 之间插入 new_node。

    before:  parent → child
    after:   parent → new_node → child

    用途：splitter 在已有子节点之间插入分割节点。
    """
    if child not in parent.children:
        raise ValueError(f"{child!r} 不是 {parent!r} 的直接子节点")
    idx = parent.children.index(child)
    parent.children.pop(idx)
    child.parent = new_node
    new_node.children.append(child)
    new_node.parent = parent
    parent.children.insert(idx, new_node)
    parent.dirty_flag = __import__(
        "core.dirty.dirty_flags", fromlist=["DirtyFlag"]
    ).DirtyFlag.DIRTY


def replace_node(old: Space, new: Space) -> None:
    """
    用 new 替换 old，保持 old 在父节点中的位置。
    old 的子节点全部迁移到 new 下。

    用途：空间类型切换（普通格 → 抽屉格）时原地替换节点。
    """
    parent = old.parent
    if parent is not None:
        idx = parent.children.index(old)
        parent.children[idx] = new
        new.parent = parent
        old.parent = None

    # 迁移子节点
    for child in old.children:
        child.parent = new
    new.children = list(old.children)
    old.children = []


def flatten(root: Space) -> list[Space]:
    """
    返回树中所有节点的扁平列表（DFS 先序）。
    适合需要批量操作所有节点的场景（如全量序列化）。
    """
    return list(walk_dfs(root))


# ================================================================
# 统计
# ================================================================

def count_nodes(root: Space) -> int:
    """树中节点总数（含根）。"""
    return sum(1 for _ in walk_dfs(root))


def count_leaves(root: Space) -> int:
    """叶节点数量，等于最终柜格数量。"""
    return sum(1 for _ in iter_leaves(root))


def max_depth(root: Space) -> int:
    """
    树的最大深度（根节点深度为 0）。
    深度过大（> 8）通常说明切割层级有误，可在 validator 里引用此函数。
    """
    if root.is_leaf:
        return 0
    return 1 + max(max_depth(child) for child in root.children)


# ================================================================
# 调试
# ================================================================

def print_stats(root: Space) -> None:
    """打印树的基本统计信息，开发期快速了解当前树状态。"""
    print(
        f"[SpaceTree] "
        f"节点数={count_nodes(root)}  "
        f"叶节点={count_leaves(root)}  "
        f"最大深度={max_depth(root)}  "
        f"脏节点={len(find_dirty(root))}"
    )
