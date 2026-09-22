export const FIRE_EXPENSE_MULTIPLE = 25;
export const FIRE_WITHDRAWAL_RATE = 0.04;
const AVG_DAYS_PER_MONTH = 365.25 / 12;
const MILLISECONDS_PER_DAY = 86_400_000;

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

function monthsToTarget(currentValue, targetEur, monthlyReturn, monthlyDeposit) {
  const firstMonthValue = Math.max(
    0,
    currentValue * (1 + monthlyReturn) + monthlyDeposit,
  );

  if (firstMonthValue <= currentValue) {
    return undefined;
  }

  if (monthlyReturn === 0) {
    return Math.ceil((targetEur - currentValue) / monthlyDeposit);
  }

  const fixedPoint = -monthlyDeposit / monthlyReturn;
  if (monthlyReturn < 0 && targetEur >= fixedPoint) {
    return undefined;
  }

  const ratio = (targetEur - fixedPoint) / (currentValue - fixedPoint);
  const months = Math.ceil(
    Math.log(ratio) / Math.log(1 + monthlyReturn),
  );

  return Number.isSafeInteger(months) && months > 0 ? months : undefined;
}

function valueAtMonth(currentValue, monthlyReturn, monthlyDeposit, month) {
  if (monthlyReturn === 0) {
    return currentValue + monthlyDeposit * month;
  }

  const growth = (1 + monthlyReturn) ** month;
  return (
    currentValue * growth +
    monthlyDeposit * ((growth - 1) / monthlyReturn)
  );
}

function findAchievement(targetEur, projection, summary) {
  const available = projection.find(
    (point) => Number(point.projected_value_eur) >= targetEur,
  );

  if (available) {
    return available;
  }

  const currentValue = Number(summary?.current_value_eur);
  const monthlyReturn = Number(summary?.monthly_return_rate ?? 0);
  const monthlyDeposit = Number(summary?.avg_monthly_net_deposit_eur);
  const currentDate = summary?.current_date;
  const projectionMonths = Number(summary?.projection_months ?? 0);

  if (
    !Number.isFinite(currentValue) ||
    !Number.isFinite(monthlyReturn) ||
    monthlyReturn <= -1 ||
    !Number.isFinite(monthlyDeposit) ||
    !currentDate
  ) {
    return undefined;
  }

  const month = monthsToTarget(
    currentValue,
    targetEur,
    monthlyReturn,
    monthlyDeposit,
  );
  const date = month ? projectedDate(currentDate, month) : undefined;

  return date
    ? {
        date,
        projected_value_eur: valueAtMonth(
          currentValue,
          monthlyReturn,
          monthlyDeposit,
          month,
        ),
        months_ahead: month,
        extended: month > projectionMonths,
      }
    : undefined;
}

export function calculateFirePlan(monthlyExpensesEur, projection, summary) {
  const monthlyExpenses = Number(monthlyExpensesEur);

  if (!Number.isFinite(monthlyExpenses) || monthlyExpenses <= 0) {
    return undefined;
  }

  const annualExpensesEur = monthlyExpenses * 12;
  const targetEur = annualExpensesEur * FIRE_EXPENSE_MULTIPLE;
  const annualWithdrawalEur = targetEur * FIRE_WITHDRAWAL_RATE;
  const monthlyWithdrawalEur = annualWithdrawalEur / 12;

  if (
    !Number.isFinite(annualExpensesEur) ||
    !Number.isFinite(targetEur) ||
    !Number.isFinite(annualWithdrawalEur) ||
    !Number.isFinite(monthlyWithdrawalEur)
  ) {
    return undefined;
  }

  const achievement = findAchievement(targetEur, projection, summary);

  return {
    monthlyExpensesEur: monthlyExpenses,
    annualExpensesEur,
    targetEur,
    annualWithdrawalEur,
    monthlyWithdrawalEur,
    achievement,
  };
}
