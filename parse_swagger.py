import json

with open(r'E:\Study\LLM\Bug聚类分析\swagger.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

paths = d.get('paths', {})
all_paths = sorted(paths.keys())

keywords = ['doc', 'book', 'knowledge', 'wiki', 'library', 'content', 'article', 'portal']
doc_apis = []
for p in all_paths:
    for kw in keywords:
        if kw in p.lower():
            doc_apis.append(p)
            break

print('=== 文档相关 API ===')
for p in doc_apis:
    methods = list(paths[p].keys())
    for m in methods:
        info = paths[p][m]
        tags = info.get('tags', ['No Tag'])
        summary = info.get('summary', 'N/A')
        print(f'{p} [{m}] - {tags[0]} - {summary}')

print()
servers = d.get('servers', [])
print('=== Servers ===')
for s in servers:
    print(f'  {s.get("url")} - {s.get("description")}')

print()
# 搜索 docs.iwhalecloud.com 相关
print('=== 搜索 docs/portal 域名相关 ===')
components = d.get('components', {})
schemas = components.get('schemas', {})
for name in schemas:
    desc = str(schemas[name])
    if 'docs' in desc.lower() or 'portal' in desc.lower():
        print(f'  Schema: {name}')