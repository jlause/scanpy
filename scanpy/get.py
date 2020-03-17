"""This module contains helper functions for accessing data."""
from typing import Optional, Iterable, Tuple
import warnings

import numpy as np
import pandas as pd
from scipy.sparse import spmatrix

from anndata import AnnData
# --------------------------------------------------------------------------------
# Plotting data helpers
# --------------------------------------------------------------------------------


# TODO: implement diffxpy method, make singledispatch
def rank_genes_groups_df(
    adata: AnnData,
    group: str,  # Can this be something other than a str?
    *,
    key: str = "rank_genes_groups",
    pval_cutoff: Optional[float] = None,
    log2fc_min: Optional[float] = None,
    log2fc_max: Optional[float] = None,
    gene_symbols: Optional[str] = None,
) -> pd.DataFrame:
    """\
    :func:`scanpy.tl.rank_genes_groups` results in the form of a
    :class:`~pandas.DataFrame`.

    Params
    ------
    adata
        Object to get results from.
    group
        Which group (as in :func:`scanpy.tl.rank_genes_groups`'s `groupby`
        argument) to return results from.
    key
        Key differential expression groups were stored under.
    pval_cutoff
        Minimum adjusted pval to return.
    log2fc_min
        Minumum logfc to return.
    log2fc_max
        Maximum logfc to return.
    gene_symbols
        Column name in `.var` DataFrame that stores gene symbols. Specifying
        this will add that column to the returned dataframe.

    Example
    -------
    >>> import scanpy as sc
    >>> pbmc = sc.datasets.pbmc68k_reduced()
    >>> sc.tl.rank_genes_groups(pbmc, groupby="louvain", use_raw=True, n_genes=pbmc.shape[1])
    >>> dedf = sc.get.rank_genes_groups_df(pbmc, group="0")
    """
    d = pd.DataFrame()
    for k in ['scores', 'names', 'logfoldchanges', 'pvals', 'pvals_adj']:
        d[k] = adata.uns[key][k][group]
    if pval_cutoff is not None:
        d = d[d["pvals_adj"] < pval_cutoff]
    if log2fc_min is not None:
        d = d[d["logfoldchanges"] > log2fc_min]
    if log2fc_max is not None:
        d = d[d["logfoldchanges"] < log2fc_max]
    if gene_symbols is not None:
        d = d.join(adata.var[gene_symbols], on="names")
    return d


