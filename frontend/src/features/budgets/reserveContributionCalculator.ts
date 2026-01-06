export type ReserveContributionInput = {
  budgetYear: number;
  targetYear: number;
  estimatedCost: number;
  inflationRate: number;
  currentFunding: number;
};

export type ReserveContributionResult = ReserveContributionInput & {
  yearsRemaining: number;
  futureCost: number;
  remainingNeeded: number;
  annualContribution: number;
  futureCostRounded: number;
  remainingNeededRounded: number;
  annualContributionRounded: number;
  isValidTargetYear: boolean;
};

const roundToCents = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100;

export const calculateReserveContribution = ({
  budgetYear,
  targetYear,
  estimatedCost,
  inflationRate,
  currentFunding,
}: ReserveContributionInput): ReserveContributionResult => {
  const yearsRemainingRaw = targetYear - budgetYear;
  const isValidTargetYear = yearsRemainingRaw > 0;
  const yearsRemaining = Math.max(yearsRemainingRaw, 0);
  const futureCost = estimatedCost * Math.pow(1 + inflationRate, yearsRemaining);
  const remainingNeeded = Math.max(futureCost - currentFunding, 0);
  const annualContribution = isValidTargetYear && yearsRemaining > 0 ? remainingNeeded / yearsRemaining : 0;

  return {
    budgetYear,
    targetYear,
    estimatedCost,
    inflationRate,
    currentFunding,
    yearsRemaining,
    futureCost,
    remainingNeeded,
    annualContribution,
    futureCostRounded: roundToCents(futureCost),
    remainingNeededRounded: roundToCents(remainingNeeded),
    annualContributionRounded: roundToCents(annualContribution),
    isValidTargetYear,
  };
};
