# Visual Bug Scan Report — Example
---

## 1) Что возвращает сканер

Каждая запись содержит:

- `kind`
- `severity`
- `message`
- `element`
- `related`
- `selector`
- `relatedSelector`
- `label`
- `relatedLabel`
- `rect`
- `relatedRect`
- `evidence`
- `suggestion`

---

## 2) Сводка

| Метрика | Значение |
|---|---:|
| Всего проблем | 7 |
| `error` | 2 |
| `warning` | 4 |
| `info` | 1 |
| Уникальных селекторов | 6 |
| Обнаружено типов | 5 |

### Распределение по типам

| Тип | Кол-во |
|---|---:|
| `OVERLAP` | 1 |
| `CLIPPED` | 1 |
| `VIEWPORT_OVERFLOW` | 1 |
| `TEXT_OVERFLOW` | 1 |
| `LOW_CONTRAST` | 1 |
| `BROKEN_STATE` | 2 |

### Приоритет разборки

1. Сначала `error`
2. Затем `warning`
3. Потом `info`

---

## 3) Найденные проблемы

---

### 1. ⛔ `LOW_CONTRAST`

**Элемент:** `a.nav-link`  
**Селектор:** `header > nav > a.nav-link:nth-of-type(2)`  
**Статус:** `error`

**Проблема:**  
Низкий контраст у ссылки в шапке: текст почти сливается с фоном и плохо читается.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `a.nav-link “Pricing”` |
| `relatedLabel` | — |
| `rect` | `{ left: 912.4, top: 18, width: 64.2, height: 24 }` |
| `evidence.contrastRatio` | `2.21` |
| `evidence.threshold` | `3.5` |
| `evidence.fontSize` | `14px` |
| `evidence.fontWeight` | `500` |
| `evidence.backgroundReliable` | `true` |

**Почему это важно:**  
Пользователь видит навигацию хуже, особенно на слабых экранах и при ярком освещении.

**Рекомендуемое исправление:**  
Увеличить контраст текста и фона, либо изменить цвет ссылки на более тёмный.

---

### 2. ⚠️ `VIEWPORT_OVERFLOW`

**Элемент:** `body`  
**Селектор:** `body`  
**Статус:** `warning`

**Проблема:**  
Страница имеет горизонтальный overflow. Контент расширяет viewport по оси X.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `body` |
| `relatedLabel` | — |
| `rect` | `{ left: 0, top: 0, width: 1440, height: 2380 }` |
| `evidence.scrollWidth` | `1536` |
| `evidence.viewportWidth` | `1440` |

**Почему это важно:**  
Появляется горизонтальная прокрутка, ломается композиция и часть интерфейса уходит за экран.

**Рекомендуемое исправление:**  
Найти элемент с лишней шириной, проверить `position: fixed/absolute`, `width`, `left/right`, `transform` и отрицательные отступы.

---

### 3. ⚠️ `CLIPPED`

**Элемент:** `div.card__menu`  
**Селектор:** `.dashboard > .card:nth-of-type(3) > .card__menu`  
**Связанный элемент:** `div.card`  
**Статус:** `warning`

**Проблема:**  
Выпадающее меню выходит за пределы контейнера и обрезается `overflow: hidden`.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `div.card__menu` |
| `relatedLabel` | `div.card` |
| `rect` | `{ left: 1218, top: 364, width: 248, height: 180 }` |
| `relatedRect` | `{ left: 1120, top: 320, width: 280, height: 210 }` |
| `evidence.parentOverflowX` | `hidden` |
| `evidence.parentOverflowY` | `hidden` |
| `evidence.clippedX` | `true` |
| `evidence.clippedY` | `true` |

**Почему это важно:**  
Часть меню недоступна для клика и визуально выглядит сломанной.

**Рекомендуемое исправление:**  
Перенести меню в более высокий слой, убрать жесткое `overflow: hidden` или изменить позиционирование.

---

### 4. ⚠️ `TEXT_OVERFLOW`

**Элемент:** `span.user-name`  
**Селектор:** `.profile-card > span.user-name`  
**Статус:** `warning`

**Проблема:**  
Текст обрезается внутри ограниченного контейнера.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `span.user-name “Alexandria Montgomery-Weston”` |
| `rect` | `{ left: 96, top: 142, width: 180, height: 20 }` |
| `evidence.scrollWidth` | `286` |
| `evidence.clientWidth` | `180` |
| `evidence.scrollHeight` | `20` |
| `evidence.clientHeight` | `20` |
| `evidence.whiteSpace` | `nowrap` |
| `evidence.textOverflow` | `ellipsis` |
| `evidence.overflow` | `hidden/hidden` |
| `evidence.hasExplicitConstraint` | `true` |
| `evidence.widthOverflow` | `true` |
| `evidence.heightOverflow` | `false` |
| `evidence.rangeOverflow` | `true` |

