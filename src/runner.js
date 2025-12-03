#!/usr/bin/env node

/**
 * SiFR Benchmark Runner
 * Evaluates LLM performance across different UI representation formats
 */

import fs from 'fs/promises';
import path from 'path';
import { OpenAI } from 'openai';
import Anthropic from '@anthropic-ai/sdk';

const MODELS = {
  'gpt-4o': { provider: 'openai', model: 'gpt-4o' },
  'gpt-4o-mini': { provider: 'openai', model: 'gpt-4o-mini' },
  'claude-sonnet': { provider: 'anthropic', model: 'claude-sonnet-4-20250514' },
  'claude-haiku': { provider: 'anthropic', model: 'claude-haiku-4-5-20251001' },
};

const FORMATS = ['sifr', 'html_raw', 'html_clean', 'axtree'];

class BenchmarkRunner {
  constructor(config) {
    this.config = config;
    this.results = [];
    this.openai = new OpenAI();
    this.anthropic = new Anthropic();
  }

  async loadTasks() {
    const data = await fs.readFile('benchmark/tasks.json', 'utf-8');
    return JSON.parse(data);
  }

  async loadPage(pageId, format) {
    const ext = format === 'sifr' ? '.sifr' : '.json';
    const filePath = `datasets/formats/${format}/${pageId}${ext}`;
    return fs.readFile(filePath, 'utf-8');
  }

  async loadGroundTruth(pageId) {
    const filePath = `benchmark/ground-truth/${pageId}.json`;
    const data = await fs.readFile(filePath, 'utf-8');
    return JSON.parse(data);
  }

  buildPrompt(task, context, format) {
    return `You are analyzing a webpage represented in ${format} format.

CONTEXT:
${context}

QUESTION: ${task.question}

Respond in this exact format:
ANSWER: [your answer]
CONFIDENCE: [0-100]
EVIDENCE: [element IDs or text that supports your answer]`;
  }

  async queryModel(modelKey, prompt) {
    const { provider, model } = MODELS[modelKey];
    const start = Date.now();

    try {
      let response, tokens;

      if (provider === 'openai') {
        const res = await this.openai.chat.completions.create({
          model,
          messages: [{ role: 'user', content: prompt }],
          temperature: 0,
          max_tokens: 500,
        });
        response = res.choices[0].message.content;
        tokens = res.usage.total_tokens;
      } else if (provider === 'anthropic') {
        const res = await this.anthropic.messages.create({
          model,
          max_tokens: 500,
          messages: [{ role: 'user', content: prompt }],
        });
        response = res.content[0].text;
        tokens = res.usage.input_tokens + res.usage.output_tokens;
      }

      return {
        response,
        tokens,
        latency: Date.now() - start,
        error: null,
      };
    } catch (err) {
      return {
        response: null,
        tokens: 0,
        latency: Date.now() - start,
        error: err.message,
      };
    }
  }

  parseResponse(raw) {
    const lines = raw.split('\n');
    const result = { answer: '', confidence: 0, evidence: '' };

    for (const line of lines) {
      if (line.startsWith('ANSWER:')) {
        result.answer = line.replace('ANSWER:', '').trim();
      } else if (line.startsWith('CONFIDENCE:')) {
        result.confidence = parseInt(line.replace('CONFIDENCE:', '').trim()) || 0;
      } else if (line.startsWith('EVIDENCE:')) {
        result.evidence = line.replace('EVIDENCE:', '').trim();
      }
    }

    return result;
  }

  scoreResponse(parsed, groundTruth, scoringType) {
    const answer = parsed.answer.toLowerCase().trim();
    const truth = groundTruth.toLowerCase().trim();

    switch (scoringType) {
      case 'element_id':
        return answer === truth ? 1.0 : 0.0;

      case 'text_match':
        if (answer === truth) return 1.0;
        if (answer.includes(truth) || truth.includes(answer)) return 0.5;
        return 0.0;

      case 'numeric':
        return parseFloat(answer) === parseFloat(truth) ? 1.0 : 0.0;

      case 'precision_recall':
        const predSet = new Set(answer.split(',').map(s => s.trim()));
        const truthSet = new Set(truth.split(',').map(s => s.trim()));
        const intersection = [...predSet].filter(x => truthSet.has(x));
        const precision = intersection.length / predSet.size || 0;
        const recall = intersection.length / truthSet.size || 0;
        return precision + recall > 0 ? (2 * precision * recall) / (precision + recall) : 0;

      default:
        return answer === truth ? 1.0 : 0.0;
    }
  }

