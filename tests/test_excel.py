import pandas as pd

df = pd.read_excel('SQL缺陷分析结果.xlsx')
print("列名:", df.columns.tolist())
print("\n前5行 - 故障单号:")
# 尝试找到故障单号列
for col in df.columns:
    if '单号' in col or 'ID' in col or 'id' in col or '任务' in col:
        print(f"\n列 '{col}':")
        print(df[col].head(5).tolist())

print("\n\n完整前3行:")
for i in range(min(3, len(df))):
    print(f"\n=== 第{i+1}行 ===")
    for col in df.columns:
        val = df.iloc[i][col]
        if pd.notna(val):
            print(f"{col}: {str(val)[:100]}")
