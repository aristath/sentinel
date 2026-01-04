import { Modal } from '@mantine/core';
import { SecurityChart } from '../charts/SecurityChart';
import { useAppStore } from '../../stores/appStore';

export function SecurityChartModal() {
  const { showSecurityChart, selectedSecuritySymbol, selectedSecurityIsin, closeSecurityChartModal } = useAppStore();

  const closeModal = () => {
    closeSecurityChartModal();
  };

  return (
    <Modal
      opened={showSecurityChart}
      onClose={closeModal}
      title="Security Chart"
      size="xl"
    >
      {selectedSecurityIsin && (
        <SecurityChart
          isin={selectedSecurityIsin}
          symbol={selectedSecuritySymbol}
          onClose={closeModal}
        />
      )}
    </Modal>
  );
}

