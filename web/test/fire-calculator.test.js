import assert from "node:assert/strict";
import test from "node:test";

import {
  FIRE_EXPENSE_MULTIPLE,
  FIRE_WITHDRAWAL_RATE,
  calculateFirePlan,
  fireYearsRemaining,
  formatFireProjection,
} from "../src/fire-calculator.js";

test("calculates the 25x target and four-percent annual withdrawal", () => {
  const plan = calculateFirePlan(
    2_000,
    0,
    [
      { date: "2026-09-22", projected_value_eur: 25_000, months_ahead: 0 },
      { date: "2049-09-22", projected_value_eur: 590_000, months_ahead: 276 },
      { date: "2050-01-22", projected_value_eur: 605_000, months_ahead: 280 },
    ],
    {},
  );

  assert.equal(FIRE_EXPENSE_MULTIPLE, 25);
  assert.equal(FIRE_WITHDRAWAL_RATE, 0.04);
  assert.equal(plan.monthlyExpensesEur, 2_000);
  assert.equal(plan.annualExpensesEur, 24_000);
  assert.equal(plan.currentTargetEur, 600_000);
  assert.equal(plan.retirementTargetEur, 600_000);
  assert.equal(plan.retirementMonthlyExpensesEur, 2_000);
  assert.equal(plan.annualWithdrawalEur, 24_000);
  assert.equal(plan.monthlyWithdrawalEur, 2_000);
  assert.equal(plan.yearsRemaining, 24);
  assert.equal(formatFireProjection(plan), "2050 (24 years remaining)");
  assert.deepEqual(plan.achievement, {
    date: "2050-01-22",
    projected_value_eur: 605_000,
    months_ahead: 280,
    monthly_expenses_eur: 2_000,
    annual_expenses_eur: 24_000,
    target_eur: 600_000,
    extended: false,
  });
});

test("returns the current point when the target is already funded", () => {
  const plan = calculateFirePlan(
    1_000,
    2.11,
    [
      { date: "2026-09-22", projected_value_eur: 350_000, months_ahead: 0 },
    ],
    {},
  );

  assert.equal(plan.currentTargetEur, 300_000);
  assert.equal(plan.retirementTargetEur, 300_000);
  assert.equal(plan.achievement.months_ahead, 0);
  assert.equal(plan.yearsRemaining, 0);
  assert.equal(formatFireProjection(plan), "Funded now");
});

test("rounds partial remaining years up and rejects invalid month counts", () => {
  assert.equal(fireYearsRemaining(1), 1);
  assert.equal(fireYearsRemaining(12), 1);
  assert.equal(fireYearsRemaining(13), 2);
  assert.equal(fireYearsRemaining(-1), undefined);
  assert.equal(fireYearsRemaining(Number.POSITIVE_INFINITY), undefined);
});

test("extends the same projection assumptions beyond the displayed 25 years", () => {
  const plan = calculateFirePlan(
    5_000,
    0,
    [
      { date: "2026-09-22", projected_value_eur: 25_000, months_ahead: 0 },
      { date: "2051-09-22", projected_value_eur: 700_000, months_ahead: 300 },
    ],
    {
      current_date: "2026-09-22",
      current_value_eur: 25_000,
      monthly_return_rate: 0.005,
      avg_monthly_net_deposit_eur: 1_000,
      projection_months: 300,
    },
  );

  assert.equal(plan.currentTargetEur, 1_500_000);
  assert.equal(plan.achievement.date, "2060-07-23");
  assert.equal(plan.achievement.months_ahead, 406);
  assert.equal(plan.yearsRemaining, 34);
  assert.equal(plan.achievement.extended, true);
  assert.ok(plan.achievement.projected_value_eur >= plan.retirementTargetEur);
});

test("inflates current expenses and delays FIRE until the moving target is reached", () => {
  let value = 200_000;
  const projection = Array.from({ length: 301 }, (_, monthsAhead) => {
    if (monthsAhead > 0) {
      value = value * 1.005 + 1_000;
    }
    return {
      date: `${2026 + Math.floor(monthsAhead / 12)}-09-22`,
      projected_value_eur: value,
      months_ahead: monthsAhead,
    };
  });
  const summary = {
    current_date: "2026-09-22",
    current_value_eur: 200_000,
    monthly_return_rate: 0.005,
    avg_monthly_net_deposit_eur: 1_000,
    projection_months: 300,
  };
  const unadjustedPlan = calculateFirePlan(1_000, 0, projection, summary);
  const adjustedPlan = calculateFirePlan(1_000, 3, projection, summary);

  assert.ok(
    adjustedPlan.achievement.months_ahead >
      unadjustedPlan.achievement.months_ahead,
  );
  assert.ok(adjustedPlan.retirementMonthlyExpensesEur > 1_000);
  assert.ok(adjustedPlan.retirementTargetEur > 300_000);
});

test("reports no achievement when fixed assumptions cannot reach the target", () => {
  const plan = calculateFirePlan(
    5_000,
    2.11,
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
  assert.equal(
    formatFireProjection(plan),
    "Not reached under current assumptions",
  );
});

test("requires positive finite monthly expenses", () => {
  assert.equal(calculateFirePlan("", 2.11, []), undefined);
  assert.equal(calculateFirePlan(0, 2.11, []), undefined);
  assert.equal(calculateFirePlan(-1, 2.11, []), undefined);
  assert.equal(
    calculateFirePlan(Number.POSITIVE_INFINITY, 2.11, []),
    undefined,
  );
});

test("requires a finite inflation percentage greater than negative 100", () => {
  assert.equal(calculateFirePlan(1_000, -100, []), undefined);
  assert.equal(calculateFirePlan(1_000, Number.POSITIVE_INFINITY, []), undefined);
});
