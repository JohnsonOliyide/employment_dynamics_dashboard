# U.S. Employment Dynamics Dashboard

This dashboard tracks U.S. payroll employment dynamics across major industries and states.

## Files

- `index.html`: the dashboard
- `scripts/update_employment_dynamics.py`: pulls BLS CES data and builds dashboard-ready CSV files
- `data/industry_employment.csv`: generated industry data
- `data/state_employment.csv`: generated state data
- `.github/workflows/update-employment-dynamics.yml`: GitHub Actions workflow

## Dashboard sections

### Industry Employment Dynamics

Shows:
- sector contribution to payroll employment change
- sector share of total nonfarm payroll employment

### State Employment Map

Shows:
- month-over-month state payroll employment growth
- year-over-year state payroll employment growth
- each state’s share of total U.S. payroll employment

## Data source

Current Employment Statistics (CES), U.S. Bureau of Labor Statistics.

CES measures payroll jobs, not unique workers. A person with more than one payroll job may be counted more than once.



## Data refresh reliability

The scheduled workflow validates downloads before replacing published files. The live dashboard reads data directly from the repository so automated data commits are visible without a separate Pages rebuild. Source publication dates differ and missing observations remain missing. Run `python -m unittest discover -s tests` to check refresh safeguards.
