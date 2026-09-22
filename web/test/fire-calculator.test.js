import assert from "node:assert/strict";
import test from "node:test";

import {
  FIRE_EXPENSE_MULTIPLE,
  FIRE_WITHDRAWAL_RATE,
  calculateFirePlan,
} from "../src/fire-calculator.js";

test("calculates the 25x target and four-percent annual withdrawal", () => {
  const plan = calculateFirePlan(2_000, [
    { date: "2026-09-22", projected_value_eur: 25_000, months_ahead: 0 },
    { date: "2049-09-22", projected_value_eur: 590_000, months_ahead: 276 },
    { date: "2050-01-22", projected_value_eur: 605_000, months_ahead: 280 },
  ]);

  assert.equal(FIRE_EXPENSE_MULTIPLE, 25);
  assert.equal(FIRE_WITHDRAWAL_RATE, 0.04);
  assert.equal(plan.monthlyExpensesEur, 2_000);
  assert.equal(plan.annualExpensesEur, 24_000);
  assert.equal(plan.targetEur, 600_000);
  assert.equal(plan.annualWithdrawalEur, 24_000);
  assert.equal(plan.monthlyWithdrawalEur, 2_000);
  assert.deepEqual(plan.achievement, {
    date: "2050-01-22",
    projected_value_eur: 605_000,
    months_ahead: 280,
  });
});

test("returns the current point when the target is already funded", () => {
  const plan = calculateFirePlan(1_000, [
    { date: "2026-09-22", projected_value_eur: 350_000, months_ahead: 0 },
  ]);

  assert.equal(plan.targetEur, 300_000);
  assert.equal(plan.achievement.months_ahead, 0);
});

test("extends the same projection assumptions beyond the displayed 25 years", () => {
  const plan = calculateFirePlan(5_000, [
    { date: "2026-09-22", projected_value_eur: 25_000, months_ahead: 0 },
    { date: "2051-09-22", projected_value_eur: 700_000, months_ahead: 300 },
  ], {
    current_date: "2026-09-22",
    current_value_eur: 25_000,
    monthly_return_rate: 0.005,
    avg_monthly_net_deposit_eur: 1_000,
    projection_months: 300,
  });

  assert.equal(plan.targetEur, 1_500_000);
  assert.equal(plan.achievement.date, "2060-07-23");
  assert.equal(plan.achievement.months_ahead, 406);
  assert.equal(plan.achievement.extended, true);
  assert.ok(plan.achievement.projected_value_eur >= plan.targetEur);
});

test("reports no achievement when fixed assumptions cannot reach the target", () => {
  const plan = calculateFirePlan(
    5_000,
    [
      { date: "2026-09-22", projected_value_eur: 25_000, months_ahead: 0 },
      { date: "2051-09-22", projected_value_eur: 25_000, months_ahead: 300 },
    ],
    {
      current_date: "2026-09-22",
      current_value_eur: 25_000,
      monthly_return_rate: 0,
      avg_monthly_net_deposit_eur: 0,
      projection_months: 300,
    },
  );

  assert.equal(plan.achievement, undefined);
});

test("requires positive finite monthly expenses", () => {
  assert.equal(calculateFirePlan("", []), undefined);
  assert.equal(calculateFirePlan(0, []), undefined);
  assert.equal(calculateFirePlan(-1, []), undefined);
  assert.equal(calculateFirePlan(Number.POSITIVE_INFINITY, []), undefined);
});
