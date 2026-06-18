# A/B Test Report

**Experiment ID:** `exp_2026_05_27_001`  
**Task:** целевое действие агента в интерфейсе  
**Date range:** `2026-05-20 .. 2026-05-27`  
**Variants:** `A` vs `B`  
**Agent:** `UXAgent`

---

## 1. Verdict

**Final verdict:** `winner_B`  
**Statistical winner:** `B`  
**Practical winner:** `B`

### Why
- Главная метрика (`success_rate`) показала статистически значимое улучшение у варианта **B**.
- Значимых деградаций по guardrail-метрикам не зафиксировано.
- Диагностические метрики указывают на меньшее трение в траектории у **B**: меньше ошибок, меньше лишних действий, меньше возвратов.

---

## 2. Data quality checks

| Check | Result | Notes |
|---|---:|---|
| Runs in A | 1200 | unique agents: 1200 |
| Runs in B | 1198 | unique agents: 1198 |
| Sample ratio mismatch | passed | p = 0.64 |
| Logging completeness | passed | 3 incomplete runs excluded from analysis |
| Oracle confidence | 0.91 | average confidence of success detection |
| Invalid runs | A: 14 / B: 11 | runs with corrupted / incomplete traces |

**Interpretation:**  
Данные пригодны для сравнения. Признаков поломки распределения или очевидной деградации логирования не выявлено.

---

## 3. Primary metric

### 3.1 Success rate
**Metric:** доля успешных выполнений  
**Test:** two-proportion z-test  
**Multiple comparison correction:** Bonferroni

| Group | Success rate | Absolute delta vs A | Relative uplift |
|---|---:|---:|---:|
| A | 0.412 | — | — |
| B | 0.458 | +0.046 | +11.1% |

**Statistics**
- `p-value`: `0.013`
- `Bonferroni adjusted p-value`: `0.013`
- `95% CI for difference (B - A)`: `[0.010, 0.082]`
- `Significant`: `yes`

**Conclusion:**  
Вариант **B** лучше по основной метрике. Разница статистически значима.

---

## 4. Guardrail metrics

| Metric | A | B | Delta (B - A) | Test | p-value | Significant | Verdict |
|---|---:|---:|---:|---|---:|---:|---|
| steps_to_success | 11.4 | 10.2 | -1.2 | Welch t-test | 0.041 | yes | better |
| actions_per_task | 14.8 | 13.9 | -0.9 | Welch t-test | 0.087 | no | neutral |
| actions_per_success | 12.1 | 11.0 | -1.1 | Welch t-test | 0.033 | yes | better |
| trajectory_efficiency | 0.61 | 0.67 | +0.06 | Welch t-test | 0.018 | yes | better |
| invalid_action_rate | 0.083 | 0.061 | -0.022 | two-proportion z-test | 0.019 | yes | better |
| no_state_change_rate | 0.17 | 0.12 | -0.05 | two-proportion z-test | 0.006 | yes | better |
| backtrack_rate | 0.09 | 0.07 | -0.02 | two-proportion z-test | 0.044 | yes | better |
| repeat_state_rate | 0.15 | 0.11 | -0.04 | two-proportion z-test | 0.021 | yes | better |
| max_step_exhaustion_rate | 0.08 | 0.05 | -0.03 | two-proportion z-test | 0.031 | yes | better |

**Interpretation:**  
Guardrails не ухудшились. Наоборот, у **B** видно уменьшение лишних действий и трения на траектории.

---

## 5. Diagnostic summary

### Top failure reasons
1. `timeout on modal`
2. `could not find primary CTA`
3. `looped between states S3 and S4`

### Funnel view
| Funnel stage | A | B | Comment |
|---|---:|---:|---|
| Start → first action | 0.98 | 0.99 | difference negligible |
| First action → goal | 0.53 | 0.58 | B better |
| Goal → clean terminate | 0.44 | 0.50 | B better |

### Interpretation
- У варианта **B** меньше зацикливаний.
- Уменьшилась доля действий, которые не меняют состояние интерфейса.
- Проход до целевого действия стал короче и стабильнее.

---

## 6. Segment view

### Personas
| Segment | Success rate delta (B - A) | Note |
|---|---:|---|
| new_user | +0.08 | B better |
| returning_user | +0.03 | B slightly better |
| power_user | -0.01 | no clear difference |

**Interpretation:**  
Победа **B** не выглядит случайной только в одном сегменте. Улучшение есть у новых и возвращающихся пользователей.

---

## 7. QA evidence

### Example successful run: `r001`
**Group:** `B`  
**Result:** `success`  
**Final state:** `success_screen`

**Path summary:**  
`search -> open_card -> add_to_cart -> checkout -> confirm`

**Key evidence**
- финальная страница сменилась на экран подтверждения;
- действие завершилось без ошибок;
- в траектории нет возвратов назад;
- нет признаков тупика или повторяющегося состояния.

---

### Example failed run: `r002`
**Group:** `A`  
**Result:** `fail`  
**Final state:** `checkout_error`

**Path summary:**  
`search -> open_card -> checkout -> error`

**Key evidence**
- прогон завершился ошибкой;
- подтверждения целевого действия нет;
- путь оборвался на этапе оформления;
- есть явный failure state.

---

### Example uncertain run: `r017`
**Group:** `A`  
**Result:** `progress`

**Path summary:**  
`search -> open_card -> add_to_cart -> checkout -> modal_block`

**Key evidence**
- прогон не завершён;
- интерфейс заблокирован модальным окном;
- по фронтенду нельзя подтвердить успех;
- этот прогон не должен использоваться как completed success/fail.

---

## 8. Final interpretation for QA

### What QA should take from this result
- Вариант **B** является победителем по основной метрике.
- Победа подтверждается не только `success_rate`, но и снижением трения на траектории.
- Признаков деградации по guardrails нет.
- Данные выглядят пригодными для принятия решения.

### What to inspect manually
- модальные окна, которые блокируют завершение;
- повторяющиеся состояния S3/S4;
- пути, где агент делает много действий без изменения состояния;
- случаи `progress`, которые были остановлены таймаутом или блокировкой.

---

## 9. Attached statistical files

- `stats_primary.md` — проверка значимости основной метрики
- `stats_guardrails.md` — проверка значимости guardrail-метрик
- `per_run_export.json` — сырой экспорт прогонов
- `trace_examples.md` — примеры типовых трасс успеха / провала

---

## 10. Short conclusion

**Recommended action:** roll out variant `B`.  
**Reason:** statistically significant improvement in primary metric without guardrail regression.
