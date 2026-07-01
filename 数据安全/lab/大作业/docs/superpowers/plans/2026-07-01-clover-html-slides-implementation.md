# Clover HTML Slides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `clover_demo.html` 改造成可替代 PPT 的 Clover 论文汇报 HTML 幻灯片。

**Architecture:** 使用单文件 HTML 架构，CSS、HTML、JS 全部内联。页面采用固定 1920x1080 的 16:9 舞台，再整体缩放适配浏览器视口；内容按演讲主线组织成约 12-15 个 slide，每个交互模块由独立 JS 函数控制并可重置。

**Tech Stack:** 原生 HTML/CSS/JavaScript，内联 SVG/CSS 图形，浏览器键盘事件，零构建工具。

---

## File Structure

- Modify: `clover_demo.html`
  - 负责完整幻灯片展示、样式、导航、交互动画。
  - 不新增 npm、打包工具或外部运行时。
  - 当前文件已有 Clover 主题和部分交互逻辑，实现时直接重构为固定 16:9 deck。
- Read: `clover_notes.md`
  - 作为内容来源，提取论文背景、方法、实验、局限和总结。
- Read: `docs/superpowers/specs/2026-07-01-clover-html-slides-design.md`
  - 作为边界和页面结构依据。

---

### Task 1: Establish Fixed 16:9 Slide Shell

**Files:**
- Modify: `clover_demo.html`

- [ ] **Step 1: Replace responsive page shell with fixed stage**

Create a viewport wrapper and fixed deck stage:

```html
<body>
  <main class="viewport" aria-label="Clover HTML presentation">
    <div class="stage" id="stage">
      <section class="slide active" data-title="Clover">
        <h1>Clover</h1>
        <p>安全、差分隐私且通信高效的稀疏联邦学习</p>
      </section>
    </div>
    <nav class="deck-controls" aria-label="幻灯片导航">
      <button id="prevBtn" type="button">上一页</button>
      <div class="progress"><span id="progressBar"></span></div>
      <div class="counter" id="counter">1 / 1</div>
      <button id="nextBtn" type="button">下一页</button>
    </nav>
  </main>
</body>
```

- [ ] **Step 2: Add fixed-stage CSS**

Use fixed authoring dimensions and uniform scaling:

```css
:root {
  --stage-w: 1920;
  --stage-h: 1080;
  --scale: min(calc(100vw / 1920), calc((100vh - 84px) / 1080));
  --ink: #112427;
  --muted: #5f7478;
  --paper: #fbfdfb;
  --line: rgba(17, 36, 39, .14);
  --teal: #0b8f88;
  --blue: #315fbd;
  --risk: #d9552f;
  --gold: #c58b13;
  --noise: #7b5cc7;
}

* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
body { background: #0f191b; color: var(--ink); font-family: "Avenir Next", "Segoe UI", "PingFang SC", sans-serif; }
.viewport { width: 100vw; height: 100vh; display: grid; place-items: center; padding-bottom: 84px; position: relative; }
.stage {
  width: 1920px;
  height: 1080px;
  transform: scale(var(--scale));
  transform-origin: center center;
  position: relative;
  overflow: hidden;
  background: var(--paper);
  border-radius: 22px;
}
.slide {
  position: absolute;
  inset: 0;
  visibility: hidden;
  opacity: 0;
  pointer-events: none;
  transition: opacity .28s ease, transform .28s ease;
  transform: translateX(36px);
}
.slide.active {
  visibility: visible;
  opacity: 1;
  pointer-events: auto;
  transform: translateX(0);
}
.deck-controls {
  position: fixed;
  left: 24px;
  right: 24px;
  bottom: 18px;
  height: 48px;
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  gap: 14px;
  align-items: center;
}
```

- [ ] **Step 3: Verify shell locally**

Run:

```bash
open clover_demo.html
```

Expected: browser opens a 16:9 slide canvas with no vertical scrolling; controls stay outside the slide stage.

