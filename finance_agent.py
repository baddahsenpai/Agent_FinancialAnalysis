import argparse
import csv
import math
import statistics
import sys
from datetime import date, datetime

TRADING_DAYS = 252


def parse_date(raw):
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"date invalide: {raw!r}")


def load_snapshots(path):
    snapshots = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required = {"date", "value"}
        missing = required - {c.strip().lower() for c in reader.fieldnames or []}
        if missing:
            raise ValueError(f"colonnes manquantes: {sorted(missing)}")
        for row in reader:
            key = {k.strip().lower(): v for k, v in row.items()}
            snapshots.append(
                {
                    "date": parse_date(key["date"]),
                    "value": float(key["value"]),
                    "net_flow": float(key.get("deposit", "0") or 0)
                    - float(key.get("withdrawal", "0") or 0),
                }
            )
    snapshots.sort(key=lambda s: s["date"])
    if len(snapshots) < 2:
        raise ValueError("il faut au moins 2 lignes pour calculer des rendements")
    return snapshots


def daily_returns(snapshots):
    out = []
    for prev, cur in zip(snapshots, snapshots[1:]):
        if prev["value"] <= 0:
            raise ValueError(f"valeur non positive le {prev['date']}")
        r = (cur["value"] - prev["value"] - cur["net_flow"]) / prev["value"]
        out.append((cur["date"], r))
    return out


def max_drawdown(values):
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1.0)
    return worst


def compute_metrics(snapshots, returns):
    values = [s["value"] for s in snapshots]
    rets = [r for _, r in returns]
    n = len(rets)
    total_return = values[-1] / values[0] - 1.0
    net_flows = sum(s["net_flow"] for s in snapshots[1:])
    invested = values[0] + net_flows
    money_weighted = (values[-1] - invested) / invested if invested > 0 else float("nan")
    mean = statistics.fmean(rets)
    std = statistics.stdev(rets) if n > 1 else 0.0
    ann_return = (1.0 + mean) ** TRADING_DAYS - 1.0
    ann_vol = std * math.sqrt(TRADING_DAYS)
    sharpe = (ann_return - 0.0) / ann_vol if ann_vol > 0 else float("nan")
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r < 0]
    return {
        "n_days": n,
        "first_date": snapshots[0]["date"],
        "last_date": snapshots[-1]["date"],
        "start_value": values[0],
        "end_value": values[-1],
        "net_flows": net_flows,
        "total_return": total_return,
        "money_weighted": money_weighted,
        "mean_daily": mean,
        "std_daily": std,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown(values),
        "win_rate": len(wins) / n if n else 0.0,
        "avg_win": statistics.fmean(wins) if wins else 0.0,
        "avg_loss": statistics.fmean(losses) if losses else 0.0,
        "best_day": max(returns, key=lambda x: x[1]),
        "worst_day": min(returns, key=lambda x: x[1]),
    }


def required_daily_return(target_annual, trading_days_left):
    if trading_days_left <= 0:
        return 0.0
    return (1.0 + target_annual) ** (1.0 / trading_days_left) - 1.0


def target_analysis(snapshots, m, target_annual, horizon_days=None, end_date=None):
    last = snapshots[-1]["date"]
    if end_date is not None:
        remaining_days = (end_date - last).days
    else:
        remaining_days = horizon_days if horizon_days is not None else TRADING_DAYS
    remaining_trading = max(1, round(remaining_days * TRADING_DAYS / 365))
    r_req = required_daily_return(target_annual, remaining_trading)
    if m["std_daily"] > 0:
        z = (r_req - m["mean_daily"]) / m["std_daily"]
    else:
        z = 0.0 if r_req <= m["mean_daily"] else float("inf")
    projected = m["end_value"] * (1.0 + m["mean_daily"]) ** remaining_trading
    goal_value = m["end_value"] * (1.0 + target_annual) ** (remaining_trading / TRADING_DAYS)
    if z <= 0:
        verdict = "en avance sur l'objectif"
    elif z <= 1:
        verdict = "objectif atteignable avec la tendance actuelle"
    elif z <= 2:
        verdict = "objectif exigeant : il faudra accélérer par rapport à la moyenne récente"
    else:
        verdict = "objectif peu réaliste au rythme actuel"
    pace_days = None
    if m["mean_daily"] > 0:
        multiple = (1.0 + target_annual) / max(1e-9, 1.0 + m["ann_return"])
        if multiple > 1:
            pace_days = math.log(multiple) / math.log(1.0 + m["mean_daily"])
    return {
        "target_annual": target_annual,
        "remaining_days": remaining_days,
        "remaining_trading": remaining_trading,
        "required_daily": r_req,
        "z_score": z,
        "goal_value": goal_value,
        "projected_value": projected,
        "verdict": verdict,
        "pace_days": pace_days,
    }