  async runSingleTest(modelKey, format, pageId, task, groundTruth) {
    const context = await this.loadPage(pageId, format);
    const prompt = this.buildPrompt(task, context, format);
    const { response, tokens, latency, error } = await this.queryModel(modelKey, prompt);

    if (error) {
      return { model: modelKey, format, pageId, taskId: task.id, error, score: 0 };
    }

    const parsed = this.parseResponse(response);
    const truthEntry = groundTruth.tasks[task.id];
    const score = this.scoreResponse(parsed, truthEntry.answer, task.scoring);

    return {
      model: modelKey,
      format,
      pageId,
      taskId: task.id,
      response: parsed.answer,
      confidence: parsed.confidence,
      evidence: parsed.evidence,
      expected: truthEntry.answer,
      score,
      tokens,
      latency,
    };
  }

  async run() {
    const { tasks } = await this.loadTasks();
    const pages = this.config.pages || ['product_page'];
    const models = this.config.models || Object.keys(MODELS);
    const formats = this.config.formats || FORMATS;
    const runs = this.config.runs || 3;

    console.log(`\n🚀 SiFR Benchmark`);
    console.log(`   Models: ${models.join(', ')}`);
    console.log(`   Formats: ${formats.join(', ')}`);
    console.log(`   Pages: ${pages.length}`);
    console.log(`   Tasks: ${tasks.length}`);
    console.log(`   Runs per combo: ${runs}\n`);

    for (const pageId of pages) {
      const groundTruth = await this.loadGroundTruth(pageId);

      for (const model of models) {
        for (const format of formats) {
          for (const task of tasks) {
            for (let r = 0; r < runs; r++) {
              process.stdout.write(`  ${model}/${format}/${task.id} [${r + 1}/${runs}]...\r`);

              const result = await this.runSingleTest(model, format, pageId, task, groundTruth);
              result.run = r + 1;
              this.results.push(result);

              // Rate limiting
              await new Promise(res => setTimeout(res, 200));
            }
          }
        }
      }
    }

    return this.results;
  }

  aggregate() {
    const agg = {};

    for (const r of this.results) {
      const key = `${r.model}|${r.format}`;
      if (!agg[key]) {
        agg[key] = { model: r.model, format: r.format, scores: [], tokens: [], latencies: [] };
      }
      agg[key].scores.push(r.score);
      agg[key].tokens.push(r.tokens);
      agg[key].latencies.push(r.latency);
    }

    const stats = [];
    for (const key of Object.keys(agg)) {
      const d = agg[key];
      stats.push({
        model: d.model,
        format: d.format,
        accuracy: (d.scores.reduce((a, b) => a + b, 0) / d.scores.length * 100).toFixed(1) + '%',
        avg_tokens: Math.round(d.tokens.reduce((a, b) => a + b, 0) / d.tokens.length),
        avg_latency: Math.round(d.latencies.reduce((a, b) => a + b, 0) / d.latencies.length) + 'ms',
      });
    }

    return stats.sort((a, b) => parseFloat(b.accuracy) - parseFloat(a.accuracy));
  }

  async saveResults(outputDir) {
    await fs.mkdir(outputDir, { recursive: true });

    await fs.writeFile(
      path.join(outputDir, 'raw_results.json'),
      JSON.stringify(this.results, null, 2)
    );

    const stats = this.aggregate();
    await fs.writeFile(
      path.join(outputDir, 'summary.json'),
      JSON.stringify(stats, null, 2)
    );

    console.log(`\n📊 Results saved to ${outputDir}/`);
    console.table(stats);
  }
}

// CLI
const args = process.argv.slice(2);
const config = {
  models: args.includes('--models') ? args[args.indexOf('--models') + 1].split(',') : undefined,
  formats: args.includes('--formats') ? args[args.indexOf('--formats') + 1].split(',') : undefined,
  pages: args.includes('--pages') ? args[args.indexOf('--pages') + 1].split(',') : undefined,
  runs: args.includes('--runs') ? parseInt(args[args.indexOf('--runs') + 1]) : 3,
  output: args.includes('--output') ? args[args.indexOf('--output') + 1] : 'results/run_' + Date.now(),
};

const runner = new BenchmarkRunner(config);
runner.run().then(() => runner.saveResults(config.output));
