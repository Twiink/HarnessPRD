import type { RequirementsSummary } from '../services/sessionService';
import type { Message } from '../types';
import type { ReadinessCheckItem, ReadinessResult } from '../types/readiness';

export type AssessReadinessInput = {
  summary: RequirementsSummary | null;
  messages?: Message[];
};

function nonEmptyLines(value: string | string[] | undefined): string[] {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value.map((v) => v.trim()).filter(Boolean);
  }
  return value
    .split('\n')
    .map((v) => v.trim())
    .filter(Boolean);
}

function countClarificationRounds(messages: Message[]): number {
  const visible = messages.filter((m) => m.role !== 'system');
  if (visible.length <= 1) return 0;
  let rounds = 0;
  for (const msg of visible.slice(1)) {
    if (msg.content?.trim()) rounds += 1;
  }
  return Math.max(0, Math.floor(rounds / 2));
}

function hasNfr(summary: RequirementsSummary): boolean {
  const nfr = summary.non_functional_requirements;
  if (!nfr) return false;
  const groups = [nfr.performance, nfr.security, nfr.usability];
  return groups.some((g) => Array.isArray(g) && g.some((item) => item.trim()));
}

function buildCheck(
  id: string,
  label: string,
  passed: boolean,
  severity: 'blocker' | 'warning',
  detail?: string,
  fieldHint?: string,
): ReadinessCheckItem {
  return { id, label, passed, severity, detail, fieldHint };
}

function computeScore(checks: ReadinessCheckItem[]): number {
  if (checks.length === 0) return 0;
  let weightSum = 0;
  let earned = 0;
  for (const check of checks) {
    const weight = check.severity === 'blocker' ? 2 : 1;
    weightSum += weight;
    if (check.passed) earned += weight;
  }
  return Math.round((earned / weightSum) * 100);
}

export function assessRequirementsReadiness(input: AssessReadinessInput): ReadinessResult {
  const { summary, messages = [] } = input;

  if (!summary) {
    const missing = buildCheck(
      'summary.missing',
      '结构化需求摘要',
      false,
      'blocker',
      '请先完成结构化表单',
      'form',
    );
    return {
      score: 0,
      blockers: [missing],
      warnings: [],
      checks: [missing],
    };
  }

  const checks: ReadinessCheckItem[] = [];

  const productName = (summary.product_name || '').trim();
  checks.push(
    buildCheck(
      'summary.product_name',
      '产品名称',
      Boolean(productName),
      'blocker',
      productName ? undefined : '请填写产品名称',
      'product_name',
    ),
  );

  const productGoal = (summary.product_goal || '').trim();
  checks.push(
    buildCheck(
      'summary.product_goal',
      '产品目标',
      productGoal.length >= 10,
      'blocker',
      productGoal.length >= 10 ? undefined : '产品目标至少 10 字，需说明解决什么问题',
      'product_goal',
    ),
  );

  const features = summary.features || [];
  checks.push(
    buildCheck(
      'summary.features',
      '产品功能',
      features.length >= 1,
      'blocker',
      features.length >= 1 ? undefined : '至少填写 1 条产品功能',
      'features',
    ),
  );

  if (features.length > 0) {
    const emptyDesc = features.filter((f) => !(f.description || '').trim()).length;
    const shortDesc = features.filter((f) => ((f.description || '').trim().length > 0) && (f.description || '').trim().length < 10).length;
    const half = Math.ceil(features.length / 2);
    const tooManyShort = shortDesc >= half;
    checks.push(
      buildCheck(
        'summary.features.description',
        '产品功能描述',
        emptyDesc === 0 && !tooManyShort,
        tooManyShort || emptyDesc > 0 ? 'warning' : 'warning',
        emptyDesc > 0
          ? `${emptyDesc} 条 产品功能 缺少功能描述`
          : tooManyShort
            ? '过半数 产品功能 描述过短（建议每条 ≥10 字）'
            : undefined,
        'features',
      ),
    );
  }

  const platform = (summary.platform || '').trim();
  checks.push(
    buildCheck(
      'summary.platform',
      '产品平台',
      Boolean(platform),
      'blocker',
      platform ? undefined : '请填写产品平台（如 Web App）',
      'platform',
    ),
  );

  const inScope = nonEmptyLines(summary.in_scope as string | string[] | undefined);
  checks.push(
    buildCheck(
      'summary.in_scope',
      '在范围内',
      inScope.length >= 1,
      'warning',
      inScope.length >= 1 ? undefined : '建议补充项目交付范围',
      'in_scope',
    ),
  );

  const outScope = nonEmptyLines(summary.out_of_scope as string | string[] | undefined);
  checks.push(
    buildCheck(
      'summary.out_of_scope',
      '不在范围内',
      outScope.length >= 1,
      'warning',
      outScope.length >= 1 ? undefined : '建议补充项目范围外的事项',
      'out_of_scope',
    ),
  );

  checks.push(
    buildCheck(
      'summary.nfr',
      '非功能需求',
      hasNfr(summary),
      'warning',
      hasNfr(summary) ? undefined : '建议补充性能、安全或可用性要求',
      'non_functional',
    ),
  );

  const rounds = countClarificationRounds(messages);
  const coreBlockers = checks.filter((c) => c.severity === 'blocker' && !c.passed).length;
  checks.push(
    buildCheck(
      'clarification.rounds',
      '澄清对话',
      rounds > 0 || coreBlockers === 0,
      'warning',
      rounds === 0 && coreBlockers > 0 ? '尚未澄清，核心字段可能仍不完整' : rounds === 0 ? '尚未开始澄清，可直接生成或先补充对话' : undefined,
    ),
  );

  const blockers = checks.filter((c) => !c.passed && c.severity === 'blocker');
  const warnings = checks.filter((c) => !c.passed && c.severity === 'warning');
  let score = computeScore(checks);
  if (blockers.length > 0) {
    score = Math.min(score, 59);
  }

  return { score, blockers, warnings, checks };
}

export function readinessStatusLabel(result: ReadinessResult): string {
  if (result.blockers.length > 0) {
    return `${result.blockers.length} 项待补齐`;
  }
  if (result.warnings.length > 0) {
    return `${result.warnings.length} 项建议`;
  }
  return '可生成 PRD';
}

export function readinessScoreClass(score: number, hasBlockers: boolean): string {
  if (hasBlockers || score < 60) return 'border border-mark text-mark';
  if (score < 80) return 'border border-stamp text-stamp';
  return 'border border-primary-600 text-primary-700';
}
