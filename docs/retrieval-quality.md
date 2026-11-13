# 知识检索质量评测

在 48 个段落、32 条标注查询上，双路融合 `rrf` 和旧混合检索 `blend` 的 Recall@3 都为 0.8281，nDCG@3 从 0.8012 提高至 0.8037。变化集中在一条询问两种检索方法的英文问题。语义改写组的 Recall@3 均为 0.3125，这个小型向量模型对跨语言改写的覆盖有限。

## 候选从哪里来

`blend` 在按余弦距离选出的候选中加入全文相关度。`rrf` 让向量和全文检索各自选取候选。前者按余弦距离排序，后者使用 PostgreSQL 全文查询并按 `ts_rank_cd(..., 32)` 排序。数据库用一条 SQL 取回两个窗口。两个分支均限定同一知识库、向量维数以及启用且所属关系一致的文档和段落。每库每支最多取 `min(10 × top_k, 500)` 条索引记录。

服务将所有已授权知识库的候选合并，在每支内按段落去重，保留最高的分支分数，取全局窗口，再计算等权 RRF。一个段落只在实际入选的分支得票。排序依据依次为 RRF 分数、原始证据分数和段落 ID。不同向量模型的余弦分数可有不同分布；多库使用不同模型时，向量分支的全局名次也会受此影响。

独立检索 API、普通应用的检索步骤、工作流的「知识库检索」节点和管理台命中测试使用同一份 PostgreSQL 查询和融合函数。数据库回归逐项比较四个入口的段落 ID、原始分数与融合分数，覆盖原始分数和融合名次相反、文档引用限制、排除分段以及跨项目文档的情况。

## 语料与测量口径

材料为本仓库编写的中英文产品支持样例，覆盖账户、订单、知识库、工作流、网关及固件。查询分成四组，各 8 条。改写组含同义表达和跨语言问法，型号组含容易混淆的设备编号、版本号和故障码。每条查询给出相关段落与等级，2 为直接回答、1 为部分相关，其余为 0。语料、问题、标注和逐题排名均可审阅。[语料](../benchmarks/retrieval/corpus.jsonl) · [查询与标注](../benchmarks/retrieval/queries.jsonl) · [逐题排名](../benchmarks/retrieval/rankings.json)

所有方法使用相同数据、`top_k=3` 和 `min_score=0`。只在语料上训练 TF-IDF 与 12 维 LSA。额外一维处理完全不在词表中的查询，文档在该维恒为零。模型训练无需相关性标签或下载权重。PostgreSQL 16.15、pgvector 0.8.6 实际执行生产 SQL，使用项目的 Jieba 0.42.1 分词、短语查询、余弦距离和 PostgreSQL 全文分数。NumPy 版本为 1.26.4。单库、每文档一段、无关联问题或术语词典。临时表执行精确余弦检索。线上较大知识库可能使用近似 HNSW 索引。

对每题分别计算再取平均。Recall@3 为返回的相关段落占该题全部相关段落的比例；MRR@3 为首条相关段落名次的倒数；nDCG@3 用 `2^grade − 1` 增益和对数位置折扣，对照该题理想排序归一化。无命中计零。

| 方法 | Recall@3 | MRR@3 | nDCG@3 |
| --- | ---: | ---: | ---: |
| embedding | 0.7656 | 0.6875 | 0.7066 |
| keywords | 0.7969 | 0.7812 | 0.7840 |
| blend | 0.8281 | 0.7969 | 0.8012 |
| rrf | 0.8281 | 0.7969 | 0.8037 |

| 组别 | blend Recall@3 | rrf Recall@3 | blend nDCG@3 | rrf nDCG@3 |
| --- | ---: | ---: | ---: | ---: |
| 中文直接提问 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| 英文直接提问 | 1.0000 | 1.0000 | 0.9438 | 0.9539 |
| 语义改写 | 0.3125 | 0.3125 | 0.3071 | 0.3071 |
| 型号、版本、错误码 | 1.0000 | 1.0000 | 0.9539 | 0.9539 |

`en08` 同时问到关键词与向量检索，RRF 将第二条相关段落从第 3 位提至第 2 位。另有一项数据库回归专门覆盖窗口外召回，构造 32 条余弦分数更高的无关段落，旧算法漏掉型号精确命中，RRF 将其送入前三。该构造用例单独计数。语料小、相关性由编写者给定，当前测量只覆盖段落排序；业务流量中的召回率、生成式回答质量和延迟需分别测量。

## 复现

从仓库根目录执行。以下默认命令只依赖 Python 标准库，从已保存的数据库排名重算各组指标。

```sh
python benchmarks/retrieval/evaluate.py
```

重新运行全部 SQL 时需要项目 Python 环境、已安装 vector 扩展的 PostgreSQL 测试库及其临时表权限。通过标准 libpq 环境变量 `PGHOST`、`PGPORT`、`PGDATABASE`、`PGUSER` 和 `PGPASSWORD` 指定连接，也可设置 `LITEKB_BENCH_DSN`。程序创建会话临时表，连接关闭后由数据库移除。新测出的逐题排名可另存后离线评分。

```sh
python benchmarks/retrieval/evaluate.py --postgres --save local-rankings.json
python benchmarks/retrieval/evaluate.py --replay local-rankings.json
```

要用已部署的业务模型复测，在单独的空白普通知识库中导入同一份样本，等待 48 个文档的 `index_status` 均变为 `success`。脚本按文档名称关联标注，每个样本文档应有且只有一个段落。将服务密钥放入 `LITEKB_SERVICE_KEY`，`BASE` 为 LiteKB 根地址，`KB` 为已授权的测试库 ID。`--api` 仅读取检索结果，会向已配置的模型发送样本查询。

```sh
python benchmarks/retrieval/evaluate.py --archive fixture.json
curl --fail -H "Authorization: Bearer $LITEKB_SERVICE_KEY" -H "Content-Type: application/json" \
  --data-binary @fixture.json "$BASE/v1/knowledge-bases/$KB/import"
python benchmarks/retrieval/evaluate.py --api "$BASE" --kb "$KB" --save model-rankings.json
```