---

### Task 2: Rebuild Slide Content Around the Approved Mainline

**Files:**
- Modify: `clover_demo.html`
- Read: `clover_notes.md`
- Read: `docs/superpowers/specs/2026-07-01-clover-html-slides-design.md`

- [ ] **Step 1: Create slide list**

Use this slide sequence unless content density requires one split:

```text
1. Clover
2. 联邦学习的隐私错觉
3. 完整梯度通信成本高
4. top-k 梯度稀疏化
5. index 也会泄露隐私
6. Clover 的目标
7. 三服务器威胁模型
8. 稀疏向量表示
9. 隐藏 index/value 的聚合直觉
10. 为什么不用通用 ORAM
11. 分布式差分隐私
12. 实验结论
13. 局限与讨论
14. 总结
```

- [ ] **Step 2: Replace old five-slide markup**

Each slide uses the same high-level structure:

```html
<section class="slide" data-title="页面标题">
  <div class="slide-grid">
    <div class="copy">
      <p class="eyebrow">SECTION LABEL</p>
      <h1>主标题</h1>
      <p class="lead">一句话说明本页观点。</p>
      <ul class="talk-points">
        <li>最多三条短句。</li>
        <li>突出汇报时要讲的关键词。</li>
      </ul>
    </div>
    <div class="visual">
      <div class="diagram" data-module="module-name"></div>
    </div>
  </div>
</section>
```

- [ ] **Step 3: Apply content density rule**

For every slide:

```text
Heading: 8-18 Chinese characters when possible.
Lead: one sentence.
Bullets: 0-3 items.
No paragraph longer than 2 lines on 1920x1080 stage.
If a principle slide needs more than 3 bullets, split it into two slides.
```

- [ ] **Step 4: Commit content restructure**

Run:

```bash
git add clover_demo.html
git commit -m "Restructure Clover deck into speaker-led slides"
```

Expected: commit contains only `clover_demo.html`.

---

### Task 3: Implement Shared Navigation and Reset Behavior

**Files:**
- Modify: `clover_demo.html`

- [ ] **Step 1: Add navigation state**

Use one current slide index and update all slide UI from it:

```js
const slides = Array.from(document.querySelectorAll(".slide"));
let current = 0;

function showSlide(index) {
  current = (index + slides.length) % slides.length;
  slides.forEach((slide, i) => slide.classList.toggle("active", i === current));
  document.getElementById("counter").textContent = `${current + 1} / ${slides.length}`;
  document.getElementById("progressBar").style.width = `${((current + 1) / slides.length) * 100}%`;
  resetSlideAnimations(slides[current]);
}

function nextSlide() { showSlide(current + 1); }
function prevSlide() { showSlide(current - 1); }
```

- [ ] **Step 2: Add keyboard and button bindings**

```js
document.getElementById("nextBtn").addEventListener("click", nextSlide);
document.getElementById("prevBtn").addEventListener("click", prevSlide);
document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowRight" || event.key === " ") nextSlide();
  if (event.key === "ArrowLeft") prevSlide();
});
```

- [ ] **Step 3: Add deterministic reset hook**

```js
function resetSlideAnimations(slide) {
  slide.querySelectorAll("[data-active]").forEach((el) => el.removeAttribute("data-active"));
  slide.querySelectorAll(".is-active, .is-risk, .is-hidden, .is-noisy").forEach((el) => {
    el.classList.remove("is-active", "is-risk", "is-hidden", "is-noisy");
  });
}
```

- [ ] **Step 4: Verify navigation**

Open `clover_demo.html`, press left/right arrow keys, click buttons, and confirm the counter and progress bar update correctly.

---

### Task 4: Implement Communication and top-k Interaction Modules

**Files:**
- Modify: `clover_demo.html`

- [ ] **Step 1: Create reusable gradient cells**

Use fixed cell markup for dense and sparse gradient visuals:

