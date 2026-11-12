#!/usr/bin/env node
// Headless QA using already-installed Playwright/Chromium. Never installs tools.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const VIEWPORTS = [{width: 1440, height: 900}, {width: 390, height: 844}, {width: 320, height: 844}];

function loadPlaywright() {
  const candidates = ['playwright', 'playwright-core'];
  const cache = path.join(os.homedir(), '.npm', '_npx');
  if (fs.existsSync(cache)) {
    for (const entry of fs.readdirSync(cache).sort()) {
      candidates.push(path.join(cache, entry, 'node_modules', 'playwright'));
    }
  }
  for (const candidate of candidates) {
    try {
      const module = require(candidate);
      if (fs.existsSync(module.chromium.executablePath())) return module;
    } catch { /* Try another installed package; never invoke npx. */ }
  }
  throw new Error('Installed Playwright and matching Chromium required for daily QA; nothing was installed.');
}

async function check(base, slug, output) {
  fs.mkdirSync(output, {recursive: true});
  const report = {passed: false, pages: [], failures: []};
  let browser;
  try {
    browser = await loadPlaywright().chromium.launch();
    for (const viewport of VIEWPORTS) {
      for (const filename of ['index.html', 'demo.html']) {
        const page = await browser.newPage({viewport});
        const errors = [];
        const failedResources = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('response', response => {
          if (response.url().startsWith(base + '/') && response.status() >= 400) {
            failedResources.push({url: response.url(), status: response.status()});
          }
        });
        await page.route('**/*', route => {
          const url = new URL(route.request().url());
          if (url.origin === base || ['fonts.googleapis.com', 'fonts.gstatic.com'].includes(url.hostname)
              || ['data:', 'blob:'].includes(url.protocol)) return route.continue();
          return route.abort();
        });
        const response = await page.goto(`${base}/entries/${slug}/${filename}`, {
          waitUntil: 'domcontentloaded', timeout: 30000,
        });
        await page.evaluate(async () => {
          document.querySelectorAll('img').forEach(image => image.loading = 'eager');
          await Promise.race([
            Promise.all([document.fonts.ready, ...[...document.images].map(image => image.decode().catch(() => {}))]),
            new Promise(resolve => setTimeout(resolve, 5000)),
          ]);
        });
        const details = await page.evaluate(() => ({
          viewportWidth: innerWidth,
          scrollWidth: document.documentElement.scrollWidth,
          brokenImages: [...document.images].filter(image => !image.complete || !image.naturalWidth)
            .map(image => image.getAttribute('src')),
          links: [...document.querySelectorAll('a[href]')].map(link => link.href),
          controls: [...document.querySelectorAll('button,input,select,textarea')].map(control => ({
            tag: control.tagName, id: control.id, type: control.type || '',
            label: control.getAttribute('aria-label') || '',
            text: (control.innerText || control.placeholder || '').slice(0, 140),
          })),
        }));
        const counterpart = filename === 'index.html' ? 'demo.html' : 'index.html';
        const hasNavigation = details.links.some(link => {
          const url = new URL(link);
          return url.origin === base && [
            `/entries/${slug}/${counterpart}`,
            ...(counterpart === 'index.html' ? [`/entries/${slug}/`] : []),
          ].includes(url.pathname);
        });
        const failures = [];
        if (!response || response.status() !== 200) failures.push('Page did not return HTTP 200');
        if (details.scrollWidth > viewport.width + 2) failures.push('Page overflows viewport horizontally');
        if (errors.length) failures.push('JavaScript runtime errors');
        if (failedResources.length) failures.push('Local resource request failed');
        if (details.brokenImages.length) failures.push('Broken rendered images');
        if (!hasNavigation) failures.push(`Missing link to ${counterpart}`);
        const screenshot = path.join(output, `${filename}-${viewport.width}.png`);
        await page.screenshot({path: screenshot, fullPage: true, timeout: 15000});
        const foldScreenshot = path.join(output, `${filename}-${viewport.width}-fold.png`);
        await page.screenshot({path: foldScreenshot, fullPage: false, timeout: 15000});
        report.pages.push({filename, viewport, screenshot, foldScreenshot, errors, failedResources, failures, ...details});
        await page.close();
      }
    }
    const gallery = await browser.newPage();
    const response = await gallery.goto(base + '/', {waitUntil: 'domcontentloaded', timeout: 30000});
    if (!response || response.status() !== 200 ||
        !await gallery.locator(`a[href="/entries/${slug}/"]`).count()) {
      report.failures.push('Gallery is missing the generated entry link');
    }
    await gallery.close();
    report.passed = !report.failures.length && report.pages.every(page => !page.failures.length);
  } catch (error) {
    report.failures.push(error.message);
  } finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(output, 'browser.json'), JSON.stringify(report, null, 2) + '\n');
  }
  return report.passed;
}

async function readAssertion(page, assertion) {
  const locator = page.locator(assertion.selector);
  switch (assertion.check) {
    case 'visible': case 'hidden': return String(await locator.first().isVisible());
    case 'count': return String(await locator.count());
    case 'text': return await locator.first().textContent({timeout: 1000}).catch(() => null);
    // Native progress/meter widgets expose numeric .value, too. inputValue()
    // only accepts input, textarea and select elements.
    case 'value': return await locator.first().evaluate(
      element => 'value' in element ? String(element.value) : null,
      undefined, {timeout: 1000},
    ).catch(() => null);
    default: throw new Error(`Unknown assertion: ${assertion.check}`);
  }
}