def pct(x, digits=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x * 100:.{digits}f} %"


def eur(x):
    return f"{x:,.2f} EUR".replace(",", " ")


def render_report(m, t):
    lines = []
    lines.append("=== RAPPORT FINANCIER JOURNALIER ===")
    lines.append(
        f"Période analysée : {m['first_date']} -> {m['last_date']} ({m['n_days']} jours de bourse)"
    )
    lines.append(f"Valeur de départ : {eur(m['start_value'])}")
    lines.append(f"Valeur actuelle : {eur(m['end_value'])}")
    lines.append(f"Flux nets (dépôts - retraits) : {eur(m['net_flows'])}")
    lines.append(f"Rendement total : {pct(m['total_return'])}")
    lines.append(f"Rendement pondéré par les flux : {pct(m['money_weighted'])}")
    lines.append(f"Rendement annualisé : {pct(m['ann_return'])}")
    lines.append(f"Volatilité annualisée : {pct(m['ann_vol'])}")
    lines.append(f"Ratio de Sharpe (taux sans risque 0) : {m['sharpe']:.2f}")
    lines.append(f"Drawdown maximal : {pct(m['max_drawdown'])}")
    lines.append(f"Jours gagnants : {pct(m['win_rate'])} (gain moyen {pct(m['avg_win'])}, perte moyenne {pct(m['avg_loss'])})")
    lines.append(f"Meilleur jour : {m['best_day'][0]} ({pct(m['best_day'][1])})")
    lines.append(f"Pire jour : {m['worst_day'][0]} ({pct(m['worst_day'][1])})")
    lines.append("")
    lines.append("=== AVIS SUR L'OBJECTIF ===")
    lines.append(f"Objectif de rendement annualisé visé : {pct(t['target_annual'])}")
    lines.append(
        f"Temps restant : {t['remaining_days']} jours calendaires (~{t['remaining_trading']} jours de bourse)"
    )
    lines.append(f"Rendement journalier requis : {pct(t['required_daily'], 4)}")
    lines.append(f"Rendement journalier moyen constaté : {pct(m['mean_daily'], 4)}")
    lines.append(f"Valeur visée à l'échéance : {eur(t['goal_value'])}")
    lines.append(f"Valeur projetée avec la tendance actuelle : {eur(t['projected_value'])}")
    lines.append(f"Verdict : {t['verdict']} (score z = {t['z_score']:.2f})")
    if t["pace_days"] is not None:
        lines.append(
            f"Au rythme actuel, l'objectif annualisé serait atteint en ~{t['pace_days']:.0f} jours de bourse supplémentaires"
        )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyse les résultats financiers journaliers d'un portefeuille et évalue la trajectoire vers un objectif de rentabilité."
    )
    parser.add_argument("csv_path", help="fichier CSV avec colonnes date, value, deposit, withdrawal")
    parser.add_argument("--target-annual", type=float, default=0.08, help="objectif de rendement annualisé (ex: 0.08 pour 8 %%)")
    parser.add_argument("--horizon-days", type=int, default=None, help="horizon en jours calendaires")
    parser.add_argument("--end-date", type=str, default=None, help="date d'échéance YYYY-MM-DD (prioritaire sur --horizon-days)")
    parser.add_argument("--output", default=None, help="fichier où écrire le rapport (sinon stdout)")
    args = parser.parse_args(argv)

    snapshots = load_snapshots(args.csv_path)
    returns = daily_returns(snapshots)
    m = compute_metrics(snapshots, returns)
    end_date = parse_date(args.end_date) if args.end_date else None
    t = target_analysis(snapshots, m, args.target_annual, args.horizon_days, end_date)
    report = render_report(m, t)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
