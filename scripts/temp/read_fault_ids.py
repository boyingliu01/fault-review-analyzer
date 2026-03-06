import pandas as pd

df = pd.read_excel("故障单列表.xlsx")
print("列名:", df.columns.tolist())
print("\n前10行:")
print(df.head(10))
print("\n总行数:", len(df))
