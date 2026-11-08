"""Observed-only, municipal-stratified fractional-weight bootstrap on CPU.

The bands describe refitting sensitivity to the received sections. They do not
model arrival bias, absent municipalities or guarantee 90% election coverage.
The published point estimators are unchanged; known votes remain fixed.
"""
import numpy as np
import pandas as pd
from .data import build_snapshot, SECTION
from .models import Config, History, Snapshot, KEY, OBS, predict

METHODS = ('poststrat', 'swing', 'hierarchical')


class ReplicateProjector:
    """Batched algebra matching models.predict, with observed votes held fixed.

    Replica vote arrays follow history.frame row order. The replicated sample
    fits pending votes only; it never replaces votes already counted.
    """
    def __init__(self, history: History, snapshot: Snapshot):
        predict(snapshot, history, Config())  # Reuse the production input checks.
        f = history.frame.merge(snapshot.frame[OBS], on=KEY, how='left', validate='one_to_one')
        f[['n_observed', 'votes_a', 'votes_b']] = f[['n_observed', 'votes_a', 'votes_b']].fillna(0)
        self.n = f.n_sections.to_numpy(dtype=float)
        self.no = f.n_observed.to_numpy(dtype=float)
        self.a = f.votes_a.to_numpy(dtype=float); self.b = f.votes_b.to_numpy(dtype=float)
        self.prior = f.ref_share.to_numpy(dtype=float)
        self.per = f.ref_per_section.to_numpy(dtype=float)
        self.matched = f.matched.to_numpy(dtype=bool)
        self.train = (self.a + self.b > 0) & self.matched
        self.turnout_mask = self.matched & (self.no > 0)
        self.pending = (self.n - self.no) * self.per
        raw = np.stack([self.prior, np.log10(f.ref_size.to_numpy(dtype=float).clip(1))], axis=1)
        weights = self.per * self.n
        mean = (raw * weights[:, None]).sum(0) / max(weights.sum(), 1)
        scale = np.sqrt(((raw - mean) ** 2 * weights[:, None]).sum(0) / max(weights.sum(), 1))
        scale = np.where(scale > 1e-12, scale, 1.)
        self.X = np.column_stack([np.ones(len(f)), (raw - mean) / scale])
        self.states = [f.uf.eq(uf).to_numpy() for uf in f.uf.unique()]
        self.regions = [(f.region.eq(region).to_numpy(), [
            f.uf.eq(uf).to_numpy() for uf in f.loc[f.region.eq(region), 'uf'].unique()
        ]) for region in f.region.unique()]

    def predict(self, a, b, config: Config):
        if config.device != 'cpu' or config.method not in METHODS:
            raise ValueError('Bootstrap supports the three methods on CPU only')
        if min(config.lambda_region, config.lambda_uf, config.lambda_turnout) < 0:
            raise ValueError('Penalties must be nonnegative')
        a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
        if a.ndim != 2 or a.shape != b.shape or a.shape[1] != len(self.n):
            raise ValueError('Replica arrays must be draws by municipalities')
        if not np.isfinite(a).all() or not np.isfinite(b).all() or min(a.min(), b.min()) < 0:
            raise ValueError('Invalid replica vote totals')
        valid = a + b; current = valid.clip(1)
        draws = len(a)
        den = (self.per * self.no)[self.turnout_mask].sum() + config.lambda_turnout
        ratio = (valid[:, self.turnout_mask].sum(1) + config.lambda_turnout) / den if den > 0 else np.ones(draws)
        remaining = ratio[:, None] * self.pending
        fallback = (self.prior * self.per * self.n).sum() / max((self.per * self.n).sum(), 1)
        total = valid.sum(1)
        national = np.divide(a.sum(1), total, out=np.full(draws, fallback), where=total > 0)
        if config.method == 'poststrat':
            shares = np.empty_like(a)
            for mask in self.states:
                v = valid[:, mask].sum(1)
                uf = np.divide(a[:, mask].sum(1), v, out=national.copy(), where=v > 0)
                shares[:, mask] = np.where(valid[:, mask] > 0, a[:, mask] / current[:, mask], uf[:, None])
        else:
            y = a / current - self.prior

            def fit(mask, parent, penalty):
                if not mask.any():
                    return parent.copy()
                x = self.X[mask]; w = valid[:, mask]; target = y[:, mask]
                if penalty == 0:
                    root = np.sqrt(w)
                    design = x[None, :, :] * root[:, :, None]
                    inverse = np.linalg.pinv(design, rcond=max(x.shape) * np.finfo(float).eps)
                    return np.einsum('bim,bm->bi', inverse, target * root)
                matrix = np.einsum('mi,bm,mj->bij', x, w, x, optimize=True) + penalty * np.eye(3)[None]
                rhs = np.einsum('mi,bm->bi', x, w * target) + penalty * parent
                return np.linalg.solve(matrix, rhs[..., None])[..., 0]

            beta = fit(self.train, np.zeros((draws, 3)), 0.)
            shares = self.prior + beta @ self.X.T
            if config.method == 'hierarchical':
                for region, states in self.regions:
                    parent = fit(self.train & region, beta, config.lambda_region)
                    for state in states:
                        child = fit(self.train & state, parent, config.lambda_uf)
                        shares[:, state] = self.prior[state] + child @ self.X[state].T
        shares = shares.clip(0, 1)
        pending_a = (shares * remaining).sum(1)
        pending_b = ((1 - shares) * remaining).sum(1)
        # Original counted votes, rather than bootstrap pseudo-votes, are fixed.
        numerator = self.a.sum() + pending_a
        denominator = self.a.sum() + self.b.sum() + pending_a + pending_b
        return np.divide(numerator, denominator, out=national.copy(), where=denominator > 0)


