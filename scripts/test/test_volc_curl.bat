@echo off
echo 测试火山引擎Embedding API...

curl -X POST "https://ark.cn-beijing.volcs.com/api/v3/embeddings" ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer REDACTED_LLM_KEY" ^
  -d "{""encoding_format"": ""float"", ""input"": [""测试文本""], ""model"": ""doubao-embedding-text-240715""}"

echo.
echo 测试完成
pause