```html
<div class="gradient-vector" id="topkVector">
  <span class="grad-cell" data-index="1">0.12</span>
  <span class="grad-cell keep" data-index="2">-1.84</span>
  <span class="grad-cell" data-index="3">0.05</span>
  <span class="grad-cell keep" data-index="4">1.36</span>
  <span class="grad-cell" data-index="5">-0.22</span>
  <span class="grad-cell keep" data-index="6">2.10</span>
  <span class="grad-cell" data-index="7">0.08</span>
  <span class="grad-cell" data-index="8">-0.17</span>
</div>
```

- [ ] **Step 2: Add top-k animation function**

```js
function playTopK() {
  document.querySelectorAll("#topkVector .grad-cell").forEach((cell) => {
    cell.classList.toggle("is-dropped", !cell.classList.contains("keep"));
    cell.classList.toggle("is-active", cell.classList.contains("keep"));
  });
  document.getElementById("topkPairs").setAttribute("data-active", "true");
}
```

- [ ] **Step 3: Add dense upload animation function**

```js
function playDenseUpload() {
  document.querySelectorAll(".upload-packet").forEach((packet, i) => {
    packet.style.animationDelay = `${i * 120}ms`;
    packet.classList.add("is-active");
  });
  document.getElementById("denseCost").setAttribute("data-active", "true");
}
```

- [ ] **Step 4: Verify the two modules**

Open `clover_demo.html`, navigate to the communication and top-k slides, click the module buttons, and confirm:

```text
Dense upload: packets move from clients to server.
top-k: non-top-k cells fade, selected cells remain highlighted, sparse pairs appear.
Reset: leaving and returning to the slide clears the animation state.
```

---

### Task 5: Implement Privacy-Risk and Sparse-Aggregation Principle Modules

**Files:**
- Modify: `clover_demo.html`

- [ ] **Step 1: Add index leakage view**

Use one visible server/attacker panel that sees only positions:

```html
<div class="index-risk-panel" id="indexRiskPanel">
  <div class="observed-indexes">
    <span>index 2</span>
    <span>index 4</span>
    <span>index 6</span>
  </div>
  <p>即使 value 被隐藏，top-k 位置模式仍可能暴露数据分布线索。</p>
</div>
```

- [ ] **Step 2: Add index leakage function**

```js
function playIndexRisk() {
  document.getElementById("indexRiskPanel").setAttribute("data-active", "true");
  document.querySelectorAll(".index-marker").forEach((marker) => marker.classList.add("is-risk"));
}
```

- [ ] **Step 3: Add hidden aggregation function**

```js
function playHiddenAggregation() {
  document.querySelectorAll(".private-update").forEach((update) => update.classList.add("is-hidden"));
  document.querySelectorAll(".share-line").forEach((line, i) => {
    line.style.animationDelay = `${i * 90}ms`;
    line.classList.add("is-active");
  });
  document.getElementById("aggregateVector").setAttribute("data-active", "true");
}
```

- [ ] **Step 4: Verify principle modules**

Expected:

```text
Index risk slide: only index markers become prominent; value cells do not become the focus.
Hidden aggregation slide: client updates become masked/sharded before reaching three servers.
Final output: aggregate vector appears, individual client updates remain hidden.
```

---

### Task 6: Implement ORAM Comparison and Distributed DP Module

**Files:**
- Modify: `clover_demo.html`

- [ ] **Step 1: Add ORAM comparison as static diagram**

Use two columns:

```html
<div class="compare-grid">
  <article class="compare-card heavy">
    <h3>通用 ORAM</h3>
    <p>隐藏访问模式，适用范围广，但为通用性付出高通信和运行成本。</p>
  </article>
  <article class="compare-card focused">
    <h3>Clover 专用设计</h3>
    <p>围绕 top-k 稀疏聚合优化，只解决当前任务需要的隐藏和聚合。</p>
  </article>
</div>
```

