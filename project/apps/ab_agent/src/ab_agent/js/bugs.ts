/*
  Visual Bug Scanner
  Framework-agnostic DOM/layout heuristic scanner for:
  1) overlaps / occlusions
  2) clipping / overflow hidden issues
  3) viewport overflow
  4) text overflow
  5) contrast / readability
  6) size anomalies in repeated components
  7) broken interactive states

  Usage:
    import { scanVisualBugs, logVisualBugs } from './visual-bug-scanner';

    const issues = scanVisualBugs(document.body);
    logVisualBugs(issues);

  Or in DevTools console after bundling:
    window.scanVisualBugs(document.body)
*/

export type VisualBugKind =
  | 'OVERLAP'
  | 'CLIPPED'
  | 'VIEWPORT_OVERFLOW'
  | 'TEXT_OVERFLOW'
  | 'LOW_CONTRAST'
  | 'SIZE_ANOMALY'
  | 'BROKEN_STATE';

export type VisualBugSeverity = 'info' | 'warning' | 'error';

export interface VisualBugIssue {
  kind: VisualBugKind;
  severity: VisualBugSeverity;
  message: string;
  element: Element;
  related?: Element | null;
  selector: string;
  relatedSelector?: string;
  label: string;
  relatedLabel?: string;
  rect: DOMRectReadOnly;
  relatedRect?: DOMRectReadOnly | null;
  evidence?: Record<string, unknown>;
  suggestion?: string;
}

export interface VisualBugScanOptions {
  root?: ParentNode;
  maxResults?: number;
  viewportPadding?: number;
  minOverlapAreaPx?: number;
  minOverlapCoverageRatio?: number;
  minTextPixels?: number;
  contrastAaThreshold?: number;
  contrastLargeTextThreshold?: number;
  sizeAnomalyDeviationRatio?: number;
  includeHidden?: boolean;
  debug?: boolean;
}

const DEFAULT_OPTIONS: Required<Omit<VisualBugScanOptions, 'root'>> = {
  maxResults: 250,
  viewportPadding: 0,
  minOverlapAreaPx: 24,
  minOverlapCoverageRatio: 0.15,
  minTextPixels: 8,
  // Normal text threshold. Lower it only if your product deliberately allows weaker contrast.
  contrastAaThreshold: 3.5,
  // Large text threshold. Lower it only if your product deliberately allows weaker contrast for large text.
  contrastLargeTextThreshold: 2.8,
  sizeAnomalyDeviationRatio: 0.35,
  includeHidden: false,
  debug: false,
};

type RGBA = { r: number; g: number; b: number; a: number };

type Candidate = {
  el: Element;
  rect: DOMRectReadOnly;
  index: number;
  style: CSSStyleDeclaration;
};

function isElement(node: Node | null): node is Element {
  return !!node && node.nodeType === Node.ELEMENT_NODE;
}

function clamp(n: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, n));
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

function area(rect: DOMRectReadOnly): number {
  return Math.max(0, rect.width) * Math.max(0, rect.height);
}

function intersects(a: DOMRectReadOnly, b: DOMRectReadOnly): boolean {
  return !(
    a.right <= b.left ||
    a.left >= b.right ||
    a.bottom <= b.top ||
    a.top >= b.bottom
  );
}

function intersectionRect(a: DOMRectReadOnly, b: DOMRectReadOnly): DOMRectReadOnly | null {
  if (!intersects(a, b)) return null;
  const left = Math.max(a.left, b.left);
  const top = Math.max(a.top, b.top);
  const right = Math.min(a.right, b.right);
  const bottom = Math.min(a.bottom, b.bottom);
  return new DOMRectReadOnly(left, top, Math.max(0, right - left), Math.max(0, bottom - top));
}

function isTextNode(node: Node): node is Text {
  return node.nodeType === Node.TEXT_NODE;
}

function isVisibleStyle(style: CSSStyleDeclaration): boolean {
  return (
    style.display !== 'none' &&
    style.visibility !== 'hidden' &&
    style.visibility !== 'collapse' &&
    Number.parseFloat(style.opacity || '1') > 0
  );
}

function isElementActuallyVisible(el: Element, includeHidden = false): boolean {
  const style = getComputedStyle(el);
  if (!includeHidden && !isVisibleStyle(style)) return false;
  const rects = el.getClientRects();
  if (rects.length === 0) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) return false;
  return true;
}

function getDirectTextContent(el: Element): string {
  const parts: string[] = [];
  for (const child of Array.from(el.childNodes)) {
    if (isTextNode(child)) {
      const t = child.textContent?.replace(/\s+/g, ' ').trim() ?? '';
      if (t) parts.push(t);
    }
  }
  return parts.join(' ').replace(/\s+/g, ' ').trim();
}

function getFlattenedTextContent(el: Element): string {
  return (el.textContent ?? '').replace(/\s+/g, ' ').trim();
}

function getElementLabel(el: Element): string {
  const tag = el.tagName.toLowerCase();
  const id = (el as HTMLElement).id ? `#${(el as HTMLElement).id}` : '';
  const className = (el as HTMLElement).className;
  const classes =
    typeof className === 'string' && className.trim()
      ? `.${className.trim().split(/\s+/).slice(0, 3).join('.')}`
      : '';

  const role = el.getAttribute('role');
  const ariaLabel = el.getAttribute('aria-label');
  const title = el.getAttribute('title');
  const text = getDirectTextContent(el) || getFlattenedTextContent(el);
  const shortText = text ? ` “${text.slice(0, 80)}${text.length > 80 ? '…' : ''}”` : '';
  const name = ariaLabel || title || shortText;
  const rolePart = role ? `[role=${role}]` : '';

  return `${tag}${id}${classes}${rolePart}${name ? ` ${name}` : ''}`.trim();
}

