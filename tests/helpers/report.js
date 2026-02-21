const fs = require('fs');
const path = require('path');

const SCREENSHOTS_DIR = path.join(__dirname, '..', 'screenshots');
const RESULTS_DIR = path.join(__dirname, '..', 'test-results');

class FrictionLogger {
  constructor(journeyName, page) {
    this.journeyName = journeyName;
    this.page = page;
    this.steps = [];
    this.frictions = [];
    this.startTime = Date.now();
    this.stepCounter = 0;

    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
  }

  async step(name, fn) {
    this.stepCounter++;
    const stepNum = String(this.stepCounter).padStart(2, '0');
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '');
    const screenshotName = `${this.journeyName}-${stepNum}-${slug}.png`;
    const stepRecord = {
      number: this.stepCounter,
      name,
      screenshot: screenshotName,
      status: 'pass',
      error: null,
      duration: 0,
    };

    const stepStart = Date.now();

    try {
      await fn();
      await this.page.screenshot({
        path: path.join(SCREENSHOTS_DIR, screenshotName),
        fullPage: false,
        timeout: 30000,
      });
    } catch (err) {
      stepRecord.status = 'fail';
      stepRecord.error = err.message;

      // Take screenshot even on failure
      try {
        await this.page.screenshot({
          path: path.join(SCREENSHOTS_DIR, screenshotName),
          fullPage: false,
          timeout: 15000,
        });
      } catch (_) {
        // Screenshot failed too — skip it
      }

      throw err;
    } finally {
      stepRecord.duration = Date.now() - stepStart;
      this.steps.push(stepRecord);
    }
  }

  logFriction(severity, description, suggestion) {
    this.frictions.push({
      severity,
      description,
      suggestion: suggestion || '',
      step: this.stepCounter,
    });
  }

  async checkLinks(selector) {
    const links = await this.page.$$(selector + ' a');
    const issues = [];

    for (const link of links) {
      const href = await link.getAttribute('href');
      const text = (await link.textContent()).trim();

      if (!href || href === '#' || href === 'javascript:void(0)' || href === 'javascript:void(0);') {
        issues.push({ text: text || '(no text)', href: href || '(empty)', problem: 'broken href' });
      }
    }

    if (issues.length > 0) {
      this.logFriction(
        'medium',
        `Found ${issues.length} link(s) with broken href patterns in "${selector}": ${issues.map(i => `"${i.text}" → ${i.href}`).join(', ')}`,
        'Ensure all links have valid destinations'
      );
    }

    return issues;
  }

  async checkAccessibility(selector) {
    const issues = [];

    // Check images have alt text
    const images = await this.page.$$(selector + ' img');
    for (const img of images) {
      const alt = await img.getAttribute('alt');
      if (!alt && alt !== '') {
        issues.push('Image missing alt attribute');
      }
    }

    // Check buttons have accessible text
    const buttons = await this.page.$$(selector + ' button');
    for (const btn of buttons) {
      const text = (await btn.textContent()).trim();
      const ariaLabel = await btn.getAttribute('aria-label');
      const title = await btn.getAttribute('title');
      if (!text && !ariaLabel && !title) {
        issues.push('Button missing text/aria-label/title');
      }
    }

    // Check inputs have labels
    const inputs = await this.page.$$(selector + ' input:not([type="hidden"])');
    for (const input of inputs) {
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const placeholder = await input.getAttribute('placeholder');
      if (id) {
        const label = await this.page.$(`${selector} label[for="${id}"]`);
        if (!label && !ariaLabel && !placeholder) {
          issues.push(`Input #${id} missing label/aria-label/placeholder`);
        }
      }
    }

    if (issues.length > 0) {
      this.logFriction(
        'medium',
        `Accessibility issues in "${selector}": ${issues.join('; ')}`,
        'Add missing alt text, aria-labels, and form labels'
      );
    }

    return issues;
  }

  generateReport() {
    const totalDuration = Date.now() - this.startTime;
    const passedSteps = this.steps.filter(s => s.status === 'pass').length;

    // Rating: start at 10, deduct per friction severity
    const deductions = { critical: 3, high: 2, medium: 1, low: 0.5 };
    let rating = 10;
    for (const f of this.frictions) {
      rating -= deductions[f.severity] || 0;
    }
    rating = Math.max(1, Math.round(rating * 10) / 10);

    const result = {
      journeyName: this.journeyName,
      rating,
      steps: this.steps,
      frictions: this.frictions,
      timing: {
        total: totalDuration,
        totalFormatted: (totalDuration / 1000).toFixed(1) + 's',
      },
      passedSteps,
      totalSteps: this.steps.length,
    };

    // Write JSON result for report aggregation
    const resultPath = path.join(RESULTS_DIR, `${this.journeyName}.json`);
    fs.writeFileSync(resultPath, JSON.stringify(result, null, 2));

    return result;
  }
}

