import { Badge, Button, Card, Group, Modal, RingProgress, SimpleGrid, Stack, Text } from '@mantine/core';

import { PortfolioWeightControls } from './PortfolioWeightControls';
import { SecurityMLHistoryChart } from './SecurityMLHistoryChart';

export function MLTuningModal({
  opened,
  onClose,
  securities = [],
  weightsDraft,
  weightsBaseline,
  onWeightChange,
  onSaveWeights,
  onResetWeights,
  isSavingWeights = false,
  weightsError = '',
  onResetRetrain,
  isResetRetraining = false,
  resetStatus = null,
  securityOverlaysMap = {},
}) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      fullScreen
      title={
        <Group gap="sm">
          <Text fw={600}>ML Tuning</Text>
          <Badge size="sm" variant="light">{securities.length} securities</Badge>
        </Group>
      }
      withCloseButton
      overlayProps={{ backgroundOpacity: 0.65, blur: 2 }}
    >
      <Stack gap="md">
        <Card withBorder shadow="sm">
          <Group justify="space-between" align="flex-start" mb="sm">
            <Stack gap={2}>
              <Text fw={600} size="sm">Global Prediction Weights</Text>
              <Text size="xs" c="dimmed">Adjust sliders to preview live projection changes on all security cards.</Text>
            </Stack>
            {resetStatus?.running ? (
              <Group gap="xs">
                <RingProgress
                  size={34}
                  thickness={4}
                  sections={[
                    {
                      value: resetStatus.models_total
                        ? (resetStatus.models_current / resetStatus.models_total) * 100
                        : (resetStatus.current_step / Math.max(1, resetStatus.total_steps || 1)) * 100,
                      color: 'orange',
                    },
                  ]}
                />
                <Text size="xs" c="dimmed" maw={220}>
                  {resetStatus.models_total
                    ? `Retraining ${resetStatus.current_symbol} (${resetStatus.models_current}/${resetStatus.models_total})`
                    : `Retraining: ${resetStatus.step_name}`}
                </Text>
              </Group>
            ) : (
              <Button
                size="xs"
                color="orange"
                variant="light"
                onClick={onResetRetrain}
                loading={isResetRetraining}
              >
                Reset & Retrain Models
              </Button>
            )}
          </Group>

          <PortfolioWeightControls
            opened
            onToggle={() => {}}
            draftWeights={weightsDraft}
            baselineWeights={weightsBaseline}
            onWeightChange={onWeightChange}
            onSave={onSaveWeights}
            onReset={onResetWeights}
            isSaving={isSavingWeights}
            error={weightsError}
            showToggle={false}
          />
        </Card>

        <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md" verticalSpacing="md">
          {securities.map((security) => {
            const history = securityOverlaysMap?.[security.symbol] || [];
            return (
              <Card key={security.symbol} withBorder shadow="sm" p="sm">
                <Group justify="space-between" mb="xs">
                  <Stack gap={0}>
                    <Text size="sm" fw={600}>{security.symbol}</Text>
                    <Text size="xs" c="dimmed" lineClamp={1}>{security.name || security.symbol}</Text>
                  </Stack>
                  {security.ml_enabled === 1 ? (
                    <Badge size="xs" color="blue" variant="light">ML On</Badge>
                  ) : (
                    <Badge size="xs" variant="default">Wavelet</Badge>
                  )}
                </Group>

                <SecurityMLHistoryChart
                  snapshots={history}
                  weightsDraft={weightsDraft}
                  height={190}
                />
              </Card>
            );
          })}
        </SimpleGrid>
      </Stack>
    </Modal>
  );
}