function cssEscapeSafe(value: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') return CSS.escape(value);
  return value.replace(/[^a-zA-Z0-9_-]/g, '\\$&');
}

function uniqueSelectorFor(el: Element): string {
  const htmlEl = el as HTMLElement;
  const testId = htmlEl.getAttribute('data-testid') || htmlEl.getAttribute('data-test') || htmlEl.getAttribute('data-qa');
  if (testId) {
    const attrName = htmlEl.getAttribute('data-testid')
      ? 'data-testid'
      : htmlEl.getAttribute('data-test')
      ? 'data-test'
      : 'data-qa';
    return `[${attrName}="${cssEscapeSafe(testId)}"]`;
  }

  if (htmlEl.id) return `#${cssEscapeSafe(htmlEl.id)}`;

  const parts: string[] = [];
  let current: Element | null = el;
  let depth = 0;
  while (current && current !== document.documentElement && depth < 5) {
    const tag = current.tagName.toLowerCase();
    const parent = current.parentElement;
    if (!parent) {
      parts.unshift(tag);
      break;
    }

    const siblings = Array.from(parent.children).filter((n) => n.tagName === current!.tagName);
    if (siblings.length === 1) {
      parts.unshift(tag);
    } else {
      const index = siblings.indexOf(current) + 1;
      parts.unshift(`${tag}:nth-of-type(${index})`);
    }
    current = parent;
    depth += 1;

    if (current && current.id) {
      parts.unshift(`#${cssEscapeSafe(current.id)}`);
      break;
    }
  }
  return parts.join(' > ');
}

function getVisibleRect(el: Element): DOMRectReadOnly {
  return el.getBoundingClientRect();
}

function hasPaint(style: CSSStyleDeclaration): boolean {
  const bg = style.backgroundColor;
  const border = style.borderTopColor;
  const shadow = style.boxShadow;
  const bgImage = style.backgroundImage;
  return (
    bg !== 'rgba(0, 0, 0, 0)' ||
    border !== 'rgba(0, 0, 0, 0)' ||
    shadow !== 'none' ||
    bgImage !== 'none'
  );
}

function parseCssColor(input: string): RGBA | null {
  const s = input.trim().toLowerCase();
  if (!s || s === 'transparent') return { r: 0, g: 0, b: 0, a: 0 };
  const rgb = s.match(/^rgba?\(([^)]+)\)$/);
  if (rgb) {
    const parts = rgb[1].split(',').map((x) => x.trim());
    const [r, g, b] = parts.slice(0, 3).map((v) => Number.parseFloat(v));
    const a = parts[3] !== undefined ? Number.parseFloat(parts[3]) : 1;
    if ([r, g, b, a].some((n) => Number.isNaN(n))) return null;
    return { r, g, b, a: clamp(a, 0, 1) };
  }

  const hex = s.match(/^#([0-9a-f]{3,8})$/i);
  if (hex) {
    const value = hex[1];
    if (value.length === 3) {
      const r = Number.parseInt(value[0] + value[0], 16);
      const g = Number.parseInt(value[1] + value[1], 16);
      const b = Number.parseInt(value[2] + value[2], 16);
      return { r, g, b, a: 1 };
    }
    if (value.length === 4) {
      const r = Number.parseInt(value[0] + value[0], 16);
      const g = Number.parseInt(value[1] + value[1], 16);
      const b = Number.parseInt(value[2] + value[2], 16);
      const a = Number.parseInt(value[3] + value[3], 16) / 255;
      return { r, g, b, a };
    }
    if (value.length === 6 || value.length === 8) {
      const r = Number.parseInt(value.slice(0, 2), 16);
      const g = Number.parseInt(value.slice(2, 4), 16);
      const b = Number.parseInt(value.slice(4, 6), 16);
      const a = value.length === 8 ? Number.parseInt(value.slice(6, 8), 16) / 255 : 1;
      return { r, g, b, a };
    }
  }

  return null;
}

function composite(fg: RGBA, bg: RGBA): RGBA {
  const a = fg.a + bg.a * (1 - fg.a);
  if (a === 0) return { r: 0, g: 0, b: 0, a: 0 };
  return {
    r: Math.round((fg.r * fg.a + bg.r * bg.a * (1 - fg.a)) / a),
    g: Math.round((fg.g * fg.a + bg.g * bg.a * (1 - fg.a)) / a),
    b: Math.round((fg.b * fg.a + bg.b * bg.a * (1 - fg.a)) / a),
    a,
  };
}

