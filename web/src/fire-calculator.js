export const FIRE_EXPENSE_MULTIPLE = 25;
export const FIRE_WITHDRAWAL_RATE = 0.04;
const AVG_DAYS_PER_MONTH = 365.25 / 12;
const MILLISECONDS_PER_DAY = 86_400_000;

export function fireYearsRemaining(monthsAhead) {
  const months = Number(monthsAhead);

  if (!Number.isFinite(months) || months < 0) {
    return undefined;
  }

  return Math.ceil(months / 12);
}

export function formatFireProjection(plan) {
  const achievement = plan?.achievement;

  if (!achievement) {
    return "Not reached under current assumptions";
  }
  if (achievement.months_ahead === 0) {
    return "Funded now";
  }

  const yearsRemaining = plan.yearsRemaining;
  const unit = yearsRemaining === 1 ? "year" : "years";
  return `${String(achievement.date).slice(0, 4)} (${yearsRemaining} ${unit} remaining)`;
}

function projectedDate(currentDate, monthsAhead) {
  const start = Date.parse(`${currentDate}T00:00:00Z`);

  if (!Number.isFinite(start)) {
    return undefined;
  }

  const date = new Date(
    start +
      Math.round(monthsAhead * AVG_DAYS_PER_MONTH) * MILLISECONDS_PER_DAY,
  );

  return Number.isFinite(date.getTime())
    ? date.toISOString().slice(0, 10)
    : undefined;
}

function fireValuesAtMonth(monthlyExpensesEur, annualInflation, monthsAhead) {
  const inflationMultiplier = (1 + annualInflation) ** (monthsAhead / 12);
  const monthlyExpenses = monthlyExpensesEur * inflationMultiplier;
  const annualExpenses = monthlyExpenses * 12;

  return {
    monthly_expenses_eur: monthlyExpenses,
    annual_expenses_eur: annualExpenses,
    target_eur: annualExpenses * FIRE_EXPENSE_MULTIPLE,
  };
}

function findAchievement(
  monthlyExpensesEur,
  annualInflation,
  projection,
  summary,
) {
  for (const point of projection) {
    const monthsAhead = Number(point.months_ahead);
    const projectedValue = Number(point.projected_value_eur);
    const fireValues = fireValuesAtMonth(
      monthlyExpensesEur,
      annualInflation,
      monthsAhead,
    );

    if (projectedValue >= fireValues.target_eur) {
      return { ...point, ...fireValues, extended: false };
    }
  }

  const monthlyReturn = Number(summary?.monthly_return_rate ?? 0);
  const monthlyDeposit = Number(summary?.avg_monthly_net_deposit_eur);
  const currentDate = summary?.current_date;
  const projectionMonths = Number(summary?.projection_months ?? 0);
  let value = Number(summary?.current_value_eur);
  let month = 0;
  let fireValues = fireValuesAtMonth(
    monthlyExpensesEur,
    annualInflation,
    month,
  );
  let previousFundingRatio = value / fireValues.target_eur;
  const portfolioGrowthFactor = 1 + monthlyReturn;
  const monthlyInflationFactor = (1 + annualInflation) ** (1 / 12);

  if (
    !Number.isFinite(value) ||
    !Number.isSafeInteger(month) ||
    !Number.isFinite(monthlyReturn) ||
    monthlyReturn <= -1 ||
    !Number.isFinite(monthlyDeposit) ||
    !currentDate ||
    !Number.isFinite(previousFundingRatio)
  ) {
    return undefined;
  }

  while (Number.isSafeInteger(month)) {
    month += 1;
    value = Math.max(0, value * portfolioGrowthFactor + monthlyDeposit);
    fireValues = fireValuesAtMonth(
      monthlyExpensesEur,
      annualInflation,
      month,
    );

    if (!Number.isFinite(fireValues.target_eur)) {
      return undefined;
    }

    if (value >= fireValues.target_eur) {
      const date = projectedDate(currentDate, month);
      return date
        ? {
            date,
            projected_value_eur: value,
            months_ahead: month,
            extended: month > projectionMonths,
            ...fireValues,
          }
        : undefined;
    }

    if (!Number.isFinite(value) || (value === 0 && monthlyDeposit <= 0)) {
      return undefined;
    }

    const fundingRatio = value / fireValues.target_eur;
    // When the target grows at least as quickly as the portfolio and the
    // funding ratio has started falling, fixed contributions cannot create a
    // later recovery: the ratio has passed its single possible peak.
    if (
      monthlyInflationFactor >= 1 &&
      portfolioGrowthFactor <= monthlyInflationFactor &&
      fundingRatio <= previousFundingRatio
    ) {
      return undefined;
    }
    previousFundingRatio = fundingRatio;
  }

  return undefined;
}

export function calculateFirePlan(
  monthlyExpensesEur,
  expectedInflationPct,
  projection,
  summary,
) {
  const monthlyExpenses = Number(monthlyExpensesEur);
  const inflationPct = Number(expectedInflationPct);

  if (
    !Number.isFinite(monthlyExpenses) ||
    monthlyExpenses <= 0 ||
    !Number.isFinite(inflationPct) ||
    inflationPct <= -100
  ) {
    return undefined;
  }

  const annualInflation = inflationPct / 100;
  const annualExpensesEur = monthlyExpenses * 12;
  const currentTargetEur = annualExpensesEur * FIRE_EXPENSE_MULTIPLE;

  if (
    !Number.isFinite(annualExpensesEur) ||
    !Number.isFinite(currentTargetEur)
  ) {
    return undefined;
  }

  const achievement = findAchievement(
    monthlyExpenses,
    annualInflation,
    projection,
    summary,
  );
  const retirementTargetEur = achievement?.target_eur;
  const annualWithdrawalEur = retirementTargetEur
    ? retirementTargetEur * FIRE_WITHDRAWAL_RATE
    : undefined;

  return {
    monthlyExpensesEur: monthlyExpenses,
    annualExpensesEur,
    expectedInflationPct: inflationPct,
    currentTargetEur,
    retirementMonthlyExpensesEur: achievement?.monthly_expenses_eur,
    retirementAnnualExpensesEur: achievement?.annual_expenses_eur,
    retirementTargetEur,
    annualWithdrawalEur,
    monthlyWithdrawalEur: annualWithdrawalEur
      ? annualWithdrawalEur / 12
      : undefined,
    yearsRemaining: achievement
      ? fireYearsRemaining(achievement.months_ahead)
      : undefined,
    achievement,
  };
}