def obs_df(
    adata: AnnData,
    keys: Iterable[str] = (),
    obsm_keys: Iterable[Tuple[str, int]] = (),
    *,
    layer: str = None,
    gene_symbols: str = None,
    use_raw: bool = False,
) -> pd.DataFrame:
    """\
    Return values for observations in adata.

    Params
    ------
    adata
        AnnData object to get values from.
    keys
        Keys from either `.var_names`, `.var[gene_symbols]`, or `.obs.columns`.
    obsm_keys
        Tuple of `(key from obsm, column index of obsm[key])`.
    layer
        Layer of `adata` to use as expression values.
    gene_symbols
        Column of `adata.var` to search for `keys` in.
    use_raw
        Whether to get expression values from `adata.raw`.

    Returns
    -------
    A dataframe with `adata.obs_names` as index, and values specified by `keys`
    and `obsm_keys`.

    Examples
    --------
    Getting value for plotting:

    >>> import scanpy as sc
    >>> pbmc = sc.datasets.pbmc68k_reduced()
    >>> plotdf = sc.get.obs_df(
            pbmc,
            keys=["CD8B", "n_genes"],
            obsm_keys=[("X_umap", 0), ("X_umap", 1)]
        )
    >>> plotdf.plot.scatter("X_umap0", "X_umap1", c="CD8B")

    Calculating mean expression for marker genes by cluster:

    >>> pbmc = sc.datasets.pbmc68k_reduced()
    >>> marker_genes = ['CD79A', 'MS4A1', 'CD8A', 'CD8B', 'LYZ']
    >>> genedf = sc.get.obs_df(
            pbmc,
            keys=["louvain", *marker_genes]
        )
    >>> grouped = genedf.groupby("louvain")
    >>> mean, var = grouped.mean(), grouped.var()
    """
    if use_raw and layer is not None:
        raise ValueError("Cannot specify use_raw=True and a layer at the same time.")
    ad = adata.raw if use_raw else adata
    idx = ad.var_names if gene_symbols is None else ad.var[gene_symbols]
    gene_names = pd.Series(ad.var_names, index=idx)
    del ad, idx

    lookup_keys = []
    not_found = []
    found_twice = []
    for key in keys:
        in_obs, in_var_index = False, False
        if key in adata.obs.columns:
            lookup_keys.append(key)
            in_obs = True
        if key in gene_names.index:
            in_var_index = True
            if not in_obs:
                lookup_keys.append(gene_names[key])
        # Test failure cases
        if not (in_obs or in_var_index):
            not_found.append(key)
        elif in_obs and in_var_index:
            found_twice.append(key)
    if len(not_found) > 0 or len(found_twice) > 0:
        ad_str = "adata.raw" if use_raw else "adata"
        if gene_symbols is None:
            gene_error = f"`{ad_str}.var_names`"
        else:
            gene_error = f"gene_symbols column `{ad_str}.var['{gene_symbols}']`"
        if len(found_twice) > 0:
            raise KeyError(
                f"Found keys {found_twice} in columns of `obs` and in {gene_error}.\n"
                "\n"
                "This will be an error in a future version of scanpy, "
                "but interpreting as a variable name for now."
            )
        else:
            raise KeyError(
                f"Could not find keys '{not_found}' in columns of `adata.obs` or in"
                f" {gene_error}."
            )

    # Make df
    df = pd.DataFrame(index=adata.obs_names)
    for k, l in zip(keys, lookup_keys):
        if not use_raw or k in adata.obs.columns:
            df[k] = adata.obs_vector(l, layer=layer)
        else:
            df[k] = adata.raw.obs_vector(l)
    for k, idx in obsm_keys:
        added_k = f"{k}-{idx}"
        val = adata.obsm[k]
        if isinstance(val, np.ndarray):
            df[added_k] = np.ravel(val[:, idx])
        elif isinstance(val, spmatrix):
            df[added_k] = np.ravel(val[:, idx].toarray())
        elif isinstance(val, pd.DataFrame):
            df[added_k] = val.loc[:, idx]
    return df


def var_df(
    adata: AnnData,
    keys: Iterable[str] = (),
    varm_keys: Iterable[Tuple[str, int]] = (),
    *,
    layer: str = None,
) -> pd.DataFrame:
    """\
    Return values for observations in adata.

    Params
    ------
    adata
        AnnData object to get values from.
    keys
        Keys from either `.obs_names`, or `.var.columns`.
    varm_keys
        Tuple of `(key from varm, column index of varm[key])`.
    layer
        Layer of `adata` to use as expression values.

    Returns
    -------
    A dataframe with `adata.var_names` as index, and values specified by `keys`
    and `varm_keys`.
    """
    # Argument handling
    lookup_keys = []
    not_found = []
    found_twice = []
    for key in keys:
        in_var, in_obs_index = False, False
        if key in adata.var.columns:
            in_var = True
            lookup_keys.append(key)
        if key in adata.obs_names:
            in_obs_index = True
            if not in_var:
                lookup_keys.append(key)
        # Test failure cases
        if not (in_var or in_obs_index):
            not_found.append(key)
        elif in_var and in_obs_index:
            found_twice.append(key)
    if len(found_twice) > 0:
        raise KeyError(
            f"Found keys {found_twice} in columns of `var` and in `adata.obs_names`.\n"
            "\n"
            "This will be an error in a future version of scanpy, "
            "but interpreting as a observation name for now."
        )
    if len(not_found) > 0:
        raise KeyError(
            f"Could not find keys '{not_found}' in columns of `adata.var` or"
            " in `adata.obs_names`."
        )

    # Make df
    df = pd.DataFrame(index=adata.var_names)
    for k, l in zip(keys, lookup_keys):
        df[k] = adata.var_vector(l, layer=layer)
    for k, idx in varm_keys:
        added_k = f"{k}-{idx}"
        val = adata.varm[k]
        if isinstance(val, np.ndarray):
            df[added_k] = np.ravel(val[:, idx])
        elif isinstance(val, spmatrix):
            df[added_k] = np.ravel(val[:, idx].toarray())
        elif isinstance(val, pd.DataFrame):
            df[added_k] = val.loc[:, idx]
    return df
