# Independent check: plain pandas straight from the raw Sales export, no app code.
import pandas as pd, sys
d = sys.argv[1] if len(sys.argv) > 1 else 'data'  # run from repo root: python docs/independent_check.py
s = pd.read_csv(f'{d}/Sales.csv', parse_dates=['Date'])
st = pd.read_csv(f'{d}/Support_EX_B_Stores.csv', sep='\t')
print('TOTAL', round(s.Revenue.sum(), 2))
m = s.merge(st[['ID', 'StoreType']], left_on='Store ID', right_on='ID')
print('ROWS after store join', len(m), 'sum', round(m.Revenue.sum(), 2))
print(m.groupby('StoreType').Revenue.sum().round(2).to_dict())
print(s.groupby(s.Date.dt.year).Revenue.sum().round(2).to_dict())
mon = s.groupby(s.Date.dt.month).Revenue.sum()
print('MONTH share of 5yr total %', (mon / mon.sum() * 100).round(2).to_dict())