function generateMarkdownReport(resultsDir) {
  const dir = resultsDir || RESULTS_DIR;
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));

  if (files.length === 0) {
    console.log('No journey results found in', dir);
    return;
  }

  const results = files.map(f => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8')));
  const baseURL = process.env.BASE_URL || 'https://neshama.ca';
  const timestamp = new Date().toISOString().replace('T', ' ').replace(/\.\d+Z/, ' UTC');

  const journeyLabels = {
    'community-member': 'Community Member',
    'shiva-organizer': 'Shiva Organizer',
    'caterer-directory': 'Caterer Directory',
  };

  let md = `# Neshama Pre-Deploy Smoke Test Report\nGenerated: ${timestamp} | Target: ${baseURL}\n\n`;

  // Summary table
  md += `## Summary\n| Journey | Rating | Steps | Frictions | Time |\n|---------|--------|-------|-----------|------|\n`;
  for (const r of results) {
    const label = journeyLabels[r.journeyName] || r.journeyName;
    md += `| ${label} | ${r.rating}/10 | ${r.passedSteps}/${r.totalSteps} | ${r.frictions.length} | ${r.timing.totalFormatted} |\n`;
  }

  // Prioritized fixes (all frictions sorted by severity)
  const allFrictions = [];
  for (const r of results) {
    for (const f of r.frictions) {
      allFrictions.push({ ...f, journey: journeyLabels[r.journeyName] || r.journeyName });
    }
  }
  const severityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  allFrictions.sort((a, b) => (severityOrder[a.severity] ?? 4) - (severityOrder[b.severity] ?? 4));

  if (allFrictions.length > 0) {
    md += `\n## Prioritized Fixes\n`;
    allFrictions.forEach((f, i) => {
      md += `${i + 1}. [${f.severity.toUpperCase()}] (${f.journey}) ${f.description}`;
      if (f.suggestion) md += ` — ${f.suggestion}`;
      md += `\n`;
    });
  }

  // Per-journey sections
  for (const r of results) {
    const label = journeyLabels[r.journeyName] || r.journeyName;
    md += `\n## Journey: ${label}\n`;

    md += `### Steps\n`;
    for (const s of r.steps) {
      const icon = s.status === 'pass' ? 'PASS' : 'FAIL';
      md += `- [${icon}] Step ${s.number}: ${s.name} (${(s.duration / 1000).toFixed(1)}s)`;
      if (s.error) md += ` — Error: ${s.error}`;
      md += `\n`;
    }

    if (r.frictions.length > 0) {
      md += `### Friction Points\n`;
      for (const f of r.frictions) {
        md += `- [${f.severity.toUpperCase()}] ${f.description}`;
        if (f.suggestion) md += ` — ${f.suggestion}`;
        md += `\n`;
      }
    }

    md += `### Screenshots\n`;
    md += r.steps.map(s => s.screenshot).join(', ') + `\n`;
  }

  const reportPath = path.join(__dirname, '..', 'playwright-report.md');
  fs.writeFileSync(reportPath, md);
  console.log(`Report saved to ${reportPath}`);
  return md;
}

module.exports = { FrictionLogger, generateMarkdownReport };
