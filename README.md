# Telco Commercial Performance & Initiative Impact

> Work in progress. A Power BI case study on **synthetic data** for a fictional South African
> mobile operator. No real company's data, prices or customers are used.

## What this shows

- Explaining why revenue and ARPU moved, split into gross additions, churn, migrations,
  price and usage.
- Measuring a commercial initiative against a baseline and a randomised control group.
- Reconciling the reporting data to its source and documenting every metric definition.

Because the data generator plants known effects, each finding can be checked against the
truth in `data/ground_truth.json`.

## Reproduce the data

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python src/generate_data.py
```

## Repository

| Path | Contents |
|------|----------|
| `src/` | Data generator, validation and reference calculations |
| `powerbi/` | Power BI project (PBIP) |
| `docs/` | Metric dictionary and decision log |