function rgbaToLuminance(color: RGBA): number {
  const flatten = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  const r = flatten(color.r);
  const g = flatten(color.g);
  const b = flatten(color.b);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(fg: RGBA, bg: RGBA): number {
  const fgOpaque = fg.a < 1 ? composite(fg, { r: 255, g: 255, b: 255, a: 1 }) : fg;
  const bgOpaque = bg.a < 1 ? composite(bg, { r: 255, g: 255, b: 255, a: 1 }) : bg;
  const l1 = rgbaToLuminance(fgOpaque);
  const l2 = rgbaToLuminance(bgOpaque);
  const bright = Math.max(l1, l2);
  const dark = Math.min(l1, l2);
  return (bright + 0.05) / (dark + 0.05);
}

function isLargeText(style: CSSStyleDeclaration): boolean {
  const size = Number.parseFloat(style.fontSize || '16');
  const weight = style.fontWeight === 'bold' ? 700 : Number.parseInt(style.fontWeight || '400', 10) || 400;
  return size >= 24 || (size >= 18.5 && weight >= 700);
}

function effectiveBackgroundColor(el: Element): { color: RGBA; reliable: boolean } {
  let current: Element | null = el;
  let reliable = true;

  while (current && current !== document.documentElement) {
    const style = getComputedStyle(current);
    if (style.backgroundImage && style.backgroundImage !== 'none') {
      reliable = false;
    }
    const c = parseCssColor(style.backgroundColor);
    if (c && c.a > 0) {
      // Use the first painted background in the ancestor chain.
      return { color: c.a < 1 ? composite(c, { r: 255, g: 255, b: 255, a: 1 }) : c, reliable };
    }
    current = current.parentElement;
  }

  const bodyStyle = getComputedStyle(document.body);
  const htmlStyle = getComputedStyle(document.documentElement);
  const bodyBg = parseCssColor(bodyStyle.backgroundColor);
  const htmlBg = parseCssColor(htmlStyle.backgroundColor);
  const fallback = bodyBg?.a ? bodyBg : htmlBg?.a ? htmlBg : { r: 255, g: 255, b: 255, a: 1 };
  return { color: fallback, reliable };
}

function textCandidateScore(el: Element): number {
  const style = getComputedStyle(el);
  if (!isVisibleStyle(style)) return 0;
  const text = getFlattenedTextContent(el);
  if (!text) return 0;
  const ownText = getDirectTextContent(el);
  const role = el.getAttribute('role');
  const tag = el.tagName.toLowerCase();
  let score = 0;
  if (ownText) score += 2;
  if (role || tag === 'button' || tag === 'a' || tag === 'label' || tag === 'summary') score += 2;
  if (tag.match(/^(h[1-6]|p|span|div|li|td|th|label|button|a|small|strong|em)$/)) score += 1;
  if (text.length <= 120) score += 1;
  if (el.childElementCount === 0) score += 2;
  return score;
}

function interactiveCandidate(el: Element): boolean {
  const tag = el.tagName.toLowerCase();
  const role = (el.getAttribute('role') || '').toLowerCase();
  const tabIndex = el.getAttribute('tabindex');
  const style = getComputedStyle(el);
  if (tag === 'button' || tag === 'summary' || tag === 'select' || tag === 'textarea') return true;
  if (tag === 'input') return true;
  if (tag === 'a' && (el as HTMLAnchorElement).href) return true;
  if (['button', 'link', 'tab', 'menuitem', 'checkbox', 'radio', 'switch', 'option', 'treeitem'].includes(role)) return true;
  if (tabIndex !== null && tabIndex !== '-1') return true;
  if (style.cursor === 'pointer') return true;
  if (el.hasAttribute('onclick') || el.hasAttribute('data-action')) return true;
  return false;
}

function getPaintOrderScore(el: Element): number {
  const style = getComputedStyle(el);
  let score = 0;
  const z = Number.parseInt(style.zIndex || '0', 10);
  score += Number.isFinite(z) ? z * 100000 : 0;
  const position = style.position;
  if (position === 'fixed') score += 90000;
  else if (position === 'sticky') score += 70000;
  else if (position === 'absolute') score += 50000;
  else if (position === 'relative') score += 10000;
  if (style.transform !== 'none') score += 3000;
  if (style.opacity !== '1') score += 1000;

  let depth = 0;
  let current: Element | null = el;
  while (current && current !== document.documentElement && depth < 8) {
    depth += 1;
    current = current.parentElement;
  }
  score += depth;
  return score;
}

function compareDomOrder(a: Element, b: Element): number {
  if (a === b) return 0;
  const pos = a.compareDocumentPosition(b);
  if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
  if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
  return 0;
}

function isAncestorOrSelf(ancestor: Element, node: Element): boolean {
  return ancestor === node || ancestor.contains(node);
}

function isLikelyOccluding(upper: Element, lower: Element): boolean {
  if (isAncestorOrSelf(lower, upper) || isAncestorOrSelf(upper, lower)) return false;
  const upperScore = getPaintOrderScore(upper);
  const lowerScore = getPaintOrderScore(lower);
  if (upperScore !== lowerScore) return upperScore > lowerScore;
  return compareDomOrder(upper, lower) > 0;
}

function makeIssue(
  kind: VisualBugKind,
  severity: VisualBugSeverity,
  element: Element,
  message: string,
  related?: Element | null,
  suggestion?: string,
  evidence?: Record<string, unknown>,
): VisualBugIssue {
  return {
    kind,
    severity,
    message,
    element,
    related: related ?? null,
    selector: uniqueSelectorFor(element),
    relatedSelector: related ? uniqueSelectorFor(related) : undefined,
    label: getElementLabel(element),
    relatedLabel: related ? getElementLabel(related) : undefined,
    rect: element.getBoundingClientRect(),
    relatedRect: related ? related.getBoundingClientRect() : null,
    suggestion,
    evidence,
  };
}

function elementFromPointSafe(x: number, y: number): Element | null {
  const node = document.elementFromPoint(x, y);
  return isElement(node) ? node : null;
}

function pickTextLineage(el: Element): Element[] {
  const arr: Element[] = [];
  let current: Element | null = el;
  while (current && current !== document.documentElement) {
    if (textCandidateScore(current) > 0) arr.push(current);
    current = current.parentElement;
  }
  return arr;
}

function scanOverlaps(candidates: Candidate[], options: Required<Omit<VisualBugScanOptions, 'root'>>): VisualBugIssue[] {
  const issues: VisualBugIssue[] = [];
  const seen = new Set<string>();

  const samplePointsFor = (rect: DOMRectReadOnly): Array<[number, number]> => {
    const pad = 2;
    const pts: Array<[number, number]> = [];
    const xs = [rect.left + pad, rect.left + rect.width / 2, rect.right - pad];
    const ys = [rect.top + pad, rect.top + rect.height / 2, rect.bottom - pad];
    for (const x of xs) {
      for (const y of ys) pts.push([x, y]);
    }
    return pts.filter(([x, y]) => x >= 0 && y >= 0 && x <= window.innerWidth && y <= window.innerHeight);
  };

  for (const candidate of candidates) {
    const { el, rect } = candidate;
    if (area(rect) < 16) continue;

    const points = samplePointsFor(rect);
    const topHits = new Map<Element, number>();

    for (const [x, y] of points) {
      const top = elementFromPointSafe(x, y);
      if (!top || top === el) continue;

      // Never report parent-child / ancestor-descendant overlap here.
      // Those are layout relationships, not visual occlusion bugs.
      if (el.contains(top) || top.contains(el)) continue;

      if (!isElementActuallyVisible(top, options.includeHidden)) continue;
      topHits.set(top, (topHits.get(top) || 0) + 1);
    }

    for (const [top, count] of topHits) {
      if (count < 2) continue;
      const inter = intersectionRect(rect, top.getBoundingClientRect());
      if (!inter) continue;
      const interArea = area(inter);
      const coverage = interArea / Math.max(1, area(rect));
      if (interArea < options.minOverlapAreaPx || coverage < options.minOverlapCoverageRatio) continue;
      if (!isLikelyOccluding(top, el)) continue;

      const key = `${uniqueSelectorFor(el)}|${uniqueSelectorFor(top)}|${Math.round(inter.left)}|${Math.round(inter.top)}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const elName = getElementLabel(el);
      const topName = getElementLabel(top);
      const severity: VisualBugSeverity = coverage > 0.5 ? 'error' : 'warning';
      
      // ME
      if (coverage <= 0.99){ 
      issues.push(
        makeIssue(
          'OVERLAP',
          severity,
          el,
          `Элемент ${elName} частично перекрыт ${topName} (${round2(coverage * 100)}% площади).`,
          top,
          'Проверь z-index, position, overflow и реальные точки наложения.',
          { coverage, intersectionArea: round2(interArea), topHits: count },
        ),
      );}
    }
  }

  return issues;
}

function scanViewportOverflow(candidates: Candidate[], options: Required<Omit<VisualBugScanOptions, 'root'>>): VisualBugIssue[] {
  const issues: VisualBugIssue[] = [];
  const seen = new Set<string>();

  const docEl = document.documentElement;
  const pageW = Math.max(docEl.scrollWidth, docEl.clientWidth);

  // Vertical scrolling is normal for most pages, so do not report page height overflow.
  if (pageW > window.innerWidth + options.viewportPadding + 1) {
    const key = `PAGE_SCROLL_X:${pageW}`;
    if (!seen.has(key)) {
      seen.add(key);
      issues.push(
        makeIssue(
          'VIEWPORT_OVERFLOW',
          'warning',
          document.body,
          `Страница имеет горизонтальный overflow: scrollWidth=${pageW}, viewportWidth=${window.innerWidth}.`,
          null,
          'Найди элемент, который расширяет страницу по X. Обычно это один прямоугольник с большим left/right.',
          { scrollWidth: pageW, viewportWidth: window.innerWidth },
        ),
      );
    }
  }

  for (const c of candidates) {
    const rect = c.rect;
    const el = c.el;
    const rectOutsideX =
      rect.left < -options.viewportPadding ||
      rect.right > window.innerWidth + options.viewportPadding;

    if (!rectOutsideX) continue;
    if (area(rect) < 8) continue;

    const key = `${uniqueSelectorFor(el)}|${Math.round(rect.left)}|${Math.round(rect.top)}`;
    if (seen.has(key)) continue;
    seen.add(key);

    issues.push(
      makeIssue(
        'VIEWPORT_OVERFLOW',
        'warning',
        el,
        `Элемент ${getElementLabel(el)} выходит за горизонтальные границы viewport: [${round2(rect.left)}, ${round2(rect.right)}], viewportWidth=${window.innerWidth}.`,
        null,
        'Проверь fixed/absolute позиционирование, ширину блока и наличие горизонтального скролла.',
        { rect: { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom } },
      ),
    );
  }

  return issues;
}

function scanClipping(candidates: Candidate[], options: Required<Omit<VisualBugScanOptions, 'root'>>): VisualBugIssue[] {
  const issues: VisualBugIssue[] = [];
  const seen = new Set<string>();

  for (const parentCandidate of candidates) {
    const parent = parentCandidate.el as HTMLElement;
    const parentStyle = parentCandidate.style;
    const ox = parentStyle.overflowX;
    const oy = parentStyle.overflowY;
    const overflowClip = ['hidden', 'clip', 'scroll', 'auto'].includes(ox) || ['hidden', 'clip', 'scroll', 'auto'].includes(oy);
    if (!overflowClip) continue;

    const parentRect = parentCandidate.rect;
    const parentClient = parent.getBoundingClientRect();
    const children = Array.from(parent.children);
    for (const child of children) {
      if (!isElementActuallyVisible(child, options.includeHidden)) continue;
      const childRect = child.getBoundingClientRect();
      const inter = intersectionRect(parentClient, childRect);
      if (!inter) continue;

      const clippedX = childRect.left < parentClient.left - 0.5 || childRect.right > parentClient.right + 0.5;
      const clippedY = childRect.top < parentClient.top - 0.5 || childRect.bottom > parentClient.bottom + 0.5;
      if (!clippedX && !clippedY) continue;

      const coverage = area(inter) / Math.max(1, area(childRect));
      if (coverage >= 0.98) continue; // mostly visible; ignore

      const key = `${uniqueSelectorFor(parent)}|${uniqueSelectorFor(child)}|${Math.round(childRect.left)}|${Math.round(childRect.top)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      
      issues.push(
        makeIssue(
          'CLIPPED',
          'warning',
          child,
          `Дочерний элемент ${getElementLabel(child)} выходит за пределы контейнера ${getElementLabel(parent)} и, вероятно, обрезается overflow=${ox}/${oy}.`,
          parent,
          'Проверь overflow, padding, width/height и позиционирование потомка.',
          { parentOverflowX: ox, parentOverflowY: oy, clippedX, clippedY },
        ),
      );
    }

    const ownText = getDirectTextContent(parent) || getFlattenedTextContent(parent);
    if (!ownText) continue;
    const scrollW = parent.scrollWidth;
    const clientW = parent.clientWidth;
    const scrollH = parent.scrollHeight;
    const clientH = parent.clientHeight;
    const textClipped =
      (scrollW > clientW + 1 || scrollH > clientH + 1) &&
      (['hidden', 'clip'].includes(ox) || ['hidden', 'clip'].includes(oy));
    if (!textClipped) continue;

    const key = `${uniqueSelectorFor(parent)}|TEXT_CLIP`;
    if (seen.has(key)) continue;
    seen.add(key);
    
    // ME
    if (scrollW > clientW) {
    issues.push(
      makeIssue(
        'CLIPPED',
        'warning',
        parent,
        `Текст/контент в ${getElementLabel(parent)} превышает доступную область и скрыт overflow: scrollWidth=${scrollW}, clientWidth=${clientW}, scrollHeight=${scrollH}, clientHeight=${clientH}.`,
        null,
        'Для текста обычно нужен ellipsis, переносы или увеличение контейнера.',
        { scrollWidth: scrollW, clientWidth: clientW, scrollHeight: scrollH, clientHeight: clientH },
      ),
    );}
  }

  return issues;
}

function scanTextOverflow(
  candidates: Candidate[],
  options: Required<Omit<VisualBugScanOptions, 'root'>>,
): VisualBugIssue[] {
  const issues: VisualBugIssue[] = [];
  const seen = new Set<string>();

  const textNodeRangeRect = (el: Element): DOMRectReadOnly | null => {
    const range = document.createRange();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let first: Text | null = null;
    let last: Text | null = null;

    let node = walker.nextNode();
    while (node) {
      if (isTextNode(node) && node.textContent && node.textContent.trim()) {
        if (!first) first = node;
        last = node;
      }
      node = walker.nextNode();
    }

    if (!first || !last) return null;

    try {
      range.setStart(first, 0);
      range.setEnd(last, last.textContent?.length ?? 0);
      const r = range.getBoundingClientRect();
      return r.width > 0 || r.height > 0 ? r : null;
    } catch {
      return null;
    }
  };

  const isExplicitlyConstrained = (style: CSSStyleDeclaration): boolean => {
    const ox = style.overflowX;
    const oy = style.overflowY;
    const overflowClipping =
      ['hidden', 'clip', 'scroll', 'auto'].includes(ox) ||
      ['hidden', 'clip', 'scroll', 'auto'].includes(oy);

    const textClipping = style.textOverflow === 'ellipsis' || style.textOverflow === 'clip';
    const noWrap = style.whiteSpace === 'nowrap';

    const hasSizeConstraint =
      style.width !== 'auto' ||
      style.maxWidth !== 'none' ||
      style.height !== 'auto' ||
      style.maxHeight !== 'none';

    return overflowClipping || textClipping || noWrap || hasSizeConstraint;
  };

  for (const c of candidates) {
    const el = c.el;
    const style = c.style;

    const text = getFlattenedTextContent(el);
    if (!text) continue;

    // Only check elements that are likely to render text themselves.
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const directText = getDirectTextContent(el);
    const semanticText =
      ['button', 'a', 'label', 'p', 'span', 'small', 'strong', 'em', 'b', 'i', 'u', 's',
       'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'summary', 'caption', 'legend',
       'code', 'pre', 'blockquote', 'figcaption', 'dt', 'dd', 'option'].includes(tag) ||
      ['button', 'link', 'heading', 'listitem', 'menuitem', 'tab', 'tooltip', 'note'].includes(role) ||
      directText.length > 0;

    if (!semanticText) continue;

    const rect = c.rect;
    if (area(rect) < options.minTextPixels) continue;

    const scrollW = (el as HTMLElement).scrollWidth;
    const clientW = (el as HTMLElement).clientWidth;
    const scrollH = (el as HTMLElement).scrollHeight;
    const clientH = (el as HTMLElement).clientHeight;

    const overflowX = style.overflowX;
    const overflowY = style.overflowY;
    const textOverflow = style.textOverflow;
    const whiteSpace = style.whiteSpace;

    const hasExplicitConstraint = isExplicitlyConstrained(style);

    // These are the only real signals we trust.
    const widthOverflow = clientW > 0 && scrollW > clientW + 1;
    const heightOverflow = clientH > 0 && scrollH > clientH + 1;

    const textRect = textNodeRangeRect(el);
    const rangeOverflow =
      !!textRect &&
      (textRect.width > rect.width + 1 || textRect.height > rect.height + 1);

    // Important:
    // - 0 clientWidth/clientHeight by itself is NOT a bug.
    // - ordinary flow text without explicit constraints is NOT a bug.
    // - only report when there is an explicit constraint AND a real overflow signal.
    const shouldFlag =
      hasExplicitConstraint && (widthOverflow || heightOverflow || rangeOverflow);

    if (!shouldFlag) continue;

    const key = `${uniqueSelectorFor(el)}|${Math.round(rect.left)}|${Math.round(rect.top)}|${widthOverflow ? 'x' : ''}${heightOverflow ? 'y' : ''}`;
    if (seen.has(key)) continue;
    seen.add(key);

    const severity: VisualBugSeverity =
      widthOverflow || heightOverflow ? 'warning' : 'info';

    issues.push(
      makeIssue(
        'TEXT_OVERFLOW',
        severity,
        el,
        `Текст в ${getElementLabel(el)} выходит за ограниченную область: scrollWidth=${scrollW}, clientWidth=${clientW}, scrollHeight=${scrollH}, clientHeight=${clientH}, white-space=${whiteSpace}, text-overflow=${textOverflow}, overflow=${overflowX}/${overflowY}.`,
        null,
        'Проверяй только реально ограниченные текстовые контейнеры: overflow hidden/clip, ellipsis, nowrap, фиксированную ширину/высоту. Обычный flow-контент не должен попадать сюда.',
        {
          scrollWidth: scrollW,
          clientWidth: clientW,
          scrollHeight: scrollH,
          clientHeight: clientH,
          whiteSpace,
          textOverflow,
          overflow: `${overflowX}/${overflowY}`,
          hasExplicitConstraint,
          widthOverflow,
          heightOverflow,
          rangeOverflow,
        },
      ),
    );
  }

  return issues;
}

function scanContrast(candidates: Candidate[], options: Required<Omit<VisualBugScanOptions, 'root'>>): VisualBugIssue[] {
  const issues: VisualBugIssue[] = [];
  const seen = new Set<string>();

  const contrastTextTags = new Set([
    'button', 'a', 'label', 'p', 'span', 'small', 'strong', 'em', 'b', 'i', 'u', 's',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td', 'th', 'summary', 'caption', 'legend',
    'code', 'pre', 'blockquote', 'figcaption', 'dt', 'dd', 'option'
  ]);

  for (const c of candidates) {
    const el = c.el;
    const style = c.style;
    if (el === document.body || el === document.documentElement) continue;
    if (['script', 'style', 'noscript', 'template', 'meta', 'link', 'head'].includes(el.tagName.toLowerCase())) continue;

    const text = getFlattenedTextContent(el);
    if (!text) continue;

    // Only evaluate elements that actually render text themselves,
    // not generic containers that merely wrap descendants.
    const directText = getDirectTextContent(el);
    const tag = el.tagName.toLowerCase();
    const role = (el.getAttribute('role') || '').toLowerCase();
    const isSemanticText = contrastTextTags.has(tag) || ['button', 'link', 'heading', 'listitem', 'menuitem', 'tab', 'tooltip', 'note'].includes(role);
    const isDirectTextBox = directText.length > 0;

    if (!isSemanticText && !isDirectTextBox) continue;

    const rect = c.rect;
    if (area(rect) < options.minTextPixels) continue;

    const fg = parseCssColor(style.color);
    if (!fg) continue;

    const bgInfo = effectiveBackgroundColor(el);
    const bg = bgInfo.color;
    const ratio = contrastRatio(fg, bg);
    const largeText = isLargeText(style);
    const threshold = largeText ? options.contrastLargeTextThreshold : options.contrastAaThreshold;

    if (ratio >= threshold) continue;

    const key = `${uniqueSelectorFor(el)}|${Math.round(rect.left)}|${Math.round(rect.top)}|${ratio.toFixed(2)}`;
    if (seen.has(key)) continue;
    seen.add(key);

    issues.push(
      makeIssue(
        'LOW_CONTRAST',
        ratio < 3 ? 'error' : 'warning',
        el,
        `Низкий контраст у ${getElementLabel(el)}: ratio=${ratio.toFixed(2)}; threshold=${threshold}; largeText=${largeText}; backgroundReliable=${bgInfo.reliable}.`,
        null,
        'Проверь color/background, прозрачности, градиенты и тексты поверх изображений.',
        {
          contrastRatio: round2(ratio),
          threshold,
          fontSize: style.fontSize,
          fontWeight: style.fontWeight,
          backgroundReliable: bgInfo.reliable,
          foreground: style.color,
          background: `rgb(${bg.r}, ${bg.g}, ${bg.b})`,
        },
      ),
    );
  }

  return issues;
}

function sizeSignature(el: Element): string {
  const role = el.getAttribute('role') || '';
  const tag = el.tagName.toLowerCase();
  const classTokens = (el as HTMLElement).className;
  const classes = typeof classTokens === 'string'
    ? classTokens.split(/\s+/).filter(Boolean).slice(0, 3).sort().join('.')
    : '';
  return `${tag}|${role}|${classes}`;
}

function median(values: number[]): number {
  const arr = values.slice().sort((a, b) => a - b);
  if (arr.length === 0) return 0;
  const mid = Math.floor(arr.length / 2);
  return arr.length % 2 === 0 ? (arr[mid - 1] + arr[mid]) / 2 : arr[mid];
}

function visualStateSignature(el: Element): string {
  const s = getComputedStyle(el);
  const fields = [
    s.color,
    s.backgroundColor,
    s.borderTopColor,
    s.borderTopWidth,
    s.borderRadius,
    s.fontWeight,
    s.textDecorationLine,
    s.boxShadow,
    s.opacity,
  ];
  return fields.join('|');
}

function scanBrokenStates(candidates: Candidate[], options: Required<Omit<VisualBugScanOptions, 'root'>>): VisualBugIssue[] {
  const issues: VisualBugIssue[] = [];
  const seen = new Set<string>();

  for (const c of candidates) {
    const el = c.el;
    const style = c.style;
    if (!interactiveCandidate(el)) continue;
    if (!isElementActuallyVisible(el, options.includeHidden)) continue;

    const disabled =
      el.hasAttribute('disabled') ||
      el.getAttribute('aria-disabled') === 'true' ||
      el.getAttribute('data-disabled') === 'true';

    if (disabled) {
      const looksActive =
        style.opacity === '1' &&
        style.filter === 'none' &&
        style.pointerEvents !== 'none' &&
        style.cursor !== 'not-allowed';
      if (looksActive) {
        const key = `${uniqueSelectorFor(el)}|disabled`;
        if (!seen.has(key)) {
          seen.add(key);
          issues.push(
            makeIssue(
              'BROKEN_STATE',
              'warning',
              el,
              `Отключённый элемент ${getElementLabel(el)} визуально не выглядит отключённым.`,
              null,
              'Сделай disabled-состояние явным: opacity, cursor, border, text color или другой signal.',
              { disabled: true, computedOpacity: style.opacity, cursor: style.cursor },
            ),
          );
        }
      }
    }

    const expanded = el.getAttribute('aria-expanded');
    const controls = el.getAttribute('aria-controls');
    if (expanded !== null && controls) {
      const target = document.getElementById(controls);
      if (target) {
        const visible = isElementActuallyVisible(target, options.includeHidden);
        const shouldBeVisible = expanded === 'true';
        if (visible !== shouldBeVisible) {
          const key = `${uniqueSelectorFor(el)}|expanded|${controls}`;
          if (!seen.has(key)) {
            seen.add(key);
            issues.push(
              makeIssue(
                'BROKEN_STATE',
                'error',
                el,
                `aria-expanded=${expanded} у ${getElementLabel(el)}, но контролируемый блок ${getElementLabel(target)} видим=${visible}.`,
                target,
                'Синхронизируй aria-expanded с реальной видимостью контролируемого контейнера.',
                { ariaExpanded: expanded, controls, controlledVisible: visible },
              ),
            );
          }
        }
      }
    }

    const focusable = interactiveCandidate(el);
    if (focusable) {
      const outline = style.outlineStyle;
      const outlineWidth = Number.parseFloat(style.outlineWidth || '0');
      const boxShadow = style.boxShadow;
      const risk = outline === 'none' && outlineWidth === 0 && boxShadow === 'none';
      if (risk) {
        const key = `${uniqueSelectorFor(el)}|focus`;
        if (!seen.has(key)) {
          seen.add(key);
          issues.push(
            makeIssue(
              'BROKEN_STATE',
              'info',
              el,
              `У ${getElementLabel(el)} нет явного focus-индикатора по computed style.`,
              null,
              'Это риск для клавиатурной навигации. Добавь заметный focus ring и не обрезай его overflow-ом.',
              { outlineStyle: outline, outlineWidth, boxShadow },
            ),
          );
        }
      }
    }
  }

  // Active / selected groups: compare siblings inside the same parent.
  const parents = new Map<Element, Element[]>();
  for (const c of candidates) {
    const el = c.el;
    if (!el.parentElement) continue;
    if (!interactiveCandidate(el)) continue;
    const parent = el.parentElement;
    if (!parents.has(parent)) parents.set(parent, []);
    parents.get(parent)!.push(el);
  }

  for (const [parent, items] of parents) {
    const activeItems = items.filter((el) => {
      const attrs = [
        el.getAttribute('aria-selected'),
        el.getAttribute('aria-pressed'),
        el.getAttribute('aria-current'),
        el.getAttribute('data-state'),
      ].filter(Boolean);
      return attrs.some((v) => v !== 'false' && v !== 'off' && v !== 'closed' && v !== 'inactive');
    });

    if (activeItems.length === 0) continue;

    const sigMap = new Map<string, Element[]>();
    for (const el of items) {
      const sig = visualStateSignature(el);
      if (!sigMap.has(sig)) sigMap.set(sig, []);
      sigMap.get(sig)!.push(el);
    }

    if (sigMap.size <= 1) {
      // all look the same — suspicious if some are active and some are not.
      const key = `same-style-group|${uniqueSelectorFor(parent)}`;
      if (!seen.has(key)) {
        seen.add(key);
        issues.push(
          makeIssue(
            'BROKEN_STATE',
            'info',
            parent,
            `У группы интерактивных элементов в ${getElementLabel(parent)} есть активные состояния, но computed style почти одинаковый у всех элементов.`,
            null,
            'Проверь выделение active/selected/pressed состояний: цвет, фон, бордер, font-weight, underline или другой distinct signal.',
            { activeCount: activeItems.length, childCount: items.length },
          ),
        );
      }
    }
  }

  return issues;
}

function walkElements(root: ParentNode): Element[] {
  const out: Element[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  let node = walker.currentNode;
  while (node) {
    if (isElement(node)) out.push(node);
    node = walker.nextNode();
  }
  return out;
}

function collectCandidates(root: ParentNode, options: Required<Omit<VisualBugScanOptions, 'root'>>): Candidate[] {
  const elements = walkElements(root);
  const candidates: Candidate[] = [];
  const nonVisualTags = new Set(['script', 'style', 'noscript', 'template', 'meta', 'link', 'head', 'title']);

  for (let i = 0; i < elements.length; i += 1) {
    const el = elements[i];
    const tag = el.tagName.toLowerCase();
    if (nonVisualTags.has(tag)) continue;
    if (el === document.body || el === document.documentElement) continue;
    const style = getComputedStyle(el);
    if (!options.includeHidden && !isVisibleStyle(style)) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    candidates.push({ el, rect, index: i, style });
  }

  return candidates;
}

export function scanVisualBugs(root: ParentNode = document.body, options: VisualBugScanOptions = {}): VisualBugIssue[] {
  const merged: Required<Omit<VisualBugScanOptions, 'root'>> = {
    ...DEFAULT_OPTIONS,
    ...options,
  };

  const candidates = collectCandidates(root, merged);
  const issues: VisualBugIssue[] = [];

  // Order matters a bit: first hard structural problems, then content/readability.
  issues.push(...scanViewportOverflow(candidates, merged));
  issues.push(...scanClipping(candidates, merged));
  issues.push(...scanTextOverflow(candidates, merged));
  issues.push(...scanContrast(candidates, merged));
  issues.push(...scanOverlaps(candidates, merged));
  issues.push(...scanBrokenStates(candidates, merged));

  // De-duplicate by selector + kind + message prefix.
  const dedup = new Map<string, VisualBugIssue>();
  for (const issue of issues) {
    const key = `${issue.kind}|${issue.selector}|${issue.relatedSelector || ''}|${issue.message}`;
    if (!dedup.has(key)) dedup.set(key, issue);
  }

  return Array.from(dedup.values()).slice(0, merged.maxResults);
}

function severityEmoji(sev: VisualBugSeverity): string {
  switch (sev) {
    case 'error':
      return '⛔';
    case 'warning':
      return '⚠️';
    default:
      return 'ℹ️';
  }
}

export function formatIssue(issue: VisualBugIssue): string {
  const base = `${severityEmoji(issue.severity)} [${issue.kind}] ${issue.message}`;
  const details = [
    `selector=${issue.selector}`,
    issue.relatedSelector ? `related=${issue.relatedSelector}` : '',
    `rect=${round2(issue.rect.left)},${round2(issue.rect.top)} ${round2(issue.rect.width)}x${round2(issue.rect.height)}`,
    issue.relatedRect
      ? `relatedRect=${round2(issue.relatedRect.left)},${round2(issue.relatedRect.top)} ${round2(issue.relatedRect.width)}x${round2(issue.relatedRect.height)}`
      : '',
    issue.suggestion ? `hint=${issue.suggestion}` : '',
  ]
    .filter(Boolean)
    .join(' | ');
  return `${base}\n  ${details}`;
}

export function logVisualBugs(issues: VisualBugIssue[], title = 'Visual bug scan'): void {
  if (!issues.length) {
    console.info(`${title}: no issues found`);
    return;
  }

  console.groupCollapsed(`${title}: ${issues.length} issue(s)`);
  for (const issue of issues) {
    console.groupCollapsed(`${severityEmoji(issue.severity)} ${issue.kind} — ${issue.label}`);
    console.log(formatIssue(issue));
    console.log('element', issue.element);
    if (issue.related) console.log('related', issue.related);
    if (issue.evidence) console.log('evidence', issue.evidence);
    if (issue.suggestion) console.log('suggestion', issue.suggestion);
    console.groupEnd();
  }
  console.groupEnd();
}

export function scanAndLogVisualBugs(root: ParentNode = document.body, options: VisualBugScanOptions = {}): VisualBugIssue[] {
  const issues = scanVisualBugs(root, options);
  logVisualBugs(issues);
  return issues;
}

declare global {
  interface Window {
    scanVisualBugs?: typeof scanVisualBugs;
    logVisualBugs?: typeof logVisualBugs;
    scanAndLogVisualBugs?: typeof scanAndLogVisualBugs;
  }
}

if (typeof window !== 'undefined') {
  window.scanVisualBugs = scanVisualBugs;
  window.logVisualBugs = logVisualBugs;
  window.scanAndLogVisualBugs = scanAndLogVisualBugs;
}

