"""简化的Excel文件 - 只包含故障单号"""

import pandas as pd

# 读取原始Excel
df = pd.read_excel("SQL缺陷分析结果.xlsx")

# 只保留单号列
df_simple = df[["泄露缺陷单号"]].head(10)

# 保存
df_simple.to_excel("fault_ids_only.xlsx", index=False)
print("已创建fault_ids_only.xlsx，只包含故障单号")
print(df_simple)