**Почему это важно:**  
Название пользователя или сущности теряется, что ухудшает понимание интерфейса.

**Рекомендуемое исправление:**  
Сделать контейнер шире, разрешить перенос, либо явно оставить `ellipsis`, если это допустимо по UX.

---

### 5. ⛔ `BROKEN_STATE`

**Элемент:** `button.filter-toggle`  
**Селектор:** `.filters > button.filter-toggle`  
**Связанный элемент:** `div.filters-panel`  
**Статус:** `error`

**Проблема:**  
`aria-expanded=true`, но контролируемый блок скрыт.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `button.filter-toggle “Filters”` |
| `relatedLabel` | `div.filters-panel` |
| `rect` | `{ left: 24, top: 88, width: 112, height: 36 }` |
| `relatedRect` | `{ left: 24, top: 128, width: 320, height: 240 }` |
| `evidence.ariaExpanded` | `true` |
| `evidence.controls` | `filters-panel` |
| `evidence.controlledVisible` | `false` |

**Почему это важно:**  
Техническое состояние и реальное UI-состояние расходятся. Это ломает доступность и вводит пользователя в заблуждение.

**Рекомендуемое исправление:**  
Синхронизировать `aria-expanded` с фактической видимостью панели.

---

### 6. ℹ️ `BROKEN_STATE`

**Элемент:** `a.sidebar-link`  
**Селектор:** `.sidebar > a.sidebar-link:nth-of-type(4)`  
**Статус:** `info`

**Проблема:**  
У интерактивного элемента нет явного focus-индикатора.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `a.sidebar-link “Billing”` |
| `rect` | `{ left: 18, top: 248, width: 124, height: 28 }` |
| `evidence.outlineStyle` | `none` |
| `evidence.outlineWidth` | `0` |
| `evidence.boxShadow` | `none` |

**Почему это важно:**  
Клавиатурная навигация становится хуже. Элемент может быть формально доступен, но фактически неудобен.

**Рекомендуемое исправление:**  
Добавить заметный `focus ring` и убедиться, что он не обрезается контейнером.

---

### 7. ⚠️ `OVERLAP`

**Элемент:** `button.primary-cta`  
**Селектор:** `.hero > button.primary-cta`  
**Связанный элемент:** `div.cookie-banner`  
**Статус:** `warning`

**Проблема:**  
Кнопка частично перекрыта баннером.

**Детали:**

| Поле | Значение |
|---|---|
| `label` | `button.primary-cta “Start trial”` |
| `relatedLabel` | `div.cookie-banner “We use cookies”` |
| `rect` | `{ left: 72, top: 612, width: 184, height: 48 }` |
| `relatedRect` | `{ left: 40, top: 590, width: 360, height: 84 }` |
| `evidence.coverage` | `0.36` |
| `evidence.intersectionArea` | `1584` |
| `evidence.topHits` | `6` |

**Почему это важно:**  
Главное действие на экране становится хуже доступным и выглядит заблокированным.

**Рекомендуемое исправление:**  
Изменить порядок слоёв, отступы или высоту/позицию баннера.

---

## 4) Что в этом отчете следует читать первым

- `error` — уже явная поломка.
- `warning` — высокая вероятность дефекта.
- `info` — риск, который лучше исправить до релиза.

---

## 5) Что именно хранить в отчете

Для каждой записи полезно показывать:

- тип проблемы (`kind`)
- уровень критичности (`severity`)
- человекочитаемое объяснение (`message`)
- конкретный DOM-элемент (`label`, `selector`, `rect`)
- связанный элемент, если он есть (`related*`)
- машинные детали (`evidence`)
- рекомендацию (`suggestion`)

---

## 6) Пример формата одной записи

```ts
{
  kind: "TEXT_OVERFLOW",
  severity: "warning",
  message: "Текст выходит за ограниченную область...",
  selector: ".profile-card > span.user-name",
  relatedSelector: undefined,
  label: "span.user-name “Alexandria Montgomery-Weston”",
  relatedLabel: undefined,
  rect: { left: 96, top: 142, width: 180, height: 20 },
  relatedRect: null,
  evidence: {
    scrollWidth: 286,
    clientWidth: 180,
    whiteSpace: "nowrap",
    textOverflow: "ellipsis"
  },
  suggestion: "Сделать контейнер шире или разрешить перенос."
}
```

---

## 7) Замечание по типам

`SIZE_ANOMALY` есть в перечислении типов, но в текущей версии сканера отдельный проход под него не реализован.  
Это лучше явно отметить в документации, чтобы никто не ждал от отчета несуществующей проверки.

---

## 8) Итог

Этот формат удобен тем, что:

- быстро отделяет реальные ошибки от риска;
- показывает и DOM-селектор, и визуальные координаты;
- дает одно место для `evidence`, чтобы не терять технический контекст;
- подходит и для ручного просмотра, и для автогенерации отчета из JSON.