- [ ] **Step 2: Add DP trade-off controls**

```html
<input id="epsilonSlider" type="range" min="1" max="10" value="5" />
<div class="dp-metrics">
  <span id="privacyLabel">隐私强度：中</span>
  <span id="noiseLabel">噪声规模：中</span>
  <span id="utilityLabel">模型效用：中</span>
</div>
```

- [ ] **Step 3: Add DP update function**

```js
function updateDPTradeoff() {
  const epsilon = Number(document.getElementById("epsilonSlider").value);
  const strongPrivacy = epsilon <= 3;
  const weakPrivacy = epsilon >= 8;
  document.getElementById("privacyLabel").textContent = `隐私强度：${strongPrivacy ? "强" : weakPrivacy ? "弱" : "中"}`;
  document.getElementById("noiseLabel").textContent = `噪声规模：${strongPrivacy ? "大" : weakPrivacy ? "小" : "中"}`;
  document.getElementById("utilityLabel").textContent = `模型效用：${strongPrivacy ? "较低" : weakPrivacy ? "较高" : "中"}`;
}
document.getElementById("epsilonSlider").addEventListener("input", updateDPTradeoff);
```

- [ ] **Step 4: Verify ORAM and DP**

Expected:

```text
ORAM slide: comparison is static and readable from projector distance.
DP slide: moving epsilon slider updates privacy, noise, and utility labels immediately.
No text claims exact DP accounting or experimental reproduction.
```

---

### Task 7: Offline Robustness and Visual Polish

**Files:**
- Modify: `clover_demo.html`

- [ ] **Step 1: Remove external runtime dependency**

Replace external icon dependency with inline text/icons or CSS shapes. Remove:

```html
<script src="https://unpkg.com/lucide@latest"></script>
```

Expected: the deck works without network access.

- [ ] **Step 2: Add reduced-motion support**

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .001ms !important;
  }
}
```

- [ ] **Step 3: Check text fit**

Open each slide and verify:

```text
No heading overlaps visuals.
No bullet exceeds its panel.
Controls do not cover slide content.
Important labels are readable at 1280x720 browser size.
```

- [ ] **Step 4: Commit visual polish**

Run:

```bash
git add clover_demo.html
git commit -m "Polish Clover HTML deck visuals and offline behavior"
```

---

### Task 8: Final Verification

**Files:**
- Verify: `clover_demo.html`

- [ ] **Step 1: Run local static server**

Run:

```bash
python3 -m http.server 8080
```

Expected: server prints `Serving HTTP on :: port 8080` or equivalent.

- [ ] **Step 2: Open the deck**

Open:

```text
http://localhost:8080/clover_demo.html
```

Expected: deck loads with no missing external network dependency.

- [ ] **Step 3: Manual verification checklist**

Check:

```text
All slides reachable with keyboard and buttons.
Progress and counter match slide count.
Dense upload, top-k, index risk, sparse aggregation, and DP modules work.
Leaving and returning to interactive slides resets deterministic animation states.
No vertical scrolling.
No text overflow or incoherent overlap.
Deck remains speaker-led rather than report-like.
```

- [ ] **Step 4: Final commit**

Run:

```bash
git status --short
git add clover_demo.html
git commit -m "Finalize Clover presentation deck"
```

Expected: commit includes final `clover_demo.html` changes.

---

## Self-Review

- Spec coverage: The plan covers HTML-as-PPT format, flexible 12-15 page range, fixed 16:9 stage, speaker-led content density, detailed principle modules, interaction boundaries, offline presentation, and validation.
- Red-flag scan: The plan contains concrete paths, commands, code snippets, and expected verification results.
- Type consistency: Shared JS functions use consistent names: `showSlide`, `nextSlide`, `prevSlide`, `resetSlideAnimations`, `playTopK`, `playDenseUpload`, `playIndexRisk`, `playHiddenAggregation`, `updateDPTradeoff`.