def bootstrap_intervals(observed: pd.DataFrame, history: History, draws=200,
                        seed=42, coverage=.9, batch_size=8, configs=None, return_samples=False):
    """Equal-tail conditional bands from positive section weights within cities.

    Inputs contain only received sections and first-turn/structural history.
    Unobserved vote totals and final election results are not accepted.
    """
    if not isinstance(draws, int) or draws < 40 or not 0 < coverage < 1 or batch_size < 1:
        raise ValueError('Use >=40 draws, coverage in (0,1) and positive batch_size')
    observed = observed[SECTION + ['votes_a', 'votes_b']]
    snapshot = build_snapshot(observed)
    engine = ReplicateProjector(history, snapshot)
    configs = configs or {m: Config(method=m) for m in METHODS}
    methods = {m: {'share_a': predict(snapshot, history, c).share_a, 'lower_a': None, 'upper_a': None}
               for m, c in configs.items()}
    result = {'coverage': coverage, 'draws': draws, 'seed': seed, 'methods': methods,
              'observed_sections': len(observed), 'observed_municipalities': len(snapshot.frame),
              'pending_municipalities_without_observations': int(((engine.n > engine.no) & (engine.no == 0)).sum()),
              'one_section_municipalities': int((engine.no == 1).sum()),
              'kind': 'municipal_stratified_fractional_weight_bootstrap', 'calibrated': False}
    if (engine.n == engine.no).all():
        for p in methods.values(): p.update(lower_a=p['share_a'], upper_a=p['share_a'])
        if return_samples: result['samples_a'] = {m: [p['share_a']] * draws for m, p in methods.items()}
        return result
    if observed.empty or (observed.votes_a + observed.votes_b).sum() <= 0:
        return result
    codes = pd.MultiIndex.from_frame(history.frame[KEY]).get_indexer(pd.MultiIndex.from_frame(observed[KEY]))
    if (codes < 0).any(): raise ValueError('Observed section absent from history')
    sort = np.argsort(codes, kind='stable'); codes = codes[sort]
    starts = np.r_[0, np.flatnonzero(codes[1:] != codes[:-1]) + 1]
    count = np.diff(np.r_[starts, len(codes)])
    groups = codes[starts]
    a = observed.votes_a.to_numpy(dtype=float)[sort]; b = observed.votes_b.to_numpy(dtype=float)[sort]
    rng = np.random.default_rng(seed)
    samples = {m: [] for m in methods}
    for start in range(0, draws, batch_size):
        size = min(batch_size, draws - start)
        weights = rng.exponential(size=(size, len(observed)))
        normalizer = np.add.reduceat(weights, starts, axis=1)
        a_draw = np.zeros((size, len(history.frame))); b_draw = np.zeros_like(a_draw)
        a_draw[:, groups] = np.add.reduceat(weights * a, starts, axis=1) / normalizer * count
        b_draw[:, groups] = np.add.reduceat(weights * b, starts, axis=1) / normalizer * count
        for m, config in configs.items(): samples[m].append(engine.predict(a_draw, b_draw, config))
    alpha = (1 - coverage) / 2
    for m, chunks in samples.items():
        samples[m] = np.concatenate(chunks)
        lower, upper = np.quantile(samples[m], [alpha, 1 - alpha])
        methods[m].update(lower_a=float(lower), upper_a=float(upper))
    if return_samples: result['samples_a'] = {m: values.tolist() for m, values in samples.items()}
    return result
