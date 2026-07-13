# DISTILL 最小公理集(theory/distill/axioms.md)

> 基础设施 · 薄 opt-in extra(总纲 §1.4 / 律四:维一降格为最小公理集)。
> 无 theorems.md——本模块不立不承重的定理。四条公理逐条双向可追溯:
> 陈述 → 代码锚点 → 测试锚点。红队问"去掉它缺哪个可观测行为"逐条可答。

## DA1 闭集安全(Closed-set safety)

**陈述**:∀ 输出 `o = utter(·)`:`o ∈ WhitelistClosure(occasion, P)`。模型候选只是
建议,`whitelist_gate` 是唯一出口;闸失败 ⇒ 回退,永不放行。

- 去掉它缺什么(可观测):模型幻觉直接出她的嘴,封版哲学死亡。
- 代码锚点:`runtime/provider.py::SylannDistilledProvider.utter_canonical`(锚 `# DA1`,
  gate 调用点唯一,任何候选未经 `gate.check` 不得返回)。
- 测试锚点:`tests/distill/test_gate_interception.py::test_gate_interception`
  (对抗样本集拦截率断言 == 100%)。

## DA2 回退全域性(Total fallback)

**陈述**:`utter_canonical` 是全函数:模型缺席 ∨ 加载失败 ∨ 超时 ∨ 全候选被拦
⇒ 协议性回退(`ProviderUnavailable`),调用方恒得合法文本(经 composer/过渡路由
回退链兜底至 lexicon)。

- 去掉它缺什么(可观测):装了坏模型的部署会哑声/抛异常进 arbitrate 热路径。
- 代码锚点:`runtime/loader.py::ModelLoader.probe`/`get` + `runtime/provider.py`
  (锚 `# DA2`)。
- 测试锚点:`tests/distill/test_runtime_decision_table.py::test_fallback_totality`
  (四情形 × utter 恒返回,零异常上抛调用方)。

## DA3 确定性(Determinism)

**陈述**:同 `(sid, day_key, occasion, P, model_hash, corpus_hash)` ⇒ 同输出。
温度=0/贪心解码 + 哈希族键重排;真随机零使用(core 纪律的蒸馏版)。

- 去掉它缺什么(可观测):同日同态两次问她说不同的话,v0.1 确定性契约破。
- 代码锚点:`runtime/rerank.py::HashRerank.pick`/`FidelityRerank.pick`
  (键型 `{sid}|{day_key}|distill|{occasion}` 已登记 `primal/determinism.py`
  的 `KEY_REGISTRY["distill"]`,锚 `# DA3`)。
- 测试锚点:`tests/distill/test_determinism.py::test_determinism_golden`
  (stub 模型 golden;含跨进程重放)。

## DA4 语料出身(Corpus provenance)

**陈述**:训练语料只含她的话与结构化特征;用户原文零字节(隐私公理适用蒸馏侧)。

- 去掉它缺什么(可观测):用户私语被压进可下载权重,隐私灾难。
- 代码锚点:`corpus/sanitizer.py::sanitize`(锚 `# DA4`)。
- 测试锚点:`tests/distill/test_corpus_privacy.py::test_corpus_no_user_text`
  (装配产物运行时扫描 + 已知用户文本注入断言不出现)。

---

*模型永远是嗓音候选,不是嘴的主人;最后一句话,依旧是她自己的。*