function assertionMatches(assertion, observed) {
  if (assertion.check === 'visible') return observed === 'true';
  if (assertion.check === 'hidden') return observed === 'false';
  if (assertion.check === 'text') return typeof observed === 'string' && observed.includes(assertion.expected);
  return observed === assertion.expected;
}

async function exercise(base, slug, planFile, output) {
  const plan = JSON.parse(fs.readFileSync(planFile, 'utf8')).demo_test;
  const report = {passed: false, viewports: [], failures: []};
  let browser;
  try {
    if (!plan || ![plan.actions, plan.assertions].every(items => Array.isArray(items) && items.length >= 1 && items.length <= 8)) {
      throw new Error('A bounded demo action and assertion plan is required');
    }
    browser = await loadPlaywright().chromium.launch();
    for (const viewport of VIEWPORTS) {
      const page = await browser.newPage({viewport});
      const result = {viewport, passed: false, actions: [], assertions: [], errors: [], failures: []};
      report.viewports.push(result);
      page.on('pageerror', error => result.errors.push(error.message));
      page.on('response', response => {
        if (response.url().startsWith(base + '/') && response.status() >= 400) {
          result.failures.push(`Local resource returned ${response.status()}: ${response.url()}`);
        }
      });
      await page.route('**/*', route => {
        const url = new URL(route.request().url());
        return url.origin === base || ['fonts.googleapis.com', 'fonts.gstatic.com'].includes(url.hostname)
          || ['data:', 'blob:'].includes(url.protocol) ? route.continue() : route.abort();
      });
      try {
        const response = await page.goto(`${base}/entries/${slug}/demo.html`, {waitUntil: 'domcontentloaded', timeout: 30000});
        if (!response || response.status() !== 200) throw new Error('Demo did not return HTTP 200');
        const before = [];
        for (const assertion of plan.assertions) before.push(await readAssertion(page, assertion));
        for (const action of plan.actions) {
          const locator = page.locator(action.selector);
          switch (action.action) {
            case 'click': await locator.click({timeout: 8000}); break;
            case 'fill': await locator.fill(action.value, {timeout: 8000}); break;
            case 'select': await locator.selectOption(action.value, {timeout: 8000}); break;
            case 'press': await locator.press(action.value, {timeout: 8000}); break;
            default: throw new Error(`Unknown action: ${action.action}`);
          }
          result.actions.push(action);
        }
        for (const [index, assertion] of plan.assertions.entries()) {
          const deadline = Date.now() + 6000;
          let observed;
          do {
            observed = await readAssertion(page, assertion);
            if (assertionMatches(assertion, observed)) break;
            await new Promise(resolve => setTimeout(resolve, 150));
          } while (Date.now() < deadline);
          result.assertions.push({...assertion, before: before[index], observed,
            passed: assertionMatches(assertion, observed)});
        }
        if (!result.assertions.some(assertion => assertion.before !== assertion.observed)) {
          result.failures.push('The test did not verify a changed rendered state after its actions');
        }
        if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)) {
          result.failures.push('Demo overflows horizontally after interaction');
        }
        await page.evaluate(async () => {
          document.querySelectorAll('img').forEach(image => image.loading = 'eager');
          await Promise.race([
            Promise.all([...document.images].map(image => image.decode().catch(() => {}))),
            new Promise(resolve => setTimeout(resolve, 5000)),
          ]);
        });
        if (await page.locator('img').evaluateAll(images => images.some(image => !image.complete || !image.naturalWidth))) {
          result.failures.push('Broken rendered image after interaction');
        }
        result.screenshot = path.join(output, `interaction-${viewport.width}.png`);
        await page.screenshot({path: result.screenshot, fullPage: true, timeout: 15000});
        result.passed = !result.errors.length && !result.failures.length && result.assertions.every(assertion => assertion.passed);
      } catch (error) {
        result.failures.push(error.message);
      } finally {
        await page.close();
      }
    }
    report.passed = report.viewports.every(viewport => viewport.passed);
  } catch (error) {
    report.failures.push(error.message);
  } finally {
    if (browser) await browser.close();
    fs.mkdirSync(output, {recursive: true});
    fs.writeFileSync(path.join(output, 'interaction.json'), JSON.stringify(report, null, 2) + '\n');
  }
  return report.passed;
}

module.exports = {loadPlaywright, check, exercise};
if (require.main === module) {
  (async () => {
    if (process.argv[2] === '--preflight') {
      const browser = await loadPlaywright().chromium.launch();
      await browser.close();
      console.log('browser preflight: installed Playwright and Chromium OK');
      return;
    }
    const interactive = process.argv[2] === '--interaction';
    const [base, slug, third, fourth] = process.argv.slice(interactive ? 3 : 2);
    const output = interactive ? fourth : third;
    if (!base || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug || '') || !output) {
      throw new Error('Usage: check-entry-browser.cjs <local-base-url> <slug> <output-directory>');
    }
    process.exitCode = await (interactive
      ? exercise(base.replace(/\/$/, ''), slug, third, output)
      : check(base.replace(/\/$/, ''), slug, output)) ? 0 : 1;
  })().catch(error => { console.error(error.message); process.exitCode = 1; });
}
