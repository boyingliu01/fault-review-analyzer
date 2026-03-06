import pandas as pd

df = pd.read_excel("SQL缺陷分析结果.xlsx")
print("Columns:", df.columns.tolist())
print("\nFirst 10 rows:")
for i, row in df.head(10).iterrows():
    print(f"\n--- Row {i + 1} ---")
    print(row.to_dict())
