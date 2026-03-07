import json
with open('swagger.txt', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Servers定义:")
print(json.dumps(data.get('servers', []), indent=2, ensure_ascii=False))

print("\n\n查找可能有用的API (非task相关但可能返回数据):")
paths = data.get('paths', {})
useful_paths = [p for p in paths.keys() if 'list' in p.lower() or 'query' in p.lower() or 'search' in p.lower()]
for p in useful_paths[:20]:
    methods = paths[p]
    if isinstance(methods, dict) and 'get' in methods:
        summary = methods.get('get', {}).get('summary', '')
        print(f"  {p}: {summary}")
